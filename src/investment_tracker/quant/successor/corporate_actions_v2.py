from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import math
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

NORMALIZATION_SCHEMA = "CORPORATE-ACTION-NORMALIZATION-v2"
NORMALIZATION_STATUS = "PROPOSED_AWAITING_INDEPENDENT_AUDIT"
_RATIO_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)->([0-9]+(?:\.[0-9]+)?)$")
_REL_TOL = 1e-10
_ABS_TOL = 1e-12


class CorporateActionNormalizationError(ValueError):
    """Fail-closed successor normalization error."""


@dataclass(frozen=True)
class EndpointRate:
    normalized_text: str
    old_units: Decimal
    new_units: Decimal
    unit_multiplier: float


@dataclass(frozen=True)
class NormalizedSplit:
    symbol: str
    effective_date: date
    unit_multiplier: float
    rehab_adjustment_ratio: float
    endpoint_rate: str
    endpoint_dated: bool
    rehab_record_sha256: str
    endpoint_record_sha256: str


@dataclass(frozen=True)
class SplitNormalizationResult:
    schema_version: str
    status: str
    symbol: str
    events: tuple[NormalizedSplit, ...]
    ignored_dated_endpoint_outside_window: int
    ignored_undated_endpoint_records: int
    ignored_rehab_outside_window: int


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")


def _identity(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_bytes(dict(value))).hexdigest()


def _positive_decimal(value: object, identity: str) -> Decimal:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError) as exc:
        raise CorporateActionNormalizationError(
            f"SUCCESSOR_SPLIT_RATIO_INVALID:{identity}"
        ) from exc
    if not number.is_finite() or number <= 0:
        raise CorporateActionNormalizationError(
            f"SUCCESSOR_SPLIT_RATIO_INVALID:{identity}"
        )
    return number


def normalize_endpoint_rate(value: object) -> EndpointRate:
    """Normalize documented OpenD old-units to new-units split syntax.

    Accepted separators are the documented ASCII arrow -> and Unicode
    RIGHTWARDS ARROW U+2192. Unicode is NFKC-normalized before the explicit
    U+2192-to-ASCII translation. Other separators are intentionally rejected.
    """
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u2192", "->")
    text = "".join(text.split())
    match = _RATIO_RE.fullmatch(text)
    if match is None:
        raise CorporateActionNormalizationError(
            f"SUCCESSOR_SPLIT_RATE_SYNTAX_UNSUPPORTED:{text or 'EMPTY'}"
        )
    old_units = _positive_decimal(match.group(1), "ENDPOINT_OLD_UNITS")
    new_units = _positive_decimal(match.group(2), "ENDPOINT_NEW_UNITS")
    multiplier = new_units / old_units
    return EndpointRate(
        normalized_text=f"{old_units.normalize()}->{new_units.normalize()}",
        old_units=old_units,
        new_units=new_units,
        unit_multiplier=float(multiplier),
    )


def rehab_adjustment_ratio_to_unit_multiplier(value: object) -> float:
    """Convert OpenD rehab split_ratio into a portfolio share multiplier.

    OpenD documents rehab split_ratio as old/new. For example, a 1-to-5
    split has split_ratio 1/5. A position ledger requires new/old, therefore
    the unit multiplier is the reciprocal.
    """
    ratio = _positive_decimal(value, "REHAB_SPLIT_RATIO")
    return float(Decimal(1) / ratio)


def _date(value: object, identity: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError) as exc:
            raise CorporateActionNormalizationError(
                f"SUCCESSOR_SPLIT_DATE_INVALID:{identity}"
            ) from exc
    text = str(value or "").strip()
    if not text or text == "0":
        raise CorporateActionNormalizationError(
            f"SUCCESSOR_SPLIT_DATE_MISSING:{identity}"
        )
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise CorporateActionNormalizationError(
            f"SUCCESSOR_SPLIT_DATE_INVALID:{identity}"
        ) from exc


def _optional_endpoint_date(row: Mapping[str, Any]) -> date | None:
    raw = row.get("ex_date_str")
    if raw in (None, "", 0, "0"):
        raw = row.get("ex_date")
    if raw in (None, "", 0, "0"):
        return None
    return _date(raw, "ENDPOINT_EX_DATE")


def _same_multiplier(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=_REL_TOL, abs_tol=_ABS_TOL)


def _rehab_split_ratio(row: Mapping[str, Any]) -> float | None:
    raw = row.get("split_ratio")
    if raw in (None, "", 0, "0"):
        return None
    ratio = _positive_decimal(raw, "REHAB_SPLIT_RATIO")
    if ratio == Decimal(1):
        return None
    return float(ratio)


