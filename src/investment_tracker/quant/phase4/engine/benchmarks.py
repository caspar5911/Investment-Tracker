from __future__ import annotations

from investment_tracker.quant.phase4.engine.execution import (
    _replay,
    _validated_friction,
    _validated_scored,
)
from investment_tracker.quant.phase4.engine.market import MarketPanel
from investment_tracker.quant.phase4.engine.models import PortfolioReplay


_INITIAL_CASH: float = 100000.0


def cash_benchmark(scored: MarketPanel) -> PortfolioReplay:
    """Constant initial cash with zero exposure, fills, turnover, and return."""

    open_values, close_values, symbols, sessions = _validated_scored(scored)
    pending = [None] * len(sessions)
    return _replay(
        open_values,
        close_values,
        symbols,
        sessions,
        pending,
        friction_bps=0,
        initial_cash=_INITIAL_CASH,
        binding=None,
    )


def equal_weight_buy_and_hold(
    scored: MarketPanel, *, friction_bps: int
) -> PortfolioReplay:
    """One equal-weight buy-and-hold over the admitted symbol order.

    The equal-weight signal forms at the first scored session close, executes
    once at the next eligible open under the same friction case, and then holds
    without rebalance.
    """

    open_values, close_values, symbols, sessions = _validated_scored(scored)
    _validated_friction(friction_bps)
    count = len(sessions)
    pending = [None] * count
    if count >= 2:
        weight = 1.0 / len(symbols)
        weights = tuple((symbol, weight) for symbol in symbols)
        pending[0] = (sessions[0], sessions[1], weights)
    return _replay(
        open_values,
        close_values,
        symbols,
        sessions,
        pending,
        friction_bps=friction_bps,
        initial_cash=_INITIAL_CASH,
        binding=None,
    )


__all__ = ("cash_benchmark", "equal_weight_buy_and_hold")
