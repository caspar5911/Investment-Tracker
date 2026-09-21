from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import importlib
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd

from investment_tracker.independent_audit.phase6.authority import canonical_json_bytes

PROTOCOL_VERSION = "PHASE6-BLIND-REPLACEMENT-v1"
PREREGISTRATION_COMMIT_SHA = "0ddff58e36a2637ff5d12d044f1fee12e64e9a00"
ORIGINAL_CONTRACT_SHA256 = "f64f31c20172491f6175a176592d463fed36f73ecf2b99542022afa55f50b77e"
REJECTED_CLASSIFICATION_SHA256 = "7d450b567211e4590434af8aa93c28b943eecc053be2620647d446139c4ce2f0"
SELECTION_SEED_MATERIAL = (
    f"{PROTOCOL_VERSION}|{ORIGINAL_CONTRACT_SHA256}|{REJECTED_CLASSIFICATION_SHA256}"
)
SELECTION_SEED = sha256(SELECTION_SEED_MATERIAL.encode("ascii")).hexdigest()
LISTING_CUTOFF = date(2022, 6, 2)
SELECTION_COUNT = 5
RESEARCH_SYMBOLS = frozenset(("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP"))
REJECTED_SYMBOLS = frozenset(("HACK", "SOXX", "NLR", "URNM", "GEV"))
FORBIDDEN_SYMBOLS = RESEARCH_SYMBOLS | REJECTED_SYMBOLS
_HISTORY_TOKENS = (
    "Qot_RequestHistoryKL",
    "RequestHistoryKL",
    "request_history_kline",
    "protoid=3103",
    "proto_id=3103",
    "proto id=3103",
    "proto:3103",
    "proto=3103",
)
_US_SYMBOL_PATTERN = re.compile(r"(?<![A-Z0-9])US[.]([A-Z][A-Z0-9.-]{0,11})(?![A-Z0-9])")
_CANONICAL_SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,11}$")
_LEVERAGED_TOKEN_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?:-?[123]X)(?![A-Z0-9])",
)
_NAME_BLOCK_TOKENS = (
    "LEVERAGED",
    "INVERSE",
    "ULTRAPRO",
    "ULTRASHORT",
    "ULTRA",
    "BEAR",
    "ETN",
)
_CONTEXT_RADIUS = 8


@dataclass(frozen=True)
class Candidate:
    symbol: str
    code: str
    name: str
    listing_date: str
    rank_key: str


def _load_sdk() -> tuple[Any, str]:
    errors: list[str] = []
    for module_name in ("moomoo", "futu"):
        try:
            return importlib.import_module(module_name), module_name
        except ImportError as exc:
            errors.append(str(exc))
    raise RuntimeError(
        "MOOMOO_OR_FUTU_OPEND_PYTHON_PACKAGE_REQUIRED:" + "|".join(errors)
    )


def _static_frame(context: Any, sdk: Any) -> pd.DataFrame:
    ret, data = context.get_stock_basicinfo(
        sdk.Market.US,
        sdk.SecurityType.ETF,
    )
    if ret != sdk.RET_OK:
        raise RuntimeError(f"PHASE6_REPLACEMENT_STATIC_INFO_FAILED:{data}")
    if not isinstance(data, pd.DataFrame):
        raise ValueError("PHASE6_REPLACEMENT_STATIC_INFO_INVALID")
    required = {"code", "name", "listing_date", "delisting"}
    if not required.issubset(data.columns):
        raise ValueError("PHASE6_REPLACEMENT_STATIC_INFO_SCHEMA_MISMATCH")
    columns = ["code", "name", "listing_date", "delisting"]
    if "stock_type" in data.columns:
        columns.append("stock_type")
    return data.loc[:, columns].copy(deep=True)


