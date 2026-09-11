from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

import pandas as pd

from .base import finalize_targets, validate_allocation
from .indicators import momentum, sma


@dataclass(frozen=True)
class TrendMomentumStrategy:
    fast_window: int
    slow_window: int
    momentum_lookback: int
    allocation: float

    family: str = "trend_momentum"
    entry_rule: str = "close > slow SMA, fast SMA > slow SMA, and momentum > 0"
    exit_rule: str = "exit when any entry condition is false"
    position_sizing: str = "fixed percentage of strategy capital"
    execution_timing: Literal["NEXT_BAR_OPEN"] = "NEXT_BAR_OPEN"
    risk_rules: str = "long-only; no leverage; exposure capped at allocation"

    def __post_init__(self) -> None:
        validate_allocation(self.allocation)
        if self.fast_window <= 0 or self.slow_window <= 0 or self.momentum_lookback <= 0:
            raise ValueError("indicator windows must be positive")
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be less than slow_window")

    @property
    def maximum_exposure(self) -> float:
        return self.allocation

    @property
    def parameters(self) -> Mapping[str, int | float | str]:
        return {
            "fast_window": self.fast_window,
            "slow_window": self.slow_window,
            "momentum_lookback": self.momentum_lookback,
            "allocation": self.allocation,
        }

    def targets(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["close"].astype(float)
        slow = sma(close, self.slow_window)
        eligible = (
            (close > slow)
            & (sma(close, self.fast_window) > slow)
            & (momentum(close, self.momentum_lookback) > 0)
        )
        return finalize_targets(eligible.astype(float) * self.allocation, self.maximum_exposure)
