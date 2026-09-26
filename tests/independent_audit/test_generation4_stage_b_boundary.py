from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

import investment_tracker.independent_audit.successor.acquisition_authority as acquisition_authority_module
from investment_tracker.independent_audit.successor import acquisition as acquisition_module
from investment_tracker.independent_audit.successor.acquisition_authority import (
    SCHEMA as SCHEMA_V1,
    SCHEMA_V2,
    STATUS,
    SuccessorAcquisitionAuthorityError,
    load_acquisition_authorization,
)
from investment_tracker.independent_audit.successor.phase6_contract import (
    verify_phase6_contract,
)
from investment_tracker.independent_audit.post_generation3 import stage_b_cli

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/generation4/phase6/evaluation-contract.json"
SELECTION = ROOT / "data/generation4/preaccess/holdout-selection.json"
ATTESTATION = ROOT / "data/generation4/preaccess/virginity-attestation.json"
EVIDENCE = ROOT / "data/generation4/preaccess/virginity-evidence.json"
TEMPLATE = ROOT / "data/governance/successor/generation4-acquisition-authorization.template.json"

SPLIT_NORMALIZER = ROOT / "src/investment_tracker/quant/successor/corporate_actions_v2.py"
DIVIDEND_RECONCILIATION = ROOT / "src/investment_tracker/quant/successor/dividend_reconciliation_v3.py"
EVALUATOR = ROOT / "src/investment_tracker/independent_audit/successor/evaluate_dividend_v3.py"
PHASE6_VERIFIER = ROOT / "src/investment_tracker/independent_audit/successor/phase6_contract.py"
ACQUISITION_AUTHORITY = ROOT / "src/investment_tracker/independent_audit/successor/acquisition_authority.py"
ACQUISITION = ROOT / "src/investment_tracker/independent_audit/successor/acquisition.py"
RELEASE = ROOT / "src/investment_tracker/independent_audit/successor/release.py"
CLOSURE = ROOT / "src/investment_tracker/independent_audit/successor/closure.py"
VIRGINITY = ROOT / "src/investment_tracker/independent_audit/successor/virginity.py"
STAGE_B_CLI = ROOT / "src/investment_tracker/independent_audit/post_generation3/stage_b_cli.py"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _payload() -> dict:
    contract = _contract()
    return {
        "schema_version": SCHEMA_V2,
        "authority": "INDEPENDENT_AUDIT",
        "status": STATUS,
        "authorization_id": "INDEP-AUDIT-GEN4-ACQUISITION-SYNTHETIC",
        "signed_by": "Synthetic Independent Auditor Fixture",
        "approved_at_utc": "2026-09-23T12:00:00Z",
        "successor_formal_name": "GENERATION_4",
        "candidate_id": contract["strategy"]["candidate_id"],
        "binding_sha256": contract["strategy"]["binding_sha256"],
        "implementation_sha256": contract["strategy"]["implementation_sha256"],
        "split_normalizer_sha256": contract["methodology"]["split_normalizer_sha256"],
        "dividend_reconciliation_sha256": contract["methodology"]["dividend_reconciliation_sha256"],
        "successor_evaluator_sha256": contract["methodology"]["successor_evaluator_sha256"],
        "phase6_verifier_implementation_sha256": _sha(PHASE6_VERIFIER),
        "acquisition_authority_implementation_sha256": _sha(ACQUISITION_AUTHORITY),
        "acquisition_implementation_sha256": _sha(ACQUISITION),
        "release_implementation_sha256": _sha(RELEASE),
        "closure_implementation_sha256": _sha(CLOSURE),
        "virginity_verifier_implementation_sha256": _sha(VIRGINITY),
        "stage_b_cli_implementation_sha256": _sha(STAGE_B_CLI),
        "phase6_contract_sha256": _sha(CONTRACT),
        "selection_sha256": _sha(SELECTION),
        "virginity_attestation_sha256": _sha(ATTESTATION),
        "virginity_evidence_sha256": _sha(EVIDENCE),
        "locked_symbols": contract["final_holdout"]["locked_symbols"],
        "one_time": True,
        "acquisition_start_marker_required_before_provider_read": True,
        "retry_after_historical_access_allowed": False,
        "symbol_substitution_after_access_allowed": False,
        "historical_data_included_in_authorization_artifact": False,
        "holdout_performance_inspected": False,
        "one_time_evaluation_after_verified_release_authorized": True,
        "phase7_authorized": False,
        "production_readiness_approved": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }


def _legacy_v1_payload() -> dict:
    payload = _payload()
    payload["schema_version"] = SCHEMA_V1
    payload["successor_normalizer_sha256"] = payload.pop("split_normalizer_sha256")
    for field in (
        "dividend_reconciliation_sha256",
        "phase6_verifier_implementation_sha256",
        "acquisition_authority_implementation_sha256",
        "closure_implementation_sha256",
        "virginity_verifier_implementation_sha256",
        "stage_b_cli_implementation_sha256",
    ):
        payload.pop(field)
    return payload


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _load(path: Path):
    return load_acquisition_authorization(
        authorization_path=path,
        phase6_contract_path=CONTRACT,
        selection_path=SELECTION,
        virginity_attestation_path=ATTESTATION,
        virginity_evidence_path=EVIDENCE,
    )


def test_real_generation4_contract_is_verified_without_rewriting_file() -> None:
    before = CONTRACT.read_bytes()
    contract = verify_phase6_contract(CONTRACT)
    after = CONTRACT.read_bytes()

    assert before == after
    assert contract["schema_version"] == "SUCCESSOR-PHASE6-EVALUATION-CONTRACT-v2"
    assert contract["successor_formal_name"] == "GENERATION_4"
    assert (
        contract["methodology"]["successor_normalizer_sha256"]
        == contract["methodology"]["split_normalizer_sha256"]
    )
    assert contract["governance"]["protected_history_access_authorized"] is False
    assert contract["governance"]["symbol_substitution_after_access_allowed"] is False


def test_audited_generation4_evaluator_identity_is_unchanged() -> None:
    assert _sha(EVALUATOR) == "fb20b368d6d7ac0f698c5ab45e5824aaad73341cccfacc25bc6903b98c9a2b21"


def test_non_authorizing_stage_b_template_cannot_grant_access() -> None:
    with pytest.raises(
        SuccessorAcquisitionAuthorityError,
        match="SUCCESSOR_GENERATION4_REQUIRES_ACQUISITION_AUTHORIZATION_V2",
    ):
        _load(TEMPLATE)


def test_generation4_rejects_legacy_v1_authorization(tmp_path: Path) -> None:
    with pytest.raises(
        SuccessorAcquisitionAuthorityError,
        match="SUCCESSOR_GENERATION4_REQUIRES_ACQUISITION_AUTHORIZATION_V2",
    ):
        _load(_write(tmp_path / "auth-v1.json", _legacy_v1_payload()))


def test_generation4_contract_controls_schema_gate_not_authorization_claim(
    tmp_path: Path,
) -> None:
    payload = _legacy_v1_payload()
    payload["successor_formal_name"] = "GENERATION_3_TEST_FIXTURE"
    with pytest.raises(
        SuccessorAcquisitionAuthorityError,
        match="SUCCESSOR_GENERATION4_REQUIRES_ACQUISITION_AUTHORIZATION_V2",
    ):
        _load(_write(tmp_path / "auth-v1-spoof.json", payload))


def test_generation4_v1_rejected_before_sdk_or_provider_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorization = _write(tmp_path / "auth-v1.json", _legacy_v1_payload())
    sdk_loaded = False

    def fail_if_sdk_loaded():
        nonlocal sdk_loaded
        sdk_loaded = True
        raise AssertionError("SDK must not load for a rejected Generation-4 v1 authorization")

    monkeypatch.setattr(acquisition_module, "_load_sdk", fail_if_sdk_loaded)
    with pytest.raises(
        SuccessorAcquisitionAuthorityError,
        match="SUCCESSOR_GENERATION4_REQUIRES_ACQUISITION_AUTHORIZATION_V2",
    ):
        acquisition_module.preflight_acquisition(
            authorization_path=authorization,
            phase6_contract_path=CONTRACT,
            selection_path=SELECTION,
            virginity_attestation_path=ATTESTATION,
            virginity_evidence_path=EVIDENCE,
        )
    assert sdk_loaded is False


