from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from investment_tracker.independent_audit.generation2 import research_provenance_export as rpe
from investment_tracker.quant.data.cache import content_hash


def _frame(offset: float) -> pd.DataFrame:
    index = pd.DatetimeIndex([pd.Timestamp("2014-01-02", tz="UTC")], name="timestamp")
    return pd.DataFrame(
        {
            "open": [100.0 + offset],
            "high": [101.0 + offset],
            "low": [99.0 + offset],
            "close": [100.5 + offset],
            "volume": [1000.0 + offset],
        },
        index=index,
    )


class _CleanReport:
    clean = True
    issues = ()


class _Validator:
    def __init__(self, name):
        assert name == "XNYS"

    def validate(self, frame, request):
        return _CleanReport()


class _Source:
    requests = []

    def __init__(self, *, host, port):
        assert host == "127.0.0.1"
        assert port == 11111

    def fetch_with_evidence(self, request):
        assert request.symbol in rpe.RESEARCH_SYMBOLS
        assert request.symbol not in rpe.FORBIDDEN_HOLDOUT_SYMBOLS
        assert request.start.isoformat() == "2014-01-01"
        assert request.end.isoformat() == "2022-12-31"
        assert request.adjustment == "QFQ"
        self.requests.append(request)
        offset = float(rpe.RESEARCH_SYMBOLS.index(request.symbol))
        normalized = _frame(offset)
        raw = normalized.reset_index().rename(columns={"timestamp": "time_key"})
        raw.insert(0, "code", f"US.{request.symbol}")
        return SimpleNamespace(
            status="SUCCESS",
            normalized=normalized,
            error=None,
            pages=(SimpleNamespace(page_number=1, frame=raw),),
            retrieved_at=datetime(2026, 9, 22, 1, 0, tzinfo=timezone.utc),
        )


def test_export_reconciles_provider_origin_snapshot(monkeypatch, tmp_path: Path):
    _Source.requests = []
    primary = {
        symbol: content_hash(_frame(float(rpe.RESEARCH_SYMBOLS.index(symbol))))
        for symbol in rpe.RESEARCH_SYMBOLS
    }
    monkeypatch.setattr(rpe, "MoomooHistoricalDataSource", _Source)
    monkeypatch.setattr(rpe, "BarDataValidator", _Validator)
    monkeypatch.setattr(
        rpe,
        "verify_reproduction_report",
        lambda path: {
            "report_sha256": "a" * 64,
            "snapshot_symbols": primary,
        },
    )

    result = rpe.export_and_reconcile(
        output_root=tmp_path / "export",
        reproduction_report_path=tmp_path / "reproduction.json",
    )
    assert result["status"] == "MATCHED"
    assert result["independent_source_established"] is True
    assert result["decision_critical"] is False
    assert all(result["normalized_hashes_match"].values())
    assert [request.symbol for request in _Source.requests] == list(rpe.RESEARCH_SYMBOLS)
    assert not ({request.symbol for request in _Source.requests} & rpe.FORBIDDEN_HOLDOUT_SYMBOLS)
    assert (tmp_path / "export" / "provider-origin-snapshot.json").is_file()
    assert (tmp_path / "export" / "primary-snapshot.json").is_file()
    assert (tmp_path / "export" / "reconciliation.json").is_file()
    assert (tmp_path / "export" / "result.json").is_file()


def test_export_refuses_nonempty_output_before_provider_access(monkeypatch, tmp_path: Path):
    root = tmp_path / "export"
    root.mkdir()
    (root / "existing").write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        rpe,
        "MoomooHistoricalDataSource",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("provider must not open")),
    )
    with pytest.raises(FileExistsError, match="GEN2_PROVENANCE_OUTPUT_NOT_EMPTY"):
        rpe.export_and_reconcile(
            output_root=root,
            reproduction_report_path=tmp_path / "reproduction.json",
        )


def test_forbidden_holdout_is_disjoint_from_research_universe():
    assert not (set(rpe.RESEARCH_SYMBOLS) & rpe.FORBIDDEN_HOLDOUT_SYMBOLS)


def test_provider_origin_export_is_strictly_2014_through_2022():
    assert rpe.CAMPAIGN_START.isoformat() == "2014-01-01"
    assert rpe.CAMPAIGN_END.isoformat() == "2022-12-31"
