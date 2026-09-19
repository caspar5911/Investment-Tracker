from pathlib import Path

import pytest

from investment_tracker.quant.phase5 import opend
from investment_tracker.quant.phase5.methodology import (
    PROTECTED_SYMBOLS,
    SYMBOLS,
    assert_requested_symbols,
    frozen_binding,
)


def test_exact_frozen_identity_and_canonical_universe():
    binding = frozen_binding()
    assert binding.budget_position == 150
    assert binding.parameters_dict == {
        "lookback_sessions": 126,
        "rebalance_sessions": 21,
        "skip_sessions": 21,
        "top_k": 3,
    }
    assert SYMBOLS == ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
    assert not (set(SYMBOLS) & PROTECTED_SYMBOLS)


def test_protected_symbol_is_rejected_before_sdk_or_connection(monkeypatch, tmp_path):
    called = False

    def forbidden():
        nonlocal called
        called = True
        raise AssertionError("SDK must not be loaded")

    monkeypatch.setattr(opend, "_load_sdk", forbidden)
    with pytest.raises(ValueError, match="PROTECTED_SYMBOL"):
        opend.export_opend_bundle(tmp_path, symbols=(*SYMBOLS[:-1], "HACK"))
    assert called is False


def test_opend_module_has_no_trading_surface_and_no_qfq():
    source = Path(opend.__file__).read_text(encoding="utf-8")
    assert "AuType.NONE" in source
    assert "AuType.QFQ" not in source
    assert "OpenSecTradeContext" not in source
    assert "place_order" not in source
    assert "get_corporate_actions_dividends" in source
    assert "get_corporate_actions_stock_splits" in source
