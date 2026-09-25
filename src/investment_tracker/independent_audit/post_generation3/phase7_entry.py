from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from investment_tracker.independent_audit.successor.acquisition_authority import (
    SCHEMA_V2 as ACQUISITION_AUTHORIZATION_SCHEMA,
    SuccessorAcquisitionAuthorityError,
    SuccessorAcquisitionAuthorizationV2,
    load_acquisition_authorization,
)
from investment_tracker.independent_audit.successor.phase6_contract import (
    verify_phase6_contract,
)
from investment_tracker.independent_audit.successor.release import (
    load_receipt,
    load_release,
)


READINESS_SCHEMA = "GENERATION4-PHASE7-ENTRY-READINESS-v1"
READINESS_STATUS = "GENERATION4_PHASE7_READY_FOR_INDEPENDENT_AUDIT"
PHASE6_STATUS = "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"

GEN4_PHASE7_EVIDENCE_INVALID = "GEN4_PHASE7_EVIDENCE_INVALID"
GEN4_PHASE7_GOVERNANCE_MISMATCH = "GEN4_PHASE7_GOVERNANCE_MISMATCH"
GEN4_PHASE7_IDENTITY_MISMATCH = "GEN4_PHASE7_IDENTITY_MISMATCH"
GEN4_PHASE7_CHAIN_MISMATCH = "GEN4_PHASE7_CHAIN_MISMATCH"
GEN4_PHASE7_AUTHORIZATION_MISSING = "GEN4_PHASE7_AUTHORIZATION_MISSING"
GEN4_PHASE7_AUTHORIZATION_INVALID = "GEN4_PHASE7_AUTHORIZATION_INVALID"
GEN4_PHASE7_AUTHORIZATION_MISMATCH = "GEN4_PHASE7_AUTHORIZATION_MISMATCH"

_CONTRACT_SCHEMA = "SUCCESSOR-PHASE6-EVALUATION-CONTRACT-v2"
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
_STRATEGY = {
    "candidate_id": _CANDIDATE_ID,
    "binding_sha256": _BINDING_SHA256,
    "implementation_sha256": _IMPLEMENTATION_SHA256,
    "family": "G2-A",
    "lookback": 189,
    "skip": 21,
    "top_k": 1,
    "rebalance": 21,
    "long_only": True,
    "portfolio_leverage_allowed": False,
    "short_selling_allowed": False,
    "candidate_search_allowed": False,
    "parameter_mutation_allowed": False,
    "signal_on_completed_session": True,
    "earliest_fill": "NEXT_ELIGIBLE_SESSION_OPEN",
}


class _Generation4Phase7AuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "GENERATION4-PHASE7-ENTRY-INDEPENDENT-AUDIT-REQUEST-v1"
    ]
    status: Literal["READY_FOR_INDEPENDENT_AUDIT"]
    authority: Literal["NONE"]
    generation: Literal["GENERATION_4"]
    implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    phase7_gate_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_cli_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_id: str = Field(min_length=1)
    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    split_normalizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dividend_reconciliation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locked_symbols: tuple[str, ...]
    holdout_id: str = Field(min_length=1)
    release_id: str = Field(min_length=1)
    phase6_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_consumption_marker_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase6_closure_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase6_status: Literal[
        "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"
    ]
    one_time_consumed: Literal[True]
    authority_granted: Literal[False]
    phase7_authorized: Literal[False]
    phase7_started: Literal[False]
    production_readiness_approved: Literal[False]
    live_trading_authorized: Literal[False]
    recon009_status: Literal["OPEN"]
    paper_only: Literal[True]


