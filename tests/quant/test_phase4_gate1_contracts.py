from __future__ import annotations

import ast
from pathlib import Path

from investment_tracker.quant.phase4.preregistration.access import (
    Gate1ReadCapability,
)


PACKAGE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "investment_tracker"
    / "quant"
    / "phase4"
    / "preregistration"
)

BANNED_IMPORT_FRAGMENTS = (
    "investment_tracker.quant.backtest",
    "investment_tracker.quant.data",
    "investment_tracker.quant.experiments",
    "investment_tracker.quant.moomoo",
    "investment_tracker.quant.optimizer",
    "investment_tracker.quant.promotion",
    "investment_tracker.quant.reports",
    "investment_tracker.quant.strategies",
    "investment_tracker.quant.universe",
    "investment_tracker.quant.validation",
    "investment_tracker.quant.workflow",
)

BANNED_SOURCE_TOKENS = (
    "OpenQuoteContext",
    "OpenSecTradeContext",
    "OpenFutureTradeContext",
    "OpenCryptoTradeContext",
    "place_order",
    "modify_order",
    "cancel_order",
    "unlock_trade",
)


def test_gate1_package_has_no_banned_import_or_trading_token() -> None:
    for path in sorted(PACKAGE_ROOT.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(
            fragment in imported
            for fragment in BANNED_IMPORT_FRAGMENTS
            for imported in imports
        ), path
        assert not any(token in source for token in BANNED_SOURCE_TOKENS), path


def test_read_capability_exposes_no_generic_discovery_or_network_method() -> None:
    public = {
        name
        for name in dir(Gate1ReadCapability)
        if not name.startswith("_")
    }
    assert public == {
        "evidence",
        "read_admitted_artifact",
        "read_admitted_git_object",
    }
