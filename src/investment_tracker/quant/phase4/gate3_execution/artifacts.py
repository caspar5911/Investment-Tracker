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


METHOD_FILENAMES = {
    "baseline_sleeve_method": "method.json",
    "regime_return_method": "method.json",
    "gate3_execution_methodology_manifest": "manifest.json",
}


class MethodologyEvidenceStore:
    """Exact-byte, append-only methodology evidence under a fixed subtree."""

    def __init__(self, repository_root: Path) -> None:
        try:
            self.root = resolve_repository_root(repository_root, code="ARTIFACT_PATH_INVALID")
            contained_path(
                self.root, ("results", "phase4", "gate3", "execution_methodology"),
                code="ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("ARTIFACT_PATH_INVALID: redirect or escape rejected") from exc

    def _path(self, kind: str, content: str) -> Path:
        if kind not in METHOD_FILENAMES or len(content) != 64 or any(ch not in "0123456789abcdef" for ch in content):
            raise ValueError("ARTIFACT_IDENTITY_INVALID: unsupported kind or digest")
        parts = (
            "results", "phase4", "gate3", "execution_methodology", kind,
            "sha256", content, METHOD_FILENAMES[kind],
        )
        try:
            return contained_path(self.root, parts, code="ARTIFACT_PATH_INVALID")
        except Gate3AuthorityError as exc:
            raise ValueError("ARTIFACT_PATH_INVALID: redirect or escape rejected") from exc

    def _identity(self, kind: str, content: str) -> ArtifactIdentity:
        destination = self._path(kind, content)
        relative = normalize_repository_path(self.root, destination)
        return ArtifactIdentity(
            kind=kind, content_sha256=content, path=relative,
            sha256=artifact_envelope_identity(content_sha256=content, kind=kind, path=relative),
        )

    def write_json(self, kind: str, document: object, *, final: bool = False) -> ArtifactIdentity:
        if (kind == "gate3_execution_methodology_manifest") != final:
            raise ValueError("ARTIFACT_ORDER_INVALID: manifest must be final")
        payload = canonical_json_bytes(document)
        content = sha256(payload).hexdigest()
        destination = self._path(kind, content)
        identity = self._identity(kind, content)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != payload:
                raise ValueError("IMMUTABLE_ARTIFACT_COLLISION: unequal fixed-address content")
            return identity
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._path(kind, content)
        handle, temporary_name = tempfile.mkstemp(prefix=".tmp-gate3-method-", dir=destination.parent)
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

    def verify(self, identity: ArtifactIdentity) -> bytes:
        if not isinstance(identity, ArtifactIdentity):
            raise ValueError("ARTIFACT_IDENTITY_INVALID: typed identity required")
        destination = self._path(identity.kind, identity.content_sha256)
        expected = self._identity(identity.kind, identity.content_sha256)
        if identity != expected:
            raise ValueError("ARTIFACT_IDENTITY_INVALID: noncanonical path or envelope")
        try:
            payload = destination.read_bytes()
        except OSError as exc:
            raise ValueError("ARTIFACT_BYTES_INVALID: referenced bytes missing") from exc
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise ValueError("ARTIFACT_BYTES_INVALID: content digest changed")
        try:
            parsed = json.loads(payload)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("ARTIFACT_BYTES_INVALID: invalid JSON") from exc
        if canonical_json_bytes(parsed) != payload:
            raise ValueError("ARTIFACT_BYTES_INVALID: noncanonical JSON")
        return payload


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
        # Pydantic model_copy(update=...) does not validate updates. Revalidate
        # before creating any bytes so a forged EXECUTED/result record cannot
        # be published under this preparation-only schema.
        record = TrialRecord.model_validate(record.model_dump(mode="json"))
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