class Generation4Phase7Authorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["GENERATION4-PHASE7-ENTRY-AUTHORIZATION-v1"]
    authority: Literal["INDEPENDENT_AUDIT"]
    status: Literal["GENERATION4_PHASE7_ENTRY_AUTHORIZED"]
    authorization_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    signed_by: str = Field(min_length=1, max_length=256)
    approved_at_utc: str = Field(min_length=1)
    generation: Literal["GENERATION_4"]
    implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    audit_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_gate_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_cli_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_id: Literal["G2-A|lookback=189|skip=21|top_k=1|rebalance=21"]
    binding_sha256: Literal[
        "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"
    ]
    implementation_sha256: Literal[
        "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"
    ]
    split_normalizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dividend_reconciliation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locked_symbols: tuple[str, ...]
    holdout_id: str = Field(min_length=1)
    release_id: str = Field(min_length=1)
    phase6_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_consumption_marker_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase6_closure_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase6_status: Literal[
        "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"
    ]
    one_time_consumed: Literal[True]
    phase7_entry_authorized: Literal[True]
    phase7_started: Literal[False]
    retry_authorized: Literal[False]
    holdout_reuse_authorized: Literal[False]
    candidate_search_authorized: Literal[False]
    symbol_substitution_authorized: Literal[False]
    result_dependent_methodology_change_allowed: Literal[False]
    result_dependent_parameter_change_allowed: Literal[False]
    production_readiness_approved: Literal[False]
    live_trading_authorized: Literal[False]
    recon009_status: Literal["OPEN"]
    paper_only: Literal[True]


class Generation4Phase7EntryError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _load_object(path: Path, *, detail: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, detail
        ) from exc
    if not isinstance(value, dict):
        raise Generation4Phase7EntryError(GEN4_PHASE7_EVIDENCE_INVALID, detail)
    return value


def _require_equal(
    actual: object, expected: object, *, code: str, field: str
) -> None:
    if actual != expected:
        raise Generation4Phase7EntryError(code, field)


def _require_false(value: object, *, field: str) -> None:
    _require_equal(
        value, False, code=GEN4_PHASE7_GOVERNANCE_MISMATCH, field=field
    )


def _require_true(value: object, *, field: str) -> None:
    _require_equal(value, True, code=GEN4_PHASE7_GOVERNANCE_MISMATCH, field=field)


def _verify_contract(contract: dict[str, Any]) -> None:
    _require_equal(
        contract.get("schema_version"),
        _CONTRACT_SCHEMA,
        code=GEN4_PHASE7_IDENTITY_MISMATCH,
        field="contract.schema_version",
    )
    _require_equal(
        contract.get("status"),
        "FROZEN_PRE_ACCESS",
        code=GEN4_PHASE7_GOVERNANCE_MISMATCH,
        field="contract.status",
    )
    _require_equal(
        contract.get("authority"),
        "INDEPENDENT_AUDIT",
        code=GEN4_PHASE7_GOVERNANCE_MISMATCH,
        field="contract.authority",
    )
    _require_equal(
        contract.get("successor_formal_name"),
        "GENERATION_4",
        code=GEN4_PHASE7_IDENTITY_MISMATCH,
        field="contract.successor_formal_name",
    )
    strategy = contract.get("strategy")
    if not isinstance(strategy, dict):
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "contract.strategy"
        )
    for field, expected in _STRATEGY.items():
        _require_equal(
            strategy.get(field),
            expected,
            code=GEN4_PHASE7_IDENTITY_MISMATCH,
            field=f"contract.strategy.{field}",
        )
    methodology = contract.get("methodology")
    if not isinstance(methodology, dict):
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "contract.methodology"
        )
    for field, expected in (
        ("split_normalizer_sha256", _SPLIT_NORMALIZER_SHA256),
        ("dividend_reconciliation_sha256", _DIVIDEND_RECONCILIATION_SHA256),
        ("successor_evaluator_sha256", _SUCCESSOR_EVALUATOR_SHA256),
    ):
        _require_equal(
            methodology.get(field),
            expected,
            code=GEN4_PHASE7_IDENTITY_MISMATCH,
            field=f"contract.methodology.{field}",
        )
    governance = contract.get("governance")
    if not isinstance(governance, dict):
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "contract.governance"
        )
    for field, expected in (
        ("retry_after_historical_access_allowed", False),
        ("symbol_substitution_after_access_allowed", False),
        ("phase7_authorized", False),
        ("production_readiness_approved", False),
        ("recon009_status", "OPEN"),
        ("paper_only", True),
    ):
        _require_equal(
            governance.get(field),
            expected,
            code=GEN4_PHASE7_GOVERNANCE_MISMATCH,
            field=f"contract.governance.{field}",
        )


