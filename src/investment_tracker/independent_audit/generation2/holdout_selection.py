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
    registry_content_sha256,
)
from investment_tracker.quant.generation2.survivor_identity import (
    verify_survivor_identity,
)

CONTRACT_SCHEMA = "GENERATION2-BLIND-FINAL-HOLDOUT-SELECTION-CONTRACT-v1"
RESULT_SCHEMA = "GENERATION2-BLIND-FINAL-HOLDOUT-SELECTION-v1"
STATIC_SCHEMA = "GENERATION2-HOLDOUT-STATIC-SNAPSHOT-v1"
PROVIDER_LEDGER_SCHEMA = "GENERATION2-HOLDOUT-PROVIDER-HISTORY-LEDGER-v1"
LOG_MANIFEST_SCHEMA = "GENERATION2-HOLDOUT-LOG-MANIFEST-v1"
HISTORY_CONTEXT_SCHEMA = "GENERATION2-HOLDOUT-HISTORY-CONTEXT-v1"

FROZEN_PROTOCOL_VERSION = "GENERATION2-BLIND-FINAL-HOLDOUT-v1"
FROZEN_SEED_SHA256 = "bc41de35fd0b4889a98d06b614e353696a29c539d9398f1d19b2bb7df0094094"
FROZEN_LISTING_CUTOFF = date(2022, 3, 3)
FROZEN_SELECTION_COUNT = 5
FROZEN_IDENTITY_SHA256 = "96580b61ddb617f54157cc2ce12f5dc5316dc143321f1aaf214e7a563b5aff87"
FROZEN_BINDING_SHA256 = "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"
FROZEN_IMPLEMENTATION_SHA256 = "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"
FROZEN_REGISTRY_SHA256 = "1c7965d2b6250aab9f521dd2c9605e5beb277785a08f846c3ba35447b4e16651"
FROZEN_CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"

_CANONICAL_SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,11}$")


@dataclass(frozen=True)
class Candidate:
    symbol: str
    code: str
    name: str
    listing_date: str
    rank_key: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_contract() -> Path:
    return _repo_root() / "data" / "governance" / "generation2-holdout-selection-contract.json"


def _default_identity_root() -> Path:
    return _repo_root() / "data" / "governance" / "generation2-campaign"


