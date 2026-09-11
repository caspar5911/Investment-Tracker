from __future__ import annotations

from investment_tracker.quant.optimizer.candidate_generator import CandidateGenerator
from investment_tracker.quant.optimizer.search import (
    CandidateEvaluation,
    SearchBudget,
    run_search,
)


def generator(count: int) -> CandidateGenerator:
    return CandidateGenerator.from_parameter_grid(
        "momentum",
        {"lookback": list(range(1, count + 1)), "allocation": [1.0]},
    )


def test_parameter_grid_order_and_ids_are_deterministic() -> None:
    first = list(CandidateGenerator.from_parameter_grid(
        "trend", {"slow_window": [50, 40], "fast_window": [20, 15], "allocation": [1.0]}
    ))
    second = list(CandidateGenerator.from_parameter_grid(
        "trend", {"allocation": [1.0], "fast_window": [20, 15], "slow_window": [50, 40]}
    ))
    assert first == second
    assert len({item.candidate_id for item in first}) == 4


def test_search_never_exceeds_family_budget() -> None:
    result = run_search(
        generator(700),
        lambda candidate: CandidateEvaluation(candidate, float(candidate.parameters["lookback"]), True, False),
        SearchBudget(max_candidates=500, patience=50, meaningful_improvement=0.0),
    )
    assert result.evaluated_count == 500
    assert result.stop_reason == "MAX_CANDIDATES"


def test_search_stops_after_fifty_without_meaningful_improvement() -> None:
    result = run_search(
        generator(100),
        lambda candidate: CandidateEvaluation(candidate, 1.0, True, False),
        SearchBudget(max_candidates=500, patience=50, meaningful_improvement=0.01),
    )
    assert result.evaluated_count == 51
    assert result.stop_reason == "NO_MEANINGFUL_IMPROVEMENT_50"


def test_search_stops_immediately_when_robustness_deteriorates() -> None:
    result = run_search(
        generator(10),
        lambda candidate: CandidateEvaluation(candidate, 1.0, True, True),
        SearchBudget(max_candidates=500, patience=50, meaningful_improvement=0.01),
    )
    assert result.evaluated_count == 1
    assert result.stop_reason == "ROBUSTNESS_DETERIORATED"


def test_search_stops_after_persistent_out_of_sample_failure() -> None:
    result = run_search(
        generator(100),
        lambda candidate: CandidateEvaluation(candidate, 1.0, False, False),
        SearchBudget(max_candidates=500, patience=50, meaningful_improvement=0.01),
    )
    assert result.evaluated_count == 50
    assert result.stop_reason == "OUT_OF_SAMPLE_NOT_IMPROVED_50"
