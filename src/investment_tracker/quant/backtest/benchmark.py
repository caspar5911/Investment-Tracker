from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from .engine import run_backtest
from .models import BacktestResult, ExecutionAssumptions


def buy_and_hold(bars: pd.DataFrame, assumptions: ExecutionAssumptions) -> BacktestResult:
    targets = pd.Series(1.0, index=bars.index, name="target_exposure")
    return run_backtest(bars, targets, assumptions)


def cash_benchmark(index: pd.Index, initial_capital: float) -> pd.Series:
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    return pd.Series(float(initial_capital), index=index, name="cash_benchmark")


def aggregate_equal_weight(equity_curves: Mapping[str, pd.Series], initial_capital: float) -> pd.Series:
    if not equity_curves:
        raise ValueError("at least one equity curve is required")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    first_index = next(iter(equity_curves.values())).index
    normalized: list[pd.Series] = []
    for name, curve in sorted(equity_curves.items()):
        if not curve.index.equals(first_index):
            raise ValueError(f"equity curve index mismatch: {name}")
        normalized.append(curve.astype(float) / float(curve.iloc[0]))
    combined = pd.concat(normalized, axis=1).mean(axis=1) * initial_capital
    combined.name = "equal_weight_portfolio"
    return combined