def _load_contract(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("schema_version") != CONTRACT_SCHEMA:
        raise ValueError("GEN2_HOLDOUT_SELECTION_CONTRACT_SCHEMA_MISMATCH")
    exact = {
        "status": "FROZEN_BEFORE_CANDIDATE_UNIVERSE_QUERY",
        "authority": "INDEPENDENT_AUDIT",
        "protocol_version": FROZEN_PROTOCOL_VERSION,
        "candidate_id": FROZEN_CANDIDATE_ID,
        "survivor_identity_report_sha256": FROZEN_IDENTITY_SHA256,
        "binding_sha256": FROZEN_BINDING_SHA256,
        "implementation_sha256": FROZEN_IMPLEMENTATION_SHA256,
        "holdout_exclusion_registry_sha256": FROZEN_REGISTRY_SHA256,
        "listing_cutoff": FROZEN_LISTING_CUTOFF.isoformat(),
        "selection_count": FROZEN_SELECTION_COUNT,
        "historical_holdout_access_authorized": False,
        "phase6_authorized": False,
        "phase7_authorized": False,
        "production_readiness_approved": False,
    }
    for key, value in exact.items():
        if payload.get(key) != value:
            raise ValueError(f"GEN2_HOLDOUT_SELECTION_CONTRACT_MISMATCH:{key}")
    ranking = payload.get("ranking")
    if not isinstance(ranking, dict) or ranking.get("seed_sha256") != FROZEN_SEED_SHA256:
        raise ValueError("GEN2_HOLDOUT_SELECTION_SEED_MISMATCH")
    return payload, sha256(raw).hexdigest()


def _verify_frozen_inputs(
    *,
    contract_path: Path,
    identity_root: Path,
    registry_path: Path,
) -> tuple[dict[str, Any], str, frozenset[str]]:
    contract, contract_sha = _load_contract(contract_path)
    identity = verify_survivor_identity(identity_root, _repo_root())
    if identity.get("report_sha256") != FROZEN_IDENTITY_SHA256:
        raise ValueError("GEN2_HOLDOUT_SELECTION_IDENTITY_MISMATCH")
    if identity.get("binding_sha256") != FROZEN_BINDING_SHA256:
        raise ValueError("GEN2_HOLDOUT_SELECTION_BINDING_MISMATCH")
    if identity.get("implementation_sha256") != FROZEN_IMPLEMENTATION_SHA256:
        raise ValueError("GEN2_HOLDOUT_SELECTION_IMPLEMENTATION_MISMATCH")
    registry = load_holdout_exclusion_registry(registry_path)
    if registry_content_sha256(registry) != FROZEN_REGISTRY_SHA256:
        raise ValueError("GEN2_HOLDOUT_SELECTION_REGISTRY_MISMATCH")
    return contract, contract_sha, excluded_symbols(registry)


def _static_snapshot(frame: pd.DataFrame) -> bytes:
    rows: list[dict[str, object]] = []
    for row in frame.to_dict(orient="records"):
        rows.append(
            {
                "code": str(row.get("code", "")),
                "name": str(row.get("name", "")),
                "listing_date": str(row.get("listing_date", "")),
                "delisting": bool(row.get("delisting", False)),
                "stock_type": str(row.get("stock_type", "ETF")),
            }
        )
    rows.sort(key=lambda item: (item["code"], item["name"]))
    if len({item["code"] for item in rows}) != len(rows):
        raise ValueError("GEN2_HOLDOUT_STATIC_DUPLICATE_CODE")
    return canonical_json_bytes(
        {
            "schema_version": STATIC_SCHEMA,
            "provider": "MOOMOO_OPEND",
            "market": "US",
            "security_type": "ETF",
            "permitted_fields": ["code", "name", "listing_date", "delisting", "stock_type"],
            "rows": rows,
        }
    )


def _provider_history_ledger(context: Any, sdk: Any) -> tuple[set[str], bytes]:
    ret, data = context.get_history_kl_quota(get_detail=True)
    if ret != sdk.RET_OK:
        raise RuntimeError(f"GEN2_HOLDOUT_PROVIDER_LEDGER_FAILED:{data}")
    if not isinstance(data, tuple) or len(data) != 3:
        raise ValueError("GEN2_HOLDOUT_PROVIDER_LEDGER_INVALID")
    used, remaining, details = data
    if not isinstance(details, list):
        raise ValueError("GEN2_HOLDOUT_PROVIDER_LEDGER_DETAILS_INVALID")
    rows: list[dict[str, str]] = []
    symbols: set[str] = set()
    for item in details:
        if not isinstance(item, dict):
            raise ValueError("GEN2_HOLDOUT_PROVIDER_LEDGER_ROW_INVALID")
        code = str(item.get("code", "")).strip().upper()
        request_time = str(item.get("request_time", ""))
        name = str(item.get("name", ""))
        if code.startswith("US."):
            symbol = code[3:]
            if _CANONICAL_SYMBOL_PATTERN.fullmatch(symbol):
                symbols.add(symbol)
        rows.append({"code": code, "name": name, "request_time": request_time})
    rows.sort(key=lambda item: (item["code"], item["request_time"], item["name"]))
    payload = canonical_json_bytes(
        {
            "schema_version": PROVIDER_LEDGER_SCHEMA,
            "provider": "MOOMOO_OPEND",
            "provider_limitations": ["CURRENT_PROVIDER_QUOTA_HISTORY_WINDOW_ONLY"],
            "used_quota": int(used),
            "remaining_quota": int(remaining),
            "details": rows,
        }
    )
    return symbols, payload


def _rank_key(symbol: str) -> str:
    return sha256(f"{FROZEN_SEED_SHA256}|{symbol}".encode("ascii")).hexdigest()


def select_from_static_frame(
    frame: pd.DataFrame,
    *,
    permanent_exclusions: frozenset[str],
    provider_history_symbols: set[str],
    retained_log_history_symbols: set[str],
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
        if listed is None or listed > FROZEN_LISTING_CUTOFF:
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
                rank_key=_rank_key(symbol),
            )
        )

    eligible.sort(key=lambda item: (item.rank_key, item.symbol))
    return tuple(eligible[:FROZEN_SELECTION_COUNT]), excluded


