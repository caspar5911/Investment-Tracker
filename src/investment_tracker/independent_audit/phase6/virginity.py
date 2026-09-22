from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import importlib
from pathlib import Path
from typing import Any

from .authority import (
    CONTRACT_SHA256,
    LOCKED_SYMBOLS,
    VirginHoldoutAttestation,
    canonical_json_bytes,
)
from .replacement import _history_context_symbols


PROVIDER_PROTOCOL_ID = 3104
PROVIDER_WINDOW_DAYS = 7
LIMITATIONS = (
    "PROVIDER_QUOTA_HISTORY_LIMITED_TO_CURRENT_7_DAY_PERIOD",
    "RETAINED_LOCAL_LOGS_NOT_PROVIDER_IMMUTABLE",
)


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


def _provider_quota(context: Any, sdk: Any) -> tuple[int, int, list[dict[str, str]]]:
    ret, data = context.get_history_kl_quota(get_detail=True)
    if ret != sdk.RET_OK:
        raise RuntimeError(f"PHASE6_PROVIDER_QUOTA_FAILED:{data}")
    if not isinstance(data, tuple) or len(data) != 3:
        raise ValueError("PHASE6_PROVIDER_QUOTA_SCHEMA_MISMATCH")
    used, remaining, raw_details = data
    if (
        isinstance(used, bool)
        or not isinstance(used, int)
        or used < 0
        or isinstance(remaining, bool)
        or not isinstance(remaining, int)
        or remaining < 0
        or not isinstance(raw_details, list)
    ):
        raise ValueError("PHASE6_PROVIDER_QUOTA_SCHEMA_MISMATCH")

    details: list[dict[str, str]] = []
    for item in raw_details:
        if not isinstance(item, dict):
            raise ValueError("PHASE6_PROVIDER_QUOTA_DETAIL_INVALID")
        code = str(item.get("code", "")).strip().upper()
        name = str(item.get("name", "")).strip()
        request_time = str(item.get("request_time", "")).strip()
        if not code or not request_time:
            raise ValueError("PHASE6_PROVIDER_QUOTA_DETAIL_INVALID")
        details.append(
            {
                "code": code,
                "name": name,
                "request_time": request_time,
            }
        )
    details.sort(key=lambda item: (item["code"], item["request_time"], item["name"]))
    if used != len(details):
        raise ValueError("PHASE6_PROVIDER_QUOTA_DETAIL_COUNT_MISMATCH")
    return used, remaining, details


