from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from investment_tracker.independent_audit.phase6.authority import canonical_json_bytes
from investment_tracker.independent_audit.phase6.replacement import _history_context_symbols
from investment_tracker.independent_audit.generation2.holdout_selection import (
    FROZEN_BINDING_SHA256,
    FROZEN_CANDIDATE_ID,
    FROZEN_IMPLEMENTATION_SHA256,
    FROZEN_IDENTITY_SHA256,
    _load_contract,
)
from investment_tracker.independent_audit.phase6.virginity import _load_sdk, _provider_quota

LOCKED_SYMBOLS = ("BNO", "GBIL", "CWS", "ESG", "VICI")
SELECTION_SCHEMA = "GENERATION2-BLIND-FINAL-HOLDOUT-SELECTION-v1"
SELECTION_STATUS = "GENERATION2_HOLDOUT_SELECTION_FROZEN"
EVIDENCE_SCHEMA = "GENERATION2-COMPOSITE-VIRGINITY-EVIDENCE-v1"
ATTESTATION_SCHEMA = "GENERATION2-VIRGIN-HOLDOUT-ATTESTATION-v1"
ATTESTATION_STATUS = "COMPOSITE_EVIDENCE_NO_PRIOR_LOCKED_SYMBOL_ACCESS_FOUND"
PROVIDER_PROTOCOL_ID = 3104
PROVIDER_WINDOW_DAYS = 7
LIMITATIONS = (
    "PROVIDER_QUOTA_HISTORY_LIMITED_TO_CURRENT_7_DAY_PERIOD",
    "RETAINED_LOCAL_LOGS_NOT_PROVIDER_IMMUTABLE",
    "INDEPENDENT_SOURCE_PROVENANCE_GATE_OPEN",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_selection() -> Path:
    return _repo_root() / "data" / "generation2" / "holdout-selection" / "selection.json"


def _default_contract() -> Path:
    return _repo_root() / "data" / "governance" / "generation2-holdout-selection-contract.json"


def _verify_selection(path: Path, contract_path: Path) -> tuple[dict[str, Any], str, str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    contract, contract_sha = _load_contract(contract_path)
    expected = {
        "schema_version": SELECTION_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": SELECTION_STATUS,
        "candidate_id": FROZEN_CANDIDATE_ID,
        "binding_sha256": FROZEN_BINDING_SHA256,
        "implementation_sha256": FROZEN_IMPLEMENTATION_SHA256,
        "survivor_identity_report_sha256": FROZEN_IDENTITY_SHA256,
        "selection_contract_sha256": contract_sha,
        "selection_seed_sha256": contract["ranking"]["seed_sha256"],
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(f"GEN2_VIRGINITY_SELECTION_MISMATCH:{key}")
    selected = payload.get("selected")
    if not isinstance(selected, list) or [item.get("symbol") for item in selected] != list(LOCKED_SYMBOLS):
        raise ValueError("GEN2_VIRGINITY_SELECTION_SYMBOL_SET_MISMATCH")
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        raise ValueError("GEN2_VIRGINITY_SELECTION_SAFETY_INVALID")
    for key in (
        "historical_market_data_api_called",
        "quote_api_called",
        "market_snapshot_api_called",
        "rehab_api_called",
        "fundamental_api_called",
        "trading_api_called",
        "strategy_evaluation_executed",
        "candidate_parameters_changed",
        "phase6_authorized",
        "phase7_started",
        "production_readiness_approved",
    ):
        if safety.get(key) is not False:
            raise ValueError(f"GEN2_VIRGINITY_SELECTION_SAFETY_MISMATCH:{key}")
    return payload, sha256(raw).hexdigest(), contract_sha


def capture_composite_virginity(
    *,
    log_paths: tuple[Path, ...],
    evidence_output_path: Path,
    attestation_output_path: Path,
    selection_path: Path | None = None,
    selection_contract_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> tuple[Path, Path]:
    selection_path = selection_path or _default_selection()
    selection_contract_path = selection_contract_path or _default_contract()
    selection, selection_sha, selection_contract_sha = _verify_selection(
        Path(selection_path), Path(selection_contract_path)
    )

    evidence_output = Path(evidence_output_path)
    attestation_output = Path(attestation_output_path)
    for output in (evidence_output, attestation_output):
        if output.exists():
            raise FileExistsError(f"GEN2_COMPOSITE_VIRGINITY_OUTPUT_EXISTS:{output.name}")

    sdk, sdk_name = _load_sdk()
    context = sdk.OpenQuoteContext(host=host, port=port)
    try:
        used, remaining, details = _provider_quota(context, sdk)
    finally:
        context.close()

    locked_codes = {f"US.{symbol}" for symbol in LOCKED_SYMBOLS}
    provider_matches = tuple(
        item["code"] for item in details if item["code"] in locked_codes
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
            "schema_version": "GENERATION2-PROVIDER-QUOTA-DETAIL-v1",
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
            "schema_version": "GENERATION2-RETAINED-LOG-MANIFEST-v1",
            "files": file_manifest,
        }
    )
    history_context_bytes = canonical_json_bytes(
        {
            "schema_version": "GENERATION2-RETAINED-LOG-HISTORY-CONTEXT-v1",
            "history_protocol": "Qot_RequestHistoryKL",
            "history_protocol_id": 3103,
            "context_radius_lines": 8,
            "contexts": history_contexts,
        }
    )

    captured_at = datetime.now(timezone.utc)
    evidence = {
        "schema_version": EVIDENCE_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "candidate_id": FROZEN_CANDIDATE_ID,
        "binding_sha256": FROZEN_BINDING_SHA256,
        "implementation_sha256": FROZEN_IMPLEMENTATION_SHA256,
        "survivor_identity_report_sha256": FROZEN_IDENTITY_SHA256,
        "selection_sha256": selection_sha,
        "selection_contract_sha256": selection_contract_sha,
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
        "phase6_authorized": False,
        "phase7_started": False,
    }
    evidence_bytes = canonical_json_bytes(evidence)
    evidence_output.parent.mkdir(parents=True, exist_ok=True)
    evidence_output.write_bytes(evidence_bytes)

    if provider_matches or log_locked_matches:
        raise ValueError(
            "GEN2_COMPOSITE_VIRGINITY_FAILED:"
            f"provider={','.join(provider_matches) or 'NONE'}:"
            f"logs={','.join(log_locked_matches) or 'NONE'}"
        )

    evidence_sha = sha256(evidence_bytes).hexdigest()
    attestation = {
        "schema_version": ATTESTATION_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": ATTESTATION_STATUS,
        "candidate_id": FROZEN_CANDIDATE_ID,
        "binding_sha256": FROZEN_BINDING_SHA256,
        "implementation_sha256": FROZEN_IMPLEMENTATION_SHA256,
        "survivor_identity_report_sha256": FROZEN_IDENTITY_SHA256,
        "selection_sha256": selection_sha,
        "selection_contract_sha256": selection_contract_sha,
        "attestation_id": f"gen2-composite-{sha256(canonical_json_bytes({'selection': selection_sha, 'evidence': evidence_sha})).hexdigest()[:32]}",
        "locked_symbols": list(LOCKED_SYMBOLS),
        "evidence_kind": "COMPOSITE_PROVIDER_QUOTA_AND_RETAINED_LOGS",
        "evidence_bundle_sha256": evidence_sha,
        "captured_at_utc": captured_at.isoformat(),
        "provider_quota_protocol_id": PROVIDER_PROTOCOL_ID,
        "provider_quota_window_days": PROVIDER_WINDOW_DAYS,
        "provider_used_quota": used,
        "provider_remaining_quota": remaining,
        "provider_detail_sha256": sha256(provider_detail_bytes).hexdigest(),
        "provider_locked_symbol_matches": [],
        "retained_log_manifest_sha256": sha256(log_manifest_bytes).hexdigest(),
        "retained_log_history_context_sha256": sha256(history_context_bytes).hexdigest(),
        "retained_log_locked_symbol_history_matches": [],
        "complete_query_history": False,
        "independent_provider_component": True,
        "local_retained_log_component": True,
        "coordinator_self_report_only": False,
        "independent_source_provenance_gate": "OPEN",
        "historical_acquisition_authorized": False,
        "limitations": list(LIMITATIONS),
    }
    attestation_output.parent.mkdir(parents=True, exist_ok=True)
    attestation_output.write_bytes(canonical_json_bytes(attestation))
    return evidence_output, attestation_output


def verify_attestation(
    *,
    attestation_path: Path,
    evidence_path: Path,
    selection_path: Path | None = None,
    selection_contract_path: Path | None = None,
) -> dict[str, Any]:
    selection_path = selection_path or _default_selection()
    selection_contract_path = selection_contract_path or _default_contract()
    _, selection_sha, selection_contract_sha = _verify_selection(
        Path(selection_path), Path(selection_contract_path)
    )
    raw = Path(attestation_path).read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("schema_version") != ATTESTATION_SCHEMA:
        raise ValueError("GEN2_VIRGINITY_ATTESTATION_SCHEMA_MISMATCH")
    if payload.get("status") != ATTESTATION_STATUS:
        raise ValueError("GEN2_VIRGINITY_ATTESTATION_STATUS_MISMATCH")
    if payload.get("locked_symbols") != list(LOCKED_SYMBOLS):
        raise ValueError("GEN2_VIRGINITY_ATTESTATION_SYMBOL_SET_MISMATCH")
    if payload.get("selection_sha256") != selection_sha:
        raise ValueError("GEN2_VIRGINITY_ATTESTATION_SELECTION_MISMATCH")
    if payload.get("selection_contract_sha256") != selection_contract_sha:
        raise ValueError("GEN2_VIRGINITY_ATTESTATION_CONTRACT_MISMATCH")
    if payload.get("provider_locked_symbol_matches") != []:
        raise ValueError("GEN2_VIRGINITY_ATTESTATION_PROVIDER_MATCH")
    if payload.get("retained_log_locked_symbol_history_matches") != []:
        raise ValueError("GEN2_VIRGINITY_ATTESTATION_LOG_MATCH")
    if payload.get("independent_source_provenance_gate") != "OPEN":
        raise ValueError("GEN2_VIRGINITY_ATTESTATION_PROVENANCE_GATE_MISMATCH")
    if payload.get("historical_acquisition_authorized") is not False:
        raise ValueError("GEN2_VIRGINITY_ATTESTATION_AUTHORITY_MISMATCH")
    evidence_bytes = Path(evidence_path).read_bytes()
    if payload.get("evidence_bundle_sha256") != sha256(evidence_bytes).hexdigest():
        raise ValueError("GEN2_VIRGINITY_ATTESTATION_EVIDENCE_MISMATCH")
    return payload
