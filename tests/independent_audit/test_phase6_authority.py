from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from investment_tracker.independent_audit.phase6 import opend_qfq
from investment_tracker.independent_audit.phase6.access_logs import scan_access_logs
from investment_tracker.independent_audit.phase6.authority import (
    CONTRACT_SHA256,
    LOCKED_SYMBOLS,
    VirginHoldoutAttestation,
    load_acquisition_authorization,
    load_frozen_contract,
)
from investment_tracker.independent_audit.phase6.release import (
    issue_acquisition_authorization,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/phase6/phase6-evaluation-contract.json"


def _attestation(path: Path) -> Path:
    value = VirginHoldoutAttestation(
        schema_version="PHASE6-VIRGIN-HOLDOUT-ATTESTATION-v1",
        authority="INDEPENDENT_AUDIT",
        status="INDEPENDENTLY_VERIFIED_NO_PRIOR_LOCKED_SYMBOL_ACCESS",
        attestation_id="audit-test-attestation",
        locked_symbols=LOCKED_SYMBOLS,
        evidence_kind="PROVIDER_SIDE_QUERY_HISTORY",
        evidence_bundle_sha256="a" * 64,
        coverage_start_utc=datetime(2026, 9, 1, tzinfo=timezone.utc),
        coverage_end_utc=datetime(2026, 9, 20, tzinfo=timezone.utc),
        complete_query_history=True,
        independent_source=True,
        coordinator_self_report_only=False,
        limitations=(),
    )
    path.write_text(
        json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def test_frozen_contract_exact_identity_and_governance():
    contract = load_frozen_contract(CONTRACT)
    assert contract["schema_version"] == "PHASE6-EVALUATION-CONTRACT-v1"
    assert CONTRACT_SHA256 == "f64f31c20172491f6175a176592d463fed36f73ecf2b99542022afa55f50b77e"


def test_access_log_scan_does_not_promote_no_match_into_virgin_attestation(tmp_path: Path):
    log = tmp_path / "OpenD.log"
    log.write_text("ordinary quote request\n", encoding="utf-8")
    output = tmp_path / "evidence.json"
    scan_access_logs(
        (log,),
        source_description="test OpenD log",
        coverage_start_utc=datetime(2026, 9, 1, tzinfo=timezone.utc),
        coverage_end_utc=datetime(2026, 9, 20, tzinfo=timezone.utc),
        output_path=output,
    )
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["status"] == "NO_LOCKED_SYMBOL_REFERENCE_FOUND_IN_SUPPLIED_LOGS"
    assert evidence["matches"] == []
    assert evidence["schema_version"] != "PHASE6-VIRGIN-HOLDOUT-ATTESTATION-v1"


def test_access_log_scan_records_locked_symbol_reference_without_line_content(tmp_path: Path):
    log = tmp_path / "OpenD.log"
    log.write_text("request US.HACK daily\n", encoding="utf-8")
    output = tmp_path / "evidence.json"
    scan_access_logs(
        (log,),
        source_description="test OpenD log",
        coverage_start_utc=datetime(2026, 9, 1, tzinfo=timezone.utc),
        coverage_end_utc=datetime(2026, 9, 20, tzinfo=timezone.utc),
        output_path=output,
    )
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["status"] == "LOCKED_SYMBOL_REFERENCE_FOUND"
    assert evidence["matches"][0]["symbol"] == "HACK"
    assert "line" not in evidence["matches"][0]


def test_authorization_binds_contract_attestation_and_ci(tmp_path: Path):
    attestation = _attestation(tmp_path / "attestation.json")
    output = tmp_path / "authorization.json"
    issue_acquisition_authorization(
        contract_path=CONTRACT,
        attestation_path=attestation,
        ci_head_sha="b" * 40,
        ci_run_id=12345,
        output_path=output,
    )
    authorization = load_acquisition_authorization(
        output,
        contract_path=CONTRACT,
        attestation_path=attestation,
    )
    assert authorization.status == "FINAL_HOLDOUT_ACQUISITION_AUTHORIZED"
    assert authorization.holdout_performance_inspected is False


def test_invalid_authorization_stops_before_moomoo_sdk_load(monkeypatch, tmp_path: Path):
    attestation = _attestation(tmp_path / "attestation.json")
    authorization = tmp_path / "authorization.json"
    authorization.write_text("{}", encoding="utf-8")
    called = False

    def forbidden():
        nonlocal called
        called = True
        raise AssertionError("provider SDK must not load before authorization")

    monkeypatch.setattr(opend_qfq, "_load_sdk", forbidden)
    with pytest.raises(Exception):
        opend_qfq.acquire_and_seal(
            repository_root=ROOT,
            contract_path=CONTRACT,
            attestation_path=attestation,
            authorization_path=authorization,
            private_output_dir=tmp_path / "private",
        )
    assert called is False