def capture_composite_virginity(
    *,
    log_paths: tuple[Path, ...],
    evidence_output_path: Path,
    attestation_output_path: Path,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> tuple[Path, Path]:
    evidence_output = Path(evidence_output_path)
    attestation_output = Path(attestation_output_path)
    for output in (evidence_output, attestation_output):
        if output.exists():
            raise FileExistsError(f"PHASE6_COMPOSITE_EVIDENCE_OUTPUT_EXISTS:{output.name}")

    sdk, sdk_name = _load_sdk()
    context = sdk.OpenQuoteContext(host=host, port=port)
    try:
        used, remaining, details = _provider_quota(context, sdk)
    finally:
        context.close()

    locked_codes = {f"US.{symbol}" for symbol in LOCKED_SYMBOLS}
    provider_matches = tuple(
        item["code"]
        for item in details
        if item["code"] in locked_codes
    )

    contaminated, file_manifest, history_contexts = _history_context_symbols(
        log_paths,
        candidate_symbols=set(LOCKED_SYMBOLS),
    )
    log_locked_matches = tuple(
        symbol for symbol in LOCKED_SYMBOLS if symbol in contaminated
    )

    provider_detail_bytes = canonical_json_bytes(
        {
            "schema_version": "PHASE6-PROVIDER-QUOTA-DETAIL-v1",
            "provider": "MOOMOO_OPEND",
            "protocol": "Qot_RequestHistoryKLQuota",
            "protocol_id": PROVIDER_PROTOCOL_ID,
            "window_days": PROVIDER_WINDOW_DAYS,
            "used_quota": used,
            "remaining_quota": remaining,
            "details": details,
        }
    )
    log_manifest_bytes = canonical_json_bytes(
        {
            "schema_version": "PHASE6-RETAINED-LOG-MANIFEST-v1",
            "files": file_manifest,
        }
    )
    history_context_bytes = canonical_json_bytes(
        {
            "schema_version": "PHASE6-RETAINED-LOG-HISTORY-CONTEXT-v1",
            "history_protocol": "Qot_RequestHistoryKL",
            "history_protocol_id": 3103,
            "context_radius_lines": 8,
            "contexts": history_contexts,
        }
    )

    captured_at = datetime.now(timezone.utc)
    evidence = {
        "schema_version": "PHASE6-COMPOSITE-VIRGINITY-EVIDENCE-v1",
        "authority": "INDEPENDENT_AUDIT",
        "evaluation_contract_sha256": CONTRACT_SHA256,
        "locked_symbols": list(LOCKED_SYMBOLS),
        "captured_at_utc": captured_at.isoformat(),
        "provider": {
            "sdk_module": sdk_name,
            "api": "get_history_kl_quota",
            "get_detail": True,
            "protocol": "Qot_RequestHistoryKLQuota",
            "protocol_id": PROVIDER_PROTOCOL_ID,
            "window_days": PROVIDER_WINDOW_DAYS,
            "used_quota": used,
            "remaining_quota": remaining,
            "detail_sha256": sha256(provider_detail_bytes).hexdigest(),
            "locked_symbol_matches": list(provider_matches),
            "details": details,
        },
        "retained_logs": {
            "file_manifest_sha256": sha256(log_manifest_bytes).hexdigest(),
            "history_context_sha256": sha256(history_context_bytes).hexdigest(),
            "file_count": len(file_manifest),
            "history_context_count": len(history_contexts),
            "locked_symbol_history_matches": list(log_locked_matches),
            "files": file_manifest,
            "history_contexts": history_contexts,
        },
        "complete_lifetime_query_history": False,
        "limitations": list(LIMITATIONS),
        "historical_market_data_api_called": False,
        "strategy_evaluation_executed": False,
    }
    evidence_bytes = canonical_json_bytes(evidence)
    evidence_output.parent.mkdir(parents=True, exist_ok=True)
    evidence_output.write_bytes(evidence_bytes)

    if provider_matches or log_locked_matches:
        raise ValueError(
            "PHASE6_COMPOSITE_VIRGINITY_FAILED:"
            f"provider={','.join(provider_matches) or 'NONE'}:"
            f"logs={','.join(log_locked_matches) or 'NONE'}"
        )

    evidence_sha = sha256(evidence_bytes).hexdigest()
    seed = canonical_json_bytes(
        {
            "contract_sha256": CONTRACT_SHA256,
            "evidence_bundle_sha256": evidence_sha,
            "locked_symbols": list(LOCKED_SYMBOLS),
        }
    )
    attestation = VirginHoldoutAttestation(
        schema_version="PHASE6-VIRGIN-HOLDOUT-ATTESTATION-v2",
        authority="INDEPENDENT_AUDIT",
        status="COMPOSITE_EVIDENCE_NO_PRIOR_LOCKED_SYMBOL_ACCESS_FOUND",
        attestation_id=f"phase6-composite-{sha256(seed).hexdigest()[:32]}",
        locked_symbols=LOCKED_SYMBOLS,
        evidence_kind="COMPOSITE_PROVIDER_QUOTA_AND_RETAINED_LOGS",
        evidence_bundle_sha256=evidence_sha,
        captured_at_utc=captured_at,
        provider_quota_protocol_id=PROVIDER_PROTOCOL_ID,
        provider_quota_window_days=PROVIDER_WINDOW_DAYS,
        provider_used_quota=used,
        provider_remaining_quota=remaining,
        provider_detail_sha256=sha256(provider_detail_bytes).hexdigest(),
        provider_locked_symbol_matches=(),
        retained_log_manifest_sha256=sha256(log_manifest_bytes).hexdigest(),
        retained_log_history_context_sha256=sha256(history_context_bytes).hexdigest(),
        retained_log_locked_symbol_history_matches=(),
        complete_query_history=False,
        independent_provider_component=True,
        local_retained_log_component=True,
        coordinator_self_report_only=False,
        limitations=LIMITATIONS,
    )
    attestation_output.parent.mkdir(parents=True, exist_ok=True)
    attestation_output.write_bytes(
        canonical_json_bytes(attestation.model_dump(mode="json"))
    )
    return evidence_output, attestation_output
