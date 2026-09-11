from __future__ import annotations

import numpy as np
import pandas as pd

from .models import BacktestResult, ExecutionAssumptions
from .portfolio import PortfolioLedger


class BacktestInputError(ValueError):
    pass


def run_backtest(
    bars: pd.DataFrame,
    targets: pd.Series,
    assumptions: ExecutionAssumptions,
) -> BacktestResult:
    _validate_inputs(bars, targets)
    ledger = PortfolioLedger(assumptions)
    equity_values: list[float] = []
    cash_values: list[float] = []
    position_values: list[float] = []
    exposure_values: list[float] = []
    last_executed_target = 0.0

    for index, (timestamp, bar) in enumerate(bars.iterrows()):
        if index > 0:
            prior_target = float(targets.iloc[index - 1])
            if not np.isclose(prior_target, last_executed_target, atol=1e-12, rtol=0):
                ledger.rebalance_at_open(timestamp, float(bar["open"]), prior_target)
                last_executed_target = prior_target
        close = float(bar["close"])
        equity = ledger.equity(close)
        if not np.isfinite(equity) or equity < -1e-8 or ledger.cash < -1e-8:
            raise RuntimeError("portfolio accounting produced invalid equity or cash")
        position_value = ledger.quantity * close
        exposure = 0.0 if equity == 0 else position_value / equity
        if exposure < -1e-10 or exposure > 1.0 + 1e-8:
            raise RuntimeError("portfolio exposure escaped the long-only unlevered range")
        equity_values.append(equity)
        cash_values.append(ledger.cash)
        position_values.append(ledger.quantity)
        exposure_values.append(exposure)

    return BacktestResult(
        equity_curve=pd.Series(equity_values, index=bars.index, name="equity"),
        cash_curve=pd.Series(cash_values, index=bars.index, name="cash"),
        position_curve=pd.Series(position_values, index=bars.index, name="quantity"),
        exposure_curve=pd.Series(exposure_values, index=bars.index, name="exposure"),
        fills=tuple(ledger.fills),
        trades=tuple(ledger.trades),
        turnover_notional=ledger.turnover_notional,
        assumptions=assumptions,
    )


def _validate_inputs(bars: pd.DataFrame, targets: pd.Series) -> None:
    if bars.empty:
        raise BacktestInputError("bars must not be empty")
    if not bars.index.equals(targets.index):
        raise BacktestInputError("target index must exactly match bars index")
    if not bars.index.is_monotonic_increasing or bars.index.has_duplicates:
        raise BacktestInputError("bar index must be unique and increasing")
    for column in ("open", "close"):
        if column not in bars.columns:
            raise BacktestInputError(f"bars missing {column}")
        values = bars[column].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values <= 0).any():
            raise BacktestInputError(f"{column} prices must be finite and positive")
    target_values = targets.to_numpy(dtype=float)
    if not np.isfinite(target_values).all() or (target_values < 0).any() or (target_values > 1).any():
        raise BacktestInputError("target exposure must be finite and within [0, 1]")
