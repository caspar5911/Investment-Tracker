from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from enum import Enum
from functools import reduce
from operator import mul
from statistics import median
from typing import Literal, Mapping

from pydantic import Field, field_validator, model_validator

from .canonical import hypothesis_identity, source_identity
from .models import FrozenGate1Model


class SourceTier(str, Enum):
    PEER_REVIEWED_ACADEMIC = "PEER_REVIEWED_ACADEMIC"
    ACADEMIC_WORKING_PAPER = "ACADEMIC_WORKING_PAPER"
    SSRN = "SSRN"
    ESTABLISHED_QUANTITATIVE_FIRM = "ESTABLISHED_QUANTITATIVE_FIRM"
    CFA_OR_INSTITUTIONAL = "CFA_OR_INSTITUTIONAL"
    OFFICIAL_EXCHANGE_OR_MARKET_RESEARCH = "OFFICIAL_EXCHANGE_OR_MARKET_RESEARCH"
    REPUTABLE_QUANTITATIVE_PRACTITIONER = "REPUTABLE_QUANTITATIVE_PRACTITIONER"
    BLOG_FORUM_OR_SOCIAL_HYPOTHESIS_ONLY = "BLOG_FORUM_OR_SOCIAL_HYPOTHESIS_ONLY"

    @property
    def tier(self) -> int:
        return list(type(self)).index(self) + 1


class ResearchSource(FrozenGate1Model):
    schema_version: Literal["PHASE4-RESEARCH-SOURCE-v1"] = "PHASE4-RESEARCH-SOURCE-v1"
    source_id: str = Field(pattern=r"^source-[0-9a-f]{64}$")
    title: str | None
    authors: tuple[str, ...] | None
    publication: str | None
    year: int | None
    canonical_url: str | None
    source_type: SourceTier
    evidence_role: Literal["SUPPORT", "COUNTEREVIDENCE"]
    retrieved_at: datetime
    methodology: str
    asset_classes: str
    test_period: str | None
    strategy_concept: str
    reported_parameters_horizons: str | None
    mechanism: str
    claimed_findings: str
    limitations: str
    frozen_universe_relevance: str
    primary_evidence_eligible: bool
    primary_evidence_eligibility_reason: str
    citation_verified: bool
    phase4_validation_information_used: Literal[False] = False
    missing_fact_explanations: dict[str, str] = Field(default_factory=dict)

    @staticmethod
    def bibliographic_identity(payload: Mapping[str, object]) -> dict[str, object]:
        return {
            "title": payload.get("title"),
            "authors": payload.get("authors"),
            "publication": payload.get("publication"),
            "year": payload.get("year"),
            "canonical_url": payload.get("canonical_url"),
        }

    @model_validator(mode="after")
    def validate_source(self) -> "ResearchSource":
        missing = {
            name
            for name in ("title", "authors", "publication", "year", "canonical_url")
            if getattr(self, name) is None
        }
        if missing - set(self.missing_fact_explanations):
            raise ValueError("each missing bibliographic fact requires an explanation")
        if any(not value.strip() for value in self.missing_fact_explanations.values()):
            raise ValueError("missing-fact explanations must be non-empty")
        if not self.citation_verified:
            raise ValueError("sealed source citations must be verified")
        if (
            self.source_type is SourceTier.BLOG_FORUM_OR_SOCIAL_HYPOTHESIS_ONLY
            and self.primary_evidence_eligible
        ):
            raise ValueError("Tier 8 cannot be primary evidence eligible")
        expected = source_identity(self.bibliographic_identity(self.model_dump(mode="json")))
        if self.source_id != expected:
            raise ValueError("source identity does not match bibliographic identity")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("retrieval time must be timezone-aware")
        return self


HypothesisState = Literal["PROPOSED", "ADMITTED", "REJECTED_BEFORE_TESTING"]


