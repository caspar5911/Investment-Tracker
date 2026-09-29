from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd

from investment_tracker.independent_audit.phase6.authority import canonical_json_bytes
from investment_tracker.independent_audit.phase6 import replacement as legacy_helpers
from investment_tracker.quant.generation2.holdout_exclusion import (
    excluded_symbols,
    load_holdout_exclusion_registry,
)

from .authority import load_methodology_authorization

SELECTION_SCHEMA = "SUCCESSOR-BLIND-FINAL-HOLDOUT-SELECTION-v1"
STATIC_SCHEMA = "SUCCESSOR-HOLDOUT-STATIC-SNAPSHOT-v1"
PROVIDER_LEDGER_SCHEMA = "SUCCESSOR-HOLDOUT-PROVIDER-HISTORY-LEDGER-v1"
_CANONICAL_SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,11}$")


@dataclass(frozen=True)
class Candidate:
    symbol: str
    code: str
    name: str
    listing_date: str
    rank_key: str


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _load_selection_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("SUCCESSOR_SELECTION_CONTRACT_INVALID") from exc
    if (
        payload.get("schema_version") != "SUCCESSOR-HOLDOUT-SELECTION-CONTRACT-v1"
        or payload.get("status") != "FROZEN_AFTER_INDEPENDENT_AUDIT_BEFORE_CANDIDATE_QUERY"
        or payload.get("authority") != "INDEPENDENT_AUDIT"
    ):
        raise ValueError("SUCCESSOR_SELECTION_CONTRACT_INVALID")
    governance = payload.get("governance", {})
    if (
        governance.get("protected_history_access_authorized") is not False
        or governance.get("phase7_authorized") is not False
        or governance.get("paper_only") is not True
    ):
        raise ValueError("SUCCESSOR_SELECTION_CONTRACT_GOVERNANCE_INVALID")
    return payload


def _static_snapshot(frame: pd.DataFrame) -> bytes:
    rows = [
        {
            "code": str(row.get("code", "")),
            "name": str(row.get("name", "")),
            "listing_date": str(row.get("listing_date", "")),
            "delisting": bool(row.get("delisting", False)),
            "stock_type": str(row.get("stock_type", "ETF")),
        }
        for row in frame.to_dict(orient="records")
    ]
    rows.sort(key=lambda item: (item["code"], item["name"]))
    if len({item["code"] for item in rows}) != len(rows):
        raise ValueError("SUCCESSOR_HOLDOUT_STATIC_DUPLICATE_CODE")
    return canonical_json_bytes(
        {
            "schema_version": STATIC_SCHEMA,
            "provider": "MOOMOO_OPEND",
            "market": "US",
            "security_type": "ETF",
            "permitted_fields": [
                "code",
                "name",
                "listing_date",
                "delisting",
                "stock_type",
            ],
            "rows": rows,
        }
    )


def _provider_history_ledger(context: Any, sdk: Any) -> tuple[set[str], bytes]:
    ret, data = context.get_history_kl_quota(get_detail=True)
    if ret != sdk.RET_OK or not isinstance(data, tuple) or len(data) != 3:
        raise RuntimeError(f"SUCCESSOR_PROVIDER_LEDGER_FAILED:{data}")
    used, remaining, details = data
    if not isinstance(details, list):
        raise ValueError("SUCCESSOR_PROVIDER_LEDGER_INVALID")
    rows: list[dict[str, str]] = []
    symbols: set[str] = set()
    for item in details:
        if not isinstance(item, dict):
            raise ValueError("SUCCESSOR_PROVIDER_LEDGER_ROW_INVALID")
        code = str(item.get("code", "")).strip().upper()
        request_time = str(item.get("request_time", ""))
        name = str(item.get("name", ""))
        if code.startswith("US."):
            symbol = code[3:]
            if _CANONICAL_SYMBOL_PATTERN.fullmatch(symbol):
                symbols.add(symbol)
        rows.append({"code": code, "name": name, "request_time": request_time})
    rows.sort(key=lambda item: (item["code"], item["request_time"], item["name"]))
    return symbols, canonical_json_bytes(
        {
            "schema_version": PROVIDER_LEDGER_SCHEMA,
            "provider": "MOOMOO_OPEND",
            "provider_limitations": ["CURRENT_PROVIDER_QUOTA_HISTORY_WINDOW_ONLY"],
            "used_quota": int(used),
            "remaining_quota": int(remaining),
            "details": rows,
        }
    )


