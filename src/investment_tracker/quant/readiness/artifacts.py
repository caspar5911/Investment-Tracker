from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile
from typing import Any, get_args

from .constants import ArtifactKind
from .hashing import (
    ArtifactIdentityError,
    artifact_identity,
    canonical_json_bytes,
    exact_file_sha256,
    normalize_repository_path,
)
from .models import ReadinessArtifactIdentity


class ReadinessArtifactIntegrityError(RuntimeError):
    """Raised when readiness artifact storage cannot preserve identity."""


class ReadinessArtifactStore:
    def __init__(self, repository_root: Path, results_root: Path) -> None:
        repository = Path(repository_root)
        try:
            repository = repository.resolve(strict=True)
        except OSError as exc:
            raise ReadinessArtifactIntegrityError(
                "repository root must be an existing directory"
            ) from exc
        if not repository.is_dir():
            raise ReadinessArtifactIntegrityError(
                "repository root must be an existing directory"
            )

        configured_results = Path(results_root)
        if not configured_results.is_absolute():
            configured_results = repository / configured_results
        try:
            results_relative = normalize_repository_path(
                repository,
                configured_results,
            )
        except ArtifactIdentityError as exc:
            raise ReadinessArtifactIntegrityError(
                f"results root must be repository-root constrained: {exc}"
            ) from exc

        self._repository_root = repository
        self._results_root = repository.joinpath(
            *PurePosixPath(results_relative).parts
        )
        self._readiness_root = self._results_root / "phase4" / "readiness"

    @staticmethod
    def _validate_kind(kind: ArtifactKind) -> ArtifactKind:
        if kind not in get_args(ArtifactKind):
            raise ReadinessArtifactIntegrityError(f"unknown artifact kind: {kind}")
        return kind

    @staticmethod
    def _validate_filename(filename: str) -> str:
        if not isinstance(filename, str):
            raise ReadinessArtifactIntegrityError("artifact filename must be a string")
        posix = PurePosixPath(filename)
        windows = PureWindowsPath(filename)
        if (
            not filename
            or filename in {".", ".."}
            or "\x00" in filename
            or "/" in filename
            or "\\" in filename
            or posix.is_absolute()
            or windows.is_absolute()
            or windows.drive
            or len(posix.parts) != 1
            or len(windows.parts) != 1
        ):
            raise ReadinessArtifactIntegrityError(
                "artifact filename must be one portable path component"
            )
        return filename

    def _normalize(self, path: Path) -> str:
        try:
            return normalize_repository_path(self._repository_root, path)
        except ArtifactIdentityError as exc:
            raise ReadinessArtifactIntegrityError(str(exc)) from exc

    def _destination(
        self,
        kind: ArtifactKind,
        filename: str,
        content_sha256: str,
    ) -> Path:
        return (
            self._readiness_root
            / kind
            / "sha256"
            / content_sha256
            / filename
        )

    def _identity_for(
        self,
        path: Path,
        kind: ArtifactKind,
        expected_bytes: bytes,
    ) -> ReadinessArtifactIdentity:
        try:
            identity = artifact_identity(self._repository_root, path, kind)
        except (ArtifactIdentityError, OSError, ValueError) as exc:
            raise ReadinessArtifactIntegrityError(
                f"artifact identity verification failed: {path}"
            ) from exc
        if identity.content_sha256 != exact_file_sha256(path):
            raise ReadinessArtifactIntegrityError("artifact content hash mismatch")
        try:
            actual_bytes = path.read_bytes()
        except OSError as exc:
            raise ReadinessArtifactIntegrityError(f"artifact unreadable: {path}") from exc
        if actual_bytes != expected_bytes:
            raise ReadinessArtifactIntegrityError(f"immutable artifact collision: {path}")
        self.verify(identity)
        return identity

    def _write_bytes(
        self,
        kind: ArtifactKind,
        filename: str,
        payload: bytes,
    ) -> ReadinessArtifactIdentity:
        guarded_kind = self._validate_kind(kind)
        guarded_filename = self._validate_filename(filename)
        content_sha256 = sha256(payload).hexdigest()
        destination = self._destination(
            guarded_kind,
            guarded_filename,
            content_sha256,
        )
        self._normalize(destination)

        if destination.exists() or destination.is_symlink():
            if destination.is_symlink():
                raise ReadinessArtifactIntegrityError(
                    f"artifact path contains symlink component: {destination}"
                )
            if not destination.is_file():
                raise ReadinessArtifactIntegrityError(
                    f"immutable artifact destination is non-regular: {destination}"
                )
            return self._identity_for(destination, guarded_kind, payload)

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ReadinessArtifactIntegrityError(
                f"artifact destination parent cannot be created: {destination.parent}"
            ) from exc
        self._normalize(destination)

        handle = -1
        temporary: Path | None = None
        try:
            handle, temporary_name = tempfile.mkstemp(
                prefix=".tmp-",
                dir=destination.parent,
            )
            temporary = Path(temporary_name)
            with os.fdopen(handle, "wb") as stream:
                handle = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if destination.exists() or destination.is_symlink():
                if not destination.is_file() or destination.is_symlink():
                    raise ReadinessArtifactIntegrityError(
                        f"immutable artifact destination is non-regular: {destination}"
                    )
                return self._identity_for(destination, guarded_kind, payload)
            os.replace(temporary, destination)
            temporary = None
        except ReadinessArtifactIntegrityError:
            raise
        except OSError as exc:
            raise ReadinessArtifactIntegrityError(
                f"immutable artifact write failed: {destination}"
            ) from exc
        finally:
            if handle >= 0:
                os.close(handle)
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as exc:
                    raise ReadinessArtifactIntegrityError(
                        f"temporary artifact cleanup failed: {temporary}"
                    ) from exc

        return self._identity_for(destination, guarded_kind, payload)

    def write_json(
        self,
        kind: ArtifactKind,
        filename: str,
        payload: object,
    ) -> ReadinessArtifactIdentity:
        try:
            encoded = canonical_json_bytes(payload)
        except (TypeError, ValueError) as exc:
            raise ReadinessArtifactIntegrityError(
                "readiness artifact payload is not canonical JSON"
            ) from exc
        return self._write_bytes(kind, filename, encoded)

    def write_text(
        self,
        kind: ArtifactKind,
        filename: str,
        text: str,
    ) -> ReadinessArtifactIdentity:
        if not isinstance(text, str):
            raise ReadinessArtifactIntegrityError("readiness artifact text must be a string")
        return self._write_bytes(kind, filename, text.encode("utf-8"))

    def verify(self, identity: ReadinessArtifactIdentity) -> Path:
        logical = PurePosixPath(identity.path)
        path = self._repository_root.joinpath(*logical.parts)
        expected = self._destination(
            identity.kind,
            logical.name,
            identity.content_sha256,
        )
        if path != expected:
            raise ReadinessArtifactIntegrityError(
                "artifact kind or content path does not match configured storage"
            )
        normalized = self._normalize(path)
        if normalized != identity.path:
            raise ReadinessArtifactIntegrityError("artifact path is not canonical")
        if not path.is_file() or path.is_symlink():
            raise ReadinessArtifactIntegrityError(
                f"artifact is missing or non-regular: {path}"
            )
        try:
            actual_content_sha256 = exact_file_sha256(path)
            actual_identity = artifact_identity(
                self._repository_root,
                path,
                identity.kind,
            )
        except (ArtifactIdentityError, OSError, ValueError) as exc:
            raise ReadinessArtifactIntegrityError(
                f"artifact verification failed: {path}"
            ) from exc
        if actual_content_sha256 != identity.content_sha256:
            raise ReadinessArtifactIntegrityError(
                "artifact content hash mismatch: "
                f"expected {identity.content_sha256}, got {actual_content_sha256}"
            )
        if actual_identity != identity:
            raise ReadinessArtifactIntegrityError("artifact envelope identity mismatch")
        return path

    def read_json(self, identity: ReadinessArtifactIdentity) -> Any:
        path = self.verify(identity)
        try:
            return json.loads(path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReadinessArtifactIntegrityError(
                f"artifact JSON is unreadable or invalid: {path}"
            ) from exc

    def read_text(self, identity: ReadinessArtifactIdentity) -> str:
        path = self.verify(identity)
        try:
            return path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ReadinessArtifactIntegrityError(
                f"artifact text is unreadable or not UTF-8: {path}"
            ) from exc
