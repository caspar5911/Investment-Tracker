from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from pydantic import ValidationError

PREFLIGHT_SCHEMA = "GENERATION4-PHASE7-EVALUATION-PREFLIGHT-v1"
PREFLIGHT_STATUS = "GENERATION4_PHASE7_EVALUATION_PREFLIGHT_READY"

GEN4_PHASE7_EVAL_BOUNDARY_INVALID = "GEN4_PHASE7_EVAL_BOUNDARY_INVALID"
GEN4_PHASE7_EVAL_BOUNDARY_UNRESOLVED = "GEN4_PHASE7_EVAL_BOUNDARY_UNRESOLVED"
GEN4_PHASE7_EVAL_EVIDENCE_INVALID = "GEN4_PHASE7_EVAL_EVIDENCE_INVALID"
GEN4_PHASE7_EVAL_START_ARTIFACT_INVALID = "GEN4_PHASE7_EVAL_START_ARTIFACT_INVALID"
GEN4_PHASE7_EVAL_START_CONTRACT_INVALID = "GEN4_PHASE7_EVAL_START_CONTRACT_INVALID"
GEN4_PHASE7_EVAL_CONTRACT_MISSING = "GEN4_PHASE7_EVAL_CONTRACT_MISSING"
GEN4_PHASE7_EVAL_CONTRACT_INVALID = "GEN4_PHASE7_EVAL_CONTRACT_INVALID"
GEN4_PHASE7_EVAL_BINDING_MISMATCH = "GEN4_PHASE7_EVAL_BINDING_MISMATCH"
GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH = "GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH"

_START_SCHEMA = "GENERATION4-PHASE7-START-v1"
_START_STATUS = "GENERATION4_PHASE7_STARTED"
_START_CONTRACT_SCHEMA = "GENERATION4-PHASE7-START-CONTRACT-v1"
_START_CONTRACT_STATUS = "FROZEN_PRE_START"
_AUTHORITY = "COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION"
_PHASE6_STATUS = "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"

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

_RESEARCH_UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
_FORBIDDEN_HOLDOUT_SHA256 = (
    "1f7880217a7679df2513551372d8abe1b81c63d13ab6c729077c017186ba80b7"
)
_BENCHMARK_SYMBOL = "SPY"
_FRICTION_CASES_BPS = (0, 3, 10, 25, 50)
_PRIMARY_FRICTION_BPS = 3
_INITIAL_CASH = 100_000.0
_WARMUP_SESSION_LIMIT = 210
_CHECKPOINT_SESSIONS = (63, 126, 252)

_EXPECTED_IDENTITY: dict[str, str] = {
    "candidate_id": _CANDIDATE_ID,
    "binding_sha256": _BINDING_SHA256,
    "implementation_sha256": _IMPLEMENTATION_SHA256,
    "split_normalizer_sha256": _SPLIT_NORMALIZER_SHA256,
    "dividend_reconciliation_sha256": _DIVIDEND_RECONCILIATION_SHA256,
    "successor_evaluator_sha256": _SUCCESSOR_EVALUATOR_SHA256,
}

_START_ARTIFACT_GOVERNANCE: dict[str, object] = {
    "phase7_entry_authorized": True,
    "phase7_started": True,
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
    "phase6_status": _PHASE6_STATUS,
    "one_time_consumed": True,
    "recon009_status": "OPEN",
    "paper_only": True,
}

_START_CONTRACT_GOVERNANCE: dict[str, object] = {
    **_START_ARTIFACT_GOVERNANCE,
    "phase7_started": False,
}

_EVALUATION_GOVERNANCE: dict[str, object] = {
    "phase7_started": True,
    "phase7_performance_evaluation_authorized": False,
    "production_readiness_approved": False,
    "live_trading_authorized": False,
    "holdout_reuse_authorized": False,
    "candidate_search_authorized": False,
    "parameter_mutation_authorized": False,
    "symbol_substitution_authorized": False,
    "adaptive_walk_forward_authorized": False,
    "annual_reoptimization_authorized": False,
    "result_dependent_methodology_change_allowed": False,
    "result_dependent_parameter_change_allowed": False,
    "recon009_status": "OPEN",
    "paper_only": True,
}

