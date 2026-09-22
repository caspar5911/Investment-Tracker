from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .authority import load_methodology_authorization

SCHEMA = "SUCCESSOR-HOLDOUT-SELECTION-CONTRACT-v1"
STATUS = "FROZEN_AFTER_INDEPENDENT_AUDIT_BEFORE_CANDIDATE_QUERY"


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def build_holdout_selection_contract(
    *,
    authorization_path: Path,
    corporate_action_contract_path: Path,
    holdout_exclusion_registry_path: Path,
    predecessor_closure_path: Path,
) -> dict[str, Any]:
    auth = load_methodology_authorization(
        authorization_path=authorization_path,
        corporate_action_contract_path=corporate_action_contract_path,
        holdout_exclusion_registry_path=holdout_exclusion_registry_path,
        predecessor_closure_path=predecessor_closure_path,
    )
    return {
        "schema_version": SCHEMA,
        "status": STATUS,
        "authority": "INDEPENDENT_AUDIT",
        "successor_formal_name": auth.successor_formal_name,
        "methodology_authorization_id": auth.approval_id,
        "methodology_authorization_sha256": _sha(authorization_path),
        "corporate_action_contract_sha256": auth.corporate_action_contract_sha256,
        "holdout_exclusion_registry_sha256": auth.holdout_exclusion_registry_sha256,
        "evaluation_window": {
            "start": auth.evaluation_calendar_start,
            "end": auth.evaluation_calendar_end,
        },
        "required_warmup_sessions": auth.required_pre_window_sessions,
        "selection_count": auth.selection_count,
        "listing_cutoff": auth.listing_cutoff,
        "selection_seed_sha256": auth.selection_seed_sha256,
        "candidate_universe": {
            "market": "US",
            "security_type": "ETF",
            "permitted_static_fields": [
                "code",
                "name",
                "listing_date",
                "delisting",
                "stock_type",
            ],
            "historical_prices_allowed": False,
            "returns_allowed": False,
            "volume_allowed": False,
            "fundamentals_allowed": False,
            "performance_ranking_allowed": False,
        },
        "selection_rules": {
            "apply_permanent_exclusion_registry_before_ranking": True,
            "exclude_provider_history_ledger_symbols": True,
            "exclude_retained_log_history_symbols": True,
            "deterministic_hash_ranking": True,
            "manual_substitution_allowed": False,
            "insufficient_eligible_symbols_result": "UNKNOWN_ABSTAIN",
        },
        "governance": {
            "protected_history_access_authorized": False,
            "one_time_acquisition_required": True,
            "retry_after_historical_access_allowed": False,
            "phase7_authorized": False,
            "production_readiness_approved": False,
            "recon009_status": "OPEN",
            "paper_only": True,
        },
    }


def seal_holdout_selection_contract(payload: dict[str, Any], output_path: Path) -> Path:
    path = Path(output_path)
    if path.exists():
        raise FileExistsError("SUCCESSOR_SELECTION_CONTRACT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return path
