from __future__ import annotations

import inspect
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from investment_tracker.quant.phase4.gate3.inputs import load_frozen_authority_inputs
from investment_tracker.quant.phase4.gate3.models import Gate3AuthorityError
from investment_tracker.quant.phase4.gate3.seal import (
    GATE1_MANIFEST_IDENTITY,
    GATE2_MANIFEST_IDENTITY,
    load_and_verify_gate3_authority,
    preflight_gate3,
    seal_gate3_authorities,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_seal_requires_committed_source_revision() -> None:
    with pytest.raises(Gate3AuthorityError, match="SOURCE_REVISION_INVALID"):
        seal_gate3_authorities(REPOSITORY_ROOT, source_revision="not-a-commit")


def test_missing_authority_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(Gate3AuthorityError, match="AUTHORITY_MANIFEST_MISSING"):
        load_and_verify_gate3_authority(tmp_path, "0" * 64)


def test_gate2_identity_is_exact_and_not_discovered_as_latest() -> None:
    assert GATE2_MANIFEST_IDENTITY.content_sha256 == (
        "c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6"
    )
    source = inspect.getsource(load_and_verify_gate3_authority).lower()
    assert "mtime" not in source
    assert "glob(" not in source
    assert "rglob(" not in source


def test_preflight_requires_explicit_manifest_digest() -> None:
    signature = inspect.signature(preflight_gate3)
    assert signature.parameters["manifest_content_sha256"].default is inspect.Parameter.empty


def test_gate3_namespace_has_no_campaign_or_trading_surface() -> None:
    import investment_tracker.quant.phase4.gate3 as gate3

    forbidden = {
        "run_campaign", "execute_candidate", "rank_candidates", "select_survivor",
        "place_order", "unlock_trade", "open_trade_context",
    }
    assert forbidden.isdisjoint(set(dir(gate3)))


def test_frozen_loader_handles_timestamp_index_and_requests_no_open_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_columns: list[tuple[str, ...]] = []
    real_read_table = pq.read_table

    def observed_read_table(path: Path, *, columns: list[str]):
        requested_columns.append(tuple(columns))
        return real_read_table(path, columns=columns)

    monkeypatch.setattr(pq, "read_table", observed_read_table)
    frozen = load_frozen_authority_inputs(
        REPOSITORY_ROOT,
        gate1_identity=GATE1_MANIFEST_IDENTITY,
        gate2_identity=GATE2_MANIFEST_IDENTITY,
    )

    assert len(frozen.all_sessions) == 2266
    assert len(frozen.validation_sessions) == 1008
    assert tuple(frozen.close_by_symbol) == (
        "SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP"
    )
    assert requested_columns == [("timestamp", "close")] * 8
