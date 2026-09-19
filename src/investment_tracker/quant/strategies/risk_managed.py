from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

import numpy as np
import pandas as pd

from .base import finalize_targets, validate_allocation
from .indicators import realized_volatility, sma


@dataclass(frozen=True)
class RiskManagedTrendStrategy:
    trend_window: int
    volatility_window: int
    target_volatility: float
    maximum_exposure: float

    family: str = "risk_managed_trend"
    entry_rule: str = "close > trend SMA"
    exit_rule: str = "exit when close <= trend SMA"
    position_sizing: str = "target volatility divided by realized volatility"
    execution_timing: Literal["NEXT_BAR_OPEN"] = "NEXT_BAR_OPEN"
    risk_rules: str = "long-only; no leverage; exposure capped at maximum_exposure"

    def __post_init__(self) -> None:
        validate_allocation(self.maximum_exposure)
        if self.trend_window <= 0 or self.volatility_window < 2:
            raise ValueError("trend_window must be positive and volatility_window at least two")
        if self.target_volatility <= 0:
            raise ValueError("target_volatility must be positive")

    @property
    def parameters(self) -> Mapping[str, int | float | str]:
        return {
            "trend_window": self.trend_window,
            "volatility_window": self.volatility_window,
            "target_volatility": self.target_volatility,
            "maximum_exposure": self.maximum_exposure,
        }

    def targets(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["close"].astype(float)
        trend = close > sma(close, self.trend_window)
        volatility = realized_volatility(close, self.volatility_window)
        sized = (self.target_volatility / volatility).replace([np.inf, -np.inf], np.nan)
        targets = sized.clip(lower=0.0, upper=self.maximum_exposure).where(trend, 0.0)
        return finalize_targets(targets, self.maximum_exposure)
