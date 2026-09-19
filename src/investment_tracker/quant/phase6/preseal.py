from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Generic, Literal, TypeVar
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.quant.phase5.authority import load_phase4_authority
from investment_tracker.quant.phase5.methodology import (
    SELECTED_BINDING_SHA256,
    SELECTED_CANDIDATE_ID,
    SELECTED_IMPLEMENTATION_SHA256,
)

T = TypeVar("T")

PHASE5_WAIVER_PATH = (
    "docs/superpowers/reports/2026-09-20-phase5-independent-source-waiver.md"
)


class Phase6HoldoutReuseError(RuntimeError):
    pass


class HoldoutRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["PHASE6-HOLDOUT-RELEASE-v1"]
    authority: Literal["INDEPENDENT_AUDIT"]
    status: Literal["FINAL_HOLDOUT_RELEASE_AUTHORIZED"]
    release_id: str = Field(min_length=1)
    holdout_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    one_time: Literal[True]

    @model_validator(mode="after")
    def validate_frozen_identity(self) -> "HoldoutRelease":
        if (
            self.candidate_id != SELECTED_CANDIDATE_ID
            or self.binding_sha256 != SELECTED_BINDING_SHA256
            or self.implementation_sha256 != SELECTED_IMPLEMENTATION_SHA256
        ):
            raise ValueError("PHASE6_RELEASE_FROZEN_IDENTITY_MISMATCH")
        return self


def load_release_envelope(path: Path) -> HoldoutRelease:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("PHASE6_RELEASE_INVALID") from exc
    if not isinstance(value, dict):
        raise ValueError("PHASE6_RELEASE_INVALID")
    return HoldoutRelease.model_validate(value)


def _safety() -> dict[str, object]:
    return {
        "final_holdout_accessed": False,
        "protected_symbols_accessed": [],
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "phase4_feedback_written": False,
        "phase5_feedback_written": False,
        "live_trading_capability": False,
        "phase7_started": False,
    }


def phase6_preflight(repository_root: Path) -> dict[str, object]:
    repository = Path(repository_root).resolve()
    _, _, binding = load_phase4_authority(repository)

    waiver = repository / PHASE5_WAIVER_PATH
    try:
        waiver_text = waiver.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("PHASE6_PHASE5_WAIVER_MISSING") from exc
    required = (
        "PHASE5_UNKNOWN_ABSTAIN",
        "INDEPENDENT_SOURCE_SNAPSHOT_MISSING",
        "OpenD-validated, independently unverified research evidence",
    )
    if any(value not in waiver_text for value in required):
        raise ValueError("PHASE6_PHASE5_WAIVER_IDENTITY_MISMATCH")

    return {
        "schema_version": "PHASE6-PREUNSEAL-READINESS-v1",
        "status": "PHASE6_READY_FOR_INDEPENDENT_AUDIT_RELEASE",
        "candidate_id": SELECTED_CANDIDATE_ID,
        "binding_sha256": binding.binding_sha256,
        "implementation_sha256": binding.implementation_sha256,
        "phase5_formal_status": "PHASE5_UNKNOWN_ABSTAIN",
        "phase5_limitation": "INDEPENDENT_SOURCE_SNAPSHOT_MISSING",
        "release_authority_required": "INDEPENDENT_AUDIT",
        "holdout_accessed": False,
        "safety": _safety(),
    }


def consume_released_holdout(
    release: HoldoutRelease,
    *,
    marker_directory: Path,
    payload_reader: Callable[[], T],
) -> T:
    # Validate again at the irreversible boundary even if the caller already
    # constructed the model elsewhere.
    release = HoldoutRelease.model_validate(release.model_dump(mode="json"))
    root = Path(marker_directory)
    root.mkdir(parents=True, exist_ok=True)
    marker = root / f"{release.release_id}.consumed.json"
    record = {
        "schema_version": "PHASE6-HOLDOUT-CONSUMPTION-v1",
        "status": "FINAL_HOLDOUT_CONSUMED",
        "release_id": release.release_id,
        "holdout_id": release.holdout_id,
        "candidate_id": release.candidate_id,
        "binding_sha256": release.binding_sha256,
        "implementation_sha256": release.implementation_sha256,
        "evaluation_contract_sha256": release.evaluation_contract_sha256,
        "holdout_bundle_sha256": release.holdout_bundle_sha256,
    }
    try:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump(record, handle, sort_keys=True, separators=(",", ":"))
    except FileExistsError as exc:
        raise Phase6HoldoutReuseError(
            f"final holdout release already consumed: {release.release_id}"
        ) from exc

    return payload_reader()
