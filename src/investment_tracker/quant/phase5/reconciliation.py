from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path

from .dataset import Phase5Dataset


def _tolerance(reference: float) -> float:
    # "Stricter of USD 0.01 or 1 bp" means the smaller permitted difference.
    return min(0.01, abs(reference) * 0.0001)


def _normalize_date(value: object) -> str:
    return str(value).replace("/", "-")[:10]


def reconcile_massive_snapshot(
    dataset: Phase5Dataset,
    snapshot_path: Path | None,
    *,
    fill_sessions: set[str],
) -> dict[str, object]:
    if snapshot_path is None:
        return {
            "status": "UNKNOWN",
            "reason": "INDEPENDENT_SOURCE_SNAPSHOT_MISSING",
            "discrepancies": [],
        }
    try:
        raw_snapshot = Path(snapshot_path).read_bytes()
    except OSError:
        return {
            "status": "UNKNOWN",
            "reason": "INDEPENDENT_SOURCE_SNAPSHOT_INVALID",
            "discrepancies": [],
        }
    snapshot_sha256 = sha256(raw_snapshot).hexdigest()
    try:
        value = json.loads(raw_snapshot.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "status": "UNKNOWN",
            "reason": "INDEPENDENT_SOURCE_SNAPSHOT_INVALID",
            "snapshot_sha256": snapshot_sha256,
            "discrepancies": [],
        }
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "PHASE5-MASSIVE-CROSSCHECK-v1"
        or value.get("provider") != "MASSIVE"
    ):
        return {
            "status": "UNKNOWN",
            "reason": "INDEPENDENT_SOURCE_SNAPSHOT_INVALID",
            "snapshot_sha256": snapshot_sha256,
            "discrepancies": [],
        }
    bars = value.get("bars")
    dividends = value.get("dividends")
    splits = value.get("splits")
    if not isinstance(bars, dict) or not isinstance(dividends, dict) or not isinstance(splits, dict):
        return {
            "status": "UNKNOWN",
            "reason": "INDEPENDENT_SOURCE_SNAPSHOT_INVALID",
            "snapshot_sha256": snapshot_sha256,
            "discrepancies": [],
        }

    discrepancies: list[dict[str, object]] = []
    missing: list[str] = []
    for symbol, frame in dataset.bars.items():
        source = bars.get(symbol)
        if not isinstance(source, dict):
            missing.append(f"bars:{symbol}")
            continue
        by_date = {ts.strftime("%Y-%m-%d"): ts for ts in frame.index}
        for session in sorted(fill_sessions):
            if session not in by_date:
                continue
            other = source.get(session)
            if not isinstance(other, dict):
                missing.append(f"bars:{symbol}:{session}")
                continue
            row = frame.loc[by_date[session]]
            for field in ("open", "close"):
                left = float(row[field])
                try:
                    right = float(other[field])
                except (KeyError, TypeError, ValueError):
                    missing.append(f"bars:{symbol}:{session}:{field}")
                    continue
                if not math.isfinite(right) or abs(left - right) > _tolerance(left):
                    discrepancies.append(
                        {
                            "kind": "PRICE",
                            "symbol": symbol,
                            "session": session,
                            "field": field,
                            "opend": left,
                            "independent": right,
                            "tolerance": _tolerance(left),
                        }
                    )

        independent_divs = dividends.get(symbol)
        if not isinstance(independent_divs, list):
            missing.append(f"dividends:{symbol}")
        else:
            by_ex = {
                _normalize_date(item.get("ex_dividend_date")): item
                for item in independent_divs
                if isinstance(item, dict) and item.get("ex_dividend_date")
            }
            for event in dataset.actions.dividends[symbol]:
                key = event.ex_date.strftime("%Y-%m-%d")
                item = by_ex.get(key)
                if item is None:
                    missing.append(f"dividends:{symbol}:{key}")
                    continue
                try:
                    amount = float(item["cash_amount"])
                except (KeyError, TypeError, ValueError):
                    missing.append(f"dividends:{symbol}:{key}:amount")
                    continue
                if not math.isfinite(amount) or abs(amount - event.amount_per_unit) > 1e-8:
                    discrepancies.append(
                        {
                            "kind": "DIVIDEND",
                            "symbol": symbol,
                            "ex_date": key,
                            "opend_amount": event.amount_per_unit,
                            "independent_amount": amount,
                        }
                    )

        independent_splits = splits.get(symbol)
        if not isinstance(independent_splits, list):
            missing.append(f"splits:{symbol}")
        else:
            by_date_split = {
                _normalize_date(item.get("execution_date")): item
                for item in independent_splits
                if isinstance(item, dict) and item.get("execution_date")
            }
            for event in dataset.actions.splits[symbol]:
                key = event.effective_date.strftime("%Y-%m-%d")
                item = by_date_split.get(key)
                if item is None:
                    missing.append(f"splits:{symbol}:{key}")
                    continue
                try:
                    multiplier = float(item["split_to"]) / float(item["split_from"])
                except (KeyError, TypeError, ValueError, ZeroDivisionError):
                    missing.append(f"splits:{symbol}:{key}:ratio")
                    continue
                if not math.isfinite(multiplier) or abs(multiplier - event.unit_multiplier) > 1e-12:
                    discrepancies.append(
                        {
                            "kind": "SPLIT",
                            "symbol": symbol,
                            "effective_date": key,
                            "opend_multiplier": event.unit_multiplier,
                            "independent_multiplier": multiplier,
                        }
                    )

    if missing:
        return {
            "status": "UNKNOWN",
            "reason": "INDEPENDENT_SOURCE_EVIDENCE_INCOMPLETE",
            "snapshot_sha256": snapshot_sha256,
            "missing": sorted(set(missing)),
            "discrepancies": discrepancies,
        }
    if discrepancies:
        return {
            "status": "MISMATCH",
            "reason": "MATERIAL_PROVIDER_DISCREPANCY",
            "snapshot_sha256": snapshot_sha256,
            "discrepancies": discrepancies,
        }
    return {
        "status": "MATCH",
        "reason": "OK",
        "snapshot_sha256": snapshot_sha256,
        "discrepancies": [],
    }