class HypothesisRecord(FrozenGate1Model):
    schema_version: Literal["PHASE4-HYPOTHESIS-v1"] = "PHASE4-HYPOTHESIS-v1"
    hypothesis_id: str = Field(pattern=r"^phase4-hypothesis-[0-9a-f]{64}$")
    display_name: str
    lifecycle_state: HypothesisState
    supporting_source_ids: tuple[str, ...]
    economic_behavioral_rationale: str
    signal_concept: str
    entry_logic: str
    exit_logic: str
    cross_sectional_ranking_logic: str
    allocation_logic: str
    cash_rule: str
    risk_rule: str
    rebalance_frequency: str
    expected_turnover_class: str
    expected_strengths: tuple[str, ...]
    named_failure_regimes: tuple[str, ...]
    rule_set_mode: Literal["FIXED"] = "FIXED"
    parameter_tuple_mode: Literal["FIXED"] = "FIXED"
    annual_reoptimization: Literal[False] = False
    periodic_reoptimization: Literal[False] = False
    regime_behavior_map: dict[str, str]
    regime_partition_rule: str
    parameter_dimensions: dict[str, tuple[int | float, ...]]
    complete_grid_definition: str
    expected_candidate_count: int = Field(ge=0)
    baseline_distinction: str
    implementation_requirements: tuple[str, ...]
    anti_lookahead_requirements: tuple[str, ...]
    benchmark_expectations: str
    falsification_conditions: tuple[str, ...]
    simplicity_component_count: int = Field(ge=0)
    family_semantic_name: str | None
    family_slots_consumed: Literal[0, 1]
    rejection_reason: str | None = None
    validation_data_accessed: Literal[False] = False
    validation_metrics_accessed: Literal[False] = False
    campaign_results_accessed: Literal[False] = False
    provider_calls: Literal[0] = 0
    strategy_search_executed: Literal[False] = False
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()

    @classmethod
    def semantic_payload(cls, payload: Mapping[str, object]) -> dict[str, object]:
        excluded = {
            "hypothesis_id", "display_name", "schema_version",
            "validation_data_accessed", "validation_metrics_accessed",
            "campaign_results_accessed", "provider_calls",
            "strategy_search_executed", "final_holdout_accessed",
            "protected_symbols_accessed",
        }
        return {key: value for key, value in payload.items() if key not in excluded}

    @classmethod
    def identity_for(cls, payload: Mapping[str, object]) -> str:
        return hypothesis_identity(cls.semantic_payload(payload))

    @model_validator(mode="after")
    def validate_lifecycle_and_identity(self) -> "HypothesisRecord":
        if self.hypothesis_id != self.identity_for(self.model_dump(mode="json")):
            raise ValueError("hypothesis identity does not match semantic payload")
        if self.lifecycle_state == "ADMITTED":
            if self.family_semantic_name is None or self.family_slots_consumed != 1:
                raise ValueError("admitted hypothesis must consume exactly one family slot")
            if self.rejection_reason is not None:
                raise ValueError("admitted hypothesis cannot have a rejection reason")
        elif self.lifecycle_state == "REJECTED_BEFORE_TESTING":
            if self.family_semantic_name is not None or self.family_slots_consumed != 0:
                raise ValueError("rejected hypothesis cannot define or consume a family")
            if not self.rejection_reason:
                raise ValueError("rejected hypothesis requires a reason")
        return self


def enforce_research_cutoff(
    sources: tuple[ResearchSource, ...], cutoff: datetime
) -> tuple[ResearchSource, ...]:
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("research cutoff must be timezone-aware")
    if any(source.retrieved_at > cutoff for source in sources):
        raise ValueError("source retrieved after research cutoff")
    return sources