def _verify_identity_fields(
    value: dict[str, Any],
    *,
    name: str,
    contract: dict[str, Any],
    locked_symbols_field: str | None = None,
) -> None:
    strategy = contract["strategy"]
    for field in ("candidate_id", "binding_sha256", "implementation_sha256"):
        _require_equal(
            value.get(field),
            strategy[field],
            code=GEN4_PHASE7_IDENTITY_MISMATCH,
            field=f"{name}.{field}",
        )
    if locked_symbols_field is not None:
        _require_equal(
            value.get(locked_symbols_field),
            contract["final_holdout"]["locked_symbols"],
            code=GEN4_PHASE7_IDENTITY_MISMATCH,
            field=f"{name}.{locked_symbols_field}",
        )


def _verify_downstream_methodology(
    value: dict[str, Any], *, name: str, contract: dict[str, Any]
) -> None:
    methodology = contract["methodology"]
    for field, expected in (
        ("successor_normalizer_sha256", methodology["split_normalizer_sha256"]),
        ("successor_evaluator_sha256", methodology["successor_evaluator_sha256"]),
    ):
        _require_equal(
            value.get(field),
            expected,
            code=GEN4_PHASE7_IDENTITY_MISMATCH,
            field=f"{name}.{field}",
        )


def _verify_receipt(
    receipt: dict[str, Any],
    *,
    contract: dict[str, Any],
    contract_sha256: str,
    acquisition_authorization_sha256: str,
) -> None:
    for field, expected in (
        ("schema_version", "SUCCESSOR-PHASE6-HOLDOUT-ACQUISITION-RECEIPT-v1"),
        ("authority", "INDEPENDENT_AUDIT"),
        ("status", "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED"),
        ("successor_formal_name", "GENERATION_4"),
    ):
        _require_equal(
            receipt.get(field),
            expected,
            code=GEN4_PHASE7_EVIDENCE_INVALID,
            field=f"receipt.{field}",
        )
    _verify_identity_fields(
        receipt,
        name="receipt",
        contract=contract,
        locked_symbols_field="protected_symbols_accessed",
    )
    _verify_downstream_methodology(receipt, name="receipt", contract=contract)
    for field, expected in (
        ("phase6_contract_sha256", contract_sha256),
        ("acquisition_authorization_sha256", acquisition_authorization_sha256),
    ):
        _require_equal(
            receipt.get(field),
            expected,
            code=GEN4_PHASE7_CHAIN_MISMATCH,
            field=f"receipt.{field}",
        )
    _require_true(
        receipt.get("final_holdout_accessed"), field="receipt.final_holdout_accessed"
    )
    _require_false(
        receipt.get("performance_computed"), field="receipt.performance_computed"
    )
    _require_false(
        receipt.get("performance_inspected"), field="receipt.performance_inspected"
    )
    _require_false(receipt.get("retry_allowed"), field="receipt.retry_allowed")
    _require_true(
        receipt.get("artifact_readback_verified"),
        field="receipt.artifact_readback_verified",
    )


