"""Auditor-owned source amendment required before Phase-7 collection resumes."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[4]
_AMENDMENT_PATH = (
    _ROOT / "data/governance/successor/generation4-phase7-source-amendment-authorization.json"
)
_REQUEST_PATH = (
    _ROOT / "data/governance/successor/generation4-phase7-source-amendment-independent-audit-request.json"
)
_FIRST_CONTRACT_PATH = (
    _ROOT / "data/governance/successor/generation4-phase7-first-checkpoint-contract.json"
)
_ORIGINAL_AUTH_PATH = (
    _ROOT / "data/governance/successor/generation4-phase7-evaluation-authorization.json"
)
_FIRST_CONTRACT_SHA256 = "464b53fea8b08b33b3db851d27b3f4c1228ecf9bcb8a88966faa8c2a50d413bf"
_CANONICAL_INPUT = object()
_SOURCE_FILES = (
    "src/investment_tracker/independent_audit/post_generation3/phase7_evaluation.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_evaluation_cli.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_data.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_collector.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_collector_cli.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_first_checkpoint.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_checkpoint_gate.py",
    "src/investment_tracker/independent_audit/post_generation3/phase7_source_amendment.py",
    "src/investment_tracker/quant/phase7/generation4_durability.py",
)
_FALSE_FLAGS = (
    "production_readiness_approved", "live_trading_authorized",
    "candidate_search_authorized", "parameter_mutation_authorized",
    "symbol_substitution_authorized", "holdout_reuse_authorized",
    "result_dependent_methodology_change_allowed",
    "checkpoint_evaluation_authorized",
)
_FIELDS = frozenset({
    "schema_version", "status", "authority", "authorization_id",
    "approved_at_utc", "artifact_sha256", "audit_request_sha256",
    "original_evaluation_authorization_id", "original_evaluation_authorization_sha256",
    "evaluation_contract_sha256", "first_checkpoint_contract_sha256",
    "implementation_commit", "source_sha256", "candidate_id",
    "research_universe", "forbidden_holdout_symbols", "benchmark_symbol",
    "friction_cases_bps", "primary_friction_bps", "first_scored_session",
    "warmup_session_count", "dq030_status", "recon009_status",
    "paper_only", *_FALSE_FLAGS,
})


class SourceAmendmentError(RuntimeError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _require(condition: bool) -> None:
    if not condition:
        raise SourceAmendmentError("source_amendment_invalid_or_missing")


def _verify_sources(commit: str, hashes: dict[str, str]) -> None:
    _require(isinstance(commit, str) and len(commit) == 40)
    _require(isinstance(hashes, dict) and set(hashes) == set(_SOURCE_FILES))
    for relative in _SOURCE_FILES:
        path = _ROOT / relative
        _require(path.is_file() and not path.is_symlink())
        current = path.read_bytes()
        committed = subprocess.run(
            ["git", "-C", str(_ROOT), "show", f"{commit}:{relative}"],
            check=True, capture_output=True,
        ).stdout
        _require(current == committed and hashes[relative] == sha256(current).hexdigest())


def verify_source_amendment(
    original_authorization: Any,
    *,
    supplied_authorization_path: Path | None | object = _CANONICAL_INPUT,
    supplied_authorization_bytes: bytes | None | object = _CANONICAL_INPUT,
) -> None:
    """Bind source bytes and the caller's exact authorization to the audit decision.

    A direct checkpoint-gate call uses the canonical file. The acquisition
    loader passes its already-read bytes and path; mappings cannot prove that
    file identity and fail closed when an amendment is needed.
    """
    try:
        from .phase7_data import Generation4Phase7EvaluationAuthorization

        _require(_AMENDMENT_PATH.is_file() and not _AMENDMENT_PATH.is_symlink())
        contract_bytes = _FIRST_CONTRACT_PATH.read_bytes()
        _require(sha256(contract_bytes).hexdigest() == _FIRST_CONTRACT_SHA256)
        contract = json.loads(contract_bytes)
        _require(_ORIGINAL_AUTH_PATH.is_file() and not _ORIGINAL_AUTH_PATH.is_symlink())
        if (
            supplied_authorization_path is _CANONICAL_INPUT
            and supplied_authorization_bytes is _CANONICAL_INPUT
        ):
            supplied_authorization_path = _ORIGINAL_AUTH_PATH
            supplied_authorization_bytes = _ORIGINAL_AUTH_PATH.read_bytes()
        _require(
            isinstance(supplied_authorization_path, Path)
            and supplied_authorization_path.is_file()
            and not supplied_authorization_path.is_symlink()
            and supplied_authorization_path.absolute() == _ORIGINAL_AUTH_PATH.absolute()
        )
        _require(type(supplied_authorization_bytes) is bytes)
        _require(sha256(supplied_authorization_bytes).hexdigest()
                 == contract["evaluation_authorization_sha256"])
        _require(type(original_authorization) is Generation4Phase7EvaluationAuthorization)
        _require(
            original_authorization.model_dump(mode="json") == json.loads(supplied_authorization_bytes)
        )
        raw = _AMENDMENT_PATH.read_bytes()
        amendment = json.loads(raw)
        _require(isinstance(amendment, dict) and set(amendment) == _FIELDS)
        body = {key: value for key, value in amendment.items() if key != "artifact_sha256"}
        _require(amendment["artifact_sha256"] == sha256(_canonical_json(body)).hexdigest())
        request_bytes = _REQUEST_PATH.read_bytes()
        request = json.loads(request_bytes)
        _require(isinstance(request, dict))
        _require(request.get("schema_version") == "GENERATION4-PHASE7-SOURCE-AMENDMENT-INDEPENDENT-AUDIT-REQUEST-v1")
        _require(request.get("status") == "READY_FOR_INDEPENDENT_AUDIT")
        _require(request.get("authority") == "NONE")
        for field in (
            "original_evaluation_authorization_sha256", "first_checkpoint_contract_sha256",
            "implementation_commit", "source_sha256", "candidate_id",
            "checkpoint_evaluation_authorized",
        ):
            _require(request.get(field) == amendment[field])
        expected = {
            "schema_version": "GENERATION4-PHASE7-SOURCE-AMENDMENT-AUTHORIZATION-v1",
            "status": "GENERATION4_PHASE7_SOURCE_AMENDMENT_AUTHORIZED",
            "authority": "INDEPENDENT_AUDIT",
            "audit_request_sha256": sha256(request_bytes).hexdigest(),
            "original_evaluation_authorization_id": contract["evaluation_authorization_id"],
            "original_evaluation_authorization_sha256": contract["evaluation_authorization_sha256"],
            "evaluation_contract_sha256": contract["evaluation_contract_sha256"],
            "first_checkpoint_contract_sha256": _FIRST_CONTRACT_SHA256,
            "candidate_id": contract["candidate_id"],
            "research_universe": contract["research_universe"],
            "forbidden_holdout_symbols": contract["forbidden_holdout_symbols"],
            "benchmark_symbol": contract["benchmark_symbol"],
            "friction_cases_bps": contract["friction_cases_bps"],
            "primary_friction_bps": contract["primary_friction_bps"],
            "first_scored_session": contract["first_scored_session"],
            "warmup_session_count": contract["warmup_session_count"],
            "dq030_status": "UNRESOLVED",
            "recon009_status": "OPEN",
            "paper_only": True,
        }
        for field, value in expected.items():
            _require(type(amendment[field]) is type(value) and amendment[field] == value)
        _require(original_authorization.authorization_id == amendment["original_evaluation_authorization_id"])
        for field in _FALSE_FLAGS:
            _require(amendment[field] is False)
        _require(isinstance(amendment["authorization_id"], str) and
                 amendment["authorization_id"].startswith("INDEP-AUDIT-GEN4-PHASE7-SOURCE-"))
        approved = datetime.fromisoformat(amendment["approved_at_utc"].replace("Z", "+00:00"))
        _require(approved.tzinfo is not None and approved.utcoffset() is not None)
        _verify_sources(amendment["implementation_commit"], amendment["source_sha256"])
    except SourceAmendmentError:
        raise
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        raise SourceAmendmentError("source_amendment_invalid_or_missing") from None
