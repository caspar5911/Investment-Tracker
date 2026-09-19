from __future__ import annotations

import pytest

from investment_tracker.quant.optimizer.scorer import CandidateEvidence, score_candidate
from investment_tracker.quant.validation.bootstrap import bootstrap_interval
from investment_tracker.quant.validation.robustness import (
    friction_scenarios,
    neighbor_parameters,
    robustness_summary,
)


def evidence(**updates) -> CandidateEvidence:
    values = {
        "validation_cagr": 0.10,
        "sharpe": 1.0,
        "sortino": 1.4,
        "calmar": 0.8,
        "benchmark_excess_return": 0.03,
        "walk_forward_consistency": 0.75,
        "parameter_stability": 0.80,
        "turnover": 0.50,
        "max_drawdown": -0.125,
        "friction_sensitivity": 0.90,
        "period_concentration": 0.40,
        "out_of_sample_improved": True,
        "robustness_deteriorated": False,
    }
    values.update(updates)
    return CandidateEvidence(**values)


def test_trend_neighbors_include_reasonable_values_and_not_base() -> None:
    neighbors = neighbor_parameters(
        "trend",
        {"fast_window": 20, "slow_window": 50, "allocation": 1.0},
    )
    assert {"fast_window": 15, "slow_window": 40, "allocation": 1.0} in neighbors
    assert {"fast_window": 25, "slow_window": 60, "allocation": 1.0} in neighbors
    assert {"fast_window": 20, "slow_window": 50, "allocation": 1.0} not in neighbors
    assert all(item["fast_window"] < item["slow_window"] for item in neighbors)


def test_friction_scenarios_are_sorted_unique_and_include_stress() -> None:
    assert friction_scenarios(10.0) == (0.0, 10.0, 25.0, 50.0)


def test_seeded_bootstrap_is_deterministic() -> None:
    first = bootstrap_interval([0.01, 0.02, -0.01, 0.03], draws=500, seed=7)
    second = bootstrap_interval([0.01, 0.02, -0.01, 0.03], draws=500, seed=7)
    assert first == second
    assert first[0] <= first[1]


def test_robustness_summary_measures_stability_cost_and_period_concentration() -> None:
    result = robustness_summary(
        base_validation_return=0.10,
        neighbor_returns=[0.08, 0.09, -0.01, 0.07],
        friction_returns={0.0: 0.11, 10.0: 0.10, 25.0: 0.08, 50.0: 0.06},
        fold_returns=[0.02, 0.03, -0.01, 0.04],
    )
    assert result.parameter_stability == 0.75
    assert result.friction_sensitivity == pytest.approx(0.06 / 0.11)
    assert result.walk_forward_consistency == 0.75
    assert result.period_concentration == pytest.approx(0.04 / 0.08)
    assert not result.deteriorated


def test_unstable_neighbor_performance_reduces_score() -> None:
    stable = score_candidate(evidence(parameter_stability=0.9))
    unstable = score_candidate(evidence(parameter_stability=0.2))
    assert stable.total is not None and unstable.total is not None
    assert stable.total > unstable.total


def test_turnover_drawdown_and_cost_sensitivity_are_penalized() -> None:
    strong = score_candidate(evidence())
    fragile = score_candidate(
        evidence(turnover=4.0, max_drawdown=-0.45, friction_sensitivity=0.1)
    )
    assert strong.total is not None and fragile.total is not None
    assert strong.total > fragile.total


def test_missing_decision_critical_metric_is_unrankable() -> None:
    result = score_candidate(evidence(sharpe=None))
    assert result.status == "UNRANKABLE"
    assert result.total is None
    assert "sharpe" in result.reasons
