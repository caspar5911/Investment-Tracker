"""Provider-free, structural readiness for the preregistered first checkpoint.

This module never authorizes or runs the frozen Phase-7 evaluator. Its ready
status says only that an exact-63 snapshot is structurally available.
"""

from __future__ import annotations

import json
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any

import exchange_calendars as xcals

from . import phase7_collector as collector
from .phase7_data import Generation4Phase7EvaluationAuthorization

_ROOT = Path(__file__).resolve().parents[4]
_CONTRACT_PATH = (
    _ROOT / "data/governance/successor/generation4-phase7-first-checkpoint-contract.json"
)
_CONTRACT_SHA256 = "464b53fea8b08b33b3db851d27b3f4c1228ecf9bcb8a88966faa8c2a50d413bf"
_BOUND_FILES = {
    "evaluation_authorization_sha256": "data/governance/successor/generation4-phase7-evaluation-authorization.json",
    "evaluation_request_sha256": "data/governance/successor/generation4-phase7-evaluation-independent-audit-request.json",
    "evaluation_contract_sha256": "data/governance/successor/generation4-phase7-evaluation-contract.json",
    "start_artifact_sha256": "data/governance/successor/generation4-phase7-start.json",
    "start_contract_sha256": "data/governance/successor/generation4-phase7-start-contract.json",
    "entry_authorization_sha256": "data/governance/successor/generation4-phase7-entry-authorization.json",
    "evaluation_source_sha256": "src/investment_tracker/independent_audit/post_generation3/phase7_evaluation.py",
    "evaluation_cli_source_sha256": "src/investment_tracker/independent_audit/post_generation3/phase7_evaluation_cli.py",
    "durability_source_sha256": "src/investment_tracker/quant/phase7/generation4_durability.py",
    "data_boundary_source_sha256": "src/investment_tracker/independent_audit/post_generation3/phase7_data.py",
    "collector_source_sha256": "src/investment_tracker/independent_audit/post_generation3/phase7_collector.py",
}
_FROZEN_SOURCE_COMMITS = {
    "evaluation_cli_source_sha256": "5149ac70d2561abff4b2cc6d2b8c75dbedfa3bd2",
    "durability_source_sha256": "5149ac70d2561abff4b2cc6d2b8c75dbedfa3bd2",
    "data_boundary_source_sha256": "5149ac70d2561abff4b2cc6d2b8c75dbedfa3bd2",
    "collector_source_sha256": "9eb2ea9d0277998d14445429bbd25d3fbb6b2f4b",
}


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError("first_checkpoint_binding")


def _contract() -> dict[str, Any]:
    _require(not _CONTRACT_PATH.is_symlink())
    raw = _CONTRACT_PATH.read_bytes()
    _require(sha256(raw).hexdigest() == _CONTRACT_SHA256)
    contract = json.loads(raw)
    _require(isinstance(contract, dict))
    for field, relative in _BOUND_FILES.items():
        path = _ROOT / relative
        _require(path.is_file() and not path.is_symlink())
        if field in _FROZEN_SOURCE_COMMITS:
            frozen = subprocess.run(
                ["git", "-C", str(_ROOT), "show", f"{_FROZEN_SOURCE_COMMITS[field]}:{relative}"],
                capture_output=True, check=True,
            ).stdout
            _require(contract[field] == sha256(frozen).hexdigest())
        else:
            _require(contract[field] == sha256(path.read_bytes()).hexdigest())
    expected = {
        "schema_version": "GENERATION4-PHASE7-FIRST-CHECKPOINT-CONTRACT-v1",
        "status": "PREREGISTERED_EXECUTION_BLOCKED",
        "authority": "NONE",
        "checkpoint_scored_sessions": 63,
        "checkpoint_label": "EARLY_DIAGNOSTIC",
        "snapshot_selection": "EXACT_63_COMPLETE_SNAPSHOT_ONLY",
        "first_scored_session": "2026-09-28",
        "last_scored_session": "2026-12-24",
        "warmup_start": "2025-11-24",
        "warmup_session_count": 210,
        "warmup_excluded_from_scored_pnl": True,
        "exact_snapshot_session_count": 273,
        "first_verified_snapshot_id": "gen4-phase7-snapshot-09c0946bea22026f08bc572fe58b8c16",
        "first_verified_snapshot_manifest_sha256": "16e0b046985ae295567923f4543bb0098865fc86c83bbeda605f1bbd1caf8784",
        "frozen_evaluation_implementation_commit": "5149ac70d2561abff4b2cc6d2b8c75dbedfa3bd2",
        "collector_implementation_commit": "9eb2ea9d0277998d14445429bbd25d3fbb6b2f4b",
        "candidate_id": "G2-A|lookback=189|skip=21|top_k=1|rebalance=21",
        "research_universe": ["GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP"],
        "benchmark_symbol": "SPY",
        "friction_cases_bps": [0, 3, 10, 25, 50],
        "primary_friction_bps": 3,
        "signal_price_convention": "QFQ",
        "execution_price_convention": "UNADJUSTED",
        "corporate_actions_required": True,
        "dq030_status": "UNRESOLVED",
        "recon009_status": "OPEN",
        "checkpoint_specific_independent_audit_authorization_required": True,
        "checkpoint_evaluation_authorized": False,
        "paper_only": True,
    }
    for field, value in expected.items():
        _require(type(contract[field]) is type(value) and contract[field] == value)
    for field in (
        "production_readiness_approved", "live_trading_authorized",
        "candidate_search_authorized", "parameter_mutation_authorized",
        "symbol_substitution_authorized", "holdout_reuse_authorized",
        "result_dependent_methodology_change_allowed",
    ):
        _require(contract[field] is False)
    return contract


