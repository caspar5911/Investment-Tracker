"""Typed candidate evidence. Authority acceptance is validate_result, not construction."""
from __future__ import annotations

from typing import Literal
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.quant.phase4.engine.models import (
    BootstrapEvidence, DurabilityEvidence, FixedStrategyBinding, FoldSliceEvidence,
    FrictionEvidence, MetricValue, PortfolioReplay, SupportedMetrics,
)
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity, DataPartitionIdentity
from investment_tracker.quant.phase4.preregistration.policy import CandidateSurvivorEvidence


class FrozenResultModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', strict=True, arbitrary_types_allowed=True, allow_inf_nan=False)


class Provenance(FrozenResultModel):
    campaign_id: Literal['PHASE4-FIXED-LONG-ONLY-2014-2022-v1'] = 'PHASE4-FIXED-LONG-ONLY-2014-2022-v1'
    population_position: int = Field(ge=1, le=180)
    candidate_id: str
    trial_id: str
    family_id: str
    hypothesis_id: str
    family_definition_sha256: str
    rule_set_sha256: str
    parameter_tuple_sha256: str
    candidate_population_sha256: str
    train_identity: DataPartitionIdentity
    validation_identity: DataPartitionIdentity
    gate1_manifest: ArtifactIdentity
    gate2_manifest: ArtifactIdentity
    gate3_manifest: ArtifactIdentity
    execution_methodology: ArtifactIdentity
    engine_implementation_sha256: str
    scored_market_panel_sha256: str
    source_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    initial_cash: Literal[100000.0] = 100000.0
    primary_friction_bps: Literal[3] = 3
    execution_convention: Literal['COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN'] = 'COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN'
    execution_series: Literal['QFQ_NORMALIZED'] = 'QFQ_NORMALIZED'
    decision_grade: Literal[False] = False
    evaluation_context_sha256: str


class RegimeRow(FrozenResultModel):
    regime_id: Literal['broad_negative_trend', 'broad_positive_trend', 'mixed_cross_asset']
    ending_sessions: tuple[pd.Timestamp, ...]
    return_vector: tuple[float, ...]
    return_observation_count: int
    positive_return_count: int
    positive_return_percentage: float | None
    arithmetic_mean_session_return: float | None
    conditional_compounded_return: float | None
    status: Literal['AVAILABLE', 'UNKNOWN']
    reason: Literal['OK', 'NO_RETURN_OBSERVATIONS']


class RegimeEvidence(FrozenResultModel):
    first_session_label: str
    first_session_return: None = None
    regimes: tuple[RegimeRow, RegimeRow, RegimeRow]


class NeighborObservation(FrozenResultModel):
    binding: FixedStrategyBinding
    status: Literal['AVAILABLE', 'UNKNOWN']
    reason: str = Field(min_length=1)
    replay: PortfolioReplay | None

    @model_validator(mode='after')
    def status_payload(self):
        if (self.status == 'AVAILABLE') != (self.replay is not None):
            raise ValueError('NEIGHBOR_STATUS_PAYLOAD_MISMATCH')
        return self


class NeighborSummary(FrozenResultModel):
    valid_count: int
    positive_count: int
    positive_fraction: float | None
    median_benchmark_excess: float | None
    status: Literal['AVAILABLE', 'UNKNOWN']
    reason: Literal['OK', 'INSUFFICIENT_VALID_NEIGHBORS']
    metrics: tuple[SupportedMetrics, ...]


class SurvivorProjection(FrozenResultModel):
    status: Literal['AVAILABLE', 'UNKNOWN']
    reasons: tuple[str, ...]
    evidence: CandidateSurvivorEvidence | None


class ExecutedEvidence(FrozenResultModel):
    replays: tuple[PortfolioReplay, ...] = Field(min_length=5, max_length=5)
    benchmark: PortfolioReplay
    cash: PortfolioReplay
    primary_replay_sha256: str
    bootstrap_input_sha256: str
    metrics: SupportedMetrics
    durability: DurabilityEvidence
    candidate_folds: FoldSliceEvidence
    benchmark_folds: FoldSliceEvidence
    regimes: RegimeEvidence
    friction: FrictionEvidence
    neighbors: tuple[NeighborObservation, ...]
    neighborhood: NeighborSummary
    bootstrap: BootstrapEvidence


class StopWitness(FrozenResultModel):
    reason: Literal['PERSISTENT_OOS_FAILURE'] = 'PERSISTENT_OOS_FAILURE'
    trigger_position: int = Field(ge=1, le=180)
    prior_results: tuple[ArtifactIdentity, ...] = Field(min_length=50, max_length=50)


class CandidateResult(FrozenResultModel):
    schema_version: Literal['PHASE4-GATE3-CANDIDATE-RESULT-v1'] = 'PHASE4-GATE3-CANDIDATE-RESULT-v1'
    provenance: Provenance
    status: Literal['EXECUTED', 'UNKNOWN', 'ABSTAIN', 'SKIPPED_FAMILY_STOP', 'CAMPAIGN_EXECUTION_FAILED']
    reason: str = Field(min_length=1)
    evidence: ExecutedEvidence | None
    stop_witness: StopWitness | None = None
    stored_projection: SurvivorProjection | None = None

    @model_validator(mode='after')
    def status_payload(self):
        if (self.status == 'EXECUTED') != (self.evidence is not None):
            raise ValueError('STATUS_EVIDENCE_MISMATCH')
        if (self.status == 'SKIPPED_FAMILY_STOP') != (self.stop_witness is not None):
            raise ValueError('STOP_WITNESS_MISMATCH')
        if self.status != 'EXECUTED' and self.stored_projection is not None:
            raise ValueError('UNAVAILABLE_PROJECTION_FORBIDDEN')
        return self
