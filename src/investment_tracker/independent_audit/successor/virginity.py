from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from investment_tracker.independent_audit.phase6.authority import canonical_json_bytes
from investment_tracker.independent_audit.phase6 import replacement as legacy_helpers

EVIDENCE_SCHEMA = "SUCCESSOR-COMPOSITE-VIRGINITY-EVIDENCE-v1"
ATTESTATION_SCHEMA = "SUCCESSOR-VIRGIN-HOLDOUT-ATTESTATION-v1"
ATTESTATION_STATUS = "COMPOSITE_EVIDENCE_NO_PRIOR_SELECTED_SYMBOL_ACCESS_FOUND"
LIMITATIONS = (
    "PROVIDER_QUOTA_HISTORY_LIMITED_TO_CURRENT_7_DAY_PERIOD",
    "RETAINED_LOCAL_LOGS_NOT_PROVIDER_IMMUTABLE",
)


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _load_selection(path: Path) -> tuple[dict[str, Any], tuple[str, ...]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("SUCCESSOR_VIRGINITY_SELECTION_INVALID") from exc
    if (
        payload.get("schema_version") != "SUCCESSOR-BLIND-FINAL-HOLDOUT-SELECTION-v1"
        or payload.get("status") != "SUCCESSOR_HOLDOUT_SELECTION_FROZEN"
        or payload.get("historical_market_data_api_called") is not False
        or payload.get("protected_history_access_authorized") is not False
    ):
        raise ValueError("SUCCESSOR_VIRGINITY_SELECTION_INVALID")
    selected = payload.get("selected")
    if not isinstance(selected, list) or not selected:
        raise ValueError("SUCCESSOR_VIRGINITY_SELECTION_INVALID")
    symbols = tuple(str(item.get("symbol", "")).strip().upper() for item in selected)
    if any(not symbol for symbol in symbols) or len(set(symbols)) != len(symbols):
        raise ValueError("SUCCESSOR_VIRGINITY_SELECTION_INVALID")
    return payload, symbols


def _provider_quota(context: Any, sdk: Any) -> tuple[int, int, list[dict[str, str]]]:
    ret, data = context.get_history_kl_quota(get_detail=True)
    if ret != sdk.RET_OK or not isinstance(data, tuple) or len(data) != 3:
        raise RuntimeError(f"SUCCESSOR_VIRGINITY_PROVIDER_QUOTA_FAILED:{data}")
    used, remaining, details = data
    if (
        isinstance(used, bool)
        or not isinstance(used, int)
        or isinstance(remaining, bool)
        or not isinstance(remaining, int)
        or not isinstance(details, list)
    ):
        raise ValueError("SUCCESSOR_VIRGINITY_PROVIDER_QUOTA_INVALID")
    rows: list[dict[str, str]] = []
    for item in details:
        if not isinstance(item, dict):
            raise ValueError("SUCCESSOR_VIRGINITY_PROVIDER_QUOTA_INVALID")
        rows.append(
            {
                "code": str(item.get("code", "")).strip().upper(),
                "name": str(item.get("name", "")).strip(),
                "request_time": str(item.get("request_time", "")).strip(),
            }
        )
    rows.sort(key=lambda item: (item["code"], item["request_time"], item["name"]))
    return used, remaining, rows


def capture_virginity(
    *,
    selection_path: Path,
    log_paths: tuple[Path, ...],
    evidence_output_path: Path,
    attestation_output_path: Path,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> tuple[Path, Path]:
    for output in (evidence_output_path, attestation_output_path):
        if Path(output).exists():
            raise FileExistsError(f"SUCCESSOR_VIRGINITY_OUTPUT_EXISTS:{Path(output).name}")

    selection, symbols = _load_selection(selection_path)
    sdk, sdk_name = legacy_helpers._load_sdk()
    context = sdk.OpenQuoteContext(host=host, port=port)
    try:
        used, remaining, details = _provider_quota(context, sdk)
    finally:
        context.close()

    locked_codes = {f"US.{symbol}" for symbol in symbols}
    provider_matches = sorted(
        {
            item["code"][3:]
            for item in details
            if item["code"] in locked_codes
        }
    )
    contaminated, file_manifest, history_contexts = legacy_helpers._history_context_symbols(
        log_paths,
        candidate_symbols=set(symbols),
    )
    log_matches = sorted(set(symbols).intersection(contaminated))

    captured_at = datetime.now(timezone.utc).isoformat()
    evidence = {
        "schema_version": EVIDENCE_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": (
            ATTESTATION_STATUS
            if not provider_matches and not log_matches
            else "SELECTED_SYMBOL_PRIOR_ACCESS_DETECTED"
        ),
        "selection_sha256": _sha(selection_path),
        "successor_formal_name": selection["successor_formal_name"],
        "selected_symbols": list(symbols),
        "captured_at_utc": captured_at,
        "provider": {
            "sdk_module": sdk_name,
            "api": "get_history_kl_quota",
            "get_detail": True,
            "used_quota": used,
            "remaining_quota": remaining,
            "locked_symbol_matches": provider_matches,
            "details": details,
        },
        "retained_logs": {
            "files": file_manifest,
            "history_contexts": history_contexts,
            "locked_symbol_history_matches": log_matches,
        },
        "complete_lifetime_query_history": False,
        "limitations": list(LIMITATIONS),
        "historical_market_data_api_called": False,
        "strategy_evaluation_executed": False,
        "protected_history_access_authorized": False,
        "phase7_authorized": False,
    }
    evidence_bytes = canonical_json_bytes(evidence)
    evidence_path = Path(evidence_output_path)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_bytes(evidence_bytes)

    if provider_matches or log_matches:
        raise ValueError(
            "SUCCESSOR_VIRGINITY_FAILED:"
            f"provider={','.join(provider_matches) or 'NONE'}:"
            f"logs={','.join(log_matches) or 'NONE'}"
        )

    evidence_sha = sha256(evidence_bytes).hexdigest()
    attestation = {
        "schema_version": ATTESTATION_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": ATTESTATION_STATUS,
        "attestation_id": f"successor-virginity-{evidence_sha[:32]}",
        "successor_formal_name": selection["successor_formal_name"],
        "selected_symbols": list(symbols),
        "selection_sha256": _sha(selection_path),
        "evidence_bundle_sha256": evidence_sha,
        "captured_at_utc": captured_at,
        "provider_used_quota": used,
        "provider_remaining_quota": remaining,
        "provider_locked_symbol_matches": [],
        "retained_log_locked_symbol_history_matches": [],
        "complete_query_history": False,
        "limitations": list(LIMITATIONS),
        "historical_market_data_api_called": False,
        "protected_history_access_authorized": False,
        "phase7_authorized": False,
    }
    attestation_path = Path(attestation_output_path)
    attestation_path.parent.mkdir(parents=True, exist_ok=True)
    attestation_path.write_bytes(canonical_json_bytes(attestation))
    return evidence_path, attestation_path


def verify_attestation(
    *,
    selection_path: Path,
    evidence_path: Path,
    attestation_path: Path,
) -> dict[str, Any]:
    selection, symbols = _load_selection(selection_path)
    try:
        evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
        attestation = json.loads(Path(attestation_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("SUCCESSOR_VIRGINITY_ATTESTATION_INVALID") from exc
    if (
        evidence.get("status") != ATTESTATION_STATUS
        or attestation.get("schema_version") != ATTESTATION_SCHEMA
        or attestation.get("status") != ATTESTATION_STATUS
        or attestation.get("selected_symbols") != list(symbols)
        or attestation.get("selection_sha256") != _sha(selection_path)
        or attestation.get("evidence_bundle_sha256") != _sha(evidence_path)
        or attestation.get("historical_market_data_api_called") is not False
        or attestation.get("protected_history_access_authorized") is not False
    ):
        raise ValueError("SUCCESSOR_VIRGINITY_ATTESTATION_INVALID")
    return attestation
