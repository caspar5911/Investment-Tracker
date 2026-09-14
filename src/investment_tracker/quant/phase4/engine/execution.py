from __future__ import annotations

import math
from numbers import Integral
from typing import Sequence, Tuple

import numpy as np
import pandas as pd

from investment_tracker.quant.phase4.engine.market import MarketPanel
from investment_tracker.quant.phase4.engine.models import (
    Fill,
    FixedStrategyBinding,
    Gate2SealError,
    PortfolioReplay,
    SessionState,
    TargetInstruction,
)


_INITIAL_CASH: float = 100000.0
_NOTIONAL_TOLERANCE: float = 1e-12
_EXPOSURE_TOLERANCE: float = 1e-12
_FLOAT_DUST: float = 1e-9

PendingTarget = Tuple[
    pd.Timestamp, pd.Timestamp | None, Tuple[Tuple[str, float], ...]
]


def _accounting(message: str) -> Gate2SealError:
    return Gate2SealError("ACCOUNTING_INVARIANT_FAILURE", message)


def _long_only(message: str) -> Gate2SealError:
    return Gate2SealError("LONG_ONLY_INVARIANT_FAILURE", message)


def _validated_scored(
    panel: MarketPanel,
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...], tuple[pd.Timestamp, ...]]:
    if not isinstance(panel, MarketPanel):
        raise _accounting("execution requires a market panel")
    if panel.role != "SCORED":
        raise _accounting("execution requires a scored panel")
    symbols = panel.symbols
    sessions = panel.sessions
    open_values = panel.open_prices.to_numpy(dtype=np.float64, copy=True)
    close_values = panel.close_prices.to_numpy(dtype=np.float64, copy=True)
    return open_values, close_values, symbols, sessions


def _validated_friction(friction_bps: int) -> int:
    if (
        isinstance(friction_bps, bool)
        or not isinstance(friction_bps, Integral)
        or friction_bps < 0
    ):
        raise _accounting("friction_bps must be a nonnegative integer")
    return int(friction_bps)


def _validated_cash(initial_cash: float) -> float:
    if isinstance(initial_cash, bool) or not isinstance(
        initial_cash, (int, float)
    ):
        raise _accounting("initial_cash must be a finite positive value")
    value = float(initial_cash)
    if not math.isfinite(value) or value <= 0.0:
        raise _accounting("initial_cash must be a finite positive value")
    return value


def _make_fill(
    symbol: str,
    signal_ts: pd.Timestamp,
    fill_ts: pd.Timestamp,
    reference_open: float,
    units_delta: float,
    notional: float,
    friction: float,
    binding: FixedStrategyBinding | None,
) -> Fill:
    return Fill(
        symbol=symbol,
        signal_timestamp=signal_ts,
        fill_timestamp=fill_ts,
        reference_open=float(reference_open),
        units_delta=float(units_delta),
        fill_notional=float(notional),
        friction=float(friction),
        binding=binding,
    )


