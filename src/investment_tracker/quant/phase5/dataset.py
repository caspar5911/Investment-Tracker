from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd

from .methodology import ACQUISITION_CUTOFF, SYMBOLS, assert_requested_symbols


@dataclass(frozen=True)
class RehabEvent:
    symbol: str
    ex_date: pd.Timestamp
    forward_a: float
    forward_b: float
    cash_dividend: float
    split_multiplier: float | None


@dataclass(frozen=True)
class DividendEvent:
    symbol: str
    ex_date: pd.Timestamp
    pay_date: pd.Timestamp
    amount_per_unit: float
    currency: str


@dataclass(frozen=True)
class DividendCoverageGap:
    symbol: str
    ex_date: pd.Timestamp
    reason: str


@dataclass(frozen=True)
class SplitEvent:
    symbol: str
    effective_date: pd.Timestamp
    unit_multiplier: float


@dataclass(frozen=True)
class CorporateActionBook:
    rehab: dict[str, tuple[RehabEvent, ...]]
    dividends: dict[str, tuple[DividendEvent, ...]]
    splits: dict[str, tuple[SplitEvent, ...]]


@dataclass(frozen=True)
class Phase5Dataset:
    bars: dict[str, pd.DataFrame]
    common_sessions: tuple[pd.Timestamp, ...]
    actions: CorporateActionBook
    provider_manifest_sha256: str
    first_common_session: str
    last_common_session: str
    common_history_years: float
    signal_sessions: tuple[pd.Timestamp, ...] | None = None
    dividend_coverage_gaps: tuple[DividendCoverageGap, ...] = ()
    latest_unsupported_dividend_ex_date: str | None = None


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _timestamp(value: object, *, field: str) -> pd.Timestamp:
    text = " ".join(str(value).strip().split())
    if not text or text.lower() in {"nan", "none"}:
        raise ValueError(f"PHASE5_DATE_MISSING:{field}")

    iso = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:$|[ T])", text)
    if iso:
        year, month, day = (int(part) for part in iso.groups())
    else:
        named = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})(?:$|\s)", text)
        if not named:
            raise ValueError(f"PHASE5_DATE_INVALID:{field}")
        month_name, day_text, year_text = named.groups()
        month = _MONTHS.get(month_name.lower())
        if month is None:
            raise ValueError(f"PHASE5_DATE_INVALID:{field}")
        year, day = int(year_text), int(day_text)

    try:
        return pd.Timestamp(f"{year:04d}-{month:02d}-{day:02d}", tz="UTC")
    except ValueError as exc:
        raise ValueError(f"PHASE5_DATE_INVALID:{field}") from exc


def _number(row: pd.Series, name: str, default: float = 0.0) -> float:
    if name not in row or pd.isna(row[name]) or str(row[name]).strip() == "":
        return default
    value = float(row[name])
    if not math.isfinite(value):
        raise ValueError(f"PHASE5_REHAB_NONFINITE:{name}")
    return value


def _validate_manifest(root: Path) -> dict[str, object]:
    path = root / "manifest.json"
    if not path.is_file():
        raise ValueError("PHASE5_PROVIDER_MANIFEST_MISSING")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("PHASE5_PROVIDER_MANIFEST_INVALID") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "PHASE5-OPEND-PROVIDER-EXPORT-v1"
        or manifest.get("provider") != "MOOMOO_OPEND"
        or manifest.get("bar_autype") != "NONE"
        or manifest.get("bar_type") != "K_DAY"
        or manifest.get("extended_time") is not False
        or manifest.get("trading_context_created") is not False
        or manifest.get("protected_symbols_accessed") != []
        or manifest.get("final_holdout_accessed") is not False
    ):
        raise ValueError("PHASE5_PROVIDER_MANIFEST_GOVERNANCE_MISMATCH")
    assert_requested_symbols(tuple(manifest.get("symbols", ())))
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != len(SYMBOLS) * 4:
        raise ValueError("PHASE5_PROVIDER_FILESET_MISMATCH")
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("PHASE5_PROVIDER_FILESET_MISMATCH")
        rel, expected = item.get("path"), item.get("sha256")
        if not isinstance(rel, str) or not isinstance(expected, str):
            raise ValueError("PHASE5_PROVIDER_FILESET_MISMATCH")
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("PHASE5_PROVIDER_PATH_ESCAPE") from exc
        if not candidate.is_file() or _hash(candidate) != expected:
            raise ValueError("PHASE5_PROVIDER_FILE_IDENTITY_MISMATCH")
    return manifest


