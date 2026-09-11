from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    cagr: float | None
    annualized_volatility: float | None
    max_drawdown: float
    sharpe: float | None
    sortino: float | None
    calmar: float | None
    trade_count: int
    win_rate: float | None
    average_win: float | None
    average_loss: float | None
    profit_factor: float | None
    turnover: float | None
    exposure: float | None
    time_in_market: float | None


def calculate_metrics(
    equity_curve: pd.Series,
    *,
    realized_pnls: Iterable[float] = (),
    turnover_notional: float = 0.0,
    exposure: pd.Series | None = None,
    periods_per_year: int = 252,
) -> PerformanceMetrics:
    equity = equity_curve.astype(float)
    if equity.empty or not np.isfinite(equity.to_numpy()).all() or (equity <= 0).any():
        raise ValueError("equity curve must contain positive finite values")
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    elapsed_days = (equity.index[-1] - equity.index[0]).total_seconds() / 86_400 if len(equity) > 1 else 0
    cagr = None if elapsed_days <= 0 else float((equity.iloc[-1] / equity.iloc[0]) ** (365.25 / elapsed_days) - 1.0)

    returns = equity.pct_change(fill_method=None).dropna().to_numpy(dtype=float)
    volatility = None
    sharpe = None
    sortino = None
    if len(returns) >= 2:
        standard_deviation = float(np.std(returns, ddof=1))
        if standard_deviation > 0:
            volatility = standard_deviation * math.sqrt(periods_per_year)
            sharpe = float(np.mean(returns) / standard_deviation * math.sqrt(periods_per_year))
        downside_deviation = float(math.sqrt(np.mean(np.minimum(returns, 0.0) ** 2)))
        if downside_deviation > 0:
            sortino = float(np.mean(returns) / downside_deviation * math.sqrt(periods_per_year))

    drawdown = equity / equity.cummax() - 1.0
    max_drawdown = float(drawdown.min())
    calmar = None
    if cagr is not None and max_drawdown < 0:
        calmar = cagr / abs(max_drawdown)

    pnls = tuple(float(value) for value in realized_pnls)
    wins = tuple(value for value in pnls if value > 0)
    losses = tuple(value for value in pnls if value < 0)
    trade_count = len(pnls)
    win_rate = None if trade_count == 0 else len(wins) / trade_count
    average_win = None if not wins else float(np.mean(wins))
    average_loss = None if not losses else float(np.mean(losses))
    profit_factor = None if not wins or not losses else sum(wins) / abs(sum(losses))
    average_equity = float(equity.mean())
    turnover = None if average_equity <= 0 else turnover_notional / average_equity

    average_exposure = None
    time_in_market = None
    if exposure is not None:
        aligned = exposure.reindex(equity.index).astype(float)
        if aligned.isna().any() or not np.isfinite(aligned.to_numpy()).all():
            raise ValueError("exposure must align with equity and be finite")
        average_exposure = float(aligned.mean())
        time_in_market = float((aligned > 0).mean())

    return PerformanceMetrics(
        total_return=total_return,
        cagr=cagr,
        annualized_volatility=volatility,
        max_drawdown=max_drawdown,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        trade_count=trade_count,
        win_rate=win_rate,
        average_win=average_win,
        average_loss=average_loss,
        profit_factor=profit_factor,
        turnover=turnover,
        exposure=average_exposure,
        time_in_market=time_in_market,
    )


def metrics_for_backtest(result) -> PerformanceMetrics:
    return calculate_metrics(
        result.equity_curve,
        realized_pnls=(trade.realized_pnl for trade in result.trades),
        turnover_notional=result.turnover_notional,
        exposure=result.exposure_curve,
    )