def validate_hypothesis_registry(
    sources: tuple[ResearchSource, ...], hypotheses: tuple[HypothesisRecord, ...]
) -> tuple[HypothesisRecord, ...]:
    source_by_id = {source.source_id: source for source in sources}
    if len(source_by_id) != len(sources):
        raise ValueError("duplicate source identity")
    admitted = tuple(row for row in hypotheses if row.lifecycle_state == "ADMITTED")
    if not 1 <= len(admitted) <= 10:
        raise ValueError("admitted hypothesis count must be between one and ten")
    families = [row.family_semantic_name for row in admitted]
    if len(set(families)) != len(families):
        raise ValueError("admitted hypotheses must map one-to-one to families")
    for hypothesis in admitted:
        if len(set(hypothesis.supporting_source_ids)) < 2:
            raise ValueError("admitted hypothesis requires at least two sources")
        try:
            support = tuple(source_by_id[item] for item in hypothesis.supporting_source_ids)
        except KeyError as exc:
            raise ValueError("hypothesis cites an unknown source") from exc
        if not all(source.primary_evidence_eligible for source in support):
            raise ValueError("hypothesis support must be primary-evidence eligible")
        if not any(source.source_type.tier <= 3 for source in support):
            raise ValueError("hypothesis needs at least one tier 1-3 source")
    return hypotheses


class CandidateOOSOutcome(FrozenGate1Model):
    benchmark_excess_return: float | None
    robustness_passed: bool = True
    friction_passed: bool = True
    bootstrap_passed: bool = True
    neighborhood_passed: bool = True
    absolute_return_passed: bool = True


class FamilyStopPolicy(FrozenGate1Model):
    schema_version: Literal["PHASE4-FAMILY-STOP-POLICY-v1"] = "PHASE4-FAMILY-STOP-POLICY-v1"
    allowed_stop_reasons: tuple[str, ...] = (
        "EXHAUSTED_GRID", "PER_FAMILY_BUDGET_EXHAUSTED",
        "AGGREGATE_BUDGET_EXHAUSTED", "PERSISTENT_OOS_FAILURE",
    )
    persistent_oos_failure_consecutive_count: Literal[50] = 50
    increment_basis: Literal["VALIDATION_BENCHMARK_EXCESS_NONPOSITIVE_OR_UNAVAILABLE"] = (
        "VALIDATION_BENCHMARK_EXCESS_NONPOSITIVE_OR_UNAVAILABLE"
    )
    positive_benchmark_excess_resets: Literal[True] = True
    isolated_robustness_failures_increment: Literal[False] = False
    isolated_robustness_failures_terminate: Literal[False] = False


FAMILY_STOP_POLICY = FamilyStopPolicy()


def update_oos_failure_streak(
    current_streak: int, outcome: CandidateOOSOutcome
) -> tuple[int, bool]:
    if current_streak < 0:
        raise ValueError("OOS streak cannot be negative")
    streak = (
        0
        if outcome.benchmark_excess_return is not None
        and outcome.benchmark_excess_return > 0
        else current_streak + 1
    )
    return streak, streak >= FAMILY_STOP_POLICY.persistent_oos_failure_consecutive_count


