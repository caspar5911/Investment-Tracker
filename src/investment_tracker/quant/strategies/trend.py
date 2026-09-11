from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

import pandas as pd

from .base import finalize_targets, validate_allocation
from .indicators import sma


@dataclass(frozen=True)
class TrendStrategy:
    fast_window: int
    slow_window: int
    allocation: float

    family: str = "trend"
    entry_rule: str = "close > slow SMA and fast SMA > slow SMA"
    exit_rule: str = "exit when either trend condition is false"
    position_sizing: str = "fixed percentage of strategy capital"
    execution_timing: Literal["NEXT_BAR_OPEN"] = "NEXT_BAR_OPEN"
    risk_rules: str = "long-only; no leverage; exposure capped at allocation"

    def __post_init__(self) -> None:
        validate_allocation(self.allocation)
        if self.fast_window <= 0 or self.slow_window <= 0:
            raise ValueError("moving-average windows must be positive")
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
            "allocation": self.allocation,
        }

    def targets(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["close"].astype(float)
        fast = sma(close, self.fast_window)
        slow = sma(close, self.slow_window)
        eligible = (close > slow) & (fast > slow)
        return finalize_targets(eligible.astype(float) * self.allocation, self.maximum_exposure)
