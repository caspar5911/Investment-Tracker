"""B7: RECON-009 runtime proof harness — collect/verify the 5 evidence
classes into an immutable hash-addressed bundle, but the gate MUST STAY OPEN:
code, unit tests, or a synthetic bundle never resolve RECON-009."""

from __future__ import annotations

import pytest

from investment_tracker.quant.generation2 import recon009 as R


def commit() -> str:
    return "a" * 40


def run_id() -> str:
    return "RUN-0001"


def delivery(rec: R.SuccessfulAlertDelivery) -> R.SuccessfulAlertDelivery:
    return rec


def make_all() -> dict:
    cid = "alert-1"
    wid = "write-1"
    sha = "hash-1"
    return {
        "delivery": R.SuccessfulAlertDelivery(
            run_id=run_id(),
            commit_sha=commit(),
            recorded_utc="2026-09-22T00:00:00Z",
            input_identity="event-A",
            output_identity=f"out-{cid}",
            classification="SUCCESS",
            alert_identity=cid,
            destination="ops://alertbus",
            delivery_receipt="rcpt-1",
        ),
        "ack": R.Acknowledgement(
            run_id=run_id(),
            commit_sha=commit(),
            recorded_utc="2026-09-22T00:01:00Z",
            input_identity=cid,
            output_identity="ack-1",
            classification="SUCCESS",
            alert_identity=cid,
            acknowledgement_identity="ack-1",
            actor="operator-alpha",
            acknowledgement_utc="2026-09-22T00:01:00Z",
        ),
        "retry": R.FailedDeliveryRetryOrEscalation(
            run_id=run_id(),
            commit_sha=commit(),
            recorded_utc="2026-09-22T00:02:00Z",
            input_identity="event-B",
            output_identity="out-retry",
            classification="SUCCESS",
            alert_identity="alert-2",
            attempt_count=3,
            retry_executed=True,
            escalation_executed=True,
            terminal_outcome="ESCALATED",
            lineage=("attempt-1", "attempt-2", "attempt-3"),
        ),
        "recovery": R.InterruptedWriteRecovery(
            run_id=run_id(),
            commit_sha=commit(),
            recorded_utc="2026-09-22T00:03:00Z",
            input_identity=wid,
            output_identity="recovered-1",
            classification="SUCCESS",
            write_identity=wid,
            interrupted=True,
            recovered=True,
            duplicate_records=0,
            lost_records=0,
        ),
        "readback": R.PostWriteReadbackVerification(
            run_id=run_id(),
            commit_sha=commit(),
            recorded_utc="2026-09-22T00:04:00Z",
            input_identity=wid,
            output_identity="readback-1",
            classification="SUCCESS",
            write_identity=wid,
            intended_sha256=sha,
            readback_sha256=sha,
        ),
    }


def build(records: dict) -> R.Recon009ProofBundle:
    return R.build_bundle(
        delivery=records["delivery"],
        acknowledgement=records["ack"],
        failed_delivery=records["retry"],
        interrupted_write=records["recovery"],
        readback=records["readback"],
    )


def test_bundle_hash_is_stable_and_content_sensitive() -> None:
    recs = make_all()
    a = build(recs)
    b = build(make_all())
    assert a.bundle_sha256 == b.bundle_sha256
    assert len(a.bundle_sha256) == 64
    # Mutating one record changes the bundle identity.
    recs2 = make_all()
    recs2["delivery"] = R.SuccessfulAlertDelivery(
        **{**recs2["delivery"].model_dump(), "destination": "ops://other"}
    )
    assert build(recs2).bundle_sha256 != a.bundle_sha256


def test_complete_bundle_all_evidence_pass() -> None:
    assessment = R.assess(build(make_all()))
    assert assessment.evidence_status == "ALL_EVIDENCE_PASS"
    assert assessment.incomplete_classes == ()
    # The gate itself must stay OPEN: a synthetic/code-driven bundle never
    # resolves RECON-009.
    assert assessment.gate_status == "OPEN"
    assert assessment.resolution_requires_operator_governance is True


def test_missing_class_is_incomplete_and_open() -> None:
    recs = make_all()
    bundle = R.build_bundle(
        delivery=recs["delivery"],
        acknowledgement=None,
        failed_delivery=recs["retry"],
        interrupted_write=recs["recovery"],
        readback=recs["readback"],
    )
    assessment = R.assess(bundle)
    assert assessment.evidence_status == "INCOMPLETE"
    assert "ACKNOWLEDGEMENT" in assessment.incomplete_classes
    assert assessment.gate_status == "OPEN"


