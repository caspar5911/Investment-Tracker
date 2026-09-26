from __future__ import annotations

import json
from pathlib import Path

import pytest

from investment_tracker.independent_audit.post_generation3 import (
    phase7_entry as phase7_entry_module,
    phase7_start as phase7_start_module,
)
from investment_tracker.independent_audit.post_generation3.phase7_start import (
    GEN4_PHASE7_START_BINDING_MISMATCH,
    GEN4_PHASE7_START_ENTRY_INVALID,
    GEN4_PHASE7_START_GOVERNANCE_MISMATCH,
    Generation4Phase7StartError,
    verify_generation4_phase7_start_readiness,
)
from tests.independent_audit.test_generation4_phase7_entry import (
    _audit_request,
    _authorization,
    _entry,
    _readiness,
    _valid_chain,
    _write,
)


EXPECTED_SYMBOLS = ["QQQM", "FALN", "IIPR", "PSTL", "EFAS"]
EVIDENCE_HASH_FIELDS = (
    "phase6_contract_sha256",
    "acquisition_authorization_sha256",
    "acquisition_receipt_sha256",
    "release_sha256",
    "evaluation_result_sha256",
    "evaluation_consumption_marker_sha256",
    "phase6_closure_sha256",
)
IDENTITY_FIELDS = (
    "candidate_id",
    "binding_sha256",
    "implementation_sha256",
    "split_normalizer_sha256",
    "dividend_reconciliation_sha256",
    "successor_evaluator_sha256",
)


def _valid_start_inputs(tmp_path: Path) -> tuple[dict[str, Path], dict[str, object]]:
    paths = _valid_chain(tmp_path)
    readiness = _readiness(paths)
    request_path = _audit_request(tmp_path, readiness)
    authorization_path = _authorization(tmp_path, readiness, request_path)
    entry = _entry(paths, request_path, authorization_path)
    paths.update(
        {
            "audit_request": request_path,
            "authorization": authorization_path,
            "phase7_entry": Path(phase7_entry_module.__file__),
            "phase7_entry_cli": tmp_path / "phase7_entry_cli.py",
        }
    )
    return paths, entry


def _start_kwargs(paths: dict[str, Path]) -> dict[str, Path]:
    return {
        "audit_request_path": paths["audit_request"],
        "authorization_path": paths["authorization"],
        "phase6_contract_path": paths["contract"],
        "acquisition_authorization_path": paths["acquisition_authorization"],
        "selection_path": paths["selection"],
        "virginity_attestation_path": paths["virginity_attestation"],
        "virginity_evidence_path": paths["virginity_evidence"],
        "acquisition_receipt_path": paths["receipt"],
        "release_path": paths["release"],
        "phase6_result_path": paths["result"],
        "consumption_marker_path": paths["marker"],
        "phase6_closure_path": paths["closure"],
        "phase7_entry_path": paths["phase7_entry"],
        "phase7_entry_cli_path": paths["phase7_entry_cli"],
    }


def _replace_entry(monkeypatch: pytest.MonkeyPatch, entry: dict[str, object]) -> None:
    monkeypatch.setattr(
        phase7_start_module,
        "evaluate_generation4_phase7_entry",
        lambda **_: entry.copy(),
    )


def _mutate_json(path: Path, field: str, value: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    _write(path, payload)


def _expect_start_error(
    paths: dict[str, Path], code: str
) -> pytest.ExceptionInfo[Generation4Phase7StartError]:
    with pytest.raises(Generation4Phase7StartError) as excinfo:
        verify_generation4_phase7_start_readiness(**_start_kwargs(paths))
    assert excinfo.value.code == code
    return excinfo


def test_valid_synthetic_entry_chain_is_ready_without_metrics(tmp_path: Path):
    paths, _ = _valid_start_inputs(tmp_path)

    report = verify_generation4_phase7_start_readiness(**_start_kwargs(paths))

    assert report["schema_version"] == "GENERATION4-PHASE7-START-READINESS-v1"
    assert report["status"] == "GENERATION4_PHASE7_START_READY"
    assert report["candidate_id"] == (
        "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
    )
    assert report["locked_symbols"] == EXPECTED_SYMBOLS
    assert report["phase7_entry_authorized"] is True
    assert report["phase7_started"] is False
    assert report["phase7_performance_evaluation_authorized"] is False
    assert report["production_readiness_approved"] is False
    assert report["live_trading_authorized"] is False
    assert report["recon009_status"] == "OPEN"
    assert report["paper_only"] is True
    assert "metrics" not in report


def test_missing_authorization_fails_closed(tmp_path: Path):
    paths, _ = _valid_start_inputs(tmp_path)
    paths["authorization"].unlink()

    _expect_start_error(paths, GEN4_PHASE7_START_ENTRY_INVALID)


def test_invalid_authorization_fails_closed(tmp_path: Path):
    paths, _ = _valid_start_inputs(tmp_path)
    _mutate_json(paths["authorization"], "unexpected", True)

    _expect_start_error(paths, GEN4_PHASE7_START_ENTRY_INVALID)


def test_wrong_authorization_id_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    paths, entry = _valid_start_inputs(tmp_path)
    entry["authorization_id"] = "DIFFERENT-AUTHORIZATION"
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_BINDING_MISMATCH)


def test_audit_request_hash_mismatch_fails_closed(tmp_path: Path):
    paths, _ = _valid_start_inputs(tmp_path)
    request = json.loads(paths["audit_request"].read_text(encoding="utf-8"))
    request["authority"] = "INDEPENDENT_AUDIT"
    _write(paths["audit_request"], request)

    _expect_start_error(paths, GEN4_PHASE7_START_ENTRY_INVALID)


@pytest.mark.parametrize("field", IDENTITY_FIELDS)
def test_identity_drift_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
):
    paths, entry = _valid_start_inputs(tmp_path)
    entry[field] = "f" * 64 if field != "candidate_id" else "DIFFERENT-CANDIDATE"
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_BINDING_MISMATCH)


def test_locked_symbol_order_drift_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    paths, entry = _valid_start_inputs(tmp_path)
    _mutate_json(paths["authorization"], "locked_symbols", list(reversed(EXPECTED_SYMBOLS)))
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_BINDING_MISMATCH)


@pytest.mark.parametrize("field", EVIDENCE_HASH_FIELDS)
def test_each_evidence_hash_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
):
    paths, entry = _valid_start_inputs(tmp_path)
    entry[field] = "f" * 64
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_BINDING_MISMATCH)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("production_readiness_approved", True),
        ("live_trading_authorized", True),
        ("recon009_status", "CLOSED"),
        ("paper_only", False),
    ),
)
def test_entry_governance_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
):
    paths, entry = _valid_start_inputs(tmp_path)
    entry[field] = value
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_GOVERNANCE_MISMATCH)


@pytest.mark.parametrize(
    "field",
    (
        "retry_authorized",
        "holdout_reuse_authorized",
        "candidate_search_authorized",
        "symbol_substitution_authorized",
        "result_dependent_methodology_change_allowed",
        "result_dependent_parameter_change_allowed",
    ),
)
def test_forbidden_authority_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
):
    paths, entry = _valid_start_inputs(tmp_path)
    _mutate_json(paths["authorization"], field, True)
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_ENTRY_INVALID)
