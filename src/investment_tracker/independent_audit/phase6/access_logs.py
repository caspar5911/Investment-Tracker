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
