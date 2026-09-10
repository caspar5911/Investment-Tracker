from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from .governance import assert_symbol_allowed
from .identity import canonical_bar_key, raw_digest_token
from .models import WorkerManifest


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    counts: dict[str, int]
    errors: tuple[str, ...]


def _parse_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"invalid bar_date: {value!r}")


def validate_market_bars(
    rows: Iterable[Mapping[str, object]],
    benchmark_dates: set[date],
) -> ValidationReport:
    materialized = list(rows)
    errors: list[str] = []
    parsed_dates: list[date] = []
    keys: list[str] = []
    close_usable = 0
    range_usable = 0
    benchmark_mismatches = 0

    if not materialized:
        errors.append("no market-data evidence")

    for index, row in enumerate(materialized, start=1):
        try:
            asset = assert_symbol_allowed(str(row["asset"]))
            bar_date = _parse_date(row["bar_date"])
            expected_key = canonical_bar_key(asset, bar_date)
            actual_key = str(row["bar_key"])
            if actual_key != expected_key:
                errors.append(f"row {index}: bar_key mismatch")

            expected_digest = raw_digest_token(
                asset,
                bar_date,
                row["open_raw"],
                row["high_raw"],
                row["low_raw"],
                row["close_raw"],
                row["volume_raw"],
                row["trade_count_raw"],
                row["vwap_raw"],
            )
            if str(row["source_digest"]) != expected_digest:
                errors.append(f"row {index}: source_digest mismatch")

            parsed_dates.append(bar_date)
            keys.append(actual_key)
            if row.get("close_usable") is True:
                close_usable += 1
            if row.get("range_usable") is True:
                range_usable += 1
            if bar_date not in benchmark_dates:
                benchmark_mismatches += 1
        except Exception as exc:
            errors.append(f"row {index}: invalid market bar: {exc}")

    duplicate_keys = [key for key, count in Counter(keys).items() if count > 1]
    if duplicate_keys:
        errors.append(f"duplicate bar_key: {', '.join(sorted(duplicate_keys))}")

    duplicate_dates = [value.isoformat() for value, count in Counter(parsed_dates).items() if count > 1]
    if duplicate_dates:
        errors.append(f"duplicate bar_date: {', '.join(sorted(duplicate_dates))}")

    if benchmark_mismatches:
        errors.append(f"benchmark date mismatch count: {benchmark_mismatches}")

    counts = {
        "rows": len(materialized),
        "unique_dates": len(set(parsed_dates)),
        "unique_keys": len(set(keys)),
        "close_usable": close_usable,
        "range_usable": range_usable,
        "benchmark_mismatches": benchmark_mismatches,
    }
    return ValidationReport(ok=not errors, counts=counts, errors=tuple(errors))


def validate_manifest_files(manifest_path: str | Path) -> ValidationReport:
    path = Path(manifest_path)
    errors: list[str] = []
    verified_files = 0

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = WorkerManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return ValidationReport(
            ok=False,
            counts={"verified_files": 0},
            errors=(f"invalid manifest: {exc}",),
        )

    if not manifest.output_digests:
        errors.append("no output evidence declared")

    for relative_name, expected_digest in manifest.output_digests.items():
        artifact_path = path.parent / relative_name
        try:
            actual_digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        except OSError as exc:
            errors.append(f"missing artifact {relative_name}: {exc}")
            continue
        if actual_digest != expected_digest:
            errors.append(f"digest mismatch: {relative_name}")
            continue
        verified_files += 1

    return ValidationReport(
        ok=not errors,
        counts={"verified_files": verified_files},
        errors=tuple(errors),
    )
