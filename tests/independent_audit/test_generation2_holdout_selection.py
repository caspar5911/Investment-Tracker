from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from investment_tracker.independent_audit.generation2 import holdout_selection as hs


def _frame() -> pd.DataFrame:
    rows = []
    for symbol, year in [
        ("AAA", 2015), ("BBB", 2016), ("CCC", 2017), ("DDD", 2018),
        ("EEE", 2019), ("FFF", 2020), ("GGG", 2021), ("HHH", 2014),
    ]:
        rows.append({
            "code": f"US.{symbol}",
            "name": f"{symbol} Core ETF",
            "listing_date": f"{year}-01-02",
            "delisting": False,
            "stock_type": "ETF",
        })
    rows.extend([
        {"code": "US.SPY", "name": "Research ETF", "listing_date": "1993-01-29", "delisting": False, "stock_type": "ETF"},
        {"code": "US.FQAL", "name": "Prior Holdout ETF", "listing_date": "2016-09-15", "delisting": False, "stock_type": "ETF"},
        {"code": "US.LATE", "name": "Late ETF", "listing_date": "2022-03-04", "delisting": False, "stock_type": "ETF"},
        {"code": "US.EPOCH", "name": "Epoch ETF", "listing_date": "1970-01-01", "delisting": False, "stock_type": "ETF"},
        {"code": "US.LEV", "name": "Example 3X Daily Bull ETF", "listing_date": "2010-01-01", "delisting": False, "stock_type": "ETF"},
    ])
    return pd.DataFrame(rows)


def test_frozen_seed_and_cutoff():
    assert hs.FROZEN_SEED_SHA256 == "bc41de35fd0b4889a98d06b614e353696a29c539d9398f1d19b2bb7df0094094"
    assert hs.FROZEN_LISTING_CUTOFF.isoformat() == "2022-03-03"
    assert hs.FROZEN_SELECTION_COUNT == 5


def test_selector_applies_registry_and_both_contamination_sources():
    selected, counts = hs.select_from_static_frame(
        _frame(),
        permanent_exclusions=frozenset({"SPY", "FQAL"}),
        provider_history_symbols={"CCC"},
        retained_log_history_symbols={"DDD"},
    )
    symbols = {item.symbol for item in selected}
    assert len(selected) == 5
    assert not symbols & {"SPY", "FQAL", "CCC", "DDD", "LATE", "EPOCH", "LEV"}
    assert counts["permanent_exclusion_registry"] == 2
    assert counts["provider_history_ledger"] == 1
    assert counts["retained_log_history_context"] == 1
    assert counts["listing_date_missing_or_too_late"] == 2
    assert counts["invalid_or_blocked_name"] == 1


def test_selection_order_is_deterministic():
    frame = _frame().iloc[:8].copy()
    kwargs = dict(
        permanent_exclusions=frozenset(),
        provider_history_symbols=set(),
        retained_log_history_symbols=set(),
    )
    one, _ = hs.select_from_static_frame(frame, **kwargs)
    two, _ = hs.select_from_static_frame(frame.sample(frac=1, random_state=7), **kwargs)
    assert [x.symbol for x in one] == [x.symbol for x in two]
    expected = sorted(
        [str(v)[3:] for v in frame["code"]],
        key=lambda s: (hs._rank_key(s), s),
    )[:5]
    assert [x.symbol for x in one] == expected


def test_provider_ledger_extracts_symbols_without_market_data():
    class FakeSdk:
        RET_OK = 0

    class Context:
        def get_history_kl_quota(self, get_detail=False):
            assert get_detail is True
            return 0, (
                2,
                298,
                [
                    {"code": "US.AAA", "name": "A", "request_time": "2026-09-22 01:00:00"},
                    {"code": "US.BBB", "name": "B", "request_time": "2026-09-22 02:00:00"},
                ],
            )

    symbols, payload = hs._provider_history_ledger(Context(), FakeSdk)
    assert symbols == {"AAA", "BBB"}
    parsed = json.loads(payload)
    assert parsed["used_quota"] == 2
    assert parsed["provider_limitations"] == ["CURRENT_PROVIDER_QUOTA_HISTORY_WINDOW_ONLY"]


def test_static_snapshot_rejects_duplicate_codes():
    frame = _frame().iloc[:2].copy()
    frame.loc[1, "code"] = frame.loc[0, "code"]
    with pytest.raises(ValueError, match="GEN2_HOLDOUT_STATIC_DUPLICATE_CODE"):
        hs._static_snapshot(frame)


def test_output_collision_fails_before_provider_access(monkeypatch, tmp_path: Path):
    out = tmp_path / "selection.json"
    out.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(hs, "_verify_frozen_inputs", lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not verify after collision")))
    with pytest.raises(FileExistsError, match="GEN2_HOLDOUT_SELECTION_OUTPUT_EXISTS"):
        hs.acquire_and_select(
            log_paths=(tmp_path,),
            output_path=out,
            static_snapshot_path=tmp_path / "static.json",
            provider_ledger_output_path=tmp_path / "ledger.json",
        )


def test_contract_loader_rejects_seed_tamper(tmp_path: Path):
    source = Path("data/governance/generation2-holdout-selection-contract.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["ranking"]["seed_sha256"] = "0" * 64
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="GEN2_HOLDOUT_SELECTION_SEED_MISMATCH"):
        hs._load_contract(path)


def test_full_selector_uses_only_static_and_quota_interfaces(monkeypatch, tmp_path: Path):
    class FakeContext:
        def __init__(self):
            self.calls = []
            self.closed = False
        def get_stock_basicinfo(self, market, stock_type):
            self.calls.append("static")
            return 0, _frame()
        def get_history_kl_quota(self, get_detail=False):
            self.calls.append("quota")
            return 0, (1, 299, [{"code":"US.CCC","name":"C","request_time":"2026-09-22 01:00:00"}])
        def close(self):
            self.closed = True

    class Market:
        US = object()
    class SecurityType:
        ETF = object()
    class FakeSdk:
        RET_OK = 0
        def __init__(self, ctx): self.ctx = ctx
        def OpenQuoteContext(self, host, port): return self.ctx

    FakeSdk.Market = Market
    FakeSdk.SecurityType = SecurityType

    ctx = FakeContext()
    monkeypatch.setattr(hs.legacy_helpers, "_load_sdk", lambda: (FakeSdk(ctx), "fake"))
    monkeypatch.setattr(
        hs,
        "_verify_frozen_inputs",
        lambda **kwargs: (
            {"evaluation_window":{"start":"2023-01-01","end":"2025-12-31"},"required_warmup_sessions":210},
            "a"*64,
            frozenset({"SPY","FQAL"}),
        ),
    )

    log = tmp_path / "OpenD.log"
    log.write_text("Qot_RequestHistoryKL protoID=3103\nsecurity=DDD\n", encoding="utf-8")
    out = tmp_path / "selection.json"
    hs.acquire_and_select(
        log_paths=(log,),
        output_path=out,
        static_snapshot_path=tmp_path / "static.json",
        provider_ledger_output_path=tmp_path / "ledger.json",
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "GENERATION2_HOLDOUT_SELECTION_FROZEN"
    assert len(payload["selected"]) == 5
    assert ctx.calls == ["static", "quota"]
    assert ctx.closed is True
    assert payload["safety"]["historical_market_data_api_called"] is False
    assert payload["safety"]["phase6_authorized"] is False
