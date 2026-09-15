from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import tempfile

from investment_tracker.quant.phase4.gate3.filesystem import contained_path, resolve_repository_root
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity, Gate3AuthorityError
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    normalize_repository_path,
)

from .campaign import TrialRecord


class TrialEvidenceStore:
    """Immutable synthetic/future trial evidence; preparation writes no real trials."""

    def __init__(self, repository_root: Path) -> None:
        try:
            self.root = resolve_repository_root(repository_root, code="ARTIFACT_PATH_INVALID")
            self.base = contained_path(
                self.root,
                ("results", "phase4", "gate3", "campaign", "trial_record"),
                code="ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("ARTIFACT_PATH_INVALID: redirect or escape rejected") from exc

    def _path(self, content: str) -> Path:
        try:
            return contained_path(
                self.root,
                ("results", "phase4", "gate3", "campaign", "trial_record", "sha256", content, "record.json"),
                code="ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("ARTIFACT_PATH_INVALID: redirect or escape rejected") from exc

    def write(self, record: TrialRecord) -> ArtifactIdentity:
        if not isinstance(record, TrialRecord):
            raise ValueError("TRIAL_RECORD_INVALID: typed evidence required")
        payload = canonical_json_bytes(record.model_dump(mode="json"))
        content = sha256(payload).hexdigest()
        destination = self._path(content)
        relative = normalize_repository_path(self.root, destination)
        identity = ArtifactIdentity(
            kind="phase4_gate3_trial_record",
            content_sha256=content,
            path=relative,
            sha256=artifact_envelope_identity(
                content_sha256=content,
                kind="phase4_gate3_trial_record",
                path=relative,
            ),
        )
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != payload:
                raise ValueError("IMMUTABLE_ARTIFACT_COLLISION: unequal content at fixed address")
            return identity
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._path(content)
        handle, temporary_name = tempfile.mkstemp(prefix=".tmp-gate3-trial-", dir=destination.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != payload:
                    raise ValueError("IMMUTABLE_ARTIFACT_COLLISION: concurrent unequal content")
        finally:
            temporary.unlink(missing_ok=True)
        return identity

    def verify(self, identity: ArtifactIdentity) -> dict[str, object]:
        if not isinstance(identity, ArtifactIdentity) or identity.kind != "phase4_gate3_trial_record":
            raise ValueError("TRIAL_ARTIFACT_INVALID: exact typed identity required")
        if identity.sha256 != artifact_envelope_identity(
            content_sha256=identity.content_sha256,
            kind=identity.kind,
            path=identity.path,
        ):
            raise ValueError("TRIAL_ARTIFACT_INVALID: artifact envelope changed")
        relative = PurePosixPath(identity.path)
        expected_prefix = PurePosixPath("results/phase4/gate3/campaign/trial_record/sha256")
        if relative.parts[: len(expected_prefix.parts)] != expected_prefix.parts or relative.name != "record.json":
            raise ValueError("TRIAL_ARTIFACT_INVALID: noncanonical path")
        destination = self._path(identity.content_sha256)
        if normalize_repository_path(self.root, destination) != identity.path:
            raise ValueError("TRIAL_ARTIFACT_INVALID: content-addressed path mismatch")
        payload = destination.read_bytes()
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise ValueError("TRIAL_ARTIFACT_INVALID: exact bytes changed")
        parsed = json.loads(payload)
        if canonical_json_bytes(parsed) != payload:
            raise ValueError("TRIAL_ARTIFACT_INVALID: noncanonical JSON")
        return TrialRecord.model_validate(parsed).model_dump(mode="json")
