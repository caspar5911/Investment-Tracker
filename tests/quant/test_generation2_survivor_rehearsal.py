"""Tests for the generation-2 survivor-bound synthetic Phase-6 rehearsal (C7).

C7 re-runs the EXACT frozen survivor through the full one-time irreversible
Phase-6 rehearsal pipeline (B2 infrastructure) on fully synthetic data and
drives the same machinery through the fail-closed fault suite (B3), then
seals the result as a new self-verifying, content-addressed artifact that
chains the sealed VALIDATION report, the survivor-freeze artifact, and the
survivor's evaluation contract.

No real symbol, real holdout data, real provider, or network call is used.
The evaluation contract (AES-256-GCM AAD) binds the sealed synthetic bundle
to the frozen survivor's grid record, so the rehearsal cannot be silently
re-pointed at a different candidate.
"""

from __future__ import annotations

import hashlib
import json
import math
import pathlib

import pandas as pd
import pytest

from investment_tracker.quant.generation2 import campaign, survivor_freeze, validation
from investment_tracker.quant.generation2.campaign import CampaignError, canonical_bytes, content_sha256
from investment_tracker.quant.generation2.grid import (
    RESEARCH_SYMBOLS,
    GridCandidate,
    canonical_grid_manifest,
)
from investment_tracker.quant.generation2.rehearsal import RehearsalError
from investment_tracker.quant.generation2.survivor_rehearsal import (
    SURVIVOR_REHEARSAL_PASSED,
    SURVIVOR_REHEARSAL_REPORT_NAME,
    SYNTHETIC_SESSIONS,
    build_survivor_evaluation_contract,
    run_fault_suite,
    run_survivor_rehearsal,
    seal_survivor_rehearsal_report,
    survivor_evaluation_contract_sha256,
    synthetic_survivor_bundle,
    verify_survivor_rehearsal_report,
)

FROZEN_ENTRIES = canonical_grid_manifest()["candidates"]
SURVIVOR = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
FRICTION = (0, 3, 25)

COMMITTED = (
    validation._repo_root()
    / "data"
    / "governance"
    / "generation2-campaign"
    / SURVIVOR_REHEARSAL_REPORT_NAME
)


def _candidate(candidate_id: str) -> GridCandidate:
    for entry in FROZEN_ENTRIES:
        if entry["candidate_id"] == candidate_id:
            data = dict(entry)
            data.pop("candidate_id")
            return GridCandidate(candidate_id=candidate_id, **data)
    raise LookupError(candidate_id)


def _bars(n: int = 2300) -> dict[str, pd.DataFrame]:
    """Deterministic drift-dominant bars (same shape as the C4/C6 tests)."""
    index = pd.bdate_range("2014-01-01", periods=n, tz="UTC")
    bars: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(RESEARCH_SYMBOLS):
        values = [
            100.0 + 0.15 * i + 0.1 * offset + 4.0 * math.sin(i / 20.0)
            for i in range(n)
        ]
        bars[symbol] = pd.DataFrame({"open": values, "close": values}, index=index)
    return bars


def _sealed_campaign(evidence_root: pathlib.Path) -> dict:
    """Seal a single-candidate TRAIN + VALIDATION chain with the survivor.

    A one-candidate shortlist guarantees the survivor is exactly ``SURVIVOR``.
    """
    bars = _bars()
    evidence = campaign.run_train_campaign(
        bars,
        (_candidate(SURVIVOR),),
        friction_cases=FRICTION,
    )
    campaign.seal_train_campaign(evidence, evidence_root, friction_cases=FRICTION)
    train_payload = campaign.verify_train_report(evidence_root / campaign.REPORT_NAME)
    result = validation.run_validation_campaign(train_payload, bars, FRICTION)
    assert result["survivor"] == SURVIVOR
    validation.seal_validation_report(result, evidence_root, friction_cases=FRICTION)
    return result