_ARTIFACT_START_CONTRACT_FIELDS: tuple[str, ...] = (
    "authorization_id",
    "entry_authorization_sha256",
    "audit_request_sha256",
    "holdout_id",
    "release_id",
    "locked_symbols",
    "phase6_status",
    "one_time_consumed",
    "phase6_contract_sha256",
    "acquisition_authorization_sha256",
    "acquisition_receipt_sha256",
    "release_sha256",
    "evaluation_result_sha256",
    "evaluation_consumption_marker_sha256",
    "phase6_closure_sha256",
    "phase7_entry_implementation_commit",
    "phase7_entry_source_sha256",
    "phase7_entry_cli_source_sha256",
    "phase7_start_implementation_commit",
    "phase7_start_source_sha256",
    "phase7_start_cli_source_sha256",
)

_EVALUATION_START_ARTIFACT_FIELDS: tuple[str, ...] = (
    "phase7_entry_implementation_commit",
    "phase7_entry_source_sha256",
    "phase7_entry_cli_source_sha256",
    "phase7_start_implementation_commit",
    "phase7_start_source_sha256",
    "phase7_start_cli_source_sha256",
)


class Generation4Phase7EvaluationError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


class Generation4Phase7EvaluationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["GENERATION4-PHASE7-EVALUATION-CONTRACT-v1"]
    status: Literal["FROZEN_PRE_EVALUATION"]
    authority: Literal[_AUTHORITY]
    generation: Literal["GENERATION_4"]
    candidate_id: str = Field(min_length=1)
    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    split_normalizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dividend_reconciliation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_artifact_self_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    entry_authorization_id: str = Field(min_length=1)
    entry_authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_entry_implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    phase7_entry_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_entry_cli_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_start_implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    phase7_start_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_start_cli_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_evaluation_implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    phase7_evaluation_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_evaluation_cli_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    research_universe: tuple[str, ...]
    forbidden_holdout_symbols: tuple[str, ...]
    benchmark_symbol: str = Field(min_length=1)
    initial_cash: float = Field(gt=0)
    friction_cases_bps: tuple[int, ...]
    primary_friction_bps: int
    prospective_first_scored_session: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    warmup_session_limit: int = Field(gt=0)
    checkpoint_sessions: tuple[int, ...]
    historical_lane_classification: Literal["REUSED_HISTORY_DIAGNOSTIC_ONLY"]
    dq030_status: Literal["UNRESOLVED"]
    phase7_started: StrictBool
    phase7_performance_evaluation_authorized: StrictBool
    production_readiness_approved: StrictBool
    live_trading_authorized: StrictBool
    holdout_reuse_authorized: StrictBool
    candidate_search_authorized: StrictBool
    parameter_mutation_authorized: StrictBool
    symbol_substitution_authorized: StrictBool
    adaptive_walk_forward_authorized: StrictBool
    annual_reoptimization_authorized: StrictBool
    result_dependent_methodology_change_allowed: StrictBool
    result_dependent_parameter_change_allowed: StrictBool
    recon009_status: str = Field(min_length=1)
    paper_only: StrictBool


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_json_object(
    path: Path, code: str, detail: str
) -> dict[str, Any]:
    if not path.is_file():
        raise Generation4Phase7EvaluationError(code, f"{detail}:missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise Generation4Phase7EvaluationError(code, f"{detail}:unreadable")
    if not isinstance(payload, dict):
        raise Generation4Phase7EvaluationError(code, f"{detail}:not_object")
    return payload


def _require_value(
    payload: dict[str, Any], field: str, expected: object, code: str
) -> None:
    actual = payload.get(field)
    match = actual is expected if isinstance(expected, bool) else actual == expected
    if not match:
        raise Generation4Phase7EvaluationError(code, field)


def _verify_header(
    payload: dict[str, Any], expected: dict[str, str], code: str
) -> None:
    for field, value in expected.items():
        if payload.get(field) != value:
            raise Generation4Phase7EvaluationError(code, field)


def _verify_governance(payload: dict[str, Any], expectations: dict[str, object]) -> None:
    for field, expected in expectations.items():
        _require_value(payload, field, expected, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


def _verify_start_artifact(payload: dict[str, Any]) -> None:
    _verify_header(
        payload,
        {"schema_version": _START_SCHEMA, "status": _START_STATUS, "authority": _AUTHORITY},
        GEN4_PHASE7_EVAL_START_ARTIFACT_INVALID,
    )
    self_hash = payload.get("artifact_sha256")
    if not isinstance(self_hash, str):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_EVIDENCE_INVALID, "start_artifact.artifact_sha256"
        )
    body = {key: value for key, value in payload.items() if key != "artifact_sha256"}
    if sha256(_canonical_json(body)).hexdigest() != self_hash:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_EVIDENCE_INVALID, "start_artifact.artifact_sha256"
        )
    if "metrics" in payload:
        raise Generation4Phase7EvaluationError(GEN4_PHASE7_EVAL_EVIDENCE_INVALID, "metrics")


