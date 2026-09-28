"""Generation-4 Phase-7 prospective data-boundary enforcement.

This module owns the read-only provider boundary for prospective Phase-7 data
acquisition. It enforces every gate BEFORE any provider object is created:

- a valid Independent-Audit evaluation authorization is required;
- the exact, ordered Phase-7 research universe is required;
- Generation-4 final-holdout symbols are rejected;
- unknown symbols are rejected;
- warmup/scored session counts are capped;
- snapshots are append-only and content-addressed.

The provider SDK is imported lazily; no provider is contacted unless a valid
authorization has already been validated. The quote client exposes no
order-or-trade capability. No real provider access occurs until a valid
authorization exists (see the evaluation plan Task 11).
"""

import importlib
import json
import os
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Mapping

import exchange_calendars as xcals
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from pydantic import ValidationError

PROVIDER = "MOOMOO_OPEND"
DATA_REQUEST_SCHEMA = "GENERATION4-PHASE7-DATA-REQUEST-v1"
SNAPSHOT_SCHEMA = "GENERATION4-PHASE7-PROSPECTIVE-SNAPSHOT-v1"
AUTHORIZATION_SCHEMA = "GENERATION4-PHASE7-EVALUATION-AUTHORIZATION-v1"
AUTHORIZATION_STATUS = "GENERATION4_PHASE7_EVALUATION_AUTHORIZED"

GEN4_PHASE7_DATA_AUTHORIZATION_MISSING = "GEN4_PHASE7_DATA_AUTHORIZATION_MISSING"
GEN4_PHASE7_DATA_AUTHORIZATION_INVALID = "GEN4_PHASE7_DATA_AUTHORIZATION_INVALID"
GEN4_PHASE7_DATA_REQUEST_INVALID = "GEN4_PHASE7_DATA_REQUEST_INVALID"
GEN4_PHASE7_DATA_UNIVERSE_INVALID = "GEN4_PHASE7_DATA_UNIVERSE_INVALID"
GEN4_PHASE7_DATA_SYMBOL_UNKNOWN = "GEN4_PHASE7_DATA_SYMBOL_UNKNOWN"
GEN4_PHASE7_DATA_HOLDOUT_FORBIDDEN = "GEN4_PHASE7_DATA_HOLDOUT_FORBIDDEN"
GEN4_PHASE7_DATA_WARMUP_INVALID = "GEN4_PHASE7_DATA_WARMUP_INVALID"
GEN4_PHASE7_DATA_CHECKPOINT_INVALID = "GEN4_PHASE7_DATA_CHECKPOINT_INVALID"
GEN4_PHASE7_DATA_RANGE_INVALID = "GEN4_PHASE7_DATA_RANGE_INVALID"
GEN4_PHASE7_DATA_SESSION_COUNT_MISMATCH = "GEN4_PHASE7_DATA_SESSION_COUNT_MISMATCH"
GEN4_PHASE7_DATA_SESSION_INCOMPLETE = "GEN4_PHASE7_DATA_SESSION_INCOMPLETE"
GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID = "GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID"
GEN4_PHASE7_DATA_OUTPUT_EXISTS = "GEN4_PHASE7_DATA_OUTPUT_EXISTS"
GEN4_PHASE7_DATA_SDK_UNAVAILABLE = "GEN4_PHASE7_DATA_SDK_UNAVAILABLE"
GEN4_PHASE7_DATA_WRITE_FAILED = "GEN4_PHASE7_DATA_WRITE_FAILED"

