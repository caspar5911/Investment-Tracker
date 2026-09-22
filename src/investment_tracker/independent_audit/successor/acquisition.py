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

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import pandas as pd

from .acquisition_authority import load_acquisition_authorization
from .phase6_contract import verify_phase6_contract

SCHEMA = "SUCCESSOR-PHASE6-HOLDOUT-ACQUISITION-v1"
RECEIPT_SCHEMA = "SUCCESSOR-PHASE6-HOLDOUT-ACQUISITION-RECEIPT-v1"
MAGIC = b"SUCCESSOR-PHASE6-AESGCM-v1\n"
NONCE_BYTES = 12


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(Path(path).read_bytes())


def _load_sdk() -> tuple[Any, str]:
    errors: list[str] = []
    for name in ("moomoo", "futu"):
        try:
            return importlib.import_module(name), name
        except ImportError as exc:
            errors.append(str(exc))
    raise RuntimeError("SUCCESSOR_MOOMOO_OR_FUTU_PACKAGE_REQUIRED:" + "|".join(errors))


def _verify_sdk_capabilities(sdk: Any) -> None:
    context_type = getattr(sdk, "OpenQuoteContext", None)
    required = (
        "request_history_kline",
        "get_history_kl_quota",
        "get_rehab",
        "get_corporate_actions_dividends",
        "get_corporate_actions_stock_splits",
    )
    if context_type is None or any(not hasattr(context_type, name) for name in required):
        raise RuntimeError("SUCCESSOR_ACQUISITION_SDK_CAPABILITY_MISSING")
    if not hasattr(getattr(sdk, "AuType", object), "QFQ") or not hasattr(
        getattr(sdk, "AuType", object), "NONE"
    ):
        raise RuntimeError("SUCCESSOR_ACQUISITION_SDK_AUTYPE_MISSING")


def _provider_quota_preflight(
    context: Any, sdk: Any, locked_symbols: tuple[str, ...], required_capacity: int
) -> dict[str, Any]:
    ret, data = context.get_history_kl_quota(get_detail=True)
    if ret != sdk.RET_OK or not isinstance(data, tuple) or len(data) != 3:
        raise RuntimeError(f"SUCCESSOR_ACQUISITION_QUOTA_FAILED:{data}")
    used, remaining, details = data
    if not isinstance(remaining, int) or isinstance(remaining, bool) or remaining < required_capacity:
        raise RuntimeError(f"SUCCESSOR_ACQUISITION_QUOTA_INSUFFICIENT:{remaining}")
    if not isinstance(details, list):
        raise RuntimeError("SUCCESSOR_ACQUISITION_QUOTA_DETAIL_INVALID")
    locked_codes = {f"US.{symbol}" for symbol in locked_symbols}
    matches = sorted(
        {
            str(item.get("code", "")).strip().upper()[3:]
            for item in details
            if isinstance(item, dict)
            and str(item.get("code", "")).strip().upper() in locked_codes
        }
    )
    if matches:
        raise RuntimeError(
            "SUCCESSOR_ACQUISITION_VIRGINITY_RECHECK_FAILED:" + ",".join(matches)
        )
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
    count = int(holdout["required_pre_window_sessions"])
    calendar = xcals.get_calendar("XNYS")
    scored = _utc_sessions(calendar.sessions_in_range(start, end))
    prior = _utc_sessions(
        calendar.sessions_in_range(start - pd.Timedelta(days=900), start - pd.Timedelta(days=1))
    )
    if len(scored) < 2 or len(prior) < count:
        raise ValueError("SUCCESSOR_ACQUISITION_SESSION_AUTHORITY_INSUFFICIENT")
    return prior[-count:], scored


def _page_bars(
    context: Any,
    sdk: Any,
    *,
    code: str,
    start: str,
    end: str,
    autype: Any,
) -> pd.DataFrame:
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
            raise RuntimeError(f"SUCCESSOR_HISTORY_FAILED:{code}:{data}")
        if not isinstance(data, pd.DataFrame):
            raise RuntimeError(f"SUCCESSOR_HISTORY_INVALID:{code}")
        pages.append(data.copy(deep=True))
        if page_key is None:
            break
    if not pages:
        raise RuntimeError(f"SUCCESSOR_HISTORY_EMPTY:{code}")
    return pd.concat(pages, ignore_index=True)


