from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

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
_LOCKED_SYMBOLS_SHA256 = (
    "1f7880217a7679df2513551372d8abe1b81c63d13ab6c729077c017186ba80b7"
)

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


class Generation4Phase7StartContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["GENERATION4-PHASE7-START-CONTRACT-v1"]
    status: Literal["FROZEN_PRE_START"]
    authority: Literal[
        "COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION"
    ]
    generation: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    split_normalizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dividend_reconciliation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locked_symbols: tuple[str, ...]
    holdout_id: str = Field(min_length=1)
    release_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    entry_authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase6_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_consumption_marker_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase6_closure_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase6_status: str = Field(min_length=1)
    one_time_consumed: StrictBool
    phase7_entry_implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    phase7_entry_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_entry_cli_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_start_implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    phase7_start_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_start_cli_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_entry_authorized: StrictBool
    phase7_started: StrictBool
    phase7_performance_evaluation_authorized: StrictBool
    production_readiness_approved: StrictBool
    live_trading_authorized: StrictBool
    retry_authorized: StrictBool
    holdout_reuse_authorized: StrictBool
    candidate_search_authorized: StrictBool
    parameter_mutation_authorized: StrictBool
    symbol_substitution_authorized: StrictBool
    result_dependent_methodology_change_allowed: StrictBool
    result_dependent_parameter_change_allowed: StrictBool
    recon009_status: str = Field(min_length=1)
    paper_only: StrictBool


