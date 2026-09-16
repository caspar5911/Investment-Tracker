from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Literal, TypeVar

from pydantic import BaseModel

from investment_tracker.quant.phase4.gate3.filesystem import (
    contained_path,
    resolve_repository_root,
)
from investment_tracker.quant.phase4.gate3.models import (
    ArtifactIdentity,
    Gate3AuthorityError,
)
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    normalize_repository_path,
)

from .models import AttemptRecord, CampaignResultSet, PositionReceipt


T = TypeVar("T", bound=BaseModel)


class RunnerStateStore:
    """Deterministic no-overwrite position state; never discovers authority by listing."""

    def __init__(self, repository_root: Path) -> None:
        try:
            self.root = resolve_repository_root(
                repository_root,
                code="ARTIFACT_PATH_INVALID",
            )
            contained_path(
                self.root,
                ("results", "phase4", "gate3", "campaign"),
                code="ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("ARTIFACT_PATH_INVALID") from exc

    def _position_path(
        self,
        kind: Literal["attempt", "receipt"],
        position: int,
    ) -> Path:
        if (
            isinstance(position, bool)
            or not isinstance(position, int)
            or not 1 <= position <= 180
        ):
            raise ValueError("RUNNER_POSITION_INVALID")
        try:
            return contained_path(
                self.root,
                (
                    "results",
                    "phase4",
                    "gate3",
                    "campaign",
                    kind,
                    f"position-{position:04d}.json",
                ),
                code="ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("ARTIFACT_PATH_INVALID") from exc

    def _result_set_path(self) -> Path:
        try:
            return contained_path(
                self.root,
                ("results", "phase4", "gate3", "campaign", "result_set.json"),
                code="ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("ARTIFACT_PATH_INVALID") from exc

    def _identity(
        self,
        kind: str,
        path: Path,
        payload: bytes,
    ) -> ArtifactIdentity:
        content = sha256(payload).hexdigest()
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

    def _publish(self, path: Path, payload: bytes) -> None:
        if path.exists() or path.is_symlink():
            if (
                path.is_symlink()
                or not path.is_file()
                or path.read_bytes() != payload
            ):
                raise ValueError("IMMUTABLE_ARTIFACT_COLLISION")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.name == "result_set.json":
            checked = self._result_set_path()
        else:
            parent_kind = path.parent.name
            if parent_kind not in {"attempt", "receipt"}:
                raise ValueError("ARTIFACT_PATH_INVALID")
            position = int(path.stem.removeprefix("position-"))
            checked = self._position_path(parent_kind, position)
        if checked != path:
            raise ValueError("ARTIFACT_PATH_INVALID")
        handle, name = tempfile.mkstemp(
            prefix=".tmp-gate3-runner-",
            dir=path.parent,
        )
        temporary = Path(name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if (
                    path.is_symlink()
                    or not path.is_file()
                    or path.read_bytes() != payload
                ):
                    raise ValueError("IMMUTABLE_ARTIFACT_COLLISION")
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _payload(model: BaseModel) -> bytes:
        return canonical_json_bytes(model.model_dump(mode="json"))

    def _read_optional(
        self,
        path: Path,
        model: type[T],
        kind: str,
    ) -> tuple[T, ArtifactIdentity] | None:
        if path.is_symlink():
            raise ValueError("ARTIFACT_PATH_INVALID")
        if not path.exists():
            return None
        if not path.is_file():
            raise ValueError("ARTIFACT_PATH_INVALID")
        payload = path.read_bytes()
        try:
            parsed = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("ARTIFACT_BYTES_INVALID") from exc
        if canonical_json_bytes(parsed) != payload:
            raise ValueError("ARTIFACT_BYTES_INVALID")
        try:
            value = model.model_validate_json(payload)
        except ValueError as exc:
            raise ValueError("ARTIFACT_BYTES_INVALID") from exc
        if self._payload(value) != payload:
            raise ValueError("ARTIFACT_BYTES_INVALID")
        return value, self._identity(kind, path, payload)

    def write_attempt(self, record: AttemptRecord) -> ArtifactIdentity:
        if not isinstance(record, AttemptRecord):
            raise ValueError("RUNNER_ATTEMPT_INVALID")
        path = self._position_path("attempt", record.population_position)
        payload = self._payload(record)
        self._publish(path, payload)
        return self._identity("phase4_gate3_runner_attempt", path, payload)

    def read_attempt(
        self,
        position: int,
    ) -> tuple[AttemptRecord, ArtifactIdentity] | None:
        path = self._position_path("attempt", position)
        return self._read_optional(
            path,
            AttemptRecord,
            "phase4_gate3_runner_attempt",
        )

    def write_receipt(self, record: PositionReceipt) -> ArtifactIdentity:
        if not isinstance(record, PositionReceipt):
            raise ValueError("RUNNER_RECEIPT_INVALID")
        attempt = self.read_attempt(record.population_position)
        if record.result_status == "SKIPPED_FAMILY_STOP":
            if attempt is not None:
                raise ValueError("RUNNER_SKIPPED_ATTEMPT_INVALID")
        else:
            if attempt is None:
                raise ValueError("RUNNER_ATTEMPT_MISSING")
            attempted, _ = attempt
            if (
                attempted.population_position != record.population_position
                or attempted.candidate_id != record.candidate_id
                or attempted.trial_id != record.trial_id
            ):
                raise ValueError("RUNNER_RECEIPT_ATTEMPT_MISMATCH")
        path = self._position_path("receipt", record.population_position)
        payload = self._payload(record)
        self._publish(path, payload)
        return self._identity("phase4_gate3_runner_receipt", path, payload)

    def read_receipt(
        self,
        position: int,
    ) -> tuple[PositionReceipt, ArtifactIdentity] | None:
        path = self._position_path("receipt", position)
        return self._read_optional(
            path,
            PositionReceipt,
            "phase4_gate3_runner_receipt",
        )

    def write_result_set(
        self,
        result_set: CampaignResultSet,
    ) -> ArtifactIdentity:
        if not isinstance(result_set, CampaignResultSet):
            raise ValueError("RUNNER_RESULT_SET_INVALID")
        observed: list[ArtifactIdentity] = []
        for position in range(1, 181):
            found = self.read_receipt(position)
            if found is None:
                raise ValueError("RUNNER_ACCOUNTABILITY_INCOMPLETE")
            receipt, _ = found
            if receipt.population_position != position:
                raise ValueError("RUNNER_RECEIPT_POSITION_MISMATCH")
            if receipt.result_status == "CAMPAIGN_EXECUTION_FAILED":
                raise ValueError("RUNNER_CAMPAIGN_FAILED")
            if receipt.result_status == "SKIPPED_FAMILY_STOP":
                if self.read_attempt(position) is not None:
                    raise ValueError("RUNNER_SKIPPED_ATTEMPT_INVALID")
            else:
                attempt = self.read_attempt(position)
                if attempt is None:
                    raise ValueError("RUNNER_ATTEMPT_MISSING")
                attempted, _ = attempt
                if (
                    attempted.runner_manifest != result_set.runner_manifest
                    or attempted.candidate_id != receipt.candidate_id
                    or attempted.trial_id != receipt.trial_id
                ):
                    raise ValueError("RUNNER_RESULT_SET_ATTEMPT_MISMATCH")
            observed.append(receipt.result_artifact)
        if tuple(observed) != result_set.result_artifacts:
            raise ValueError("RUNNER_RESULT_SET_RECEIPT_MISMATCH")
        path = self._result_set_path()
        payload = self._payload(result_set)
        self._publish(path, payload)
        return self._identity(
            "phase4_gate3_campaign_result_set",
            path,
            payload,
        )

    def read_result_set(
        self,
    ) -> tuple[CampaignResultSet, ArtifactIdentity] | None:
        path = self._result_set_path()
        return self._read_optional(
            path,
            CampaignResultSet,
            "phase4_gate3_campaign_result_set",
        )


__all__ = ("RunnerStateStore",)