class DurabilityPolicy(FrozenGate1Model):
    schema_version: Literal["PHASE4-DURABILITY-POLICY-v1"] = "PHASE4-DURABILITY-POLICY-v1"
    deployment_strategy_count: Literal[1] = 1
    position_direction: Literal["LONG_ONLY"] = "LONG_ONLY"
    rule_set_mode: Literal["FIXED"] = "FIXED"
    parameter_tuple_mode: Literal["FIXED"] = "FIXED"
    parameter_fitting_from_train: Literal[False] = False
    annual_reoptimization: Literal[False] = False
    periodic_reoptimization: Literal[False] = False
    primary_proof_mode: Literal["FIXED_PARAMETER_CHRONOLOGICAL"] = "FIXED_PARAMETER_CHRONOLOGICAL"
    adaptive_walk_forward_in_phase4: Literal[False] = False
    cagr_hard_target: None = None
    aspirational_sustainable_cagr: Literal["15_TO_20_PERCENT_OR_MORE_IF_DEFENSIBLE"] = (
        "15_TO_20_PERCENT_OR_MORE_IF_DEFENSIBLE"
    )
    durability_precedes_fitted_cagr: Literal[True] = True
    train_start: date = date(2014, 1, 2)
    train_end: date = date(2018, 12, 31)
    train_sessions: Literal[1258] = 1258
    validation_declared_start: date = date(2019, 1, 1)
    validation_start: date = date(2019, 1, 2)
    validation_end: date = date(2022, 12, 30)
    validation_sessions: Literal[1008] = 1008
    earlier_train_use: Literal["LAGGED_INDICATOR_INITIALIZATION_ONLY"] = "LAGGED_INDICATOR_INITIALIZATION_ONLY"
    validation_portfolio_reset_once: Literal[True] = True
    fold_portfolio_resets: Literal[False] = False
    train_pnl_in_validation: Literal[False] = False
    first_scored_signal_on_validation_session: Literal[True] = True
    next_eligible_validation_session_execution: Literal[True] = True
    walk_forward_mode: Literal["FIXED_STRATEGY_CONTINUOUS_VALIDATION_SUBPERIODS"] = (
        "FIXED_STRATEGY_CONTINUOUS_VALIDATION_SUBPERIODS"
    )
    rolling_calendar_month_horizons: tuple[int, ...] = (12, 36)
    rolling_anchor_rule: Literal["LATEST_SCORED_XNYS_SESSION_ON_OR_BEFORE_GREGORIAN_OFFSET"] = (
        "LATEST_SCORED_XNYS_SESSION_ON_OR_BEFORE_GREGORIAN_OFFSET"
    )
    incomplete_period_behavior: Literal["UNKNOWN_EXCLUDED_FROM_AGGREGATES"] = (
        "UNKNOWN_EXCLUDED_FROM_AGGREGATES"
    )
    losing_month_definition: Literal["STRICTLY_NEGATIVE_ZERO_BREAKS"] = "STRICTLY_NEGATIVE_ZERO_BREAKS"
    friction_cases_bps: tuple[int, ...] = (0, 3, 10, 25, 50)
    identity_invariant_cases: tuple[str, ...] = (
        "EVERY_SESSION", "EVERY_CALENDAR_PERIOD", "EVERY_WALK_FORWARD_FOLD",
        "EVERY_REGIME", "EVERY_FRICTION_CASE", "EVERY_ROBUSTNESS_CASE",
    )
    invariant_fields: tuple[str, ...] = (
        "candidate_id", "family_definition_sha256", "rule_set_sha256",
        "parameter_tuple_sha256",
    )
    identity_mismatch_result: Literal["INVARIANT_FAILURE_REJECT"] = "INVARIANT_FAILURE_REJECT"


DURABILITY_POLICY = DurabilityPolicy()


class PeriodReturn(FrozenGate1Model):
    period: str
    availability: Literal["AVAILABLE", "UNKNOWN"]
    return_value: float | None
    reason: str | None = None


class RollingReturn(FrozenGate1Model):
    horizon_calendar_months: int
    anchor: date
    endpoint: date
    return_value: float


class RollingSummary(FrozenGate1Model):
    status: Literal["AVAILABLE", "UNKNOWN"]
    reason: Literal["INSUFFICIENT_DATA"] | None = None
    minimum: float | None = None
    median: float | None = None
    positive_window_percentage: float | None = None


class DurabilityEvidence(FrozenGate1Model):
    schema_version: Literal["PHASE4-DURABILITY-EVIDENCE-v1"] = "PHASE4-DURABILITY-EVIDENCE-v1"
    calendar_month_returns: tuple[PeriodReturn, ...]
    calendar_year_returns: tuple[PeriodReturn, ...]
    positive_month_percentage: float | None
    positive_month_percentage_status: Literal["AVAILABLE", "UNKNOWN"]
    positive_year_percentage: float | None
    average_positive_month: float | None
    average_negative_month: float | None
    worst_month: float | None
    worst_year: float | None
    longest_losing_month_sequence: int | None
    positive_month_return_concentration: float | None
    positive_year_return_concentration: float | None
    top_three_positive_month_return_concentration: float | None
    rolling_12_month_returns: tuple[RollingReturn, ...]
    rolling_36_month_returns: tuple[RollingReturn, ...]
    rolling_60_month_returns: tuple[RollingReturn, ...]
    rolling_12_month_summary: RollingSummary
    rolling_36_month_summary: RollingSummary
    rolling_60_month_summary: RollingSummary