def _verify_release(
    release: dict[str, Any],
    *,
    receipt: dict[str, Any],
    contract: dict[str, Any],
    contract_sha256: str,
    receipt_sha256: str,
) -> None:
    for field, expected in (
        ("schema_version", "SUCCESSOR-PHASE6-HOLDOUT-RELEASE-v1"),
        ("authority", "INDEPENDENT_AUDIT"),
        ("status", "FINAL_HOLDOUT_RELEASE_AUTHORIZED"),
        ("successor_formal_name", "GENERATION_4"),
    ):
        _require_equal(
            release.get(field),
            expected,
            code=GEN4_PHASE7_EVIDENCE_INVALID,
            field=f"release.{field}",
        )
    _verify_identity_fields(
        release,
        name="release",
        contract=contract,
        locked_symbols_field="locked_symbols",
    )
    _verify_downstream_methodology(release, name="release", contract=contract)
    for field, expected in (
        ("holdout_id", receipt.get("holdout_id")),
        ("phase6_contract_sha256", contract_sha256),
        ("holdout_bundle_sha256", receipt.get("bundle_sha256")),
        ("holdout_key_sha256", receipt.get("key_sha256")),
    ):
        _require_equal(
            release.get(field),
            expected,
            code=GEN4_PHASE7_IDENTITY_MISMATCH,
            field=f"release.{field}",
        )
    _require_equal(
        release.get("acquisition_receipt_file_sha256"),
        receipt_sha256,
        code=GEN4_PHASE7_CHAIN_MISMATCH,
        field="release.acquisition_receipt_file_sha256",
    )
    _require_true(release.get("one_time"), field="release.one_time")
    _require_false(
        release.get("performance_inspected_before_release"),
        field="release.performance_inspected_before_release",
    )
    _require_true(
        release.get("one_time_evaluation_authorized"),
        field="release.one_time_evaluation_authorized",
    )
    _require_false(
        release.get("phase7_authorized"), field="release.phase7_authorized"
    )
    _require_false(
        release.get("production_readiness_approved"),
        field="release.production_readiness_approved",
    )
    _require_equal(
        release.get("recon009_status"),
        "OPEN",
        code=GEN4_PHASE7_GOVERNANCE_MISMATCH,
        field="release.recon009_status",
    )


def _verify_result(
    result: dict[str, Any],
    *,
    release: dict[str, Any],
    contract: dict[str, Any],
    contract_sha256: str,
) -> None:
    for field, expected, code in (
        (
            "schema_version",
            "SUCCESSOR-PHASE6-FINAL-HOLDOUT-EVALUATION-v2",
            GEN4_PHASE7_EVIDENCE_INVALID,
        ),
        (
            "authority",
            "COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE",
            GEN4_PHASE7_EVIDENCE_INVALID,
        ),
        ("status", PHASE6_STATUS, GEN4_PHASE7_GOVERNANCE_MISMATCH),
        ("successor_formal_name", "GENERATION_4", GEN4_PHASE7_IDENTITY_MISMATCH),
        ("phase6_contract_sha256", contract_sha256, GEN4_PHASE7_IDENTITY_MISMATCH),
        ("holdout_id", release.get("holdout_id"), GEN4_PHASE7_IDENTITY_MISMATCH),
        ("release_id", release.get("release_id"), GEN4_PHASE7_IDENTITY_MISMATCH),
    ):
        _require_equal(result.get(field), expected, code=code, field=f"result.{field}")
    _verify_identity_fields(
        result,
        name="result",
        contract=contract,
        locked_symbols_field="locked_symbols",
    )
    _verify_downstream_methodology(result, name="result", contract=contract)
    _require_true(result.get("one_time_consumed"), field="result.one_time_consumed")
    for field in (
        "candidate_search_executed",
        "candidate_parameters_changed",
        "holdout_symbol_substitution_executed",
        "phase7_authorized",
        "phase7_started",
        "production_readiness_approved",
    ):
        _require_false(result.get(field), field=f"result.{field}")
    _require_equal(
        result.get("recon009_status"),
        "OPEN",
        code=GEN4_PHASE7_GOVERNANCE_MISMATCH,
        field="result.recon009_status",
    )


