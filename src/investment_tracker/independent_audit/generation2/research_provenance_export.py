from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import pandas as pd

from investment_tracker.quant.data.cache import content_hash
from investment_tracker.quant.data.models import DataRequest
from investment_tracker.quant.data.moomoo_client import MoomooHistoricalDataSource
from investment_tracker.quant.data.validation import BarDataValidator
from investment_tracker.quant.generation2.grid import RESEARCH_SYMBOLS
from investment_tracker.quant.generation2.provenance import (
    FileHash,
    SourceSnapshot,
    reconcile,
    snapshot_content_sha256,
)
from investment_tracker.quant.generation2.reproduction import verify_reproduction_report
from investment_tracker.quant.universe.constants import (
    CALENDAR_SOURCE_VERSION,
    CAMPAIGN_END,
    CAMPAIGN_START,
    NORMALIZATION_VERSION,
)

EXPORT_SCHEMA = "GENERATION2-RESEARCH-PROVIDER-ORIGIN-EXPORT-v1"
PRIMARY_SCHEMA = "GENERATION2-PRIMARY-RESEARCH-SNAPSHOT-v1"
RECONCILIATION_SCHEMA = "GENERATION2-INDEPENDENT-RECONCILIATION-v1"

FORBIDDEN_HOLDOUT_SYMBOLS = frozenset(("BNO", "GBIL", "CWS", "ESG", "VICI"))


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _expected_session_authority_sha256() -> str:
    calendar = xcals.get_calendar("XNYS")
    sessions = pd.DatetimeIndex(calendar.sessions_in_range(CAMPAIGN_START, CAMPAIGN_END))
    dates = [ts.tz_convert("UTC").date().isoformat() if ts.tzinfo else ts.date().isoformat() for ts in sessions]
    return sha256(
        _canonical_bytes(
            {
                "calendar": "XNYS",
                "calendar_source_version": CALENDAR_SOURCE_VERSION,
                "range_start": CAMPAIGN_START.isoformat(),
                "range_end": CAMPAIGN_END.isoformat(),
                "sessions": dates,
            }
        )
    ).hexdigest()


def _normalized_csv_bytes(frame: pd.DataFrame) -> bytes:
    canonical = frame.loc[:, ("open", "high", "low", "close", "volume")].copy()
    canonical.index.name = "timestamp"
    return canonical.to_csv(
        index=True,
        date_format="%Y-%m-%dT%H:%M:%S.%f%z",
        float_format="%.17g",
        lineterminator="\n",
    ).encode("utf-8")


