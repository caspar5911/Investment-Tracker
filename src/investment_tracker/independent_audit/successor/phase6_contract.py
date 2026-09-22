from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .authority import load_methodology_authorization
from .virginity import verify_attestation

SCHEMA = "SUCCESSOR-PHASE6-EVALUATION-CONTRACT-v1"
STATUS = "FROZEN_PRE_ACCESS"


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _load_selection(path: Path) -> tuple[dict[str, Any], tuple[str, ...]]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("SUCCESSOR_PHASE6_SELECTION_INVALID") from exc
    if (
        value.get("schema_version") != "SUCCESSOR-BLIND-FINAL-HOLDOUT-SELECTION-v1"
        or value.get("status") != "SUCCESSOR_HOLDOUT_SELECTION_FROZEN"
        or value.get("historical_market_data_api_called") is not False
        or value.get("protected_history_access_authorized") is not False
    ):
        raise ValueError("SUCCESSOR_PHASE6_SELECTION_INVALID")
    selected = value.get("selected")
    if not isinstance(selected, list) or not selected:
        raise ValueError("SUCCESSOR_PHASE6_SELECTION_INVALID")
    symbols = tuple(str(item.get("symbol", "")).strip().upper() for item in selected)
    if any(not symbol for symbol in symbols) or len(symbols) != len(set(symbols)):
        raise ValueError("SUCCESSOR_PHASE6_SELECTION_INVALID")
    return value, symbols


def build_phase6_contract(
    *,
    methodology_authorization_path: Path,
    selection_path: Path,
    virginity_evidence_path: Path,
    virginity_attestation_path: Path,
    corporate_action_contract_path: Path,
    successor_normalizer_path: Path,
    successor_evaluator_path: Path,
    holdout_exclusion_registry_path: Path,
    predecessor_closure_path: Path,
) -> dict[str, Any]:
    auth = load_methodology_authorization(
        authorization_path=methodology_authorization_path,
        corporate_action_contract_path=corporate_action_contract_path,
        holdout_exclusion_registry_path=holdout_exclusion_registry_path,
        predecessor_closure_path=predecessor_closure_path,
        successor_normalizer_path=successor_normalizer_path,
        successor_evaluator_path=successor_evaluator_path,
    )
    selection, symbols = _load_selection(selection_path)
    if (
        selection.get("successor_formal_name") != auth.successor_formal_name
        or selection.get("methodology_authorization_id") != auth.approval_id
        or selection.get("methodology_authorization_sha256") != _sha(methodology_authorization_path)
        or selection.get("candidate_id") != auth.candidate_id
        or selection.get("binding_sha256") != auth.binding_sha256
        or selection.get("implementation_sha256") != auth.implementation_sha256
        or selection.get("successor_normalizer_sha256") != auth.successor_normalizer_sha256
        or selection.get("successor_evaluator_sha256") != auth.successor_evaluator_sha256
        or len(symbols) != auth.selection_count
    ):
        raise ValueError("SUCCESSOR_PHASE6_SELECTION_IDENTITY_MISMATCH")

    attestation = verify_attestation(
        selection_path=selection_path,
        evidence_path=virginity_evidence_path,
        attestation_path=virginity_attestation_path,
    )
    if attestation.get("selected_symbols") != list(symbols):
        raise ValueError("SUCCESSOR_PHASE6_VIRGINITY_SYMBOL_MISMATCH")

    return {
        "schema_version": SCHEMA,
        "status": STATUS,
        "authority": "INDEPENDENT_AUDIT",
        "successor_formal_name": auth.successor_formal_name,
        "methodology_authorization_id": auth.approval_id,
        "methodology_authorization_sha256": _sha(methodology_authorization_path),
        "strategy": {
            "candidate_id": auth.candidate_id,
            "binding_sha256": auth.binding_sha256,
            "implementation_sha256": auth.implementation_sha256,
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
        },
        "final_holdout": {
            "locked_symbols": list(symbols),
            "calendar_start": auth.evaluation_calendar_start,
            "calendar_end": auth.evaluation_calendar_end,
            "required_pre_window_sessions": auth.required_pre_window_sessions,
            "benchmark_reference_symbol": "SPY",
            "selection_sha256": _sha(selection_path),
            "virginity_attestation_sha256": _sha(virginity_attestation_path),
            "virginity_evidence_sha256": _sha(virginity_evidence_path),
            "holdout_exclusion_registry_sha256": _sha(holdout_exclusion_registry_path),
        },
        "methodology": {
            "accounting": "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v2",
            "signal_price_convention": "MOOMOO_QFQ_DAILY_RTH",
            "execution_price_convention": "MOOMOO_UNADJUSTED_DAILY_RTH",
            "marking_price_convention": "MOOMOO_UNADJUSTED_DAILY_RTH",
            "corporate_action_normalization_contract": "CORPORATE-ACTION-NORMALIZATION-CONTRACT-v2",
            "corporate_action_contract_sha256": _sha(corporate_action_contract_path),
            "successor_normalizer_sha256": _sha(successor_normalizer_path),
            "successor_evaluator_sha256": _sha(successor_evaluator_path),
            "corporate_action_sources": [
                "MOOMOO_REHAB",
                "MOOMOO_CORPORATE_ACTION_DIVIDENDS",
                "MOOMOO_CORPORATE_ACTION_STOCK_SPLITS",
            ],
            "fractional_shares": "RETAIN_IN_RESEARCH_LEDGER",
            "cash_distributions": "GROSS_WITH_RECEIVABLE_FROM_EX_DATE_TO_PAY_DATE",
            "same_bar_execution_allowed": False,
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
            "methodology_authorized": True,
            "virginity_verified": True,
            "protected_history_access_authorized": False,
            "acquisition_authorization_required": True,
            "one_time_acquisition_required": True,
            "retry_after_historical_access_allowed": False,
            "phase7_authorized": False,
            "production_readiness_approved": False,
            "recon009_status": "OPEN",
            "paper_only": True,
        },
    }


def seal_phase6_contract(payload: dict[str, Any], output_path: Path) -> Path:
    path = Path(output_path)
    if path.exists():
        raise FileExistsError("SUCCESSOR_PHASE6_CONTRACT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def verify_phase6_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("SUCCESSOR_PHASE6_CONTRACT_INVALID") from exc
    if (
        payload.get("schema_version") != SCHEMA
        or payload.get("status") != STATUS
        or payload.get("authority") != "INDEPENDENT_AUDIT"
        or payload.get("governance", {}).get("protected_history_access_authorized") is not False
        or payload.get("governance", {}).get("phase7_authorized") is not False
        or payload.get("governance", {}).get("paper_only") is not True
    ):
        raise ValueError("SUCCESSOR_PHASE6_CONTRACT_INVALID")
    return payload