def _load_evaluation_contract(
    path: Path,
) -> Generation4Phase7EvaluationContract:
    if not path.is_file():
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_CONTRACT_MISSING, "evaluation_contract"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_CONTRACT_INVALID, "evaluation_contract:unreadable"
        )
    try:
        return Generation4Phase7EvaluationContract.model_validate(payload)
    except ValidationError:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_CONTRACT_INVALID, "evaluation_contract"
        )


def _mismatch(field: str) -> Generation4Phase7EvaluationError:
    return Generation4Phase7EvaluationError(
        GEN4_PHASE7_EVAL_BINDING_MISMATCH, f"evaluation_contract.{field}"
    )


def _verify_evaluation_bindings(
    contract: Generation4Phase7EvaluationContract,
    artifact: dict[str, Any],
    start_artifact_path: Path,
    start_contract_path: Path,
) -> None:
    if contract.start_artifact_sha256 != _sha(start_artifact_path):
        raise _mismatch("start_artifact_sha256")
    if contract.start_artifact_self_hash != artifact.get("artifact_sha256"):
        raise _mismatch("start_artifact_self_hash")
    if contract.start_contract_sha256 != _sha(start_contract_path):
        raise _mismatch("start_contract_sha256")
    if contract.entry_authorization_id != artifact.get("authorization_id"):
        raise _mismatch("entry_authorization_id")
    if contract.entry_authorization_sha256 != artifact.get("entry_authorization_sha256"):
        raise _mismatch("entry_authorization_sha256")
    for field in _EVALUATION_START_ARTIFACT_FIELDS:
        if getattr(contract, field) != artifact.get(field):
            raise _mismatch(field)
    for field, expected in _EXPECTED_IDENTITY.items():
        if getattr(contract, field) != expected:
            raise _mismatch(field)
    if contract.research_universe != _RESEARCH_UNIVERSE:
        raise _mismatch("research_universe")
    if sha256(
        _canonical_json(list(contract.forbidden_holdout_symbols))
    ).hexdigest() != _FORBIDDEN_HOLDOUT_SHA256:
        raise _mismatch("forbidden_holdout_symbols")
    if contract.benchmark_symbol != _BENCHMARK_SYMBOL:
        raise _mismatch("benchmark_symbol")
    if contract.initial_cash != _INITIAL_CASH:
        raise _mismatch("initial_cash")
    if contract.friction_cases_bps != _FRICTION_CASES_BPS:
        raise _mismatch("friction_cases_bps")
    if contract.primary_friction_bps != _PRIMARY_FRICTION_BPS:
        raise _mismatch("primary_friction_bps")
    if contract.warmup_session_limit != _WARMUP_SESSION_LIMIT:
        raise _mismatch("warmup_session_limit")
    if contract.checkpoint_sessions != _CHECKPOINT_SESSIONS:
        raise _mismatch("checkpoint_sessions")


