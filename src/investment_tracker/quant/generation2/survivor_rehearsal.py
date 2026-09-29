"""Generation-2 survivor-bound synthetic Phase-6 rehearsal (C7).

Re-runs the EXACT frozen survivor through the full one-time irreversible
Phase-6 rehearsal pipeline (the B2 infrastructure in ``rehearsal``) on fully
synthetic data, and drives the same machinery through the fail-closed fault
suite (B3). The result is sealed as a new self-verifying,
content-addressed artifact that chains the sealed VALIDATION report, the
survivor-freeze artifact, and the survivor's evaluation contract.

Governance invariants enforced here (fail-closed):

- the rehearsal consumes synthetic data only: no real symbol, real holdout
  data, real provider, or network call is ever made;
- the evaluation contract (the AES-256-GCM AAD) is the content hash of the
  frozen survivor's grid record, so the sealed synthetic bundle is bound to
  exactly that candidate and cannot be re-pointed at a different one;
- the fault suite re-drives every B3 failure mode and records the observed
  stable code; any deviation from the expected code is
  ``SURVIVOR_REHEARSAL_FAULT_DEVIATION`` and is never sealed;
- a sealed VALIDATION report without a survivor refuses to rehearse
  (``SURVIVOR_REHEARSAL_NO_SURVIVOR``);
- the report is written exclusively (``SURVIVOR_REHEARSAL_EXISTS``) and
  verification recomputes the content hash, the survivor's frozen binding,
  the evaluation-contract hash, and the whole fault suite
  (``SURVIVOR_REHEARSAL_TAMPERED`` on any divergence).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Callable

from investment_tracker.quant.generation2.campaign import (
    CampaignError,
    assert_frozen_candidate,
    canonical_bytes,
    content_sha256,
)
from investment_tracker.quant.generation2.grid import RESEARCH_SYMBOLS
from investment_tracker.quant.generation2.rehearsal import (
    AcquiredBundle,
    RehearsalError,
    SyntheticAcquisitionProvider,
    build_sealed_bundle,
    create_release,
    create_seal_receipt,
    consume_rehearsal,
    open_bundle,
    readback_verify,
    run_synthetic_rehearsal,
    write_canonical_file,
    write_sealed_bundle,
)
from investment_tracker.quant.generation2.reproduction import default_environment
from investment_tracker.quant.generation2.survivor_freeze import (
    FREEZE_REPORT_NAME,
    verify_survivor_freeze,
)
from investment_tracker.quant.generation2.validation import (
    REPORT_NAME as VALIDATION_REPORT_NAME,
    frozen_candidate_by_id,
    verify_validation_report,
)

SURVIVOR_REHEARSAL_SCHEMA = "GENERATION2-SURVIVOR-REHEARSAL-v1"
SURVIVOR_REHEARSAL_PASSED = "SURVIVOR_SYNTHETIC_PHASE6_REHEARSAL_PASSED"
SURVIVOR_REHEARSAL_REPORT_NAME = "survivor-rehearsal-report.json"
SURVIVOR_REHEARSAL_NO_SURVIVOR = "SURVIVOR_REHEARSAL_NO_SURVIVOR"
SURVIVOR_REHEARSAL_EXISTS = "SURVIVOR_REHEARSAL_EXISTS"
SURVIVOR_REHEARSAL_TAMPERED = "SURVIVOR_REHEARSAL_TAMPERED"
SURVIVOR_REHEARSAL_FAULT_DEVIATION = "SURVIVOR_REHEARSAL_FAULT_DEVIATION"

EVALUATION_CONTRACT_SCHEMA = "GENERATION2-SURVIVOR-EVALUATION-CONTRACT-v1"

# Synthetic, fixed identifiers: the rehearsal is one-time by construction and
# the fixed values keep the sealed artifact reproducible and auditable.
SYNTHETIC_HOLDOUT_ID = "G2-SYNTHETIC-SURVIVOR-REHEARSAL"
SYNTHETIC_AUTHORIZATION_ID = "G2-SYNTHETIC-SURVIVOR-AUTH-1"
SYNTHETIC_RELEASE_ID = "G2-SYNTHETIC-SURVIVOR-REL-1"
SYNTHETIC_UTC = "2026-09-22T00:00:00Z"
SYNTHETIC_ADJUSTMENT = "QFQ"
SYNTHETIC_SESSIONS = (
    "2023-01-02",
    "2023-01-03",
    "2023-01-04",
    "2023-01-05",
    "2023-01-06",
)
SYNTHETIC_KEY = hashlib.sha256(b"g2-synthetic-survivor-rehearsal-key").digest()
# The fault suite is a separate rehearsal pass; its contract AAD is a fixed
# synthetic identity, deliberately NOT bound to the survivor.
FAULT_SUITE_CONTRACT_SHA256 = hashlib.sha256(
    b"g2-synthetic-fault-suite-contract"
).hexdigest()

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

__all__ = [
    "EVALUATION_CONTRACT_SCHEMA",
    "FAULT_SUITE_CONTRACT_SHA256",
    "SYNTHETIC_SESSIONS",
    "SURVIVOR_REHEARSAL_PASSED",
    "SURVIVOR_REHEARSAL_REPORT_NAME",
    "SURVIVOR_REHEARSAL_SCHEMA",
    "build_survivor_evaluation_contract",
    "check_fault",
    "run_fault_suite",
    "run_survivor_rehearsal",
    "seal_survivor_rehearsal_report",
    "survivor_evaluation_contract_sha256",
    "synthetic_survivor_bundle",
    "verify_survivor_rehearsal_report",
    "main",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def synthetic_survivor_bundle() -> AcquiredBundle:
    """Deterministic synthetic acquisition bundle over the research symbols."""
    bars: dict[str, dict[str, dict[str, float]]] = {}
    for offset, symbol in enumerate(RESEARCH_SYMBOLS):
        per_symbol: dict[str, dict[str, float]] = {}
        for index, session in enumerate(SYNTHETIC_SESSIONS):
            value = 100.0 + 0.25 * index + 0.01 * offset
            per_symbol[session] = {"open": value, "close": value + 0.1}
        bars[symbol] = per_symbol
    return AcquiredBundle(
        symbols=RESEARCH_SYMBOLS,
        sessions=SYNTHETIC_SESSIONS,
        bars=bars,
        adjustment_convention=SYNTHETIC_ADJUSTMENT,
    )


def build_survivor_evaluation_contract(survivor_id: str) -> dict:
    """The evaluation contract binding the rehearsal to the frozen survivor.

    The candidate must bind to the frozen grid (fail-closed); the contract is
    the content-addressed AAD for the encrypted seal, so the sealed bundle
    cannot be opened or produced under a different survivor's identity.
    """
    candidate = frozen_candidate_by_id(survivor_id)
    assert_frozen_candidate(candidate)
    return {
        "schema_version": EVALUATION_CONTRACT_SCHEMA,
        "phase": "PHASE6_SYNTHETIC_REHEARSAL",
        "authority": "SYNTHETIC_REHEARSAL",
        "survivor": candidate.candidate_id,
        "candidate": candidate.to_manifest_dict(),
    }


def survivor_evaluation_contract_sha256(survivor_id: str) -> str:
    return content_sha256(build_survivor_evaluation_contract(survivor_id))


# ---------------------------------------------------------------------------
# Fault suite (B3 re-drive, survivor-rehearsal scoped)
# ---------------------------------------------------------------------------


def check_fault(name: str, expected_code: str, trigger: Callable[[], None]) -> dict:
    """Run one fault trigger and confirm the exact stable fail-closed code.

    A trigger that does not raise, or that raises a different stable code, is
    a rehearsal deviation: fail-closed, never recorded as a pass.
    """
    try:
        trigger()
    except RehearsalError as exc:
        observed = exc.code
    else:
        raise CampaignError(
            SURVIVOR_REHEARSAL_FAULT_DEVIATION,
            f"fault {name} did not fail closed",
        )
    if observed != expected_code:
        raise CampaignError(
            SURVIVOR_REHEARSAL_FAULT_DEVIATION,
            f"fault {name}: expected {expected_code}, observed {observed}",
        )
    return {
        "fault": name,
        "expected_code": expected_code,
        "observed_code": observed,
        "passed": True,
    }


class _FaultProvider:
    """Fake provider that raises a RehearsalError with a given code."""

    def __init__(self, code: str) -> None:
        self.code = code

    def acquire(self, _authorization) -> AcquiredBundle:
        raise RehearsalError(self.code, "fault injection")


class _CrashProvider:
    """Fake provider that raises an unexpected, non-RehearsalError error."""

    def acquire(self, _authorization) -> AcquiredBundle:
        raise RuntimeError("boom: synthetic provider crash")


def _fault_rehearsal(
    provider,
    directory: Path,
    *,
    expected_sha256: str,
    authorization_id: str,
    release_id: str,
) -> None:
    run_synthetic_rehearsal(
        provider,
        marker_dir=directory / "markers",
        sealed_dir=directory / "sealed",
        key=SYNTHETIC_KEY,
        holdout_id=SYNTHETIC_HOLDOUT_ID,
        authorization_id=authorization_id,
        release_id=release_id,
        expected_bundle_sha256=expected_sha256,
        expected_sessions=SYNTHETIC_SESSIONS,
        adjustment_convention=SYNTHETIC_ADJUSTMENT,
        evaluation_contract_sha256=FAULT_SUITE_CONTRACT_SHA256,
        now_utc=SYNTHETIC_UTC,
    )


def run_fault_suite(root: Path | str) -> list[dict]:
    """Re-drive every B3 failure mode; record each observed stable code.

    Any deviation from the expected stable code raises
    ``SURVIVOR_REHEARSAL_FAULT_DEVIATION`` (fail-closed, never sealable).
    """
    root = Path(root)
    bundle = synthetic_survivor_bundle()
    expected_sha = bundle.sha256()
    good_provider = SyntheticAcquisitionProvider(bundle)
    records: list[dict] = []

    def _provider_connect_failure() -> None:
        _fault_rehearsal(
            _FaultProvider("REHEARSAL_PROVIDER_CONNECT_FAILED"),
            root / "01",
            expected_sha256=expected_sha,
            authorization_id="AUTH-1",
            release_id="REL-1",
        )

    records.append(
        check_fault(
            "provider_connect_failure",
            "REHEARSAL_PROVIDER_CONNECT_FAILED",
            _provider_connect_failure,
        )
    )

    def _provider_unexpected_crash() -> None:
        _fault_rehearsal(
            _CrashProvider(),
            root / "02",
            expected_sha256=expected_sha,
            authorization_id="AUTH-2",
            release_id="REL-2",
        )

    records.append(
        check_fault(
            "provider_unexpected_crash",
            "REHEARSAL_ACQUISITION_INTERRUPTED",
            _provider_unexpected_crash,
        )
    )

    def _virginity_hash_mismatch() -> None:
        _fault_rehearsal(
            good_provider,
            root / "03",
            expected_sha256="f" * 64,
            authorization_id="AUTH-3",
            release_id="REL-3",
        )

    records.append(
        check_fault(
            "virginity_hash_mismatch",
            "REHEARSAL_VIRGINITY_HASH_MISMATCH",
            _virginity_hash_mismatch,
        )
    )

    sealed = build_sealed_bundle(
        bundle,
        key=SYNTHETIC_KEY,
        evaluation_contract_sha256=FAULT_SUITE_CONTRACT_SHA256,
    )
    wrong_key = hashlib.sha256(b"g2-fault-suite-wrong-key").digest()

    def _corrupt_sealed_bundle() -> None:
        corrupt = sealed[:5] + bytes([sealed[5] ^ 0xFF]) + sealed[6:]
        open_bundle(corrupt, key=SYNTHETIC_KEY, aad=FAULT_SUITE_CONTRACT_SHA256)

    records.append(
        check_fault(
            "corrupt_sealed_bundle",
            "REHEARSAL_DECRYPTION_FAILED",
            _corrupt_sealed_bundle,
        )
    )

    records.append(
        check_fault(
            "wrong_key_open",
            "REHEARSAL_DECRYPTION_FAILED",
            lambda: open_bundle(sealed, key=wrong_key, aad=FAULT_SUITE_CONTRACT_SHA256),
        )
    )

    records.append(
        check_fault(
            "evaluation_contract_aad_mismatch",
            "REHEARSAL_DECRYPTION_FAILED",
            lambda: open_bundle(sealed, key=SYNTHETIC_KEY, aad="d" * 64),
        )
    )

    def _authorization_reuse() -> None:
        _fault_rehearsal(
            good_provider,
            root / "07",
            expected_sha256=expected_sha,
            authorization_id="AUTH-7",
            release_id="REL-7",
        )
        # Second run under the same one-time acquisition-start marker.
        _fault_rehearsal(
            good_provider,
            root / "07",
            expected_sha256=expected_sha,
            authorization_id="AUTH-7",
            release_id="REL-7",
        )

    records.append(
        check_fault(
            "authorization_reuse",
            "REHEARSAL_ACQUISITION_STARTED_ONCE",
            _authorization_reuse,
        )
    )

    def _second_evaluation() -> None:
        directory = root / "08"
        sealed_path = directory / "sealed.bin"
        write_sealed_bundle(sealed_path, sealed)
        receipt = create_seal_receipt(
            holdout_id=SYNTHETIC_HOLDOUT_ID,
            sealed_bundle_sha256=hashlib.sha256(sealed).hexdigest(),
            evaluation_contract_sha256=FAULT_SUITE_CONTRACT_SHA256,
            key=SYNTHETIC_KEY,
            sealed_utc=SYNTHETIC_UTC,
        )
        release = create_release(
            release_id="REL-8",
            holdout_id=SYNTHETIC_HOLDOUT_ID,
            evaluation_contract_sha256=FAULT_SUITE_CONTRACT_SHA256,
            sealed_bundle_sha256=hashlib.sha256(sealed).hexdigest(),
            receipt=receipt,
        )

        def _consume() -> None:
            consume_rehearsal(
                release=release,
                receipt=receipt,
                marker_dir=directory / "markers",
                sealed_path=sealed_path,
                key=SYNTHETIC_KEY,
                expected_sessions=SYNTHETIC_SESSIONS,
            )

        _consume()
        _consume()

    records.append(
        check_fault(
            "second_evaluation",
            "REHEARSAL_EVALUATION_ALREADY_CONSUMED",
            _second_evaluation,
        )
    )

    def _seal_receipt_mismatch() -> None:
        receipt = create_seal_receipt(
            holdout_id=SYNTHETIC_HOLDOUT_ID,
            sealed_bundle_sha256="a" * 64,
            evaluation_contract_sha256=FAULT_SUITE_CONTRACT_SHA256,
            key=SYNTHETIC_KEY,
            sealed_utc=SYNTHETIC_UTC,
        )
        create_release(
            release_id="REL-9",
            holdout_id=SYNTHETIC_HOLDOUT_ID,
            evaluation_contract_sha256=FAULT_SUITE_CONTRACT_SHA256,
            sealed_bundle_sha256="b" * 64,
            receipt=receipt,
        )

    records.append(
        check_fault(
            "seal_receipt_mismatch",
            "REHEARSAL_RECEIPT_MISMATCH",
            _seal_receipt_mismatch,
        )
    )

    def _interrupted_canonical_write() -> None:
        write_canonical_file(
            root / "10" / "canon.json", b"payload", expected_sha256="f" * 64
        )

    records.append(
        check_fault(
            "interrupted_canonical_write",
            "REHEARSAL_CANONICAL_WRITE_INTERRUPTED",
            _interrupted_canonical_write,
        )
    )

    def _post_write_readback_mismatch() -> None:
        path = root / "11" / "canon.json"
        write_canonical_file(path, b"payload")
        readback_verify(path, expected_sha256="f" * 64)

    records.append(
        check_fault(
            "post_write_readback_mismatch",
            "REHEARSAL_READBACK_MISMATCH",
            _post_write_readback_mismatch,
        )
    )

    return records


# ---------------------------------------------------------------------------
# Sealed C7 artifact
# ---------------------------------------------------------------------------


def seal_survivor_rehearsal_report(payload: dict, root: Path | str) -> dict:
    """Seal the survivor-rehearsal report exclusively under ``root``."""
    root = Path(root)
    report_path = root / SURVIVOR_REHEARSAL_REPORT_NAME
    if report_path.exists():
        raise CampaignError(
            SURVIVOR_REHEARSAL_EXISTS,
            f"a survivor-rehearsal report already exists at {report_path}",
        )
    sealed = dict(payload)
    sealed["report_sha256"] = content_sha256(sealed)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with report_path.open("xb") as handle:
            handle.write(canonical_bytes(sealed))
    except FileExistsError as exc:
        raise CampaignError(
            SURVIVOR_REHEARSAL_EXISTS,
            f"a survivor-rehearsal report already exists at {report_path}",
        ) from exc
    return sealed


def verify_survivor_rehearsal_report(path: Path | str) -> dict:
    """Verify a sealed survivor-rehearsal report; fail closed on any divergence."""
    payload = json.loads(Path(path).read_bytes().decode("utf-8"))
    claimed = payload.pop("report_sha256", None)
    if claimed is None or content_sha256(payload) != claimed:
        raise CampaignError(
            SURVIVOR_REHEARSAL_TAMPERED,
            f"report content hash does not match {Path(path)}",
        )
    if payload.get("schema_version") != SURVIVOR_REHEARSAL_SCHEMA:
        raise CampaignError(
            SURVIVOR_REHEARSAL_TAMPERED,
            f"schema_version is {payload.get('schema_version')!r}, expected {SURVIVOR_REHEARSAL_SCHEMA!r}",
        )
    if payload.get("status") != SURVIVOR_REHEARSAL_PASSED:
        raise CampaignError(
            SURVIVOR_REHEARSAL_TAMPERED,
            f"status is {payload.get('status')!r}, expected {SURVIVOR_REHEARSAL_PASSED!r}",
        )
    survivor = payload.get("survivor")
    if not isinstance(survivor, str) or not survivor:
        raise CampaignError(
            SURVIVOR_REHEARSAL_TAMPERED, "survivor is missing or not a string"
        )
    try:
        frozen_candidate_by_id(survivor)
    except CampaignError as exc:
        raise CampaignError(
            SURVIVOR_REHEARSAL_TAMPERED,
            f"survivor {survivor!r} is not part of the frozen generation-2 grid",
        ) from exc
    if survivor_evaluation_contract_sha256(survivor) != payload.get(
        "evaluation_contract_sha256"
    ):
        raise CampaignError(
            SURVIVOR_REHEARSAL_TAMPERED,
            "evaluation_contract_sha256 does not match the frozen survivor's contract",
        )
    for key in (
        "validation_report_sha256",
        "authorization_sha256",
        "bundle_sha256",
        "sealed_bundle_sha256",
        "receipt_sha256",
        "transcript_sha256",
    ):
        value = payload.get(key)
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise CampaignError(
                SURVIVOR_REHEARSAL_TAMPERED, f"{key} is not a 64-char sha256"
            )
    freeze_sha = payload.get("survivor_freeze_sha256")
    if freeze_sha is not None and not (
        isinstance(freeze_sha, str) and _SHA256.fullmatch(freeze_sha)
    ):
        raise CampaignError(
            SURVIVOR_REHEARSAL_TAMPERED, "survivor_freeze_sha256 is not a 64-char sha256"
        )
    faults = payload.get("fault_suite")
    if not isinstance(faults, list) or not faults:
        raise CampaignError(
            SURVIVOR_REHEARSAL_TAMPERED, "fault_suite must be a non-empty list"
        )
    for record in faults:
        if not isinstance(record, dict):
            raise CampaignError(
                SURVIVOR_REHEARSAL_TAMPERED, "fault_suite entries must be objects"
            )
        if record.get("passed") is not True:
            raise CampaignError(
                SURVIVOR_REHEARSAL_TAMPERED,
                f"fault {record.get('fault')!r} was not recorded as passed",
            )
        if (
            not isinstance(record.get("fault"), str)
            or not isinstance(record.get("expected_code"), str)
            or not isinstance(record.get("observed_code"), str)
        ):
            raise CampaignError(
                SURVIVOR_REHEARSAL_TAMPERED, "fault_suite entry fields are malformed"
            )
        if record["observed_code"] != record["expected_code"]:
            raise CampaignError(
                SURVIVOR_REHEARSAL_TAMPERED,
                f"fault {record['fault']!r} observed code deviates from expectation",
            )
    environment = payload.get("environment")
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(value, str) and value
        for key, value in environment.items()
    ):
        raise CampaignError(
            SURVIVOR_REHEARSAL_TAMPERED,
            "environment must map names to version strings",
        )
    payload["report_sha256"] = claimed
    return payload


def run_survivor_rehearsal(evidence_root: Path | str, *, now_utc: str = SYNTHETIC_UTC) -> dict:
    """Run the survivor-bound synthetic Phase-6 rehearsal and seal the C7 report.

    Verifies the sealed VALIDATION report (and the survivor-freeze artifact
    when present), re-runs the full rehearsal pipeline with the survivor's
    evaluation contract as the seal AAD, re-drives the fault suite, and seals
    the result under ``evidence_root``.
    """
    evidence_root = Path(evidence_root)
    validation_payload = verify_validation_report(evidence_root / VALIDATION_REPORT_NAME)
    survivor_id = validation_payload.get("survivor")
    if not isinstance(survivor_id, str) or not survivor_id:
        raise CampaignError(
            SURVIVOR_REHEARSAL_NO_SURVIVOR,
            "the sealed VALIDATION report has no survivor to rehearse",
        )
    freeze_path = evidence_root / FREEZE_REPORT_NAME
    survivor_freeze_sha = (
        verify_survivor_freeze(freeze_path)["report_sha256"]
        if freeze_path.exists()
        else None
    )

    work_root = evidence_root / "survivor-rehearsal"
    bundle = synthetic_survivor_bundle()
    evaluation_contract_sha = survivor_evaluation_contract_sha256(survivor_id)
    try:
        transcript = run_synthetic_rehearsal(
            SyntheticAcquisitionProvider(bundle),
            marker_dir=work_root / "markers",
            sealed_dir=work_root / "sealed",
            key=SYNTHETIC_KEY,
            holdout_id=SYNTHETIC_HOLDOUT_ID,
            authorization_id=SYNTHETIC_AUTHORIZATION_ID,
            release_id=SYNTHETIC_RELEASE_ID,
            expected_bundle_sha256=bundle.sha256(),
            expected_sessions=SYNTHETIC_SESSIONS,
            adjustment_convention=SYNTHETIC_ADJUSTMENT,
            evaluation_contract_sha256=evaluation_contract_sha,
            now_utc=now_utc,
        )
        faults = run_fault_suite(work_root / "faults")
    except RehearsalError as exc:
        # The one-time rehearsal markers are exclusive: a re-run is refused by
        # the B2 pipeline (stable code) and surfaced here as a CampaignError
        # so the orchestrator's failure type is uniform and fail-closed.
        raise CampaignError(exc.code, str(exc)) from exc
    payload = {
        "schema_version": SURVIVOR_REHEARSAL_SCHEMA,
        "status": SURVIVOR_REHEARSAL_PASSED,
        "survivor": survivor_id,
        "validation_report_sha256": validation_payload["report_sha256"],
        "survivor_freeze_sha256": survivor_freeze_sha,
        "evaluation_contract_sha256": evaluation_contract_sha,
        "holdout_id": transcript.holdout_id,
        "authorization_sha256": transcript.authorization_sha256,
        "bundle_sha256": transcript.bundle_sha256,
        "sealed_bundle_sha256": transcript.sealed_bundle_sha256,
        "receipt_sha256": transcript.receipt_sha256,
        "transcript_sha256": transcript.transcript_sha256,
        "fault_suite": faults,
        "environment": default_environment(),
    }
    return seal_survivor_rehearsal_report(payload, evidence_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-run the frozen survivor through the synthetic Phase-6 rehearsal and seal the C7 report."
    )
    parser.add_argument(
        "--evidence-root",
        default=str(_repo_root() / "data" / "governance" / "generation2-campaign"),
        help="directory containing the sealed VALIDATION report and receiving the survivor-rehearsal report",
    )
    args = parser.parse_args(argv)
    payload = run_survivor_rehearsal(Path(args.evidence_root))
    print(f"schema_version={payload['schema_version']}")
    print(f"status={payload['status']}")
    print(f"survivor={payload['survivor']}")
    print(f"validation_report_sha256={payload['validation_report_sha256']}")
    print(f"survivor_freeze_sha256={payload['survivor_freeze_sha256']}")
    print(f"evaluation_contract_sha256={payload['evaluation_contract_sha256']}")
    print(f"transcript_sha256={payload['transcript_sha256']}")
    print(f"fault_suite_size={len(payload['fault_suite'])}")
    print(f"report_sha256={payload['report_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
