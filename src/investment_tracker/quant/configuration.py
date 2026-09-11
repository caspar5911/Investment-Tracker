from __future__ import annotations

from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from investment_tracker.governance import assert_symbol_allowed


class StrictQuantModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UniverseConfig(StrictQuantModel):
    version: Literal["UNIVERSE-v1"]
    symbols: tuple[str, ...] = Field(min_length=1)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(assert_symbol_allowed(value) for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("universe symbols must be unique")
        return normalized


class BacktestConfig(StrictQuantModel):
    version: Literal["QUANT-BACKTEST-v1"]
    initial_capital: float = Field(gt=0)
    allocation: float = Field(gt=0, le=1)
    commission_bps: float = Field(ge=0)
    slippage_bps: float = Field(ge=0)
    allow_fractional: bool


class ValidationConfig(StrictQuantModel):
    version: Literal["QUANT-VALIDATION-v1"]
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    final_holdout_start: date
    final_holdout_end: date
    max_candidates_per_family: int = Field(gt=0, le=500)
    patience: int = Field(gt=0, le=50)

    @model_validator(mode="after")
    def validate_chronology(self) -> "ValidationConfig":
        boundaries = (
            self.train_start,
            self.train_end,
            self.validation_start,
            self.validation_end,
            self.final_holdout_start,
            self.final_holdout_end,
        )
        if list(boundaries) != sorted(boundaries):
            raise ValueError("train, validation and final holdout dates must be chronological")
        if self.train_end >= self.validation_start:
            raise ValueError("train and validation periods must be disjoint")
        if self.validation_end >= self.final_holdout_start:
            raise ValueError("validation and final holdout periods must be disjoint")
        return self


class QuantConfig(StrictQuantModel):
    universe: UniverseConfig
    backtest: BacktestConfig
    validation: ValidationConfig


def _load_yaml(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"configuration must be a mapping: {path}")
    return payload


def load_quant_config(directory: Path) -> QuantConfig:
    return QuantConfig(
        universe=UniverseConfig.model_validate(_load_yaml(directory / "universe.yaml")),
        backtest=BacktestConfig.model_validate(_load_yaml(directory / "backtest.yaml")),
        validation=ValidationConfig.model_validate(_load_yaml(directory / "validation.yaml")),
    )


def load_default_config() -> QuantConfig:
    defaults = files("investment_tracker.quant").joinpath("defaults")
    return QuantConfig(
        universe=UniverseConfig.model_validate(yaml.safe_load(defaults.joinpath("universe.yaml").read_text(encoding="utf-8"))),
        backtest=BacktestConfig.model_validate(yaml.safe_load(defaults.joinpath("backtest.yaml").read_text(encoding="utf-8"))),
        validation=ValidationConfig.model_validate(yaml.safe_load(defaults.joinpath("validation.yaml").read_text(encoding="utf-8"))),
    )