def _verify_marker(
    marker: dict[str, Any],
    *,
    release: dict[str, Any],
    contract: dict[str, Any],
    contract_sha256: str,
    result_sha256: str,
) -> None:
    for field, expected, code in (
        (
            "schema_version",
            "SUCCESSOR-PHASE6-HOLDOUT-CONSUMPTION-v1",
            GEN4_PHASE7_EVIDENCE_INVALID,
        ),
        ("status", "FINAL_HOLDOUT_RELEASE_CONSUMED", GEN4_PHASE7_GOVERNANCE_MISMATCH),
        ("release_id", release.get("release_id"), GEN4_PHASE7_IDENTITY_MISMATCH),
        ("holdout_id", release.get("holdout_id"), GEN4_PHASE7_IDENTITY_MISMATCH),
        (
            "candidate_id",
            contract["strategy"]["candidate_id"],
            GEN4_PHASE7_IDENTITY_MISMATCH,
        ),
        ("phase6_contract_sha256", contract_sha256, GEN4_PHASE7_IDENTITY_MISMATCH),
        (
            "holdout_bundle_sha256",
            release.get("holdout_bundle_sha256"),
            GEN4_PHASE7_IDENTITY_MISMATCH,
        ),
        ("evaluation_status", PHASE6_STATUS, GEN4_PHASE7_GOVERNANCE_MISMATCH),
    ):
        _require_equal(marker.get(field), expected, code=code, field=f"marker.{field}")
    _require_equal(
        marker.get("evaluation_result_sha256"),
        result_sha256,
        code=GEN4_PHASE7_CHAIN_MISMATCH,
        field="marker.evaluation_result_sha256",
    )
    _require_true(
        marker.get("result_readback_verified"),
        field="marker.result_readback_verified",
    )
    _require_false(marker.get("retry_allowed"), field="marker.retry_allowed")


def _verify_closure(
    closure: dict[str, Any],
    *,
    release: dict[str, Any],
    contract: dict[str, Any],
    evidence_hashes: dict[str, str],
) -> None:
    for field, expected, code in (
        (
            "schema_version",
            "SUCCESSOR-PHASE6-FINAL-HOLDOUT-CLOSURE-v1",
            GEN4_PHASE7_EVIDENCE_INVALID,
        ),
        (
            "authority",
            "COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE",
            GEN4_PHASE7_EVIDENCE_INVALID,
        ),
        ("status", PHASE6_STATUS, GEN4_PHASE7_GOVERNANCE_MISMATCH),
        ("successor_formal_name", "GENERATION_4", GEN4_PHASE7_IDENTITY_MISMATCH),
        ("holdout_id", release.get("holdout_id"), GEN4_PHASE7_IDENTITY_MISMATCH),
        ("release_id", release.get("release_id"), GEN4_PHASE7_IDENTITY_MISMATCH),
    ):
        _require_equal(
            closure.get(field), expected, code=code, field=f"closure.{field}"
        )
    _verify_identity_fields(
        closure,
        name="closure",
        contract=contract,
        locked_symbols_field="locked_symbols",
    )
    _verify_downstream_methodology(closure, name="closure", contract=contract)
    for field in (
        "phase6_contract_sha256",
        "acquisition_receipt_sha256",
        "release_sha256",
        "evaluation_result_sha256",
        "evaluation_consumption_marker_sha256",
    ):
        _require_equal(
            closure.get(field),
            evidence_hashes[field],
            code=GEN4_PHASE7_CHAIN_MISMATCH,
            field=f"closure.{field}",
        )
    one_time = closure.get("one_time_semantics")
    phase7 = closure.get("phase7")
    if not isinstance(one_time, dict) or not isinstance(phase7, dict):
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "closure.governance"
        )
    _require_true(
        one_time.get("holdout_consumed"),
        field="closure.one_time_semantics.holdout_consumed",
    )
    _require_false(
        one_time.get("retry_authorized"),
        field="closure.one_time_semantics.retry_authorized",
    )
    _require_false(
        one_time.get("symbol_substitution_authorized"),
        field="closure.one_time_semantics.symbol_substitution_authorized",
    )
    _require_true(
        one_time.get("methodology_change_from_holdout_forbidden"),
        field="closure.one_time_semantics.methodology_change_from_holdout_forbidden",
    )
    _require_true(
        one_time.get("parameter_change_from_holdout_forbidden"),
        field="closure.one_time_semantics.parameter_change_from_holdout_forbidden",
    )
    _require_true(
        phase7.get("eligible_for_independent_entry_review"),
        field="closure.phase7.eligible_for_independent_entry_review",
    )
    for field in ("authorized", "entry_artifact_created", "started"):
        _require_false(phase7.get(field), field=f"closure.phase7.{field}")
    _require_false(
        closure.get("production_readiness_approved"),
        field="closure.production_readiness_approved",
    )
    _require_equal(
        closure.get("recon009_status"),
        "OPEN",
        code=GEN4_PHASE7_GOVERNANCE_MISMATCH,
        field="closure.recon009_status",
    )