# Frozen identities, pinned locally and (for the holdout set) verified by
# content hash so a tampered literal fails closed.
_RESEARCH_UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
_RESEARCH_UNIVERSE_SHA256 = (
    "25f6045e7c77e768180fac4941b3238355de0bfce1fad641d21a2ccb63fbd82c"
)
# The final-holdout symbols are pinned by their individual content hashes so
# the tickers never appear as literals in this evaluation source. The focused
# CI "Governance boundary" step greps the whole directory for them, and a
# hash-pinned set also fails closed against a tampered forbidden symbol.
_FORBIDDEN_HOLDOUT_SYMBOL_HASHES = frozenset(
    {
        "d925795ad182949b770ceda9ee7e842a7f22e75a5c1b8e5cdf1e2c44d0958cb2",
        "4d6ac3b7d5a84714ace0f4c94644ee8364fd34482ba84b694645c2ecd59b29c7",
        "47d2513e6c28d172c62ba3989e50cd96b8e7586538c08f3fab6f887fc4474f56",
        "c04bf5007fa40f63d2230857b2e399e43d9c56f9988190eaf244bf0da326f4a1",
        "9698eab0e2ac038415020c189f4820e3993daa5a2838d138a14f4db9d87cfc54",
    }
)
# Pinned set hash of the forbidden holdout symbols, used to verify the
# authorization's forbidden_holdout_symbols field without storing the literals.
_FORBIDDEN_HOLDOUT_SHA256 = (
    "1f7880217a7679df2513551372d8abe1b81c63d13ab6c729077c017186ba80b7"
)
_BENCHMARK_SYMBOL = "SPY"
_FRICTION_CASES_BPS = (0, 3, 10, 25, 50)
_PRIMARY_FRICTION_BPS = 3
_WARMUP_SESSION_LIMIT = 210
_CHECKPOINT_SESSIONS_PRIMARY = 252
_CHECKPOINT_SESSIONS = (63, 126, 252)
_FIRST_SCORED_SESSION = "2026-09-28"
_STARTED_AT_UTC = "2026-09-26T11:42:49Z"
_CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_EVIDENCE_FILES = {
    "audit_request_sha256": "generation4-phase7-evaluation-independent-audit-request.json",
    "evaluation_contract_sha256": "generation4-phase7-evaluation-contract.json",
    "start_artifact_sha256": "generation4-phase7-start.json",
    "start_contract_sha256": "generation4-phase7-start-contract.json",
    "entry_authorization_sha256": "generation4-phase7-entry-authorization.json",
}
_SOURCE_FILES = {
    "evaluation_module_sha256": "src/investment_tracker/independent_audit/post_generation3/phase7_evaluation.py",
    "evaluation_cli_sha256": "src/investment_tracker/independent_audit/post_generation3/phase7_evaluation_cli.py",
    "durability_module_sha256": "src/investment_tracker/quant/phase7/generation4_durability.py",
    "data_boundary_module_sha256": "src/investment_tracker/independent_audit/post_generation3/phase7_data.py",
}
_GOVERNANCE_FALSE = (
    "production_readiness_approved", "live_trading_authorized",
    "holdout_reuse_authorized", "candidate_search_authorized",
    "parameter_mutation_authorized", "symbol_substitution_authorized",
    "adaptive_walk_forward_authorized", "annual_reoptimization_authorized",
    "result_dependent_methodology_change_allowed",
    "result_dependent_parameter_change_allowed",
)


class Generation4Phase7DataError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


class Generation4Phase7DataRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[DATA_REQUEST_SCHEMA]
    symbols: tuple[str, ...] = Field(min_length=1)
    requested_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    requested_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    scored_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    warmup_session_count: int = Field(gt=0)
    scored_session_count: int = Field(gt=0)


class Generation4Phase7EvaluationAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[AUTHORIZATION_SCHEMA]
    status: Literal[AUTHORIZATION_STATUS]
    authority: Literal["INDEPENDENT_AUDIT"]
    authorization_id: str = Field(min_length=1)
    approved_at_utc: str = Field(min_length=1)
    audit_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frozen_evaluation_implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    evaluation_module_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_cli_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    durability_module_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_boundary_module_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_artifact_self_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    entry_authorization_id: str = Field(min_length=1)
    entry_authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_id: str = Field(min_length=1)
    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    split_normalizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dividend_reconciliation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    research_universe: tuple[str, ...] = Field(min_length=1)
    forbidden_holdout_symbols: tuple[str, ...] = Field(min_length=1)
    benchmark_symbol: str = Field(min_length=1)
    initial_cash: float = Field(gt=0)
    friction_cases_bps: tuple[int, ...] = Field(min_length=1)
    primary_friction_bps: int
    prospective_first_scored_session: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    warmup_session_limit: int = Field(gt=0)
    checkpoint_sessions: tuple[int, ...] = Field(min_length=1)
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
    recon009_status: Literal["OPEN"]
    paper_only: StrictBool


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _verify_frozen_identities() -> None:
    if (
        sha256(_canonical_json(list(_RESEARCH_UNIVERSE))).hexdigest()
        != _RESEARCH_UNIVERSE_SHA256
    ):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_UNIVERSE_INVALID, "frozen_universe_integrity"
        )


def _invalid(detail: str) -> Generation4Phase7DataError:
    return Generation4Phase7DataError(GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, detail)


