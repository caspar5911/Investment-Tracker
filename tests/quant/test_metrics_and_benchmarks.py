from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.backtest.benchmark import (
    aggregate_equal_weight,
    buy_and_hold,
    cash_benchmark,
)
from investment_tracker.quant.backtest.metrics import calculate_metrics
from investment_tracker.quant.backtest.models import ExecutionAssumptions


def equity(values: list[float], start: str = "2024-01-02", freq: str = "B") -> pd.Series:
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=freq, tz="UTC"))


def market_bars(values: list[float]) -> pd.DataFrame:
    prices = np.asarray(values, dtype=float)
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": np.full(len(prices), 1000),
        },
        index=pd.date_range("2024-01-02", periods=len(prices), freq="B", tz="UTC"),
    )


def test_max_drawdown_from_known_equity_path() -> None:
    metrics = calculate_metrics(equity([100, 120, 90, 108]))
    assert metrics.max_drawdown == pytest.approx(-0.25)


def test_cagr_uses_actual_elapsed_time() -> None:
    curve = pd.Series(
        [100.0, 121.0],
        index=pd.DatetimeIndex(["2020-01-01", "2021-01-01"], tz="UTC"),
    )
    expected = 1.21 ** (365.25 / 366.0) - 1
    assert calculate_metrics(curve).cagr == pytest.approx(expected)


def test_sharpe_sortino_and_calmar_are_risk_adjusted() -> None:
    curve = equity([100.0, 110.0, 104.5, 106.59])
    returns = np.asarray([0.10, -0.05, 0.02])
    expected_sharpe = returns.mean() / returns.std(ddof=1) * math.sqrt(252)
    expected_sortino = returns.mean() / math.sqrt(np.mean(np.minimum(returns, 0) ** 2)) * math.sqrt(252)
    metrics = calculate_metrics(curve)
    assert metrics.sharpe == pytest.approx(expected_sharpe)
    assert metrics.sortino == pytest.approx(expected_sortino)
    assert metrics.calmar == pytest.approx(metrics.cagr / abs(metrics.max_drawdown))


def test_undefined_ratios_are_none() -> None:
    metrics = calculate_metrics(equity([100, 100, 100]))
    assert metrics.sharpe is None
    assert metrics.sortino is None
    assert metrics.calmar is None


def test_trade_statistics_and_turnover_use_realized_trades() -> None:
    metrics = calculate_metrics(
        equity([100, 105, 102]),
        realized_pnls=(10.0, -5.0),
        turnover_notional=150.0,
        exposure=equity([0.0, 1.0, 0.5]),
    )
    assert metrics.trade_count == 2
    assert metrics.win_rate == 0.5
    assert metrics.average_win == 10.0
    assert metrics.average_loss == -5.0
    assert metrics.profit_factor == 2.0
    assert metrics.turnover == pytest.approx(150.0 / ((100 + 105 + 102) / 3))
    assert metrics.exposure == 0.5
    assert metrics.time_in_market == pytest.approx(2 / 3)


def test_buy_and_hold_and_cash_use_same_dates_and_capital() -> None:
    bars = market_bars([10, 20, 30])
    assumptions = ExecutionAssumptions(
        initial_capital=1000,
        commission_bps=0,
        slippage_bps=0,
        allow_fractional=True,
    )
    held = buy_and_hold(bars, assumptions)
    cash = cash_benchmark(bars.index, 1000)
    assert held.equity_curve.index.equals(bars.index)
    assert held.final_equity == 1500
    assert cash.tolist() == [1000, 1000, 1000]


def test_equal_weight_portfolio_aggregates_normalized_equity() -> None:
    combined = aggregate_equal_weight(
        {"A": equity([100, 110, 121]), "B": equity([100, 90, 99])},
        initial_capital=1000,
    )
    assert combined.tolist() == [1000, 1000, 1100]