def normalize_split_events(
    *,
    symbol: str,
    rehab_rows: Sequence[Mapping[str, Any]],
    endpoint_rows: Sequence[Mapping[str, Any]],
    evaluation_start: date | str,
    evaluation_end: date | str,
    scored_sessions: Iterable[date | str],
) -> SplitNormalizationResult:
    """Normalize split evidence without accessing market history.

    Rehab is the effective-date authority. The corporate-action endpoint is a
    corroborating source. For markets where that endpoint has no ex-date, an
    undated row may corroborate an in-window rehab event only when its
    normalized unit multiplier is a unique one-to-one match.
    """
    start = _date(evaluation_start, "EVALUATION_START")
    end = _date(evaluation_end, "EVALUATION_END")
    if end < start:
        raise CorporateActionNormalizationError("SUCCESSOR_SPLIT_WINDOW_INVALID")
    sessions = {_date(item, "SCORED_SESSION") for item in scored_sessions}

    dated_endpoint: list[dict[str, Any]] = []
    undated_endpoint: list[dict[str, Any]] = []
    ignored_dated_outside = 0

    for row in endpoint_rows:
        if not isinstance(row, Mapping):
            raise CorporateActionNormalizationError(
                "SUCCESSOR_SPLIT_ENDPOINT_RECORD_INVALID"
            )
        event_date = _optional_endpoint_date(row)
        if event_date is not None and not (start <= event_date <= end):
            ignored_dated_outside += 1
            continue
        if event_date is not None and event_date not in sessions:
            raise CorporateActionNormalizationError(
                f"SUCCESSOR_SPLIT_SESSION_INVALID:{symbol}:{event_date.isoformat()}"
            )
        rate = normalize_endpoint_rate(row.get("rate"))
        item = {
            "date": event_date,
            "unit_multiplier": rate.unit_multiplier,
            "rate": rate.normalized_text,
            "sha256": _identity(row),
            "used": False,
        }
        if event_date is None:
            undated_endpoint.append(item)
        else:
            dated_endpoint.append(item)

    dated_keys = [
        (item["date"], item["rate"], item["sha256"]) for item in dated_endpoint
    ]
    dated_semantic_keys = [(item["date"], item["rate"]) for item in dated_endpoint]
    if len(dated_keys) != len(set(dated_keys)) or len(dated_semantic_keys) != len(
        set(dated_semantic_keys)
    ):
        raise CorporateActionNormalizationError(
            f"SUCCESSOR_SPLIT_DUPLICATE_ENDPOINT_EVENT:{symbol}"
        )

    rehab_events: list[dict[str, Any]] = []
    ignored_rehab_outside = 0
    seen_rehab_dates: set[date] = set()
    for row in rehab_rows:
        if not isinstance(row, Mapping):
            raise CorporateActionNormalizationError(
                "SUCCESSOR_SPLIT_REHAB_RECORD_INVALID"
            )
        event_date = _date(row.get("ex_div_date"), "REHAB_EX_DATE")
        if not (start <= event_date <= end):
            ignored_rehab_outside += 1
            continue
        split_ratio = _rehab_split_ratio(row)
        if split_ratio is None:
            continue
        if event_date not in sessions:
            raise CorporateActionNormalizationError(
                f"SUCCESSOR_SPLIT_SESSION_INVALID:{symbol}:{event_date.isoformat()}"
            )
        if event_date in seen_rehab_dates:
            raise CorporateActionNormalizationError(
                f"SUCCESSOR_SPLIT_DUPLICATE_REHAB_EVENT:{symbol}:{event_date.isoformat()}"
            )
        seen_rehab_dates.add(event_date)
        rehab_events.append(
            {
                "date": event_date,
                "adjustment_ratio": split_ratio,
                "unit_multiplier": rehab_adjustment_ratio_to_unit_multiplier(
                    split_ratio
                ),
                "sha256": _identity(row),
            }
        )

    normalized: list[NormalizedSplit] = []
    for rehab in rehab_events:
        same_date = [
            item
            for item in dated_endpoint
            if not item["used"] and item["date"] == rehab["date"]
        ]
        if same_date:
            if len(same_date) != 1:
                raise CorporateActionNormalizationError(
                    f"SUCCESSOR_SPLIT_ENDPOINT_DATE_AMBIGUOUS:{symbol}:{rehab['date'].isoformat()}"
                )
            candidate = same_date[0]
            if not _same_multiplier(
                candidate["unit_multiplier"], rehab["unit_multiplier"]
            ):
                raise CorporateActionNormalizationError(
                    f"SUCCESSOR_SPLIT_SOURCE_DISAGREEMENT:{symbol}:{rehab['date'].isoformat()}"
                )
        else:
            matches = [
                item
                for item in undated_endpoint
                if not item["used"]
                and _same_multiplier(
                    item["unit_multiplier"], rehab["unit_multiplier"]
                )
            ]
            if len(matches) != 1:
                reason = "MISSING" if not matches else "AMBIGUOUS"
                raise CorporateActionNormalizationError(
                    f"SUCCESSOR_SPLIT_UNDATED_ENDPOINT_{reason}:{symbol}:{rehab['date'].isoformat()}"
                )
            candidate = matches[0]

        candidate["used"] = True
        normalized.append(
            NormalizedSplit(
                symbol=symbol,
                effective_date=rehab["date"],
                unit_multiplier=rehab["unit_multiplier"],
                rehab_adjustment_ratio=rehab["adjustment_ratio"],
                endpoint_rate=candidate["rate"],
                endpoint_dated=candidate["date"] is not None,
                rehab_record_sha256=rehab["sha256"],
                endpoint_record_sha256=candidate["sha256"],
            )
        )

    unmatched_dated = [item for item in dated_endpoint if not item["used"]]
    if unmatched_dated:
        item = min(unmatched_dated, key=lambda value: value["date"])
        raise CorporateActionNormalizationError(
            f"SUCCESSOR_SPLIT_ENDPOINT_WITHOUT_REHAB:{symbol}:{item['date'].isoformat()}"
        )

    ignored_undated = sum(1 for item in undated_endpoint if not item["used"])
    return SplitNormalizationResult(
        schema_version=NORMALIZATION_SCHEMA,
        status=NORMALIZATION_STATUS,
        symbol=symbol,
        events=tuple(sorted(normalized, key=lambda item: item.effective_date)),
        ignored_dated_endpoint_outside_window=ignored_dated_outside,
        ignored_undated_endpoint_records=ignored_undated,
        ignored_rehab_outside_window=ignored_rehab_outside,
    )