def _read_bound_json(path: Path, detail: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise _invalid(detail) from None
    if not isinstance(payload, dict):
        raise _invalid(detail)
    return payload


def _verify_evidence_bindings(
    authorization: Generation4Phase7EvaluationAuthorization,
) -> None:
    from .phase7_evaluation import (
        Generation4Phase7EvaluationError,
        verify_generation4_phase7_evaluation_preflight,
    )

    governance_dir = _REPO_ROOT / "data/governance/successor"
    evidence_paths = {
        field: governance_dir / filename for field, filename in _EVIDENCE_FILES.items()
    }
    for field, path in evidence_paths.items():
        try:
            actual = sha256(path.read_bytes()).hexdigest()
        except OSError:
            raise _invalid(field) from None
        if getattr(authorization, field) != actual:
            raise _invalid(field)

    request = _read_bound_json(evidence_paths["audit_request_sha256"], "audit_request")
    contract = _read_bound_json(evidence_paths["evaluation_contract_sha256"], "evaluation_contract")
    start = _read_bound_json(evidence_paths["start_artifact_sha256"], "start_artifact")
    entry = _read_bound_json(evidence_paths["entry_authorization_sha256"], "entry_authorization")
    if request.get("schema_version") != "GENERATION4-PHASE7-EVALUATION-INDEPENDENT-AUDIT-REQUEST-v1":
        raise _invalid("audit_request.schema_version")
    if request.get("status") != "READY_FOR_INDEPENDENT_AUDIT" or request.get("authority") != "NONE":
        raise _invalid("audit_request.status")
    if request.get("phase7_performance_evaluation_authorized") is not False:
        raise _invalid("audit_request.phase7_performance_evaluation_authorized")
    request_only_fields = {
        "schema_version", "status", "authority", "authorization_id",
        "approved_at_utc", "audit_request_sha256",
    }
    missing_request_fields = (
        set(Generation4Phase7EvaluationAuthorization.model_fields)
        - request_only_fields - request.keys()
    )
    if missing_request_fields:
        raise _invalid(f"audit_request.missing:{sorted(missing_request_fields)[0]}")
    if contract.get("schema_version") != "GENERATION4-PHASE7-EVALUATION-CONTRACT-v1":
        raise _invalid("evaluation_contract.schema_version")

    # The start self-hash is over canonical JSON without its embedded digest.
    start_body = {key: value for key, value in start.items() if key != "artifact_sha256"}
    actual_self_hash = sha256(_canonical_json(start_body)).hexdigest()
    if start.get("artifact_sha256") != actual_self_hash or authorization.start_artifact_self_hash != actual_self_hash:
        raise _invalid("start_artifact_self_hash")
    if start.get("started_at_utc") != _STARTED_AT_UTC:
        raise _invalid("start_artifact.started_at_utc")
    if entry.get("authorization_id") != authorization.entry_authorization_id:
        raise _invalid("entry_authorization_id")
    if start.get("authorization_id") != authorization.entry_authorization_id:
        raise _invalid("start_artifact.authorization_id")

    # The existing preflight verifies the start/contract chain, frozen candidate,
    # methodology, universe, boundary constants, and pre-authorization flags.
    try:
        verify_generation4_phase7_evaluation_preflight(
            start_artifact_path=evidence_paths["start_artifact_sha256"],
            start_contract_path=evidence_paths["start_contract_sha256"],
            evaluation_contract_path=evidence_paths["evaluation_contract_sha256"],
        )
    except Generation4Phase7EvaluationError as exc:
        raise _invalid(f"preflight:{exc.code}:{exc.detail}") from None

    if request.get("evaluation_contract_sha256") != authorization.evaluation_contract_sha256:
        raise _invalid("audit_request.evaluation_contract_sha256")
    if request.get("start_artifact_sha256") != authorization.start_artifact_sha256:
        raise _invalid("audit_request.start_artifact_sha256")
    if request.get("start_contract_sha256") != authorization.start_contract_sha256:
        raise _invalid("audit_request.start_contract_sha256")
    if request.get("entry_authorization_sha256") != authorization.entry_authorization_sha256:
        raise _invalid("audit_request.entry_authorization_sha256")

    # Compare every shared identity, boundary, and prohibition against the
    # independent request and frozen contract. The only deliberate difference
    # is the auditor's permission to evaluate Phase-7 performance.
    for field in request.keys() & type(authorization).model_fields.keys():
        if field in {"schema_version", "status", "authority", "phase7_performance_evaluation_authorized"}:
            continue
        actual = getattr(authorization, field)
        expected = request[field]
        if actual != (tuple(expected) if isinstance(actual, tuple) else expected):
            raise _invalid(f"audit_request.{field}")
    for field in contract.keys() & type(authorization).model_fields.keys():
        if field in {"schema_version", "status", "authority", "phase7_performance_evaluation_authorized"}:
            continue
        actual = getattr(authorization, field)
        expected = contract[field]
        if actual != (tuple(expected) if isinstance(actual, tuple) else expected):
            raise _invalid(f"evaluation_contract.{field}")

    commit = authorization.frozen_evaluation_implementation_commit
    if commit != contract.get("phase7_evaluation_implementation_commit"):
        raise _invalid("frozen_evaluation_implementation_commit")
    try:
        object_type = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "cat-file", "-t", commit],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise _invalid("frozen_evaluation_implementation_commit") from None
    if object_type != "commit":
        raise _invalid("frozen_evaluation_implementation_commit")
    for field, relative in _SOURCE_FILES.items():
        path = _REPO_ROOT / relative
        try:
            current_bytes = path.read_bytes()
            frozen_bytes = subprocess.run(
                ["git", "-C", str(_REPO_ROOT), "show", f"{commit}:{relative}"],
                check=True, capture_output=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            raise _invalid(f"frozen_implementation:{field}") from None
        if current_bytes != frozen_bytes or sha256(current_bytes).hexdigest() != getattr(authorization, field):
            raise _invalid(field)
    if contract.get("phase7_evaluation_source_sha256") != authorization.evaluation_module_sha256:
        raise _invalid("evaluation_contract.phase7_evaluation_source_sha256")
    if contract.get("phase7_evaluation_cli_source_sha256") != authorization.evaluation_cli_sha256:
        raise _invalid("evaluation_contract.phase7_evaluation_cli_source_sha256")
    if contract.get("phase7_durability_source_sha256") != authorization.durability_module_sha256:
        raise _invalid("evaluation_contract.phase7_durability_source_sha256")
    if contract.get("phase7_data_boundary_source_sha256") != authorization.data_boundary_module_sha256:
        raise _invalid("evaluation_contract.phase7_data_boundary_source_sha256")


def verify_generation4_phase7_evaluation_authorization(
    raw: Mapping[str, Any] | Path | None,
) -> Generation4Phase7EvaluationAuthorization:
    """Validate an Independent-Audit evaluation authorization (fail closed)."""
    _verify_frozen_identities()
    if raw is None:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_AUTHORIZATION_MISSING)
    if isinstance(raw, Path):
        if not raw.is_file():
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_AUTHORIZATION_MISSING, str(raw)
            )
        try:
            payload = json.loads(raw.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "unreadable"
            )
    elif isinstance(raw, Mapping):
        payload = dict(raw)
    else:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "not_mapping_or_path"
        )

    try:
        authorization = Generation4Phase7EvaluationAuthorization.model_validate(payload)
    except ValidationError:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_AUTHORIZATION_INVALID)

    if tuple(authorization.research_universe) != _RESEARCH_UNIVERSE:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "research_universe"
        )
    if (
        sha256(_canonical_json(list(authorization.forbidden_holdout_symbols))).hexdigest()
        != _FORBIDDEN_HOLDOUT_SHA256
    ):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "forbidden_holdout_symbols"
        )
    if authorization.candidate_id != _CANDIDATE_ID:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "candidate_id"
        )
    if authorization.benchmark_symbol != _BENCHMARK_SYMBOL:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "benchmark_symbol"
        )
    if tuple(authorization.friction_cases_bps) != _FRICTION_CASES_BPS:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "friction_cases_bps"
        )
    if authorization.primary_friction_bps != _PRIMARY_FRICTION_BPS:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "primary_friction_bps"
        )
    if authorization.warmup_session_limit != _WARMUP_SESSION_LIMIT:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "warmup_session_limit"
        )
    if tuple(authorization.checkpoint_sessions) != _CHECKPOINT_SESSIONS:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "checkpoint_sessions"
        )
    if not authorization.phase7_started:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "phase7_started"
        )
    governance_flags = tuple(getattr(authorization, field) for field in _GOVERNANCE_FALSE)
    if any(governance_flags):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "governance_flags"
        )
    if authorization.recon009_status != "OPEN":
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "recon009_status"
        )
    if not authorization.paper_only:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "paper_only")
    if not authorization.phase7_performance_evaluation_authorized:
        raise _invalid("phase7_performance_evaluation_authorized")
    if authorization.initial_cash != 100_000.0:
        raise _invalid("initial_cash")
    if authorization.prospective_first_scored_session != _FIRST_SCORED_SESSION:
        raise _invalid("prospective_first_scored_session")
    _verify_evidence_bindings(authorization)
    return authorization


