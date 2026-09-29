"""Generation-4 Phase-7 prospective accounting-path governance tests.

The real prospective path must preserve the frozen Phase-6 convention:
QFQ bars for signal generation, unadjusted bars for execution/P&L, and
reconciled split/dividend events for both the strategy and SPY benchmark.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from investment_tracker.independent_audit.post_generation3.phase7_data import (
    Phase7QuoteClient,
    acquire_prospective_phase7_data,
)
from investment_tracker.quant.generation2.accounting import DividendEvent, SplitEvent
from investment_tracker.quant.phase7 import generation4_durability as dur


UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")


def _sessions() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(
        [
            "2026-09-23",
            "2026-09-24",
            "2026-09-25",
            "2026-09-28",
            "2026-09-29",
            "2026-09-30",
        ],
        tz="UTC",
    )


def _bars(offset: float = 0.0) -> pd.DataFrame:
    index = _sessions()
    values = [100.0 + offset + i for i in range(len(index))]
    return pd.DataFrame(
        {
            "open": values,
            "high": [x + 1.0 for x in values],
            "low": [x - 1.0 for x in values],
            "close": [x + 0.5 for x in values],
            "volume": [1000 + i for i in range(len(index))],
        },
        index=index,
    )


def _raw_provider_bars(symbol: str, adjustment: str) -> pd.DataFrame:
    frame = _bars(0.0 if adjustment == "QFQ" else 10.0).reset_index(drop=False)
    frame = frame.rename(columns={"index": "session"})
    frame["time_key"] = frame["session"].dt.strftime("%Y-%m-%d 00:00:00")
    frame["code"] = f"US.{symbol}"
    return frame.drop(columns=["session"])


def _request():
    return {
        "schema_version": "GENERATION4-PHASE7-DATA-REQUEST-v1",
        "symbols": list(UNIVERSE),
        "requested_start": "2025-11-26",
        "requested_end": "2026-09-30",
        "scored_start": "2026-09-28",
        "warmup_session_count": 210,
        "scored_session_count": 3,
    }


class _SnapshotClient:
    def __init__(self):
        self.calls = []

    def fetch_daily_bars(self, symbol, start, end):
        self.calls.append(("QFQ", symbol))
        return _raw_provider_bars(symbol, "QFQ")

    def fetch_unadjusted_daily_bars(self, symbol, start, end):
        self.calls.append(("NONE", symbol))
        return _raw_provider_bars(symbol, "NONE")

    def fetch_rehab(self, symbol):
        self.calls.append(("REHAB", symbol))
        return pd.DataFrame(
            columns=[
                "ex_div_date",
                "per_cash_div",
                "special_dividend",
                "per_share_div_ratio",
                "per_share_trans_ratio",
                "allotment_ratio",
                "stk_spo_ratio",
                "spin_off_ratio",
            ]
        )

    def fetch_dividends(self, symbol):
        self.calls.append(("DIVIDENDS", symbol))
        return {"dividend_list": []}

    def fetch_splits(self, symbol):
        self.calls.append(("SPLITS", symbol))
        return {"split_list": []}

    def close(self):
        self.calls.append(("CLOSE", None))


def test_snapshot_persists_qfq_unadjusted_and_corporate_action_sources(
    bound_evidence, tmp_path, monkeypatch
):
    # Keep this test focused on evidence shape; session-integrity coverage is
    # separately exercised by test_generation4_phase7_snapshot_integrity.py.
    expected_sessions = _sessions()
    monkeypatch.setattr(
        "investment_tracker.independent_audit.post_generation3.phase7_data._calendar_window",
        lambda **kwargs: (expected_sessions, 210, 3),
    )
    client = _SnapshotClient()
    manifest = acquire_prospective_phase7_data(
        evaluation_authorization=bound_evidence.authorization,
        request=_request(),
        output_dir=tmp_path / "out",
        retrieved_at_utc="2026-10-01T00:00:00Z",
        client_factory=lambda **kwargs: client,
    )
    root = tmp_path / "out" / "snapshots" / manifest["snapshot_id"]
    for symbol in UNIVERSE:
        assert (root / "bars" / "qfq" / f"{symbol}.csv").is_file()
        assert (root / "bars" / "unadjusted" / f"{symbol}.csv").is_file()
        assert (root / "corporate_actions" / "rehab" / f"{symbol}.csv").is_file()
        assert (root / "corporate_actions" / "dividends" / f"{symbol}.json").is_file()
        assert (root / "corporate_actions" / "splits" / f"{symbol}.json").is_file()
    assert manifest["signal_price_convention"] == "QFQ"
    assert manifest["execution_price_convention"] == "UNADJUSTED"
    assert manifest["corporate_actions_included"] is True


def test_quote_client_exposes_unadjusted_and_corporate_action_reads():
    class AuType:
        QFQ = "QFQ"
        NONE = "NONE"

    class KLType:
        K_DAY = "K_DAY"

    class Context:
        def request_history_kline(self, code, **kwargs):
            return 0, _raw_provider_bars(code.split(".")[-1], kwargs["autype"]), None

        def get_rehab(self, code):
            return 0, pd.DataFrame()

        def get_corporate_actions_dividends(self, code):
            return 0, {"dividend_list": []}

        def get_corporate_actions_stock_splits(self, code, next_key=None, num=50):
            return 0, {"split_list": [], "next_key": "-1"}

        def close(self):
            pass

    sdk = SimpleNamespace(
        AuType=AuType,
        KLType=KLType,
        RET_OK=0,
        __name__="fake",
        __version__="0",
    )
    client = Phase7QuoteClient(Context(), sdk=sdk, host="127.0.0.1", port=11111)
    assert not client.fetch_unadjusted_daily_bars("SPY", "2026-09-28", "2026-09-30").empty
    assert isinstance(client.fetch_rehab("SPY"), pd.DataFrame)
    assert client.fetch_dividends("SPY") == {"dividend_list": []}
    assert client.fetch_splits("SPY") == {"split_list": []}


def test_prospective_checkpoint_replays_unadjusted_bars_with_actions(monkeypatch):
    signal_bars = {symbol: _bars(0.0) for symbol in UNIVERSE}
    execution_bars = {symbol: _bars(25.0) for symbol in UNIVERSE}
    split = SplitEvent("QQQ", pd.Timestamp("2026-09-29", tz="UTC"), 2.0, "split-id")
    dividend = DividendEvent(
        "QQQ",
        pd.Timestamp("2026-09-29", tz="UTC"),
        pd.Timestamp("2026-09-30", tz="UTC"),
        0.5,
        "div-id",
    )
    seen = {
        "target_bars": None,
        "target_kwargs": None,
        "replay_bars": [],
        "splits": [],
        "dividends": [],
    }

    def fake_targets(bars, **kwargs):
        seen["target_bars"] = bars
        seen["target_kwargs"] = kwargs
        return ()

    monkeypatch.setattr(dur, "build_fixed_targets", fake_targets)

    class Replay:
        def __init__(self, bars):
            self.sessions = tuple(_sessions())
            self.close_equity = tuple(100000.0 + i for i in range(6))
            self.total_turnover = 0.0
            self.friction_bps = 0
            self.initial_cash = 100000.0
            self.states = ()
            self.fills = ()

    def fake_replay(bars, targets, **kwargs):
        seen["replay_bars"].append(bars)
        seen["splits"].append(tuple(kwargs.get("splits", ())))
        seen["dividends"].append(tuple(kwargs.get("dividends", ())))
        return Replay(bars)

    monkeypatch.setattr(dur, "replay_decision_targets", fake_replay)
    monkeypatch.setattr(dur, "exposure_invariant_passes", lambda replay: True)
    monkeypatch.setattr(
        dur,
        "_prospective_benchmark_total_return",
        lambda *args, **kwargs: {"status": "AVAILABLE", "value": 0.0, "reason": "OK"},
    )

    snapshot = dur.ProspectiveCheckpoint(
        bars=signal_bars,
        execution_bars=execution_bars,
        splits=(split,),
        dividends=(dividend,),
        scored_start=pd.Timestamp("2026-09-28", tz="UTC"),
        checkpoint_cutoff=3,
    )
    report = dur.prospective_checkpoint_report(snapshot)
    assert report["status"] == dur.PHASE7_PROSPECTIVE_EVIDENCE_PENDING
    assert seen["target_bars"] is signal_bars
    assert seen["target_kwargs"]["due_from"] == pd.Timestamp("2026-09-28", tz="UTC")
    assert seen["target_kwargs"]["due_until"] == pd.Timestamp("2026-09-30", tz="UTC")
    assert seen["target_kwargs"]["align_start"] == pd.Timestamp("2026-09-28", tz="UTC")
    assert seen["replay_bars"]
    assert all(value is execution_bars for value in seen["replay_bars"])
    assert all(value == (split,) for value in seen["splits"])
    assert all(value == (dividend,) for value in seen["dividends"])
