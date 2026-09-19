from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from investment_tracker.governance import LockedHoldoutError
from investment_tracker.quant.validation.access import (
    DataStage,
    HoldoutAccessError,
    ResearchDataView,
    ResearchStage,
    SplitDefinition,
)
from investment_tracker.quant.validation.holdout import (
    FrozenCandidateManifest,
    HoldoutReuseError,
    SealedHoldoutEvaluator,
)


class RecordingStore:
    def __init__(self):
        self.calls: list[tuple[str, DataStage]] = []

    def load(self, symbol: str, stage: DataStage):
        self.calls.append((symbol, stage))
        return {"symbol": symbol, "stage": stage.value}


def split() -> SplitDefinition:
    return SplitDefinition.create(
        version="QUANT-SPLIT-v1",
        train_start=date(2010, 1, 1),
        train_end=date(2018, 12, 31),
        validation_start=date(2019, 1, 1),
        validation_end=date(2022, 12, 31),
        final_holdout_start=date(2023, 1, 1),
        final_holdout_end=date(2025, 12, 31),
    )


def manifest(fee_bps: float = 1.0) -> FrozenCandidateManifest:
    return FrozenCandidateManifest.create(
        candidate_id="candidate-001",
        strategy_family="trend",
        strategy_code_hash="a" * 64,
        strategy_parameters={"fast_window": 20, "slow_window": 50, "allocation": 1.0},
        universe_config_hash="b" * 64,
        data_manifest_hashes={"SPY": "c" * 64},
        split_definition_hash=split().digest,
        engine_version="QUANT-ENGINE-v1",
        fee_model={"name": "bps", "commission_bps": fee_bps},
        slippage_model={"name": "bps", "slippage_bps": 2.0},
        execution_convention="COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN",
        dependency_lock_hash="d" * 64,
        git_commit="e" * 40,
        frozen_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )


def test_split_is_hashed_and_stage_boundaries_are_disjoint() -> None:
    definition = split()
    assert len(definition.digest) == 64
    assert definition.stage_for(date(2015, 1, 2)) is DataStage.TRAIN
    assert definition.stage_for(date(2020, 1, 2)) is DataStage.VALIDATION
    assert definition.stage_for(date(2024, 1, 2)) is DataStage.FINAL_HOLDOUT
    assert definition.stage_for(date(2009, 1, 2)) is None


def test_research_view_loads_only_train_and_validation() -> None:
    store = RecordingStore()
    view = ResearchDataView(store)
    assert view.load("SPY", ResearchStage.TRAIN)["stage"] == "TRAIN"
    assert view.load("SPY", ResearchStage.VALIDATION)["stage"] == "VALIDATION"
    assert store.calls == [
        ("SPY", DataStage.TRAIN),
        ("SPY", DataStage.VALIDATION),
    ]


def test_research_view_rejects_final_holdout_before_store_access() -> None:
    store = RecordingStore()
    view = ResearchDataView(store)
    with pytest.raises(HoldoutAccessError, match="sealed"):
        view.load("SPY", DataStage.FINAL_HOLDOUT)
    assert store.calls == []


def test_research_view_guards_symbol_before_store_access() -> None:
    store = RecordingStore()
    view = ResearchDataView(store)
    with pytest.raises(LockedHoldoutError):
        view.load("URNM", ResearchStage.TRAIN)
    assert store.calls == []


def test_candidate_digest_covers_fee_and_every_manifest_dimension() -> None:
    first = manifest(fee_bps=1.0)
    second = manifest(fee_bps=2.0)
    assert first.digest != second.digest
    assert first.status == "FROZEN_CANDIDATE"
    assert set(first.data_manifest_hashes) == {"SPY"}


def test_holdout_evaluation_closes_candidate_cycle_before_loading(tmp_path: Path) -> None:
    store = RecordingStore()
    callback_calls = 0

    def evaluate_candidate(candidate, data_by_symbol):
        nonlocal callback_calls
        callback_calls += 1
        return {"total_return": 0.05, "candidate_digest": candidate.digest}

    evaluator = SealedHoldoutEvaluator(store, evaluate_candidate)
    result = evaluator.evaluate(manifest(), tmp_path)
    assert result.status == "FROZEN_CANDIDATE_NOT_PRODUCTION_APPROVED"
    assert result.metrics["total_return"] == 0.05
    assert store.calls == [("SPY", DataStage.FINAL_HOLDOUT)]
    assert callback_calls == 1
    assert len(list(tmp_path.glob("*.started.json"))) == 1
    assert len(list(tmp_path.glob("*.result.json"))) == 1

    with pytest.raises(HoldoutReuseError):
        evaluator.evaluate(manifest(), tmp_path)
    assert callback_calls == 1


def test_failed_holdout_evaluation_still_consumes_candidate(tmp_path: Path) -> None:
    store = RecordingStore()

    def fail(candidate, data_by_symbol):
        raise RuntimeError("calculation failed")

    evaluator = SealedHoldoutEvaluator(store, fail)
    with pytest.raises(RuntimeError, match="calculation failed"):
        evaluator.evaluate(manifest(), tmp_path)
    with pytest.raises(HoldoutReuseError):
        evaluator.evaluate(manifest(), tmp_path)
