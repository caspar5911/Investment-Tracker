from __future__ import annotations

import math

from investment_tracker.quant.phase4.preregistration.policy import (
    CandidateSurvivorEvidence,
    _eligible,
    select_survivor,
)

from .models import Phase4Audit, Phase4Decision


def rejection_reasons(row: CandidateSurvivorEvidence) -> tuple[str, ...]:
    reasons: list[str] = []
    joint = sum(
        return_value > 0 and excess > 0
        for return_value, excess in zip(
            row.walk_forward_returns,
            row.walk_forward_benchmark_excess,
            strict=True,
        )
    )
    positives = [value for value in row.walk_forward_returns if value > 0]
    concentration = (
        max(positives) / sum(positives)
        if positives and sum(positives) > 0
        else None
    )
    friction_3 = row.friction_returns_bps.get(3)
    expected_retention = (
        row.friction_returns_bps.get(25, 0.0) / friction_3
        if friction_3 is not None and friction_3 > 0
        else None
    )
    if row.is_baseline:
        reasons.append("BASELINE_NOT_ELIGIBLE")
    if not (row.validation_total_return > 0 and row.validation_total_return > row.cash_return):
        reasons.append("VALIDATION_RETURN_NONPOSITIVE_OR_NOT_ABOVE_CASH")
    if row.benchmark_excess_return <= 0:
        reasons.append("BENCHMARK_EXCESS_NONPOSITIVE")
    if row.sharpe is None or row.sharpe <= 0:
        reasons.append("SHARPE_UNAVAILABLE_OR_NONPOSITIVE")
    if row.sortino is None or row.sortino <= 0:
        reasons.append("SORTINO_UNAVAILABLE_OR_NONPOSITIVE")
    if joint < 3:
        reasons.append("INSUFFICIENT_JOINT_POSITIVE_FOLDS")
    if row.walk_forward_joint_consistency != joint:
        reasons.append("WALK_FORWARD_JOINT_CONSISTENCY_MISMATCH")
    if row.neighborhood_valid_count < 2:
        reasons.append("INSUFFICIENT_VALID_NEIGHBORS")
    if row.neighborhood_positive_fraction is None or row.neighborhood_positive_fraction < 2 / 3:
        reasons.append("NEIGHBOR_POSITIVE_FRACTION_TOO_LOW_OR_UNKNOWN")
    if row.neighborhood_median_benchmark_excess is None or row.neighborhood_median_benchmark_excess < 0:
        reasons.append("NEIGHBOR_MEDIAN_BENCHMARK_EXCESS_NEGATIVE_OR_UNKNOWN")
    if set(row.friction_returns_bps) != {0, 3, 10, 25, 50}:
        reasons.append("FRICTION_CASES_INVALID")
    if row.friction_returns_bps.get(25, -1.0) <= 0:
        reasons.append("FRICTION_25BPS_NONPOSITIVE")
    if (
        expected_retention is None
        or not math.isclose(
            row.friction_25bps_retention_ratio,
            expected_retention,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
    ):
        reasons.append("FRICTION_RETENTION_INVALID")
    if concentration is None or concentration > 0.75:
        reasons.append("POSITIVE_FOLD_CONCENTRATION_INVALID")
    if row.annualized_one_way_turnover is None or not 0 <= row.annualized_one_way_turnover <= 12.0:
        reasons.append("TURNOVER_INVALID")
    if row.average_gross_exposure is None or not 0 <= row.average_gross_exposure <= 1.0:
        reasons.append("AVERAGE_GROSS_EXPOSURE_INVALID")
    if not row.all_session_exposures_valid:
        reasons.append("SESSION_EXPOSURE_INVALID")
    if row.bootstrap_lower_endpoint is None or row.bootstrap_lower_endpoint < 0:
        reasons.append("BOOTSTRAP_LOWER_ENDPOINT_NEGATIVE_OR_UNKNOWN")
    if not row.fixed_identity_invariant:
        reasons.append("FIXED_IDENTITY_INVARIANT_FAILURE")
    if not row.durability_evidence_complete:
        reasons.append("DURABILITY_EVIDENCE_INCOMPLETE")
    if any(value is not None for value in (row.max_drawdown, row.calmar, row.dsr, row.pbo)):
        reasons.append("UNAVAILABLE_METRICS_CONVENTION_VIOLATION")
    eligible = _eligible(row)
    if eligible != (not reasons):
        raise ValueError("PHASE4_FINALIZATION_POLICY_DIVERGENCE")
    return tuple(reasons)


def select_candidate_id(
    candidates: tuple[CandidateSurvivorEvidence, ...],
) -> str:
    return select_survivor(candidates)


def select_phase4_decision(
    audit: Phase4Audit,
    *,
    audit_artifact,
) -> Phase4Decision:
    candidates = tuple(
        row.survivor_evidence
        for row in audit.rows
        if row.survivor_evidence is not None
    )
    selected = select_survivor(candidates)
    if selected == "NO_CREDIBLE_STRATEGY_FOUND":
        return Phase4Decision(
            status="NO_CREDIBLE_STRATEGY_FOUND",
            audit_artifact=audit_artifact,
            campaign_result_set=audit.campaign_result_set,
            survivor_policy=audit.survivor_policy,
            durability_policy=audit.durability_policy,
        )
    row = next(item for item in audit.rows if item.candidate_id == selected)
    if row.eligibility_status != "ELIGIBLE":
        raise ValueError("PHASE4_FINALIZATION_SELECTION_MISMATCH")
    return Phase4Decision(
        status="ONE_FROZEN_SURVIVOR",
        audit_artifact=audit_artifact,
        campaign_result_set=audit.campaign_result_set,
        survivor_policy=audit.survivor_policy,
        durability_policy=audit.durability_policy,
        selected_candidate_id=row.candidate_id,
        selected_result_artifact=row.result_artifact,
        selected_population_position=row.population_position,
        selected_family_id=row.family_id,
        selected_hypothesis_id=row.hypothesis_id,
        selected_rule_set_sha256=row.rule_set_sha256,
        selected_parameter_tuple_sha256=row.parameter_tuple_sha256,
        selected_family_definition_sha256=row.family_definition_sha256,
    )
