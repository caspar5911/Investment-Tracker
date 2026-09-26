from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from investment_tracker.independent_audit.phase6.authority import canonical_json_bytes
from investment_tracker.independent_audit.phase6 import replacement as legacy_helpers
from investment_tracker.independent_audit.successor.holdout_selection import (
    _provider_history_ledger,
    _static_snapshot,
    select_from_static_frame,
)
from investment_tracker.quant.generation2.holdout_exclusion import (
    excluded_symbols,
    load_holdout_exclusion_registry,
)

from .authority import load_methodology_authorization
from .selection_contract import SCHEMA as CONTRACT_SCHEMA, STATUS as CONTRACT_STATUS

SELECTION_SCHEMA = "SUCCESSOR-BLIND-FINAL-HOLDOUT-SELECTION-v1"


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _load_selection_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("POST_GEN3_SELECTION_CONTRACT_INVALID") from exc
    if (
        payload.get("schema_version") != CONTRACT_SCHEMA
        or payload.get("status") != CONTRACT_STATUS
        or payload.get("authority") != "INDEPENDENT_AUDIT"
    ):
        raise ValueError("POST_GEN3_SELECTION_CONTRACT_INVALID")
    governance = payload.get("governance", {})
    if (
        governance.get("protected_history_access_authorized") is not False
        or governance.get("symbol_substitution_after_access_allowed") is not False
        or governance.get("phase7_authorized") is not False
        or governance.get("paper_only") is not True
    ):
        raise ValueError("POST_GEN3_SELECTION_CONTRACT_GOVERNANCE_INVALID")
    return payload


