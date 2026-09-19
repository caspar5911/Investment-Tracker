from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.strategies.indicators import (
    atr,
    momentum,
    realized_volatility,
    sma,
)
from investment_tracker.quant.strategies.momentum import MomentumStrategy
from investment_tracker.quant.strategies.risk_managed import RiskManagedTrendStrategy
from investment_tracker.quant.strategies.trend import TrendStrategy
from investment_tracker.quant.strategies.trend_momentum import TrendMomentumStrategy


def bars(closes: list[float]) -> pd.DataFrame:
    values = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {
            "open": values,
            "high": values + 1.0,
            "low": values - 1.0,
            "close": values,
            "volume": np.full(len(values), 1000),
        },
        index=pd.date_range("2024-01-02", periods=len(values), freq="B", tz="UTC"),
    )


def test_sma_uses_only_current_and_prior_values() -> None:
    values = pd.Series([10.0, 20.0, 30.0, 999.0])
    result = sma(values, 3)
    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == 20.0


def test_momentum_is_hand_calculable_and_has_no_early_signal() -> None:
    values = pd.Series([100.0, 110.0, 121.0])
    result = momentum(values, 2)
    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(0.21)


def test_atr_uses_true_range() -> None:
    frame = pd.DataFrame(
        {"high": [11.0, 13.0], "low": [9.0, 10.0], "close": [10.0, 12.0]}
    )
    result = atr(frame, 2)
    assert np.isnan(result.iloc[0])
    assert result.iloc[1] == pytest.approx(2.5)


def test_realized_volatility_is_annualized_and_backward_looking() -> None:
    values = pd.Series([100.0, 110.0, 99.0, 108.9])
    result = realized_volatility(values, 2)
    expected = pd.Series(np.log(values / values.shift(1))).rolling(2).std(ddof=1).iloc[2] * np.sqrt(252)
    assert result.iloc[2] == pytest.approx(expected)
    assert np.isnan(result.iloc[1])


def test_trend_target_is_long_only_and_capped() -> None:
    strategy = TrendStrategy(fast_window=2, slow_window=3, allocation=0.5)
    targets = strategy.targets(bars([1.0, 2.0, 3.0, 2.0]))
    assert targets.tolist() == [0.0, 0.0, 0.5, 0.0]
    assert strategy.execution_timing == "NEXT_BAR_OPEN"
    assert strategy.maximum_exposure == 0.5


def test_momentum_requires_positive_trailing_return() -> None:
    strategy = MomentumStrategy(lookback=2, allocation=1.0)
    assert strategy.targets(bars([100.0, 90.0, 99.0, 80.0])).tolist() == [0.0, 0.0, 0.0, 0.0]
    assert strategy.targets(bars([100.0, 90.0, 101.0])).tolist() == [0.0, 0.0, 1.0]


def test_trend_momentum_requires_both_gates() -> None:
    strategy = TrendMomentumStrategy(
        fast_window=2,
        slow_window=3,
        momentum_lookback=2,
        allocation=0.25,
    )
    targets = strategy.targets(bars([100.0, 90.0, 120.0, 80.0]))
    assert targets.tolist() == [0.0, 0.0, 0.25, 0.0]


def test_risk_managed_trend_reduces_exposure_when_volatility_rises() -> None:
    strategy = RiskManagedTrendStrategy(
        trend_window=2,
        volatility_window=2,
        target_volatility=0.10,
        maximum_exposure=1.0,
    )
    low_vol = strategy.targets(bars([100, 101, 102, 103, 104]))
    high_vol = strategy.targets(bars([100, 120, 105, 130, 140]))
    assert 0 < low_vol.iloc[-1] <= 1
    assert 0 < high_vol.iloc[-1] < low_vol.iloc[-1]


@pytest.mark.parametrize("allocation", [-0.1, 0.0, 1.01])
def test_allocation_outside_long_only_unlevered_range_is_rejected(allocation: float) -> None:
    with pytest.raises(ValueError, match="allocation"):
        TrendStrategy(fast_window=2, slow_window=3, allocation=allocation)


def test_invalid_parameter_order_is_rejected() -> None:
    with pytest.raises(ValueError, match="fast_window must be less than slow_window"):
        TrendStrategy(fast_window=5, slow_window=5, allocation=1.0)
