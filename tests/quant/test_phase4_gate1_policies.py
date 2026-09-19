from __future__ import annotations

from datetime import date

import pytest

from investment_tracker.quant.phase4.preregistration.policy import (
    CandidateOOSOutcome,
    CandidateSurvivorEvidence,
    DQ030UnavailableMetrics,
    DURABILITY_POLICY,
    FAMILY_STOP_POLICY,
    PHASE5_CONTRACT,
    SURVIVOR_POLICY,
    compute_durability_evidence,
    select_survivor,
    update_oos_failure_streak,
)


def test_persistent_oos_failure_is_exactly_fifty_consecutive_nonpositive_or_unknown() -> None:
    streak = 0
    for _ in range(49):
        streak, stopped = update_oos_failure_streak(streak, CandidateOOSOutcome(benchmark_excess_return=0.0))
        assert stopped is False
    streak, stopped = update_oos_failure_streak(streak, CandidateOOSOutcome(benchmark_excess_return=None))
    assert (streak, stopped) == (50, True)
    assert FAMILY_STOP_POLICY.persistent_oos_failure_consecutive_count == 50


def test_positive_excess_resets_and_isolated_robustness_failures_never_increment() -> None:
    streak, stopped = update_oos_failure_streak(12, CandidateOOSOutcome(
        benchmark_excess_return=0.01, robustness_passed=False,
        friction_passed=False, bootstrap_passed=False,
        neighborhood_passed=False, absolute_return_passed=False,
    ))
    assert (streak, stopped) == (0, False)
    streak, stopped = update_oos_failure_streak(7, CandidateOOSOutcome(
        benchmark_excess_return=0.01, robustness_passed=False,
    ))
    assert (streak, stopped) == (0, False)


def test_fixed_strategy_and_frozen_validation_semantics_are_explicit() -> None:
    policy = DURABILITY_POLICY
    assert policy.deployment_strategy_count == 1
    assert policy.position_direction == "LONG_ONLY"
    assert policy.rule_set_mode == policy.parameter_tuple_mode == "FIXED"
    assert policy.parameter_fitting_from_train is False
    assert policy.annual_reoptimization is False
    assert policy.periodic_reoptimization is False
    assert policy.primary_proof_mode == "FIXED_PARAMETER_CHRONOLOGICAL"
    assert policy.adaptive_walk_forward_in_phase4 is False
    assert policy.cagr_hard_target is None
    assert policy.durability_precedes_fitted_cagr is True
    assert policy.train_start == date(2014, 1, 2)
    assert policy.train_end == date(2018, 12, 31)
    assert policy.train_sessions == 1258
    assert policy.validation_start == date(2019, 1, 2)
    assert policy.validation_end == date(2022, 12, 30)
    assert policy.validation_sessions == 1008
    assert policy.validation_portfolio_reset_once is True
    assert policy.fold_portfolio_resets is False
    assert policy.train_pnl_in_validation is False
    assert policy.first_scored_signal_on_validation_session is True
    assert policy.next_eligible_validation_session_execution is True


def test_monthly_yearly_metrics_and_losing_streak_use_compounding_and_strict_signs() -> None:
    sessions = (
        date(2019, 1, 2), date(2019, 1, 3),
        date(2019, 2, 1), date(2019, 3, 1), date(2020, 1, 2),
    )
    evidence = compute_durability_evidence(
        sessions=sessions,
        daily_returns=(0.10, -0.05, -0.02, 0.0, 0.03),
        expected_sessions=sessions,
    )
    months = {item.period: item.return_value for item in evidence.calendar_month_returns}
    assert months["2019-01"] == pytest.approx(1.10 * 0.95 - 1)
    assert evidence.positive_month_percentage == pytest.approx(2 / 4)
    assert evidence.average_positive_month == pytest.approx(((1.10 * 0.95 - 1) + 0.03) / 2)
    assert evidence.average_negative_month == pytest.approx(-0.02)
    assert evidence.worst_month == pytest.approx(-0.02)
    assert evidence.longest_losing_month_sequence == 1
    assert evidence.calendar_year_returns[0].return_value == pytest.approx(1.10 * 0.95 * 0.98 - 1)