def verify_generation4_phase7_evaluation_preflight(
    *,
    start_artifact_path: Path,
    start_contract_path: Path,
    evaluation_contract_path: Path,
) -> dict[str, Any]:
    artifact = _load_json_object(
        start_artifact_path, GEN4_PHASE7_EVAL_EVIDENCE_INVALID, "start_artifact"
    )
    _verify_start_artifact(artifact)
    _verify_governance(artifact, _START_ARTIFACT_GOVERNANCE)

    start_contract = _load_json_object(
        start_contract_path, GEN4_PHASE7_EVAL_START_CONTRACT_INVALID, "start_contract"
    )
    _verify_header(
        start_contract,
        {
            "schema_version": _START_CONTRACT_SCHEMA,
            "status": _START_CONTRACT_STATUS,
            "authority": _AUTHORITY,
        },
        GEN4_PHASE7_EVAL_START_CONTRACT_INVALID,
    )
    _verify_governance(start_contract, _START_CONTRACT_GOVERNANCE)

    for field, expected in _EXPECTED_IDENTITY.items():
        _require_value(
            artifact, field, expected, GEN4_PHASE7_EVAL_BINDING_MISMATCH
        )
        _require_value(
            start_contract, field, expected, GEN4_PHASE7_EVAL_BINDING_MISMATCH
        )

    for field in _ARTIFACT_START_CONTRACT_FIELDS:
        if artifact.get(field) != start_contract.get(field):
            raise Generation4Phase7EvaluationError(
                GEN4_PHASE7_EVAL_BINDING_MISMATCH, f"start:{field}"
            )
    if artifact.get("start_contract_sha256") != _sha(start_contract_path):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "start_artifact.start_contract_sha256"
        )

    contract = _load_evaluation_contract(evaluation_contract_path)
    _verify_evaluation_bindings(
        contract, artifact, start_artifact_path, start_contract_path
    )
    _verify_governance(contract.model_dump(), _EVALUATION_GOVERNANCE)

    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": PREFLIGHT_STATUS,
        "generation": contract.generation,
        "start_artifact_sha256": contract.start_artifact_sha256,
        "start_artifact_self_hash": contract.start_artifact_self_hash,
        "start_contract_sha256": contract.start_contract_sha256,
        "evaluation_contract_sha256": _sha(evaluation_contract_path),
        "start_artifact_started_at_utc": artifact.get("started_at_utc"),
        "entry_authorization_id": contract.entry_authorization_id,
        "entry_authorization_sha256": contract.entry_authorization_sha256,
        "candidate_id": contract.candidate_id,
        "binding_sha256": contract.binding_sha256,
        "implementation_sha256": contract.implementation_sha256,
        "split_normalizer_sha256": contract.split_normalizer_sha256,
        "dividend_reconciliation_sha256": contract.dividend_reconciliation_sha256,
        "successor_evaluator_sha256": contract.successor_evaluator_sha256,
        "phase7_entry_implementation_commit": contract.phase7_entry_implementation_commit,
        "phase7_start_implementation_commit": contract.phase7_start_implementation_commit,
        "phase7_evaluation_implementation_commit": contract.phase7_evaluation_implementation_commit,
        "research_universe": list(contract.research_universe),
        "forbidden_holdout_symbols_sha256": _FORBIDDEN_HOLDOUT_SHA256,
        "benchmark_symbol": contract.benchmark_symbol,
        "initial_cash": contract.initial_cash,
        "friction_cases_bps": list(contract.friction_cases_bps),
        "primary_friction_bps": contract.primary_friction_bps,
        "prospective_first_scored_session": contract.prospective_first_scored_session,
        "warmup_session_limit": contract.warmup_session_limit,
        "checkpoint_sessions": list(contract.checkpoint_sessions),
        "historical_lane_classification": contract.historical_lane_classification,
        "dq030_status": contract.dq030_status,
        "phase7_started": contract.phase7_started,
        "phase7_performance_evaluation_authorized": contract.phase7_performance_evaluation_authorized,
        "production_readiness_approved": contract.production_readiness_approved,
        "live_trading_authorized": contract.live_trading_authorized,
        "holdout_reuse_authorized": contract.holdout_reuse_authorized,
        "candidate_search_authorized": contract.candidate_search_authorized,
        "parameter_mutation_authorized": contract.parameter_mutation_authorized,
        "symbol_substitution_authorized": contract.symbol_substitution_authorized,
        "adaptive_walk_forward_authorized": contract.adaptive_walk_forward_authorized,
        "annual_reoptimization_authorized": contract.annual_reoptimization_authorized,
        "result_dependent_methodology_change_allowed": contract.result_dependent_methodology_change_allowed,
        "result_dependent_parameter_change_allowed": contract.result_dependent_parameter_change_allowed,
        "recon009_status": contract.recon009_status,
        "paper_only": contract.paper_only,
    }


