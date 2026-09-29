from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from .authority import (
    BENCHMARK_SYMBOL,
    CONTRACT_SHA256,
    HOLDOUT_END,
    HOLDOUT_START,
    LOCKED_SYMBOLS,
    WARMUP_SESSIONS,
    load_acquisition_authorization,
    load_frozen_contract,
    sha256_bytes,
)
from .bundle import build_plain_bundle, encrypt_bundle

DATA_SYMBOLS = (*LOCKED_SYMBOLS, BENCHMARK_SYMBOL)


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


def _utc_sessions(index: object) -> pd.DatetimeIndex:
    values = pd.DatetimeIndex(index)
    if values.tz is None:
        values = values.tz_localize("UTC")
    else:
        values = values.tz_convert("UTC")
    return values.normalize()


def expected_sessions() -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    import exchange_calendars as xcals

    calendar = xcals.get_calendar("XNYS")
    scored = _utc_sessions(
        calendar.sessions_in_range(
            pd.Timestamp(HOLDOUT_START),
            pd.Timestamp(HOLDOUT_END),
        )
    )
    search_start = pd.Timestamp(HOLDOUT_START) - pd.Timedelta(days=730)
    prior = _utc_sessions(
        calendar.sessions_in_range(
            search_start,
            pd.Timestamp(HOLDOUT_START) - pd.Timedelta(days=1),
        )
    )
    if len(prior) < WARMUP_SESSIONS or len(scored) < 2:
        raise ValueError("PHASE6_AUDIT_EXPECTED_SESSION_AUTHORITY_INSUFFICIENT")
    return prior[-WARMUP_SESSIONS:], scored


