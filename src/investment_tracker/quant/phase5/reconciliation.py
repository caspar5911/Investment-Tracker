from __future__ import annotations

import json
import math
from pathlib import Path

from .dataset import Phase5Dataset


def _tolerance(reference: float) -> float:
    return min(0.01, abs(reference) * 0.0001)


def reconcile_massive_snapshot(dataset: Phase5Dataset, snapshot_path: Path | None, *, fill_sessions: set[str]) -> dict[str, object]:
    if snapshot_path is None:
        return {"status": "UNKNOWN", "reason": "INDEPENDENT_SOURCE_SNAPSHOT_MISSING", "discrepancies": []}
    value = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "PHASE5-MASSIVE-CROSSCHECK-v1":
        return {"status": "UNKNOWN", "reason": "INDEPENDENT_SOURCE_SNAPSHOT_INVALID", "discrepancies": []}
    bars = value.get("bars")
    if not isinstance(bars, dict):
        return {"status": "UNKNOWN", "reason": "INDEPENDENT_SOURCE_SNAPSHOT_INVALID", "discrepancies": []}
    discrepancies: list[dict[str, object]] = []
    missing: list[str] = []
    for symbol, frame in dataset.bars.items():
        source = bars.get(symbol)
        if not isinstance(source, dict):
            missing.append(symbol)
            continue
        by_date = {ts.strftime("%Y-%m-%d"): ts for ts in frame.index}
        for session in fill_sessions:
            if session not in by_date:
                continue
            if session not in source:
                missing.append(f"{symbol}:{session}")
                continue
            row = frame.loc[by_date[session]]
            other = source[session]
            if not isinstance(other, dict):
                missing.append(f"{symbol}:{session}")
                continue
            for field in ("open", "close"):
                left = float(row[field])
                try:
                    right = float(other[field])
                except (KeyError, TypeError, ValueError):
                    missing.append(f"{symbol}:{session}:{field}")
                    continue
                if not math.isfinite(right) or abs(left - right) > _tolerance(left):
                    discrepancies.append({"symbol": symbol, "session": session, "field": field, "opend": left, "independent": right, "tolerance": _tolerance(left)})
    if missing:
        return {"status": "UNKNOWN", "reason": "INDEPENDENT_SOURCE_EVIDENCE_INCOMPLETE", "missing": sorted(set(missing)), "discrepancies": discrepancies}
    if discrepancies:
        return {"status": "MISMATCH", "reason": "MATERIAL_PRICE_DISCREPANCY", "discrepancies": discrepancies}
    return {"status": "MATCH", "reason": "OK", "discrepancies": []}