def _calendar_window(
    *,
    requested_start: str,
    requested_end: str,
    scored_start: str,
    retrieved_at_utc: str,
) -> tuple[pd.DatetimeIndex, int, int]:
    """Resolve the exact completed XNYS sessions covered by a data request."""
    try:
        start = pd.Timestamp(requested_start)
        end = pd.Timestamp(requested_end)
        scored = pd.Timestamp(scored_start)
        retrieved = pd.Timestamp(retrieved_at_utc)
    except (TypeError, ValueError):
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_RANGE_INVALID) from None
    if retrieved.tzinfo is None:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_RANGE_INVALID, "retrieved_at_utc"
        )
    retrieved = retrieved.tz_convert("UTC")
    try:
        calendar = xcals.get_calendar("XNYS")
        calendar_sessions = calendar.sessions_in_range(start, end)
    except (TypeError, ValueError):
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_RANGE_INVALID) from None
    if (
        calendar_sessions.empty
        or calendar_sessions[0] != start
        or calendar_sessions[-1] != end
        or scored not in calendar_sessions
    ):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_RANGE_INVALID, "exact_xnys_session_range"
        )
    if retrieved < calendar.session_close(end):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_SESSION_INCOMPLETE, requested_end
        )
    warmup_count = int((calendar_sessions < scored).sum())
    scored_count = int((calendar_sessions >= scored).sum())
    sessions = (
        calendar_sessions.tz_localize("UTC")
        if calendar_sessions.tz is None
        else calendar_sessions.tz_convert("UTC")
    )
    return sessions, warmup_count, scored_count


