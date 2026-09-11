from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from investment_tracker.quant.cli import main, parser
from investment_tracker.quant.experiments import (
    ExperimentRecord,
    ExperimentStore,
    ResearchCandidateManifest,
)
from investment_tracker.quant.reports.generate_report import (
    render_report,
    write_leaderboard,
)


def experiment(experiment_id: str, score: float | None, sharpe: float | None) -> ExperimentRecord:
    manifest = ResearchCandidateManifest.create(
        candidate_id=f"candidate-{experiment_id}",
        strategy_family="trend",
        strategy_code_hash="a" * 64,
        strategy_parameters={"fast_window": 20, "slow_window": 50, "allocation": 1.0},
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
    return ExperimentRecord(
        experiment_id=experiment_id,
        status="RESEARCH_ONLY",
        candidate_manifest=manifest,
        symbols=("SPY",),
        train_period=(date(2010, 1, 1), date(2018, 12, 31)),
        validation_period=(date(2019, 1, 1), date(2022, 12, 31)),
        metrics={"cagr": 0.08, "max_drawdown": -0.12},
        validation_metrics={"cagr": 0.06, "sharpe": sharpe},
        score=score,
        accepted=score is not None and score >= 60,
        reason="evaluated",
        stop_reason="EXHAUSTED",
        recorded_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )


def test_missing_metrics_render_unknown() -> None:
    report = render_report([experiment("exp-1", None, None)])
    assert "Sharpe: UNKNOWN" in report
    assert "Score: UNKNOWN" in report
    assert "production-approved" not in report.lower()


def test_leaderboard_is_deterministic_and_unranked_rows_sort_last(tmp_path: Path) -> None:
    path = tmp_path / "leaderboard.csv"
    write_leaderboard(
        [experiment("low", 50.0, 0.5), experiment("unknown", None, None), experiment("high", 70.0, 1.2)],
        path,
    )
    rows = path.read_text(encoding="utf-8").splitlines()
    assert rows[1].startswith("high,")
    assert rows[2].startswith("low,")
    assert rows[3].startswith("unknown,")
    assert "UNKNOWN" in rows[3]


def test_cli_exposes_research_commands_and_no_live_switch() -> None:
    help_text = parser().format_help().lower()
    for command in ("download", "backtest", "optimize", "validate", "report", "export-moomoo"):
        assert command in help_text
    assert "--live" not in help_text
    with pytest.raises(SystemExit):
        parser().parse_args(["download", "--live"])


def test_report_command_reads_experiments_and_writes_derived_views(tmp_path: Path) -> None:
    experiments = tmp_path / "experiments"
    ExperimentStore(experiments).append(experiment("exp-1", 65.0, 0.9))
    leaderboard = tmp_path / "leaderboard.csv"
    report = tmp_path / "latest_report.md"
    exit_code = main([
        "report",
        "--experiments-dir", str(experiments),
        "--leaderboard", str(leaderboard),
        "--report", str(report),
    ])
    assert exit_code == 0
    assert leaderboard.exists()
    assert report.exists()
    assert "exp-1" in report.read_text(encoding="utf-8")


def test_validate_command_fails_closed_on_invalid_experiment(tmp_path: Path) -> None:
    experiments = tmp_path / "experiments"
    experiments.mkdir()
    (experiments / "broken.json").write_text("{}", encoding="utf-8")
    assert main(["validate", "--experiments-dir", str(experiments)]) == 2
