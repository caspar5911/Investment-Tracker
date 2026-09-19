from pathlib import Path

import pandas as pd
import pytest

from investment_tracker.quant.phase5 import dataset, opend
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


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        ("2026-09-01", "2026-09-01"),
        ("2026/09/01", "2026-09-01"),
        ("Sep 1, 2026", "2026-09-01"),
        ("September 1, 2026", "2026-09-01"),
    ),
)
def test_opend_date_normalization_uses_the_full_provider_date(raw, expected):
    parsed = dataset._timestamp(raw, field="test_date")
    assert parsed == pd.Timestamp(expected, tz="UTC")


def test_zero_match_dividend_detail_becomes_a_dq_coverage_gap():
    missing_ex_date = pd.Timestamp("2019-12-23", tz="UTC")
    supported_ex_date = pd.Timestamp("2020-03-23", tz="UTC")
    rehab = (
        dataset.RehabEvent("QQQ", missing_ex_date, 1.0, 0.0, 0.4577, None),
        dataset.RehabEvent("QQQ", supported_ex_date, 1.0, 0.0, 0.3632, None),
    )
    response = {
        "dividend_list": [
            {
                "ex_date": "2020-03-23",
                "dividend_payable_date": "2020-04-30",
                "statement": "USD 0.3632 per share",
            }
        ]
    }

    events, gaps = dataset._dividends("QQQ", rehab, response)

    assert tuple(event.ex_date for event in events) == (supported_ex_date,)
    assert gaps == (
        dataset.DividendCoverageGap(
            symbol="QQQ",
            ex_date=missing_ex_date,
            reason="DIVIDEND_DETAIL_MISSING",
        ),
    )


def test_accounting_boundary_is_first_common_session_strictly_after_latest_gap():
    gaps = (
        dataset.DividendCoverageGap(
            symbol="IEF",
            ex_date=pd.Timestamp("2019-12-19", tz="UTC"),
            reason="DIVIDEND_DETAIL_MISSING",
        ),
        dataset.DividendCoverageGap(
            symbol="QQQ",
            ex_date=pd.Timestamp("2019-12-23", tz="UTC"),
            reason="DIVIDEND_DETAIL_MISSING",
        ),
    )
    common = pd.DatetimeIndex(
        [
            pd.Timestamp("2019-12-23", tz="UTC"),
            pd.Timestamp("2019-12-24", tz="UTC"),
            pd.Timestamp("2019-12-26", tz="UTC"),
        ]
    )

    assert dataset._first_defensible_accounting_session(common, gaps) == common[1]


def test_duplicate_dividend_detail_remains_ambiguous():
    ex_date = pd.Timestamp("2020-03-23", tz="UTC")
    rehab = (
        dataset.RehabEvent("QQQ", ex_date, 1.0, 0.0, 0.3632, None),
    )
    record = {
        "ex_date": "2020-03-23",
        "dividend_payable_date": "2020-04-30",
        "statement": "USD 0.3632 per share",
    }

    with pytest.raises(ValueError, match="PHASE5_DIVIDEND_PAYDATE_AMBIGUOUS:QQQ:2020-03-23"):
        dataset._dividends("QQQ", rehab, {"dividend_list": [record, dict(record)]})
