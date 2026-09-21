from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from investment_tracker.independent_audit.phase6 import replacement


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"code": "US.AAA", "name": "Alpha Core ETF", "listing_date": "2018-01-02", "delisting": False, "stock_type": "ETF"},
            {"code": "US.BBB", "name": "Beta Value ETF", "listing_date": "2019-02-03", "delisting": False, "stock_type": "ETF"},
            {"code": "US.CCC", "name": "Gamma Income ETF", "listing_date": "2020-03-04", "delisting": False, "stock_type": "ETF"},
            {"code": "US.DDD", "name": "Delta Quality ETF", "listing_date": "2021-04-05", "delisting": False, "stock_type": "ETF"},
            {"code": "US.EEE", "name": "Epsilon Allocation ETF", "listing_date": "2017-05-06", "delisting": False, "stock_type": "ETF"},
            {"code": "US.FFF", "name": "Zeta Diversified ETF", "listing_date": "2016-06-07", "delisting": False, "stock_type": "ETF"},
            {"code": "US.GGG", "name": "Eta Global ETF", "listing_date": "2015-07-08", "delisting": False, "stock_type": "ETF"},
            {"code": "US.HHH", "name": "Theta Balanced ETF", "listing_date": "2014-08-09", "delisting": False, "stock_type": "ETF"},
            {"code": "US.LATE", "name": "Late ETF", "listing_date": "2022-06-03", "delisting": False, "stock_type": "ETF"},
            {"code": "US.LEV", "name": "Example 3X Daily Bull ETF", "listing_date": "2012-01-01", "delisting": False, "stock_type": "ETF"},
            {"code": "US.SPY", "name": "Research ETF", "listing_date": "1993-01-29", "delisting": False, "stock_type": "ETF"},
            {"code": "US.GONE", "name": "Gone ETF", "listing_date": "2010-01-01", "delisting": True, "stock_type": "ETF"},
        ]
    )


def test_selection_seed_is_frozen_and_preregistered():
    expected = replacement.sha256(
        replacement.SELECTION_SEED_MATERIAL.encode("ascii")
    ).hexdigest()
    assert replacement.SELECTION_SEED == expected
    assert replacement.PREREGISTRATION_COMMIT_SHA == "0ddff58e36a2637ff5d12d044f1fee12e64e9a00"


def test_selector_is_deterministic_and_fails_over_only_for_predeclared_exclusions():
    frame = _frame()
    candidates, excluded = replacement.select_from_static_frame(
        frame,
        contaminated_symbols={"CCC"},
    )
    assert len(candidates) == 5
    assert "CCC" not in {item.symbol for item in candidates}
    assert "SPY" not in {item.symbol for item in candidates}
    assert "LATE" not in {item.symbol for item in candidates}
    assert "LEV" not in {item.symbol for item in candidates}
    assert excluded["historical_kline_context"] == 1
    assert excluded["research_or_rejected_symbol"] == 1
    assert excluded["listing_date_missing_or_too_late"] == 1
    assert excluded["invalid_or_blocked_name"] == 1
    expected = sorted(
        [symbol for symbol in ("AAA", "BBB", "DDD", "EEE", "FFF", "GGG", "HHH")],
        key=lambda symbol: (replacement._rank_key(symbol), symbol),
    )[:5]
    assert [item.symbol for item in candidates] == expected


def test_log_parser_marks_only_symbols_near_explicit_history_protocol(tmp_path: Path):
    log = tmp_path / "OpenD.log"
    log.write_text(
        "ordinary static info US.AAA\n"
        "something else\n"
        "Qot_RequestHistoryKL protoID=3103\n"
        "security US.BBB\n"
        "response\n"
        + "\n".join("padding" for _ in range(20))
        + "\nordinary metadata US.CCC\n",
        encoding="utf-8",
    )
    contaminated, manifest, contexts = replacement._history_context_symbols((log,))
    assert "BBB" in contaminated
    assert "CCC" not in contaminated
    assert len(manifest) == 1
    assert contexts
    assert all("raw_line" not in item for item in contexts)


def test_acquire_and_select_uses_static_metadata_only(monkeypatch, tmp_path: Path):
    class FakeContext:
        def __init__(self):
            self.closed = False

        def get_stock_basicinfo(self, market, stock_type):
            return 0, _frame()

        def close(self):
            self.closed = True

    class FakeMarket:
        US = object()

    class FakeSecurityType:
        ETF = object()

    class FakeSdk:
        RET_OK = 0
        Market = FakeMarket
        SecurityType = FakeSecurityType

        def __init__(self, context):
            self._context = context

        def OpenQuoteContext(self, host, port):
            return self._context

    context = FakeContext()
    sdk = FakeSdk(context)
    monkeypatch.setattr(replacement, "_load_sdk", lambda: (sdk, "fake-moomoo"))

    log = tmp_path / "OpenD.log"
    log.write_text(
        "Qot_RequestHistoryKL\nsecurity US.CCC\n",
        encoding="utf-8",
    )
    output = tmp_path / "selection.json"
    snapshot = tmp_path / "static.json"

    replacement.acquire_and_select(
        log_paths=(log,),
        output_path=output,
        static_snapshot_path=snapshot,
    )

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "PHASE6_REPLACEMENT_SELECTION_FROZEN"
    assert len(result["selected"]) == 5
    assert result["safety"]["historical_market_data_api_called"] is False
    assert result["safety"]["strategy_evaluation_executed"] is False
    assert result["preregistration_commit_sha"] == replacement.PREREGISTRATION_COMMIT_SHA
    assert context.closed is True
    assert snapshot.is_file()


def test_insufficient_pool_abstains_without_rule_relaxation():
    frame = pd.DataFrame(
        [
            {"code": "US.AAA", "name": "Alpha ETF", "listing_date": "2010-01-01", "delisting": False},
            {"code": "US.BBB", "name": "Beta ETF", "listing_date": "2010-01-01", "delisting": False},
        ]
    )
    selected, excluded = replacement.select_from_static_frame(
        frame,
        contaminated_symbols=set(),
    )
    assert len(selected) == 2
    assert sum(excluded.values()) == 0
