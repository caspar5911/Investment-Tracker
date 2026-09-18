from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import TypeVar

from pydantic import BaseModel

from investment_tracker.quant.phase4.gate3.filesystem import (
    contained_path,
    resolve_repository_root,
)
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity, Gate3AuthorityError
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    normalize_repository_path,
)

from .models import Phase4Audit, Phase4Decision


T = TypeVar("T", bound=BaseModel)


class FinalizationArtifactStore:
    _KINDS = {
        "phase4_finalization_audit": ("audit", "audit.json", Phase4Audit),
        "phase4_finalization_decision": ("decision", "decision.json", Phase4Decision),
    }

    def __init__(self, repository_root: Path) -> None:
        try:
            self.root = resolve_repository_root(
                repository_root,
                code="PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID",
            )
            contained_path(
                self.root,
                ("results", "phase4", "finalization"),
                code="PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID") from exc

    @staticmethod
    def _payload(model: BaseModel) -> bytes:
        return canonical_json_bytes(model.model_dump(mode="json"))

    def _path(self, kind: str, content: str) -> Path:
        if kind not in self._KINDS or len(content) != 64 or any(
            char not in "0123456789abcdef" for char in content
        ):
            raise ValueError("ARTIFACT_IDENTITY_INVALID")
        directory, filename, _ = self._KINDS[kind]
        try:
            return contained_path(
                self.root,
                (
                    "results",
                    "phase4",
                    "finalization",
                    directory,
                    "sha256",
                    content,
                    filename,
                ),
                code="PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID") from exc

    def identity(self, kind: str, content: str) -> ArtifactIdentity:
        path = self._path(kind, content)
        relative = normalize_repository_path(self.root, path)
        return ArtifactIdentity(
            kind=kind,
            content_sha256=content,
            path=relative,
            sha256=artifact_envelope_identity(
                content_sha256=content,
                kind=kind,
                path=relative,
            ),
        )

    def _publish(self, identity: ArtifactIdentity, payload: bytes) -> None:
        destination = self._path(identity.kind, identity.content_sha256)
        if destination.exists() or destination.is_symlink():
            if (
                destination.is_symlink()
                or not destination.is_file()
                or destination.read_bytes() != payload
            ):
                raise ValueError("IMMUTABLE_ARTIFACT_COLLISION")
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        checked = self._path(identity.kind, identity.content_sha256)
        if checked != destination:
            raise ValueError("PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID")
        handle, name = tempfile.mkstemp(
            prefix=".tmp-phase4-finalization-",
            dir=destination.parent,
        )
        temporary = Path(name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if (
                    destination.is_symlink()
                    or not destination.is_file()
                    or destination.read_bytes() != payload
                ):
                    raise ValueError("IMMUTABLE_ARTIFACT_COLLISION")
        finally:
            temporary.unlink(missing_ok=True)

    def _write(self, kind: str, model: BaseModel) -> ArtifactIdentity:
        payload = self._payload(model)
        identity = self.identity(kind, sha256(payload).hexdigest())
        self._publish(identity, payload)
        return identity

    def _read(self, identity: ArtifactIdentity, model: type[T]) -> T:
        expected = self.identity(identity.kind, identity.content_sha256)
        if identity != expected:
            raise ValueError("ARTIFACT_IDENTITY_INVALID")
        path = self._path(identity.kind, identity.content_sha256)
        if path.is_symlink() or not path.is_file():
            raise ValueError("ARTIFACT_BYTES_INVALID")
        payload = path.read_bytes()
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise ValueError("ARTIFACT_BYTES_INVALID")
        try:
            parsed = json.loads(payload)
            if canonical_json_bytes(parsed) != payload:
                raise ValueError("noncanonical")
            value = model.model_validate(parsed, strict=True)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ValueError("ARTIFACT_BYTES_INVALID") from exc
        if self._payload(value) != payload:
            raise ValueError("ARTIFACT_BYTES_INVALID")
        return value

    def write_audit(self, audit: Phase4Audit) -> ArtifactIdentity:
        return self._write("phase4_finalization_audit", audit)

    def read_audit(self, identity: ArtifactIdentity) -> Phase4Audit:
        return self._read(identity, Phase4Audit)

    def write_decision(self, decision: Phase4Decision) -> ArtifactIdentity:
        return self._write("phase4_finalization_decision", decision)

    def read_decision(self, identity: ArtifactIdentity) -> Phase4Decision:
        return self._read(identity, Phase4Decision)
