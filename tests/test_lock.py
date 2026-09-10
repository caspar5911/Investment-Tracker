import json
from datetime import datetime, timedelta, timezone

import pytest

from investment_tracker.coordinator_lock import CanonicalWriteLock, LockHeldError, StaleLockError


def test_lock_is_single_writer_and_owner_releases(tmp_path):
    path = tmp_path / "lock.json"
    lock = CanonicalWriteLock(path)
    lock.acquire("COORD-1", "URA-2019", "SNAP-1")
    data = json.loads(path.read_text())
    assert data["run_id"] == "COORD-1"
    assert data["scope"] == "URA-2019"
    assert data["snapshot_id"] == "SNAP-1"

    with pytest.raises(LockHeldError):
        lock.acquire("COORD-2", "CIBR-2019", "SNAP-2")
    with pytest.raises(LockHeldError):
        lock.release("COORD-2")

    lock.release("COORD-1")
    assert not path.exists()


def test_stale_lock_is_reported_but_not_broken(tmp_path):
    path = tmp_path / "lock.json"
    path.write_text(json.dumps({
        "run_id": "OLD",
        "scope": "URA-2019",
        "snapshot_id": "SNAP-OLD",
        "acquired_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    }))
    lock = CanonicalWriteLock(path, stale_after_seconds=60)
    with pytest.raises(StaleLockError):
        lock.acquire("NEW", "URA-2020", "SNAP-NEW")
    assert path.exists()