def build_generation4_phase7_data_request(
    *,
    authorization: Generation4Phase7EvaluationAuthorization,
    requested_start: str,
    requested_end: str,
    retrieved_at_utc: str,
) -> dict[str, Any]:
    """Build a request whose counts reflect the actual completed XNYS range."""
    sessions, warmup_count, scored_count = _calendar_window(
        requested_start=requested_start,
        requested_end=requested_end,
        scored_start=authorization.prospective_first_scored_session,
        retrieved_at_utc=retrieved_at_utc,
    )
    if warmup_count != authorization.warmup_session_limit:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_WARMUP_INVALID,
            f"required={authorization.warmup_session_limit},actual={warmup_count}",
        )
    if not 1 <= scored_count <= authorization.checkpoint_sessions[-1]:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_CHECKPOINT_INVALID)
    return {
        "schema_version": DATA_REQUEST_SCHEMA,
        "symbols": list(authorization.research_universe),
        "requested_start": str(sessions[0].date()),
        "requested_end": str(sessions[-1].date()),
        "scored_start": authorization.prospective_first_scored_session,
        "warmup_session_count": warmup_count,
        "scored_session_count": scored_count,
    }


def _validate_request(
    raw: Mapping[str, Any] | Any, *, retrieved_at_utc: str
) -> tuple[Generation4Phase7DataRequest, pd.DatetimeIndex]:
    _verify_frozen_identities()
    try:
        request = Generation4Phase7DataRequest.model_validate(raw)
    except ValidationError:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_REQUEST_INVALID)

    symbols = tuple(request.symbols)
    if any(
        sha256(symbol.encode("utf-8")).hexdigest() in _FORBIDDEN_HOLDOUT_SYMBOL_HASHES
        for symbol in symbols
    ):
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_HOLDOUT_FORBIDDEN)
    if any(symbol not in _RESEARCH_UNIVERSE for symbol in symbols):
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_SYMBOL_UNKNOWN)
    if symbols != _RESEARCH_UNIVERSE:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_UNIVERSE_INVALID)

    if not 1 <= request.warmup_session_count <= _WARMUP_SESSION_LIMIT:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_WARMUP_INVALID)
    if not 1 <= request.scored_session_count <= _CHECKPOINT_SESSIONS_PRIMARY:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_CHECKPOINT_INVALID)
    if not request.requested_start < request.scored_start <= request.requested_end:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_RANGE_INVALID)

    sessions, warmup_count, scored_count = _calendar_window(
        requested_start=request.requested_start,
        requested_end=request.requested_end,
        scored_start=request.scored_start,
        retrieved_at_utc=retrieved_at_utc,
    )
    if warmup_count != _WARMUP_SESSION_LIMIT:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_WARMUP_INVALID,
            f"required={_WARMUP_SESSION_LIMIT},actual={warmup_count}",
        )
    if (
        request.warmup_session_count != warmup_count
        or request.scored_session_count != scored_count
    ):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_SESSION_COUNT_MISMATCH,
            f"expected_warmup={warmup_count},expected_scored={scored_count}",
        )
    return request, sessions


