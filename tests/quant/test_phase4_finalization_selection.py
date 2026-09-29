from __future__ import annotations

from investment_tracker.quant.phase4.finalization.selection import (
    rejection_reasons,
    select_candidate_id,
)
from investment_tracker.quant.phase4.preregistration.policy import CandidateSurvivorEvidence


def _evidence(candidate_id: str, *, excess: float = 0.10, joint: int = 4) -> CandidateSurvivorEvidence:
    folds = (0.04, 0.03, 0.02, 0.01)
    fold_excess = tuple(0.01 if index < joint else -0.01 for index in range(4))
    return CandidateSurvivorEvidence(
        candidate_id=candidate_id,
        is_baseline=False,
        validation_total_return=0.25,
        cash_return=0.0,
        benchmark_excess_return=excess,
        sharpe=1.0,
        sortino=1.2,
        walk_forward_returns=folds,
        walk_forward_benchmark_excess=fold_excess,
        neighborhood_valid_count=3,
        neighborhood_positive_fraction=1.0,
        neighborhood_median_benchmark_excess=0.01,
        friction_returns_bps={0:0.27,3:0.25,10:0.23,25:0.20,50:0.16},
        annualized_one_way_turnover=2.0,
        average_gross_exposure=0.8,
        all_session_exposures_valid=True,
        bootstrap_lower_endpoint=0.0001,
        fixed_identity_invariant=True,
        durability_evidence_complete=True,
        walk_forward_joint_consistency=joint,
        positive_year_percentage=1.0,
        minimum_rolling_36_month_return=0.05,
        minimum_rolling_12_month_return=0.01,
        longest_losing_month_sequence=2,
        worst_year=0.02,
        worst_month=-0.03,
        positive_year_return_concentration=0.4,
        top_three_positive_month_return_concentration=0.3,
        positive_month_percentage=0.65,
        friction_25bps_retention_ratio=0.20/0.25,
        signal_component_count=3,
        cagr=0.06,
        max_drawdown=None,
        calmar=None,
        dsr=None,
        pbo=None,
    )


def test_selection_delegates_to_frozen_policy() -> None:
    a = _evidence("phase4-" + "a" * 64, joint=3)
    b = _evidence("phase4-" + "b" * 64, joint=4)
    assert select_candidate_id((a, b)) == b.candidate_id


def test_zero_eligible_returns_no_credible_strategy() -> None:
    row = _evidence("phase4-" + "c" * 64, excess=-0.01)
    assert select_candidate_id((row,)) == "NO_CREDIBLE_STRATEGY_FOUND"
    assert "BENCHMARK_EXCESS_NONPOSITIVE" in rejection_reasons(row)
