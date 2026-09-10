from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from investment_tracker.governance import FROZEN_VERSIONS
from investment_tracker.models import InputSnapshot, WorkerManifest


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