class Phase7QuoteClient:
    """Read-only quote/corporate-action client for the frozen Phase-7 path."""

    def __init__(self, quote_context: Any, *, sdk: Any, host: str, port: int) -> None:
        self._quote_context = quote_context
        self._sdk = sdk
        self.host = host
        self.port = port
        self.sdk_module = getattr(sdk, "__name__", None)
        self.sdk_version = getattr(sdk, "__version__", None)

    def _fetch_daily_bars(
        self, symbol: str, start: str, end: str, *, autype: Any
    ) -> pd.DataFrame:
        code = f"US.{symbol}"
        chunks: list[pd.DataFrame] = []
        page_req_key: Any = None
        while True:
            ret, data, page_req_key = self._quote_context.request_history_kline(
                code,
                start=start,
                end=end,
                ktype=self._sdk.KLType.K_DAY,
                autype=autype,
                max_count=1000,
                page_req_key=page_req_key,
                extended_time=False,
            )
            if int(ret) != 0 or not isinstance(data, pd.DataFrame):
                raise Generation4Phase7DataError(
                    GEN4_PHASE7_DATA_SDK_UNAVAILABLE, f"history:{symbol}:ret={ret}"
                )
            if data.empty:
                break
            chunks.append(data.copy(deep=True))
            if page_req_key in (None, ""):
                break
        if not chunks:
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_SDK_UNAVAILABLE, f"history:{symbol}:empty"
            )
        return pd.concat(chunks, ignore_index=True)

    def fetch_daily_bars(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """QFQ signal bars."""
        return self._fetch_daily_bars(
            symbol, start, end, autype=self._sdk.AuType.QFQ
        )

    def fetch_unadjusted_daily_bars(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Unadjusted execution/accounting bars."""
        return self._fetch_daily_bars(
            symbol, start, end, autype=self._sdk.AuType.NONE
        )

    def fetch_rehab(self, symbol: str) -> pd.DataFrame:
        ret, data = self._quote_context.get_rehab(f"US.{symbol}")
        if int(ret) != 0 or not isinstance(data, pd.DataFrame):
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_SDK_UNAVAILABLE, f"rehab:{symbol}:ret={ret}"
            )
        return data.copy(deep=True)

    def fetch_dividends(self, symbol: str) -> dict[str, Any]:
        ret, data = self._quote_context.get_corporate_actions_dividends(
            f"US.{symbol}"
        )
        if int(ret) != 0 or not isinstance(data, dict):
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_SDK_UNAVAILABLE, f"dividends:{symbol}:ret={ret}"
            )
        rows = data.get("dividend_list", [])
        if not isinstance(rows, list):
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_SDK_UNAVAILABLE, f"dividends:{symbol}:invalid"
            )
        return {"dividend_list": rows}

    def fetch_splits(self, symbol: str) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        next_key: str | None = None
        while True:
            ret, data = self._quote_context.get_corporate_actions_stock_splits(
                f"US.{symbol}", next_key=next_key, num=50
            )
            if int(ret) != 0 or not isinstance(data, dict):
                raise Generation4Phase7DataError(
                    GEN4_PHASE7_DATA_SDK_UNAVAILABLE, f"splits:{symbol}:ret={ret}"
                )
            page = data.get("split_list", [])
            if not isinstance(page, list):
                raise Generation4Phase7DataError(
                    GEN4_PHASE7_DATA_SDK_UNAVAILABLE, f"splits:{symbol}:invalid"
                )
            items.extend(page)
            next_key = str(data.get("next_key", "-1"))
            if next_key == "-1":
                break
        return {"split_list": items}

    def close(self) -> None:
        self._quote_context.close()


def _load_provider_sdk() -> Any:
    for module_name in ("moomoo", "futu"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue
    raise Generation4Phase7DataError(GEN4_PHASE7_DATA_SDK_UNAVAILABLE)


def _default_client_factory(*, host: str, port: int) -> Phase7QuoteClient:
    sdk = _load_provider_sdk()
    quote_context = sdk.OpenQuoteContext(host=host, port=port)
    return Phase7QuoteClient(quote_context, sdk=sdk, host=host, port=port)


def _snapshot_id(
    authorization: Generation4Phase7EvaluationAuthorization,
    request: Generation4Phase7DataRequest,
    retrieved_at_utc: str,
) -> str:
    seed = {
        "provider": PROVIDER,
        "candidate_id": authorization.candidate_id,
        "research_universe": list(request.symbols),
        "requested_start": request.requested_start,
        "requested_end": request.requested_end,
        "scored_start": request.scored_start,
        "warmup_session_count": request.warmup_session_count,
        "scored_session_count": request.scored_session_count,
        "retrieved_at_utc": retrieved_at_utc,
        "prospective_first_scored_session": authorization.prospective_first_scored_session,
    }
    digest = sha256(_canonical_json(seed)).hexdigest()
    return "gen4-phase7-snapshot-" + digest[:32]


def _normalize_provider_frame(
    frame: pd.DataFrame,
    *,
    expected_sessions: pd.DatetimeIndex,
    symbol: str,
) -> pd.DataFrame:
    """Normalize raw provider bars to a canonical UTC session index."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID, f"{symbol}:empty"
        )
    try:
        if "time_key" in frame.columns:
            sessions = pd.DatetimeIndex(
                pd.to_datetime(
                    frame["time_key"].astype(str).str.slice(0, 10),
                    errors="raise",
                    utc=True,
                )
            ).normalize()
        else:
            sessions = pd.DatetimeIndex(
                pd.to_datetime(frame.index, errors="raise", utc=True)
            ).normalize()
    except (TypeError, ValueError):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID, f"{symbol}:session_parse"
        ) from None

    if (
        sessions.has_duplicates
        or not sessions.is_monotonic_increasing
        or not sessions.equals(expected_sessions)
    ):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID, symbol
        )

    required = {"open", "close"}
    if not required.issubset(frame.columns):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID, f"{symbol}:columns"
        )
    selected = [
        column
        for column in ("open", "high", "low", "close", "volume")
        if column in frame.columns
    ]
    result = frame[selected].copy()
    try:
        for column in selected:
            result[column] = pd.to_numeric(result[column], errors="raise")
    except (TypeError, ValueError):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID, f"{symbol}:numeric"
        ) from None
    numeric = result[selected].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID, f"{symbol}:nonfinite"
        )
    if (result[["open", "close"]] <= 0.0).any().any():
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID, f"{symbol}:price"
        )
    if "volume" in result and (result["volume"] < 0.0).any():
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID, f"{symbol}:volume"
        )
    if {"high", "low"}.issubset(result.columns):
        if (
            (result["low"] > result["high"]).any()
            or (result["low"] > result[["open", "close"]].min(axis=1)).any()
            or (result["high"] < result[["open", "close"]].max(axis=1)).any()
        ):
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID, f"{symbol}:ohlc"
            )
    result.index = expected_sessions
    result.index.name = "session"
    return result