def acquire_and_select(
    *,
    methodology_authorization_path: Path,
    selection_contract_path: Path,
    predecessor_closure_path: Path,
    split_contract_path: Path,
    dividend_contract_path: Path,
    split_normalizer_path: Path,
    dividend_reconciliation_path: Path,
    successor_evaluator_path: Path,
    holdout_exclusion_registry_path: Path,
    log_paths: tuple[Path, ...],
    output_path: Path,
    static_snapshot_path: Path,
    provider_ledger_output_path: Path,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> Path:
    for output in (output_path, static_snapshot_path, provider_ledger_output_path):
        if Path(output).exists():
            raise FileExistsError(
                f"POST_GEN3_HOLDOUT_SELECTION_OUTPUT_EXISTS:{Path(output).name}"
            )

    auth = load_methodology_authorization(
        authorization_path=methodology_authorization_path,
        predecessor_closure_path=predecessor_closure_path,
        split_contract_path=split_contract_path,
        dividend_contract_path=dividend_contract_path,
        split_normalizer_path=split_normalizer_path,
        dividend_reconciliation_path=dividend_reconciliation_path,
        successor_evaluator_path=successor_evaluator_path,
        holdout_exclusion_registry_path=holdout_exclusion_registry_path,
    )
    contract = _load_selection_contract(selection_contract_path)

    exact = {
        "methodology_authorization_id": auth.approval_id,
        "methodology_authorization_sha256": _sha(methodology_authorization_path),
        "candidate_id": auth.candidate_id,
        "binding_sha256": auth.binding_sha256,
        "implementation_sha256": auth.implementation_sha256,
        "split_contract_sha256": auth.split_contract_sha256,
        "dividend_contract_sha256": auth.dividend_contract_sha256,
        "split_normalizer_sha256": auth.split_normalizer_sha256,
        "dividend_reconciliation_sha256": auth.dividend_reconciliation_sha256,
        "successor_evaluator_sha256": auth.successor_evaluator_sha256,
        "holdout_exclusion_registry_sha256": _sha(holdout_exclusion_registry_path),
    }
    if any(contract.get(key) != value for key, value in exact.items()):
        raise ValueError("POST_GEN3_SELECTION_CONTRACT_IDENTITY_MISMATCH")

    registry = load_holdout_exclusion_registry(holdout_exclusion_registry_path)
    permanent = excluded_symbols(registry)
    seed = str(contract["selection_seed_sha256"])
    cutoff = date.fromisoformat(str(contract["listing_cutoff"]))
    count = int(contract["selection_count"])

    sdk, sdk_name = legacy_helpers._load_sdk()
    context = sdk.OpenQuoteContext(host=host, port=port)
    try:
        frame = legacy_helpers._static_frame(context, sdk)
        provider_history_symbols, provider_ledger = _provider_history_ledger(context, sdk)
    finally:
        context.close()

    candidate_symbols = {
        str(code).strip().upper()[3:]
        for code in frame["code"].tolist()
        if str(code).strip().upper().startswith("US.")
    }
    retained_history, file_manifest, history_contexts = legacy_helpers._history_context_symbols(
        log_paths,
        candidate_symbols=candidate_symbols,
    )
    selected, excluded_counts = select_from_static_frame(
        frame,
        permanent_exclusions=permanent,
        provider_history_symbols=provider_history_symbols,
        retained_log_history_symbols=retained_history,
        listing_cutoff=cutoff,
        selection_count=count,
        seed_sha256=seed,
    )

    static_bytes = _static_snapshot(frame)
    status = (
        "SUCCESSOR_HOLDOUT_SELECTION_FROZEN"
        if len(selected) == count
        else "SUCCESSOR_HOLDOUT_SELECTION_UNKNOWN_ABSTAIN"
    )
    result = {
        "schema_version": SELECTION_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": status,
        "successor_formal_name": auth.successor_formal_name,
        "methodology_authorization_id": auth.approval_id,
        "methodology_authorization_sha256": _sha(methodology_authorization_path),
        "selection_contract_sha256": _sha(selection_contract_path),
        "candidate_id": auth.candidate_id,
        "binding_sha256": auth.binding_sha256,
        "implementation_sha256": auth.implementation_sha256,
        "split_contract_sha256": auth.split_contract_sha256,
        "dividend_contract_sha256": auth.dividend_contract_sha256,
        "split_normalizer_sha256": auth.split_normalizer_sha256,
        "dividend_reconciliation_sha256": auth.dividend_reconciliation_sha256,
        "successor_evaluator_sha256": auth.successor_evaluator_sha256,
        "holdout_exclusion_registry_sha256": _sha(holdout_exclusion_registry_path),
        "selection_seed_sha256": seed,
        "evaluation_window": contract["evaluation_window"],
        "required_warmup_sessions": contract["required_warmup_sessions"],
        "listing_cutoff": contract["listing_cutoff"],
        "selection_count_required": count,
        "provider": "MOOMOO_OPEND",
        "provider_sdk_module": sdk_name,
        "static_api": "get_stock_basicinfo",
        "provider_access_evidence_api": "get_history_kl_quota",
        "static_snapshot_sha256": sha256(static_bytes).hexdigest(),
        "provider_ledger_sha256": sha256(provider_ledger).hexdigest(),
        "retained_log_manifest_sha256": sha256(
            canonical_json_bytes({"files": file_manifest})
        ).hexdigest(),
        "retained_history_context_sha256": sha256(
            canonical_json_bytes({"contexts": history_contexts})
        ).hexdigest(),
        "excluded_counts": excluded_counts,
        "selected": [
            {
                "position": index + 1,
                "symbol": item.symbol,
                "code": item.code,
                "name": item.name,
                "listing_date": item.listing_date,
                "rank_key": item.rank_key,
            }
            for index, item in enumerate(selected)
        ],
        "historical_market_data_api_called": False,
        "protected_history_access_authorized": False,
        "phase7_authorized": False,
        "production_readiness_approved": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }

    for path, payload in (
        (static_snapshot_path, static_bytes),
        (provider_ledger_output_path, provider_ledger),
        (output_path, canonical_json_bytes(result)),
    ):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return Path(output_path)
