from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile
from typing import Literal, get_args

from .canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    normalize_repository_path,
)
from .models import Gate1ArtifactIdentity


WritableArtifactKind = Literal[
    "baseline_definitions",
    "strategy_family_definitions",
    "deterministic_grids",
    "family_budget_policy",
    "durability_policy",
    "survivor_policy",
    "information_access_policy",
    "research_report",
    "phase4_preregistration_manifest",
]


class Gate1ArtifactError(RuntimeError):
    """Raised when immutable Gate 1 evidence cannot be safely stored."""


class Gate1ArtifactStore:
    def __init__(self, repository_root: Path, results_root: Path) -> None:
        try:
            repository = Path(repository_root).resolve(strict=True)
        except OSError as exc:
            raise Gate1ArtifactError("repository root must exist") from exc
        if not repository.is_dir():
            raise Gate1ArtifactError("repository root must be a directory")
        configured = Path(results_root)
        if not configured.is_absolute():
            configured = repository / configured
        try:
            configured_relative = configured.relative_to(repository)
        except ValueError:
            configured_relative = None
        if configured_relative is not None:
            current = repository
            for component in configured_relative.parts:
                current = current / component
                if current.is_symlink():
                    raise Gate1ArtifactError(
                        "results root contains a symlink component"
                    )
        try:
            relative = normalize_repository_path(repository, configured)
        except (OSError, ValueError) as exc:
            raise Gate1ArtifactError("results root must be repository constrained") from exc
        self._repository_root = repository
        self._results_root = repository.joinpath(*PurePosixPath(relative).parts)
        self._gate1_root = self._results_root / "phase4" / "gate1"

    @staticmethod
    def _validate_kind(kind: WritableArtifactKind) -> WritableArtifactKind:
        if kind not in get_args(WritableArtifactKind):
            raise Gate1ArtifactError(f"unsupported Gate 1 artifact kind: {kind}")
        return kind

    @staticmethod
    def _validate_filename(filename: str) -> str:
        if not isinstance(filename, str):
            raise Gate1ArtifactError("artifact filename must be a string")
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
            raise Gate1ArtifactError(
                "artifact filename must be one portable path component"
            )
        return filename

    def _assert_no_symlink(self, path: Path) -> None:
        try:
            relative = path.relative_to(self._repository_root)
        except ValueError as exc:
            raise Gate1ArtifactError("artifact path is outside repository") from exc
        current = self._repository_root
        for component in relative.parts:
            current = current / component
            if current.is_symlink():
                raise Gate1ArtifactError(
                    f"artifact path contains symlink component: {path}"
                )

    def _identity(
        self,
        kind: WritableArtifactKind,
        destination: Path,
        payload: bytes,
    ) -> Gate1ArtifactIdentity:
        content_sha256 = sha256(payload).hexdigest()
        relative = normalize_repository_path(self._repository_root, destination)
        envelope_sha256 = artifact_envelope_identity(
            content_sha256=content_sha256,
            kind=kind,
            path=relative,
        )
        return Gate1ArtifactIdentity(
            kind=kind,
            content_sha256=content_sha256,
            path=relative,
            sha256=envelope_sha256,
        )

    def _destination(
        self,
        kind: WritableArtifactKind,
        filename: str,
        content_sha256: str,
    ) -> Path:
        return self._gate1_root / kind / "sha256" / content_sha256 / filename

    def _publish(
        self,
        kind: WritableArtifactKind,
        filename: str,
        payload: bytes,
        *,
        final_commit: bool,
    ) -> Gate1ArtifactIdentity:
        guarded_kind = self._validate_kind(kind)
        guarded_filename = self._validate_filename(filename)
        content_sha256 = sha256(payload).hexdigest()
        destination = self._destination(
            guarded_kind, guarded_filename, content_sha256
        )
        try:
            normalize_repository_path(self._repository_root, destination)
        except (OSError, ValueError) as exc:
            raise Gate1ArtifactError("artifact destination is outside repository") from exc
        self._assert_no_symlink(destination)
        identity = self._identity(guarded_kind, destination, payload)

        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file():
                raise Gate1ArtifactError("immutable artifact destination is invalid")
            try:
                existing = destination.read_bytes()
            except OSError as exc:
                raise Gate1ArtifactError("immutable artifact is unreadable") from exc
            if existing != payload:
                raise Gate1ArtifactError("immutable artifact collision")
            if not final_commit:
                self.verify(identity)
            return identity

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise Gate1ArtifactError("artifact parent cannot be created") from exc
        self._assert_no_symlink(destination)

        handle = -1
        temporary: Path | None = None
        try:
            handle, temporary_name = tempfile.mkstemp(
                prefix=".tmp-gate1-", dir=destination.parent
            )
            temporary = Path(temporary_name)
            with os.fdopen(handle, "wb") as stream:
                handle = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if destination.is_symlink() or not destination.is_file():
                    raise Gate1ArtifactError(
                        "immutable artifact destination is invalid"
                    )
                if destination.read_bytes() != payload:
                    raise Gate1ArtifactError("immutable artifact collision")
            else:
                temporary.unlink()
                temporary = None
        except Gate1ArtifactError:
            raise
        except OSError as exc:
            raise Gate1ArtifactError("immutable artifact write failed") from exc
        finally:
            if handle >= 0:
                os.close(handle)
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as exc:
                    raise Gate1ArtifactError(
                        "temporary artifact cleanup failed"
                    ) from exc

        if not final_commit:
            self.verify(identity)
        return identity

    def write_json(
        self,
        kind: WritableArtifactKind,
        filename: str,
        payload: object,
    ) -> Gate1ArtifactIdentity:
        try:
            encoded = canonical_json_bytes(payload)
        except (TypeError, ValueError) as exc:
            raise Gate1ArtifactError("artifact payload is not canonical JSON") from exc
        return self._publish(kind, filename, encoded, final_commit=False)

    def write_bytes(
        self,
        kind: WritableArtifactKind,
        filename: str,
        payload: bytes,
    ) -> Gate1ArtifactIdentity:
        if not isinstance(payload, bytes):
            raise Gate1ArtifactError("artifact payload must be bytes")
        return self._publish(kind, filename, payload, final_commit=False)

    def commit_json(
        self,
        kind: Literal["phase4_preregistration_manifest"],
        filename: str,
        payload: object,
    ) -> Gate1ArtifactIdentity:
        if kind != "phase4_preregistration_manifest":
            raise Gate1ArtifactError("final commit kind must be the Gate 1 manifest")
        try:
            encoded = canonical_json_bytes(payload)
        except (TypeError, ValueError) as exc:
            raise Gate1ArtifactError("artifact payload is not canonical JSON") from exc
        return self._publish(kind, filename, encoded, final_commit=True)

    def verify(self, identity: Gate1ArtifactIdentity) -> bytes:
        if identity.kind not in get_args(WritableArtifactKind):
            raise Gate1ArtifactError("artifact kind is not writable Gate 1 evidence")
        destination = self._repository_root.joinpath(
            *PurePosixPath(identity.path).parts
        )
        self._assert_no_symlink(destination)
        try:
            payload = destination.read_bytes()
        except OSError as exc:
            raise Gate1ArtifactError("artifact is unreadable") from exc
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise Gate1ArtifactError("artifact content digest mismatch")
        expected = self._identity(identity.kind, destination, payload)
        if expected != identity:
            raise Gate1ArtifactError("artifact envelope identity mismatch")
        return payload