def _validated_bars(
    frame: pd.DataFrame, *, identity: str, required_sessions: pd.DatetimeIndex
) -> pd.DataFrame:
    required = {"time_key", "open", "high", "low", "close"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError(f"SUCCESSOR_BAR_SCHEMA_MISMATCH:{identity}")
    sessions = pd.to_datetime(
        frame["time_key"].astype(str).str.slice(0, 10), errors="raise", utc=True
    ).dt.normalize()
    if sessions.duplicated().any():
        raise ValueError(f"SUCCESSOR_DUPLICATE_SESSION:{identity}")
    values = pd.DataFrame(index=pd.DatetimeIndex(sessions))
    for name in ("open", "high", "low", "close"):
        values[name] = pd.to_numeric(frame[name], errors="raise").to_numpy(dtype=float)
    matrix = values[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if (
        not values.index.is_monotonic_increasing
        or not all(math.isfinite(float(value)) and float(value) > 0 for value in matrix.flat)
        or (values["low"] > values[["open", "close"]].min(axis=1)).any()
        or (values["high"] < values[["open", "close"]].max(axis=1)).any()
        or (values["low"] > values["high"]).any()
    ):
        raise ValueError(f"SUCCESSOR_BAR_VALUES_INVALID:{identity}")
    missing = required_sessions.difference(values.index)
    if len(missing):
        raise ValueError(
            f"SUCCESSOR_REQUIRED_SESSION_MISSING:{identity}:{missing[0].date().isoformat()}"
        )
    return values.loc[required_sessions].copy()


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    rendered = frame.rename_axis("session").reset_index()
    rendered["session"] = rendered["session"].dt.strftime("%Y-%m-%d")
    return rendered.to_csv(
        index=False, lineterminator="\n", float_format="%.17g"
    ).encode("utf-8")


def _rehab_bytes(context: Any, sdk: Any, code: str) -> bytes:
    ret, data = context.get_rehab(code)
    if ret != sdk.RET_OK or not isinstance(data, pd.DataFrame):
        raise RuntimeError(f"SUCCESSOR_REHAB_FAILED:{code}:{data}")
    out = data.copy(deep=True)
    if "ex_div_date" in out.columns:
        out = out.sort_values(["ex_div_date"], kind="stable")
    return out.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")


def _dividend_bytes(context: Any, sdk: Any, code: str) -> bytes:
    ret, data = context.get_corporate_actions_dividends(code)
    if ret != sdk.RET_OK or not isinstance(data, dict):
        raise RuntimeError(f"SUCCESSOR_DIVIDENDS_FAILED:{code}:{data}")
    values = data.get("dividend_list", [])
    if not isinstance(values, list):
        raise RuntimeError(f"SUCCESSOR_DIVIDENDS_INVALID:{code}")
    return _canonical_bytes({"dividend_list": values})


def _split_bytes(context: Any, sdk: Any, code: str) -> bytes:
    items: list[dict[str, Any]] = []
    next_key: str | None = None
    while True:
        ret, data = context.get_corporate_actions_stock_splits(
            code, next_key=next_key, num=50
        )
        if ret != sdk.RET_OK or not isinstance(data, dict):
            raise RuntimeError(f"SUCCESSOR_SPLITS_FAILED:{code}:{data}")
        page = data.get("split_list", [])
        if not isinstance(page, list):
            raise RuntimeError(f"SUCCESSOR_SPLITS_INVALID:{code}")
        items.extend(page)
        next_key = str(data.get("next_key", "-1"))
        if next_key == "-1":
            break
    return _canonical_bytes({"split_list": items})


def _safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or name.startswith("/")
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("SUCCESSOR_BUNDLE_PATH_INVALID")
    return name


def _build_bundle(
    manifest: dict[str, Any], entries: dict[str, bytes]
) -> tuple[bytes, dict[str, Any]]:
    ordered = {name: entries[name] for name in sorted(entries)}
    full = {
        **manifest,
        "files": [
            {"path": name, "sha256": _sha_bytes(payload), "bytes": len(payload)}
            for name, payload in ordered.items()
        ],
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in [
            ("manifest.json", _canonical_bytes(full)),
            *ordered.items(),
        ]:
            info = zipfile.ZipInfo(_safe_name(name), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o600 << 16
            archive.writestr(info, payload)
    return buffer.getvalue(), full


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RuntimeError("SUCCESSOR_ACQUISITION_AUTHORIZATION_ALREADY_CONSUMED") from exc
    if path.read_bytes() != payload:
        raise OSError("SUCCESSOR_ACQUISITION_MARKER_READBACK_FAILED")


def _replace_verified(path: Path, payload: bytes) -> None:
    partial = path.with_name(path.name + ".partial")
    with partial.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)
    if path.read_bytes() != payload:
        raise OSError("SUCCESSOR_ACQUISITION_MARKER_READBACK_FAILED")


def preflight_acquisition(
    *,
    authorization_path: Path,
    phase6_contract_path: Path,
    selection_path: Path,
    virginity_attestation_path: Path,
    virginity_evidence_path: Path,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> dict[str, Any]:
    auth = load_acquisition_authorization(
        authorization_path=authorization_path,
        phase6_contract_path=phase6_contract_path,
        selection_path=selection_path,
        virginity_attestation_path=virginity_attestation_path,
        virginity_evidence_path=virginity_evidence_path,
    )
    sdk, sdk_name = _load_sdk()
    _verify_sdk_capabilities(sdk)
    context = sdk.OpenQuoteContext(host=host, port=port)
    try:
        quota = _provider_quota_preflight(
            context, sdk, auth.locked_symbols, len(auth.locked_symbols) + 1
        )
    finally:
        context.close()
    return {
        "schema_version": "SUCCESSOR-PHASE6-ACQUISITION-PREFLIGHT-v1",
        "status": "SUCCESSOR_ACQUISITION_PREFLIGHT_READY",
        "authorization_id": auth.authorization_id,
        "successor_formal_name": auth.successor_formal_name,
        "sdk_module": sdk_name,
        "sdk_version": str(getattr(sdk, "__version__", "UNKNOWN")),
        "provider_used_quota": quota["used"],
        "provider_remaining_quota": quota["remaining"],
        "locked_symbol_matches": quota["locked_matches"],
        "historical_market_data_api_called": False,
        "historical_access_consumed": False,
        "phase7_authorized": False,
    }


def acquire_and_seal(
    *,
    repository_root: Path,
    authorization_path: Path,
    phase6_contract_path: Path,
    selection_path: Path,
    virginity_attestation_path: Path,
    virginity_evidence_path: Path,
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
        raise ValueError("SUCCESSOR_PRIVATE_OUTPUT_MUST_BE_OUTSIDE_REPOSITORY")

    auth = load_acquisition_authorization(
        authorization_path=authorization_path,
        phase6_contract_path=phase6_contract_path,
        selection_path=selection_path,
        virginity_attestation_path=virginity_attestation_path,
        virginity_evidence_path=virginity_evidence_path,
    )
    contract = verify_phase6_contract(phase6_contract_path)

    sdk, sdk_name = _load_sdk()
    _verify_sdk_capabilities(sdk)
    preflight_context = sdk.OpenQuoteContext(host=host, port=port)
    try:
        quota = _provider_quota_preflight(
            preflight_context, sdk, auth.locked_symbols, len(auth.locked_symbols) + 1
        )
    finally:
        preflight_context.close()

    output.mkdir(parents=True, exist_ok=True)
    marker_path = output / f"{auth.authorization_id}.acquisition-start.json"
    marker = {
        "schema_version": SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": "FINAL_HOLDOUT_ACQUISITION_STARTED",
        "authorization_id": auth.authorization_id,
        "authorization_sha256": _sha_file(authorization_path),
        "phase6_contract_sha256": _sha_file(phase6_contract_path),
        "locked_symbols": list(auth.locked_symbols),
        "historical_access_started": False,
        "retry_allowed_after_historical_access": False,
        "provider_quota_preflight": quota,
    }
    _write_exclusive(marker_path, _canonical_bytes(marker))

    warmup, scored = expected_sessions(contract)
    required_sessions = warmup.append(scored)
    request_start = warmup[0].date().isoformat()
    request_end = contract["final_holdout"]["calendar_end"]
    benchmark = contract["final_holdout"]["benchmark_reference_symbol"]
    data_symbols = (*auth.locked_symbols, benchmark)

    marker["historical_access_started"] = True
    marker["historical_access_started_at_utc"] = datetime.now(timezone.utc).isoformat()
    _replace_verified(marker_path, _canonical_bytes(marker))

    context = sdk.OpenQuoteContext(host=host, port=port)
    entries: dict[str, bytes] = {}
    try:
        for symbol in data_symbols:
            code = f"US.{symbol}"
            qfq = _page_bars(
                context, sdk, code=code, start=request_start, end=request_end, autype=sdk.AuType.QFQ
            )
            raw = _page_bars(
                context, sdk, code=code, start=request_start, end=request_end, autype=sdk.AuType.NONE
            )
            entries[f"bars/qfq/{symbol}.csv"] = _csv_bytes(
                _validated_bars(qfq, identity=f"{symbol}:QFQ", required_sessions=required_sessions)
            )
            entries[f"bars/unadjusted/{symbol}.csv"] = _csv_bytes(
                _validated_bars(raw, identity=f"{symbol}:NONE", required_sessions=required_sessions)
            )
            entries[f"corporate_actions/rehab/{symbol}.csv"] = _rehab_bytes(context, sdk, code)
            entries[f"corporate_actions/dividends/{symbol}.json"] = _dividend_bytes(context, sdk, code)
            entries[f"corporate_actions/splits/{symbol}.json"] = _split_bytes(context, sdk, code)
    finally:
        context.close()

    retrieved_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "provider": "MOOMOO_OPEND",
        "sdk_module": sdk_name,
        "sdk_version": str(getattr(sdk, "__version__", "UNKNOWN")),
        "successor_formal_name": auth.successor_formal_name,
        "phase6_contract_sha256": _sha_file(phase6_contract_path),
        "acquisition_authorization_sha256": _sha_file(authorization_path),
        "candidate_id": auth.candidate_id,
        "binding_sha256": auth.binding_sha256,
        "implementation_sha256": auth.implementation_sha256,
        "successor_normalizer_sha256": auth.successor_normalizer_sha256,
        "locked_symbols": list(auth.locked_symbols),
        "benchmark_reference_symbol": benchmark,
        "requested_start": request_start,
        "requested_end": request_end,
        "holdout_start": contract["final_holdout"]["calendar_start"],
        "holdout_end": contract["final_holdout"]["calendar_end"],
        "warmup_session_count": len(warmup),
        "scored_session_count": len(scored),
        "retrieved_at_utc": retrieved_at,
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(auth.locked_symbols),
        "performance_computed": False,
        "performance_inspected": False,
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "phase7_started": False,
        "live_trading_capability": False,
    }
    plaintext, full_manifest = _build_bundle(manifest, entries)
    contract_sha = _sha_file(phase6_contract_path)
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(
        nonce, plaintext, contract_sha.encode("ascii")
    )
    encrypted = MAGIC + nonce + ciphertext
    plaintext_sha = _sha_bytes(plaintext)
    bundle_sha = _sha_bytes(encrypted)
    holdout_id = f"successor-phase6-holdout-{plaintext_sha[:32]}"

    bundle_path = output / f"{holdout_id}.bundle.aesgcm"
    key_path = output / f"{holdout_id}.key"
    receipt_path = output / f"{holdout_id}.receipt.json"
    for path in (bundle_path, key_path, receipt_path):
        if path.exists():
            raise FileExistsError(f"SUCCESSOR_IMMUTABLE_OUTPUT_EXISTS:{path.name}")

    bundle_path.write_bytes(encrypted)
    key_path.write_text(key.hex(), encoding="ascii")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass

    if _sha_file(bundle_path) != bundle_sha or sha256(bytes.fromhex(key_path.read_text())).hexdigest() != sha256(key).hexdigest():
        raise OSError("SUCCESSOR_ACQUISITION_ARTIFACT_READBACK_FAILED")

    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED",
        "successor_formal_name": auth.successor_formal_name,
        "holdout_id": holdout_id,
        "phase6_contract_sha256": contract_sha,
        "acquisition_authorization_sha256": _sha_file(authorization_path),
        "candidate_id": auth.candidate_id,
        "binding_sha256": auth.binding_sha256,
        "implementation_sha256": auth.implementation_sha256,
        "successor_normalizer_sha256": auth.successor_normalizer_sha256,
        "bundle_sha256": bundle_sha,
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
        "retrieved_at_utc": retrieved_at,
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(auth.locked_symbols),
        "performance_computed": False,
        "performance_inspected": False,
        "retry_allowed": False,
        "artifact_readback_verified": True,
    }
    receipt_bytes = _canonical_bytes(receipt)
    receipt_path.write_bytes(receipt_bytes)
    if receipt_path.read_bytes() != receipt_bytes:
        raise OSError("SUCCESSOR_ACQUISITION_RECEIPT_READBACK_FAILED")
    return receipt_path
