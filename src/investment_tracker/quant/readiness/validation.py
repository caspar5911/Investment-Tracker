from __future__ import annotations

from typing import Literal, Protocol

import numpy as np
import pandas as pd
from pydantic import ConfigDict, Field, ValidationError, model_validator

from investment_tracker.quant.backtest.engine import run_backtest
from investment_tracker.quant.backtest.models import BacktestResult, ExecutionAssumptions
from investment_tracker.quant.validation.access import SplitDefinition

from .models import FrozenReadinessModel


class ValidationBoundaryError(ValueError):
    """Raised when TRAIN state or evidence would cross into VALIDATION."""


class ValidationTargetBuilder(Protocol):
    def __call__(self, bars: pd.DataFrame) -> pd.Series: ...


class ValidationWarmupPolicy(FrozenReadinessModel):
    schema_version: Literal["PHASE4-VALIDATION-WARMUP-v1"] = (
        "PHASE4-VALIDATION-WARMUP-v1"
    )
    warmup_sessions: int = Field(ge=0)
    derivation: Literal["PREDECLARED_CAUSAL_LAG_ONLY"] = (
        "PREDECLARED_CAUSAL_LAG_ONLY"
    )
    performance_fields_used: Literal[False] = False
    fitting_performed: Literal[False] = False
    calibration_performed: Literal[False] = False
    selection_performed: Literal[False] = False


class ValidationResetState(FrozenReadinessModel):
    schema_version: Literal["PHASE4-VALIDATION-RESET-v1"] = (
        "PHASE4-VALIDATION-RESET-v1"
    )
    initial_cash: float = Field(gt=0)
    positions: dict[str, float] = Field(default_factory=dict, max_length=0)
    pending_orders: tuple[object, ...] = Field(default=(), max_length=0)
    turnover: Literal[0.0] = 0.0
    realized_pnl: Literal[0.0] = 0.0
    cost_basis: dict[str, float] = Field(default_factory=dict, max_length=0)
    inherited_train_state: Literal[False] = False


