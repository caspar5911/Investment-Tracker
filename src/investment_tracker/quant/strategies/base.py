from __future__ import annotations

from typing import Literal, Mapping, Protocol

import pandas as pd


class StrategyDefinition(Protocol):
    family: str
    entry_rule: str
    exit_rule: str
    position_sizing: str
    maximum_exposure: float
    execution_timing: Literal["NEXT_BAR_OPEN"]
    risk_rules: str

    @property
    def parameters(self) -> Mapping[str, int | float | str]: ...

    def targets(self, bars: pd.DataFrame) -> pd.Series: ...


def validate_allocation(allocation: float) -> None:
    if not 0 < allocation <= 1:
        raise ValueError("allocation must be greater than zero and no more than one")


def finalize_targets(targets: pd.Series, maximum_exposure: float) -> pd.Series:
    numeric = targets.astype(float).fillna(0.0).clip(lower=0.0, upper=maximum_exposure)
    numeric.name = "target_exposure"
    return numeric