def test_incomplete_periods_are_unknown_and_excluded_from_aggregates() -> None:
    evidence = compute_durability_evidence(
        sessions=(date(2020, 1, 2),), daily_returns=(0.1,),
        expected_sessions=(date(2020, 1, 2), date(2020, 1, 3)),
    )
    assert evidence.calendar_month_returns[0].availability == "UNKNOWN"
    assert evidence.calendar_month_returns[0].return_value is None
    assert evidence.positive_month_percentage is None
    assert evidence.positive_month_percentage_status == "UNKNOWN"


def test_gregorian_rolling_anchors_are_not_fixed_session_counts() -> None:
    sessions = tuple(date(year, month, 1) for year in range(2017, 2023) for month in range(1, 13))
    evidence = compute_durability_evidence(
        sessions=sessions, daily_returns=tuple(0.01 for _ in sessions), expected_sessions=sessions,
    )
    first_12 = evidence.rolling_12_month_returns[0]
    assert first_12.endpoint == date(2018, 1, 1)
    assert first_12.anchor == date(2017, 1, 1)
    first_36 = evidence.rolling_36_month_returns[0]
    assert first_36.endpoint == date(2020, 1, 1)
    assert first_36.anchor == date(2017, 1, 1)
    first_60 = evidence.rolling_60_month_returns[0]
    assert first_60.endpoint == date(2022, 1, 1)
    assert first_60.anchor == date(2017, 1, 1)
    assert evidence.rolling_12_month_summary.status == "AVAILABLE"
    assert evidence.rolling_36_month_summary.status == "AVAILABLE"


def test_concentration_formulas_and_insufficient_data_are_explicit() -> None:
    sessions = (date(2020, 1, 2), date(2020, 2, 3), date(2020, 3, 2), date(2020, 4, 1))
    evidence = compute_durability_evidence(sessions, (0.10, 0.05, -0.02, 0.01), sessions)
    assert evidence.positive_month_return_concentration == pytest.approx(0.10 / 0.16)
    assert evidence.top_three_positive_month_return_concentration == pytest.approx(1.0)
    assert evidence.rolling_36_month_summary.status == "UNKNOWN"
    assert evidence.rolling_36_month_summary.reason == "INSUFFICIENT_DATA"


def _candidate(candidate_id: str, *, cagr: float = 0.30,
               positive_years: float = 0.75, min_3y: float = 0.15,
               eligible: bool = True, baseline: bool = False) -> CandidateSurvivorEvidence:
    return CandidateSurvivorEvidence(
        candidate_id=candidate_id, is_baseline=baseline,
        validation_total_return=0.40 if eligible else -0.01, cash_return=0.0,
        benchmark_excess_return=0.10, sharpe=1.0, sortino=1.2,
        walk_forward_returns=(0.05, 0.04, 0.03, -0.01),
        walk_forward_benchmark_excess=(0.02, 0.01, 0.01, -0.01),
        neighborhood_valid_count=3, neighborhood_positive_fraction=2 / 3,
        neighborhood_median_benchmark_excess=0.0,
        friction_returns_bps={0: 0.40, 3: 0.38, 10: 0.35, 25: 0.30, 50: 0.20},
        annualized_one_way_turnover=4.0, average_gross_exposure=0.8,
        all_session_exposures_valid=True, bootstrap_lower_endpoint=0.0,
        fixed_identity_invariant=True, durability_evidence_complete=True,
        walk_forward_joint_consistency=3, positive_year_percentage=positive_years,
        minimum_rolling_36_month_return=min_3y, minimum_rolling_12_month_return=0.02,
        longest_losing_month_sequence=2, worst_year=-0.05, worst_month=-0.03,
        positive_year_return_concentration=0.45,
        top_three_positive_month_return_concentration=0.35,
        positive_month_percentage=0.60, friction_25bps_retention_ratio=0.30 / 0.38,
        signal_component_count=4, cagr=cagr,
        max_drawdown=None, calmar=None, dsr=None, pbo=None,
    )


