from __future__ import annotations

import ast
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from investment_tracker.quant.experiments import ExperimentRecord, ResearchCandidateManifest
from investment_tracker.quant.moomoo.strategybase_exporter import (
    ExportBlockedError,
    export_strategy,
)
from investment_tracker.quant.promotion import PromotionGate, ValidatedSnapshot


def snapshot(family: str = "trend") -> ValidatedSnapshot:
    parameters_by_family = {
        "trend": {"fast_window": 20, "slow_window": 50, "allocation": 0.5},
        "momentum": {"lookback": 63, "allocation": 0.5},
        "trend_momentum": {
            "fast_window": 20,
            "slow_window": 50,
            "momentum_lookback": 63,
            "allocation": 0.5,
        },
        "risk_managed_trend": {
            "trend_window": 200,
            "volatility_window": 20,
            "target_volatility": 0.1,
            "maximum_exposure": 1.0,
        },
    }
    manifest = ResearchCandidateManifest.create(
        candidate_id=f"candidate-{family}",
        strategy_family=family,
        strategy_code_hash="a" * 64,
        strategy_parameters=parameters_by_family[family],
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
    record = ExperimentRecord(
        experiment_id=f"experiment-{family}",
        status="RESEARCH_ONLY",
        candidate_manifest=manifest,
        symbols=("SPY",),
        train_period=(date(2010, 1, 1), date(2018, 12, 31)),
        validation_period=(date(2019, 1, 1), date(2022, 12, 31)),
        metrics={"cagr": 0.08},
        validation_metrics={"cagr": 0.06},
        score=65.0,
        accepted=True,
        reason="passed",
        stop_reason="EXHAUSTED",
        recorded_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )
    gate = PromotionGate(
        research_passed=True,
        validation_passed=True,
        walk_forward_passed=True,
        robustness_passed=True,
        benchmark_passed=True,
        tests_passed=True,
    )
    return ValidatedSnapshot.create(record, gate)


def test_export_requires_validated_snapshot_before_filesystem_access(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied"
    occupied.write_text("not a directory", encoding="utf-8")
    with pytest.raises(ExportBlockedError, match="VALIDATED_SNAPSHOT"):
        export_strategy(object(), occupied / "strategy.py")


def test_exported_trend_source_uses_documented_completed_bar_and_order_guards(tmp_path: Path) -> None:
    path = export_strategy(snapshot("trend"), tmp_path / "strategy.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(isinstance(node, ast.ClassDef) and node.name == "Strategy" for node in ast.walk(tree))
    assert "select=2" in source
    assert "request_orderid" in source
    assert "max_qty_to_buy_on_cash" in source
    assert "qty=abs(holding)" in source
    assert "OpenTradeContext" not in source
    assert "OpenQuoteContext" not in source
    assert "LIVE" not in source
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))


def test_momentum_export_uses_completed_current_and_lookback_bars(tmp_path: Path) -> None:
    source = export_strategy(snapshot("momentum"), tmp_path / "momentum.py").read_text(encoding="utf-8")
    assert "select=2" in source
    assert "select=65" in source


def test_combined_export_contains_trend_and_momentum_gates(tmp_path: Path) -> None:
    source = export_strategy(snapshot("trend_momentum"), tmp_path / "combined.py").read_text(encoding="utf-8")
    assert source.count("ma(") >= 2
    assert "select=65" in source


def test_unsupported_strategy_fails_closed_without_writing(tmp_path: Path) -> None:
    destination = tmp_path / "risk.py"
    with pytest.raises(ExportBlockedError, match="cannot be represented exactly"):
        export_strategy(snapshot("risk_managed_trend"), destination)
    assert not destination.exists()


def test_export_never_overwrites_existing_source(tmp_path: Path) -> None:
    destination = tmp_path / "strategy.py"
    export_strategy(snapshot(), destination)
    before = destination.read_bytes()
    with pytest.raises(FileExistsError):
        export_strategy(snapshot(), destination)
    assert destination.read_bytes() == before
