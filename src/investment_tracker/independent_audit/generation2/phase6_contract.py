from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from investment_tracker.quant.generation2.campaign import content_sha256
from investment_tracker.quant.generation2.survivor_identity import verify_survivor_identity

from .preaccess import STATUS_READY
from .research_provenance_cache import verify_cache_provenance
from .virginity import (
    FROZEN_BINDING_SHA256,
    FROZEN_CANDIDATE_ID,
    FROZEN_IMPLEMENTATION_SHA256,
    FROZEN_IDENTITY_SHA256,
    LOCKED_SYMBOLS,
    verify_attestation,
)

CONTRACT_SCHEMA = "GENERATION2-PHASE6-EVALUATION-CONTRACT-v1"
CONTRACT_STATUS = "FROZEN_PRE_ACCESS"


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def build_contract(
    *,
    repository_root: Path,
    preaccess_status_path: Path,
    selection_path: Path,
    selection_contract_path: Path,
    virginity_attestation_path: Path,
    virginity_evidence_path: Path,
    provenance_root: Path,
) -> dict[str, Any]:
    repository_root = Path(repository_root)
    preaccess = json.loads(Path(preaccess_status_path).read_text(encoding="utf-8"))
    if preaccess.get("status") != STATUS_READY:
        raise ValueError("GEN2_PHASE6_CONTRACT_PREACCESS_NOT_READY")
    if preaccess.get("locked_symbols") != list(LOCKED_SYMBOLS):
        raise ValueError("GEN2_PHASE6_CONTRACT_SYMBOL_SET_MISMATCH")
    if preaccess.get("independent_source_established") is not True:
        raise ValueError("GEN2_PHASE6_CONTRACT_PROVENANCE_NOT_ESTABLISHED")

    attestation = verify_attestation(
        attestation_path=virginity_attestation_path,
        evidence_path=virginity_evidence_path,
        selection_path=selection_path,
        selection_contract_path=selection_contract_path,
    )
    provenance = verify_cache_provenance(Path(provenance_root))
    if (
        provenance.get("status") != "MATCHED"
        or provenance.get("independent_source_established") is not True
        or provenance.get("decision_critical") is not False
    ):
        raise ValueError("GEN2_PHASE6_CONTRACT_RECONCILIATION_NOT_MATCHED")
    if preaccess.get("primary_snapshot_sha256") != provenance.get("primary_snapshot_sha256"):
        raise ValueError("GEN2_PHASE6_CONTRACT_PREACCESS_PRIMARY_SNAPSHOT_MISMATCH")
    if preaccess.get("provider_origin_snapshot_sha256") != provenance.get("provider_origin_snapshot_sha256"):
        raise ValueError("GEN2_PHASE6_CONTRACT_PREACCESS_PROVIDER_SNAPSHOT_MISMATCH")
    if preaccess.get("reconciliation_sha256") != provenance.get("reconciliation_sha256"):
        raise ValueError("GEN2_PHASE6_CONTRACT_PREACCESS_RECONCILIATION_MISMATCH")

    identity = verify_survivor_identity(
        repository_root / "data" / "governance" / "generation2-campaign",
        repository_root,
    )
    if identity.get("candidate_id") != FROZEN_CANDIDATE_ID:
        raise ValueError("GEN2_PHASE6_CONTRACT_CANDIDATE_MISMATCH")
    if identity.get("binding_sha256") != FROZEN_BINDING_SHA256:
        raise ValueError("GEN2_PHASE6_CONTRACT_BINDING_MISMATCH")
    if identity.get("implementation_sha256") != FROZEN_IMPLEMENTATION_SHA256:
        raise ValueError("GEN2_PHASE6_CONTRACT_IMPLEMENTATION_MISMATCH")
    if identity.get("report_sha256") != FROZEN_IDENTITY_SHA256:
        raise ValueError("GEN2_PHASE6_CONTRACT_IDENTITY_MISMATCH")

    candidate_binding = identity["candidate_binding"]
    expected = {
        "candidate_id": FROZEN_CANDIDATE_ID,
        "family": "G2-A",
        "lookback": 189,
        "skip": 21,
        "top_k": 1,
        "rebalance": 21,
    }
    for key, value in expected.items():
        if candidate_binding.get(key) != value:
            raise ValueError(f"GEN2_PHASE6_CONTRACT_PARAMETER_MISMATCH:{key}")

    payload: dict[str, Any] = {
        "schema_version": CONTRACT_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": CONTRACT_STATUS,
        "generation": "GENERATION_2",
        "strategy": {
            "candidate_id": FROZEN_CANDIDATE_ID,
            "family": "G2-A",
            "candidate_binding": candidate_binding,
            "binding_sha256": FROZEN_BINDING_SHA256,
            "implementation_sha256": FROZEN_IMPLEMENTATION_SHA256,
            "survivor_identity_report_sha256": FROZEN_IDENTITY_SHA256,
            "long_only": True,
            "portfolio_leverage_allowed": False,
            "short_selling_allowed": False,
            "candidate_search_allowed": False,
            "parameter_mutation_allowed": False,
            "signal_on_completed_session": True,
            "earliest_fill": "NEXT_ELIGIBLE_SESSION_OPEN",
        },
        "final_holdout": {
            "locked_symbols": list(LOCKED_SYMBOLS),
            "calendar_start": "2023-01-01",
            "calendar_end": "2025-12-31",
            "required_pre_window_sessions": 210,
            "benchmark_reference_symbol": "SPY",
            "selection_sha256": _sha(selection_path),
            "selection_contract_sha256": _sha(selection_contract_path),
            "virginity_attestation_sha256": _sha(virginity_attestation_path),
            "virginity_evidence_sha256": _sha(virginity_evidence_path),
            "independent_reconciliation_sha256": provenance["reconciliation_sha256"],
            "primary_research_snapshot_sha256": provenance["primary_snapshot_sha256"],
            "provider_origin_research_snapshot_sha256": provenance["provider_origin_snapshot_sha256"],
            "preaccess_status_sha256": _sha(preaccess_status_path),
        },
        "methodology": {
            "accounting": "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1",
            "signal_price_convention": "MOOMOO_QFQ_DAILY_RTH",
            "execution_price_convention": "MOOMOO_UNADJUSTED_DAILY_RTH",
            "marking_price_convention": "MOOMOO_UNADJUSTED_DAILY_RTH",
            "corporate_action_sources": [
                "MOOMOO_REHAB",
                "MOOMOO_CORPORATE_ACTION_DIVIDENDS",
                "MOOMOO_CORPORATE_ACTION_STOCK_SPLITS",
            ],
            "fractional_shares": "RETAIN_IN_RESEARCH_LEDGER",
            "cash_distributions": "GROSS_WITH_RECEIVABLE_FROM_EX_DATE_TO_PAY_DATE",
            "same_bar_execution_allowed": False,
            "decision_grade_accounting_contract": True,
        },
        "friction": {
            "initial_cash": 100000.0,
            "primary_friction_bps": 3,
            "fixed_friction_cases_bps": [0, 3, 10, 25, 50],
            "basis": "ABSOLUTE_TRADED_NOTIONAL_BUYS_AND_SELLS",
        },
        "metrics": {
            "required": [
                "total_return",
                "cagr",
                "sharpe",
                "sortino",
                "annualized_one_way_turnover",
                "max_drawdown",
                "calmar",
                "rolling_12m_positive_fraction",
                "all_session_exposure_invariant",
            ],
            "max_drawdown_convention": "GENERATION2-DQ030",
            "performance_pass_threshold": None,
        },
        "result_contract": {
            "complete_status": "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE",
            "incomplete_or_dq_status": "PHASE6_UNKNOWN_ABSTAIN",
            "one_time_consumption_required": True,
            "phase7_requires_complete_status_and_explicit_entry_artifact": True,
        },
        "governance": {
            "independent_source_established": True,
            "virginity_verified": True,
            "historical_access_authorized": False,
            "phase7_authorized": False,
            "production_readiness_approved": False,
            "paper_only": True,
        },
    }
    payload["contract_sha256"] = content_sha256(payload)
    return payload


def seal_contract(payload: dict[str, Any], output_path: Path) -> Path:
    output = Path(output_path)
    if output.exists():
        raise FileExistsError("GEN2_PHASE6_CONTRACT_EXISTS")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return output


def verify_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    claimed = payload.pop("contract_sha256", None)
    if claimed is None or content_sha256(payload) != claimed:
        raise ValueError("GEN2_PHASE6_CONTRACT_HASH_MISMATCH")
    if payload.get("schema_version") != CONTRACT_SCHEMA or payload.get("status") != CONTRACT_STATUS:
        raise ValueError("GEN2_PHASE6_CONTRACT_SCHEMA_STATUS_MISMATCH")
    if payload.get("final_holdout", {}).get("locked_symbols") != list(LOCKED_SYMBOLS):
        raise ValueError("GEN2_PHASE6_CONTRACT_SYMBOL_SET_MISMATCH")
    if payload.get("governance", {}).get("historical_access_authorized") is not False:
        raise ValueError("GEN2_PHASE6_CONTRACT_AUTHORITY_MISMATCH")
    payload["contract_sha256"] = claimed
    return payload
