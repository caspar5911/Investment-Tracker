"""Fail-closed Independent-Audit gate for the exact first Phase-7 checkpoint.

No provider or performance code is imported here. The authorization artifact is
auditor-owned and deliberately absent until the exact-63 snapshot is reviewed.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import weakref
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from . import phase7_first_checkpoint as first
from . import phase7_collector as collector
from . import phase7_source_amendment as source_amendment

PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED = "PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED"
PHASE7_CHECKPOINT_PENDING = "PHASE7_CHECKPOINT_PENDING"
PHASE7_UNKNOWN_ABSTAIN = "PHASE7_UNKNOWN_ABSTAIN"
PHASE7_CHECKPOINT_AUTHORIZED = "PHASE7_CHECKPOINT_AUTHORIZED"

_ROOT = Path(__file__).resolve().parents[4]
_SNAPSHOT_ROOT = _ROOT / "data/phase7/generation4/prospective/snapshots"
_AUTHORIZATION_PATH = (
    _ROOT / "data/governance/successor/generation4-phase7-first-checkpoint-authorization.json"
)
_AUDIT_REQUEST_PATH = (
    _ROOT / "data/governance/successor/generation4-phase7-first-checkpoint-independent-audit-request.json"
)
_RESULT_PATH = _ROOT / "data/phase7/generation4/checkpoints/first63/checkpoint-result.json"
_SOURCE_FILES = (
    "src/investment_tracker/independent_audit/post_generation3/phase7_checkpoint_gate.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_evaluation_cli.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_collector.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_collector_cli.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_first_checkpoint.py",
    "src/investment_tracker/quant/phase7/generation4_durability.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_data.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_evaluation.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_source_amendment.py",
)
_FALSE_FLAGS = (
    "production_readiness_approved", "live_trading_authorized",
    "candidate_search_authorized", "parameter_mutation_authorized",
    "symbol_substitution_authorized", "holdout_reuse_authorized",
    "result_dependent_methodology_change_allowed",
)
_AUTH_FIELDS = frozenset({
    "schema_version", "status", "authority", "authorization_id",
    "approved_at_utc", "artifact_sha256", "audit_request_sha256",
    "checkpoint_contract_sha256", "evaluation_contract_sha256",
    "source_amendment_authorization_sha256",
    "evaluation_authorization_sha256", "evaluation_authorization_id",
    "implementation_commit", "source_sha256", "snapshot_id",
    "snapshot_manifest_sha256", "snapshot_chain_sha256", "checkpoint_scored_sessions",
    "candidate_id", "research_universe", "forbidden_holdout_symbols",
    "benchmark_symbol", "friction_cases_bps", "primary_friction_bps",
    "first_scored_session", "last_scored_session", "warmup_start",
    "warmup_session_count", "warmup_excluded_from_scored_pnl",
    "signal_price_convention", "execution_price_convention",
    "corporate_actions_required", "dq030_status", "recon009_status",
    "paper_only", *_FALSE_FLAGS,
})


class CheckpointGateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.detail = ""
        super().__init__(code)


class _CheckpointPermit:
    __slots__ = (
        "snapshot_id", "manifest_sha256", "authorization_sha256",
        "authorization_id", "implementation_commit", "source_sha256", "__weakref__",
        "source_amendment_sha256", "snapshot_chain_sha256",
    )

    def __init__(self, snapshot_id: str, manifest_sha256: str, authorization_sha256: str,
                 authorization_id: str, implementation_commit: str,
                 source_sha256: dict[str, str], source_amendment_sha256: str,
                 snapshot_chain_sha256: str):
        object.__setattr__(self, "snapshot_id", snapshot_id)
        object.__setattr__(self, "manifest_sha256", manifest_sha256)
        object.__setattr__(self, "authorization_sha256", authorization_sha256)
        object.__setattr__(self, "authorization_id", authorization_id)
        object.__setattr__(self, "implementation_commit", implementation_commit)
        object.__setattr__(self, "source_sha256", tuple(sorted(source_sha256.items())))
        object.__setattr__(self, "source_amendment_sha256", source_amendment_sha256)
        object.__setattr__(self, "snapshot_chain_sha256", snapshot_chain_sha256)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("checkpoint permit is immutable")


_ISSUED: weakref.WeakSet[_CheckpointPermit] = weakref.WeakSet()


def _require(condition: bool, code: str = PHASE7_UNKNOWN_ABSTAIN) -> None:
    if not condition:
        raise CheckpointGateError(code)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _verify_current_sources(commit: str, hashes: dict[str, str]) -> None:
    _require(isinstance(commit, str) and len(commit) == 40)
    _require(isinstance(hashes, dict) and set(hashes) == set(_SOURCE_FILES))
    for relative in _SOURCE_FILES:
        path = _ROOT / relative
        _require(path.is_file() and not path.is_symlink())
        current = path.read_bytes()
        frozen = subprocess.run(
            ["git", "-C", str(_ROOT), "show", f"{commit}:{relative}"],
            check=True, capture_output=True,
        ).stdout
        _require(current == frozen and hashes[relative] == sha256(current).hexdigest())


def _verified_authorization(contract: dict[str, Any], selected: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if not _AUTHORIZATION_PATH.is_file() or _AUTHORIZATION_PATH.is_symlink():
        raise CheckpointGateError(PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED)
    try:
        raw = _AUTHORIZATION_PATH.read_bytes()
        authority = json.loads(raw)
        _require(isinstance(authority, dict) and set(authority) == _AUTH_FIELDS)
        body = {key: value for key, value in authority.items() if key != "artifact_sha256"}
        _require(authority["artifact_sha256"] == sha256(_canonical_json(body)).hexdigest())
        request = json.loads(_AUDIT_REQUEST_PATH.read_bytes())
        _require(isinstance(request, dict))
        _require(request.get("schema_version") == "GENERATION4-PHASE7-FIRST-CHECKPOINT-INDEPENDENT-AUDIT-REQUEST-v1")
        _require(request.get("status") == "READY_FOR_INDEPENDENT_AUDIT")
        _require(request.get("authority") == "NONE")
        for field in (
            "checkpoint_contract_sha256", "evaluation_authorization_sha256",
            "source_amendment_authorization_sha256", "implementation_commit",
            "source_sha256", "snapshot_id", "snapshot_manifest_sha256",
            "snapshot_chain_sha256", "checkpoint_scored_sessions", "candidate_id",
        ):
            _require(request.get(field) == authority[field])
        expected = {
            "schema_version": "GENERATION4-PHASE7-FIRST-CHECKPOINT-AUTHORIZATION-v1",
            "status": PHASE7_CHECKPOINT_AUTHORIZED,
            "authority": "INDEPENDENT_AUDIT",
            "checkpoint_contract_sha256": first._CONTRACT_SHA256,
            "evaluation_contract_sha256": contract["evaluation_contract_sha256"],
            "evaluation_authorization_sha256": contract["evaluation_authorization_sha256"],
            "evaluation_authorization_id": contract["evaluation_authorization_id"],
            "source_amendment_authorization_sha256": sha256(
                source_amendment._AMENDMENT_PATH.read_bytes()
            ).hexdigest(),
            "snapshot_id": selected["selected_snapshot_id"],
            "snapshot_manifest_sha256": selected["selected_manifest_sha256"],
            "snapshot_chain_sha256": selected["selected_snapshot_chain_sha256"],
            "checkpoint_scored_sessions": 63,
            "candidate_id": contract["candidate_id"],
            "research_universe": contract["research_universe"],
            "forbidden_holdout_symbols": contract["forbidden_holdout_symbols"],
            "benchmark_symbol": contract["benchmark_symbol"],
            "friction_cases_bps": contract["friction_cases_bps"],
            "primary_friction_bps": contract["primary_friction_bps"],
            "first_scored_session": contract["first_scored_session"],
            "last_scored_session": contract["last_scored_session"],
            "warmup_start": contract["warmup_start"],
            "warmup_session_count": contract["warmup_session_count"],
            "warmup_excluded_from_scored_pnl": True,
            "signal_price_convention": "QFQ",
            "execution_price_convention": "UNADJUSTED",
            "corporate_actions_required": True,
            "dq030_status": "UNRESOLVED",
            "recon009_status": "OPEN",
            "paper_only": True,
            "audit_request_sha256": sha256(_AUDIT_REQUEST_PATH.read_bytes()).hexdigest(),
        }
        for field, value in expected.items():
            _require(type(authority[field]) is type(value) and authority[field] == value)
        for field in _FALSE_FLAGS:
            _require(authority[field] is False)
        _require(isinstance(authority["authorization_id"], str)
                 and authority["authorization_id"].startswith("INDEP-AUDIT-GEN4-PHASE7-CP63-"))
        approved = datetime.fromisoformat(authority["approved_at_utc"].replace("Z", "+00:00"))
        _require(approved.tzinfo is not None and approved.utcoffset() is not None)
        _verify_current_sources(authority["implementation_commit"], authority["source_sha256"])
        return authority, sha256(raw).hexdigest()
    except CheckpointGateError:
        raise
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError):
        raise CheckpointGateError(PHASE7_UNKNOWN_ABSTAIN) from None


def checkpoint_execution_permit(snapshot_dir: Path) -> _CheckpointPermit:
    """Verify structural evidence, then a separate audit decision, before bars load."""
    try:
        contract = first._contract()
        readiness = first.first_checkpoint_readiness()
        status = readiness["status"]
        if status == PHASE7_CHECKPOINT_PENDING:
            raise CheckpointGateError(PHASE7_CHECKPOINT_PENDING)
        _require(status == collector.PHASE7_CHECKPOINT_READY)
        _require(readiness["selected_snapshot_scored_sessions"] == 63)
        selected_id = readiness["selected_snapshot_id"]
        _require(snapshot_dir.is_dir() and not snapshot_dir.is_symlink())
        _require(snapshot_dir.resolve() == (_SNAPSHOT_ROOT / selected_id).resolve())
        try:
            source_amendment.verify_source_amendment(first._historical_snapshot_authorization())
        except source_amendment.SourceAmendmentError:
            raise CheckpointGateError(PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED) from None
        authority, digest = _verified_authorization(contract, readiness)
        permit = _CheckpointPermit(
            selected_id, readiness["selected_manifest_sha256"], digest,
            authority["authorization_id"], authority["implementation_commit"],
            authority["source_sha256"], authority["source_amendment_authorization_sha256"],
            readiness["selected_snapshot_chain_sha256"],
        )
        _ISSUED.add(permit)
        return permit
    except CheckpointGateError:
        raise
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        raise CheckpointGateError(PHASE7_UNKNOWN_ABSTAIN) from None


def require_checkpoint_permit(permit: object, snapshot: object) -> None:
    """Reject unissued or mismatched permits before touching any bars or signals."""
    if not isinstance(permit, _CheckpointPermit) or permit not in _ISSUED:
        raise CheckpointGateError(PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED)
    try:
        _require(sha256(_AUTHORIZATION_PATH.read_bytes()).hexdigest() == permit.authorization_sha256)
        _require(sha256(source_amendment._AMENDMENT_PATH.read_bytes()).hexdigest()
                 == permit.source_amendment_sha256)
    except OSError:
        raise CheckpointGateError(PHASE7_UNKNOWN_ABSTAIN) from None
    current = first.first_checkpoint_readiness()
    _require(current.get("status") == collector.PHASE7_CHECKPOINT_READY)
    _require(current.get("selected_snapshot_id") == permit.snapshot_id)
    _require(current.get("selected_manifest_sha256") == permit.manifest_sha256)
    _require(current.get("selected_snapshot_chain_sha256") == permit.snapshot_chain_sha256)
    bindings = getattr(snapshot, "evidence_bindings", None)
    if not isinstance(bindings, dict) or bindings.get("snapshot_manifest_sha256") != permit.manifest_sha256:
        raise CheckpointGateError(PHASE7_UNKNOWN_ABSTAIN)


def write_checkpoint_result(permit: object, report: dict[str, Any]) -> dict[str, Any]:
    """Publish one content-bound result with exclusive create and readback."""
    _require(isinstance(permit, _CheckpointPermit) and permit in _ISSUED)
    _require(isinstance(report, dict))
    require_checkpoint_permit(
        permit, SimpleNamespace(evidence_bindings=report.get("evidence_bindings"))
    )
    _require(report.get("scored_session_count") == 63)
    _require(report.get("checkpoint_cutoff") == 63)
    _require(report.get("checkpoint_label") == "EARLY_DIAGNOSTIC")
    _require(report.get("status") == "PHASE7_PROSPECTIVE_EVIDENCE_PENDING")
    _require(report.get("candidate_id") == first._contract()["candidate_id"])
    _require(report.get("paper_only") is True)
    _require(report.get("production_authority") is False)
    _require(report.get("live_trading_authority") is False)
    _require(report.get("production_pass") is False)
    _require(report.get("signal_price_convention") == "QFQ")
    _require(report.get("execution_price_convention") == "UNADJUSTED")
    _require(report.get("no_tuning_performed") is True)
    _require(report.get("no_final_holdout_reuse") is True)
    _require(report.get("candidate_changed") is False)
    _require(report.get("methodology_changed") is False)
    _require(report.get("exposure_invariant_passes") is True)
    cases = report.get("friction_cases")
    _require(isinstance(cases, dict) and set(cases) == {"0", "3", "10", "25", "50"})
    for bps in (0, 3, 10, 25, 50):
        case = cases[str(bps)]
        _require(isinstance(case, dict) and case.get("friction_bps") == bps)
        _require(case.get("scored_session_count") == 63)
        metric = case.get("total_return")
        _require(isinstance(metric, dict) and metric.get("status") == "AVAILABLE")
        _require(type(metric.get("value")) in (float, int) and math.isfinite(metric["value"]))
    for field in ("benchmark_total_return", "excess_return_vs_spy", "excess_return_vs_cash"):
        metric = report.get(field)
        _require(isinstance(metric, dict) and metric.get("status") == "AVAILABLE")
        _require(type(metric.get("value")) in (float, int) and math.isfinite(metric["value"]))
    bindings = report.get("evidence_bindings")
    _require(isinstance(bindings, dict) and
             bindings.get("snapshot_manifest_sha256") == permit.manifest_sha256)
    for field in ("max_drawdown", "calmar", "recovery"):
        _require(report.get(field) == {
            "status": "UNKNOWN", "value": None, "reason": "DQ-030_UNRESOLVED"
        })
    _require(report.get("rolling_12m_return") == {
        "status": "UNKNOWN", "value": None, "reason": "INCOMPLETE_WINDOW"
    })
    allowed_report_fields = (
        "schema", "candidate_id", "checkpoint_cutoff", "scored_session_count",
        "checkpoint_label", "scored_start", "status", "signal_price_convention",
        "execution_price_convention", "friction_cases", "benchmark_total_return",
        "excess_return_vs_spy", "excess_return_vs_cash", "exposure_invariant_passes",
        "max_drawdown", "calmar", "recovery", "paper_only",
        "production_authority", "live_trading_authority", "production_pass",
        "no_tuning_performed", "no_final_holdout_reuse", "candidate_changed",
        "methodology_changed", "evidence_bindings", "corporate_action_reconciliation",
        "rolling_12m_return",
    )
    filtered_report = {key: report[key] for key in allowed_report_fields if key in report}
    body = {
        "schema_version": "GENERATION4-PHASE7-FIRST-CHECKPOINT-RESULT-v1",
        "status": "EARLY_DIAGNOSTIC_NON_DECISION_GRADE",
        "checkpoint_contract_sha256": first._CONTRACT_SHA256,
        "evaluation_contract_sha256": first._contract()["evaluation_contract_sha256"],
        "checkpoint_authorization_id": permit.authorization_id,
        "checkpoint_authorization_sha256": permit.authorization_sha256,
        "snapshot_id": permit.snapshot_id,
        "snapshot_manifest_sha256": permit.manifest_sha256,
        "snapshot_chain_sha256": permit.snapshot_chain_sha256,
        "implementation_commit": permit.implementation_commit,
        "source_sha256": dict(permit.source_sha256),
        "candidate_id": report["candidate_id"],
        "friction_cases_bps": [0, 3, 10, 25, 50],
        "primary_friction_bps": 3,
        "benchmark_symbol": "SPY",
        "cash_total_return": 0,
        "dq030_status": "UNRESOLVED",
        "recon009_status": "OPEN",
        "paper_only": True,
        "production_readiness_approved": False,
        "live_trading_authorized": False,
        "strategy_validation_status": "UNKNOWN_ABSTAIN",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "report": filtered_report,
    }
    try:
        payload = {**body, "result_sha256": sha256(_canonical_json(body)).hexdigest()}
        raw = _canonical_json(payload)
        _require(not _RESULT_PATH.is_symlink() and not _RESULT_PATH.parent.is_symlink())
        _RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _RESULT_PATH.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        _require(_RESULT_PATH.read_bytes() == raw)
    except (OSError, ValueError, TypeError, CheckpointGateError):
        raise CheckpointGateError(PHASE7_UNKNOWN_ABSTAIN) from None
    return {"status": "PHASE7_CHECKPOINT_EVALUATED", "result_sha256": payload["result_sha256"],
            "snapshot_id": permit.snapshot_id, "result_path": str(_RESULT_PATH)}