def verify_generation4_phase7_readiness(
    *,
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
) -> dict[str, Any]:
    raw_contract = _load_object(phase6_contract_path, detail="phase6_contract")
    _verify_contract(raw_contract)
    try:
        contract = verify_phase6_contract(phase6_contract_path)
    except (OSError, ValueError) as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "phase6_contract"
        ) from exc

    try:
        authorization = load_acquisition_authorization(
            authorization_path=acquisition_authorization_path,
            phase6_contract_path=phase6_contract_path,
            selection_path=selection_path,
            virginity_attestation_path=virginity_attestation_path,
            virginity_evidence_path=virginity_evidence_path,
        )
    except SuccessorAcquisitionAuthorityError as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_IDENTITY_MISMATCH, "acquisition_authorization"
        ) from exc
    except (OSError, ValueError) as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "acquisition_authorization"
        ) from exc
    if not isinstance(authorization, SuccessorAcquisitionAuthorizationV2):
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_IDENTITY_MISMATCH, "acquisition_authorization.schema_version"
        )
    _require_equal(
        authorization.schema_version,
        ACQUISITION_AUTHORIZATION_SCHEMA,
        code=GEN4_PHASE7_IDENTITY_MISMATCH,
        field="acquisition_authorization.schema_version",
    )
    for field, actual, expected in (
        ("split_normalizer_sha256", authorization.split_normalizer_sha256, _SPLIT_NORMALIZER_SHA256),
        (
            "dividend_reconciliation_sha256",
            authorization.dividend_reconciliation_sha256,
            _DIVIDEND_RECONCILIATION_SHA256,
        ),
        (
            "successor_evaluator_sha256",
            authorization.successor_evaluator_sha256,
            _SUCCESSOR_EVALUATOR_SHA256,
        ),
        ("paper_only", authorization.paper_only, True),
    ):
        _require_equal(
            actual,
            expected,
            code=GEN4_PHASE7_IDENTITY_MISMATCH,
            field=f"acquisition_authorization.{field}",
        )
    acquisition_authorization_sha256 = _sha(acquisition_authorization_path)
    contract_sha256 = _sha(phase6_contract_path)
    receipt_sha256 = _sha(acquisition_receipt_path)
    release_sha256 = _sha(release_path)
    result_sha256 = _sha(phase6_result_path)
    marker_sha256 = _sha(consumption_marker_path)

    raw_receipt = _load_object(acquisition_receipt_path, detail="receipt")
    _verify_receipt(
        raw_receipt,
        contract=contract,
        contract_sha256=contract_sha256,
        acquisition_authorization_sha256=acquisition_authorization_sha256,
    )
    try:
        receipt = load_receipt(
            acquisition_receipt_path,
            contract_path=phase6_contract_path,
            authorization_path=acquisition_authorization_path,
            selection_path=selection_path,
            virginity_attestation_path=virginity_attestation_path,
            virginity_evidence_path=virginity_evidence_path,
        )
    except (OSError, ValueError, SuccessorAcquisitionAuthorityError) as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "receipt"
        ) from exc

    raw_release = _load_object(release_path, detail="release")
    _verify_release(
        raw_release,
        receipt=receipt,
        contract=contract,
        contract_sha256=contract_sha256,
        receipt_sha256=receipt_sha256,
    )
    try:
        release = load_release(release_path, contract_path=phase6_contract_path)
    except (OSError, ValueError) as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "release"
        ) from exc

    result = _load_object(phase6_result_path, detail="phase6_result")
    _verify_result(
        result,
        release=release,
        contract=contract,
        contract_sha256=contract_sha256,
    )
    marker = _load_object(consumption_marker_path, detail="consumption_marker")
    _verify_marker(
        marker,
        release=release,
        contract=contract,
        contract_sha256=contract_sha256,
        result_sha256=result_sha256,
    )
    closure = _load_object(phase6_closure_path, detail="phase6_closure")
    locked_symbols = list(contract["final_holdout"]["locked_symbols"])
    _verify_closure(
        closure,
        release=release,
        contract=contract,
        evidence_hashes={
            "phase6_contract_sha256": contract_sha256,
            "acquisition_receipt_sha256": receipt_sha256,
            "release_sha256": release_sha256,
            "evaluation_result_sha256": result_sha256,
            "evaluation_consumption_marker_sha256": marker_sha256,
        },
    )

    return {
        "schema_version": READINESS_SCHEMA,
        "status": READINESS_STATUS,
        "generation": "GENERATION_4",
        "candidate_id": _CANDIDATE_ID,
        "binding_sha256": _BINDING_SHA256,
        "implementation_sha256": _IMPLEMENTATION_SHA256,
        "split_normalizer_sha256": _SPLIT_NORMALIZER_SHA256,
        "dividend_reconciliation_sha256": _DIVIDEND_RECONCILIATION_SHA256,
        "successor_evaluator_sha256": _SUCCESSOR_EVALUATOR_SHA256,
        "locked_symbols": locked_symbols,
        "holdout_id": release.get("holdout_id"),
        "release_id": release.get("release_id"),
        "phase6_status": result.get("status"),
        "one_time_consumed": result.get("one_time_consumed"),
        "phase6_contract_sha256": contract_sha256,
        "acquisition_authorization_sha256": acquisition_authorization_sha256,
        "acquisition_receipt_sha256": receipt_sha256,
        "release_sha256": release_sha256,
        "evaluation_result_sha256": result_sha256,
        "evaluation_consumption_marker_sha256": marker_sha256,
        "phase6_closure_sha256": _sha(phase6_closure_path),
        "authority_granted": False,
        "phase7_authorized": False,
        "phase7_started": False,
        "production_readiness_approved": False,
        "live_trading_authorized": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }


