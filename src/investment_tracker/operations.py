"""Fail-closed, repository-local operational reliability primitives.

The objects in this module hold process-local state only.  They neither mutate the
canonical evidence plane nor perform network delivery themselves; callers must
provide an explicit alert sink and readback function.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Callable, Protocol


@dataclass(frozen=True)
class Limitation:
    code: str
    description: str
    resolved: bool
    hard_gate: bool


RECON_009 = Limitation(
    code="RECON-009",
    description="End-to-end operational reconciliation evidence is unresolved",
    resolved=False,
    hard_gate=True,
)


class AlertStatus(StrEnum):
    PENDING = "PENDING"
    RETRY_PENDING = "RETRY_PENDING"
    DELIVERED = "DELIVERED"
    ESCALATED = "ESCALATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


@dataclass(frozen=True)
class Alert:
    alert_id: str
    run_id: str
    code: str
    message: str
    raised_at: datetime
    status: AlertStatus = AlertStatus.PENDING
    attempts: int = 0
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None


class AlertSink(Protocol):
    def deliver(self, alert: Alert) -> bool: ...


class AlertDispatcher:
    """Retrying dispatcher with event-key deduplication and explicit ack state."""

    def __init__(
        self,
        sink: AlertSink,
        escalation_sink: AlertSink | None = None,
        *,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._sink = sink
        self._escalation_sink = escalation_sink
        self._max_attempts = max_attempts
        self._alerts: dict[str, Alert] = {}
        self._event_ids: dict[tuple[str, str], str] = {}

    def raise_alert(
        self, run_id: str, code: str, message: str, raised_at: datetime
    ) -> Alert:
        _require_aware(raised_at)
        event_key = (run_id, code)
        if event_key in self._event_ids:
            return self._alerts[self._event_ids[event_key]]
        token = f"{run_id}\0{code}".encode()
        alert_id = sha256(token).hexdigest()
        alert = Alert(alert_id, run_id, code, message, raised_at)
        self._alerts[alert_id] = alert
        self._event_ids[event_key] = alert_id
        return alert

    def deliver(self, alert_id: str) -> Alert:
        alert = self._alerts[alert_id]
        if alert.status in {
            AlertStatus.DELIVERED,
            AlertStatus.ESCALATED,
            AlertStatus.ACKNOWLEDGED,
        }:
            return alert
        attempts = alert.attempts + 1
        try:
            delivered = self._sink.deliver(alert)
        except Exception:
            delivered = False
        if delivered:
            updated = replace(alert, attempts=attempts, status=AlertStatus.DELIVERED)
        elif attempts < self._max_attempts:
            updated = replace(alert, attempts=attempts, status=AlertStatus.RETRY_PENDING)
        else:
            updated = replace(alert, attempts=attempts, status=AlertStatus.ESCALATED)
            if self._escalation_sink is not None:
                # Escalation is best-effort but the unresolved condition remains
                # escalated regardless; acknowledgement must still be explicit.
                try:
                    self._escalation_sink.deliver(updated)
                except Exception:
                    pass
        self._alerts[alert_id] = updated
        return updated

    def acknowledge(self, alert_id: str, actor: str, acknowledged_at: datetime) -> Alert:
        _require_aware(acknowledged_at)
        alert = self._alerts[alert_id]
        if alert.status == AlertStatus.ACKNOWLEDGED:
            return alert
        if alert.status not in {AlertStatus.DELIVERED, AlertStatus.ESCALATED}:
            raise ValueError("an alert must be delivered or escalated before acknowledgement")
        if not actor.strip():
            raise ValueError("acknowledging actor is required")
        updated = replace(
            alert,
            status=AlertStatus.ACKNOWLEDGED,
            acknowledged_by=actor,
            acknowledged_at=acknowledged_at,
        )
        self._alerts[alert_id] = updated
        return updated


class RunMonitor:
    def __init__(self, dispatcher: AlertDispatcher, *, stale_after: timedelta) -> None:
        if stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive")
        self._dispatcher = dispatcher
        self._stale_after = stale_after
        self._heartbeats: dict[str, datetime] = {}

    def heartbeat(self, run_id: str, observed_at: datetime) -> None:
        _require_aware(observed_at)
        current = self._heartbeats.get(run_id)
        if current is not None and observed_at < current:
            raise ValueError("heartbeat time cannot move backwards")
        self._heartbeats[run_id] = observed_at

    def detect_stale(self, observed_at: datetime) -> list[Alert]:
        _require_aware(observed_at)
        return [
            self._dispatcher.raise_alert(
                run_id, "STALE_RUN", "worker heartbeat expired", observed_at
            )
            for run_id, heartbeat in sorted(self._heartbeats.items())
            if observed_at - heartbeat > self._stale_after
        ]


class RecoveryMismatchError(RuntimeError):
    pass


def verify_recovery_readback(
    run_id: str, expected_digest: str, readback: Callable[[], str]
) -> bool:
    """Fail closed unless recovered state exactly matches its expected digest."""

    if not expected_digest:
        raise ValueError("expected recovery digest is required")
    try:
        actual_digest = readback()
    except Exception as exc:
        raise RecoveryMismatchError(f"recovery readback failed for {run_id}") from exc
    if actual_digest != expected_digest:
        raise RecoveryMismatchError(f"recovery readback digest mismatch for {run_id}")
    return True


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("operational timestamps must be timezone-aware")