def _compound(values: list[float]) -> float:
    return reduce(mul, (1.0 + value for value in values), 1.0) - 1.0


def _period_rows(
    sessions: tuple[date, ...], returns: tuple[float, ...], expected: tuple[date, ...],
    *, annual: bool,
) -> tuple[PeriodReturn, ...]:
    key = (lambda value: f"{value.year:04d}") if annual else (
        lambda value: f"{value.year:04d}-{value.month:02d}"
    )
    actual_by_period: dict[str, list[tuple[date, float]]] = {}
    for session, value in zip(sessions, returns, strict=True):
        actual_by_period.setdefault(key(session), []).append((session, value))
    expected_by_period: dict[str, list[date]] = {}
    for session in expected:
        expected_by_period.setdefault(key(session), []).append(session)
    rows: list[PeriodReturn] = []
    for period in sorted(expected_by_period):
        actual = actual_by_period.get(period, [])
        if tuple(item[0] for item in actual) != tuple(expected_by_period[period]):
            rows.append(PeriodReturn(period=period, availability="UNKNOWN", return_value=None, reason="INCOMPLETE_PERIOD"))
        else:
            rows.append(PeriodReturn(period=period, availability="AVAILABLE", return_value=_compound([item[1] for item in actual])))
    return tuple(rows)


def _subtract_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 - months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _rolling(
    sessions: tuple[date, ...], returns: tuple[float, ...], expected: tuple[date, ...], months: int
) -> tuple[tuple[RollingReturn, ...], RollingSummary]:
    equity: dict[date, float] = {}
    level = 1.0
    for session, value in zip(sessions, returns, strict=True):
        level *= 1.0 + value
        equity[session] = level
    session_set = set(sessions)
    expected_set = set(expected)
    rows: list[RollingReturn] = []
    if not sessions:
        return (), RollingSummary(status="UNKNOWN", reason="INSUFFICIENT_DATA")
    for endpoint in sessions:
        target = _subtract_months(endpoint, months)
        if target < sessions[0]:
            continue
        anchors = [item for item in sessions if item <= target]
        if not anchors:
            continue
        anchor = anchors[-1]
        expected_window = {item for item in expected_set if anchor <= item <= endpoint}
        if not expected_window or not expected_window <= session_set:
            continue
        rows.append(RollingReturn(
            horizon_calendar_months=months, anchor=anchor, endpoint=endpoint,
            return_value=equity[endpoint] / equity[anchor] - 1.0,
        ))
    if not rows:
        return (), RollingSummary(status="UNKNOWN", reason="INSUFFICIENT_DATA")
    values = [item.return_value for item in rows]
    return tuple(rows), RollingSummary(
        status="AVAILABLE", minimum=min(values), median=median(values),
        positive_window_percentage=sum(value > 0 for value in values) / len(values),
    )


def _concentration(values: list[float], *, top_three: bool = False) -> float | None:
    positives = [value for value in values if value > 0]
    denominator = sum(positives)
    if denominator <= 0:
        return None
    numerator = sum(sorted(positives, reverse=True)[:3]) if top_three else max(positives)
    return numerator / denominator


