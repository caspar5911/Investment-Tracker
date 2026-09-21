"""RECON-009 Generation-2 runtime proof harness.

Implements the *evidence collection and verification* side of the RECON-009
runtime resolution contract
(``2026-09-22-recon009-runtime-resolution-contract.md``).

The five required evidence classes are:

1. ``SUCCESSFUL_ALERT_DELIVERY``
2. ``ACKNOWLEDGEMENT``
3. ``FAILED_DELIVERY_RETRY_OR_ESCALATION``
4. ``INTERRUPTED_WRITE_RECOVERY``
5. ``POST_WRITE_READBACK_VERIFICATION``

A proof run collects one (possibly missing) record per class, aggregates them
into an **immutable, content-addressed** bundle, and verifies whether all five
classes pass in one auditable generation.

**The gate stays OPEN.** Per the frozen governance record
(``data/governance/recon009-status.json``), ``code_only_resolution_allowed`` is
``False``: code, unit tests, or a synthetic bundle — even a complete,
hash-addressed one that passes all five classes — do *not* resolve RECON-009.
Resolution requires a real controlled paper-only runtime exercise plus an
explicit operator governance decision. This module therefore reports
``gate_status == "OPEN"`` unconditionally and ``resolved == False``.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RECON009_SCHEMA = "RECON-009-RUNTIME-PROOF-v1"

__all__ = [
    "RECON009_SCHEMA",
    "RECON009_REQUIRED_EVIDENCE",
    "Acknowledgement",
    "FailedDeliveryRetryOrEscalation",
    "InterruptedWriteRecovery",
    "PostWriteReadbackVerification",
    "Recon009Assessment",
    "Recon009ProofBundle",
    "SuccessfulAlertDelivery",
    "assess",
    "build_bundle",
]

CommitSha = re.compile(r"^[0-9a-f]{40}$")
Classification = Literal["SUCCESS", "FAILURE", "ABSTAIN"]

RECON009_REQUIRED_EVIDENCE: tuple[str, ...] = (
    "SUCCESSFUL_ALERT_DELIVERY",
    "ACKNOWLEDGEMENT",
    "FAILED_DELIVERY_RETRY_OR_ESCALATION",
    "INTERRUPTED_WRITE_RECOVERY",
    "POST_WRITE_READBACK_VERIFICATION",
)


class _EvidenceEnvelope(BaseModel):
    """Shared fail-closed envelope for every RECON-009 evidence record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    commit_sha: str = Field(min_length=40, max_length=40)
    recorded_utc: str = Field(min_length=1)
    input_identity: str = Field(min_length=1)
    output_identity: str = Field(min_length=1)
    classification: Classification

    @model_validator(mode="after")
    def _validate_commit_sha(self) -> "_EvidenceEnvelope":
        if not CommitSha.match(self.commit_sha):
            raise ValueError("RECON009_COMMIT_SHA_INVALID")
        return self

    def evidence_class(self) -> str:
        raise NotImplementedError


class SuccessfulAlertDelivery(_EvidenceEnvelope):
    alert_identity: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    delivery_receipt: str = Field(min_length=1)

    def evidence_class(self) -> str:
        return "SUCCESSFUL_ALERT_DELIVERY"

    def is_passing(self) -> bool:
        return self.classification == "SUCCESS" and bool(self.delivery_receipt)


class Acknowledgement(_EvidenceEnvelope):
    alert_identity: str = Field(min_length=1)
    acknowledgement_identity: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    acknowledgement_utc: str = Field(min_length=1)

    def evidence_class(self) -> str:
        return "ACKNOWLEDGEMENT"

    def is_passing(self, *, linked_alert_id: str | None = None) -> bool:
        if self.classification != "SUCCESS":
            return False
        if linked_alert_id is not None and self.alert_identity != linked_alert_id:
            return False
        return True


class FailedDeliveryRetryOrEscalation(_EvidenceEnvelope):
    alert_identity: str = Field(min_length=1)
    attempt_count: int = Field(ge=0)
    retry_executed: bool
    escalation_executed: bool
    terminal_outcome: str = Field(min_length=1)
    lineage: tuple[str, ...]

    def evidence_class(self) -> str:
        return "FAILED_DELIVERY_RETRY_OR_ESCALATION"

    def is_passing(self) -> bool:
        # A recorded retry/escalation lineage: at least one attempt, and the
        # terminal outcome is captured. Retries that eventually succeed or
        # escalate both prove the retry/escalation machinery executed.
        return self.classification == "SUCCESS" and self.attempt_count >= 1


class InterruptedWriteRecovery(_EvidenceEnvelope):
    write_identity: str = Field(min_length=1)
    interrupted: bool
    recovered: bool
    duplicate_records: int = Field(ge=0)
    lost_records: int = Field(ge=0)

    def evidence_class(self) -> str:
        return "INTERRUPTED_WRITE_RECOVERY"

    def is_passing(self) -> bool:
        return (
            self.classification == "SUCCESS"
            and self.interrupted
            and self.recovered
            and self.duplicate_records == 0
            and self.lost_records == 0
        )


class PostWriteReadbackVerification(_EvidenceEnvelope):
    write_identity: str = Field(min_length=1)
    intended_sha256: str = Field(min_length=1)
    readback_sha256: str = Field(min_length=1)

    @model_validator(mode="after")
    def _readback_must_match(self) -> "PostWriteReadbackVerification":
        # A mismatch must surface as FAILURE/ABSTAIN, never as SUCCESS. The
        # harness refuses to record a passing readback whose hashes disagree.
        if self.intended_sha256 != self.readback_sha256:
            if self.classification == "SUCCESS":
                raise ValueError("RECON009_READBACK_MISMATCH_MUST_NOT_SUCCEED")
        return self

    def is_passing(self) -> bool:
        return self.classification == "SUCCESS" and self.intended_sha256 == self.readback_sha256


