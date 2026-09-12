from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from investment_tracker.quant.backtest.models import ExecutionAssumptions
from investment_tracker.quant.readiness.validation import (
    ValidationBoundaryError,
    ValidationExecutionInputs,
    ValidationResetState,
    ValidationWarmupPolicy,
    prepare_validation_inputs,
    run_validation_from_reset,
)
from investment_tracker.quant.validation.access import SplitDefinition


def train_index() -> pd.DatetimeIndex:
    return pd.date_range("2023-12-26", periods=4, freq="B", tz="UTC")


def validation_index() -> pd.DatetimeIndex:
    return pd.date_range("2024-01-02", periods=4, freq="B", tz="UTC")


def bars_fixture(*, mutate_before_warmup: bool = False) -> pd.DataFrame:
    index = train_index().append(validation_index())
    closes = np.asarray([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0])
    if mutate_before_warmup:
        closes[:2] = [1000.0, 2000.0]
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes + 1.0,
            "low": closes - 1.0,
            "close": closes,
            "volume": np.full(len(index), 1000.0),
        },
        index=index,
    )


def split_fixture() -> SplitDefinition:
    return SplitDefinition.create(
        version="PHASE4-TEST-SPLIT-v1",
        train_start=date(2023, 12, 26),
        train_end=date(2023, 12, 29),
        validation_start=date(2024, 1, 1),
        validation_end=date(2024, 1, 5),
        final_holdout_start=date(2024, 1, 8),
        final_holdout_end=date(2024, 1, 12),
    )


def assumptions() -> ExecutionAssumptions:
    return ExecutionAssumptions(
        initial_capital=100_000.0,
        commission_bps=0.0,
        slippage_bps=0.0,
        allow_fractional=True,
    )


def rolling_target_builder(window: int):
    def build_targets(bars: pd.DataFrame) -> pd.Series:
        close = bars["close"].astype(float)
        average = close.rolling(window=window, min_periods=window).mean()
        return (close >= average).fillna(False).astype(float)

    return build_targets


def fixed_validation_targets(
    *,
    first: float = 1.0,
    last: float = 0.0,
):
    def build_targets(bars: pd.DataFrame) -> pd.Series:
        values = np.zeros(len(bars), dtype=float)
        values[-len(validation_index())] = first
        values[-1] = last
        return pd.Series(values, index=bars.index)

    return build_targets


def prepare_fixture_inputs(
    *,
    mutate_before_warmup: bool = False,
    first_validation_target: float = 1.0,
    last_validation_target: float = 0.0,
) -> ValidationExecutionInputs:
    return prepare_validation_inputs(
        bars=bars_fixture(mutate_before_warmup=mutate_before_warmup),
        target_builder=fixed_validation_targets(
            first=first_validation_target,
            last=last_validation_target,
        ),
        split=split_fixture(),
        warmup_sessions=2,
        initial_cash=100_000.0,
    )


def test_train_rows_are_visible_only_to_lagged_indicator_initialization() -> None:
    inputs = prepare_validation_inputs(
        bars=bars_fixture(),
        target_builder=rolling_target_builder(window=3),
        split=split_fixture(),
        warmup_sessions=2,
        initial_cash=100_000.0,
    )

    assert tuple(inputs.indicator_warmup.index) == tuple(train_index()[-2:])
    assert tuple(inputs.execution_bars.index) == tuple(validation_index())
    assert tuple(inputs.scored_targets.index) == tuple(validation_index())
    assert inputs.selection_inputs == ()
    assert inputs.warmup_policy.performance_fields_used is False


def test_returned_indicator_warmup_values_are_read_only() -> None:
    inputs = prepare_fixture_inputs()

    with pytest.raises(ValueError, match="read-only"):
        inputs.indicator_warmup.iloc[0, 0] = -1.0