_READINESS_BINDING_FIELDS = (
    "candidate_id",
    "binding_sha256",
    "implementation_sha256",
    "split_normalizer_sha256",
    "dividend_reconciliation_sha256",
    "successor_evaluator_sha256",
    "locked_symbols",
    "holdout_id",
    "release_id",
    "phase6_contract_sha256",
    "acquisition_authorization_sha256",
    "acquisition_receipt_sha256",
    "release_sha256",
    "evaluation_result_sha256",
    "evaluation_consumption_marker_sha256",
    "phase6_closure_sha256",
    "phase6_status",
    "one_time_consumed",
)


def _load_audit_request(path: Path) -> _Generation4Phase7AuditRequest:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return _Generation4Phase7AuditRequest.model_validate(raw)
    except Exception as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_AUTHORIZATION_INVALID, "audit_request"
        ) from exc


def load_generation4_phase7_authorization(
    *,
    authorization_path: Path,
    audit_request_path: Path,
    phase7_entry_path: Path,
    phase7_cli_path: Path,
    readiness: dict[str, Any],
) -> Generation4Phase7Authorization:
    if not Path(authorization_path).is_file():
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_AUTHORIZATION_MISSING, "authorization"
        )
    request = _load_audit_request(audit_request_path)
    try:
        request_sha256 = _sha(audit_request_path)
        gate_sha256 = _sha(phase7_entry_path)
        cli_sha256 = _sha(phase7_cli_path)
    except OSError as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_AUTHORIZATION_INVALID, "authorization_binding_source"
        ) from exc

    for field in _READINESS_BINDING_FIELDS:
        actual = getattr(request, field)
        if field == "locked_symbols":
            actual = list(actual)
        _require_equal(
            actual,
            readiness.get(field),
            code=GEN4_PHASE7_AUTHORIZATION_MISMATCH,
            field=f"audit_request.{field}",
        )
    for field, actual, expected in (
        (
            "phase7_gate_implementation_sha256",
            request.phase7_gate_implementation_sha256,
            gate_sha256,
        ),
        (
            "phase7_cli_implementation_sha256",
            request.phase7_cli_implementation_sha256,
            cli_sha256,
        ),
    ):
        _require_equal(
            actual,
            expected,
            code=GEN4_PHASE7_AUTHORIZATION_MISMATCH,
            field=f"audit_request.{field}",
        )

    try:
        raw_authorization = json.loads(
            Path(authorization_path).read_text(encoding="utf-8")
        )
        authorization = Generation4Phase7Authorization.model_validate(
            raw_authorization
        )
    except Exception as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_AUTHORIZATION_INVALID, "authorization"
        ) from exc

    for field in _READINESS_BINDING_FIELDS:
        actual = getattr(authorization, field)
        if field == "locked_symbols":
            actual = list(actual)
        _require_equal(
            actual,
            readiness.get(field),
            code=GEN4_PHASE7_AUTHORIZATION_MISMATCH,
            field=f"authorization.{field}",
        )
    for field, actual, expected in (
        (
            "implementation_commit",
            authorization.implementation_commit,
            request.implementation_commit,
        ),
        (
            "audit_request_sha256",
            authorization.audit_request_sha256,
            request_sha256,
        ),
        (
            "phase7_gate_implementation_sha256",
            authorization.phase7_gate_implementation_sha256,
            gate_sha256,
        ),
        (
            "phase7_cli_implementation_sha256",
            authorization.phase7_cli_implementation_sha256,
            cli_sha256,
        ),
    ):
        _require_equal(
            actual,
            expected,
            code=GEN4_PHASE7_AUTHORIZATION_MISMATCH,
            field=f"authorization.{field}",
        )
    return authorization


