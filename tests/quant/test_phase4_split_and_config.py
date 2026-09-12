from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import shutil

import pandas as pd
import pytest
from pydantic import ValidationError

from investment_tracker.quant.data.cache import ImmutableParquetCache
from investment_tracker.quant.readiness.constants import (
    PHASE3_DATASETS,
    PHASE3_DQ_SNAPSHOT_PATH,
    PHASE3_DQ_SNAPSHOT_SHA256,
    PHASE3_SYMBOLS,
    PHASE3_UNIVERSE_PATH,
    PHASE3_UNIVERSE_SHA256,
)
from investment_tracker.quant.readiness.hashing import canonical_sha256
from investment_tracker.quant.readiness.models import ReadinessArtifactIdentity
from investment_tracker.quant.readiness.split import (
    Phase3DependencyError,
    Phase4CampaignConfiguration,
    build_campaign_configuration,
    build_split_manifest,
    verify_phase3_dependencies,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ALL_SESSION_SHA256 = (
    "56535e937fab729abdea5c5ebc644de1cf254bb2cce998f8c0d9595fc0e889ba"
)
TRAIN_SESSION_SHA256 = (
    "7d932a1e45637404e2460107ab0f09b33d74d8a28360533bdb9fdaa96416d995"
)
VALIDATION_SESSION_SHA256 = (
    "330dc026e62cea178fc1f28df18ce6479726b4662838bf9454d354c2d00c13d6"
)


def _copy_frozen_inputs(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    paths = [PHASE3_UNIVERSE_PATH, PHASE3_DQ_SNAPSHOT_PATH]
    for dataset in PHASE3_DATASETS:
        paths.extend(
            (
                f"{dataset.path}/metadata.json",
                f"{dataset.path}/bars.parquet",
            )
        )
    for relative in paths:
        source = REPOSITORY_ROOT.joinpath(*relative.split("/"))
        destination = repository.joinpath(*relative.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return repository


def _read_json(repository: Path, relative: str) -> dict[str, object]:
    path = repository.joinpath(*relative.split("/"))
    return json.loads(path.read_bytes())


def _write_json(
    repository: Path,
    relative: str,
    payload: dict[str, object],
) -> None:
    path = repository.joinpath(*relative.split("/"))
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def split_identity() -> ReadinessArtifactIdentity:
    content_sha256 = "a" * 64
    path = (
        "results/phase4/readiness/phase4_split_manifest/sha256/"
        f"{content_sha256}/manifest.json"
    )
    envelope = {
        "content_sha256": content_sha256,
        "kind": "phase4_split_manifest",
        "path": path,
    }
    return ReadinessArtifactIdentity(
        **envelope,
        sha256=canonical_sha256(envelope),
    )


def _replace_interior_session(dataset: object) -> object:
    sessions = list(dataset.sessions)
    sessions[sessions.index(date(2015, 12, 31))] = date(2016, 1, 2)
    replaced = tuple(sessions)
    return dataset.model_copy(
        update={
            "sessions": replaced,
            "sessions_sha256": canonical_sha256(
                tuple(session.isoformat() for session in replaced)
            ),
        }
    )


def test_split_uses_only_frozen_phase3_inputs_and_exact_symbol_order() -> None:
    verified = verify_phase3_dependencies(REPOSITORY_ROOT)
    split = build_split_manifest(verified)

    assert split.symbols == (
        "SPY",
        "QQQ",
        "IWM",
        "TLT",
        "IEF",
        "GLD",
        "VNQ",
        "XLP",
    )
    assert split.phase3_universe_digest == PHASE3_UNIVERSE_SHA256
    assert split.phase3_dq_snapshot_digest == PHASE3_DQ_SNAPSHOT_SHA256
    assert split.phase3_universe_artifact == verified.universe_artifact
    assert split.phase3_dq_snapshot_artifact == verified.dq_snapshot_artifact
    assert split.provider_calls == 0
    assert split.final_holdout_accessed is False
    assert split.protected_symbols_accessed == ()


def test_dependency_verifier_uses_no_discovery_or_cache_find(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_discovery(*args: object, **kwargs: object) -> None:
        raise AssertionError("discovery and cache find are forbidden")

    monkeypatch.setattr(Path, "glob", reject_discovery)
    monkeypatch.setattr(Path, "rglob", reject_discovery)
    monkeypatch.setattr(Path, "iterdir", reject_discovery)
    monkeypatch.setattr(ImmutableParquetCache, "find", reject_discovery)

    verified = verify_phase3_dependencies(REPOSITORY_ROOT)

    assert verified.provider_calls == 0
    assert tuple(item.symbol for item in verified.datasets) == PHASE3_SYMBOLS


def test_every_symbol_has_exact_declared_and_actual_partitions() -> None:
    split = build_split_manifest(verify_phase3_dependencies(REPOSITORY_ROOT))

    assert len(split.partitions) == 8
    for partition in split.partitions:
        assert partition.train.declared_start.isoformat() == "2014-01-02"
        assert partition.train.declared_end.isoformat() == "2018-12-31"
        assert partition.train.actual_start.isoformat() == "2014-01-02"
        assert partition.train.actual_end.isoformat() == "2018-12-31"
        assert partition.train.row_count == 1258
        assert partition.train.sessions_sha256 == TRAIN_SESSION_SHA256
        assert partition.validation.declared_start.isoformat() == "2019-01-01"
        assert partition.validation.declared_end.isoformat() == "2022-12-30"
        assert partition.validation.actual_start.isoformat() == "2019-01-02"
        assert partition.validation.actual_end.isoformat() == "2022-12-30"
        assert partition.validation.row_count == 1008
        assert partition.validation.sessions_sha256 == VALIDATION_SESSION_SHA256
        assert set(partition.train.sessions).isdisjoint(
            partition.validation.sessions
        )


def test_verified_datasets_retain_exact_ordered_sessions_and_byte_identities() -> None:
    verified = verify_phase3_dependencies(REPOSITORY_ROOT)

    assert len(verified.datasets) == 8
    for expected, actual in zip(PHASE3_DATASETS, verified.datasets, strict=True):
        assert actual.symbol == expected.symbol
        assert actual.phase3_dataset_sha256 == expected.sha256
        assert actual.metadata_artifact.path == f"{expected.path}/metadata.json"
        assert actual.metadata_artifact.content_sha256 == expected.sha256
        assert actual.bars_artifact.path == f"{expected.path}/bars.parquet"
        assert actual.bars_artifact.content_sha256 == expected.bars_sha256
        assert len(actual.sessions) == 2266
        assert actual.sessions[0].isoformat() == "2014-01-02"
        assert actual.sessions[-1].isoformat() == "2022-12-30"
        assert actual.sessions_sha256 == ALL_SESSION_SHA256


def test_configuration_separates_historical_trials_from_new_budget() -> None:
    config = build_campaign_configuration(split_identity())

    assert config.maximum_new_strategy_families == 10
    assert config.maximum_candidate_trials_per_family == 500
    assert config.maximum_aggregate_new_candidate_trials == 3000
    assert config.historical_phase2_trial_count == 136
    assert config.phase4_new_trials_consumed == 0
    assert config.phase4_new_trials_remaining == 3000
    assert config.phase4_historical_trials_consume_budget is False
    assert config.phase3_universe_digest == PHASE3_UNIVERSE_SHA256
    assert config.split_manifest == split_identity()
    assert config.signal_series == "QFQ"
    assert config.execution_series == "QFQ_NORMALIZED"
    assert config.decision_grade is False
    assert config.provider_calls == 0
    assert config.external_strategy_research_performed is False
    assert config.strategy_search_executed is False
    assert config.final_holdout_accessed is False
    assert config.protected_symbols_accessed == ()
    assert config.live_trading_capability is False


@pytest.mark.parametrize(
    "invalid",
    [
        {"maximum_aggregate_new_candidate_trials": 3136},
        {
            "phase4_new_trials_consumed": 1,
            "phase4_new_trials_remaining": 2999,
        },
    ],
)
def test_configuration_rejects_combined_or_preconsumed_budget(
    invalid: dict[str, object],
) -> None:
    payload = build_campaign_configuration(split_identity()).model_dump()
    payload.update(invalid)

    with pytest.raises(ValidationError):
        Phase4CampaignConfiguration.model_validate(payload)


def test_configuration_requires_written_split_identity() -> None:
    invalid = split_identity().model_copy(
        update={"kind": "phase3_universe_manifest"}
    )

    with pytest.raises(Phase3DependencyError, match="split"):
        build_campaign_configuration(invalid)


@pytest.mark.parametrize(
    "mutation",
    [
        "selected_order",
        "missing_dependency",
        "extra_dependency",
        "qfq_flag",
        "protected_symbol",
    ],
)
def test_universe_dependency_mutations_fail_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    repository = _copy_frozen_inputs(tmp_path)
    payload = _read_json(repository, PHASE3_UNIVERSE_PATH)
    selected = payload["selected_symbols"]
    assert isinstance(selected, list)
    if mutation == "selected_order":
        selected[0], selected[1] = selected[1], selected[0]
    elif mutation == "missing_dependency":
        selected.pop()
    elif mutation == "extra_dependency":
        selected.append("DIA")
    elif mutation == "qfq_flag":
        payload["qfq_execution_methodology"] = "ALTERED"
    else:
        selected[0] = "HACK"
    _write_json(repository, PHASE3_UNIVERSE_PATH, payload)

    with pytest.raises(Phase3DependencyError):
        verify_phase3_dependencies(repository)


def test_universe_path_mismatch_fails_closed(tmp_path: Path) -> None:
    repository = _copy_frozen_inputs(tmp_path)
    expected = repository.joinpath(*PHASE3_UNIVERSE_PATH.split("/"))
    expected.rename(expected.with_name("renamed-manifest.json"))

    with pytest.raises(Phase3DependencyError):
        verify_phase3_dependencies(repository)


def test_dq_snapshot_mismatch_fails_closed(tmp_path: Path) -> None:
    repository = _copy_frozen_inputs(tmp_path)
    snapshot = repository.joinpath(*PHASE3_DQ_SNAPSHOT_PATH.split("/"))
    snapshot.write_bytes(b"{}")

    with pytest.raises(Phase3DependencyError):
        verify_phase3_dependencies(repository)


def test_missing_exact_dataset_dependency_fails_closed(tmp_path: Path) -> None:
    repository = _copy_frozen_inputs(tmp_path)
    missing = repository.joinpath(
        *PHASE3_DATASETS[0].path.split("/"), "metadata.json"
    )
    missing.unlink()

    with pytest.raises(Phase3DependencyError):
        verify_phase3_dependencies(repository)


@pytest.mark.parametrize(
    "mutation",
    ["content_hash", "wrong_boundary", "missing_session", "duplicate_session"],
)
def test_dataset_content_or_session_mutation_fails_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    repository = _copy_frozen_inputs(tmp_path)
    bars_path = repository.joinpath(
        *PHASE3_DATASETS[0].path.split("/"), "bars.parquet"
    )
    bars = pd.read_parquet(bars_path, engine="pyarrow")
    if mutation == "content_hash":
        bars.iloc[0, bars.columns.get_loc("close")] += 1.0
    elif mutation == "wrong_boundary":
        changed = list(bars.index)
        changed[0] = pd.Timestamp("2014-01-01", tz="UTC")
        bars.index = pd.DatetimeIndex(changed, name=bars.index.name)
    elif mutation == "missing_session":
        bars = bars.iloc[1:]
    else:
        changed = list(bars.index)
        changed[1] = changed[0]
        bars.index = pd.DatetimeIndex(changed, name=bars.index.name)
    bars.to_parquet(bars_path, engine="pyarrow")

    with pytest.raises(Phase3DependencyError):
        verify_phase3_dependencies(repository)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_boundary"])
def test_bypassed_session_evidence_is_revalidated_before_manifest(
    mutation: str,
) -> None:
    verified = verify_phase3_dependencies(REPOSITORY_ROOT)
    dataset = verified.datasets[0]
    sessions = list(dataset.sessions)
    if mutation == "missing":
        sessions.pop(0)
    elif mutation == "duplicate":
        sessions[1] = sessions[0]
    else:
        sessions[0] = date(2014, 1, 1)
    mutated = dataset.model_copy(
        update={
            "sessions": tuple(sessions),
            "sessions_sha256": canonical_sha256(
                tuple(session.isoformat() for session in sessions)
            ),
        }
    )
    bypassed = verified.model_copy(
        update={"datasets": (mutated, *verified.datasets[1:])}
    )

    with pytest.raises(Phase3DependencyError):
        build_split_manifest(bypassed)


def test_one_dataset_cannot_substitute_an_interior_frozen_session() -> None:
    verified = verify_phase3_dependencies(REPOSITORY_ROOT)
    mutated = _replace_interior_session(verified.datasets[0])
    bypassed = verified.model_copy(
        update={"datasets": (mutated, *verified.datasets[1:])}
    )

    with pytest.raises(Phase3DependencyError):
        build_split_manifest(bypassed)


def test_all_datasets_cannot_substitute_the_same_interior_frozen_session() -> None:
    verified = verify_phase3_dependencies(REPOSITORY_ROOT)
    bypassed = verified.model_copy(
        update={
            "datasets": tuple(
                _replace_interior_session(dataset)
                for dataset in verified.datasets
            )
        }
    )

    with pytest.raises(Phase3DependencyError):
        build_split_manifest(bypassed)


def test_bars_byte_identity_cannot_be_replaced_by_valid_foreign_envelope() -> None:
    verified = verify_phase3_dependencies(REPOSITORY_ROOT)
    dataset = verified.datasets[0]
    envelope = {
        "content_sha256": "b" * 64,
        "kind": "phase3_normalized_dataset",
        "path": dataset.bars_artifact.path,
    }
    foreign_artifact = ReadinessArtifactIdentity(
        **envelope,
        sha256=canonical_sha256(envelope),
    )
    mutated = dataset.model_copy(update={"bars_artifact": foreign_artifact})
    bypassed = verified.model_copy(
        update={"datasets": (mutated, *verified.datasets[1:])}
    )

    with pytest.raises(Phase3DependencyError):
        build_split_manifest(bypassed)
