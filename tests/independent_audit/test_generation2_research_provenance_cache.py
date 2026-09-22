from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from investment_tracker.independent_audit.generation2 import research_provenance_cache as rpc
from investment_tracker.quant.data.cache import content_hash
from investment_tracker.quant.universe.models import ArtifactIdentity


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


class _RawIdentity:
    def __init__(self, symbol: str, digest: str):
        self.kind = "raw_provider_evidence"
        self.sha256 = digest
        self.path = f"phase3/raw/moomoo/sha256/{digest}/evidence.json"
        self.symbol = symbol

    def model_dump(self, mode=None):
        return {"kind": self.kind, "sha256": self.sha256, "path": self.path}


def test_cache_provenance_matches_sealed_snapshot_without_provider_calls(monkeypatch, tmp_path: Path):
    cache_root = tmp_path / "cache"
    normalized_root = cache_root / "phase3" / "normalized" / "sha256"
    normalized_root.mkdir(parents=True)

    frames = {
        symbol: _frame(float(rpc.RESEARCH_SYMBOLS.index(symbol)))
        for symbol in rpc.RESEARCH_SYMBOLS
    }
    primary = {symbol: content_hash(frame) for symbol, frame in frames.items()}
    raw_paths = {}
    raw_ids = {}
    for symbol in rpc.RESEARCH_SYMBOLS:
        raw_dir = cache_root / "raw-fixture" / symbol
        raw_dir.mkdir(parents=True)
        raw_path = raw_dir / "evidence.json"
        payload = ("raw-" + symbol).encode("utf-8")
        raw_path.write_bytes(payload)
        digest = rpc.sha256(payload).hexdigest()
        raw_paths[symbol] = raw_path
        raw_ids[symbol] = _RawIdentity(symbol, digest)

    class FakeStore:
        def __init__(self, evidence_root, results_root):
            assert Path(evidence_root) == cache_root
        def read_json(self, identity):
            symbol = identity.symbol
            return {
                "status": "SUCCESS",
                "request": {
                    "symbol": symbol,
                    "start": "2014-01-01",
                    "end": "2022-12-31",
                    "adjustment": "QFQ",
                },
            }
        def resolve(self, identity):
            return raw_paths[identity.symbol]

    def fake_load(*, store, normalized_root, symbol):
        metadata = SimpleNamespace(
            raw_evidence=raw_ids[symbol],
            normalization_version="MOOMOO-US-DAILY-EASTERN-DATE-UTC-v1",
            retrieved_at=datetime(2022, 12, 31, tzinfo=timezone.utc),
            sdk_version="test",
            opend_version="test",
        )
        frame = frames[symbol]
        return frame, metadata, content_hash(frame)

    monkeypatch.setattr(rpc, "Phase3ArtifactStore", FakeStore)
    monkeypatch.setattr(rpc, "_load_dataset_for_symbol", fake_load)
    monkeypatch.setattr(rpc, "_dataset_identity_sha", lambda root, symbol: ("a" * 63) + str(rpc.RESEARCH_SYMBOLS.index(symbol) % 10))
    monkeypatch.setattr(rpc, "_expected_session_authority_sha256", lambda: "e" * 64)
    monkeypatch.setattr(
        rpc,
        "verify_reproduction_report",
        lambda path: {"report_sha256": "f" * 64, "snapshot_symbols": primary},
    )

    result = rpc.build_from_phase3_cache(
        cache_root=cache_root,
        output_root=tmp_path / "out",
        reproduction_report_path=tmp_path / "reproduction.json",
    )
    assert result["status"] == "MATCHED"
    assert result["independent_source_established"] is True
    assert result["decision_critical"] is False
    assert result["provider_history_requested"] is False
    assert result["holdout_symbols_accessed"] == []
    assert result["research_symbols"] == list(rpc.RESEARCH_SYMBOLS)


def test_cache_provenance_research_symbols_exclude_frozen_holdout():
    frozen = {"BNO", "GBIL", "CWS", "ESG", "VICI"}
    assert not (set(rpc.RESEARCH_SYMBOLS) & frozen)
