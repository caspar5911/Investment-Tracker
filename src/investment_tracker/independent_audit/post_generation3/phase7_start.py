from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from investment_tracker.independent_audit.post_generation3.phase7_entry import (
    Generation4Phase7Authorization,
    Generation4Phase7EntryError,
    evaluate_generation4_phase7_entry,
)


START_READINESS_SCHEMA = "GENERATION4-PHASE7-START-READINESS-v1"
START_READINESS_STATUS = "GENERATION4_PHASE7_START_READY"
ENTRY_ALLOWED_STATUS = "GENERATION4_PHASE7_ENTRY_ALLOWED"
PHASE6_STATUS = "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"

GEN4_PHASE7_START_EVIDENCE_INVALID = "GEN4_PHASE7_START_EVIDENCE_INVALID"
GEN4_PHASE7_START_ENTRY_INVALID = "GEN4_PHASE7_START_ENTRY_INVALID"
GEN4_PHASE7_START_CONTRACT_MISSING = "GEN4_PHASE7_START_CONTRACT_MISSING"
GEN4_PHASE7_START_CONTRACT_INVALID = "GEN4_PHASE7_START_CONTRACT_INVALID"
GEN4_PHASE7_START_BINDING_MISMATCH = "GEN4_PHASE7_START_BINDING_MISMATCH"
GEN4_PHASE7_START_GOVERNANCE_MISMATCH = "GEN4_PHASE7_START_GOVERNANCE_MISMATCH"
GEN4_PHASE7_ALREADY_STARTED = "GEN4_PHASE7_ALREADY_STARTED"
GEN4_PHASE7_START_WRITE_FAILED = "GEN4_PHASE7_START_WRITE_FAILED"

_CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
_BINDING_SHA256 = "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"
_IMPLEMENTATION_SHA256 = (
    "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"
)
_SPLIT_NORMALIZER_SHA256 = (
    "bfbf0de5bdeb39af3535641570f3f9224f5301abb7db9fffc34c580481cace04"
)
_DIVIDEND_RECONCILIATION_SHA256 = (
    "6baa251d51f6f16be602aa82b08fc46665a4ccdd62f68705821c48c8a28ac9bc"
)
_SUCCESSOR_EVALUATOR_SHA256 = (
    "fb20b368d6d7ac0f698c5ab45e5824aaad73341cccfacc25bc6903b98c9a2b21"
)
_LOCKED_SYMBOLS = ("QQQM", "FALN", "IIPR", "PSTL", "EFAS")

_IDENTITY_EXPECTATIONS = {
    "candidate_id": _CANDIDATE_ID,
    "binding_sha256": _BINDING_SHA256,
    "implementation_sha256": _IMPLEMENTATION_SHA256,
    "split_normalizer_sha256": _SPLIT_NORMALIZER_SHA256,
    "dividend_reconciliation_sha256": _DIVIDEND_RECONCILIATION_SHA256,
    "successor_evaluator_sha256": _SUCCESSOR_EVALUATOR_SHA256,
}
_EVIDENCE_HASH_FIELDS = (
    "phase6_contract_sha256",
    "acquisition_authorization_sha256",
    "acquisition_receipt_sha256",
    "release_sha256",
    "evaluation_result_sha256",
    "evaluation_consumption_marker_sha256",
    "phase6_closure_sha256",
)
_PROHIBITION_FIELDS = (
    "retry_authorized",
    "holdout_reuse_authorized",
    "candidate_search_authorized",
    "symbol_substitution_authorized",
    "result_dependent_methodology_change_allowed",
    "result_dependent_parameter_change_allowed",
)


class Generation4Phase7StartError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _require_equal(
    actual: object, expected: object, *, code: str, field: str
) -> None:
    if actual != expected:
        raise Generation4Phase7StartError(code, field)


def _load_validated_authorization(path: Path) -> Generation4Phase7Authorization:
    try:
        raw = json.loads(Path(path).read_bytes())
        return Generation4Phase7Authorization.model_validate(raw)
    except Exception as exc:
        raise Generation4Phase7StartError(
            GEN4_PHASE7_START_ENTRY_INVALID, "authorization"
        ) from exc