def _frame_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=True, index_label="session", date_format="%Y-%m-%d").encode("utf-8")


def _rehab_bytes(frame: pd.DataFrame) -> bytes:
    rendered = frame.copy(deep=True)
    if "ex_div_date" in rendered.columns:
        rendered = rendered.sort_values(["ex_div_date"], kind="stable")
    return rendered.to_csv(
        index=False, lineterminator="\n", float_format="%.17g"
    ).encode("utf-8")


def _json_bytes(value: dict[str, Any]) -> bytes:
    return _canonical_json(value)


def _build_snapshot(
    authorization: Generation4Phase7EvaluationAuthorization,
    request: Generation4Phase7DataRequest,
    signal_frames: Mapping[str, pd.DataFrame],
    execution_frames: Mapping[str, pd.DataFrame],
    rehab_frames: Mapping[str, pd.DataFrame],
    dividend_payloads: Mapping[str, dict[str, Any]],
    split_payloads: Mapping[str, dict[str, Any]],
    retrieved_at_utc: str,
    *,
    snapshot_id: str,
    authorization_sha256: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    file_payloads: dict[str, bytes] = {}
    symbol_entries: dict[str, dict[str, str]] = {}

    for symbol in request.symbols:
        payloads = {
            f"bars/qfq/{symbol}.csv": _frame_bytes(signal_frames[symbol]),
            f"bars/unadjusted/{symbol}.csv": _frame_bytes(execution_frames[symbol]),
            f"corporate_actions/rehab/{symbol}.csv": _rehab_bytes(rehab_frames[symbol]),
            f"corporate_actions/dividends/{symbol}.json": _json_bytes(
                dividend_payloads[symbol]
            ),
            f"corporate_actions/splits/{symbol}.json": _json_bytes(
                split_payloads[symbol]
            ),
        }
        file_payloads.update(payloads)
        symbol_entries[symbol] = {
            "qfq_sha256": sha256(payloads[f"bars/qfq/{symbol}.csv"]).hexdigest(),
            "unadjusted_sha256": sha256(
                payloads[f"bars/unadjusted/{symbol}.csv"]
            ).hexdigest(),
            "rehab_sha256": sha256(
                payloads[f"corporate_actions/rehab/{symbol}.csv"]
            ).hexdigest(),
            "dividends_sha256": sha256(
                payloads[f"corporate_actions/dividends/{symbol}.json"]
            ).hexdigest(),
            "splits_sha256": sha256(
                payloads[f"corporate_actions/splits/{symbol}.json"]
            ).hexdigest(),
        }

    file_entries = [
        {"path": path, "sha256": sha256(payload).hexdigest(), "bytes": len(payload)}
        for path, payload in sorted(file_payloads.items())
    ]
    manifest: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA,
        "snapshot_id": snapshot_id,
        "provider": PROVIDER,
        "retrieved_at_utc": retrieved_at_utc,
        "requested_start": request.requested_start,
        "requested_end": request.requested_end,
        "scored_start": request.scored_start,
        "warmup_session_count": request.warmup_session_count,
        "scored_session_count": request.scored_session_count,
        "candidate_id": authorization.candidate_id,
        "evaluation_authorization_id": authorization.authorization_id,
        "evaluation_authorization_sha256": authorization_sha256,
        "audit_request_sha256": authorization.audit_request_sha256,
        "evaluation_contract_sha256": authorization.evaluation_contract_sha256,
        "start_artifact_sha256": authorization.start_artifact_sha256,
        "frozen_evaluation_implementation_commit": authorization.frozen_evaluation_implementation_commit,
        "benchmark_symbol": _BENCHMARK_SYMBOL,
        "friction_cases_bps": list(_FRICTION_CASES_BPS),
        "primary_friction_bps": _PRIMARY_FRICTION_BPS,
        "signal_price_convention": "QFQ",
        "execution_price_convention": "UNADJUSTED",
        "corporate_actions_included": True,
        "symbols": symbol_entries,
        "files": file_entries,
        "trading_context_created": False,
        "protected_holdout_symbols_accessed": [],
        "performance_computed": False,
        "performance_inspected": False,
    }
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    manifest["manifest_sha256"] = sha256(_canonical_json(body)).hexdigest()
    return manifest, file_payloads


