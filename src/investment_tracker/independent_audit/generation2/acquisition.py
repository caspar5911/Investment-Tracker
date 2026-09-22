from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import importlib
import json
import math
import os
from pathlib import Path, PurePosixPath
from typing import Any
import zipfile

import pandas as pd
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .authorization import load_authorization
from .phase6_contract import verify_contract
from .virginity import LOCKED_SYMBOLS

SCHEMA = "GENERATION2-PHASE6-HOLDOUT-ACQUISITION-v1"
RECEIPT_SCHEMA = "GENERATION2-PHASE6-HOLDOUT-ACQUISITION-RECEIPT-v1"
BENCHMARK = "SPY"
DATA_SYMBOLS = (*LOCKED_SYMBOLS, BENCHMARK)
KEY_BYTES = 32
NONCE_BYTES = 12
MAGIC = b"GEN2-PHASE6-AESGCM-v1\n"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False).encode("utf-8")


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(Path(path).read_bytes())


def _safe_name(name: str) -> str:
    p = PurePosixPath(name)
    if not name or "\\" in name or name.startswith("/") or any(x in {"", ".", ".."} for x in p.parts):
        raise ValueError("GEN2_ACQUISITION_BUNDLE_PATH_INVALID")
    return name


def _write_member(z: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(_safe_name(name), date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o600 << 16
    z.writestr(info, payload)


def _build_plain_bundle(manifest: dict[str, Any], entries: dict[str, bytes]) -> tuple[bytes, dict[str, Any]]:
    ordered = {name: entries[name] for name in sorted(entries)}
    files = [{"path": name, "sha256": _sha_bytes(payload), "bytes": len(payload)} for name, payload in ordered.items()]
    full = {**manifest, "files": files}
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        _write_member(z, "manifest.json", _canonical_bytes(full))
        for name, payload in ordered.items():
            _write_member(z, name, payload)
    return buf.getvalue(), full


def _encrypt(plaintext: bytes, contract_sha256: str) -> tuple[bytes, bytes]:
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(NONCE_BYTES)
    encrypted = AESGCM(key).encrypt(nonce, plaintext, contract_sha256.encode("ascii"))
    return MAGIC + nonce + encrypted, key


def _load_sdk() -> tuple[Any, str]:
    errors: list[str] = []
    for name in ("moomoo", "futu"):
        try:
            return importlib.import_module(name), name
        except ImportError as exc:
            errors.append(str(exc))
    raise RuntimeError("GEN2_MOOMOO_OR_FUTU_PACKAGE_REQUIRED:" + "|".join(errors))


def _verify_sdk_capabilities(sdk: Any) -> None:
    context_type = getattr(sdk, "OpenQuoteContext", None)
    required_methods = (
        "request_history_kline",
        "get_history_kl_quota",
        "get_rehab",
        "get_corporate_actions_dividends",
        "get_corporate_actions_stock_splits",
    )
    if context_type is None or any(not hasattr(context_type, name) for name in required_methods):
        raise RuntimeError("GEN2_ACQUISITION_SDK_CAPABILITY_MISSING")
    if not hasattr(getattr(sdk, "AuType", object), "QFQ") or not hasattr(getattr(sdk, "AuType", object), "NONE"):
        raise RuntimeError("GEN2_ACQUISITION_SDK_AUTYPE_MISSING")
    if not hasattr(getattr(sdk, "KLType", object), "K_DAY"):
        raise RuntimeError("GEN2_ACQUISITION_SDK_KLTYPE_MISSING")


def _provider_quota_preflight(context: Any, sdk: Any) -> dict[str, Any]:
    ret, data = context.get_history_kl_quota(get_detail=True)
    if ret != sdk.RET_OK or not isinstance(data, tuple) or len(data) != 3:
        raise RuntimeError(f"GEN2_ACQUISITION_QUOTA_FAILED:{data}")
    used, remaining, details = data
    if isinstance(remaining, bool) or not isinstance(remaining, int) or remaining < len(DATA_SYMBOLS):
        raise RuntimeError(f"GEN2_ACQUISITION_QUOTA_INSUFFICIENT:{remaining}")
    if not isinstance(details, list):
        raise RuntimeError("GEN2_ACQUISITION_QUOTA_DETAIL_INVALID")
    locked_codes = {f"US.{symbol}" for symbol in LOCKED_SYMBOLS}
    matches = sorted({
        str(item.get("code", "")).strip().upper()
        for item in details
        if isinstance(item, dict) and str(item.get("code", "")).strip().upper() in locked_codes
    })
    if matches:
        raise RuntimeError("GEN2_ACQUISITION_VIRGINITY_RECHECK_FAILED:" + ",".join(matches))
    return {"used": int(used), "remaining": remaining, "locked_matches": matches}


def _utc_sessions(index: object) -> pd.DatetimeIndex:
    values = pd.DatetimeIndex(index)
    if values.tz is None:
        values = values.tz_localize("UTC")
    else:
        values = values.tz_convert("UTC")
    return values.normalize()


def expected_sessions(contract: dict[str, Any]) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    import exchange_calendars as xcals

    holdout = contract["final_holdout"]
    start = pd.Timestamp(holdout["calendar_start"])
    end = pd.Timestamp(holdout["calendar_end"])
    warmup_count = int(holdout["required_pre_window_sessions"])
    calendar = xcals.get_calendar("XNYS")
    scored = _utc_sessions(calendar.sessions_in_range(start, end))
    prior = _utc_sessions(calendar.sessions_in_range(start - pd.Timedelta(days=900), start - pd.Timedelta(days=1)))
    if len(scored) < 2 or len(prior) < warmup_count:
        raise ValueError("GEN2_ACQUISITION_SESSION_AUTHORITY_INSUFFICIENT")
    return prior[-warmup_count:], scored


def _page_bars(context: Any, sdk: Any, *, code: str, start: str, end: str, autype: Any) -> pd.DataFrame:
    pages: list[pd.DataFrame] = []
    page_key = None
    while True:
        ret, data, page_key = context.request_history_kline(
            code,
            start=start,
            end=end,
            ktype=sdk.KLType.K_DAY,
            autype=autype,
            max_count=1000,
            page_req_key=page_key,
            extended_time=False,
        )
        if ret != sdk.RET_OK:
            raise RuntimeError(f"GEN2_HISTORY_FAILED:{code}:{data}")
        if not isinstance(data, pd.DataFrame):
            raise RuntimeError(f"GEN2_HISTORY_INVALID:{code}")
        pages.append(data.copy(deep=True))
        if page_key is None:
            break
    if not pages:
        raise RuntimeError(f"GEN2_HISTORY_EMPTY:{code}")
    return pd.concat(pages, ignore_index=True)


def _validated_bars(frame: pd.DataFrame, *, symbol: str, required_sessions: pd.DatetimeIndex) -> pd.DataFrame:
    required = {"time_key", "open", "high", "low", "close"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError(f"GEN2_BAR_SCHEMA_MISMATCH:{symbol}")
    sessions = pd.to_datetime(frame["time_key"].astype(str).str.slice(0, 10), errors="raise", utc=True).dt.normalize()
    if sessions.duplicated().any():
        raise ValueError(f"GEN2_DUPLICATE_SESSION:{symbol}")
    values = pd.DataFrame(index=pd.DatetimeIndex(sessions))
    for name in ("open", "high", "low", "close"):
        values[name] = pd.to_numeric(frame[name], errors="raise").to_numpy(dtype=float)
    matrix = values[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if (
        not values.index.is_monotonic_increasing
        or not all(math.isfinite(float(v)) and float(v) > 0.0 for v in matrix.flat)
        or (values["low"] > values[["open", "close"]].min(axis=1)).any()
        or (values["high"] < values[["open", "close"]].max(axis=1)).any()
        or (values["low"] > values["high"]).any()
    ):
        raise ValueError(f"GEN2_BAR_VALUES_INVALID:{symbol}")
    missing = required_sessions.difference(values.index)
    if len(missing):
        raise ValueError(f"GEN2_REQUIRED_SESSION_MISSING:{symbol}:{missing[0].date().isoformat()}")
    return values.loc[required_sessions].copy()


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    rendered = frame.rename_axis("session").reset_index()
    rendered["session"] = rendered["session"].dt.strftime("%Y-%m-%d")
    return rendered.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")


def _rehab_bytes(context: Any, sdk: Any, code: str) -> bytes:
    ret, data = context.get_rehab(code)
    if ret != sdk.RET_OK or not isinstance(data, pd.DataFrame):
        raise RuntimeError(f"GEN2_REHAB_FAILED:{code}:{data}")
    out = data.copy(deep=True)
    if "ex_div_date" in out.columns:
        out = out.sort_values(["ex_div_date"], kind="stable")
    return out.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")


def _dividend_bytes(context: Any, sdk: Any, code: str) -> bytes:
    ret, data = context.get_corporate_actions_dividends(code)
    if ret != sdk.RET_OK or not isinstance(data, dict):
        raise RuntimeError(f"GEN2_DIVIDENDS_FAILED:{code}:{data}")
    values = data.get("dividend_list", [])
    if not isinstance(values, list):
        raise RuntimeError(f"GEN2_DIVIDENDS_INVALID:{code}")
    return _canonical_bytes({"dividend_list": values})


def _split_bytes(context: Any, sdk: Any, code: str) -> bytes:
    items: list[dict[str, Any]] = []
    next_key: str | None = None
    while True:
        ret, data = context.get_corporate_actions_stock_splits(code, next_key=next_key, num=50)
        if ret != sdk.RET_OK or not isinstance(data, dict):
            raise RuntimeError(f"GEN2_SPLITS_FAILED:{code}:{data}")
        page = data.get("split_list", [])
        if not isinstance(page, list):
            raise RuntimeError(f"GEN2_SPLITS_INVALID:{code}")
        items.extend(page)
        next_key = str(data.get("next_key", "-1"))
        if next_key == "-1":
            break
    return _canonical_bytes({"split_list": items})


def _write_marker(path: Path, payload: dict[str, Any], *, exclusive: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _canonical_bytes(payload)
    if exclusive:
        try:
            with path.open("xb") as h:
                h.write(data)
                h.flush()
                os.fsync(h.fileno())
        except FileExistsError as exc:
            raise RuntimeError("GEN2_ACQUISITION_AUTHORIZATION_ALREADY_CONSUMED") from exc
    else:
        tmp = path.with_name(path.name + ".partial")
        with tmp.open("wb") as h:
            h.write(data)
            h.flush()
            os.fsync(h.fileno())
        os.replace(tmp, path)


def _verify_ci_classification(path: Path, authorization_commit_sha: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        value.get("schema_version") != "GENERATION2-PHASE6-CI-CLASSIFICATION-v1"
        or value.get("status") != "LEGACY_FULL_SUITE_ENVIRONMENT_FAILURE_CLASSIFIED"
        or value.get("authorization_commit_sha") != authorization_commit_sha
        or value.get("full_suite", {}).get("full_suite_green") is not False
        or value.get("assessment", {}).get("generic_suite_failure_waived_as_green") is not False
        or value.get("assessment", {}).get("generation2_regression_detected") is not False
    ):
        raise ValueError("GEN2_ACQUISITION_CI_CLASSIFICATION_INVALID")
    required = ("generation2-holdout-selection-audit", "phase6-independent-audit", "phase6-preseal-static")
    for name in required:
        if value.get("dedicated_generation2_gates", {}).get(name, {}).get("conclusion") != "success":
            raise ValueError(f"GEN2_ACQUISITION_DEDICATED_GATE_NOT_GREEN:{name}")
    return value


def preflight_acquisition(
    *,
    repository_root: Path,
    contract_path: Path,
    authorization_path: Path,
    preaccess_status_path: Path,
    attestation_path: Path,
    evidence_path: Path,
    provenance_root: Path,
    ci_classification_path: Path,
    authorization_commit_sha: str,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> dict[str, Any]:
    repository = Path(repository_root).resolve()
    verify_contract(contract_path)
    authorization = load_authorization(
        authorization_path=authorization_path,
        repository_root=repository,
        contract_path=contract_path,
        preaccess_status_path=preaccess_status_path,
        attestation_path=attestation_path,
        evidence_path=evidence_path,
        provenance_root=provenance_root,
    )
    if authorization_commit_sha != "51f077cc5acddd02a231567088f70a3c7bdb7d36":
        raise ValueError("GEN2_AUTHORIZATION_COMMIT_IDENTITY_MISMATCH")
    _verify_ci_classification(ci_classification_path, authorization_commit_sha)

    sdk, sdk_name = _load_sdk()
    _verify_sdk_capabilities(sdk)
    context = sdk.OpenQuoteContext(host=host, port=port)
    try:
        quota = _provider_quota_preflight(context, sdk)
    finally:
        context.close()
    return {
        "schema_version": "GENERATION2-PHASE6-ACQUISITION-PREFLIGHT-v1",
        "status": "GEN2_ACQUISITION_PREFLIGHT_READY",
        "authorization_id": authorization.authorization_id,
        "authorization_commit_sha": authorization_commit_sha,
        "sdk_module": sdk_name,
        "sdk_version": str(getattr(sdk, "__version__", "UNKNOWN")),
        "provider_used_quota": quota["used"],
        "provider_remaining_quota": quota["remaining"],
        "locked_symbol_matches": quota["locked_matches"],
        "historical_market_data_api_called": False,
        "historical_access_consumed": False,
    }


def acquire_and_seal(
    *,
    repository_root: Path,
    contract_path: Path,
    authorization_path: Path,
    preaccess_status_path: Path,
    attestation_path: Path,
    evidence_path: Path,
    provenance_root: Path,
    ci_classification_path: Path,
    authorization_commit_sha: str,
    private_output_dir: Path,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> Path:
    repository = Path(repository_root).resolve()
    output = Path(private_output_dir).resolve()
    try:
        output.relative_to(repository)
    except ValueError:
        pass
    else:
        raise ValueError("GEN2_PRIVATE_OUTPUT_MUST_BE_OUTSIDE_REPOSITORY")

    contract = verify_contract(contract_path)
    authorization = load_authorization(
        authorization_path=authorization_path,
        repository_root=repository,
        contract_path=contract_path,
        preaccess_status_path=preaccess_status_path,
        attestation_path=attestation_path,
        evidence_path=evidence_path,
        provenance_root=provenance_root,
    )
    if authorization_commit_sha != "51f077cc5acddd02a231567088f70a3c7bdb7d36":
        raise ValueError("GEN2_AUTHORIZATION_COMMIT_IDENTITY_MISMATCH")
    _verify_ci_classification(ci_classification_path, authorization_commit_sha)

    sdk, sdk_name = _load_sdk()
    _verify_sdk_capabilities(sdk)
    preflight_context = sdk.OpenQuoteContext(host=host, port=port)
    try:
        quota_preflight = _provider_quota_preflight(preflight_context, sdk)
    finally:
        preflight_context.close()

    output.mkdir(parents=True, exist_ok=True)
    auth_sha = _sha_file(authorization_path)
    marker = output / f"{authorization.authorization_id}.acquisition-start.json"
    marker_payload = {
        "schema_version": SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": "FINAL_HOLDOUT_ACQUISITION_STARTED",
        "authorization_id": authorization.authorization_id,
        "authorization_sha256": auth_sha,
        "evaluation_contract_sha256": contract["contract_sha256"],
        "locked_symbols": list(LOCKED_SYMBOLS),
        "benchmark_reference_symbol": BENCHMARK,
        "historical_access_started": False,
        "retry_allowed_after_historical_access": False,
        "provider_quota_preflight": quota_preflight,
        "sdk_module": sdk_name,
        "sdk_version": str(getattr(sdk, "__version__", "UNKNOWN")),
    }
    _write_marker(marker, marker_payload, exclusive=True)

    warmup, scored = expected_sessions(contract)
    required_sessions = warmup.append(scored)
    request_start = warmup[0].date().isoformat()
    request_end = contract["final_holdout"]["calendar_end"]

    context = sdk.OpenQuoteContext(host=host, port=port)
    entries: dict[str, bytes] = {}
    try:
        marker_payload["historical_access_started"] = True
        marker_payload["historical_access_started_at_utc"] = datetime.now(timezone.utc).isoformat()
        _write_marker(marker, marker_payload, exclusive=False)

        for symbol in DATA_SYMBOLS:
            code = f"US.{symbol}"
            qfq = _page_bars(context, sdk, code=code, start=request_start, end=request_end, autype=sdk.AuType.QFQ)
            raw = _page_bars(context, sdk, code=code, start=request_start, end=request_end, autype=sdk.AuType.NONE)
            entries[f"bars/qfq/{symbol}.csv"] = _csv_bytes(_validated_bars(qfq, symbol=f"{symbol}:QFQ", required_sessions=required_sessions))
            entries[f"bars/unadjusted/{symbol}.csv"] = _csv_bytes(_validated_bars(raw, symbol=f"{symbol}:NONE", required_sessions=required_sessions))
            entries[f"corporate_actions/rehab/{symbol}.csv"] = _rehab_bytes(context, sdk, code)
            entries[f"corporate_actions/dividends/{symbol}.json"] = _dividend_bytes(context, sdk, code)
            entries[f"corporate_actions/splits/{symbol}.json"] = _split_bytes(context, sdk, code)
    finally:
        context.close()

    retrieved = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "provider": "MOOMOO_OPEND",
        "sdk_module": sdk_name,
        "sdk_version": str(getattr(sdk, "__version__", "UNKNOWN")),
        "evaluation_contract_sha256": contract["contract_sha256"],
        "evaluation_contract_file_sha256": _sha_file(contract_path),
        "acquisition_authorization_sha256": auth_sha,
        "authorization_commit_sha": authorization_commit_sha,
        "ci_classification_sha256": _sha_file(ci_classification_path),
        "locked_symbols": list(LOCKED_SYMBOLS),
        "benchmark_reference_symbol": BENCHMARK,
        "signal_price_convention": "MOOMOO_QFQ_DAILY_RTH",
        "execution_price_convention": "MOOMOO_UNADJUSTED_DAILY_RTH",
        "corporate_action_sources": ["MOOMOO_REHAB", "MOOMOO_CORPORATE_ACTION_DIVIDENDS", "MOOMOO_CORPORATE_ACTION_STOCK_SPLITS"],
        "requested_start": request_start,
        "requested_end": request_end,
        "holdout_start": contract["final_holdout"]["calendar_start"],
        "holdout_end": contract["final_holdout"]["calendar_end"],
        "warmup_session_count": len(warmup),
        "scored_session_count": len(scored),
        "warmup_first_session": warmup[0].date().isoformat(),
        "warmup_last_session": warmup[-1].date().isoformat(),
        "scored_first_session": scored[0].date().isoformat(),
        "scored_last_session": scored[-1].date().isoformat(),
        "retrieved_at_utc": retrieved,
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(LOCKED_SYMBOLS),
        "performance_computed": False,
        "performance_inspected": False,
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "phase7_started": False,
        "live_trading_capability": False,
    }
    plaintext, full_manifest = _build_plain_bundle(manifest, entries)
    plaintext_sha = _sha_bytes(plaintext)
    encrypted, key = _encrypt(plaintext, contract["contract_sha256"])
    encrypted_sha = _sha_bytes(encrypted)
    holdout_id = f"gen2-phase6-holdout-{plaintext_sha[:32]}"

    bundle_path = output / f"{holdout_id}.bundle.aesgcm"
    key_path = output / f"{holdout_id}.key"
    receipt_path = output / f"{holdout_id}.receipt.json"
    for p in (bundle_path, key_path, receipt_path):
        if p.exists():
            raise FileExistsError(f"GEN2_ACQUISITION_IMMUTABLE_OUTPUT_EXISTS:{p.name}")
    bundle_path.write_bytes(encrypted)
    key_path.write_text(key.hex(), encoding="ascii")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass

    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED",
        "holdout_id": holdout_id,
        "evaluation_contract_sha256": contract["contract_sha256"],
        "acquisition_authorization_sha256": auth_sha,
        "authorization_commit_sha": authorization_commit_sha,
        "candidate_id": authorization.candidate_id,
        "binding_sha256": authorization.binding_sha256,
        "implementation_sha256": authorization.implementation_sha256,
        "bundle_sha256": encrypted_sha,
        "plaintext_bundle_sha256": plaintext_sha,
        "bundle_manifest_sha256": _sha_bytes(_canonical_bytes(full_manifest)),
        "key_sha256": sha256(key).hexdigest(),
        "bundle_bytes": len(encrypted),
        "provider": "MOOMOO_OPEND",
        "requested_start": request_start,
        "requested_end": request_end,
        "holdout_start": contract["final_holdout"]["calendar_start"],
        "holdout_end": contract["final_holdout"]["calendar_end"],
        "warmup_session_count": len(warmup),
        "scored_session_count": len(scored),
        "retrieved_at_utc": retrieved,
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(LOCKED_SYMBOLS),
        "performance_computed": False,
        "performance_inspected": False,
        "retry_allowed": False,
    }
    receipt_path.write_bytes(_canonical_bytes(receipt))
    return receipt_path