def _replay(
    open_values: np.ndarray,
    close_values: np.ndarray,
    symbols: tuple[str, ...],
    sessions: tuple[pd.Timestamp, ...],
    pending: Sequence[PendingTarget | None],
    *,
    friction_bps: int,
    initial_cash: float,
    binding: FixedStrategyBinding | None,
) -> PortfolioReplay:
    count = len(sessions)
    symbol_index = {symbol: position for position, symbol in enumerate(symbols)}
    holdings = np.zeros(len(symbols), dtype=np.float64)
    cash = float(initial_cash)
    friction_rate = float(friction_bps) / 10000.0

    fills: list[Fill] = []
    states: list[SessionState] = []
    last_target_gross = 0.0

    for position in range(count):
        open_row = open_values[position]
        close_row = close_values[position]
        open_equity = float(cash + float(np.dot(holdings, open_row)))
        if not math.isfinite(open_equity) or open_equity <= 0.0:
            raise _accounting("pre-cost open equity is not finite and positive")

        due_target = pending[position - 1] if position >= 1 else None
        if due_target is not None and due_target[1] == sessions[position]:
            signal_ts, _due_ts, target_weights = due_target
            desired = np.zeros(len(symbols), dtype=np.float64)
            for symbol, weight in target_weights:
                desired[symbol_index[symbol]] = float(weight) * open_equity
            current = holdings * open_row
            delta = desired - current
            tolerance = _NOTIONAL_TOLERANCE * max(1.0, open_equity)
            sell_order = [j for j in range(len(symbols)) if delta[j] < -tolerance]
            buy_order = [j for j in range(len(symbols)) if delta[j] > tolerance]

            for j in sell_order:
                target_units = desired[j] / open_row[j]
                units_delta = target_units - holdings[j]
                notional = units_delta * open_row[j]
                friction = abs(notional) * friction_rate
                holdings[j] = target_units
                cash += -notional - friction
                fills.append(
                    _make_fill(
                        symbols[j],
                        signal_ts,
                        sessions[position],
                        float(open_row[j]),
                        float(units_delta),
                        float(notional),
                        float(friction),
                        binding,
                    )
                )

            if buy_order:
                desired_buy = np.array(
                    [delta[j] for j in buy_order], dtype=np.float64
                )
                total_buy = float(desired_buy.sum())
                if total_buy > 0.0:
                    if total_buy * (1.0 + friction_rate) > cash:
                        scale = cash / (total_buy * (1.0 + friction_rate))
                    else:
                        scale = 1.0
                    for j, raw_notional in zip(buy_order, desired_buy, strict=True):
                        notional = raw_notional * scale
                        if notional <= 0.0:
                            continue
                        friction = notional * friction_rate
                        units_delta = notional / open_row[j]
                        holdings[j] += units_delta
                        cash -= notional + friction
                        fills.append(
                            _make_fill(
                                symbols[j],
                                signal_ts,
                                sessions[position],
                                float(open_row[j]),
                                float(units_delta),
                                float(notional),
                                float(friction),
                                binding,
                            )
                        )

        if -_FLOAT_DUST <= cash < 0.0:
            cash = 0.0
        if cash < 0.0:
            raise _accounting("post-fill cash is negative")
        if not bool(np.all(np.isfinite(holdings))) or bool(np.any(holdings < 0.0)):
            raise _accounting("holdings contain a nonfinite or negative unit")

        close_equity = float(cash + float(np.dot(holdings, close_row)))
        if not math.isfinite(close_equity) or close_equity <= 0.0:
            raise _accounting("close equity is not finite and positive")
        risky_close = float(np.dot(holdings, close_row))
        realized = risky_close / close_equity
        if not 0.0 <= realized <= 1.0 + _EXPOSURE_TOLERANCE:
            raise _long_only("realized gross exposure exceeds one")

        fresh_target = pending[position]
        if fresh_target is not None:
            last_target_gross = float(
                sum(weight for _symbol, weight in fresh_target[2])
            )
        units = tuple(
            (symbols[j], float(holdings[j]))
            for j in range(len(symbols))
            if holdings[j] > 0.0
        )
        states.append(
            SessionState(
                session=sessions[position],
                open_equity=float(open_equity),
                close_equity=float(close_equity),
                cash=float(cash),
                units=units,
                realized_gross_exposure=float(realized),
                target_gross_exposure=float(last_target_gross),
                binding=binding,
            )
        )

    total_turnover = float(sum(abs(fill.fill_notional) for fill in fills))
    return PortfolioReplay(
        candidate_id=None if binding is None else binding.candidate_id,
        binding_sha256=None if binding is None else binding.binding_sha256,
        friction_bps=int(friction_bps),
        initial_cash=float(initial_cash),
        states=tuple(states),
        fills=tuple(fills),
        total_turnover=total_turnover,
    )


def replay_targets(
    scored: MarketPanel,
    targets: Sequence[TargetInstruction | None],
    *,
    friction_bps: int,
    initial_cash: float = _INITIAL_CASH,
) -> PortfolioReplay:
    open_values, close_values, symbols, sessions = _validated_scored(scored)
    _validated_friction(friction_bps)
    _validated_cash(initial_cash)
    if isinstance(targets, (str, bytes)) or not isinstance(targets, Sequence):
        raise _accounting("targets must be a sequence aligned to scored sessions")
    target_items = tuple(targets)
    if len(target_items) != len(sessions):
        raise _accounting("targets must align one per scored session")

    panel_symbols = set(symbols)
    pending: list[PendingTarget | None] = []
    candidate_id: str | None = None
    binding_sha256: str | None = None
    binding: FixedStrategyBinding | None = None
    for index, item in enumerate(target_items):
        if item is None:
            pending.append(None)
            continue
        if not isinstance(item, TargetInstruction):
            raise _accounting("target entry must be a TargetInstruction")
        signal_ts = item.signal_timestamp
        due_ts = item.due_session
        if signal_ts != sessions[index]:
            raise _accounting("target signal does not align to its scored session")
        if due_ts is not None:
            if index + 1 >= len(sessions) or due_ts != sessions[index + 1]:
                raise _accounting(
                    "target due session must be the next scored session"
                )
        elif index + 1 < len(sessions):
            raise _accounting("only a final scored-session target may have no due session")
        for symbol, _weight in item.weights:
            if symbol not in panel_symbols:
                raise _accounting(
                    "target references a symbol absent from the scored panel"
                )
        item_candidate = item.binding.candidate_id
        item_binding = item.binding.binding_sha256
        if candidate_id is None:
            candidate_id = item_candidate
            binding_sha256 = item_binding
            binding = item.binding
        elif item_candidate != candidate_id or item_binding != binding_sha256:
            raise _accounting(
                "all targets must share one strategy binding identity"
            )
        pending.append((signal_ts, due_ts, item.weights))

    return _replay(
        open_values,
        close_values,
        symbols,
        sessions,
        pending,
        friction_bps=friction_bps,
        initial_cash=initial_cash,
        binding=binding,
    )


__all__ = ("replay_targets",)