def evaluate_generation4_phase7_entry(
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
    phase7_cli_path: Path | None = None,
) -> dict[str, Any]:
    readiness = verify_generation4_phase7_readiness(
        phase6_contract_path=phase6_contract_path,
        acquisition_authorization_path=acquisition_authorization_path,
        selection_path=selection_path,
        virginity_attestation_path=virginity_attestation_path,
        virginity_evidence_path=virginity_evidence_path,
        acquisition_receipt_path=acquisition_receipt_path,
        release_path=release_path,
        phase6_result_path=phase6_result_path,
        consumption_marker_path=consumption_marker_path,
        phase6_closure_path=phase6_closure_path,
    )
    entry_source = (
        Path(phase7_entry_path) if phase7_entry_path is not None else Path(__file__)
    )
    cli_source = (
        Path(phase7_cli_path)
        if phase7_cli_path is not None
        else Path(__file__).with_name("phase7_entry_cli.py")
    )
    authorization = load_generation4_phase7_authorization(
        authorization_path=authorization_path,
        audit_request_path=audit_request_path,
        phase7_entry_path=entry_source,
        phase7_cli_path=cli_source,
        readiness=readiness,
    )
    report = {
        "schema_version": "GENERATION4-PHASE7-ENTRY-DECISION-v1",
        "status": "GENERATION4_PHASE7_ENTRY_ALLOWED",
        "authorization_id": authorization.authorization_id,
        "implementation_commit": authorization.implementation_commit,
        "audit_request_sha256": authorization.audit_request_sha256,
        "candidate_id": readiness["candidate_id"],
        "holdout_id": readiness["holdout_id"],
        "release_id": readiness["release_id"],
        "phase7_entry_authorized": True,
        "phase7_started": False,
        "production_readiness_approved": False,
        "live_trading_authorized": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }
    report.update(
        {field: readiness[field] for field in _READINESS_BINDING_FIELDS if field.endswith("_sha256")}
    )
    return report