def _raw_page_bundle_hash(page_paths: list[Path]) -> str:
    manifest = [
        {
            "path": path.name,
            "sha256": _sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(page_paths, key=lambda p: p.name)
    ]
    return sha256(_canonical_bytes(manifest)).hexdigest()


def export_and_reconcile(
    *,
    output_root: Path,
    reproduction_report_path: Path,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> dict[str, Any]:
    if set(RESEARCH_SYMBOLS) & FORBIDDEN_HOLDOUT_SYMBOLS:
        raise ValueError("GEN2_PROVENANCE_RESEARCH_HOLDOUT_OVERLAP")

    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("GEN2_PROVENANCE_OUTPUT_NOT_EMPTY")
    (root / "raw").mkdir(parents=True, exist_ok=True)
    (root / "normalized").mkdir(parents=True, exist_ok=True)

    reproduction = verify_reproduction_report(reproduction_report_path)
    primary_hashes = reproduction.get("snapshot_symbols")
    if not isinstance(primary_hashes, dict) or set(primary_hashes) != set(RESEARCH_SYMBOLS):
        raise ValueError("GEN2_PROVENANCE_PRIMARY_HASH_SET_INVALID")

    source = MoomooHistoricalDataSource(host=host, port=port)
    validator = BarDataValidator("XNYS")
    raw_hashes: list[FileHash] = []
    normalized_hashes: list[FileHash] = []
    exported_files: list[dict[str, Any]] = []
    retrieved_at_values: list[str] = []

    for symbol in RESEARCH_SYMBOLS:
        request = DataRequest(
            symbol=symbol,
            start=CAMPAIGN_START,
            end=CAMPAIGN_END,
            adjustment="QFQ",
        )
        evidence = source.fetch_with_evidence(request)
        if evidence.status != "SUCCESS" or evidence.normalized is None:
            raise RuntimeError(f"GEN2_PROVENANCE_EXPORT_FAILED:{symbol}:{evidence.error}")

        report = validator.validate(evidence.normalized, request)
        if not report.clean:
            codes = ",".join(issue.code for issue in report.issues)
            raise ValueError(f"GEN2_PROVENANCE_VALIDATION_FAILED:{symbol}:{codes}")

        retrieved_at_values.append(evidence.retrieved_at.astimezone(timezone.utc).isoformat())

        symbol_raw = root / "raw" / symbol
        symbol_raw.mkdir(parents=True, exist_ok=True)
        page_paths: list[Path] = []
        for page in evidence.pages:
            path = symbol_raw / f"page-{page.page_number:03d}.csv"
            page.frame.to_csv(path, index=False, lineterminator="\n")
            page_paths.append(path)
            exported_files.append(
                {
                    "kind": "RAW_PROVIDER_PAGE",
                    "symbol": symbol,
                    "path": path.relative_to(root).as_posix(),
                    "sha256": _sha256_file(path),
                    "bytes": path.stat().st_size,
                    "page_number": page.page_number,
                }
            )

        normalized_path = root / "normalized" / f"{symbol}.csv"
        normalized_path.write_bytes(_normalized_csv_bytes(evidence.normalized))
        normalized_digest = content_hash(evidence.normalized)
        if _sha256_file(normalized_path) != normalized_digest:
            raise ValueError(f"GEN2_PROVENANCE_NORMALIZED_SERIALIZATION_MISMATCH:{symbol}")
        raw_digest = _raw_page_bundle_hash(page_paths)
        raw_hashes.append(FileHash(symbol=symbol, sha256=raw_digest))
        normalized_hashes.append(FileHash(symbol=symbol, sha256=normalized_digest))
        exported_files.append(
            {
                "kind": "NORMALIZED_QFQ",
                "symbol": symbol,
                "path": normalized_path.relative_to(root).as_posix(),
                "sha256": normalized_digest,
                "bytes": normalized_path.stat().st_size,
            }
        )

    expected_session_sha = _expected_session_authority_sha256()
    acquisition_utc = max(retrieved_at_values)

    independent = SourceSnapshot(
        schema_version="G2-INDEPENDENT-SOURCE-PROVENANCE-v1",
        provider="MOOMOO_OPEND",
        acquisition_utc=acquisition_utc,
        symbols=RESEARCH_SYMBOLS,
        range_start=CAMPAIGN_START.isoformat(),
        range_end=CAMPAIGN_END.isoformat(),
        adjustment_convention="QFQ",
        raw_file_hashes=tuple(raw_hashes),
        normalized_file_hashes=tuple(normalized_hashes),
        expected_session_authority_sha256=expected_session_sha,
        corporate_action_source_hashes=(),
        transformation_code_version=NORMALIZATION_VERSION,
        independence="PROVIDER_ORIGIN_EXPORT",
    )
    primary = SourceSnapshot(
        schema_version="G2-INDEPENDENT-SOURCE-PROVENANCE-v1",
        provider="SEALED_PHASE3_RESEARCH_CACHE",
        acquisition_utc="SEALED_PRE_GENERATION2_CAMPAIGN",
        symbols=RESEARCH_SYMBOLS,
        range_start=CAMPAIGN_START.isoformat(),
        range_end=CAMPAIGN_END.isoformat(),
        adjustment_convention="QFQ",
        raw_file_hashes=(),
        normalized_file_hashes=tuple(
            FileHash(symbol=symbol, sha256=str(primary_hashes[symbol]))
            for symbol in RESEARCH_SYMBOLS
        ),
        expected_session_authority_sha256=expected_session_sha,
        corporate_action_source_hashes=(),
        transformation_code_version=NORMALIZATION_VERSION,
        independence="SAME_PROVIDER",
    )
    reconciliation = reconcile(primary, independent)

    primary_payload = primary.model_dump(mode="json")
    primary_payload["snapshot_sha256"] = snapshot_content_sha256(primary)
    independent_payload = independent.model_dump(mode="json")
    independent_payload["snapshot_sha256"] = snapshot_content_sha256(independent)
    independent_payload["schema_version_export"] = EXPORT_SCHEMA
    independent_payload["files"] = sorted(
        exported_files,
        key=lambda x: (str(x["symbol"]), str(x["kind"]), str(x["path"])),
    )
    reconciliation_payload = reconciliation.model_dump(mode="json")
    reconciliation_payload["schema_version_reconciliation"] = RECONCILIATION_SCHEMA
    reconciliation_payload["reproduction_report_sha256"] = reproduction["report_sha256"]

    (root / "primary-snapshot.json").write_bytes(_canonical_bytes(primary_payload))
    (root / "provider-origin-snapshot.json").write_bytes(_canonical_bytes(independent_payload))
    (root / "reconciliation.json").write_bytes(_canonical_bytes(reconciliation_payload))

    result = {
        "status": reconciliation.status,
        "independent_source_established": reconciliation.independent_source_established,
        "decision_critical": reconciliation.decision_critical,
        "primary_snapshot_sha256": primary_payload["snapshot_sha256"],
        "provider_origin_snapshot_sha256": independent_payload["snapshot_sha256"],
        "reconciliation_sha256": _sha256_file(root / "reconciliation.json"),
        "normalized_hashes_match": {
            symbol: primary_hashes[symbol]
            == next(item.sha256 for item in normalized_hashes if item.normalized_symbol == symbol)
            for symbol in RESEARCH_SYMBOLS
        },
        "output_root": str(root),
    }
    (root / "result.json").write_bytes(_canonical_bytes(result))
    return result
