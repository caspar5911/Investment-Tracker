from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from pydantic import Field, model_validator

from investment_tracker.quant.phase4.engine.models import Gate2Authority, Phase4EngineManifest
from investment_tracker.quant.phase4.gate3.models import FrozenGate3Model
from investment_tracker.quant.phase4.preregistration.canonical import trial_identity
from investment_tracker.quant.phase4.preregistration.grids import PHASE4_CAMPAIGN_ID


POPULATION_SHA256 = "15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3"


@dataclass(frozen=True)
class CandidateReference:
    population_position: int
    candidate_id: str
    trial_id: str
    family_id: str
    hypothesis_id: str
    parameter_tuple_sha256: str
    status: str = "UNATTEMPTED"


def _expected(authority: Gate2Authority, manifest: Phase4EngineManifest) -> tuple[CandidateReference, ...]:
    if not isinstance(authority, Gate2Authority) or not isinstance(manifest, Phase4EngineManifest):
        raise ValueError("CANDIDATE_POPULATION_MISMATCH: sealed authorities required")
    grids = authority.grids
    if (
        manifest.status != "PHASE4_ENGINE_SEALED"
        or manifest.gate1_manifest != authority.manifest_identity
        or manifest.candidate_population_sha256 != POPULATION_SHA256
        or grids.candidate_parameter_population_sha256 != POPULATION_SHA256
        or manifest.candidate_count != 180
        or authority.phase4_trials_consumed != 0
        or manifest.phase4_trials_consumed != 0
    ):
        raise ValueError("CANDIDATE_POPULATION_MISMATCH: frozen population identity differs")
    rows = tuple(
        CandidateReference(
            population_position=candidate.budget_position,
            candidate_id=candidate.candidate_id,
            trial_id=candidate.trial_id,
            family_id=candidate.family_id,
            hypothesis_id=candidate.hypothesis_id,
            parameter_tuple_sha256=candidate.parameter_tuple_sha256,
        )
        for candidate in grids.candidates
    )
    if (
        len(rows) != 180
        or tuple(item.population_position for item in rows) != tuple(range(1, 181))
        or len({item.candidate_id for item in rows}) != 180
        or len({item.trial_id for item in rows}) != 180
        or any(item.trial_id != trial_identity(PHASE4_CAMPAIGN_ID, item.candidate_id) for item in rows)
    ):
        raise ValueError("CANDIDATE_POPULATION_MISMATCH: duplicate, gap, or altered trial")
    return rows


def validate_candidate_population(
    authority: Gate2Authority,
    manifest: Phase4EngineManifest,
    rows: Sequence[CandidateReference],
) -> None:
    if tuple(rows) != _expected(authority, manifest):
        raise ValueError("CANDIDATE_POPULATION_MISMATCH: rows differ from exact sealed order")


def prepare_campaign_plan(
    authority: Gate2Authority,
    manifest: Phase4EngineManifest,
) -> tuple[CandidateReference, ...]:
    """Project the sealed 180 identities; never load data or run a candidate."""

    rows = _expected(authority, manifest)
    validate_candidate_population(authority, manifest, rows)
    return rows


TrialStatus = Literal["EXECUTED", "UNKNOWN", "ABSTAIN", "SKIPPED_FAMILY_STOP"]


class TrialRecord(FrozenGate3Model):
    schema_version: Literal["PHASE4-GATE3-TRIAL-RECORD-v1"] = "PHASE4-GATE3-TRIAL-RECORD-v1"
    campaign_id: Literal["PHASE4-FIXED-LONG-ONLY-2014-2022-v1"] = PHASE4_CAMPAIGN_ID
    population_position: int = Field(ge=1, le=180)
    candidate_id: str = Field(pattern=r"^phase4-[0-9a-f]{64}$")
    trial_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    family_id: str
    hypothesis_id: str
    parameter_tuple_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: TrialStatus
    reason: str
    # Preparation schema only. A future campaign must preregister a complete
    # typed result schema before an EXECUTED candidate can be recorded.
    result: dict[str, object] | None = None

    @model_validator(mode="after")
    def validate_record(self) -> "TrialRecord":
        if self.trial_id != trial_identity(self.campaign_id, self.candidate_id):
            raise ValueError("TRIAL_IDENTITY_INVALID")
        if self.status == "EXECUTED" or self.result is not None:
            raise ValueError("PREPARATION_ONLY: authoritative campaign result schema is not sealed")
        if self.status != "EXECUTED" and not self.reason:
            raise ValueError("REASON_REQUIRED: non-executed trial needs an original reason")
        if self.status != "EXECUTED" and self.result is not None:
            raise ValueError("RESULT_INVALID: unavailable trial cannot contain numeric result")
        return self

    @classmethod
    def from_reference(
        cls,
        row: CandidateReference,
        *,
        status: TrialStatus,
        reason: str,
        result: dict[str, object] | None = None,
    ) -> "TrialRecord":
        if not isinstance(row, CandidateReference):
            raise ValueError("CANDIDATE_POPULATION_MISMATCH: sealed row required")
        return cls(
            population_position=row.population_position,
            candidate_id=row.candidate_id,
            trial_id=row.trial_id,
            family_id=row.family_id,
            hypothesis_id=row.hypothesis_id,
            parameter_tuple_sha256=row.parameter_tuple_sha256,
            status=status,
            reason=reason,
            result=result,
        )
