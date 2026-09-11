from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.backtest.engine import BacktestInputError, run_backtest
from investment_tracker.quant.backtest.models import ExecutionAssumptions


def bars(opens: list[float], closes: list[float] | None = None) -> pd.DataFrame:
    close_values = np.asarray(closes if closes is not None else opens, dtype=float)
    open_values = np.asarray(opens, dtype=float)
    return pd.DataFrame(
        {
            "open": open_values,
            "high": np.maximum(open_values, close_values) + 1,
            "low": np.minimum(open_values, close_values) - 1,
            "close": close_values,
            "volume": np.full(len(opens), 1000),
        },
        index=pd.date_range("2024-01-02", periods=len(opens), freq="B", tz="UTC"),
    )


def assumptions(**updates) -> ExecutionAssumptions:
    values = {
        "initial_capital": 1000.0,
        "commission_bps": 0.0,
        "slippage_bps": 0.0,
        "allow_fractional": True,
    }
    values.update(updates)
    return ExecutionAssumptions(**values)


def test_signal_on_day_one_executes_at_day_two_open() -> None:
    data = bars([10, 20, 30], [11, 21, 31])
    targets = pd.Series([1.0, 1.0, 0.0], index=data.index)
    result = run_backtest(data, targets, assumptions())
    assert result.fills[0].timestamp == data.index[1]
    assert result.fills[0].reference_price == 20
    assert result.position_curve.iloc[0] == 0


def test_future_signal_cannot_execute_on_same_bar() -> None:
    data = bars([10, 20, 30])
    targets = pd.Series([0.0, 1.0, 0.0], index=data.index)
    result = run_backtest(data, targets, assumptions())
    assert [fill.timestamp for fill in result.fills] == [data.index[2]]


def test_fee_and_slippage_reduce_round_trip_equity() -> None:
    data = bars([10, 20, 30])
    targets = pd.Series([1.0, 0.0, 0.0], index=data.index)
    result = run_backtest(
        data,
        targets,
        assumptions(commission_bps=10.0, slippage_bps=20.0),
    )
    buy_fill = 20.0 * 1.002
    quantity = 1000.0 / (buy_fill * 1.001)
    expected = quantity * (30.0 * 0.998) * (1 - 0.001)
    assert result.final_equity == pytest.approx(expected)
    assert len(result.fills) == 2
    assert result.fills[0].side == "BUY"
    assert result.fills[1].side == "SELL"
    assert result.fills[1].quantity > 0


def test_percentage_allocation_preserves_unallocated_cash() -> None:
    data = bars([10, 20], [10, 20])
    targets = pd.Series([0.25, 0.25], index=data.index)
    result = run_backtest(data, targets, assumptions())
    assert result.position_curve.iloc[-1] == pytest.approx(12.5)
    assert result.cash_curve.iloc[-1] == pytest.approx(750.0)
    assert result.exposure_curve.iloc[-1] == pytest.approx(0.25)


def test_whole_share_mode_never_creates_fractional_quantity() -> None:
    data = bars([10, 30])
    targets = pd.Series([1.0, 1.0], index=data.index)
    result = run_backtest(data, targets, assumptions(allow_fractional=False))
    assert result.position_curve.iloc[-1] == 33
    assert result.cash_curve.iloc[-1] == 10


def test_repeated_identical_target_does_not_create_duplicate_order() -> None:
    data = bars([10, 20, 20, 20])
    targets = pd.Series([1.0, 1.0, 1.0, 1.0], index=data.index)
    result = run_backtest(data, targets, assumptions())
    assert len(result.fills) == 1


@pytest.mark.parametrize("invalid", [-0.01, 1.01, np.nan, np.inf])
def test_invalid_target_exposure_fails_closed(invalid: float) -> None:
    data = bars([10, 20])
    targets = pd.Series([invalid, 0.0], index=data.index)
    with pytest.raises(BacktestInputError, match="target exposure"):
        run_backtest(data, targets, assumptions())


def test_target_index_must_exactly_match_bars() -> None:
    data = bars([10, 20])
    targets = pd.Series([0.0, 1.0])
    with pytest.raises(BacktestInputError, match="index"):
        run_backtest(data, targets, assumptions())