PROSPECTIVE_BOUNDARY_SCHEMA = "GENERATION4-PHASE7-PROSPECTIVE-BOUNDARY-v1"


def _parse_start_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BOUNDARY_INVALID, "started_at_utc"
        ) from None
    if parsed.tzinfo is None:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BOUNDARY_INVALID, "started_at_utc"
        )
    return parsed.astimezone(timezone.utc)


def resolve_generation4_phase7_prospective_boundary(
    *,
    sessions: Sequence[str],
    started_at_utc: str,
    warmup_session_limit: int = _WARMUP_SESSION_LIMIT,
) -> dict[str, Any]:
    if isinstance(warmup_session_limit, bool) or not isinstance(
        warmup_session_limit, int
    ):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BOUNDARY_INVALID, "warmup_session_limit"
        )
    if not 1 <= warmup_session_limit <= _WARMUP_SESSION_LIMIT:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BOUNDARY_INVALID, "warmup_session_limit"
        )
    started = _parse_start_timestamp(started_at_utc)
    if not sessions:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BOUNDARY_INVALID, "sessions"
        )
    parsed_sessions: list[date] = []
    for value in sessions:
        if not isinstance(value, str):
            raise Generation4Phase7EvaluationError(
                GEN4_PHASE7_EVAL_BOUNDARY_INVALID, "sessions"
            )
        try:
            parsed_sessions.append(date.fromisoformat(value))
        except ValueError:
            raise Generation4Phase7EvaluationError(
                GEN4_PHASE7_EVAL_BOUNDARY_INVALID, "sessions"
            ) from None
    for previous, current in zip(parsed_sessions, parsed_sessions[1:]):
        if current <= previous:
            raise Generation4Phase7EvaluationError(
                GEN4_PHASE7_EVAL_BOUNDARY_INVALID, "sessions"
            )
    scored_index: int | None = None
    for index, session in enumerate(parsed_sessions):
        if (
            datetime(
                session.year, session.month, session.day, tzinfo=timezone.utc
            )
            > started
        ):
            scored_index = index
            break
    if scored_index is None:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BOUNDARY_UNRESOLVED, "first_scored_session"
        )
    warmup_session_count = min(scored_index, warmup_session_limit)
    warmup_boundary_session = (
        sessions[scored_index - warmup_session_count]
        if warmup_session_count
        else None
    )
    first_scored_session = sessions[scored_index]
    return {
        "schema_version": PROSPECTIVE_BOUNDARY_SCHEMA,
        "generation": "GENERATION_4",
        "started_at_utc": started_at_utc,
        "first_scored_session": first_scored_session,
        "scored_boundary_session": first_scored_session,
        "warmup_boundary_session": warmup_boundary_session,
        "warmup_session_limit": warmup_session_limit,
        "warmup_session_count": warmup_session_count,
        "warmup_excluded_from_scored_pnl": True,
    }