def compute_durability_evidence(
    sessions: tuple[date, ...], daily_returns: tuple[float, ...], expected_sessions: tuple[date, ...]
) -> DurabilityEvidence:
    if len(sessions) != len(daily_returns):
        raise ValueError("sessions and returns must have the same length")
    if tuple(sorted(set(sessions))) != sessions or tuple(sorted(set(expected_sessions))) != expected_sessions:
        raise ValueError("sessions must be unique and ascending")
    months = _period_rows(sessions, daily_returns, expected_sessions, annual=False)
    years = _period_rows(sessions, daily_returns, expected_sessions, annual=True)
    month_values = [row.return_value for row in months if row.availability == "AVAILABLE" and row.return_value is not None]
    year_values = [row.return_value for row in years if row.availability == "AVAILABLE" and row.return_value is not None]
    positives = [value for value in month_values if value > 0]
    negatives = [value for value in month_values if value < 0]
    streak = longest = 0
    for value in month_values:
        streak = streak + 1 if value < 0 else 0
        longest = max(longest, streak)
    rolling12, summary12 = _rolling(sessions, daily_returns, expected_sessions, 12)
    rolling36, summary36 = _rolling(sessions, daily_returns, expected_sessions, 36)
    rolling60, summary60 = _rolling(sessions, daily_returns, expected_sessions, 60)
    return DurabilityEvidence(
        calendar_month_returns=months, calendar_year_returns=years,
        positive_month_percentage=(sum(value > 0 for value in month_values) / len(month_values) if month_values else None),
        positive_month_percentage_status="AVAILABLE" if month_values else "UNKNOWN",
        positive_year_percentage=(sum(value > 0 for value in year_values) / len(year_values) if year_values else None),
        average_positive_month=(sum(positives) / len(positives) if positives else None),
        average_negative_month=(sum(negatives) / len(negatives) if negatives else None),
        worst_month=min(month_values) if month_values else None,
        worst_year=min(year_values) if year_values else None,
        longest_losing_month_sequence=longest if month_values else None,
        positive_month_return_concentration=_concentration(month_values),
        positive_year_return_concentration=_concentration(year_values),
        top_three_positive_month_return_concentration=_concentration(month_values, top_three=True),
        rolling_12_month_returns=rolling12, rolling_36_month_returns=rolling36,
        rolling_60_month_returns=rolling60, rolling_12_month_summary=summary12,
        rolling_36_month_summary=summary36, rolling_60_month_summary=summary60,
    )


class DQ030UnavailableMetrics(FrozenGate1Model):
    max_drawdown: None = None
    max_drawdown_status: Literal["UNKNOWN"] = "UNKNOWN"
    calmar: None = None
    calmar_status: Literal["UNKNOWN"] = "UNKNOWN"
    dsr: None = None
    dsr_status: Literal["UNKNOWN"] = "UNKNOWN"
    dsr_reason: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"
    pbo: None = None
    pbo_status: Literal["UNKNOWN"] = "UNKNOWN"
    pbo_reason: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"


class SurvivorPolicy(FrozenGate1Model):
    schema_version: Literal["PHASE4-SURVIVOR-POLICY-v1"] = "PHASE4-SURVIVOR-POLICY-v1"
    ranking_keys: tuple[str, ...] = (
        "walk_forward_joint_consistency:DESC", "positive_year_percentage:DESC",
        "minimum_rolling_36_month_return:DESC", "minimum_rolling_12_month_return:DESC",
        "longest_losing_month_sequence:ASC", "worst_year:DESC", "worst_month:DESC",
        "positive_year_return_concentration:ASC", "top_three_positive_month_return_concentration:ASC",
        "positive_month_percentage:DESC", "neighborhood_positive_fraction:DESC",
        "friction_25bps_retention_ratio:DESC", "benchmark_excess_return:DESC",
        "sharpe:DESC", "sortino:DESC", "bootstrap_lower_endpoint:DESC",
        "annualized_one_way_turnover:ASC", "walk_forward_positive_concentration:ASC",
        "signal_component_count:ASC", "validation_total_return:DESC", "cagr:DESC",
        "candidate_id:ASC",
    )
    maximum_selected_candidates: Literal[1] = 1
    baselines_eligible_to_win: Literal[False] = False
    minimum_joint_positive_folds: Literal[3] = 3
    minimum_valid_neighbors: Literal[2] = 2
    minimum_neighbor_positive_fraction: float = 2 / 3
    maximum_positive_fold_concentration: Literal[0.75] = 0.75
    maximum_annualized_turnover: Literal[12.0] = 12.0
    friction_hard_gate_bps: Literal[25] = 25


