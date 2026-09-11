from __future__ import annotations

import json
from pathlib import Path

from investment_tracker.quant.workflow import run_fixture_pipeline


def test_offline_research_pipeline_never_accesses_holdout_or_canonical_state(tmp_path: Path) -> None:
    result = run_fixture_pipeline(tmp_path, fixture_universe=("SPY", "QQQ"))
    assert result.experiment_count > 0
    assert result.final_holdout_accessed is False
    assert result.snapshot.status == "VALIDATED_SNAPSHOT"
    assert len(result.snapshot.candidate_manifest.digest) == 64
    assert result.export_path.exists()
    assert (tmp_path / "results" / "leaderboard.csv").exists()
    assert (tmp_path / "results" / "latest_report.md").exists()
    assert list((tmp_path / "results").rglob("*.started.json")) == []


def test_fixture_experiments_are_explicitly_labeled_non_market_evidence(tmp_path: Path) -> None:
    run_fixture_pipeline(tmp_path, fixture_universe=("SPY",))
    experiment_path = next((tmp_path / "results" / "experiments").glob("*.json"))
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    assert "FIXTURE_ONLY" in payload["reason"]
    assert payload["status"] == "RESEARCH_ONLY"


def test_new_experiments_identify_corrected_search_policy(tmp_path: Path) -> None:
    run_fixture_pipeline(tmp_path, fixture_universe=("SPY",))
    experiment_path = next((tmp_path / "results" / "experiments").glob("*.json"))
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))

    assert payload["candidate_manifest"]["engine_version"] == (
        "QUANT-ENGINE-v1+SEARCH-POLICY-v2"
    )


def test_fixture_run_is_append_only(tmp_path: Path) -> None:
    run_fixture_pipeline(tmp_path, fixture_universe=("SPY",))
    first_count = len(list((tmp_path / "results" / "experiments").glob("*.json")))
    run_fixture_pipeline(tmp_path, fixture_universe=("SPY",))
    second_count = len(list((tmp_path / "results" / "experiments").glob("*.json")))
    assert second_count == first_count * 2


def test_experiment_persists_cash_friction_walk_forward_and_bootstrap_evidence(tmp_path: Path) -> None:
    run_fixture_pipeline(tmp_path, fixture_universe=("SPY",))
    payload = json.loads(next((tmp_path / "results" / "experiments").glob("*.json")).read_text(encoding="utf-8"))
    metrics = payload["validation_metrics"]

    assert metrics["cash_total_return"] == 0.0
    assert metrics["bootstrap_median_lower"] <= metrics["bootstrap_median_upper"]
    assert {key for key in metrics if key.startswith("friction_return_")} == {
        "friction_return_0bps",
        "friction_return_3bps",
        "friction_return_25bps",
        "friction_return_50bps",
    }
    assert {key for key in metrics if key.startswith("walk_forward_return_")} == {
        "walk_forward_return_1",
        "walk_forward_return_2",
        "walk_forward_return_3",
    }