def test_readback_mismatch_is_failure_not_silent() -> None:
    recs = make_all()
    recs["readback"] = R.PostWriteReadbackVerification(
        **{**recs["readback"].model_dump(), "readback_sha256": "DIFFERENT", "classification": "FAILURE"}
    )
    assessment = R.assess(build(recs))
    assert assessment.evidence_status != "ALL_EVIDENCE_PASS"
    assert "POST_WRITE_READBACK_VERIFICATION" in assessment.incomplete_classes
    assert assessment.gate_status == "OPEN"


def test_interrupted_write_with_duplicates_fails() -> None:
    recs = make_all()
    recs["recovery"] = R.InterruptedWriteRecovery(
        **{**recs["recovery"].model_dump(), "duplicate_records": 1, "recovered": True}
    )
    assessment = R.assess(build(recs))
    assert "INTERRUPTED_WRITE_RECOVERY" in assessment.incomplete_classes
    assert assessment.gate_status == "OPEN"


def test_acknowledgement_not_linked_fails() -> None:
    recs = make_all()
    recs["ack"] = R.Acknowledgement(
        **{**recs["ack"].model_dump(), "alert_identity": "WRONG-ALERT"}
    )
    assessment = R.assess(build(recs))
    assert "ACKNOWLEDGEMENT" in assessment.incomplete_classes
    assert assessment.gate_status == "OPEN"


def test_retry_with_zero_attempts_fails() -> None:
    recs = make_all()
    recs["retry"] = R.FailedDeliveryRetryOrEscalation(
        **{**recs["retry"].model_dump(), "attempt_count": 0}
    )
    assessment = R.assess(build(recs))
    assert "FAILED_DELIVERY_RETRY_OR_ESCALATION" in assessment.incomplete_classes
    assert assessment.gate_status == "OPEN"


def test_inconsistent_commit_sha_fails() -> None:
    recs = make_all()
    recs["readback"] = R.PostWriteReadbackVerification(
        **{**recs["readback"].model_dump(), "commit_sha": "b" * 40}
    )
    assessment = R.assess(build(recs))
    assert assessment.evidence_status != "ALL_EVIDENCE_PASS"
    assert assessment.consistent_commit_sha is False
    assert assessment.gate_status == "OPEN"


def test_inconsistent_run_id_fails() -> None:
    recs = make_all()
    recs["ack"] = R.Acknowledgement(**{**recs["ack"].model_dump(), "run_id": "RUN-9999"})
    assessment = R.assess(build(recs))
    assert assessment.consistent_run_id is False
    assert assessment.gate_status == "OPEN"


def test_partial_completion_leaves_open() -> None:
    # Even a perfectly complete, hash-addressed synthetic bundle stays OPEN.
    recs = make_all()
    for name in list(recs):
        recs[name] = None  # all missing
    bundle = R.build_bundle(
        delivery=recs["delivery"],
        acknowledgement=recs["ack"],
        failed_delivery=recs["retry"],
        interrupted_write=recs["recovery"],
        readback=recs["readback"],
    )
    assessment = R.assess(bundle)
    assert assessment.evidence_status == "INCOMPLETE"
    assert assessment.gate_status == "OPEN"


def test_invalid_commit_sha_rejected() -> None:
    with pytest.raises(Exception):
        R.SuccessfulAlertDelivery(
            run_id=run_id(),
            commit_sha="not-a-sha",
            recorded_utc="2026-09-22T00:00:00Z",
            input_identity="e",
            output_identity="o",
            classification="SUCCESS",
            alert_identity="a",
            destination="d",
            delivery_receipt="r",
        )


def test_readback_mismatch_rejected_at_construction() -> None:
    # The harness refuses a readback record that claims matched but whose
    # hashes differ: mismatch must surface as FAILURE/ABSTAIN, not silent.
    with pytest.raises(Exception):
        R.PostWriteReadbackVerification(
            run_id=run_id(),
            commit_sha=commit(),
            recorded_utc="2026-09-22T00:00:00Z",
            input_identity="w",
            output_identity="o",
            classification="SUCCESS",
            write_identity="w",
            intended_sha256="h1",
            readback_sha256="h2",
        )


def test_bundle_is_frozen() -> None:
    recs = make_all()
    bundle = build(recs)
    with pytest.raises(Exception):
        bundle.bundle_sha256 = "x"  # type: ignore[misc]


def test_gate_status_open_even_when_all_pass() -> None:
    # The central B7 invariant: even a fully passing, hash-addressed,
    # code-produced bundle cannot flip the gate to RESOLVED.
    assessment = R.assess(build(make_all()))
    assert assessment.evidence_status == "ALL_EVIDENCE_PASS"
    assert assessment.gate_status == "OPEN"
    assert assessment.resolved is False
