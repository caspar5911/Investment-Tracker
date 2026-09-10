from datetime import date, datetime, timezone

import pytest

from investment_tracker.governance import FROZEN_VERSIONS
from investment_tracker.models import InputSnapshot, WorkerManifest
from investment_tracker.snapshot import (
    SnapshotLineageError,
    StaleSnapshotError,
    verify_manifest_snapshot_lineage,
    verify_snapshot_fresh,
)


def _snapshot():
    return InputSnapshot(
        snapshot_id="SNAP-001",
        dispatch_run_id="COORD-001",
        versions=FROZEN_VERSIONS.as_dict(),
        asset="URA",
        start_date=date(2019, 1, 1),
        end_date=date(2019, 12, 31),
        spy_digest="spy-a",
        dq_refs=[],
        phase_matrix_state="NOT_STARTED",
        input_digests={"spy": "spy-a", "governance": "gov-a"},
        dispatch_timestamp=datetime(2026, 9, 10, tzinfo=timezone.utc),
        locked_holdout_excluded=True,
    )


def _manifest(**overrides):
    values = dict(
        role="URA",
        run_id="WORKER-001",
        input_snapshot_id="SNAP-001",
        input_snapshot_digests={"spy": "spy-a", "governance": "gov-a"},
        asset="URA",
        start_date=date(2019, 1, 1),
        end_date=date(2019, 12, 31),
        versions=FROZEN_VERSIONS.as_dict(),
        source_provider="Alpaca",
        source_feed="SIP",
        input_refs=["SNAP-001"],
        output_digests={"market-data.csv": "out-a"},
        locked_holdout_excluded=True,
        completion_status="READY_FOR_COORDINATOR_REVIEW",
    )
    values.update(overrides)
    return WorkerManifest(**values)


def test_snapshot_freshness_requires_exact_digest_key_set():
    manifest = _manifest()
    with pytest.raises(StaleSnapshotError, match="canonical digest set changed"):
        verify_snapshot_fresh(
            manifest,
            {"spy": "spy-a", "governance": "gov-a", "dq": "dq-new"},
        )


def test_manifest_snapshot_lineage_accepts_exact_scope_and_current_digests():
    snapshot = _snapshot()
    verify_manifest_snapshot_lineage(
        _manifest(), snapshot, {"spy": "spy-a", "governance": "gov-a"}
    )


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"input_snapshot_id": "SNAP-WRONG"}, "snapshot ID"),
        ({"asset": "CIBR"}, "asset scope"),
        ({"start_date": date(2020, 1, 1)}, "date scope"),
        ({"input_snapshot_digests": {"spy": "spy-wrong", "governance": "gov-a"}}, "digest map"),
    ],
)
def test_manifest_snapshot_lineage_rejects_scope_mismatch(overrides, match):
    with pytest.raises(SnapshotLineageError, match=match):
        verify_manifest_snapshot_lineage(
            _manifest(**overrides),
            _snapshot(),
            {"spy": "spy-a", "governance": "gov-a"},
        )
