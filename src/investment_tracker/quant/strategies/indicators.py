from __future__ import annotations

import numpy as np
import pandas as pd


def _positive_window(window: int) -> None:
    if window <= 0:
        raise ValueError("indicator window must be positive")


def sma(values: pd.Series, window: int) -> pd.Series:
    _positive_window(window)
    return values.astype(float).rolling(window=window, min_periods=window).mean()


def momentum(values: pd.Series, lookback: int) -> pd.Series:
    _positive_window(lookback)
    return values.astype(float).pct_change(periods=lookback, fill_method=None)


def true_range(bars: pd.DataFrame) -> pd.Series:
    previous_close = bars["close"].astype(float).shift(1)
    ranges = pd.concat(
        [
            bars["high"].astype(float) - bars["low"].astype(float),
            (bars["high"].astype(float) - previous_close).abs(),
            (bars["low"].astype(float) - previous_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(bars: pd.DataFrame, window: int) -> pd.Series:
    _positive_window(window)
    return true_range(bars).rolling(window=window, min_periods=window).mean()


def realized_volatility(values: pd.Series, window: int, periods_per_year: int = 252) -> pd.Series:
    _positive_window(window)
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    log_returns = np.log(values.astype(float) / values.astype(float).shift(1))
    return log_returns.rolling(window=window, min_periods=window).std(ddof=1) * np.sqrt(periods_per_year)