def test_prices_before_declared_causal_warmup_cannot_change_validation_result() -> None:
    original = prepare_validation_inputs(
        bars=bars_fixture(),
        target_builder=rolling_target_builder(window=3),
        split=split_fixture(),
        warmup_sessions=2,
        initial_cash=100_000.0,
    )
    mutated = prepare_validation_inputs(
        bars=bars_fixture(mutate_before_warmup=True),
        target_builder=rolling_target_builder(window=3),
        split=split_fixture(),
        warmup_sessions=2,
        initial_cash=100_000.0,
    )

    assert original.scored_targets.equals(mutated.scored_targets)
    assert original.reset_state == mutated.reset_state


def test_validation_portfolio_resets_and_contains_no_train_pnl() -> None:
    prepared = prepare_fixture_inputs()
    result = run_validation_from_reset(prepared, assumptions())

    assert prepared.reset_state.positions == {}
    assert prepared.reset_state.pending_orders == ()
    assert prepared.reset_state.turnover == 0.0
    assert prepared.reset_state.realized_pnl == 0.0
    assert prepared.reset_state.cost_basis == {}
    assert result.equity_curve.iloc[0] == assumptions().initial_capital
    assert result.cash_curve.iloc[0] == assumptions().initial_capital
    assert result.position_curve.iloc[0] == 0.0
    assert all(fill.timestamp in validation_index() for fill in result.fills)
    assert result.fills[0].timestamp == validation_index()[1]


def test_first_scored_signal_executes_only_on_next_validation_session() -> None:
    inputs = prepare_fixture_inputs(first_validation_target=1.0)

    assert inputs.scored_targets.index[0] == validation_index()[0]
    result = run_validation_from_reset(inputs, assumptions())
    assert result.fills[0].timestamp == validation_index()[1]


def test_last_validation_signal_without_next_session_does_not_execute() -> None:
    inputs = prepare_fixture_inputs(
        first_validation_target=0.0,
        last_validation_target=1.0,
    )
    result = run_validation_from_reset(inputs, assumptions())

    assert result.fills == ()


@pytest.mark.parametrize("method_name", ["fit", "calibrate", "select"])
def test_stateful_or_selecting_target_builders_are_rejected(method_name: str) -> None:
    class StatefulBuilder:
        def __call__(self, bars: pd.DataFrame) -> pd.Series:
            return pd.Series(0.0, index=bars.index)

    builder = StatefulBuilder()
    setattr(builder, method_name, lambda values: values)

    with pytest.raises(ValidationBoundaryError, match=method_name):
        prepare_validation_inputs(
            bars=bars_fixture(),
            target_builder=builder,
            split=split_fixture(),
            warmup_sessions=2,
            initial_cash=100_000.0,
        )


def test_train_dated_scored_targets_fail_before_backtest() -> None:
    inputs = prepare_fixture_inputs()
    train_dated = pd.Series(0.0, index=train_index())
    bypassed = inputs.model_copy(update={"scored_targets": train_dated})

    with pytest.raises(ValidationBoundaryError, match="VALIDATION"):
        run_validation_from_reset(bypassed, assumptions())


def test_warmup_policy_rejects_performance_derived_fields() -> None:
    with pytest.raises(ValidationError, match="performance_field"):
        ValidationWarmupPolicy(
            warmup_sessions=2,
            performance_field="sharpe",
        )


@pytest.mark.parametrize(
    "inherited",
    [
        {"positions": {"SPY": 1.0}},
        {"pending_orders": ("BUY",)},
        {"turnover": 1.0},
        {"realized_pnl": 1.0},
        {"cost_basis": {"SPY": 100.0}},
        {"cash": 50_000.0},
    ],
)
def test_reset_state_rejects_inherited_portfolio_fields(
    inherited: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ValidationResetState(initial_cash=100_000.0, **inherited)


def test_execution_inputs_reject_train_returns_as_validation_metrics() -> None:
    prepared = prepare_fixture_inputs()
    values = {
        field_name: getattr(prepared, field_name)
        for field_name in ValidationExecutionInputs.model_fields
    }
    values["validation_metrics"] = {"train_returns": [0.1]}

    with pytest.raises(ValidationError, match="validation_metrics"):
        ValidationExecutionInputs.model_validate(values)