class ValidationExecutionInputs(FrozenReadinessModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    schema_version: Literal["PHASE4-VALIDATION-EXECUTION-INPUTS-v1"] = (
        "PHASE4-VALIDATION-EXECUTION-INPUTS-v1"
    )
    warmup_policy: ValidationWarmupPolicy
    indicator_warmup: pd.DataFrame
    execution_bars: pd.DataFrame
    scored_targets: pd.Series
    reset_state: ValidationResetState
    selection_inputs: tuple[object, ...] = Field(default=(), max_length=0)

    @model_validator(mode="after")
    def validate_boundary(self) -> "ValidationExecutionInputs":
        if not isinstance(self.indicator_warmup.index, pd.DatetimeIndex):
            raise ValueError("indicator warm-up requires a timestamp index")
        if not isinstance(self.execution_bars.index, pd.DatetimeIndex):
            raise ValueError("VALIDATION execution requires a timestamp index")
        if self.execution_bars.empty:
            raise ValueError("VALIDATION execution bars must not be empty")
        if len(self.indicator_warmup) != self.warmup_policy.warmup_sessions:
            raise ValueError("indicator warm-up count differs from policy")
        if len(self.indicator_warmup) and not (
            self.indicator_warmup.index[-1] < self.execution_bars.index[0]
        ):
            raise ValueError("indicator warm-up must be strictly before VALIDATION")
        if not self.execution_bars.index.equals(self.scored_targets.index):
            raise ValueError("scored targets must be VALIDATION-only")
        if (
            not self.execution_bars.index.is_monotonic_increasing
            or self.execution_bars.index.has_duplicates
        ):
            raise ValueError("VALIDATION sessions must be unique and increasing")
        targets = self.scored_targets.to_numpy(dtype=float)
        if (
            not np.isfinite(targets).all()
            or (targets < 0.0).any()
            or (targets > 1.0).any()
        ):
            raise ValueError("VALIDATION targets must be finite and within [0, 1]")
        return self


def _validate_bars(bars: pd.DataFrame) -> None:
    if not isinstance(bars, pd.DataFrame) or bars.empty:
        raise ValidationBoundaryError("bars must be a non-empty DataFrame")
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise ValidationBoundaryError("bars require a timestamp index")
    if bars.index.has_duplicates or not bars.index.is_monotonic_increasing:
        raise ValidationBoundaryError("bar sessions must be unique and increasing")


def _reject_stateful_builder(target_builder: ValidationTargetBuilder) -> None:
    if not callable(target_builder):
        raise ValidationBoundaryError("target builder must be callable")
    for method_name in ("fit", "calibrate", "select"):
        if callable(getattr(target_builder, method_name, None)):
            raise ValidationBoundaryError(
                f"target builder cannot expose {method_name}"
            )


def _make_values_read_only(frame: pd.DataFrame) -> pd.DataFrame:
    frozen = frame.copy(deep=True)
    for block in frozen._mgr.blocks:
        block.values.flags.writeable = False
    return frozen


def prepare_validation_inputs(
    bars: pd.DataFrame,
    target_builder: ValidationTargetBuilder,
    split: SplitDefinition,
    warmup_sessions: int,
    initial_cash: float,
) -> ValidationExecutionInputs:
    _validate_bars(bars)
    _reject_stateful_builder(target_builder)
    if isinstance(warmup_sessions, bool) or not isinstance(warmup_sessions, int):
        raise ValidationBoundaryError("warm-up sessions must be a predeclared integer")
    try:
        policy = ValidationWarmupPolicy(warmup_sessions=warmup_sessions)
        reset = ValidationResetState(initial_cash=initial_cash)
    except ValidationError as exc:
        raise ValidationBoundaryError("invalid validation policy or reset state") from exc

    dates = bars.index.date
    train_mask = (dates >= split.train_start) & (dates <= split.train_end)
    validation_mask = (
        (dates >= split.validation_start) & (dates <= split.validation_end)
    )
    accepted_mask = train_mask | validation_mask
    if not bool(accepted_mask.all()):
        raise ValidationBoundaryError("bars contain rows outside TRAIN and VALIDATION")
    train_bars = bars.loc[train_mask]
    execution_bars = bars.loc[validation_mask].copy(deep=True)
    if execution_bars.empty:
        raise ValidationBoundaryError("VALIDATION contains no actual sessions")
    if warmup_sessions > len(train_bars):
        raise ValidationBoundaryError("declared warm-up exceeds available TRAIN sessions")
    indicator_warmup = train_bars.tail(warmup_sessions).copy(deep=True)
    if warmup_sessions == 0:
        indicator_warmup = train_bars.iloc[0:0].copy(deep=True)
    builder_bars = pd.concat((indicator_warmup, execution_bars), axis=0)
    try:
        targets = target_builder(builder_bars.copy(deep=True))
    except Exception as exc:
        raise ValidationBoundaryError("target builder failed") from exc
    if not isinstance(targets, pd.Series) or not targets.index.equals(
        builder_bars.index
    ):
        raise ValidationBoundaryError(
            "target builder must return targets for the causal input index"
        )
    scored_targets = targets.loc[execution_bars.index].astype(float).copy(deep=True)
    indicator_warmup = _make_values_read_only(indicator_warmup)
    try:
        return ValidationExecutionInputs(
            warmup_policy=policy,
            indicator_warmup=indicator_warmup,
            execution_bars=execution_bars,
            scored_targets=scored_targets,
            reset_state=reset,
            selection_inputs=(),
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValidationBoundaryError("invalid VALIDATION execution inputs") from exc


def _revalidate_inputs(
    inputs: ValidationExecutionInputs,
) -> ValidationExecutionInputs:
    try:
        raw_policy = {
            name: getattr(inputs.warmup_policy, name)
            for name in ValidationWarmupPolicy.model_fields
        }
        raw_reset = {
            name: getattr(inputs.reset_state, name)
            for name in ValidationResetState.model_fields
        }
        raw_inputs = {
            name: getattr(inputs, name)
            for name in ValidationExecutionInputs.model_fields
        }
        raw_inputs["warmup_policy"] = ValidationWarmupPolicy.model_validate(raw_policy)
        raw_inputs["reset_state"] = ValidationResetState.model_validate(raw_reset)
        return ValidationExecutionInputs.model_validate(raw_inputs)
    except (AttributeError, TypeError, ValueError, ValidationError) as exc:
        raise ValidationBoundaryError("VALIDATION inputs violate reset boundary") from exc


def run_validation_from_reset(
    inputs: ValidationExecutionInputs,
    assumptions: ExecutionAssumptions,
) -> BacktestResult:
    verified = _revalidate_inputs(inputs)
    if assumptions.initial_capital != verified.reset_state.initial_cash:
        raise ValidationBoundaryError(
            "backtest initial capital must match VALIDATION reset cash"
        )
    return run_backtest(
        verified.execution_bars.copy(deep=True),
        verified.scored_targets.copy(deep=True),
        assumptions,
    )