EvidenceRecord = (
    SuccessfulAlertDelivery
    | Acknowledgement
    | FailedDeliveryRetryOrEscalation
    | InterruptedWriteRecovery
    | PostWriteReadbackVerification
)


class Recon009ProofBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[RECON009_SCHEMA]
    run_id: str
    commit_sha: str
    delivery: SuccessfulAlertDelivery | None
    acknowledgement: Acknowledgement | None
    failed_delivery: FailedDeliveryRetryOrEscalation | None
    interrupted_write: InterruptedWriteRecovery | None
    readback: PostWriteReadbackVerification | None
    bundle_sha256: str
    # A harness-produced bundle is, by construction, code-only evidence: it can
    # never itself flip the gate to RESOLVED.
    code_only: bool = True

    @property
    def records(self) -> tuple[EvidenceRecord | None, ...]:
        return (
            self.delivery,
            self.acknowledgement,
            self.failed_delivery,
            self.interrupted_write,
            self.readback,
        )


def _bundle_evidence_payload(bundle: Recon009ProofBundle) -> dict:
    return {
        "run_id": bundle.run_id,
        "commit_sha": bundle.commit_sha,
        "delivery": bundle.delivery.model_dump() if bundle.delivery else None,
        "acknowledgement": bundle.acknowledgement.model_dump() if bundle.acknowledgement else None,
        "failed_delivery": bundle.failed_delivery.model_dump() if bundle.failed_delivery else None,
        "interrupted_write": bundle.interrupted_write.model_dump() if bundle.interrupted_write else None,
        "readback": bundle.readback.model_dump() if bundle.readback else None,
    }


def build_bundle(
    *,
    delivery: SuccessfulAlertDelivery | None,
    acknowledgement: Acknowledgement | None,
    failed_delivery: FailedDeliveryRetryOrEscalation | None,
    interrupted_write: InterruptedWriteRecovery | None,
    readback: PostWriteReadbackVerification | None,
) -> Recon009ProofBundle:
    """Aggregate the five evidence records into an immutable hash bundle."""
    present = [
        record
        for record in (delivery, acknowledgement, failed_delivery, interrupted_write, readback)
        if record is not None
    ]
    if present:
        run_id = present[0].run_id
        commit_sha = present[0].commit_sha
    else:
        # No evidence at all: use a canonical placeholder identity so the
        # bundle is still hash-addressable and the gate reports INCOMPLETE.
        run_id = ""
        commit_sha = ""
    provisional = Recon009ProofBundle(
        schema_version=RECON009_SCHEMA,
        run_id=run_id,
        commit_sha=commit_sha,
        delivery=delivery,
        acknowledgement=acknowledgement,
        failed_delivery=failed_delivery,
        interrupted_write=interrupted_write,
        readback=readback,
        bundle_sha256="",
    )
    payload = json.dumps(
        _bundle_evidence_payload(provisional),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return provisional.model_copy(update={"bundle_sha256": digest})


class Recon009Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_status: Literal["ALL_EVIDENCE_PASS", "INCOMPLETE"]
    incomplete_classes: tuple[str, ...]
    consistent_run_id: bool
    consistent_commit_sha: bool
    # Frozen: the gate always stays OPEN. See module docstring.
    gate_status: Literal["OPEN"]
    resolved: bool
    resolution_requires_operator_governance: bool
    bundle_sha256: str


def assess(bundle: Recon009ProofBundle) -> Recon009Assessment:
    """Verify all five evidence classes in one auditable generation.

    Even when every class passes, the gate remains ``OPEN``: RECON-009 is an
    operational-runtime gate that code or a synthetic bundle cannot close.
    """
    run_ids = {record.run_id for record in bundle.records if record is not None}
    commit_shas = {record.commit_sha for record in bundle.records if record is not None}
    consistent_run_id = len(run_ids) <= 1
    consistent_commit_sha = len(commit_shas) <= 1

    delivery = bundle.delivery
    incomplete: list[str] = []

    if delivery is None or not delivery.is_passing():
        incomplete.append("SUCCESSFUL_ALERT_DELIVERY")
    if bundle.acknowledgement is None or not bundle.acknowledgement.is_passing(
        linked_alert_id=delivery.alert_identity if delivery else None
    ):
        incomplete.append("ACKNOWLEDGEMENT")
    if bundle.failed_delivery is None or not bundle.failed_delivery.is_passing():
        incomplete.append("FAILED_DELIVERY_RETRY_OR_ESCALATION")
    if bundle.interrupted_write is None or not bundle.interrupted_write.is_passing():
        incomplete.append("INTERRUPTED_WRITE_RECOVERY")
    if bundle.readback is None or not bundle.readback.is_passing():
        incomplete.append("POST_WRITE_READBACK_VERIFICATION")

    all_pass = not incomplete and consistent_run_id and consistent_commit_sha
    return Recon009Assessment(
        evidence_status="ALL_EVIDENCE_PASS" if all_pass else "INCOMPLETE",
        incomplete_classes=tuple(incomplete),
        consistent_run_id=consistent_run_id,
        consistent_commit_sha=consistent_commit_sha,
        gate_status="OPEN",
        resolved=False,
        resolution_requires_operator_governance=True,
        bundle_sha256=bundle.bundle_sha256,
    )
