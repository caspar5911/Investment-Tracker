from datetime import datetime, timedelta, timezone

import pytest

from investment_tracker.operations import (
    RECON_009,
    AlertDispatcher,
    AlertStatus,
    RecoveryMismatchError,
    RunMonitor,
    verify_recovery_readback,
)


class RecordingSink:
    def __init__(self, results: list[bool]) -> None:
        self.results = iter(results)
        self.deliveries = []

    def deliver(self, alert):
        self.deliveries.append(alert)
        return next(self.results)


NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)


def test_alert_retry_acknowledgement_and_idempotent_deduplication():
    sink = RecordingSink([False, True])
    dispatcher = AlertDispatcher(sink, max_attempts=3)

    alert = dispatcher.raise_alert("run-1", "STALE_RUN", "worker heartbeat expired", NOW)
    assert dispatcher.raise_alert("run-1", "STALE_RUN", "duplicate", NOW) is alert
    assert dispatcher.deliver(alert.alert_id).status == AlertStatus.RETRY_PENDING
    assert dispatcher.deliver(alert.alert_id).status == AlertStatus.DELIVERED
    assert len(sink.deliveries) == 2

    acknowledged = dispatcher.acknowledge(alert.alert_id, "coordinator", NOW)
    assert acknowledged.status == AlertStatus.ACKNOWLEDGED
    assert dispatcher.acknowledge(alert.alert_id, "coordinator", NOW) == acknowledged


def test_exhausted_delivery_escalates_once():
    primary = RecordingSink([False, False])
    escalation = RecordingSink([True])
    dispatcher = AlertDispatcher(primary, escalation, max_attempts=2)
    alert = dispatcher.raise_alert("run-2", "READBACK_FAILED", "digest mismatch", NOW)

    dispatcher.deliver(alert.alert_id)
    result = dispatcher.deliver(alert.alert_id)
    assert result.status == AlertStatus.ESCALATED
    assert len(escalation.deliveries) == 1
    assert dispatcher.deliver(alert.alert_id) == result
    assert len(escalation.deliveries) == 1


def test_stale_run_detection_is_deterministic_and_deduplicated():
    dispatcher = AlertDispatcher(RecordingSink([True]))
    monitor = RunMonitor(dispatcher, stale_after=timedelta(minutes=15))
    monitor.heartbeat("run-3", NOW)

    assert monitor.detect_stale(NOW + timedelta(minutes=15)) == []
    first = monitor.detect_stale(NOW + timedelta(minutes=15, seconds=1))
    second = monitor.detect_stale(NOW + timedelta(hours=1))
    assert len(first) == 1
    assert second == first


def test_recovery_requires_exact_readback_and_is_idempotent():
    assert verify_recovery_readback("run-4", "sha256:abc", lambda: "sha256:abc")
    assert verify_recovery_readback("run-4", "sha256:abc", lambda: "sha256:abc")
    with pytest.raises(RecoveryMismatchError, match="run-4"):
        verify_recovery_readback("run-4", "sha256:abc", lambda: "sha256:def")


def test_recon_009_is_a_hard_production_support_limitation():
    assert RECON_009.code == "RECON-009"
    assert RECON_009.resolved is False
    assert RECON_009.hard_gate is True