def acquire_and_select(
    *,
    log_paths: tuple[Path, ...],
    output_path: Path,
    static_snapshot_path: Path,
    provider_ledger_output_path: Path,
    contract_path: Path | None = None,
    identity_root: Path | None = None,
    registry_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> Path:
    contract_path = contract_path or _default_contract()
    identity_root = identity_root or _default_identity_root()
    registry_path = registry_path or (_repo_root() / "data" / "governance" / "holdout-exclusion-registry.json")

    for path in (output_path, static_snapshot_path, provider_ledger_output_path):
        if Path(path).exists():
            raise FileExistsError(f"GEN2_HOLDOUT_SELECTION_OUTPUT_EXISTS:{Path(path).name}")

    contract, contract_sha, permanent = _verify_frozen_inputs(
        contract_path=Path(contract_path),
        identity_root=Path(identity_root),
        registry_path=Path(registry_path),
    )

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
    )

    static_bytes = _static_snapshot(frame)
    log_manifest_bytes = canonical_json_bytes(
        {"schema_version": LOG_MANIFEST_SCHEMA, "files": file_manifest}
    )
    history_context_bytes = canonical_json_bytes(
        {
            "schema_version": HISTORY_CONTEXT_SCHEMA,
            "context_radius_lines": 8,
            "history_protocol": "Qot_RequestHistoryKL",
            "history_protocol_id": 3103,
            "contexts": history_contexts,
        }
    )

    status = (
        "GENERATION2_HOLDOUT_SELECTION_FROZEN"
        if len(selected) == FROZEN_SELECTION_COUNT
        else "GENERATION2_HOLDOUT_SELECTION_UNKNOWN_ABSTAIN"
    )
    result = {
        "schema_version": RESULT_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": status,
        "protocol_version": FROZEN_PROTOCOL_VERSION,
        "selection_contract_sha256": contract_sha,
        "candidate_id": FROZEN_CANDIDATE_ID,
        "survivor_identity_report_sha256": FROZEN_IDENTITY_SHA256,
        "binding_sha256": FROZEN_BINDING_SHA256,
        "implementation_sha256": FROZEN_IMPLEMENTATION_SHA256,
        "holdout_exclusion_registry_sha256": FROZEN_REGISTRY_SHA256,
        "selection_seed_sha256": FROZEN_SEED_SHA256,
        "evaluation_window": contract["evaluation_window"],
        "required_warmup_sessions": contract["required_warmup_sessions"],
        "listing_cutoff": FROZEN_LISTING_CUTOFF.isoformat(),
        "selection_count_required": FROZEN_SELECTION_COUNT,
        "provider": "MOOMOO_OPEND",
        "provider_sdk_module": sdk_name,
        "static_api": "get_stock_basicinfo",
        "provider_access_evidence_api": "get_history_kl_quota",
        "static_snapshot_sha256": sha256(static_bytes).hexdigest(),
        "provider_ledger_sha256": sha256(provider_ledger).hexdigest(),
        "log_manifest_sha256": sha256(log_manifest_bytes).hexdigest(),
        "history_context_manifest_sha256": sha256(history_context_bytes).hexdigest(),
        "provider_history_symbol_count": len(provider_history_symbols),
        "retained_log_history_symbol_count": len(retained_history),
        "excluded_counts": excluded_counts,
        "selected": [
            {
                "position": i + 1,
                "symbol": item.symbol,
                "code": item.code,
                "name": item.name,
                "listing_date": item.listing_date,
                "rank_key": item.rank_key,
            }
            for i, item in enumerate(selected)
        ],
        "safety": {
            "historical_market_data_api_called": False,
            "quote_api_called": False,
            "market_snapshot_api_called": False,
            "rehab_api_called": False,
            "fundamental_api_called": False,
            "trading_api_called": False,
            "strategy_evaluation_executed": False,
            "candidate_parameters_changed": False,
            "phase6_authorized": False,
            "phase7_started": False,
            "production_readiness_approved": False,
        },
    }

    Path(static_snapshot_path).parent.mkdir(parents=True, exist_ok=True)
    Path(static_snapshot_path).write_bytes(static_bytes)
    Path(provider_ledger_output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(provider_ledger_output_path).write_bytes(provider_ledger)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(canonical_json_bytes(result))
    return Path(output_path)