def _no_survivor_validation_report(evidence_root: pathlib.Path) -> None:
    """Write a verified NO_CREDIBLE VALIDATION report (all candidates failing)."""
    result = _sealed_campaign(evidence_root)
    # Rebuild the payload with every candidate forced to fail: the frozen
    # selection rule must then yield no survivor and the no-credible status.
    records = []
    for record in result["candidates"].values():
        record = dict(record)
        record["pass"] = False
        record["pass_reasons"] = ["VALIDATION_NO_CREDIBLE_FORCED"]
        records.append(record)
    payload = {
        "schema_version": validation.VALIDATION_SCHEMA,
        "status": validation.STATUS_NO_CREDIBLE,
        "grid_manifest_sha256": validation.grid_manifest_sha256(),
        "train_report_sha256": result["train_report_sha256"],
        "friction_cases_bps": [int(bps) for bps in FRICTION],
        "shortlist": list(result["shortlist"]),
        "survivor": None,
        "survivor_selection_order": list(validation.SURVIVOR_SELECTION_ORDER),
        "candidates": records,
    }
    payload["report_sha256"] = content_sha256(payload)
    (evidence_root / validation.REPORT_NAME).unlink()
    (evidence_root / validation.REPORT_NAME).write_bytes(canonical_bytes(payload))


# ---------------------------------------------------------------------------
# Evaluation contract
# ---------------------------------------------------------------------------


def test_evaluation_contract_binds_frozen_survivor() -> None:
    contract = build_survivor_evaluation_contract(SURVIVOR)
    assert contract["survivor"] == SURVIVOR
    assert contract["candidate"] == _candidate(SURVIVOR).to_manifest_dict()
    sha = survivor_evaluation_contract_sha256(SURVIVOR)
    assert sha == content_sha256(contract)
    assert len(sha) == 64


def test_evaluation_contract_rejects_unknown_survivor() -> None:
    with pytest.raises(CampaignError):
        build_survivor_evaluation_contract("G2-Z|lookback=1|skip=0|top_k=1|rebalance=21")


def test_synthetic_survivor_bundle_is_deterministic_and_covers_research_symbols() -> None:
    b1 = synthetic_survivor_bundle()
    b2 = synthetic_survivor_bundle()
    assert b1.sha256() == b2.sha256()
    assert set(b1.symbols) == set(RESEARCH_SYMBOLS)
    assert b1.sessions == SYNTHETIC_SESSIONS


# ---------------------------------------------------------------------------
# Fault suite
# ---------------------------------------------------------------------------


def test_run_fault_suite_fails_closed(tmp_path: object) -> None:
    faults = run_fault_suite(pathlib.Path(tmp_path) / "faults")
    assert len(faults) >= 8
    for record in faults:
        assert record["passed"] is True
        assert record["observed_code"] == record["expected_code"]
        assert len(record["observed_code"]) > 0


def test_check_fault_deviation_raises(tmp_path: object) -> None:
    from investment_tracker.quant.generation2.survivor_rehearsal import check_fault

    def _trigger() -> None:
        raise RehearsalError("REHEARSAL_OHLC_NAN", "injected")

    with pytest.raises(CampaignError) as excinfo:
        check_fault("deliberate-deviation", "REHEARSAL_EXPECTED_CODE", _trigger)
    assert excinfo.value.code == "SURVIVOR_REHEARSAL_FAULT_DEVIATION"


# ---------------------------------------------------------------------------
# End-to-end orchestrator
# ---------------------------------------------------------------------------


def test_survivor_rehearsal_end_to_end_seals_and_verifies(tmp_path: object) -> None:
    evidence_root = pathlib.Path(tmp_path) / "evidence"
    _sealed_campaign(evidence_root)
    survivor_freeze.seal_survivor_freeze(
        survivor_freeze.build_survivor_freeze(
            validation.verify_validation_report(evidence_root / validation.REPORT_NAME),
            campaign.verify_train_report(evidence_root / campaign.REPORT_NAME),
        ),
        evidence_root,
    )

    sealed = run_survivor_rehearsal(evidence_root)
    assert sealed["status"] == SURVIVOR_REHEARSAL_PASSED
    assert sealed["survivor"] == SURVIVOR
    assert len(sealed["transcript_sha256"]) == 64
    assert len(sealed["sealed_bundle_sha256"]) == 64
    assert sealed["evaluation_contract_sha256"] == survivor_evaluation_contract_sha256(SURVIVOR)
    assert all(record["passed"] for record in sealed["fault_suite"])
    verify_survivor_rehearsal_report(evidence_root / SURVIVOR_REHEARSAL_REPORT_NAME)

    # One-time rehearsal: the exclusive seal refuses a second run.
    with pytest.raises(CampaignError) as excinfo:
        run_survivor_rehearsal(evidence_root)
    assert excinfo.value.code in (
        "REHEARSAL_ACQUISITION_STARTED_ONCE",
        "SURVIVOR_REHEARSAL_EXISTS",
    )