class Generation4Phase7StartError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


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
    locked_symbols = list(authorization.locked_symbols)
    _require_equal(
        sha256(_canonical_json(locked_symbols)).hexdigest(),
        _LOCKED_SYMBOLS_SHA256,
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
        "locked_symbols": locked_symbols,
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
    report["parameter_mutation_authorized"] = False
    return report


_CONTRACT_READINESS_FIELDS = (
    "generation",
    "candidate_id",
    "binding_sha256",
    "implementation_sha256",
    "split_normalizer_sha256",
    "dividend_reconciliation_sha256",
    "successor_evaluator_sha256",
    "locked_symbols",
    "holdout_id",
    "release_id",
    "authorization_id",
    "entry_authorization_sha256",
    "audit_request_sha256",
    *_EVIDENCE_HASH_FIELDS,
    "phase6_status",
    "one_time_consumed",
    "phase7_entry_implementation_commit",
    "phase7_entry_source_sha256",
    "phase7_entry_cli_source_sha256",
)

_CONTRACT_GOVERNANCE_EXPECTATIONS = {
    "phase7_entry_authorized": True,
    "phase7_started": False,
    "phase7_performance_evaluation_authorized": False,
    "production_readiness_approved": False,
    "live_trading_authorized": False,
    "retry_authorized": False,
    "holdout_reuse_authorized": False,
    "candidate_search_authorized": False,
    "parameter_mutation_authorized": False,
    "symbol_substitution_authorized": False,
    "result_dependent_methodology_change_allowed": False,
    "result_dependent_parameter_change_allowed": False,
    "recon009_status": "OPEN",
    "paper_only": True,
}


def load_generation4_phase7_start_contract(
    *,
    contract_path: Path,
    readiness: dict[str, Any],
    authorization_path: Path,
    audit_request_path: Path,
    phase7_entry_path: Path,
    phase7_entry_cli_path: Path,
    phase7_start_path: Path,
    phase7_start_cli_path: Path,
) -> Generation4Phase7StartContract:
    if not Path(contract_path).is_file():
        raise Generation4Phase7StartError(
            GEN4_PHASE7_START_CONTRACT_MISSING, "start_contract"
        )
    try:
        raw = json.loads(Path(contract_path).read_bytes())
        contract = Generation4Phase7StartContract.model_validate(raw)
    except Exception as exc:
        raise Generation4Phase7StartError(
            GEN4_PHASE7_START_CONTRACT_INVALID, "start_contract"
        ) from exc

    for field in _CONTRACT_READINESS_FIELDS:
        actual = getattr(contract, field)
        if field == "locked_symbols":
            actual = list(actual)
        _require_equal(
            actual,
            readiness.get(field),
            code=GEN4_PHASE7_START_BINDING_MISMATCH,
            field=field,
        )

    try:
        actual_hashes = {
            "entry_authorization_sha256": _sha(Path(authorization_path)),
            "audit_request_sha256": _sha(Path(audit_request_path)),
            "phase7_entry_source_sha256": _sha(Path(phase7_entry_path)),
            "phase7_entry_cli_source_sha256": _sha(Path(phase7_entry_cli_path)),
            "phase7_start_source_sha256": _sha(Path(phase7_start_path)),
            "phase7_start_cli_source_sha256": _sha(Path(phase7_start_cli_path)),
        }
    except OSError as exc:
        raise Generation4Phase7StartError(
            GEN4_PHASE7_START_EVIDENCE_INVALID, "contract_binding_source"
        ) from exc
    for field, actual in actual_hashes.items():
        _require_equal(
            getattr(contract, field),
            actual,
            code=GEN4_PHASE7_START_BINDING_MISMATCH,
            field=field,
        )

    for field, expected in _CONTRACT_GOVERNANCE_EXPECTATIONS.items():
        _require_equal(
            getattr(contract, field),
            expected,
            code=GEN4_PHASE7_START_GOVERNANCE_MISMATCH,
            field=field,
        )
        _require_equal(
            readiness.get(field),
            expected,
            code=GEN4_PHASE7_START_GOVERNANCE_MISMATCH,
            field=f"readiness.{field}",
        )
    return contract


def _started_at_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def start_generation4_phase7(
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
    start_contract_path: Path,
    start_output_path: Path,
    phase7_entry_path: Path | None = None,
    phase7_entry_cli_path: Path | None = None,
    phase7_start_path: Path | None = None,
    phase7_start_cli_path: Path | None = None,
) -> dict[str, Any]:
    output_path = Path(start_output_path)
    if output_path.exists():
        raise Generation4Phase7StartError(
            GEN4_PHASE7_ALREADY_STARTED, "start_output"
        )

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
    start_source = (
        Path(phase7_start_path) if phase7_start_path is not None else Path(__file__)
    )
    start_cli_source = (
        Path(phase7_start_cli_path)
        if phase7_start_cli_path is not None
        else Path(__file__).with_name("phase7_start_cli.py")
    )
    readiness = verify_generation4_phase7_start_readiness(
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
        phase7_entry_cli_path=entry_cli_source,
    )
    contract = load_generation4_phase7_start_contract(
        contract_path=Path(start_contract_path),
        readiness=readiness,
        authorization_path=Path(authorization_path),
        audit_request_path=Path(audit_request_path),
        phase7_entry_path=entry_source,
        phase7_entry_cli_path=entry_cli_source,
        phase7_start_path=start_source,
        phase7_start_cli_path=start_cli_source,
    )

    artifact = contract.model_dump(mode="json")
    artifact.update(
        {
            "schema_version": "GENERATION4-PHASE7-START-v1",
            "status": "GENERATION4_PHASE7_STARTED",
            "authority": "COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION",
            "started_at_utc": _started_at_utc(),
            "start_contract_sha256": _sha(Path(start_contract_path)),
            "phase7_started": True,
        }
    )
    artifact["artifact_sha256"] = sha256(_canonical_json(artifact)).hexdigest()
    encoded = _canonical_json(artifact)
    try:
        with output_path.open("xb") as handle:
            handle.write(encoded)
    except FileExistsError as exc:
        raise Generation4Phase7StartError(
            GEN4_PHASE7_ALREADY_STARTED, "start_output"
        ) from exc
    except OSError as exc:
        raise Generation4Phase7StartError(
            GEN4_PHASE7_START_WRITE_FAILED, "start_output"
        ) from exc

    try:
        readback = output_path.read_bytes()
        decoded = json.loads(readback)
    except Exception as exc:
        raise Generation4Phase7StartError(
            GEN4_PHASE7_START_WRITE_FAILED, "start_output_readback"
        ) from exc
    if readback != encoded or decoded != artifact:
        raise Generation4Phase7StartError(
            GEN4_PHASE7_START_WRITE_FAILED, "start_output_readback"
        )
    return artifact
