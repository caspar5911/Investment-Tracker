from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

import pandas as pd

from .base import finalize_targets, validate_allocation
from .indicators import momentum


@dataclass(frozen=True)
class MomentumStrategy:
    lookback: int
    allocation: float

    family: str = "momentum"
    entry_rule: str = "trailing return is positive"
    exit_rule: str = "exit when trailing return is non-positive"
    position_sizing: str = "fixed percentage of strategy capital"
    execution_timing: Literal["NEXT_BAR_OPEN"] = "NEXT_BAR_OPEN"
    risk_rules: str = "long-only; no leverage; exposure capped at allocation"

    def __post_init__(self) -> None:
        validate_allocation(self.allocation)
        if self.lookback <= 0:
            raise ValueError("lookback must be positive")

    @property
    def maximum_exposure(self) -> float:
        return self.allocation

    @property
    def parameters(self) -> Mapping[str, int | float | str]:
        return {"lookback": self.lookback, "allocation": self.allocation}

    def targets(self, bars: pd.DataFrame) -> pd.Series:
        eligible = momentum(bars["close"], self.lookback) > 0
        return finalize_targets(eligible.astype(float) * self.allocation, self.maximum_exposure)
