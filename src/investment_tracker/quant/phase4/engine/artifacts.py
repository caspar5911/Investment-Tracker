from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Literal, get_args

from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    normalize_repository_path,
)

from .models import GATE2_ARTIFACT_FILENAMES, Gate2ArtifactIdentity, Gate2ArtifactKind

MANIFEST_KIND: Literal["phase4_engine_manifest"] = "phase4_engine_manifest"
MARKDOWN_KIND: Literal["phase4_engine_report"] = "phase4_engine_report"


class Gate2ArtifactError(RuntimeError):
    """Raised when immutable Gate 2 evidence cannot be safely stored."""


class Gate2ArtifactStore:
    def __init__(self, repository_root: Path, results_root: Path) -> None:
        try:
            repository = Path(repository_root).resolve(strict=True)
        except OSError as exc:
            raise Gate2ArtifactError("repository root must exist") from exc
        if not repository.is_dir():
            raise Gate2ArtifactError("repository root must be a directory")
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
                    raise Gate2ArtifactError(
                        "results root contains a symlink component"
                    )
        try:
            relative = normalize_repository_path(repository, configured)
        except (OSError, ValueError) as exc:
            raise Gate2ArtifactError("results root must be repository constrained") from exc
        if PurePosixPath(relative).parts != ("results",):
            raise Gate2ArtifactError(
                "results root must be the repository results directory"
            )
        self._repository_root = repository
        self._results_root = repository.joinpath(*PurePosixPath(relative).parts)
        self._gate2_root = self._results_root / "phase4" / "gate2"

    @staticmethod
    def _validate_kind(kind: Gate2ArtifactKind) -> Gate2ArtifactKind:
        if kind not in get_args(Gate2ArtifactKind):
            raise Gate2ArtifactError(f"unsupported Gate 2 artifact kind: {kind}")
        return kind

    def _assert_no_symlink(self, path: Path) -> None:
        try:
            relative = path.relative_to(self._repository_root)
        except ValueError as exc:
            raise Gate2ArtifactError("artifact path is outside repository") from exc
        current = self._repository_root
        for component in relative.parts:
            current = current / component
            if current.is_symlink():
                raise Gate2ArtifactError(
                    f"artifact path contains symlink component: {path}"
                )

    def _identity(
        self,
        kind: Gate2ArtifactKind,
        destination: Path,
        payload: bytes,
    ) -> Gate2ArtifactIdentity:
        content_sha256 = sha256(payload).hexdigest()
        relative = normalize_repository_path(self._repository_root, destination)
        envelope_sha256 = artifact_envelope_identity(
            content_sha256=content_sha256,
            kind=kind,
            path=relative,
        )
        return Gate2ArtifactIdentity(
            kind=kind,
            content_sha256=content_sha256,
            path=relative,
            sha256=envelope_sha256,
        )

    def _destination(
        self,
        kind: Gate2ArtifactKind,
        content_sha256: str,
    ) -> Path:
        return (
            self._gate2_root
            / kind
            / "sha256"
            / content_sha256
            / GATE2_ARTIFACT_FILENAMES[kind]
        )

    def _publish(
        self,
        kind: Gate2ArtifactKind,
        payload: bytes,
        *,
        final_commit: bool,
    ) -> Gate2ArtifactIdentity:
        guarded_kind = self._validate_kind(kind)
        if guarded_kind == MANIFEST_KIND and not final_commit:
            raise Gate2ArtifactError(
                "manifest is the final Gate 2 write and requires commit_manifest"
            )
        content_sha256 = sha256(payload).hexdigest()
        destination = self._destination(guarded_kind, content_sha256)
        try:
            normalize_repository_path(self._repository_root, destination)
        except (OSError, ValueError) as exc:
            raise Gate2ArtifactError("artifact destination is outside repository") from exc
        self._assert_no_symlink(destination)
        identity = self._identity(guarded_kind, destination, payload)

        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file():
                raise Gate2ArtifactError("immutable artifact destination is invalid")
            try:
                existing = destination.read_bytes()
            except OSError as exc:
                raise Gate2ArtifactError("immutable artifact is unreadable") from exc
            if existing != payload:
                raise Gate2ArtifactError("immutable artifact collision")
            if not final_commit:
                self.verify(identity)
            return identity

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise Gate2ArtifactError("artifact parent cannot be created") from exc
        self._assert_no_symlink(destination)

        handle = -1
        temporary: Path | None = None
        try:
            handle, temporary_name = tempfile.mkstemp(
                prefix=".tmp-gate2-", dir=destination.parent
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
                    raise Gate2ArtifactError(
                        "immutable artifact destination is invalid"
                    )
                if destination.read_bytes() != payload:
                    raise Gate2ArtifactError("immutable artifact collision")
            else:
                if final_commit:
                    # The manifest link is the final fallible publication.  A
                    # denied best-effort cleanup must not turn a visible valid
                    # seal into a reported failure.
                    orphan = temporary
                    temporary = None
                    try:
                        orphan.unlink()
                    except OSError:
                        pass
                else:
                    temporary.unlink()
                    temporary = None
        except Gate2ArtifactError:
            raise
        except OSError as exc:
            raise Gate2ArtifactError("immutable artifact write failed") from exc
        finally:
            if handle >= 0:
                os.close(handle)
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as exc:
                    raise Gate2ArtifactError(
                        "temporary artifact cleanup failed"
                    ) from exc

        if not final_commit:
            self.verify(identity)
        return identity

    def write_json(
        self,
        kind: Gate2ArtifactKind,
        payload: object,
    ) -> Gate2ArtifactIdentity:
        if kind == MARKDOWN_KIND:
            raise Gate2ArtifactError(
                "artifact kind phase4_engine_report requires exact UTF-8 "
                "Markdown bytes"
            )
        try:
            encoded = canonical_json_bytes(payload)
        except (TypeError, ValueError) as exc:
            raise Gate2ArtifactError("artifact payload is not canonical JSON") from exc
        return self._publish(kind, encoded, final_commit=False)

    def write_bytes(
        self,
        kind: Gate2ArtifactKind,
        payload: bytes,
    ) -> Gate2ArtifactIdentity:
        if not isinstance(payload, bytes):
            raise Gate2ArtifactError("artifact payload must be bytes")
        if kind != MARKDOWN_KIND:
            raise Gate2ArtifactError(
                "artifact bytes are reserved for the phase4_engine_report kind"
            )
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Gate2ArtifactError("artifact bytes must be UTF-8") from exc
        return self._publish(kind, payload, final_commit=False)

    def commit_manifest(self, payload: object) -> Gate2ArtifactIdentity:
        try:
            encoded = canonical_json_bytes(payload)
        except (TypeError, ValueError) as exc:
            raise Gate2ArtifactError("artifact payload is not canonical JSON") from exc
        return self._publish(MANIFEST_KIND, encoded, final_commit=True)

    def verify(self, identity: Gate2ArtifactIdentity) -> bytes:
        if identity.kind not in get_args(Gate2ArtifactKind):
            raise Gate2ArtifactError("artifact kind is not writable Gate 2 evidence")
        destination = self._repository_root.joinpath(
            *PurePosixPath(identity.path).parts
        )
        self._assert_no_symlink(destination)
        try:
            payload = destination.read_bytes()
        except OSError as exc:
            raise Gate2ArtifactError("artifact is unreadable") from exc
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise Gate2ArtifactError("artifact content digest mismatch")
        expected = self._identity(identity.kind, destination, payload)
        if expected != identity:
            raise Gate2ArtifactError("artifact envelope identity mismatch")
        return payload