def _rank_key(seed: str, symbol: str) -> str:
    return sha256(f"{seed}|{symbol}".encode("ascii")).hexdigest()


def select_from_static_frame(
    frame: pd.DataFrame,
    *,
    permanent_exclusions: frozenset[str],
    provider_history_symbols: set[str],
    retained_log_history_symbols: set[str],
    listing_cutoff: date,
    selection_count: int,
    seed_sha256: str,
) -> tuple[tuple[Candidate, ...], dict[str, int]]:
    excluded = {
        "invalid_code": 0,
        "delisted": 0,
        "listing_date_missing_or_too_late": 0,
        "invalid_or_blocked_name": 0,
        "permanent_exclusion_registry": 0,
        "provider_history_ledger": 0,
        "retained_log_history_context": 0,
    }
    eligible: list[Candidate] = []
    seen: set[str] = set()

    for row in frame.to_dict(orient="records"):
        code = str(row.get("code", "")).strip().upper()
        if not code.startswith("US."):
            excluded["invalid_code"] += 1
            continue
        symbol = code[3:]
        if not _CANONICAL_SYMBOL_PATTERN.fullmatch(symbol) or symbol in seen:
            excluded["invalid_code"] += 1
            continue
        seen.add(symbol)

        if bool(row.get("delisting", False)):
            excluded["delisted"] += 1
            continue
        listed = legacy_helpers._listing_date(row.get("listing_date"))
        if listed is None or listed > listing_cutoff:
            excluded["listing_date_missing_or_too_late"] += 1
            continue
        name = str(row.get("name", "")).strip()
        if legacy_helpers._blocked_name(name):
            excluded["invalid_or_blocked_name"] += 1
            continue
        if symbol in permanent_exclusions:
            excluded["permanent_exclusion_registry"] += 1
            continue
        if symbol in provider_history_symbols:
            excluded["provider_history_ledger"] += 1
            continue
        if symbol in retained_log_history_symbols:
            excluded["retained_log_history_context"] += 1
            continue

        eligible.append(
            Candidate(
                symbol=symbol,
                code=code,
                name=name,
                listing_date=listed.isoformat(),
                rank_key=_rank_key(seed_sha256, symbol),
            )
        )

    eligible.sort(key=lambda item: (item.rank_key, item.symbol))
    return tuple(eligible[:selection_count]), excluded


def acquire_and_select(
    *,
    repository_root: Path,
    methodology_authorization_path: Path,
    selection_contract_path: Path,
    corporate_action_contract_path: Path,
    successor_normalizer_path: Path,
    successor_evaluator_path: Path,
    holdout_exclusion_registry_path: Path,
    predecessor_closure_path: Path,
    log_paths: tuple[Path, ...],
    output_path: Path,
    static_snapshot_path: Path,
    provider_ledger_output_path: Path,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> Path:
    for output in (output_path, static_snapshot_path, provider_ledger_output_path):
        if Path(output).exists():
            raise FileExistsError(f"SUCCESSOR_HOLDOUT_SELECTION_OUTPUT_EXISTS:{Path(output).name}")

    auth = load_methodology_authorization(
        authorization_path=methodology_authorization_path,
        corporate_action_contract_path=corporate_action_contract_path,
        holdout_exclusion_registry_path=holdout_exclusion_registry_path,
        predecessor_closure_path=predecessor_closure_path,
        successor_normalizer_path=successor_normalizer_path,
        successor_evaluator_path=successor_evaluator_path,
    )
    contract = _load_selection_contract(selection_contract_path)
    if (
        contract.get("methodology_authorization_id") != auth.approval_id
        or contract.get("methodology_authorization_sha256") != _sha(methodology_authorization_path)
        or contract.get("candidate_id") != auth.candidate_id
        or contract.get("binding_sha256") != auth.binding_sha256
        or contract.get("implementation_sha256") != auth.implementation_sha256
        or contract.get("successor_normalizer_sha256") != auth.successor_normalizer_sha256
        or contract.get("successor_evaluator_sha256") != auth.successor_evaluator_sha256
        or contract.get("holdout_exclusion_registry_sha256") != _sha(holdout_exclusion_registry_path)
    ):
        raise ValueError("SUCCESSOR_SELECTION_CONTRACT_IDENTITY_MISMATCH")

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
        "successor_normalizer_sha256": auth.successor_normalizer_sha256,
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
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(payload)
    return Path(output_path)