SURVIVOR_POLICY = SurvivorPolicy()


class CandidateSurvivorEvidence(FrozenGate1Model):
    candidate_id: str
    is_baseline: bool
    validation_total_return: float
    cash_return: float
    benchmark_excess_return: float
    sharpe: float | None
    sortino: float | None
    walk_forward_returns: tuple[float, float, float, float]
    walk_forward_benchmark_excess: tuple[float, float, float, float]
    neighborhood_valid_count: int
    neighborhood_positive_fraction: float | None
    neighborhood_median_benchmark_excess: float | None
    friction_returns_bps: dict[int, float]
    annualized_one_way_turnover: float | None
    average_gross_exposure: float | None
    all_session_exposures_valid: bool
    bootstrap_lower_endpoint: float | None
    fixed_identity_invariant: bool
    durability_evidence_complete: bool
    walk_forward_joint_consistency: int
    positive_year_percentage: float
    minimum_rolling_36_month_return: float
    minimum_rolling_12_month_return: float
    longest_losing_month_sequence: int
    worst_year: float
    worst_month: float
    positive_year_return_concentration: float
    top_three_positive_month_return_concentration: float
    positive_month_percentage: float
    friction_25bps_retention_ratio: float
    signal_component_count: int
    cagr: float
    max_drawdown: None
    calmar: None
    dsr: None
    pbo: None

    @property
    def walk_forward_positive_concentration(self) -> float | None:
        positives = [value for value in self.walk_forward_returns if value > 0]
        return max(positives) / sum(positives) if positives and sum(positives) > 0 else None


def _eligible(row: CandidateSurvivorEvidence) -> bool:
    joint = sum(
        return_value > 0 and excess > 0
        for return_value, excess in zip(row.walk_forward_returns, row.walk_forward_benchmark_excess, strict=True)
    )
    concentration = row.walk_forward_positive_concentration
    friction_3 = row.friction_returns_bps.get(3)
    expected_retention = (
        row.friction_returns_bps.get(25, 0.0) / friction_3
        if friction_3 is not None and friction_3 > 0
        else None
    )
    return all((
        not row.is_baseline,
        row.validation_total_return > 0 and row.validation_total_return > row.cash_return,
        row.benchmark_excess_return > 0,
        row.sharpe is not None and row.sharpe > 0,
        row.sortino is not None and row.sortino > 0,
        joint >= 3,
        row.walk_forward_joint_consistency == joint,
        row.neighborhood_valid_count >= 2,
        row.neighborhood_positive_fraction is not None and row.neighborhood_positive_fraction >= 2 / 3,
        row.neighborhood_median_benchmark_excess is not None and row.neighborhood_median_benchmark_excess >= 0,
        set(row.friction_returns_bps) == {0, 3, 10, 25, 50},
        row.friction_returns_bps.get(25, -1.0) > 0,
        expected_retention is not None
        and abs(row.friction_25bps_retention_ratio - expected_retention) <= 1e-15,
        concentration is not None and concentration <= 0.75,
        row.annualized_one_way_turnover is not None and 0 <= row.annualized_one_way_turnover <= 12.0,
        row.average_gross_exposure is not None and 0 <= row.average_gross_exposure <= 1.0,
        row.all_session_exposures_valid,
        row.bootstrap_lower_endpoint is not None and row.bootstrap_lower_endpoint >= 0,
        row.fixed_identity_invariant,
        row.durability_evidence_complete,
        row.max_drawdown is None, row.calmar is None, row.dsr is None, row.pbo is None,
    ))


