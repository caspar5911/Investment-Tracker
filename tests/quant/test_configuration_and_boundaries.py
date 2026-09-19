from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_tracker.quant.configuration import (
    BacktestConfig,
    QuantConfig,
    UniverseConfig,
    ValidationConfig,
    load_default_config,
)
from investment_tracker.quant.constants import TRADING_MODE


def test_config_rejects_locked_symbol() -> None:
    with pytest.raises(ValidationError, match="locked replacement holdout symbol denied"):
        UniverseConfig(version="UNIVERSE-v1", symbols=("SPY", "HACK"))


def test_unknown_config_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="mystery"):
        BacktestConfig(
            version="QUANT-BACKTEST-v1",
            initial_capital=10_000,
            allocation=1.0,
            commission_bps=1.0,
            slippage_bps=2.0,
            allow_fractional=True,
            mystery=True,
        )


def test_configuration_cannot_override_simulation_mode() -> None:
    with pytest.raises(ValidationError, match="trading_mode"):
        QuantConfig(
            universe=UniverseConfig(version="UNIVERSE-v1", symbols=("SPY",)),
            backtest=BacktestConfig(
                version="QUANT-BACKTEST-v1",
                initial_capital=10_000,
                allocation=1.0,
                commission_bps=1.0,
                slippage_bps=2.0,
                allow_fractional=True,
            ),
            validation=ValidationConfig(
                version="QUANT-VALIDATION-v1",
                train_start="2010-01-01",
                train_end="2018-12-31",
                validation_start="2019-01-01",
                validation_end="2022-12-31",
                final_holdout_start="2023-01-01",
                final_holdout_end="2025-12-31",
                max_candidates_per_family=500,
                patience=50,
            ),
            trading_mode="LIVE",
        )


def test_default_config_is_versioned_and_uses_expected_etf_universe() -> None:
    config = load_default_config()
    assert config.universe.symbols == (
        "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV",
        "XLI", "XLP", "XLY", "XLU", "VNQ", "TLT", "IEF", "GLD",
    )
    assert config.validation.max_candidates_per_family == 500
    assert config.validation.patience == 50
    assert TRADING_MODE == "SIMULATE"


def test_quant_package_has_no_canonical_mutation_imports() -> None:
    package_root = Path("src/investment_tracker/quant")
    forbidden = {
        "investment_tracker.canonical_write",
        "investment_tracker.phase_state",
    }
    violations: list[tuple[str, str]] = []
    for path in package_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name in forbidden or any(name.startswith(f"{item}.") for item in forbidden):
                    violations.append((str(path), name))
    assert violations == []


def test_quant_source_contains_no_trade_or_account_context_imports() -> None:
    package_root = Path("src/investment_tracker/quant")
    forbidden_names = {"OpenTradeContext", "OpenSecTradeContext", "OpenFutureTradeContext"}
    found: list[tuple[str, str]] = []
    for path in package_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                found.append((str(path), node.id))
            if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                found.append((str(path), node.attr))
    assert found == []
