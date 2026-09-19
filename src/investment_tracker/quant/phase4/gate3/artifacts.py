from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import tempfile

from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    normalize_repository_path,
)

from .models import ArtifactIdentity, Gate3AuthorityError
from .filesystem import contained_path, resolve_repository_root


FILENAMES = {
    "fold_authority": "authority.json",
    "regime_authority": "authority.json",
    "gate3_authority_manifest": "manifest.json",
}


class Gate3ArtifactStore:
    def __init__(self, repository_root: Path) -> None:
        self.root = resolve_repository_root(
            repository_root, code="ARTIFACT_PATH_INVALID"
        )
        self.output_root = self.root / "results" / "phase4" / "gate3"
        self._assert_no_symlink(self.output_root)

    def _assert_no_symlink(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise Gate3AuthorityError("ARTIFACT_PATH_INVALID: path escaped repository") from exc
        contained_path(
            self.root,
            tuple(relative.parts),
            code="ARTIFACT_PATH_INVALID",
        )

    def _identity(self, kind: str, destination: Path, payload: bytes) -> ArtifactIdentity:
        content = sha256(payload).hexdigest()
        relative = normalize_repository_path(self.root, destination)
        return ArtifactIdentity(
            kind=kind,
            content_sha256=content,
            path=relative,
            sha256=artifact_envelope_identity(
                content_sha256=content, kind=kind, path=relative
            ),
        )

    def write_json(self, kind: str, payload: object, *, final: bool = False) -> ArtifactIdentity:
        if kind not in FILENAMES:
            raise Gate3AuthorityError("ARTIFACT_KIND_INVALID: unsupported kind")
        if (kind == "gate3_authority_manifest") != final:
            raise Gate3AuthorityError("ARTIFACT_ORDER_INVALID: manifest must be the final write")
        encoded = canonical_json_bytes(payload)
        content = sha256(encoded).hexdigest()
        destination = self.output_root / kind / "sha256" / content / FILENAMES[kind]
        self._assert_no_symlink(destination)
        identity = self._identity(kind, destination, encoded)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != encoded:
                raise Gate3AuthorityError("IMMUTABLE_ARTIFACT_COLLISION: destination differs")
            return identity
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._assert_no_symlink(destination)
        handle, temporary_name = tempfile.mkstemp(prefix=".tmp-gate3-", dir=destination.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != encoded:
                    raise Gate3AuthorityError("IMMUTABLE_ARTIFACT_COLLISION: concurrent destination differs")
            temporary.unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)
        return identity

    def verify(self, identity: ArtifactIdentity) -> bytes:
        path = self.root.joinpath(*PurePosixPath(identity.path).parts)
        self._assert_no_symlink(path)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise Gate3AuthorityError("AUTHORITY_ARTIFACT_MISSING: referenced artifact unavailable") from exc
        expected = self._identity(identity.kind, path, payload)
        if expected != identity:
            raise Gate3AuthorityError("AUTHORITY_ARTIFACT_MISMATCH: referenced artifact changed")
        return payload