def _page_qfq(
    context: Any,
    sdk: Any,
    *,
    code: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    pages: list[pd.DataFrame] = []
    page_key = None
    while True:
        ret, data, page_key = context.request_history_kline(
            code,
            start=start,
            end=end,
            ktype=sdk.KLType.K_DAY,
            autype=sdk.AuType.QFQ,
            max_count=1000,
            page_req_key=page_key,
            extended_time=False,
        )
        if ret != sdk.RET_OK:
            raise RuntimeError(f"PHASE6_OPEND_HISTORY_FAILED:{code}:{data}")
        if not isinstance(data, pd.DataFrame):
            raise RuntimeError(f"PHASE6_OPEND_HISTORY_INVALID:{code}")
        pages.append(data.copy(deep=True))
        if page_key is None:
            break
    if not pages:
        raise RuntimeError(f"PHASE6_OPEND_HISTORY_EMPTY:{code}")
    return pd.concat(pages, ignore_index=True)


def _validated_frame(
    frame: pd.DataFrame,
    *,
    symbol: str,
    required_sessions: pd.DatetimeIndex,
) -> pd.DataFrame:
    required = {"time_key", "open", "high", "low", "close"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError(f"PHASE6_BAR_SCHEMA_MISMATCH:{symbol}")
    sessions = pd.to_datetime(
        frame["time_key"].astype(str).str.slice(0, 10),
        errors="raise",
        utc=True,
    ).dt.normalize()
    if sessions.duplicated().any():
        raise ValueError(f"PHASE6_DUPLICATE_SESSION:{symbol}")
    values = pd.DataFrame(index=pd.DatetimeIndex(sessions))
    for name in ("open", "high", "low", "close"):
        values[name] = pd.to_numeric(frame[name], errors="raise").to_numpy(dtype=float)
    matrix = values[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if (
        not values.index.is_monotonic_increasing
        or not bool(pd.notna(matrix).all())
        or not all(math.isfinite(float(value)) and float(value) > 0.0 for value in matrix.flat)
        or (values["low"] > values[["open", "close"]].min(axis=1)).any()
        or (values["high"] < values[["open", "close"]].max(axis=1)).any()
        or (values["low"] > values["high"]).any()
    ):
        raise ValueError(f"PHASE6_BAR_VALUES_INVALID:{symbol}")
    missing = required_sessions.difference(values.index)
    if len(missing):
        raise ValueError(
            f"PHASE6_REQUIRED_SESSION_MISSING:{symbol}:{missing[0].date().isoformat()}"
        )
    return values.loc[required_sessions].copy()


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    rendered = frame.rename_axis("session").reset_index()
    rendered["session"] = rendered["session"].dt.strftime("%Y-%m-%d")
    return rendered.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    ).encode("utf-8")


def acquire_and_seal(
    *,
    repository_root: Path,
    contract_path: Path,
    attestation_path: Path,
    authorization_path: Path,
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
        raise ValueError("PHASE6_PRIVATE_OUTPUT_MUST_BE_OUTSIDE_REPOSITORY")

    load_frozen_contract(contract_path)
    authorization = load_acquisition_authorization(
        authorization_path,
        contract_path=contract_path,
        attestation_path=attestation_path,
    )
    authorization_bytes = Path(authorization_path).read_bytes()
    authorization_sha = sha256_bytes(authorization_bytes)

    output.mkdir(parents=True, exist_ok=True)
    attempt_path = output / f"{authorization.authorization_id}.acquisition-started.json"
    attempt = {
        "schema_version": "PHASE6-HOLDOUT-ACQUISITION-ATTEMPT-v1",
        "authority": "INDEPENDENT_AUDIT",
        "status": "FINAL_HOLDOUT_ACQUISITION_STARTED",
        "authorization_id": authorization.authorization_id,
        "evaluation_contract_sha256": CONTRACT_SHA256,
        "acquisition_authorization_sha256": authorization_sha,
        "locked_symbols": list(LOCKED_SYMBOLS),
        "benchmark_symbol": BENCHMARK_SYMBOL,
        "historical_access_started": False,
    }
    try:
        with attempt_path.open("x", encoding="utf-8") as handle:
            json.dump(attempt, handle, sort_keys=True, separators=(",", ":"))
    except FileExistsError as exc:
        raise RuntimeError(
            f"PHASE6_ACQUISITION_AUTHORIZATION_ALREADY_CONSUMED:{authorization.authorization_id}"
        ) from exc

    warmup, scored = expected_sessions()
    required_sessions = warmup.append(scored)
    request_start = warmup[0].date().isoformat()
    request_end = HOLDOUT_END

    sdk, sdk_name = _load_sdk()
    context = sdk.OpenQuoteContext(host=host, port=port)
    frames: dict[str, pd.DataFrame] = {}
    try:
        attempt["historical_access_started"] = True
        attempt["historical_access_started_at_utc"] = datetime.now(timezone.utc).isoformat()
        attempt_path.write_text(
            json.dumps(attempt, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        for symbol in DATA_SYMBOLS:
            raw = _page_qfq(
                context,
                sdk,
                code=f"US.{symbol}",
                start=request_start,
                end=request_end,
            )
            frames[symbol] = _validated_frame(
                raw,
                symbol=symbol,
                required_sessions=required_sessions,
            )
    finally:
        context.close()

    retrieved_at = datetime.now(timezone.utc).isoformat()
    entries = {
        f"bars/{symbol}.csv": _csv_bytes(frames[symbol])
        for symbol in sorted(DATA_SYMBOLS)
    }
    base_manifest: dict[str, object] = {
        "schema_version": "PHASE6-SEALED-HOLDOUT-BUNDLE-v1",
        "authority": "INDEPENDENT_AUDIT",
        "provider": "MOOMOO_OPEND",
        "sdk_module": sdk_name,
        "sdk_version": str(getattr(sdk, "__version__", "UNKNOWN")),
        "bar_type": "K_DAY",
        "bar_autype": "QFQ",
        "extended_time": False,
        "trading_context_created": False,
        "evaluation_contract_sha256": CONTRACT_SHA256,
        "acquisition_authorization_sha256": authorization_sha,
        "requested_start": request_start,
        "requested_end": request_end,
        "holdout_start": HOLDOUT_START,
        "holdout_end": HOLDOUT_END,
        "warmup_session_count": len(warmup),
        "scored_session_count": len(scored),
        "warmup_first_session": warmup[0].date().isoformat(),
        "warmup_last_session": warmup[-1].date().isoformat(),
        "scored_first_session": scored[0].date().isoformat(),
        "scored_last_session": scored[-1].date().isoformat(),
        "locked_symbols": list(LOCKED_SYMBOLS),
        "benchmark_symbol": BENCHMARK_SYMBOL,
        "retrieved_at_utc": retrieved_at,
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(LOCKED_SYMBOLS),
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "phase4_feedback_written": False,
        "phase5_feedback_written": False,
        "live_trading_capability": False,
        "phase7_started": False,
    }
    plaintext, manifest = build_plain_bundle(manifest=base_manifest, entries=entries)
    plaintext_sha = sha256_bytes(plaintext)
    encrypted, key = encrypt_bundle(plaintext)
    bundle_sha = sha256_bytes(encrypted)
    holdout_id = f"phase6-holdout-{plaintext_sha[:32]}"

    bundle_path = output / f"{holdout_id}.bundle.aesgcm"
    key_path = output / f"{holdout_id}.key"
    receipt_path = output / f"{holdout_id}.receipt.json"
    for path in (bundle_path, key_path, receipt_path):
        if path.exists():
            raise FileExistsError(f"PHASE6_AUDIT_IMMUTABLE_OUTPUT_EXISTS:{path.name}")

    bundle_path.write_bytes(encrypted)
    key_path.write_text(key.hex(), encoding="ascii")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass

    receipt = {
        "schema_version": "PHASE6-HOLDOUT-ACQUISITION-RECEIPT-v1",
        "authority": "INDEPENDENT_AUDIT",
        "status": "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED",
        "holdout_id": holdout_id,
        "evaluation_contract_sha256": CONTRACT_SHA256,
        "acquisition_authorization_sha256": authorization_sha,
        "candidate_id": authorization.candidate_id,
        "binding_sha256": authorization.binding_sha256,
        "implementation_sha256": authorization.implementation_sha256,
        "bundle_sha256": bundle_sha,
        "plaintext_bundle_sha256": plaintext_sha,
        "key_sha256": sha256(key).hexdigest(),
        "bundle_bytes": len(encrypted),
        "provider": "MOOMOO_OPEND",
        "bar_autype": "QFQ",
        "requested_start": request_start,
        "requested_end": request_end,
        "holdout_start": HOLDOUT_START,
        "holdout_end": HOLDOUT_END,
        "warmup_session_count": len(warmup),
        "scored_session_count": len(scored),
        "retrieved_at_utc": retrieved_at,
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(LOCKED_SYMBOLS),
        "performance_computed": False,
        "performance_inspected": False,
        "bundle_manifest_sha256": sha256(
            json.dumps(
                manifest,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }
    receipt_path.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return receipt_path
