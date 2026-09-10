from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from investment_tracker.governance import FROZEN_VERSIONS
from investment_tracker.models import (
    BaselineRow,
    EpisodeOutcomeRow,
    InputSnapshot,
    MarketBar,
    ReplayDailyRow,
    WorkerManifest,
)


def snapshot_kwargs():
    return {
        "snapshot_id": "SNAP-001",
        "dispatch_run_id": "COORD-001",
        "versions": FROZEN_VERSIONS.as_dict(),
        "asset": "URA",
        "start_date": date(2019, 1, 1),
        "end_date": date(2019, 12, 31),
        "spy_digest": "spy-2019-digest",
        "dq_refs": [],
        "phase_matrix_state": "NOT_STARTED",
        "input_digests": {"spy": "spy-2019-digest", "governance": "gov-1"},
        "dispatch_timestamp": datetime(2026, 9, 10, tzinfo=timezone.utc),
        "locked_holdout_excluded": True,
    }


def test_input_snapshot_requires_frozen_versions_and_allowed_asset():
    snap = InputSnapshot(**snapshot_kwargs())
    assert snap.asset == "URA"
    assert snap.versions == FROZEN_VERSIONS.as_dict()

    bad = snapshot_kwargs()
    bad["asset"] = "HACK"
    with pytest.raises(ValidationError):
        InputSnapshot(**bad)

    bad = snapshot_kwargs()
    bad["versions"] = {**FROZEN_VERSIONS.as_dict(), "calc": "CALC-v9"}
    with pytest.raises(ValidationError):
        InputSnapshot(**bad)


def test_worker_manifest_carries_exact_snapshot_lineage():
    manifest = WorkerManifest(
        role="URA",
        run_id="WORKER-001",
        input_snapshot_id="SNAP-001",
        input_snapshot_digests={"spy": "spy-2019-digest", "governance": "gov-1"},
        asset="ura",
        start_date=date(2019, 1, 1),
        end_date=date(2019, 12, 31),
        versions=FROZEN_VERSIONS.as_dict(),
        source_provider="Alpaca",
        source_feed="SIP",
        input_refs=["Phase Matrix URA 2019"],
        output_digests={"market-data.csv": "abc"},
        locked_holdout_excluded=True,
        completion_status="READY_FOR_COORDINATOR_REVIEW",
    )
    assert manifest.asset == "URA"
    assert manifest.input_snapshot_id == "SNAP-001"


def test_canonical_models_match_live_sheet_headers_exactly():
    assert list(MarketBar.model_fields) == [
        "asset", "bar_date", "open_raw", "high_raw", "low_raw", "close_raw",
        "volume_raw", "trade_count_raw", "vwap_raw", "provider", "feed",
        "ingestion_run_id", "split_factor", "open_norm", "high_norm", "low_norm",
        "close_norm", "range_usable", "close_usable", "dq_refs", "source_window",
        "recorded_at_utc", "bar_key", "source_digest", "cache_status",
        "normalization_version",
    ]
    assert list(ReplayDailyRow.model_fields) == [
        "asset", "bar_date", "spec_version", "close_norm", "sma200", "prior60_high",
        "pullback_pct", "prior_close", "sma5", "ret20", "spy_ret20",
        "distance_to_60d_high", "trend_gate", "pullback_gate", "stabilization_gate",
        "rs_gate", "chase_gate", "signal_state", "episode_start", "data_status",
        "calculation_run_id", "evidence_ref", "calculation_version",
    ]
    assert list(EpisodeOutcomeRow.model_fields) == [
        "episode_id", "asset", "signal_start_date", "signal_end_date", "signal_days",
        "entry_date", "entry_open", "horizon_td", "asset_return", "spy_return",
        "excess_spy", "cash_return", "excess_cash", "mae", "mfe", "max_drawdown",
        "friction_bps", "return_net", "dq_status", "calculation_run_id",
        "calculation_version",
    ]
    assert list(BaselineRow.model_fields) == [
        "baseline_record_id", "asset", "baseline_type", "signal_start_date",
        "signal_end_date", "signal_days", "entry_date", "entry_open", "horizon_td",
        "asset_return", "spy_return", "excess_spy", "cash_return", "excess_cash",
        "mae", "mfe", "friction_bps", "return_net", "terminal_value",
        "contributed_capital", "money_weighted_return", "dq_status",
        "calculation_run_id", "calculation_version",
    ]
