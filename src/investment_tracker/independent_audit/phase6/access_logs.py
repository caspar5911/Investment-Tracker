from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re

from .authority import (
    AccessLogEvidence,
    AccessLogMatch,
    EvidenceFile,
    LOCKED_SYMBOLS,
)

_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?:US[.])?(HACK|SOXX|NLR|URNM|GEV)(?![A-Z0-9])",
    re.IGNORECASE,
)

_HISTORY_TOKENS = (
    "Qot_RequestHistoryKL",
    "RequestHistoryKL",
    "request_history_kline",
    "protoid=3103",
    "proto_id=3103",
    "proto id=3103",
    "proto:3103",
    "proto=3103",
    "3103",
)
_REHAB_TOKENS = (
    "Qot_RequestRehab",
    "RequestRehab",
    "get_rehab",
    "protoid=3105",
    "proto_id=3105",
    "proto id=3105",
    "proto:3105",
    "proto=3105",
)
_CONTEXT_RADIUS = 8


def _files(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    result: list[Path] = []
    for supplied in paths:
        path = Path(supplied).resolve()
        if path.is_file():
            result.append(path)
        elif path.is_dir():
            result.extend(item for item in path.rglob("*") if item.is_file())
        else:
            raise FileNotFoundError(path)
    ordered = tuple(sorted(set(result), key=lambda item: str(item)))
    if not ordered:
        raise ValueError("PHASE6_ACCESS_LOG_SET_EMPTY")
    return ordered


def scan_access_logs(
    paths: tuple[Path, ...],
    *,
    source_description: str,
    coverage_start_utc: datetime,
    coverage_end_utc: datetime,
    output_path: Path,
) -> Path:
    files = _files(paths)
    file_records: list[EvidenceFile] = []
    matches: list[AccessLogMatch] = []
    for path in files:
        payload = path.read_bytes()
        file_records.append(
            EvidenceFile(
                path=str(path),
                sha256=sha256(payload).hexdigest(),
                bytes=len(payload),
            )
        )
        text = payload.decode("utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            for match in _PATTERN.finditer(line):
                symbol = match.group(1).upper()
                if symbol in LOCKED_SYMBOLS:
                    matches.append(
                        AccessLogMatch(
                            path=str(path),
                            symbol=symbol,
                            line_number=number,
                        )
                    )
    evidence = AccessLogEvidence(
        schema_version="PHASE6-ACCESS-LOG-EVIDENCE-v1",
        status=(
            "LOCKED_SYMBOL_REFERENCE_FOUND"
            if matches
            else "NO_LOCKED_SYMBOL_REFERENCE_FOUND_IN_SUPPLIED_LOGS"
        ),
        source_description=source_description,
        coverage_start_utc=coverage_start_utc,
        coverage_end_utc=coverage_end_utc,
        files=tuple(file_records),
        matches=tuple(matches),
    )
    output = Path(output_path)
    if output.exists():
        raise FileExistsError("PHASE6_ACCESS_LOG_EVIDENCE_ALREADY_EXISTS")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            evidence.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return output


def _operation_classification(lines: list[str], line_index: int) -> tuple[str, tuple[str, ...]]:
    start = max(0, line_index - _CONTEXT_RADIUS)
    end = min(len(lines), line_index + _CONTEXT_RADIUS + 1)
    context = "\n".join(lines[start:end])
    lower = context.lower()

    history_hits = tuple(
        token
        for token in _HISTORY_TOKENS
        if token.lower() in lower
    )
    if history_hits:
        return "HISTORICAL_KLINE_CONTEXT", history_hits

    rehab_hits = tuple(
        token
        for token in _REHAB_TOKENS
        if token.lower() in lower
    )
    if rehab_hits:
        return "REHAB_CONTEXT", rehab_hits

    return "OTHER_OR_UNCLASSIFIED_SYMBOL_CONTEXT", ()


def classify_access_logs(
    paths: tuple[Path, ...],
    *,
    output_path: Path,
) -> Path:
    files = _files(paths)
    records: list[dict[str, object]] = []
    seen: set[tuple[str, int, str, str]] = set()

    for path in files:
        payload = path.read_bytes()
        text = payload.decode("utf-8", errors="replace")
        lines = text.splitlines()
        for line_index, line in enumerate(lines):
            for match in _PATTERN.finditer(line):
                symbol = match.group(1).upper()
                if symbol not in LOCKED_SYMBOLS:
                    continue
                classification, tokens = _operation_classification(lines, line_index)
                identity = (str(path), line_index + 1, symbol, classification)
                if identity in seen:
                    continue
                seen.add(identity)
                records.append(
                    {
                        "path": str(path),
                        "line_number": line_index + 1,
                        "symbol": symbol,
                        "classification": classification,
                        "operation_tokens": list(tokens),
                    }
                )

    by_symbol: dict[str, dict[str, int]] = {}
    for symbol in LOCKED_SYMBOLS:
        symbol_records = [item for item in records if item["symbol"] == symbol]
        by_symbol[symbol] = {
            "historical_kline_context": sum(
                item["classification"] == "HISTORICAL_KLINE_CONTEXT"
                for item in symbol_records
            ),
            "rehab_context": sum(
                item["classification"] == "REHAB_CONTEXT"
                for item in symbol_records
            ),
            "other_or_unclassified": sum(
                item["classification"] == "OTHER_OR_UNCLASSIFIED_SYMBOL_CONTEXT"
                for item in symbol_records
            ),
            "total": len(symbol_records),
        }

    historical = [
        item for item in records
        if item["classification"] == "HISTORICAL_KLINE_CONTEXT"
    ]
    result = {
        "schema_version": "PHASE6-ACCESS-LOG-CLASSIFICATION-v1",
        "status": (
            "HISTORICAL_KLINE_CONTEXT_FOUND"
            if historical
            else "NO_HISTORICAL_KLINE_CONTEXT_FOUND"
        ),
        "classifier": {
            "history_protocol": "Qot_RequestHistoryKL",
            "history_protocol_id": 3103,
            "context_radius_lines": _CONTEXT_RADIUS,
            "raw_line_content_emitted": False,
            "classification_is_not_a_virgin_holdout_attestation": True,
        },
        "locked_symbols": list(LOCKED_SYMBOLS),
        "counts_by_symbol": by_symbol,
        "historical_kline_matches": historical,
        "all_classified_matches": records,
    }

    output = Path(output_path)
    if output.exists():
        raise FileExistsError("PHASE6_ACCESS_LOG_CLASSIFICATION_ALREADY_EXISTS")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return output