def _canonical_static_snapshot(frame: pd.DataFrame) -> bytes:
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
        raise ValueError("PHASE6_REPLACEMENT_STATIC_INFO_DUPLICATE_CODE")
    return canonical_json_bytes(
        {
            "schema_version": "PHASE6-REPLACEMENT-STATIC-SNAPSHOT-v1",
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


def _files(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    result: list[Path] = []
    for supplied in paths:
        path = Path(supplied).resolve()
        if path.is_file():
            result.append(path)
        elif path.is_dir():
            result.extend(item for item in path.rglob("*") if item.is_file())
        else:
            raise FileNotFoundError(path)
    ordered = tuple(sorted(set(result), key=lambda item: str(item)))
    if not ordered:
        raise ValueError("PHASE6_REPLACEMENT_LOG_SET_EMPTY")
    return ordered


def _history_context_symbols(
    paths: tuple[Path, ...],
) -> tuple[set[str], list[dict[str, object]], list[dict[str, object]]]:
    contaminated: set[str] = set()
    file_manifest: list[dict[str, object]] = []
    contexts: list[dict[str, object]] = []

    for path in _files(paths):
        payload = path.read_bytes()
        file_manifest.append(
            {
                "path": str(path),
                "sha256": sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
        lines = payload.decode("utf-8", errors="replace").splitlines()
        history_lines = [
            index
            for index, line in enumerate(lines)
            if any(token.lower() in line.lower() for token in _HISTORY_TOKENS)
        ]
        for history_index in history_lines:
            start = max(0, history_index - _CONTEXT_RADIUS)
            end = min(len(lines), history_index + _CONTEXT_RADIUS + 1)
            context = "\n".join(lines[start:end]).upper()
            symbols = sorted(set(_US_SYMBOL_PATTERN.findall(context)))
            for symbol in symbols:
                contaminated.add(symbol)
            contexts.append(
                {
                    "path": str(path),
                    "history_line_number": history_index + 1,
                    "symbols": symbols,
                }
            )

    file_manifest.sort(key=lambda item: str(item["path"]))
    contexts.sort(
        key=lambda item: (str(item["path"]), int(item["history_line_number"]))
    )
    return contaminated, file_manifest, contexts


def _listing_date(value: object) -> date | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _blocked_name(name: str) -> bool:
    normalized = " ".join(str(name).upper().split())
    if not normalized or normalized == "UNKNOWN STOCK":
        return True
    if any(token in normalized for token in _NAME_BLOCK_TOKENS):
        return True
    if _LEVERAGED_TOKEN_PATTERN.search(normalized):
        return True
    if "DAILY" in normalized and any(
        token in normalized for token in ("BULL", "BEAR", "LONG", "SHORT")
    ):
        return True
    return False


def _rank_key(symbol: str) -> str:
    return sha256(f"{SELECTION_SEED}|{symbol}".encode("ascii")).hexdigest()


def select_from_static_frame(
    frame: pd.DataFrame,
    *,
    contaminated_symbols: set[str],
) -> tuple[tuple[Candidate, ...], dict[str, int]]:
    excluded: dict[str, int] = {
        "invalid_code": 0,
        "delisted": 0,
        "listing_date_missing_or_too_late": 0,
        "invalid_or_blocked_name": 0,
        "research_or_rejected_symbol": 0,
        "historical_kline_context": 0,
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

        listed = _listing_date(row.get("listing_date"))
        if listed is None or listed > LISTING_CUTOFF:
            excluded["listing_date_missing_or_too_late"] += 1
            continue

        name = str(row.get("name", "")).strip()
        if _blocked_name(name):
            excluded["invalid_or_blocked_name"] += 1
            continue

        if symbol in FORBIDDEN_SYMBOLS:
            excluded["research_or_rejected_symbol"] += 1
            continue

        if symbol in contaminated_symbols:
            excluded["historical_kline_context"] += 1
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
    return tuple(eligible[:SELECTION_COUNT]), excluded


def acquire_and_select(
    *,
    log_paths: tuple[Path, ...],
    output_path: Path,
    static_snapshot_path: Path,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> Path:
    for output in (Path(output_path), Path(static_snapshot_path)):
        if output.exists():
            raise FileExistsError(f"PHASE6_REPLACEMENT_OUTPUT_EXISTS:{output.name}")

    sdk, sdk_name = _load_sdk()
    context = sdk.OpenQuoteContext(host=host, port=port)
    try:
        frame = _static_frame(context, sdk)
    finally:
        context.close()

    # The final log snapshot is intentionally taken after the permitted static
    # metadata request and immediately before deterministic ranking. This closes
    # the selection-time race in which another historical request could occur
    # after an earlier contamination scan.
    contaminated, file_manifest, history_contexts = _history_context_symbols(log_paths)

    static_snapshot = _canonical_static_snapshot(frame)
    selected, excluded = select_from_static_frame(
        frame,
        contaminated_symbols=contaminated,
    )

    log_manifest_bytes = canonical_json_bytes(
        {
            "schema_version": "PHASE6-REPLACEMENT-LOG-MANIFEST-v1",
            "files": file_manifest,
        }
    )
    history_context_bytes = canonical_json_bytes(
        {
            "schema_version": "PHASE6-REPLACEMENT-HISTORY-CONTEXT-v1",
            "context_radius_lines": _CONTEXT_RADIUS,
            "history_protocol": "Qot_RequestHistoryKL",
            "history_protocol_id": 3103,
            "contexts": history_contexts,
        }
    )

    status = (
        "PHASE6_REPLACEMENT_SELECTION_FROZEN"
        if len(selected) == SELECTION_COUNT
        else "PHASE6_REPLACEMENT_SELECTION_UNKNOWN_ABSTAIN"
    )
    result = {
        "schema_version": "PHASE6-BLIND-REPLACEMENT-SELECTION-v1",
        "authority": "INDEPENDENT_AUDIT",
        "status": status,
        "protocol_version": PROTOCOL_VERSION,\n        "preregistration_commit_sha": PREREGISTRATION_COMMIT_SHA,
        "original_evaluation_contract_sha256": ORIGINAL_CONTRACT_SHA256,
        "rejected_holdout_classification_sha256": REJECTED_CLASSIFICATION_SHA256,
        "selection_seed_material": SELECTION_SEED_MATERIAL,
        "selection_seed_sha256": SELECTION_SEED,
        "provider": "MOOMOO_OPEND",
        "provider_sdk_module": sdk_name,
        "static_api": "get_stock_basicinfo",
        "market": "US",
        "security_type": "ETF",
        "listing_cutoff": LISTING_CUTOFF.isoformat(),
        "selection_count_required": SELECTION_COUNT,
        "static_snapshot_sha256": sha256(static_snapshot).hexdigest(),
        "log_manifest_sha256": sha256(log_manifest_bytes).hexdigest(),
        "history_context_manifest_sha256": sha256(history_context_bytes).hexdigest(),
        "historically_accessed_symbol_count": len(contaminated),
        "excluded_counts": excluded,
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
        "safety": {
            "historical_market_data_api_called": False,
            "market_snapshot_api_called": False,
            "quote_api_called": False,
            "rehab_api_called": False,
            "fundamental_api_called": False,
            "trading_api_called": False,
            "strategy_evaluation_executed": False,
            "candidate_search_executed": False,
            "candidate_parameters_changed": False,
            "phase7_started": False,
        },
    }

    static_output = Path(static_snapshot_path)
    static_output.parent.mkdir(parents=True, exist_ok=True)
    static_output.write_bytes(static_snapshot)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json_bytes(result))
    return output
