from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from .dataset import CorporateActionBook, DividendEvent, Phase5Dataset, SplitEvent
from .signals import TargetDecision


@dataclass(frozen=True)
class Fill:
    symbol: str
    signal_session: pd.Timestamp
    fill_session: pd.Timestamp
    reference_open: float
    units_delta: float
    fill_notional: float
    friction: float


@dataclass(frozen=True)
class LedgerState:
    session: pd.Timestamp
    cash: float
    receivable: float
    close_equity: float
    realized_gross_exposure: float
    target_gross_exposure: float
    units: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class ReplayResult:
    friction_bps: int
    initial_cash: float
    sessions: tuple[pd.Timestamp, ...]
    states: tuple[LedgerState, ...]
    fills: tuple[Fill, ...]
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


def _subset_actions(actions: CorporateActionBook, symbols: tuple[str, ...]) -> tuple[dict[pd.Timestamp, list[DividendEvent]], dict[pd.Timestamp, list[SplitEvent]]]:
    divs: dict[pd.Timestamp, list[DividendEvent]] = {}
    splits: dict[pd.Timestamp, list[SplitEvent]] = {}
    for symbol in symbols:
        for event in actions.dividends[symbol]:
            divs.setdefault(event.ex_date, []).append(event)
        for event in actions.splits[symbol]:
            splits.setdefault(event.effective_date, []).append(event)
    return divs, splits


def replay_targets(
    dataset: Phase5Dataset,
    targets: tuple[TargetDecision, ...],
    *,
    friction_bps: int,
    initial_cash: float = 100000.0,
    symbols: tuple[str, ...] | None = None,
    start_session: pd.Timestamp | None = None,
    end_session: pd.Timestamp | None = None,
) -> ReplayResult:
    if not targets:
        raise ValueError("PHASE5_TARGET_SEQUENCE_EMPTY")
    active_symbols = tuple(symbols or dataset.bars.keys())
    common = pd.DatetimeIndex(dataset.common_sessions)
    first = start_session or targets[0].signal_session
    last = end_session or common[-1]
    sessions = tuple(common[(common >= first) & (common <= last)])
    if len(sessions) < 2 or sessions[0] != first:
        raise ValueError("PHASE5_REPLAY_SESSION_BOUNDARY_INVALID")
    due_map = {item.due_session: item for item in targets if item.due_session is not None}
    signal_map = {item.signal_session: item for item in targets}
    if len(due_map) != sum(item.due_session is not None for item in targets):
        raise ValueError("PHASE5_DUPLICATE_DUE_TARGET")
    dividend_by_ex, split_by_date = _subset_actions(dataset.actions, active_symbols)
    holdings = {symbol: 0.0 for symbol in active_symbols}
    cash = float(initial_cash)
    receivables: list[_Receivable] = []
    friction_rate = float(friction_bps) / 10000.0
    fills: list[Fill] = []
    states: list[LedgerState] = []
    total_turnover = 0.0
    last_target_gross = 0.0

    for session in sessions:
        unsettled: list[_Receivable] = []
        for item in receivables:
            if item.pay_date <= session:
                cash += item.amount
            else:
                unsettled.append(item)
        receivables = unsettled
        div_events = dividend_by_ex.get(session, [])
        split_events = split_by_date.get(session, [])
        if {event.symbol for event in div_events} & {event.symbol for event in split_events}:
            raise ValueError("PHASE5_SAME_SESSION_DIVIDEND_SPLIT_AMBIGUOUS")
        for event in div_events:
            entitlement = holdings[event.symbol] * event.amount_per_unit
            if entitlement < 0.0 or not math.isfinite(entitlement):
                raise ValueError("PHASE5_DIVIDEND_ENTITLEMENT_INVALID")
            if entitlement > 0.0:
                receivables.append(_Receivable(event.symbol, event.pay_date, entitlement))
        for event in split_events:
            if event.unit_multiplier <= 0.0 or not math.isfinite(event.unit_multiplier):
                raise ValueError("PHASE5_SPLIT_MULTIPLIER_INVALID")
            holdings[event.symbol] *= event.unit_multiplier

        open_prices = {symbol: float(dataset.bars[symbol].loc[session, "open"]) for symbol in active_symbols}
        receivable_total = sum(item.amount for item in receivables)
        open_equity = cash + receivable_total + sum(holdings[s] * open_prices[s] for s in active_symbols)
        if not math.isfinite(open_equity) or open_equity <= 0.0:
            raise ValueError("PHASE5_OPEN_EQUITY_INVALID")

        target = due_map.get(session)
        if target is not None:
            if target.signal_session >= session:
                raise ValueError("PHASE5_NONCAUSAL_TARGET")
            weights = dict(target.weights)
            if any(symbol not in active_symbols for symbol in weights):
                raise ValueError("PHASE5_TARGET_SYMBOL_OUTSIDE_REPLAY")
            if any(weight < 0.0 or not math.isfinite(weight) for weight in weights.values()) or sum(weights.values()) > 1.0 + 1e-12:
                raise ValueError("PHASE5_TARGET_WEIGHT_INVALID")
            desired = {s: float(weights.get(s, 0.0)) * open_equity for s in active_symbols}
            current = {s: holdings[s] * open_prices[s] for s in active_symbols}
            delta = {s: desired[s] - current[s] for s in active_symbols}
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
                fills.append(Fill(symbol, target.signal_session, session, price, units_delta, notional, fee))
            buy_symbols = [symbol for symbol in active_symbols if delta[symbol] > 1e-10]
            total_buy = sum(delta[symbol] for symbol in buy_symbols)
            scale = 1.0
            if total_buy > 0.0 and total_buy * (1.0 + friction_rate) > cash:
                scale = max(0.0, cash / (total_buy * (1.0 + friction_rate)))
            for symbol in buy_symbols:
                price = open_prices[symbol]
                notional = delta[symbol] * scale
                fee = notional * friction_rate
                units_delta = notional / price
                holdings[symbol] += units_delta
                cash -= notional + fee
                total_turnover += notional
                fills.append(Fill(symbol, target.signal_session, session, price, units_delta, notional, fee))
        if -1e-8 <= cash < 0.0:
            cash = 0.0
        if cash < 0.0 or any(value < -1e-12 or not math.isfinite(value) for value in holdings.values()):
            raise ValueError("PHASE5_LONG_ONLY_ACCOUNTING_BREACH")
        close_prices = {symbol: float(dataset.bars[symbol].loc[session, "close"]) for symbol in active_symbols}
        receivable_total = sum(item.amount for item in receivables)
        risky_value = sum(holdings[s] * close_prices[s] for s in active_symbols)
        close_equity = cash + receivable_total + risky_value
        if not math.isfinite(close_equity) or close_equity <= 0.0:
            raise ValueError("PHASE5_CLOSE_EQUITY_INVALID")
        exposure = risky_value / close_equity
        if not 0.0 <= exposure <= 1.0 + 1e-12:
            raise ValueError("PHASE5_GROSS_EXPOSURE_BREACH")
        if session in signal_map:
            last_target_gross = float(sum(weight for _, weight in signal_map[session].weights))
        states.append(LedgerState(session, float(cash), float(receivable_total), float(close_equity), float(exposure), float(last_target_gross), tuple((s, float(holdings[s])) for s in active_symbols if holdings[s] > 0.0)))
    return ReplayResult(int(friction_bps), float(initial_cash), sessions, tuple(states), tuple(fills), float(total_turnover))
