from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .methodology import ACQUISITION_CUTOFF, ACQUISITION_REQUEST_START, SYMBOLS, assert_requested_symbols


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return [_jsonable(row) for row in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return _jsonable(value.to_dict())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _load_sdk() -> tuple[Any, str]:
    errors = []
    for module_name in ("moomoo", "futu"):
        try:
            return importlib.import_module(module_name), module_name
        except ImportError as exc:
            errors.append(str(exc))
    raise RuntimeError("MOOMOO_OR_FUTU_OPEND_PYTHON_PACKAGE_REQUIRED:" + "|".join(errors))


def _page_history(context: Any, sdk: Any, code: str) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    page_key = None
    while True:
        ret, data, page_key = context.request_history_kline(
            code,
            start=ACQUISITION_REQUEST_START,
            end=ACQUISITION_CUTOFF,
            ktype=sdk.KLType.K_DAY,
            autype=sdk.AuType.NONE,
            max_count=1000,
            page_req_key=page_key,
            extended_time=False,
        )
        if ret != sdk.RET_OK:
            raise RuntimeError(f"OPEND_HISTORY_FAILED:{code}:{data}")
        if not isinstance(data, pd.DataFrame):
            raise RuntimeError(f"OPEND_HISTORY_INVALID:{code}")
        rows.append(data.copy(deep=True))
        if page_key is None:
            break
    result = pd.concat(rows, ignore_index=True)
    required = {"time_key", "open", "high", "low", "close"}
    if result.empty or not required.issubset(result.columns):
        raise RuntimeError(f"OPEND_HISTORY_SCHEMA_MISMATCH:{code}")
    if result["time_key"].duplicated().any():
        raise RuntimeError(f"OPEND_HISTORY_DUPLICATE_SESSION:{code}")
    return result.sort_values("time_key", kind="stable").reset_index(drop=True)


def _stock_splits(context: Any, sdk: Any, code: str) -> dict[str, object]:
    records: list[object] = []
    next_key = None
    while True:
        ret, data = context.get_corporate_actions_stock_splits(code, next_key=next_key, num=50)
        if ret != sdk.RET_OK:
            raise RuntimeError(f"OPEND_SPLITS_FAILED:{code}:{data}")
        if not isinstance(data, dict):
            raise RuntimeError(f"OPEND_SPLITS_INVALID:{code}")
        current = _jsonable(data.get("split_list", []))
        if not isinstance(current, list):
            raise RuntimeError(f"OPEND_SPLITS_INVALID:{code}")
        records.extend(current)
        next_key = data.get("next_key")
        if next_key in (None, "", "-1"):
            break
    return {"split_list": records}


def export_opend_bundle(
    output_dir: Path,
    *,
    symbols: tuple[str, ...] = SYMBOLS,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> Path:
    canonical_symbols = assert_requested_symbols(symbols)
    sdk, sdk_name = _load_sdk()
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name in ("bars", "rehab", "dividends", "splits"):
        (root / name).mkdir(parents=True, exist_ok=True)

    files: list[dict[str, object]] = []
    context = sdk.OpenQuoteContext(host=host, port=port)
    try:
        for symbol in canonical_symbols:
            code = f"US.{symbol}"
            bars = _page_history(context, sdk, code)
            ret, rehab = context.get_rehab(code)
            if ret != sdk.RET_OK or not isinstance(rehab, pd.DataFrame):
                raise RuntimeError(f"OPEND_REHAB_FAILED:{code}:{rehab}")
            ret, dividends = context.get_corporate_actions_dividends(code)
            if ret != sdk.RET_OK or not isinstance(dividends, dict):
                raise RuntimeError(f"OPEND_DIVIDENDS_FAILED:{code}:{dividends}")
            splits = _stock_splits(context, sdk, code)
            outputs = {
                "RAW_NONE": root / "bars" / f"{symbol}.csv",
                "REHAB": root / "rehab" / f"{symbol}.csv",
                "DIVIDENDS": root / "dividends" / f"{symbol}.json",
                "SPLITS": root / "splits" / f"{symbol}.json",
            }
            bars.to_csv(outputs["RAW_NONE"], index=False, lineterminator="\n")
            rehab.to_csv(outputs["REHAB"], index=False, lineterminator="\n")
            outputs["DIVIDENDS"].write_text(
                json.dumps({"symbol": symbol, "response": _jsonable(dividends)}, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            outputs["SPLITS"].write_text(
                json.dumps({"symbol": symbol, "response": _jsonable(splits)}, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            for kind, path in outputs.items():
                files.append({"kind": kind, "symbol": symbol, "path": path.relative_to(root).as_posix(), "sha256": _sha256(path), "bytes": path.stat().st_size})
    finally:
        context.close()

    manifest = {
        "schema_version": "PHASE5-OPEND-PROVIDER-EXPORT-v1",
        "provider": "MOOMOO_OPEND",
        "sdk_module": sdk_name,
        "sdk_version": str(getattr(sdk, "__version__", "UNKNOWN")),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_start": ACQUISITION_REQUEST_START,
        "requested_end": ACQUISITION_CUTOFF,
        "symbols": list(canonical_symbols),
        "bar_type": "K_DAY",
        "bar_autype": "NONE",
        "extended_time": False,
        "trading_context_created": False,
        "protected_symbols_accessed": [],
        "final_holdout_accessed": False,
        "files": sorted(files, key=lambda item: (str(item["symbol"]), str(item["kind"]))),
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase5-opend-export")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11111)
    args = parser.parse_args(argv)
    print(export_opend_bundle(Path(args.output_dir), host=args.host, port=args.port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
