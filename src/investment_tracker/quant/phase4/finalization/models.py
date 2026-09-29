from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.quant.phase4.engine.source_identity import SourceBundleIdentity
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity
from investment_tracker.quant.phase4.gate3_runner.models import ResultStatus
from investment_tracker.quant.phase4.preregistration.policy import CandidateSurvivorEvidence


class FrozenFinalizationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FinalizationSafetyState(FrozenFinalizationModel):
    candidate_executed: Literal[False] = False
    candidate_rerun: Literal[False] = False
    strategy_search_executed: Literal[False] = False
    candidate_parameters_changed: Literal[False] = False
    survivor_policy_changed: Literal[False] = False
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()
    provider_calls: Literal[0] = 0
    downloads: Literal[0] = 0
    live_trading_capability: Literal[False] = False
    phase5_started: Literal[False] = False


class AuditRow(FrozenFinalizationModel):
    schema_version: Literal["PHASE4-FINALIZATION-AUDIT-ROW-v1"] = "PHASE4-FINALIZATION-AUDIT-ROW-v1"
    population_position: int = Field(ge=1, le=180)
    candidate_id: str = Field(pattern=r"^phase4-[0-9a-f]{64}$")
    trial_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    family_id: str = Field(pattern=r"^phase4-family-[0-9a-f]{64}$")
    hypothesis_id: str = Field(pattern=r"^phase4-hypothesis-[0-9a-f]{64}$")
    rule_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameter_tuple_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    family_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_artifact: ArtifactIdentity
    result_status: ResultStatus
    projection_status: Literal["AVAILABLE", "UNKNOWN", "NOT_APPLICABLE"]
    eligibility_status: Literal["ELIGIBLE", "REJECTED", "UNKNOWN", "NOT_APPLICABLE"]
    rejection_reasons: tuple[str, ...] = ()
    survivor_evidence: CandidateSurvivorEvidence | None = None

    @model_validator(mode="after")
    def validate_projection(self) -> "AuditRow":
        if (self.projection_status == "AVAILABLE") != (self.survivor_evidence is not None):
            raise ValueError("FINALIZATION_PROJECTION_PAYLOAD_MISMATCH")
        if self.eligibility_status == "ELIGIBLE":
            if self.projection_status != "AVAILABLE" or self.rejection_reasons:
                raise ValueError("FINALIZATION_ELIGIBLE_ROW_INVALID")
        elif self.eligibility_status == "REJECTED":
            if self.projection_status != "AVAILABLE" or not self.rejection_reasons:
                raise ValueError("FINALIZATION_REJECTED_ROW_INVALID")
        elif self.eligibility_status in {"UNKNOWN", "NOT_APPLICABLE"}:
            if self.survivor_evidence is not None or not self.rejection_reasons:
                raise ValueError("FINALIZATION_UNAVAILABLE_ROW_INVALID")
        return self


class Phase4Audit(FrozenFinalizationModel):
    schema_version: Literal["PHASE4-FINALIZATION-AUDIT-v1"] = "PHASE4-FINALIZATION-AUDIT-v1"
    campaign_result_set: ArtifactIdentity
    campaign_aggregate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_positions: Literal[180] = 180
    accounted_positions: Literal[180] = 180
    status_counts: dict[str, int]
    rows: tuple[AuditRow, ...] = Field(min_length=180, max_length=180)
    eligible_candidate_ids: tuple[str, ...]
    survivor_policy: ArtifactIdentity
    durability_policy: ArtifactIdentity
    candidate_population_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runner_manifest: ArtifactIdentity
    result_schema_manifest: ArtifactIdentity
    safety: FinalizationSafetyState = FinalizationSafetyState()

    @model_validator(mode="after")
    def validate_accounting(self) -> "Phase4Audit":
        if tuple(row.population_position for row in self.rows) != tuple(range(1, 181)):
            raise ValueError("PHASE4_FINALIZATION_ACCOUNTING_INVALID")
        if len({row.candidate_id for row in self.rows}) != 180:
            raise ValueError("PHASE4_FINALIZATION_ACCOUNTING_INVALID")
        observed: dict[str, int] = {}
        for row in self.rows:
            observed[row.result_status] = observed.get(row.result_status, 0) + 1
        if self.status_counts != dict(sorted(observed.items())):
            raise ValueError("PHASE4_FINALIZATION_ACCOUNTING_INVALID")
        expected_eligible = tuple(
            row.candidate_id for row in self.rows if row.eligibility_status == "ELIGIBLE"
        )
        if self.eligible_candidate_ids != expected_eligible:
            raise ValueError("PHASE4_FINALIZATION_ELIGIBILITY_MISMATCH")
        return self


