from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import investment_tracker.quant.workflow as workflow
from investment_tracker.quant.configuration import load_default_config
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
    assert result.stop_reason == "NO_MEANINGFUL_IMPROVEMENT"


def test_robustness_failure_rejects_candidate_but_family_continues() -> None:
    evaluated: list[int] = []

    def evaluate(candidate):
        lookback = int(candidate.parameters["lookback"])
        evaluated.append(lookback)
        return CandidateEvaluation(candidate, float(lookback), True, lookback == 1)

    result = run_search(
        generator(3),
        evaluate,
        SearchBudget(max_candidates=500, patience=50, meaningful_improvement=0.01),
    )
    assert evaluated == [1, 2, 3]
    assert result.evaluated_count == 3
    assert result.best is not None
    assert result.best.candidate.parameters["lookback"] == 3
    assert result.stop_reason == "EXHAUSTED"


def test_search_stops_after_persistent_out_of_sample_failure() -> None:
    result = run_search(
        generator(100),
        lambda candidate: CandidateEvaluation(candidate, 1.0, False, False),
        SearchBudget(max_candidates=500, patience=50, meaningful_improvement=0.01),
    )
    assert result.evaluated_count == 50
    assert result.stop_reason == "PERSISTENT_OOS_FAILURE"


def test_isolated_oos_failure_does_not_terminate_family_and_success_resets_streak() -> None:
    outcomes = iter((False, True, False, True))
    result = run_search(
        generator(4),
        lambda candidate: CandidateEvaluation(candidate, float(candidate.parameters["lookback"]), next(outcomes), False),
        SearchBudget(max_candidates=500, patience=2, meaningful_improvement=0.0),
    )
    assert result.evaluated_count == 4
    assert result.stop_reason == "EXHAUSTED"


def test_persistent_oos_failure_requires_exact_configured_consecutive_count() -> None:
    outcomes = iter((False, True, False, False, False, True))
    result = run_search(
        generator(6),
        lambda candidate: CandidateEvaluation(candidate, float(candidate.parameters["lookback"]), next(outcomes), False),
        SearchBudget(max_candidates=500, patience=3, meaningful_improvement=0.0),
    )
    assert result.evaluated_count == 5
    assert result.stop_reason == "PERSISTENT_OOS_FAILURE"


def test_cached_universe_workflow_uses_family_policy_after_robustness_rejection(
    monkeypatch,
    tmp_path,
) -> None:
    frame = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]},
        index=pd.DatetimeIndex([pd.Timestamp("2020-01-02", tz="UTC")], name="timestamp"),
    )
    monkeypatch.setattr(
        workflow.ImmutableParquetCache,
        "find",
        lambda self, request: SimpleNamespace(
            frame=frame,
            metadata=SimpleNamespace(content_hash=request.symbol.lower().encode().hex().ljust(64, "0")[:64]),
        ),
    )
    monkeypatch.setattr(
        workflow,
        "default_generators",
        lambda: {"momentum": generator(3)},
    )
    attempted: list[int] = []

    def evaluate(candidates, *args, **kwargs):
        configuration = next(iter(candidates))
        lookback = int(configuration.parameters["lookback"])
        attempted.append(lookback)
        return [SimpleNamespace(
            configuration=configuration,
            evidence=SimpleNamespace(
                robustness_deteriorated=lookback == 1,
                out_of_sample_improved=True,
            ),
            score=SimpleNamespace(total=float(lookback)),
        )]

    monkeypatch.setattr(workflow, "_evaluate_and_store", evaluate)
    summary = workflow.optimize_cached_universe(
        config=load_default_config(),
        cache_root=tmp_path / "cache",
        results_dir=tmp_path / "results",
    )

    assert attempted == [1, 2, 3]
    assert summary["experiment_count"] == 3
    assert summary["family_stop_reasons"] == {"momentum": "EXHAUSTED"}


def test_candidate_rejection_reason_names_robustness_without_family_stop() -> None:
    reasons = workflow._candidate_rejection_reasons(
        score=SimpleNamespace(status="RANKED", total=70.0),
        benchmark_excess_return=0.02,
        robustness_deteriorated=True,
        walk_forward_consistency=1.0,
    )
    assert reasons == ("ROBUSTNESS_DETERIORATED",)