def test_duplicate_seal_refused(tmp_path: object) -> None:
    payload = {"schema_version": "x", "status": "y"}
    root = pathlib.Path(tmp_path) / "rep"
    sealed = seal_survivor_rehearsal_report(payload, root)
    assert "report_sha256" in sealed
    with pytest.raises(CampaignError) as excinfo:
        seal_survivor_rehearsal_report(payload, root)
    assert excinfo.value.code == "SURVIVOR_REHEARSAL_EXISTS"


def test_rehearsal_refused_when_no_survivor(tmp_path: object) -> None:
    evidence_root = pathlib.Path(tmp_path) / "evidence"
    _no_survivor_validation_report(evidence_root)
    with pytest.raises(CampaignError) as excinfo:
        run_survivor_rehearsal(evidence_root)
    assert excinfo.value.code == "SURVIVOR_REHEARSAL_NO_SURVIVOR"


# ---------------------------------------------------------------------------
# Verify: tamper detection
# ---------------------------------------------------------------------------


def _sealed_payload(tmp_path: object) -> tuple[dict, pathlib.Path]:
    evidence_root = pathlib.Path(tmp_path) / "evidence"
    _sealed_campaign(evidence_root)
    sealed = run_survivor_rehearsal(evidence_root)
    return sealed, evidence_root / SURVIVOR_REHEARSAL_REPORT_NAME


def test_verify_detects_tampered_survivor(tmp_path: object) -> None:
    _, report = _sealed_payload(tmp_path)
    tampered = json.loads(report.read_text(encoding="utf-8"))
    tampered["survivor"] = "G2-A|lookback=63|skip=0|top_k=1|rebalance=21"
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_survivor_rehearsal_report(report)
    assert excinfo.value.code == "SURVIVOR_REHEARSAL_TAMPERED"


def test_verify_detects_tampered_fault_result(tmp_path: object) -> None:
    _, report = _sealed_payload(tmp_path)
    tampered = json.loads(report.read_text(encoding="utf-8"))
    tampered["fault_suite"][0]["observed_code"] = "REHEARSAL_SOMETHING_ELSE"
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_survivor_rehearsal_report(report)
    assert excinfo.value.code == "SURVIVOR_REHEARSAL_TAMPERED"


def test_verify_detects_tampered_status(tmp_path: object) -> None:
    _, report = _sealed_payload(tmp_path)
    tampered = json.loads(report.read_text(encoding="utf-8"))
    tampered["status"] = "SOMETHING_ELSE"
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_survivor_rehearsal_report(report)
    assert excinfo.value.code == "SURVIVOR_REHEARSAL_TAMPERED"


# ---------------------------------------------------------------------------
# Committed artifact
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not COMMITTED.exists(),
    reason="committed survivor-rehearsal artifact not present yet",
)
def test_verify_committed_survivor_rehearsal() -> None:
    payload = verify_survivor_rehearsal_report(COMMITTED)
    assert payload["status"] == SURVIVOR_REHEARSAL_PASSED
    root = COMMITTED.parent
    validation_payload = validation.verify_validation_report(
        root / validation.REPORT_NAME
    )
    assert payload["survivor"] == validation_payload["survivor"]
    assert payload["validation_report_sha256"] == validation_payload["report_sha256"]
    assert payload["survivor_freeze_sha256"] == survivor_freeze.verify_survivor_freeze(
        root / survivor_freeze.FREEZE_REPORT_NAME
    )["report_sha256"]
