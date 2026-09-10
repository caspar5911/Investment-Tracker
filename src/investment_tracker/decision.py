from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from pydantic import Field, model_validator

from .governance import FROZEN_VERSIONS, assert_symbol_allowed
from .models import StrictModel

RECOMMENDATION_VERSION = "REC-v1.0"
CONFIDENCE_VERSION = "CONF-v1.0"


class RecommendationState(str, Enum):
    CONSIDER_ACCUMULATING = "CONSIDER_ACCUMULATING"
    HOLD_OFF = "HOLD_OFF"
    CONSIDER_TRIMMING = "CONSIDER_TRIMMING"
    NO_ACTION = "NO_ACTION"
    ABSTAIN = "ABSTAIN"


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNAVAILABLE = "UNAVAILABLE"


class EvidenceHealth(StrictModel):
    market_data_fresh: bool
    benchmark_aligned: bool
    no_critical_dq: bool
    canonical_digests_valid: bool
    snapshot_current: bool
    versions_match: bool
    calculation_tests_pass: bool
    breadth_met: bool
    independent_recalculation_agrees: bool
    phase_b_passed: bool
    prospective_gate_met: bool
    operational_healthy: bool

    def failures(self) -> list[str]:
        return [name for name, value in self.model_dump().items() if not value]


class PortfolioRiskPolicy(StrictModel):
    policy_version: str = Field(min_length=1)
    max_single_position: Decimal = Field(ge=0, le=1)
    max_theme_exposure: Decimal = Field(ge=0, le=1)
    max_correlated_exposure: Decimal = Field(ge=0, le=1)
    max_aggregate_exposure: Decimal = Field(ge=0, le=1)
    minimum_cash_buffer: Decimal = Field(ge=0, le=1)


class PortfolioSnapshot(StrictModel):
    snapshot_id: str = Field(min_length=1)
    as_of_timestamp: datetime
    asset_allocation: Decimal | None = Field(default=None, ge=0, le=1)
    theme_allocation: Decimal | None = Field(default=None, ge=0, le=1)
    correlated_allocation: Decimal | None = Field(default=None, ge=0, le=1)
    aggregate_exposure: Decimal | None = Field(default=None, ge=0, le=1)
    cash_allocation: Decimal | None = Field(default=None, ge=0, le=1)


class DecisionRequest(StrictModel):
    decision_id: str = Field(min_length=1)
    asset: str
    as_of_timestamp: datetime
    market_data_cutoff: datetime
    signal_state: str
    source_snapshot_id: str = Field(min_length=1)
    evidence: EvidenceHealth
    policy: PortfolioRiskPolicy | None = None
    portfolio: PortfolioSnapshot | None = None
    relevant_dq_refs: list[str] = Field(default_factory=list)
    contrary_evidence: list[str] = Field(default_factory=list)
    invalidators: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_asset(self) -> "DecisionRequest":
        self.asset = assert_symbol_allowed(self.asset)
        return self


class DecisionRecord(StrictModel):
    decision_id: str
    asset: str
    as_of_timestamp: datetime
    market_data_cutoff: datetime
    signal_state: str
    recommendation_state: RecommendationState
    confidence_level: ConfidenceLevel
    confidence_basis: list[str]
    portfolio_risk_status: str
    max_policy_allocation: Decimal | None
    current_policy_allocation: Decimal | None
    incremental_policy_room: Decimal | None
    rationale: list[str]
    contrary_evidence: list[str]
    invalidators: list[str]
    relevant_dq_refs: list[str]
    source_snapshot_id: str
    calculation_version: str
    recommendation_version: str
    confidence_version: str
    decision_status: str
    human_approval_required: bool


def generate_decision(request: DecisionRequest) -> DecisionRecord:
    failures = request.evidence.failures()
    risk_status = "UNAVAILABLE"
    current = maximum = room = None
    if request.policy is None or request.portfolio is None:
        failures.append("portfolio_policy_or_snapshot_missing")
    else:
        values = request.portfolio
        if any(value is None for value in (
            values.asset_allocation, values.theme_allocation, values.correlated_allocation,
            values.aggregate_exposure, values.cash_allocation,
        )):
            failures.append("portfolio_value_unknown")
        else:
            current = values.asset_allocation
            maximum = request.policy.max_single_position
            room = max(Decimal("0"), maximum - current)
            violations = (
                current > maximum
                or values.theme_allocation > request.policy.max_theme_exposure
                or values.correlated_allocation > request.policy.max_correlated_exposure
                or values.aggregate_exposure > request.policy.max_aggregate_exposure
                or values.cash_allocation < request.policy.minimum_cash_buffer
            )
            risk_status = "VIOLATION" if violations else "WITHIN_POLICY"
            if violations:
                failures.append("portfolio_risk_violation")

    if failures:
        recommendation = RecommendationState.ABSTAIN
        confidence = ConfidenceLevel.UNAVAILABLE
    else:
        recommendation = {
            "ACCUMULATE": RecommendationState.CONSIDER_ACCUMULATING,
            "TRIM/AVOID": RecommendationState.CONSIDER_TRIMMING,
            "WATCH": RecommendationState.HOLD_OFF,
            "WAIT": RecommendationState.NO_ACTION,
            "ABSTAIN": RecommendationState.ABSTAIN,
        }.get(request.signal_state, RecommendationState.ABSTAIN)
        confidence = ConfidenceLevel.HIGH
        if recommendation is RecommendationState.ABSTAIN:
            failures.append("signal_abstained_or_unknown")
            confidence = ConfidenceLevel.UNAVAILABLE

    return DecisionRecord(
        decision_id=request.decision_id, asset=request.asset,
        as_of_timestamp=request.as_of_timestamp.astimezone(timezone.utc),
        market_data_cutoff=request.market_data_cutoff.astimezone(timezone.utc),
        signal_state=request.signal_state, recommendation_state=recommendation,
        confidence_level=confidence,
        confidence_basis=failures or ["all_CONF-v1.0_critical_dimensions_met"],
        portfolio_risk_status=risk_status, max_policy_allocation=maximum,
        current_policy_allocation=current, incremental_policy_room=room,
        rationale=[f"Frozen signal: {request.signal_state}", f"Portfolio risk: {risk_status}"],
        contrary_evidence=request.contrary_evidence, invalidators=request.invalidators,
        relevant_dq_refs=request.relevant_dq_refs, source_snapshot_id=request.source_snapshot_id,
        calculation_version=FROZEN_VERSIONS.calc, recommendation_version=RECOMMENDATION_VERSION,
        confidence_version=CONFIDENCE_VERSION,
        decision_status="PAPER_ONLY_NOT_PRODUCTION_APPROVED",
        human_approval_required=True,
    )
