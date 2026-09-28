"""Generation-4 Phase-7 prospective data-boundary tests (Task 6, RED first).

These tests prove, using fakes/spies (never a real provider):

- no provider object is created before the evaluation authorization is
  validated;
- the exact research universe is required (order + content);
- order mismatch is rejected;
- each Generation-4 final-holdout symbol is rejected before provider creation;
- any unknown symbol is rejected;
- a warmup request that exceeds the maximum warmup is rejected;
- a scored request that exceeds the checkpoint cutoff is rejected;
- a trade context is never created and the manifest records it;
- the read-only quote client exposes no order/trade methods;
- snapshots are append-only and an existing snapshot is never overwritten;
- the manifest records provider/date/symbol/file hashes and
  ``trading_context_created=false``.
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd
import pytest

from investment_tracker.independent_audit.post_generation3.phase7_data import (
    GEN4_PHASE7_DATA_AUTHORIZATION_INVALID,
    GEN4_PHASE7_DATA_AUTHORIZATION_MISSING,
    GEN4_PHASE7_DATA_CHECKPOINT_INVALID,
    GEN4_PHASE7_DATA_HOLDOUT_FORBIDDEN,
    GEN4_PHASE7_DATA_OUTPUT_EXISTS,
    GEN4_PHASE7_DATA_REQUEST_INVALID,
    GEN4_PHASE7_DATA_SYMBOL_UNKNOWN,
    GEN4_PHASE7_DATA_UNIVERSE_INVALID,
    GEN4_PHASE7_DATA_WARMUP_INVALID,
    Generation4Phase7DataError,
    Phase7QuoteClient,
    acquire_prospective_phase7_data,
)

RESEARCH_UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
FORBIDDEN = ("QQQM", "FALN", "IIPR", "PSTL", "EFAS")
CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
_BOUND_EVIDENCE = None


@pytest.fixture(autouse=True)
def _synthetic_authorization_evidence(bound_evidence):
    global _BOUND_EVIDENCE
    _BOUND_EVIDENCE = bound_evidence
    yield
    _BOUND_EVIDENCE = None


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _frames():
    calendar = xcals.get_calendar("XNYS")
    all_sessions = calendar.sessions_in_range("2025-01-01", "2026-09-30")
    scored_pos = all_sessions.get_loc(pd.Timestamp("2026-09-28"))
    index = all_sessions[scored_pos - 210 : scored_pos + 3]
    if index.tz is None:
        index = index.tz_localize("UTC")
    out = {}
    for i, symbol in enumerate(RESEARCH_UNIVERSE):
        close = [100.0 + 0.5 * (i + 1) * step for step in range(1, len(index) + 1)]
        out[symbol] = pd.DataFrame({"open": close, "close": close}, index=index)
    return out


class _FakeQuoteClient:
    def __init__(self, frames):
        self._frames = frames
        self.fetched = []
        self.closed = False

    def fetch_daily_bars(self, symbol, start, end):
        self.fetched.append(symbol)
        return self._frames[symbol]

    def close(self):
        self.closed = True


def _spy_client_factory(frames):
    created = {"count": 0, "clients": []}

    def factory(*, host, port):
        created["count"] += 1
        client = _FakeQuoteClient(frames)
        created["clients"].append(client)
        return client

    return factory, created


def _authorization(**overrides):
    return _BOUND_EVIDENCE.auth(**overrides)


def _request(**overrides):
    payload = {
        "schema_version": "GENERATION4-PHASE7-DATA-REQUEST-v1",
        "symbols": list(RESEARCH_UNIVERSE),
        "requested_start": str(_frames()[RESEARCH_UNIVERSE[0]].index[0].date()),
        "requested_end": "2026-09-30",
        "scored_start": "2026-09-28",
        "warmup_session_count": 210,
        "scored_session_count": 3,
    }
    payload.update(overrides)
    return payload


def _run(tmp_path, *, auth=None, request=None, captured=None):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    manifest = acquire_prospective_phase7_data(
        evaluation_authorization=auth if auth is not None else _authorization(),
        request=request if request is not None else _request(),
        output_dir=tmp_path / "out",
        retrieved_at_utc="2026-10-01T00:00:00Z",
        client_factory=factory,
    )
    if captured is not None:
        captured.update(created)
    return manifest, created


def _snapshot_manifest_path(output_dir, manifest):
    return Path(output_dir) / "snapshots" / manifest["snapshot_id"] / "manifest.json"


# ---------------------------------------------------------------------------
# No provider object is created before the authorization is validated.
# ---------------------------------------------------------------------------


def test_missing_authorization_fails_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=None,
            request=_request(),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_AUTHORIZATION_MISSING
    assert created["count"] == 0


def test_invalid_authorization_status_fails_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    bad = _authorization(status="DRAFT_TEMPLATE_NOT_AUTHORIZATION")
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=bad,
            request=_request(),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_AUTHORIZATION_INVALID
    assert created["count"] == 0


def test_authorization_with_live_trading_true_fails_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    bad = _authorization(live_trading_authorized=True)
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=bad,
            request=_request(),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_AUTHORIZATION_INVALID
    assert created["count"] == 0


def test_authorization_universe_mismatch_fails_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    bad = _authorization(research_universe=list(RESEARCH_UNIVERSE[:4]))
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=bad,
            request=_request(),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_AUTHORIZATION_INVALID
    assert created["count"] == 0


# ---------------------------------------------------------------------------
# The request is validated (universe / holdout / unknown / ranges) before any
# provider is created.
# ---------------------------------------------------------------------------


def test_exact_research_universe_is_accepted(tmp_path, capsys):
    manifest, created = _run(tmp_path)
    assert created["count"] == 1
    assert created["clients"][0].fetched == list(RESEARCH_UNIVERSE)
    assert created["clients"][0].closed is True


def test_universe_order_mismatch_rejected_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    reordered = list(RESEARCH_UNIVERSE)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=_authorization(),
            request=_request(symbols=reordered),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_UNIVERSE_INVALID
    assert created["count"] == 0


def test_extra_symbol_rejected_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=_authorization(),
            request=_request(symbols=list(RESEARCH_UNIVERSE) + ["XYZ"]),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_SYMBOL_UNKNOWN
    assert created["count"] == 0


def test_missing_symbol_rejected_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=_authorization(),
            request=_request(symbols=list(RESEARCH_UNIVERSE[:-1])),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_UNIVERSE_INVALID
    assert created["count"] == 0


@pytest.mark.parametrize("symbol", FORBIDDEN)
def test_forbidden_holdout_rejected_before_provider(tmp_path, symbol):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=_authorization(),
            request=_request(symbols=[symbol]),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_HOLDOUT_FORBIDDEN
    assert created["count"] == 0


def test_unknown_symbol_rejected_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=_authorization(),
            request=_request(symbols=list(RESEARCH_UNIVERSE) + ["AAPL"]),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_SYMBOL_UNKNOWN
    assert created["count"] == 0


def test_warmup_session_count_exceeding_limit_rejected_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=_authorization(),
            request=_request(warmup_session_count=211),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_WARMUP_INVALID
    assert created["count"] == 0


def test_scored_session_count_exceeding_checkpoint_rejected_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=_authorization(),
            request=_request(scored_session_count=253),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_CHECKPOINT_INVALID
    assert created["count"] == 0


def test_malformed_request_schema_rejected_before_provider(tmp_path):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    bad = _request()
    del bad["symbols"]
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=_authorization(),
            request=bad,
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-10-01T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_REQUEST_INVALID
    assert created["count"] == 0


# ---------------------------------------------------------------------------
# Trade context / order methods.
# ---------------------------------------------------------------------------


def test_trade_context_never_created_and_manifest_records_false(tmp_path):
    manifest, _ = _run(tmp_path)
    assert manifest["trading_context_created"] is False
    assert manifest["protected_holdout_symbols_accessed"] == []


def test_quote_client_exposes_no_order_or_trade_methods():
    names = {name for name in dir(Phase7QuoteClient) if not name.startswith("_")}
    forbidden = {
        "place_order",
        "submit_order",
        "open_trade",
        "close_trade",
        "buy",
        "sell",
        "order",
        "cancel_order",
    }
    assert not (names & forbidden)
    assert "fetch_daily_bars" in names


def test_module_source_contains_no_trade_or_order_api(tmp_path):
    from investment_tracker.independent_audit.post_generation3 import phase7_data

    source = Path(phase7_data.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "TradeContext",
        "place_order",
        "submit_order",
        "buy_stock",
        "sell_stock",
        "open_trade",
    ):
        assert forbidden not in source, f"forbidden identifier {forbidden!r} in module source"


def test_module_source_contains_no_holdout_symbols(tmp_path):
    """The module must not name any final-holdout ticker in its source.

    This mirrors the focused CI "Governance boundary" grep, which scans the
    whole ``post_generation3`` directory for the holdout tickers. The
    forbidden set is pinned by content hash (see the module) so a literal
    never appears in the evaluation source.
    """
    from investment_tracker.independent_audit.post_generation3 import phase7_data

    source = Path(phase7_data.__file__).read_text(encoding="utf-8")
    for symbol in FORBIDDEN:
        assert symbol not in source, f"holdout literal {symbol!r} in module source"


# ---------------------------------------------------------------------------
# Append-only, content-addressed snapshot output.
# ---------------------------------------------------------------------------


def test_append_only_snapshot_is_written(tmp_path):
    manifest, created = _run(tmp_path)
    snapshot_dir = Path(tmp_path) / "out" / "snapshots" / manifest["snapshot_id"]
    assert manifest["provider"] == "MOOMOO_OPEND"
    assert manifest["retrieved_at_utc"] == "2026-10-01T00:00:00Z"
    assert manifest["candidate_id"] == CANDIDATE_ID
    assert manifest["benchmark_symbol"] == "SPY"
    assert manifest["friction_cases_bps"] == [0, 3, 10, 25, 50]
    assert manifest["primary_friction_bps"] == 3

    # Every requested symbol has a bars file with a recorded content hash.
    for symbol in RESEARCH_UNIVERSE:
        bars_path = snapshot_dir / "bars" / f"{symbol}.csv"
        assert bars_path.exists()
        recorded = manifest["symbols"][symbol]["sha256"]
        assert recorded == sha256(bars_path.read_bytes()).hexdigest()

    # File hash table lists all bars files with matching hashes.
    recorded_files = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    for symbol in RESEARCH_UNIVERSE:
        relative = f"bars/{symbol}.csv"
        assert relative in recorded_files
        actual = (snapshot_dir / relative).read_bytes()
        assert recorded_files[relative] == sha256(actual).hexdigest()

    # Manifest self-hash is consistent over the manifest body.
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    assert manifest["manifest_sha256"] == sha256(_canonical(body)).hexdigest()


def test_existing_snapshot_is_never_overwritten(tmp_path):
    first, _ = _run(tmp_path)
    snapshot_dir = Path(tmp_path) / "out" / "snapshots" / first["snapshot_id"]
    manifest_before = (snapshot_dir / "manifest.json").read_bytes()
    bars_before = {
        symbol: (snapshot_dir / "bars" / f"{symbol}.csv").read_bytes()
        for symbol in RESEARCH_UNIVERSE
    }

    with pytest.raises(Generation4Phase7DataError) as excinfo:
        _run(tmp_path)

    assert excinfo.value.code == GEN4_PHASE7_DATA_OUTPUT_EXISTS
    # Nothing was changed on the second (refused) run.
    assert (snapshot_dir / "manifest.json").read_bytes() == manifest_before
    for symbol in RESEARCH_UNIVERSE:
        assert (snapshot_dir / "bars" / f"{symbol}.csv").read_bytes() == bars_before[symbol]
