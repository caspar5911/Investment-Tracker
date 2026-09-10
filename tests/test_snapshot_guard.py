import pytest

from investment_tracker.snapshot import StaleSnapshotError, verify_snapshot_fresh


class Manifest:
    input_snapshot_digests = {"spy": "a", "governance": "b"}


def test_exact_snapshot_digests_are_accepted():
    verify_snapshot_fresh(Manifest(), {"spy": "a", "governance": "b"})


def test_changed_snapshot_digest_is_rejected():
    with pytest.raises(StaleSnapshotError, match="spy"):
        verify_snapshot_fresh(Manifest(), {"spy": "changed", "governance": "b"})


def test_missing_current_digest_fails_closed():
    with pytest.raises(StaleSnapshotError, match="governance"):
        verify_snapshot_fresh(Manifest(), {"spy": "a"})