def test_legacy_v1_remains_supported_for_pre_generation4_contract(
    tmp_path: Path,
) -> None:
    legacy_contract = verify_phase6_contract(CONTRACT)
    legacy_contract["schema_version"] = "SUCCESSOR-PHASE6-EVALUATION-CONTRACT-v1"
    legacy_contract["successor_formal_name"] = "GENERATION_3_TEST_FIXTURE"
    legacy_contract_path = _write(tmp_path / "legacy-contract.json", legacy_contract)

    payload = _legacy_v1_payload()
    payload["successor_formal_name"] = "GENERATION_3_TEST_FIXTURE"
    payload["phase6_contract_sha256"] = _sha(legacy_contract_path)
    authorization = _write(tmp_path / "legacy-auth-v1.json", payload)

    auth = load_acquisition_authorization(
        authorization_path=authorization,
        phase6_contract_path=legacy_contract_path,
        selection_path=SELECTION,
        virginity_attestation_path=ATTESTATION,
        virginity_evidence_path=EVIDENCE,
    )

    assert auth.schema_version == SCHEMA_V1
    assert auth.successor_formal_name == "GENERATION_3_TEST_FIXTURE"
    assert auth.phase7_authorized is False
    assert auth.production_readiness_approved is False


def test_valid_synthetic_generation4_stage_b_authorization_binds_full_runtime(
    tmp_path: Path,
) -> None:
    auth = _load(_write(tmp_path / "auth.json", _payload()))
    assert auth.schema_version == SCHEMA_V2
    assert auth.successor_formal_name == "GENERATION_4"
    assert auth.one_time is True
    assert auth.successor_normalizer_sha256 == auth.split_normalizer_sha256
    assert auth.retry_after_historical_access_allowed is False
    assert auth.symbol_substitution_after_access_allowed is False
    assert auth.phase7_authorized is False
    assert auth.production_readiness_approved is False


@pytest.mark.parametrize(
    "field",
    [
        "phase6_verifier_implementation_sha256",
        "acquisition_authority_implementation_sha256",
        "acquisition_implementation_sha256",
        "release_implementation_sha256",
        "closure_implementation_sha256",
        "virginity_verifier_implementation_sha256",
        "stage_b_cli_implementation_sha256",
        "dividend_reconciliation_sha256",
        "successor_evaluator_sha256",
        "phase6_contract_sha256",
        "selection_sha256",
        "virginity_attestation_sha256",
        "virginity_evidence_sha256",
    ],
)
def test_generation4_stage_b_tamper_fails_closed(tmp_path: Path, field: str) -> None:
    payload = _payload()
    payload[field] = "0" * 64
    with pytest.raises(SuccessorAcquisitionAuthorityError):
        _load(_write(tmp_path / "auth.json", payload))


@pytest.mark.parametrize(
    ("filename", "error"),
    [
        (
            "corporate_actions_v2.py",
            "SUCCESSOR_SPLIT_NORMALIZER_SOURCE_IDENTITY_MISMATCH",
        ),
        (
            "dividend_reconciliation_v3.py",
            "SUCCESSOR_DIVIDEND_RECONCILIATION_SOURCE_IDENTITY_MISMATCH",
        ),
        (
            "evaluate_dividend_v3.py",
            "SUCCESSOR_EVALUATOR_SOURCE_IDENTITY_MISMATCH",
        ),
    ],
)
def test_generation4_stage_b_methodology_source_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    error: str,
) -> None:
    authorization = _write(tmp_path / "auth.json", _payload())
    original_sha = acquisition_authority_module._sha

    def drifted_sha(path: Path) -> str:
        if Path(path).name == filename:
            return "0" * 64
        return original_sha(path)

    monkeypatch.setattr(acquisition_authority_module, "_sha", drifted_sha)
    with pytest.raises(SuccessorAcquisitionAuthorityError, match=error):
        _load(authorization)


def test_stage_b_cli_uses_corrected_evaluator_not_legacy_evaluator() -> None:
    source = Path(stage_b_cli.__file__).read_text(encoding="utf-8")
    assert "evaluate_dividend_v3" in source
    assert "from investment_tracker.independent_audit.successor.evaluate import" not in source