def test_all_hard_gates_reject_missing_or_failed_evidence_and_baselines_cannot_win() -> None:
    assert select_survivor((_candidate("phase4-" + "1" * 64, eligible=False),)) == "NO_CREDIBLE_STRATEGY_FOUND"
    assert select_survivor((_candidate("baseline", baseline=True),)) == "NO_CREDIBLE_STRATEGY_FOUND"
    missing = _candidate("phase4-" + "2" * 64).model_copy(update={"durability_evidence_complete": False})
    assert select_survivor((missing,)) == "NO_CREDIBLE_STRATEGY_FOUND"


@pytest.mark.parametrize(
    "update",
    [
        {"validation_total_return": 0.0},
        {"benchmark_excess_return": 0.0},
        {"sharpe": 0.0},
        {"sortino": None},
        {"walk_forward_returns": (0.05, 0.04, -0.03, -0.01)},
        {"neighborhood_valid_count": 1},
        {"neighborhood_positive_fraction": 0.5},
        {"neighborhood_median_benchmark_excess": -0.001},
        {"friction_returns_bps": {0: 0.4, 3: 0.38, 10: 0.35, 25: 0.30}},
        {"friction_returns_bps": {0: 0.4, 3: 0.38, 10: 0.35, 25: 0.0, 50: -0.1}},
        {"friction_25bps_retention_ratio": 999.0},
        {"walk_forward_joint_consistency": 4},
        {"walk_forward_returns": (0.30, 0.01, 0.01, -0.01)},
        {"annualized_one_way_turnover": 12.0001},
        {"average_gross_exposure": 1.0001},
        {"all_session_exposures_valid": False},
        {"bootstrap_lower_endpoint": -0.0001},
        {"fixed_identity_invariant": False},
        {"durability_evidence_complete": False},
        {"max_drawdown": -0.2},
    ],
)
def test_each_hard_gate_fails_closed(update) -> None:
    row = _candidate("phase4-" + "3" * 64).model_copy(update=update)
    assert select_survivor((row,)) == "NO_CREDIBLE_STRATEGY_FOUND"


def test_robustness_first_order_can_rank_lower_cagr_candidate_first() -> None:
    fragile = _candidate("phase4-" + "a" * 64, cagr=0.30, positive_years=0.75, min_3y=0.05)
    durable = _candidate("phase4-" + "b" * 64, cagr=0.18, positive_years=1.0, min_3y=0.12)
    assert select_survivor((fragile, durable)) == durable.candidate_id
    assert SURVIVOR_POLICY.ranking_keys[-2:] == ("cagr:DESC", "candidate_id:ASC")
    assert SURVIVOR_POLICY.ranking_keys[0] == "walk_forward_joint_consistency:DESC"


def test_unavailable_governed_statistics_remain_unknown() -> None:
    assert DQ030UnavailableMetrics().model_dump() == {
        "max_drawdown": None, "max_drawdown_status": "UNKNOWN",
        "calmar": None, "calmar_status": "UNKNOWN",
        "dsr": None, "dsr_status": "UNKNOWN", "dsr_reason": "NOT_IMPLEMENTED",
        "pbo": None, "pbo_status": "UNKNOWN", "pbo_reason": "NOT_IMPLEMENTED",
    }


def test_phase5_contract_is_one_way_same_tuple_and_does_not_authorize_execution() -> None:
    assert PHASE5_CONTRACT.trigger == "EXACTLY_ONE_PHASE4_CREDIBLE_CANDIDATE"
    assert PHASE5_CONTRACT.same_strategy_unchanged is True
    assert PHASE5_CONTRACT.retuning_allowed is False
    assert PHASE5_CONTRACT.etf_substitution_allowed is False
    assert PHASE5_CONTRACT.synthetic_proxy_allowed_without_separate_preregistration is False
    assert PHASE5_CONTRACT.phase5_feedback_into_phase4_allowed is False
    assert PHASE5_CONTRACT.provider_access_authorized is False
    assert PHASE5_CONTRACT.final_holdout_release_authorized is False
    assert PHASE5_CONTRACT.rolling_calendar_month_horizons == (12, 36, 60)
    assert PHASE5_CONTRACT.drawdown_requires_dq030_resolution is True