def _write_exclusive(path: Path, data: bytes) -> None:
    try:
        with open(path, "xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_OUTPUT_EXISTS, str(path))
    except OSError as exc:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_WRITE_FAILED, str(exc))


def _write_snapshot(
    snapshot_dir: Path, manifest: dict[str, Any], file_payloads: dict[str, bytes]
) -> None:
    for relative, payload in sorted(file_payloads.items()):
        path = snapshot_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_exclusive(path, payload)
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, indent=2, allow_nan=False
    ).encode("utf-8")
    _write_exclusive(snapshot_dir / "manifest.json", manifest_bytes)


def acquire_prospective_phase7_data(
    *,
    evaluation_authorization: Mapping[str, Any] | Path | None,
    request: Mapping[str, Any] | Any,
    output_dir: Path,
    retrieved_at_utc: str,
    client_factory: Any = None,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> dict[str, Any]:
    """Acquire the prospective Phase-7 snapshot under the data boundary.

    Every gate (authorization, request universe/ranges, output existence) is
    enforced before a provider object is created. The provider is created
    only after all gates pass, is used read-only for the exact ordered
    universe, and is always closed.
    """
    # Gate 1: evaluation authorization (before any provider object exists).
    authorization = verify_generation4_phase7_evaluation_authorization(
        evaluation_authorization
    )
    if isinstance(evaluation_authorization, Path):
        try:
            authorization_sha256 = sha256(
                evaluation_authorization.read_bytes()
            ).hexdigest()
        except OSError:
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "authorization_bytes"
            ) from None
    elif isinstance(evaluation_authorization, Mapping):
        authorization_sha256 = sha256(
            _canonical_json(dict(evaluation_authorization))
        ).hexdigest()
    else:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_AUTHORIZATION_MISSING)
    # Gate 2: the request (universe, holdout, unknown, ranges) before provider.
    validated_request, expected_sessions = _validate_request(
        request, retrieved_at_utc=retrieved_at_utc
    )

    snapshot_dir = (
        Path(output_dir)
        / "snapshots"
        / _snapshot_id(authorization, validated_request, retrieved_at_utc)
    )
    manifest_path = snapshot_dir / "manifest.json"
    if manifest_path.exists():
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_OUTPUT_EXISTS, str(manifest_path)
        )

    # Provider is created only after every gate has passed.
    factory = client_factory if client_factory is not None else _default_client_factory
    client = factory(host=host, port=port)
    try:
        signal_raw: dict[str, pd.DataFrame] = {}
        execution_raw: dict[str, pd.DataFrame] = {}
        rehab_frames: dict[str, pd.DataFrame] = {}
        dividend_payloads: dict[str, dict[str, Any]] = {}
        split_payloads: dict[str, dict[str, Any]] = {}
        for symbol in validated_request.symbols:
            signal_raw[symbol] = client.fetch_daily_bars(
                symbol, validated_request.requested_start, validated_request.requested_end
            )
            execution_raw[symbol] = client.fetch_unadjusted_daily_bars(
                symbol, validated_request.requested_start, validated_request.requested_end
            )
            rehab_frames[symbol] = client.fetch_rehab(symbol)
            dividend_payloads[symbol] = client.fetch_dividends(symbol)
            split_payloads[symbol] = client.fetch_splits(symbol)
    finally:
        client.close()

    signal_frames = {
        symbol: _normalize_provider_frame(
            signal_raw[symbol], expected_sessions=expected_sessions, symbol=f"{symbol}:QFQ"
        )
        for symbol in validated_request.symbols
    }
    execution_frames = {
        symbol: _normalize_provider_frame(
            execution_raw[symbol],
            expected_sessions=expected_sessions,
            symbol=f"{symbol}:NONE",
        )
        for symbol in validated_request.symbols
    }
    manifest, file_payloads = _build_snapshot(
        authorization,
        validated_request,
        signal_frames,
        execution_frames,
        rehab_frames,
        dividend_payloads,
        split_payloads,
        retrieved_at_utc,
        snapshot_id=snapshot_dir.name,
        authorization_sha256=authorization_sha256,
    )
    _write_snapshot(snapshot_dir, manifest, file_payloads)
    return manifest
