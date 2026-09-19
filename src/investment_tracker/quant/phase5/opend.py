from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .methodology import (
    ACQUISITION_END,
    ACQUISITION_START,
    PROTECTED_SYMBOLS,
    SYMBOLS,
    assert_allowed_symbols,
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _page_history(context: Any, code: str, *, autype: Any, k_day: Any) -> Any:
    import pandas as pd

    rows = []
    page_key = None
    while True:
        ret, data, page_key = context.request_history_kline(
            code,
            start=ACQUISITION_START,
            end=ACQUISITION_END,
            ktype=k_day,
            autype=autype,
            max_count=1000,
            page_req_key=page_key,
            extended_time=False,
        )
        if ret != 0:
            raise RuntimeError(f"OPEND_HISTORY_FAILED:{code}:{data}")
        if not isinstance(data, pd.DataFrame):
            raise RuntimeError(f"OPEND_HISTORY_INVALID:{code}")
        rows.append(data.copy(deep=True))
        if page_key is None:
            break
    if not rows:
        raise RuntimeError(f"OPEND_HISTORY_EMPTY:{code}")
    result = pd.concat(rows, ignore_index=True)
    if "time_key" not in result or "open" not in result or "close" not in result:
        raise RuntimeError(f"OPEND_HISTORY_SCHEMA_MISMATCH:{code}")
    result = result.sort_values("time_key", kind="stable").drop_duplicates("time_key", keep=False)
    if result.empty:
        raise RuntimeError(f"OPEND_HISTORY_EMPTY_AFTER_DEDUP:{code}")
    return result


def export_opend_bundle(
    output_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> Path:
    """Export the exact Phase 5 OpenD bundle. No trading context is created."""

    assert_allowed_symbols(SYMBOLS)
    if any(symbol in PROTECTED_SYMBOLS for symbol in SYMBOLS):
        raise RuntimeError("PHASE5_GOVERNANCE_BREACH")

    try:
        from futu import AuType, KLType, OpenQuoteContext, RET_OK
    except ImportError as exc:
        raise RuntimeError("FUTU_OPEND_PYTHON_PACKAGE_REQUIRED") from exc

    root = Path(output_dir).resolve()
    raw_dir = root / "raw"
    qfq_dir = root / "qfq"
    rehab_dir = root / "rehab"
    for directory in (raw_dir, qfq_dir, rehab_dir):
        directory.mkdir(parents=True, exist_ok=True)

    manifest_files: list[dict[str, object]] = []
    context = OpenQuoteContext(host=host, port=port)
    try:
        for symbol in SYMBOLS:
            code = f"US.{symbol}"
            raw = _page_history(context, code, autype=AuType.NONE, k_day=KLType.K_DAY)
            qfq = _page_history(context, code, autype=AuType.QFQ, k_day=KLType.K_DAY)
            ret, rehab = context.get_rehab(code)
            if ret != RET_OK:
                raise RuntimeError(f"OPEND_REHAB_FAILED:{code}:{rehab}")

            raw_path = raw_dir / f"{symbol}.csv"
            qfq_path = qfq_dir / f"{symbol}.csv"
            rehab_path = rehab_dir / f"{symbol}.csv"
            raw.to_csv(raw_path, index=False, lineterminator="\n")
            qfq.to_csv(qfq_path, index=False, lineterminator="\n")
            rehab.to_csv(rehab_path, index=False, lineterminator="\n")

            for kind, path in (("RAW_NONE", raw_path), ("SIGNAL_QFQ", qfq_path), ("REHAB", rehab_path)):
                manifest_files.append(
                    {
                        "kind": kind,
                        "symbol": symbol,
                        "path": path.relative_to(root).as_posix(),
                        "sha256": _sha256(path),
                        "bytes": path.stat().st_size,
                    }
                )
    finally:
        context.close()

    manifest = {
        "schema_version": "PHASE5-OPEND-BUNDLE-v1",
        "provider": "MOOMOO_OPEND",
        "host_recorded": host,
        "port_recorded": int(port),
        "acquisition_start": ACQUISITION_START,
        "acquisition_end": ACQUISITION_END,
        "symbols": list(SYMBOLS),
        "raw_autype": "NONE",
        "signal_autype": "QFQ",
        "kline_type": "K_DAY",
        "extended_time": False,
        "trading_context_created": False,
        "protected_symbols_accessed": [],
        "final_holdout_accessed": False,
        "files": sorted(manifest_files, key=lambda item: (str(item["symbol"]), str(item["kind"]))),
    }
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest_path = root / "manifest.json"
    manifest_path.write_bytes(payload)
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase5-opend-export")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11111)
    args = parser.parse_args(argv)
    path = export_opend_bundle(Path(args.output_dir), host=args.host, port=args.port)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
