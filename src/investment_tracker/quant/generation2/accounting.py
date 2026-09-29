"""Decision-grade research accounting on unadjusted execution prices.

This is the Generation-2 decision ledger, versioned
``UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1``. It models a long-only
cash-constrained portfolio that:

* executes target weights at the *unadjusted* next-session open (no same-bar);
* tracks cash, shares, pending orders, fills and friction;
* applies splits / reverse-splits to the share count;
* models dividends as receivables created at the ex-date and credited to cash
  at the authoritative pay date;
* records total equity at each session close.

Research comparability normally uses front-adjusted prices, but a
*decision-grade* ledger must reflect the unadjusted execution prices that
cash actually saw. The ledger is fail-closed: any invariant breach raises a
ValueError so a downstream consumer can report UNKNOWN / ABSTAIN rather than
trust a contaminated equity series.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import pandas as pd

DECISION_ACCOUNTING_SCHEMA = "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1"

__all__ = [
    "DECISION_ACCOUNTING_SCHEMA",
    "DecisionError",
    "DecisionFill",
    "DecisionReplayResult",
    "DecisionState",
    "DecisionTarget",
    "DividendEvent",
    "SplitEvent",
    "replay_decision_targets",
]


class DecisionError(ValueError):
    """Raised when a decision-ledger invariant is breached."""


@dataclass(frozen=True)
class SplitEvent:
    symbol: str
    effective_date: pd.Timestamp
    unit_multiplier: float  # >0; <1 is a reverse split
    source_identity: str


@dataclass(frozen=True)
class DividendEvent:
    symbol: str
    ex_date: pd.Timestamp
    pay_date: pd.Timestamp
    amount_per_unit: float
    source_identity: str


@dataclass(frozen=True)
class DecisionTarget:
    """A decided target, executed at the next session open.

    ``signal_session`` is the session at which the decision is made and must
    strictly precede ``due_session`` (the execution session).
    """

    target_id: str
    signal_session: pd.Timestamp
    due_session: pd.Timestamp
    weights: dict[str, float]


@dataclass(frozen=True)
class DecisionFill:
    symbol: str
    source_target_id: str
    fill_session: pd.Timestamp
    unadjusted_open: float
    units_delta: float
    notional: float
    friction: float


@dataclass(frozen=True)
class DecisionState:
    session: pd.Timestamp
    cash: float
    receivable: float
    close_equity: float
    realized_gross_exposure: float
    units: tuple[tuple[str, float], ...]
    pending_orders: tuple[str, ...]


@dataclass(frozen=True)
class DecisionReplayResult:
    schema_version: str
    friction_bps: int
    initial_cash: float
    sessions: tuple[pd.Timestamp, ...]
    states: tuple[DecisionState, ...]
    fills: tuple[DecisionFill, ...]
    total_turnover: float

    @property
    def close_equity(self) -> tuple[float, ...]:
        return tuple(item.close_equity for item in self.states)

    @property
    def daily_returns(self) -> tuple[float, ...]:
        equity = self.close_equity
        return tuple(equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity)))


@dataclass
class _Receivable:
    symbol: str
    pay_date: pd.Timestamp
    amount: float
    source_identity: str


def _validate_target(target: DecisionTarget) -> None:
    if target.signal_session >= target.due_session:
        raise DecisionError("DECISION_NONCAUSAL_TARGET")
    if any(weight < 0.0 or not math.isfinite(weight) for weight in target.weights.values()):
        raise DecisionError("DECISION_TARGET_WEIGHT_INVALID")
    if sum(target.weights.values()) > 1.0 + 1e-12:
        raise DecisionError("DECISION_GROSS_WEIGHT_INVALID")


def _subset_actions(
    splits: Sequence[SplitEvent], dividends: Sequence[DividendEvent]
) -> tuple[dict[pd.Timestamp, list[SplitEvent]], dict[pd.Timestamp, list[DividendEvent]]]:
    split_by_date: dict[pd.Timestamp, list[SplitEvent]] = {}
    div_by_ex: dict[pd.Timestamp, list[DividendEvent]] = {}
    for event in splits:
        split_by_date.setdefault(event.effective_date, []).append(event)
    for event in dividends:
        div_by_ex.setdefault(event.ex_date, []).append(event)
    return split_by_date, div_by_ex


def replay_decision_targets(
    bars: dict[str, pd.DataFrame],
    targets: Sequence[DecisionTarget],
    splits: Sequence[SplitEvent] = (),
    dividends: Sequence[DividendEvent] = (),
    *,
    friction_bps: int = 0,
    initial_cash: float = 100_000.0,
    symbols: Sequence[str] | None = None,
) -> DecisionReplayResult:
    if not targets:
        raise DecisionError("DECISION_TARGET_SEQUENCE_EMPTY")
    for target in targets:
        _validate_target(target)
    active_symbols = tuple(symbols if symbols is not None else bars.keys())
    unknown = {symbol for target in targets for symbol in target.weights if symbol not in active_symbols}
    if unknown:
        raise DecisionError("DECISION_TARGET_SYMBOL_OUTSIDE_REPLAY")

    # Use the intersection of available sessions (all active symbols must be present).
    session_sets = [set(bars[symbol].index) for symbol in active_symbols]
    common = pd.DatetimeIndex(sorted(set.intersection(*session_sets)))
    if len(common) < 2:
        raise DecisionError("DECISION_SESSIONS_INSUFFICIENT")

    first = targets[0].due_session
    last = common[-1]
    sessions = tuple(common[(common >= first) & (common <= last)])
    if len(sessions) < 2 or sessions[0] != first:
        raise DecisionError("DECISION_REPLAY_SESSION_BOUNDARY_INVALID")
    due_map = {item.due_session: item for item in targets}
    if len(due_map) != len(targets):
        raise DecisionError("DECISION_DUPLICATE_DUE_TARGET")

    split_by_date, div_by_ex = _subset_actions(splits, dividends)
    holdings = {symbol: 0.0 for symbol in active_symbols}
    cash = float(initial_cash)
    receivables: list[_Receivable] = []
    friction_rate = float(friction_bps) / 10_000.0
    fills: list[DecisionFill] = []
    states: list[DecisionState] = []
    total_turnover = 0.0

    for session in sessions:
        # Settle receivables whose pay date has arrived (cash credit at pay date).
        unsettled: list[_Receivable] = []
        for item in receivables:
            if item.pay_date <= session:
                cash += item.amount
            else:
                unsettled.append(item)
        receivables = unsettled

        div_events = div_by_ex.get(session, [])
        split_events = split_by_date.get(session, [])
        if {event.symbol for event in div_events} & {event.symbol for event in split_events}:
            raise DecisionError("DECISION_SAME_SESSION_DIVIDEND_SPLIT_AMBIGUOUS")

        # Dividends: entitlement = shares held at the close before ex-date.
        for event in div_events:
            entitlement = holdings[event.symbol] * event.amount_per_unit
            if entitlement < 0.0 or not math.isfinite(entitlement):
                raise DecisionError("DECISION_DIVIDEND_ENTITLEMENT_INVALID")
            if entitlement > 0.0:
                receivables.append(_Receivable(event.symbol, event.pay_date, entitlement, event.source_identity))

        # Splits / reverse-splits scale the share count; cash is unchanged.
        for event in split_events:
            if event.unit_multiplier <= 0.0 or not math.isfinite(event.unit_multiplier):
                raise DecisionError("DECISION_SPLIT_MULTIPLIER_INVALID")
            holdings[event.symbol] *= event.unit_multiplier

        open_prices = {symbol: float(bars[symbol].loc[session, "open"]) for symbol in active_symbols}
        receivable_total = sum(item.amount for item in receivables)
        open_equity = cash + receivable_total + sum(
            holdings[s] * open_prices[s] for s in active_symbols
        )
        if not math.isfinite(open_equity) or open_equity <= 0.0:
            raise DecisionError("DECISION_OPEN_EQUITY_INVALID")

        target = due_map.get(session)
        pending_orders: tuple[str, ...] = (target.target_id,) if target is not None else ()
        if target is not None:
            weights = dict(target.weights)
            desired = {s: float(weights.get(s, 0.0)) * open_equity for s in active_symbols}
            current = {s: holdings[s] * open_prices[s] for s in active_symbols}
            delta = {s: desired[s] - current[s] for s in active_symbols}
            # Sells first (realize, add cash).
            for symbol in active_symbols:
                if delta[symbol] >= -1e-10:
                    continue
                price = open_prices[symbol]
                target_units = desired[symbol] / price
                units_delta = target_units - holdings[symbol]
                notional = units_delta * price
                fee = abs(notional) * friction_rate
                holdings[symbol] = target_units
                cash += -notional - fee
                total_turnover += abs(notional)
                fills.append(
                    DecisionFill(symbol, target.target_id, session, price, units_delta, notional, fee)
                )
            # Buys, scaled to available cash so long-only cash never goes negative.
            buy_symbols = [symbol for symbol in active_symbols if delta[symbol] > 1e-10]
            total_buy = sum(delta[symbol] for symbol in buy_symbols)
            scale = 1.0
            if total_buy > 0.0 and total_buy * (1.0 + friction_rate) > cash:
                scale = max(0.0, cash / (total_buy * (1.0 + friction_rate)))
            for symbol in buy_symbols:
                price = open_prices[symbol]
                notional = delta[symbol] * scale
                if notional <= 0.0:
                    continue
                fee = notional * friction_rate
                units_delta = notional / price
                holdings[symbol] += units_delta
                cash -= notional + fee
                total_turnover += notional
                fills.append(
                    DecisionFill(symbol, target.target_id, session, price, units_delta, notional, fee)
                )

        if -1e-8 <= cash < 0.0:
            cash = 0.0
        if cash < 0.0 or any(value < -1e-12 or not math.isfinite(value) for value in holdings.values()):
            raise DecisionError("DECISION_LONG_ONLY_ACCOUNTING_BREACH")

        close_prices = {symbol: float(bars[symbol].loc[session, "close"]) for symbol in active_symbols}
        receivable_total = sum(item.amount for item in receivables)
        risky_value = sum(holdings[s] * close_prices[s] for s in active_symbols)
        close_equity = cash + receivable_total + risky_value
        if not math.isfinite(close_equity) or close_equity <= 0.0:
            raise DecisionError("DECISION_CLOSE_EQUITY_INVALID")
        exposure = risky_value / close_equity
        if not 0.0 <= exposure <= 1.0 + 1e-12:
            raise DecisionError("DECISION_GROSS_EXPOSURE_BREACH")

        states.append(
            DecisionState(
                session,
                float(cash),
                float(receivable_total),
                float(close_equity),
                float(exposure),
                tuple((s, float(holdings[s])) for s in active_symbols if holdings[s] > 0.0),
                pending_orders,
            )
        )

    return DecisionReplayResult(
        DECISION_ACCOUNTING_SCHEMA,
        int(friction_bps),
        float(initial_cash),
        sessions,
        tuple(states),
        tuple(fills),
        float(total_turnover),
    )
