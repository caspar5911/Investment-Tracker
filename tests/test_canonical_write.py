from datetime import datetime, timedelta, timezone

import pytest

from investment_tracker.canonical_write import (
    CanonicalWriteCoordinator,
    ConcurrentWriterError,
    LeaseStateError,
    ReadbackMismatchError,
    StaleLeaseTakeoverError,
    WriteConflictError,
    WriteDisposition,
    canonical_payload_digest,
)


NOW = datetime(2026, 9, 11, 7, 30, tzinfo=timezone.utc)
TTL = timedelta(minutes=10)


def test_only_one_live_writer_can_hold_the_canonical_lease():
    guard = CanonicalWriteCoordinator()
    lease = guard.acquire(writer_id="coordinator", run_id="run-1", now=NOW, ttl=TTL)

    with pytest.raises(ConcurrentWriterError):
        guard.acquire(
            writer_id="independent-worker",
            run_id="run-2",
            now=NOW + timedelta(seconds=1),
            ttl=TTL,
        )

    assert guard.active_lease == lease


def test_same_writer_same_run_reacquire_is_idempotent():
    guard = CanonicalWriteCoordinator()
    first = guard.acquire(writer_id="coordinator", run_id="run-1", now=NOW, ttl=TTL)
    second = guard.acquire(
        writer_id="coordinator",
        run_id="run-1",
        now=NOW + timedelta(seconds=1),
        ttl=TTL,
    )

    assert second == first


def test_stale_takeover_requires_observed_generation():
    guard = CanonicalWriteCoordinator()
    first = guard.acquire(writer_id="coordinator", run_id="run-1", now=NOW, ttl=TTL)
    stale_time = NOW + TTL

    with pytest.raises(StaleLeaseTakeoverError):
        guard.acquire(
            writer_id="recovery",
            run_id="run-2",
            now=stale_time,
            ttl=TTL,
        )

    takeover = guard.acquire(
        writer_id="recovery",
        run_id="run-2",
        now=stale_time,
        ttl=TTL,
        expected_stale_generation=first.generation,
    )
    assert takeover.generation == first.generation + 1


def test_semantic_write_is_idempotent_only_for_identical_payload():
    guard = CanonicalWriteCoordinator()
    lease = guard.acquire(writer_id="coordinator", run_id="run-1", now=NOW, ttl=TTL)
    digest = canonical_payload_digest([{"asset": "URA", "date": "2026-09-11"}])

    assert (
        guard.prepare(
            lease,
            semantic_key="RunLedger:run-1",
            payload_digest=digest,
            now=NOW,
        )
        == WriteDisposition.READY
    )

    committed = guard.commit(
        lease,
        semantic_key="RunLedger:run-1",
        payload_digest=digest,
        readback_digest=digest,
        now=NOW,
    )
    assert committed.payload_digest == digest

    assert (
        guard.prepare(
            lease,
            semantic_key="RunLedger:run-1",
            payload_digest=digest,
            now=NOW,
        )
        == WriteDisposition.ALREADY_COMMITTED
    )

    different = canonical_payload_digest([{"asset": "URA", "date": "2026-09-12"}])
    with pytest.raises(WriteConflictError):
        guard.prepare(
            lease,
            semantic_key="RunLedger:run-1",
            payload_digest=different,
            now=NOW,
        )


def test_readback_must_match_before_commit_is_recorded():
    guard = CanonicalWriteCoordinator()
    lease = guard.acquire(writer_id="coordinator", run_id="run-1", now=NOW, ttl=TTL)
    expected = canonical_payload_digest([[1, 2, 3]])
    actual = canonical_payload_digest([[1, 2, 4]])

    with pytest.raises(ReadbackMismatchError):
        guard.commit(
            lease,
            semantic_key="ReplayDaily:URA:2026-09-11",
            payload_digest=expected,
            readback_digest=actual,
            now=NOW,
        )

    assert guard.committed("ReplayDaily:URA:2026-09-11") is None


def test_expired_or_replaced_lease_cannot_write():
    guard = CanonicalWriteCoordinator()
    first = guard.acquire(writer_id="coordinator", run_id="run-1", now=NOW, ttl=TTL)
    digest = canonical_payload_digest([[1]])

    with pytest.raises(LeaseStateError):
        guard.prepare(
            first,
            semantic_key="RunLedger:run-1",
            payload_digest=digest,
            now=NOW + TTL,
        )

    second = guard.acquire(
        writer_id="recovery",
        run_id="run-2",
        now=NOW + TTL,
        ttl=TTL,
        expected_stale_generation=first.generation,
    )
    with pytest.raises(LeaseStateError):
        guard.release(first, now=NOW + TTL)

    guard.release(second, now=NOW + TTL)
    assert guard.active_lease is None


def test_payload_digest_is_stable_for_mapping_key_order():
    left = canonical_payload_digest([{"b": 2, "a": 1}])
    right = canonical_payload_digest([{"a": 1, "b": 2}])
    assert left == right
