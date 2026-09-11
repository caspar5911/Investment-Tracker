from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence


class CanonicalWriteError(RuntimeError):
    """Base class for canonical-write safety failures."""


class ConcurrentWriterError(CanonicalWriteError):
    pass


class StaleLeaseTakeoverError(CanonicalWriteError):
    pass


class WriteConflictError(CanonicalWriteError):
    pass


class ReadbackMismatchError(CanonicalWriteError):
    pass


class LeaseStateError(CanonicalWriteError):
    pass


class WriteDisposition(StrEnum):
    READY = "READY"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"


@dataclass(frozen=True)
class WriteLease:
    writer_id: str
    run_id: str
    acquired_at: datetime
    expires_at: datetime
    generation: int


@dataclass(frozen=True)
class CommittedWrite:
    semantic_key: str
    payload_digest: str
    run_id: str
    writer_id: str
    committed_at: datetime


def canonical_payload_digest(rows: Iterable[Mapping[str, object] | Sequence[object]]) -> str:
    """Return a deterministic digest for a canonical write payload.

    Dict keys are sorted and compact JSON is used so callers can compare a
    staged payload with a post-write readback without relying on cell location.
    """

    materialized = list(rows)
    encoded = json.dumps(
        materialized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class CanonicalWriteCoordinator:
    """Process-local single-writer and idempotency guard.

    The class deliberately does not talk to Google Sheets. Runtime adapters
    must persist the lease/commit state in a durable store with compare-and-set
    semantics. This object defines and tests the invariant the adapter must
    preserve.

    A write is identified by a semantic key, not by a row number. Replaying the
    same semantic key with the same payload digest is idempotent. Replaying it
    with a different payload is a hard conflict.
    """

    def __init__(self) -> None:
        self._lease: WriteLease | None = None
        self._generation = 0
        self._committed: dict[str, CommittedWrite] = {}

    @property
    def active_lease(self) -> WriteLease | None:
        return self._lease

    def acquire(
        self,
        *,
        writer_id: str,
        run_id: str,
        now: datetime,
        ttl: timedelta,
        expected_stale_generation: int | None = None,
    ) -> WriteLease:
        _require_text(writer_id, "writer_id")
        _require_text(run_id, "run_id")
        _require_aware(now)
        if ttl <= timedelta(0):
            raise ValueError("ttl must be positive")

        current = self._lease
        if current is not None and now < current.expires_at:
            if current.writer_id == writer_id and current.run_id == run_id:
                return current
            raise ConcurrentWriterError(
                f"canonical writer already active: {current.writer_id}/{current.run_id}"
            )

        if current is not None and now >= current.expires_at:
            if expected_stale_generation != current.generation:
                raise StaleLeaseTakeoverError(
                    "stale lease takeover requires the observed generation"
                )

        self._generation += 1
        lease = WriteLease(
            writer_id=writer_id,
            run_id=run_id,
            acquired_at=now,
            expires_at=now + ttl,
            generation=self._generation,
        )
        self._lease = lease
        return lease

    def renew(self, lease: WriteLease, *, now: datetime, ttl: timedelta) -> WriteLease:
        _require_aware(now)
        if ttl <= timedelta(0):
            raise ValueError("ttl must be positive")
        self._assert_current(lease, now=now, allow_expired=False)
        renewed = WriteLease(
            writer_id=lease.writer_id,
            run_id=lease.run_id,
            acquired_at=lease.acquired_at,
            expires_at=now + ttl,
            generation=lease.generation,
        )
        self._lease = renewed
        return renewed

    def prepare(
        self,
        lease: WriteLease,
        *,
        semantic_key: str,
        payload_digest: str,
        now: datetime,
    ) -> WriteDisposition:
        _require_text(semantic_key, "semantic_key")
        _require_digest(payload_digest)
        self._assert_current(lease, now=now, allow_expired=False)

        existing = self._committed.get(semantic_key)
        if existing is None:
            return WriteDisposition.READY
        if existing.payload_digest == payload_digest:
            return WriteDisposition.ALREADY_COMMITTED
        raise WriteConflictError(
            f"semantic key already committed with a different payload: {semantic_key}"
        )

    def commit(
        self,
        lease: WriteLease,
        *,
        semantic_key: str,
        payload_digest: str,
        readback_digest: str,
        now: datetime,
    ) -> CommittedWrite:
        disposition = self.prepare(
            lease,
            semantic_key=semantic_key,
            payload_digest=payload_digest,
            now=now,
        )
        if disposition == WriteDisposition.ALREADY_COMMITTED:
            return self._committed[semantic_key]

        _require_digest(readback_digest)
        if readback_digest != payload_digest:
            raise ReadbackMismatchError(
                f"canonical readback mismatch for semantic key: {semantic_key}"
            )

        committed = CommittedWrite(
            semantic_key=semantic_key,
            payload_digest=payload_digest,
            run_id=lease.run_id,
            writer_id=lease.writer_id,
            committed_at=now,
        )
        self._committed[semantic_key] = committed
        return committed

    def release(self, lease: WriteLease, *, now: datetime) -> None:
        _require_aware(now)
        self._assert_current(lease, now=now, allow_expired=True)
        self._lease = None

    def committed(self, semantic_key: str) -> CommittedWrite | None:
        return self._committed.get(semantic_key)

    def _assert_current(
        self, lease: WriteLease, *, now: datetime, allow_expired: bool
    ) -> None:
        _require_aware(now)
        current = self._lease
        if current is None or current != lease:
            raise LeaseStateError("write lease is not the current canonical lease")
        if not allow_expired and now >= current.expires_at:
            raise LeaseStateError("canonical write lease has expired")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_text(value: str, field: str) -> None:
    if not value.strip():
        raise ValueError(f"{field} must not be empty")


def _require_digest(value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("payload digest must be lowercase sha256 hex")


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("canonical write timestamps must be timezone-aware")