def _survivor_key(row: CandidateSurvivorEvidence) -> tuple[object, ...]:
    assert row.sharpe is not None and row.sortino is not None
    assert row.bootstrap_lower_endpoint is not None
    assert row.annualized_one_way_turnover is not None
    assert row.neighborhood_positive_fraction is not None
    assert row.walk_forward_positive_concentration is not None
    return (
        -row.walk_forward_joint_consistency, -row.positive_year_percentage,
        -row.minimum_rolling_36_month_return, -row.minimum_rolling_12_month_return,
        row.longest_losing_month_sequence, -row.worst_year, -row.worst_month,
        row.positive_year_return_concentration, row.top_three_positive_month_return_concentration,
        -row.positive_month_percentage, -row.neighborhood_positive_fraction,
        -row.friction_25bps_retention_ratio, -row.benchmark_excess_return,
        -row.sharpe, -row.sortino, -row.bootstrap_lower_endpoint,
        row.annualized_one_way_turnover, row.walk_forward_positive_concentration,
        row.signal_component_count, -row.validation_total_return, -row.cagr, row.candidate_id,
    )


def select_survivor(candidates: tuple[CandidateSurvivorEvidence, ...]) -> str:
    eligible = [row for row in candidates if _eligible(row)]
    if not eligible:
        return "NO_CREDIBLE_STRATEGY_FOUND"
    return min(eligible, key=_survivor_key).candidate_id


class Phase5DownstreamContract(FrozenGate1Model):
    schema_version: Literal["PHASE5-LONG-HISTORY-DURABILITY-CONTRACT-v1"] = (
        "PHASE5-LONG-HISTORY-DURABILITY-CONTRACT-v1"
    )
    trigger: Literal["EXACTLY_ONE_PHASE4_CREDIBLE_CANDIDATE"] = "EXACTLY_ONE_PHASE4_CREDIBLE_CANDIDATE"
    same_strategy_unchanged: Literal[True] = True
    same_rule_set_and_parameter_tuple: Literal[True] = True
    desired_common_history_years: Literal["APPROXIMATELY_15_TO_20_IF_DEFENSIBLE"] = "APPROXIMATELY_15_TO_20_IF_DEFENSIBLE"
    report_actual_longest_defensible_common_history: Literal[True] = True
    retuning_allowed: Literal[False] = False
    etf_substitution_allowed: Literal[False] = False
    synthetic_proxy_allowed_without_separate_preregistration: Literal[False] = False
    phase5_feedback_into_phase4_allowed: Literal[False] = False
    provider_access_authorized: Literal[False] = False
    protected_symbol_access_authorized: Literal[False] = False
    final_holdout_release_authorized: Literal[False] = False
    rolling_calendar_month_horizons: tuple[int, ...] = (12, 36, 60)
    required_reporting: tuple[str, ...] = (
        "CAGR", "CALENDAR_YEAR_RETURNS", "CALENDAR_MONTH_RETURNS",
        "POSITIVE_YEAR_PERCENTAGE", "POSITIVE_MONTH_PERCENTAGE",
        "AVERAGE_WINNING_MONTH", "AVERAGE_LOSING_MONTH", "WORST_YEAR",
        "WORST_MONTH", "LONGEST_LOSING_MONTH_SEQUENCE", "ROLLING_12_MONTH",
        "ROLLING_3_YEAR", "ROLLING_5_YEAR_WHEN_COMPLETE", "RETURN_CONCENTRATION",
        "RECOVERY_CHARACTERISTICS", "REGIME_CONSISTENCY", "REALISTIC_COSTS_SLIPPAGE",
    )
    drawdown_requires_dq030_resolution: Literal[True] = True
    governing_question: Literal["Can this exact frozen strategy remain useful for many years without periodic retuning?"] = (
        "Can this exact frozen strategy remain useful for many years without periodic retuning?"
    )


PHASE5_CONTRACT = Phase5DownstreamContract()
