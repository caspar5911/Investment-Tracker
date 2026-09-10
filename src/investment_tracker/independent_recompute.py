"""Independent, low-level recomputation used to audit canonical replay evidence.

This module deliberately does not import the primary replay, outcome, or baseline
implementations.  Keeping the arithmetic here explicit makes agreement useful as
an implementation-diversity check rather than merely running the same code twice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Mapping

from .governance import PHASE_A_END, PHASE_B_END, assert_symbol_allowed

HORIZONS = (1, 5, 20, 60, 120, 250)
FRICTIONS_BPS = (0, 10, 25)


@dataclass(frozen=True)
class AuditBar:
    asset: str
    bar_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    range_usable: bool = True


@dataclass(frozen=True)
class IndependentReplayRow:
    asset: str
    bar_date: date
    sma200: Decimal | None
    prior60_high: Decimal | None
    sma5: Decimal | None
    ret20: Decimal | None
    spy_ret20: Decimal | None
    signal_state: str
    episode_start: bool


@dataclass(frozen=True)
class IndependentOutcome:
    signal_date: date
    entry_date: date
    horizon_td: int
    friction_bps: int
    asset_return: Decimal | None
    spy_return: Decimal | None
    excess_spy: Decimal | None
    cash_return: Decimal | None
    excess_cash: Decimal | None
    return_net: Decimal | None
    mae: Decimal | None
    mfe: Decimal | None
    censored: bool


@dataclass(frozen=True)
class ComparisonMismatch:
    section: str
    identity: str
    field: str
    canonical: Any
    recomputed: Any


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values))


def recompute_replay(asset_bars: Iterable[AuditBar], spy_bars: Iterable[AuditBar]) -> list[IndependentReplayRow]:
    """Recompute frozen price-only replay from normalized bars.

    SMA200 is inclusive: ``close[t-199]`` through ``close[t]``.  Prior-high is
    intentionally exclusive of day t. Inputs must have exactly matching dates.
    """
    raw_bars = list(asset_bars)
    raw_spy = list(spy_bars)
    # Authorization is checked before sorting or calculating any supplied data.
    for symbol in {b.asset for b in raw_bars + raw_spy}:
        assert_symbol_allowed(symbol)
    bars = sorted(raw_bars, key=lambda b: b.bar_date)
    spy = sorted(raw_spy, key=lambda b: b.bar_date)
    if not bars:
        return []
    if any(b.asset != bars[0].asset for b in bars):
        raise ValueError("asset bars contain more than one symbol")
    dates = [b.bar_date for b in bars]
    if len(dates) != len(set(dates)):
        raise ValueError("duplicate asset session")
    if dates != [b.bar_date for b in spy]:
        raise ValueError("benchmark dates must exactly match asset dates")

    closes = [b.close for b in bars]
    spy_closes = [b.close for b in spy]
    output: list[IndependentReplayRow] = []
    previous_state: str | None = None
    for i, bar in enumerate(bars):
        sma200 = _mean(closes[i - 199 : i + 1]) if i >= 199 else None
        prior_high = max(b.close for b in bars[i - 60 : i]) if i >= 60 else None
        sma5 = _mean(closes[i - 4 : i + 1]) if i >= 4 else None
        ret20 = closes[i] / closes[i - 20] - 1 if i >= 20 else None
        spy_ret20 = spy_closes[i] / spy_closes[i - 20] - 1 if i >= 20 else None

        if None in (sma200, prior_high, sma5, ret20, spy_ret20) or i == 0:
            state = "ABSTAIN"
        else:
            trend = bar.close > sma200
            pullback = Decimal("0.85") * prior_high <= bar.close <= Decimal("0.95") * prior_high
            stabilize = bar.close > closes[i - 1] and bar.close >= sma5
            relative = ret20 >= spy_ret20 - Decimal("0.05")
            chase = not (bar.close >= Decimal("0.98") * prior_high and ret20 >= Decimal("0.08"))
            if not trend and ret20 < Decimal("-0.10"):
                state = "TRIM/AVOID"
            elif not trend or not chase:
                state = "WAIT"
            elif not (pullback and stabilize and relative):
                state = "WATCH"
            else:
                state = "ACCUMULATE"
        start = state == "ACCUMULATE" and previous_state != "ACCUMULATE"
        output.append(IndependentReplayRow(bar.asset, bar.bar_date, sma200, prior_high, sma5, ret20, spy_ret20, state, start))
        previous_state = state
    return output


def recompute_outcomes(
    rows: Iterable[IndependentReplayRow],
    asset_bars: Iterable[AuditBar],
    spy_bars: Iterable[AuditBar],
    phase: str = "PHASE_A",
) -> list[IndependentOutcome]:
    """Independently apply t+1-open execution, horizons, C24 and quarantine."""
    replay_rows = list(rows)
    bars = sorted(asset_bars, key=lambda b: b.bar_date)
    spy = sorted(spy_bars, key=lambda b: b.bar_date)
    if [b.bar_date for b in bars] != [b.bar_date for b in spy]:
        raise ValueError("benchmark dates must exactly match asset dates")
    index = {b.bar_date: i for i, b in enumerate(bars)}
    boundary = PHASE_A_END if phase.upper() == "PHASE_A" else PHASE_B_END if phase.upper() == "PHASE_B" else None
    if boundary is None:
        raise ValueError("phase must be PHASE_A or PHASE_B")
    output: list[IndependentOutcome] = []
    for signal in (r for r in replay_rows if r.episode_start):
        signal_i = index[signal.bar_date]
        entry_i = signal_i + 1
        if entry_i >= len(bars):
            continue
        for horizon in HORIZONS:
            horizon_i = entry_i + horizon - 1
            unavailable = horizon_i >= len(bars) or bars[horizon_i].bar_date > boundary
            for friction in FRICTIONS_BPS:
                if unavailable:
                    output.append(IndependentOutcome(signal.bar_date, bars[entry_i].bar_date, horizon, friction, None, None, None, None, None, None, None, None, True))
                    continue
                entry, terminal = bars[entry_i], bars[horizon_i]
                spy_entry, spy_terminal = spy[entry_i], spy[horizon_i]
                gross = terminal.close / entry.open - 1
                spy_return = spy_terminal.close / spy_entry.open - 1
                elapsed = Decimal((terminal.bar_date - entry.bar_date).days) / Decimal(365)
                cash = Decimal(str(float(Decimal("1.0325")) ** float(elapsed) - 1))
                path = bars[entry_i : horizon_i + 1]
                range_ok = all(b.range_usable for b in path)
                mae = min(b.low / entry.open - 1 for b in path) if range_ok else None
                mfe = max(b.high / entry.open - 1 for b in path) if range_ok else None
                output.append(IndependentOutcome(signal.bar_date, entry.bar_date, horizon, friction, gross, spy_return, gross - spy_return, cash, gross - cash, gross - Decimal(friction) / Decimal(10_000), mae, mfe, False))
    return output


def recompute_baseline_entries(bars: Iterable[AuditBar]) -> dict[str, list[date]]:
    """Independently identify C17/C18/C19 entry sessions (all t+1 where signalled)."""
    ordered = sorted(bars, key=lambda b: b.bar_date)
    if not ordered:
        return {"C17_BUY_AND_HOLD": [], "C18_MONTHLY_DCA": [], "C19_SIMPLE_DIP": []}
    c17 = [ordered[0].bar_date]
    c18: list[date] = []
    seen_months: set[tuple[int, int]] = set()
    c19: list[date] = []
    previously_qualified = False
    for i, bar in enumerate(ordered):
        month = (bar.bar_date.year, bar.bar_date.month)
        if month not in seen_months:
            c18.append(bar.bar_date)
            seen_months.add(month)
        qualifying = i >= 60 and bar.close <= Decimal("0.90") * max(b.close for b in ordered[i - 60 : i])
        if qualifying and not previously_qualified and i + 1 < len(ordered):
            c19.append(ordered[i + 1].bar_date)
        previously_qualified = qualifying
    return {"C17_BUY_AND_HOLD": c17, "C18_MONTHLY_DCA": c18, "C19_SIMPLE_DIP": c19}


def compare_records(section: str, canonical: Iterable[Mapping[str, Any]], recomputed: Iterable[Any], identity_fields: tuple[str, ...]) -> list[ComparisonMismatch]:
    """Compare independently computed records with canonical records, fail-closed."""
    def normalize(row: Any) -> dict[str, Any]:
        return asdict(row) if hasattr(row, "__dataclass_fields__") else dict(row)

    def key(row: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(str(row.get(field)) for field in identity_fields)

    left = {key(r): r for r in map(normalize, canonical)}
    right = {key(r): r for r in map(normalize, recomputed)}
    mismatches: list[ComparisonMismatch] = []
    for record_key in sorted(set(left) | set(right)):
        identity = "|".join(record_key)
        if record_key not in left or record_key not in right:
            mismatches.append(ComparisonMismatch(section, identity, "__record__", left.get(record_key), right.get(record_key)))
            continue
        for field in sorted(set(left[record_key]) | set(right[record_key])):
            if left[record_key].get(field) != right[record_key].get(field):
                mismatches.append(ComparisonMismatch(section, identity, field, left[record_key].get(field), right[record_key].get(field)))
    return mismatches