def _bars(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"time_key", "open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"PHASE5_BAR_SCHEMA_MISMATCH:{path.name}")
    sessions = pd.to_datetime(frame["time_key"].astype(str).str.slice(0, 10), errors="raise", utc=True)
    if sessions.duplicated().any():
        raise ValueError(f"PHASE5_DUPLICATE_BAR:{path.name}")
    result = pd.DataFrame(index=pd.DatetimeIndex(sessions))
    for name in ("open", "high", "low", "close"):
        result[name] = pd.to_numeric(frame[name], errors="raise").to_numpy(dtype=float)
    result["volume"] = (
        pd.to_numeric(frame["volume"], errors="coerce").to_numpy(dtype=float)
        if "volume" in frame else np.nan
    )
    values = result[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if result.empty or not result.index.is_unique or not result.index.is_monotonic_increasing or not np.isfinite(values).all() or (values <= 0.0).any():
        raise ValueError(f"PHASE5_BAR_VALUES_INVALID:{path.name}")
    if (result["low"] > result[["open", "close"]].min(axis=1)).any() or (result["high"] < result[["open", "close"]].max(axis=1)).any() or (result["low"] > result["high"]).any():
        raise ValueError(f"PHASE5_OHLC_INVARIANT_FAILURE:{path.name}")
    valid_volume = result["volume"].dropna()
    if (valid_volume < 0).any() or (not valid_volume.empty and not np.isfinite(valid_volume).all()):
        raise ValueError(f"PHASE5_VOLUME_INVALID:{path.name}")
    cutoff = pd.Timestamp(ACQUISITION_CUTOFF, tz="UTC")
    return result.loc[result.index <= cutoff].copy()


_UNSUPPORTED_REHAB_FIELDS = (
    "per_share_div_ratio", "per_share_trans_ratio", "allotment_ratio", "allotment_price",
    "stk_spo_ratio", "stk_spo_price", "spin_off_ratio",
)


def _rehab(path: Path, symbol: str) -> tuple[RehabEvent, ...]:
    frame = pd.read_csv(path)
    if frame.empty:
        return ()
    if "ex_div_date" not in frame.columns:
        raise ValueError(f"PHASE5_REHAB_SCHEMA_MISMATCH:{symbol}")
    events: list[RehabEvent] = []
    for _, row in frame.iterrows():
        for field in _UNSUPPORTED_REHAB_FIELDS:
            if _number(row, field) != 0.0:
                raise ValueError(f"PHASE5_UNSUPPORTED_CORPORATE_ACTION:{symbol}:{field}")
        ex_date = _timestamp(row["ex_div_date"], field="ex_div_date")
        a = _number(row, "forward_adj_factorA", 1.0)
        b = _number(row, "forward_adj_factorB", 0.0)
        if a <= 0.0:
            raise ValueError(f"PHASE5_FORWARD_FACTOR_INVALID:{symbol}")
        cash = _number(row, "per_cash_div", 0.0)
        if cash < 0.0:
            raise ValueError(f"PHASE5_DIVIDEND_AMOUNT_INVALID:{symbol}")
        split_base, split_ert = _number(row, "split_base"), _number(row, "split_ert")
        join_base, join_ert = _number(row, "join_base"), _number(row, "join_ert")
        split_multiplier: float | None = None
        split_present = split_base != 0.0 or split_ert != 0.0
        join_present = join_base != 0.0 or join_ert != 0.0
        if split_present and join_present:
            raise ValueError(f"PHASE5_MULTIPLE_SPLIT_TYPES_SAME_EVENT:{symbol}")
        if split_present:
            if split_base <= 0.0 or split_ert <= 0.0:
                raise ValueError(f"PHASE5_SPLIT_RATIO_INVALID:{symbol}")
            split_multiplier = split_ert / split_base
        if join_present:
            if join_base <= 0.0 or join_ert <= 0.0:
                raise ValueError(f"PHASE5_JOIN_RATIO_INVALID:{symbol}")
            split_multiplier = join_ert / join_base
        if cash > 0.0 and split_multiplier is not None:
            raise ValueError(f"PHASE5_SAME_DATE_DIVIDEND_SPLIT_AMBIGUOUS:{symbol}")
        events.append(RehabEvent(symbol, ex_date, a, b, cash, split_multiplier))
    events.sort(key=lambda item: item.ex_date)
    if len({item.ex_date for item in events}) != len(events):
        raise ValueError(f"PHASE5_DUPLICATE_REHAB_DATE:{symbol}")
    return tuple(events)


def _load_json_response(path: Path, symbol: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("symbol") != symbol:
        raise ValueError(f"PHASE5_CORPORATE_ACTION_EXPORT_INVALID:{symbol}")
    response = value.get("response")
    if not isinstance(response, dict):
        raise ValueError(f"PHASE5_CORPORATE_ACTION_EXPORT_INVALID:{symbol}")
    return response


def _currency(statement: object) -> str:
    text = str(statement or "").upper()
    if "USD" in text or "US$" in text:
        return "USD"
    match = re.search(r"(?<![A-Z])[A-Z]{3}(?![A-Z])", text)
    if match:
        return match.group(0)
    raise ValueError("PHASE5_DIVIDEND_CURRENCY_UNKNOWN")


def _dividends(
    symbol: str,
    rehab: tuple[RehabEvent, ...],
    response: dict[str, object],
) -> tuple[tuple[DividendEvent, ...], tuple[DividendCoverageGap, ...]]:
    records = response.get("dividend_list", [])
    if not isinstance(records, list):
        raise ValueError(f"PHASE5_DIVIDEND_HISTORY_INVALID:{symbol}")
    by_ex: dict[pd.Timestamp, list[dict[str, object]]] = {}
    for raw in records:
        if not isinstance(raw, dict) or not raw.get("ex_date"):
            continue
        by_ex.setdefault(_timestamp(raw["ex_date"], field="dividend_ex_date"), []).append(raw)

    result: list[DividendEvent] = []
    gaps: list[DividendCoverageGap] = []
    for item in rehab:
        if item.cash_dividend <= 0.0:
            continue
        matches = by_ex.get(item.ex_date, [])
        if not matches:
            gaps.append(DividendCoverageGap(symbol, item.ex_date, "DIVIDEND_DETAIL_MISSING"))
            continue
        if len(matches) > 1:
            raise ValueError(f"PHASE5_DIVIDEND_PAYDATE_AMBIGUOUS:{symbol}:{item.ex_date.date()}")

        raw = matches[0]
        pay_value = raw.get("dividend_payable_date")
        if pay_value is None or str(pay_value).strip().lower() in {"", "nan", "none"}:
            gaps.append(DividendCoverageGap(symbol, item.ex_date, "DIVIDEND_PAYDATE_MISSING"))
            continue
        pay_date = _timestamp(pay_value, field="dividend_payable_date")
        if pay_date < item.ex_date:
            raise ValueError(f"PHASE5_DIVIDEND_PAYDATE_INVALID:{symbol}")
        currency = _currency(raw.get("statement"))
        if currency != "USD":
            raise ValueError(f"PHASE5_DIVIDEND_CURRENCY_NOT_USD:{symbol}:{currency}")
        result.append(DividendEvent(symbol, item.ex_date, pay_date, item.cash_dividend, currency))
    return tuple(result), tuple(gaps)


def _first_defensible_accounting_session(
    common_sessions: pd.DatetimeIndex,
    gaps: tuple[DividendCoverageGap, ...],
) -> pd.Timestamp:
    if common_sessions.empty:
        raise ValueError("PHASE5_COMMON_HISTORY_EMPTY")
    if not gaps:
        return pd.Timestamp(common_sessions[0])
    latest_gap = max(item.ex_date for item in gaps)
    eligible = common_sessions[common_sessions > latest_gap]
    if eligible.empty:
        raise ValueError("PHASE5_ACCOUNTING_BOUNDARY_EMPTY")
    return pd.Timestamp(eligible[0])


def load_opend_dataset(root: Path) -> Phase5Dataset:
    repository = Path(root).resolve()
    _validate_manifest(repository)
    bars = {symbol: _bars(repository / "bars" / f"{symbol}.csv") for symbol in SYMBOLS}
    rehab = {symbol: _rehab(repository / "rehab" / f"{symbol}.csv", symbol) for symbol in SYMBOLS}
    dividends: dict[str, tuple[DividendEvent, ...]] = {}
    gaps: list[DividendCoverageGap] = []
    splits: dict[str, tuple[SplitEvent, ...]] = {}
    for symbol in SYMBOLS:
        div_response = _load_json_response(repository / "dividends" / f"{symbol}.json", symbol)
        normalized_dividends, symbol_gaps = _dividends(symbol, rehab[symbol], div_response)
        dividends[symbol] = normalized_dividends
        gaps.extend(symbol_gaps)
        _load_json_response(repository / "splits" / f"{symbol}.json", symbol)
        splits[symbol] = tuple(
            SplitEvent(symbol, event.ex_date, event.split_multiplier)
            for event in rehab[symbol] if event.split_multiplier is not None
        )

    signal_common = bars[SYMBOLS[0]].index
    for symbol in SYMBOLS[1:]:
        signal_common = signal_common.intersection(bars[symbol].index)
    signal_common = signal_common.sort_values()
    if len(signal_common) < 2:
        raise ValueError("PHASE5_COMMON_HISTORY_EMPTY")
    for symbol in SYMBOLS:
        bars[symbol] = bars[symbol].loc[signal_common].copy()

    ordered_gaps = tuple(sorted(gaps, key=lambda item: (item.ex_date, item.symbol, item.reason)))
    accounting_start = _first_defensible_accounting_session(signal_common, ordered_gaps)
    accounting_common = signal_common[signal_common >= accounting_start]
    if len(accounting_common) < 2:
        raise ValueError("PHASE5_ACCOUNTING_HISTORY_EMPTY")
    years = (accounting_common[-1] - accounting_common[0]).total_seconds() / 86400.0 / 365.25
    latest_gap = max((item.ex_date for item in ordered_gaps), default=None)
    return Phase5Dataset(
        bars=bars,
        common_sessions=tuple(accounting_common),
        actions=CorporateActionBook(rehab=rehab, dividends=dividends, splits=splits),
        provider_manifest_sha256=_hash(repository / "manifest.json"),
        first_common_session=accounting_common[0].strftime("%Y-%m-%d"),
        last_common_session=accounting_common[-1].strftime("%Y-%m-%d"),
        common_history_years=float(years),
        signal_sessions=tuple(signal_common),
        dividend_coverage_gaps=ordered_gaps,
        latest_unsupported_dividend_ex_date=(
            None if latest_gap is None else latest_gap.strftime("%Y-%m-%d")
        ),
    )


def raw_close_frame(dataset: Phase5Dataset) -> pd.DataFrame:
    sessions = dataset.signal_sessions or dataset.common_sessions
    return pd.DataFrame(
        {symbol: dataset.bars[symbol]["close"] for symbol in SYMBOLS},
        index=pd.DatetimeIndex(sessions),
    )