def _validate_history(snapshots: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    _require(isinstance(snapshots, list))
    if not snapshots:
        return
    first = snapshots[0]
    _require(first["snapshot_id"] == contract["first_verified_snapshot_id"])
    _require(first["manifest_sha256"] == contract["first_verified_snapshot_manifest_sha256"])
    _require(first["scored_session_count"] == 1)
    _require(first["requested_end"] == contract["first_scored_session"])
    calendar = xcals.get_calendar("XNYS")
    previous_count = 0
    previous_end = ""
    for snapshot in snapshots:
        count = snapshot["scored_session_count"]
        end = snapshot["requested_end"]
        _require(type(count) is int and count > previous_count)
        _require(isinstance(end, str) and end > previous_end)
        _require(snapshot["requested_start"] == contract["warmup_start"])
        _require(snapshot["scored_start"] == contract["first_scored_session"])
        _require(snapshot["warmup_session_count"] == contract["warmup_session_count"])
        _require(snapshot["candidate_id"] == contract["candidate_id"])
        _require(snapshot["evaluation_authorization_id"] == contract["evaluation_authorization_id"])
        _require(snapshot["evaluation_authorization_sha256"] == contract["evaluation_authorization_sha256"])
        _require(len(calendar.sessions_in_range(contract["first_scored_session"], end)) == count)
        previous_count, previous_end = count, end


def _historical_snapshot_authorization() -> Generation4Phase7EvaluationAuthorization:
    """Parse the hash-pinned original authority for read-only snapshot checks.

    This is not an acquisition or evaluation authorization for amended code.
    The original file hash and frozen source identities are checked by _contract.
    """
    path = collector._AUTHORIZATION_PATH
    _require(path.is_file() and not path.is_symlink())
    return Generation4Phase7EvaluationAuthorization.model_validate(
        json.loads(path.read_bytes())
    )


def first_checkpoint_readiness() -> dict[str, Any]:
    """Inspect governance and verified snapshot structure; disclose no performance."""
    result: dict[str, Any] = {
        "status": collector.PHASE7_UNKNOWN_ABSTAIN,
        "checkpoint_scored_sessions": 63,
        "evaluation_authorized": False,
        "performance_computed": False,
    }
    stage = "contract"
    try:
        contract = _contract()
        stage = "authorization"
        authorization = _historical_snapshot_authorization()
        _require(authorization.authorization_id == contract["evaluation_authorization_id"])
        _require(authorization.candidate_id == contract["candidate_id"])
        _require(list(authorization.research_universe) == contract["research_universe"])
        _require(list(authorization.forbidden_holdout_symbols) == contract["forbidden_holdout_symbols"])
        _require(authorization.benchmark_symbol == contract["benchmark_symbol"])
        _require(list(authorization.friction_cases_bps) == contract["friction_cases_bps"])
        _require(authorization.primary_friction_bps == contract["primary_friction_bps"])
        _require(authorization.prospective_first_scored_session == contract["first_scored_session"])
        _require(authorization.warmup_session_limit == contract["warmup_session_count"])
        _require(authorization.dq030_status == contract["dq030_status"])
        _require(authorization.recon009_status == contract["recon009_status"])
        _require(authorization.paper_only is True)
        # Authority has not been consumed: verify manifests and file metadata
        # only. Full payload verification belongs after checkpoint consumption.
        stage = "snapshot_structure"
        snapshots = collector._structural_snapshots(authorization)
        stage = "history"
        _validate_history(snapshots, contract)
        stage = "selection"
        exact = [s for s in snapshots if s["scored_session_count"] == 63]
        if exact:
            _require(len(exact) == 1)
            selected = exact[0]
            _require(selected["requested_end"] == contract["last_scored_session"])
            history = [
                {"snapshot_id": item["snapshot_id"],
                 "manifest_sha256": item["manifest_sha256"],
                 "requested_end": item["requested_end"]}
                for item in snapshots if item["requested_end"] <= contract["last_scored_session"]
            ]
            chain_digest = sha256(json.dumps(
                history, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")).hexdigest()
            result.update({
                "status": collector.PHASE7_CHECKPOINT_READY,
                "selected_snapshot_id": selected["snapshot_id"],
                "selected_manifest_sha256": selected["manifest_sha256"],
                "selected_snapshot_scored_sessions": 63,
                "selected_snapshot_chain_sha256": chain_digest,
            })
        elif not snapshots or snapshots[-1]["scored_session_count"] < 63:
            result["status"] = "PHASE7_CHECKPOINT_PENDING"
    except Exception:
        # Invalid governance or snapshot evidence cannot grant readiness.
        result["failure_stage"] = stage
        return result
    return result
