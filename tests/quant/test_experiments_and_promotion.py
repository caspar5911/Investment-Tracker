from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_tracker.quant.experiments import (
    ArtifactExistsError,
    ExperimentRecord,
    ExperimentStore,
    ResearchCandidateManifest,
)
from investment_tracker.quant.promotion import (
    BaselineRegistry,
    PromotionBlockedError,
    PromotionGate,
    promote_candidate,
)


def candidate_manifest(**parameter_updates) -> ResearchCandidateManifest:
    parameters = {"fast_window": 20, "slow_window": 50, "allocation": 1.0}
    parameters.update(parameter_updates)
    return ResearchCandidateManifest.create(
        candidate_id="candidate-001",
        strategy_family="trend",
        strategy_code_hash="a" * 64,
        strategy_parameters=parameters,
        universe_config_hash="b" * 64,
        data_manifest_hashes={"SPY": "c" * 64},
        split_definition_hash="d" * 64,
        engine_version="QUANT-ENGINE-v1",
        fee_model={"commission_bps": 1.0},
        slippage_model={"slippage_bps": 2.0},
        execution_convention="COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN",
        dependency_lock_hash="e" * 64,
        git_commit="f" * 40,
        created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )


def experiment(experiment_id: str = "exp-001", **parameter_updates) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        status="RESEARCH_ONLY",
        candidate_manifest=candidate_manifest(**parameter_updates),
        symbols=("SPY",),
        train_period=(date(2010, 1, 1), date(2018, 12, 31)),
        validation_period=(date(2019, 1, 1), date(2022, 12, 31)),
        metrics={"cagr": 0.08, "max_drawdown": -0.12},
        validation_metrics={"cagr": 0.06, "sharpe": 0.9},
        score=62.5,
        accepted=True,
        reason="deterministic research gates passed",
        stop_reason="EXHAUSTED",
        recorded_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )


def passed_gate() -> PromotionGate:
    return PromotionGate(
        research_passed=True,
        validation_passed=True,
        walk_forward_passed=True,
        robustness_passed=True,
        benchmark_passed=True,
        tests_passed=True,
    )


def test_experiment_store_never_overwrites(tmp_path: Path) -> None:
    store = ExperimentStore(tmp_path)
    first = store.append(experiment())
    assert first.exists()
    with pytest.raises(ArtifactExistsError, match="already exists"):
        store.append(experiment())
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_rejected_experiment_remains_when_subsequent_candidate_is_persisted(tmp_path: Path) -> None:
    store = ExperimentStore(tmp_path)
    rejected = experiment("exp-rejected").model_copy(update={
        "accepted": False,
        "reason": "rejected: ROBUSTNESS_DETERIORATED",
    })
    subsequent = experiment("exp-subsequent")

    first_path = store.append(rejected)
    first_bytes = first_path.read_bytes()
    store.append(subsequent)

    assert first_path.read_bytes() == first_bytes
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_candidate_digest_changes_with_parameters() -> None:
    assert candidate_manifest().digest != candidate_manifest(fast_window=25).digest


def test_promotion_fails_closed_when_any_gate_is_false(tmp_path: Path) -> None:
    registry = BaselineRegistry(tmp_path / "baselines")
    gate = passed_gate().model_copy(update={"robustness_passed": False})
    with pytest.raises(PromotionBlockedError, match="robustness_passed"):
        promote_candidate(experiment(), gate, registry)
    assert not (tmp_path / "baselines").exists()


def test_promotion_adds_new_version_without_mutating_existing_baseline(tmp_path: Path) -> None:
    registry_root = tmp_path / "baselines"
    existing = registry_root / "frozen-existing.json"
    existing.parent.mkdir(parents=True)
    existing.write_text("immutable baseline", encoding="utf-8")
    before = existing.read_bytes()

    snapshot = promote_candidate(experiment(), passed_gate(), BaselineRegistry(registry_root))
    assert existing.read_bytes() == before
    assert snapshot.status == "VALIDATED_SNAPSHOT"
    assert (registry_root / snapshot.digest / "snapshot.json").exists()


def test_validated_snapshot_is_frozen_and_change_requires_new_digest(tmp_path: Path) -> None:
    registry = BaselineRegistry(tmp_path)
    first = promote_candidate(experiment("exp-1"), passed_gate(), registry)
    second = promote_candidate(experiment("exp-2", fast_window=25), passed_gate(), registry)
    assert first.digest != second.digest
    with pytest.raises(ValidationError):
        first.status = "RESEARCH_ONLY"


def test_baseline_registry_never_overwrites_same_snapshot(tmp_path: Path) -> None:
    registry = BaselineRegistry(tmp_path)
    record = experiment()
    snapshot = promote_candidate(record, passed_gate(), registry)
    with pytest.raises(ArtifactExistsError):
        registry.add(snapshot)