class Phase4Decision(FrozenFinalizationModel):
    schema_version: Literal["PHASE4-FINAL-DECISION-v1"] = "PHASE4-FINAL-DECISION-v1"
    status: Literal["ONE_FROZEN_SURVIVOR", "NO_CREDIBLE_STRATEGY_FOUND"]
    audit_artifact: ArtifactIdentity
    campaign_result_set: ArtifactIdentity
    survivor_policy: ArtifactIdentity
    durability_policy: ArtifactIdentity
    selected_candidate_id: str | None = Field(default=None, pattern=r"^phase4-[0-9a-f]{64}$")
    selected_result_artifact: ArtifactIdentity | None = None
    selected_population_position: int | None = Field(default=None, ge=1, le=180)
    selected_family_id: str | None = Field(default=None, pattern=r"^phase4-family-[0-9a-f]{64}$")
    selected_hypothesis_id: str | None = Field(default=None, pattern=r"^phase4-hypothesis-[0-9a-f]{64}$")
    selected_rule_set_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_parameter_tuple_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_family_definition_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    phase5_feedback_into_phase4_forbidden: Literal[True] = True
    safety: FinalizationSafetyState = FinalizationSafetyState()

    @model_validator(mode="after")
    def validate_selected_payload(self) -> "Phase4Decision":
        selected = (
            self.selected_candidate_id,
            self.selected_result_artifact,
            self.selected_population_position,
            self.selected_family_id,
            self.selected_hypothesis_id,
            self.selected_rule_set_sha256,
            self.selected_parameter_tuple_sha256,
            self.selected_family_definition_sha256,
        )
        if self.status == "ONE_FROZEN_SURVIVOR":
            if any(value is None for value in selected):
                raise ValueError("PHASE4_FINALIZATION_SELECTED_PAYLOAD_MISSING")
        elif any(value is not None for value in selected):
            raise ValueError("PHASE4_FINALIZATION_SELECTED_PAYLOAD_FORBIDDEN")
        return self


class FinalizationManifest(FrozenFinalizationModel):
    schema_version: Literal["PHASE4-FINALIZATION-AUTHORITY-v1"] = "PHASE4-FINALIZATION-AUTHORITY-v1"
    status: Literal["PHASE4_FINALIZATION_SEALED"] = "PHASE4_FINALIZATION_SEALED"
    spec: ArtifactIdentity
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_bundle: SourceBundleIdentity
    campaign_result_set: ArtifactIdentity
    campaign_aggregate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_population_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runner_manifest: ArtifactIdentity
    result_schema_manifest: ArtifactIdentity
    survivor_policy: ArtifactIdentity
    durability_policy: ArtifactIdentity
    audit_artifact: ArtifactIdentity
    decision_artifact: ArtifactIdentity
    safety: FinalizationSafetyState = FinalizationSafetyState()


class FinalizationPreflight(FrozenFinalizationModel):
    status: Literal["PHASE4_FINALIZATION_SEALED"] = "PHASE4_FINALIZATION_SEALED"
    manifest: ArtifactIdentity
    decision_status: Literal["ONE_FROZEN_SURVIVOR", "NO_CREDIBLE_STRATEGY_FOUND"]
    eligible_candidate_count: int = Field(ge=0, le=180)
    safety: FinalizationSafetyState = FinalizationSafetyState()