def verify_generation4_phase7_start_readiness(
    *,
    audit_request_path: Path,
    authorization_path: Path,
    phase6_contract_path: Path,
    acquisition_authorization_path: Path,
    selection_path: Path,
    virginity_attestation_path: Path,
    virginity_evidence_path: Path,
    acquisition_receipt_path: Path,
    release_path: Path,
    phase6_result_path: Path,
    consumption_marker_path: Path,
    phase6_closure_path: Path,
    phase7_entry_path: Path | None = None,
    phase7_entry_cli_path: Path | None = None,
) -> dict[str, Any]:
    entry_source = (
        Path(phase7_entry_path)
        if phase7_entry_path is not None
        else Path(__file__).with_name("phase7_entry.py")
    )
    entry_cli_source = (
        Path(phase7_entry_cli_path)
        if phase7_entry_cli_path is not None
        else Path(__file__).with_name("phase7_entry_cli.py")
    )
    try:
        entry = evaluate_generation4_phase7_entry(
            audit_request_path=Path(audit_request_path),
            authorization_path=Path(authorization_path),
            phase6_contract_path=Path(phase6_contract_path),
            acquisition_authorization_path=Path(acquisition_authorization_path),
            selection_path=Path(selection_path),
            virginity_attestation_path=Path(virginity_attestation_path),
            virginity_evidence_path=Path(virginity_evidence_path),
            acquisition_receipt_path=Path(acquisition_receipt_path),
            release_path=Path(release_path),
            phase6_result_path=Path(phase6_result_path),
            consumption_marker_path=Path(consumption_marker_path),
            phase6_closure_path=Path(phase6_closure_path),
            phase7_entry_path=entry_source,
            phase7_cli_path=entry_cli_source,
        )
    except Generation4Phase7EntryError as exc:
        raise Generation4Phase7StartError(
            GEN4_PHASE7_START_ENTRY_INVALID, exc.code
        ) from exc

    _require_equal(
        entry.get("status"),
        ENTRY_ALLOWED_STATUS,
        code=GEN4_PHASE7_START_ENTRY_INVALID,
        field="entry.status",
    )
    authorization = _load_validated_authorization(Path(authorization_path))
    try:
        authorization_sha256 = _sha(Path(authorization_path))
        audit_request_sha256 = _sha(Path(audit_request_path))
        entry_source_sha256 = _sha(entry_source)
        entry_cli_source_sha256 = _sha(entry_cli_source)
    except OSError as exc:
        raise Generation4Phase7StartError(
            GEN4_PHASE7_START_EVIDENCE_INVALID, "entry_binding_source"
        ) from exc

    for field, expected in _IDENTITY_EXPECTATIONS.items():
        _require_equal(
            entry.get(field),
            expected,
            code=GEN4_PHASE7_START_BINDING_MISMATCH,
            field=f"entry.{field}",
        )
        _require_equal(
            getattr(authorization, field),
            expected,
            code=GEN4_PHASE7_START_BINDING_MISMATCH,
            field=f"authorization.{field}",
        )
    _require_equal(
        list(authorization.locked_symbols),
        list(_LOCKED_SYMBOLS),
        code=GEN4_PHASE7_START_BINDING_MISMATCH,
        field="authorization.locked_symbols",
    )
    for field in (
        "authorization_id",
        "implementation_commit",
        "audit_request_sha256",
        "holdout_id",
        "release_id",
        *_EVIDENCE_HASH_FIELDS,
    ):
        expected = getattr(authorization, field)
        _require_equal(
            entry.get(field),
            expected,
            code=GEN4_PHASE7_START_BINDING_MISMATCH,
            field=f"entry.{field}",
        )
    _require_equal(
        authorization.audit_request_sha256,
        audit_request_sha256,
        code=GEN4_PHASE7_START_BINDING_MISMATCH,
        field="authorization.audit_request_sha256",
    )
    _require_equal(
        authorization.phase7_gate_implementation_sha256,
        entry_source_sha256,
        code=GEN4_PHASE7_START_BINDING_MISMATCH,
        field="authorization.phase7_gate_implementation_sha256",
    )
    _require_equal(
        authorization.phase7_cli_implementation_sha256,
        entry_cli_source_sha256,
        code=GEN4_PHASE7_START_BINDING_MISMATCH,
        field="authorization.phase7_cli_implementation_sha256",
    )

    for field, expected in (
        ("phase7_entry_authorized", True),
        ("phase7_started", False),
        ("production_readiness_approved", False),
        ("live_trading_authorized", False),
        ("recon009_status", "OPEN"),
        ("paper_only", True),
    ):
        _require_equal(
            entry.get(field),
            expected,
            code=GEN4_PHASE7_START_GOVERNANCE_MISMATCH,
            field=f"entry.{field}",
        )
    _require_equal(
        authorization.phase6_status,
        PHASE6_STATUS,
        code=GEN4_PHASE7_START_GOVERNANCE_MISMATCH,
        field="authorization.phase6_status",
    )
    _require_equal(
        authorization.one_time_consumed,
        True,
        code=GEN4_PHASE7_START_GOVERNANCE_MISMATCH,
        field="authorization.one_time_consumed",
    )
    for field in _PROHIBITION_FIELDS:
        _require_equal(
            getattr(authorization, field),
            False,
            code=GEN4_PHASE7_START_GOVERNANCE_MISMATCH,
            field=f"authorization.{field}",
        )

    report: dict[str, Any] = {
        "schema_version": START_READINESS_SCHEMA,
        "status": START_READINESS_STATUS,
        "generation": "GENERATION_4",
        "authorization_id": authorization.authorization_id,
        "phase7_entry_implementation_commit": authorization.implementation_commit,
        "entry_authorization_sha256": authorization_sha256,
        "audit_request_sha256": audit_request_sha256,
        "phase7_entry_source_sha256": entry_source_sha256,
        "phase7_entry_cli_source_sha256": entry_cli_source_sha256,
        "candidate_id": _CANDIDATE_ID,
        "binding_sha256": _BINDING_SHA256,
        "implementation_sha256": _IMPLEMENTATION_SHA256,
        "split_normalizer_sha256": _SPLIT_NORMALIZER_SHA256,
        "dividend_reconciliation_sha256": _DIVIDEND_RECONCILIATION_SHA256,
        "successor_evaluator_sha256": _SUCCESSOR_EVALUATOR_SHA256,
        "locked_symbols": list(_LOCKED_SYMBOLS),
        "holdout_id": authorization.holdout_id,
        "release_id": authorization.release_id,
        "phase6_status": PHASE6_STATUS,
        "one_time_consumed": True,
        "phase7_entry_authorized": True,
        "phase7_started": False,
        "phase7_performance_evaluation_authorized": False,
        "production_readiness_approved": False,
        "live_trading_authorized": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }
    report.update(
        {field: getattr(authorization, field) for field in _EVIDENCE_HASH_FIELDS}
    )
    report.update({field: False for field in _PROHIBITION_FIELDS})
    return report
