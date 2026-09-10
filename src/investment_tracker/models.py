from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .governance import FROZEN_VERSIONS, assert_symbol_allowed


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _validate_versions(value: dict[str, str]) -> dict[str, str]:
    if value != FROZEN_VERSIONS.as_dict():
        raise ValueError("version set does not match frozen tracker versions")
    return value


def _allowed_asset(value: str) -> str:
    return assert_symbol_allowed(value)


class InputSnapshot(StrictModel):
    snapshot_id: str = Field(min_length=1)
    dispatch_run_id: str = Field(min_length=1)
    versions: dict[str, str]
    asset: str
    start_date: date
    end_date: date
    spy_digest: str = Field(min_length=1)
    dq_refs: list[str]
    phase_matrix_state: str = Field(min_length=1)
    input_digests: dict[str, str]
    dispatch_timestamp: datetime
    locked_holdout_excluded: Literal[True]

    @field_validator("versions")
    @classmethod
    def validate_versions(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_versions(value)

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        return _allowed_asset(value)

    @model_validator(mode="after")
    def validate_scope(self) -> "InputSnapshot":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if not self.input_digests:
            raise ValueError("input_digests must not be empty")
        return self


class WorkerManifest(StrictModel):
    role: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    input_snapshot_id: str = Field(min_length=1)
    input_snapshot_digests: dict[str, str]
    asset: str
    start_date: date
    end_date: date
    versions: dict[str, str]
    source_provider: Literal["Alpaca"]
    source_feed: Literal["SIP"]
    input_refs: list[str]
    output_digests: dict[str, str]
    locked_holdout_excluded: Literal[True]
    completion_status: Literal["READY_FOR_COORDINATOR_REVIEW"]

    @field_validator("versions")
    @classmethod
    def validate_versions(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_versions(value)

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        return _allowed_asset(value)

    @model_validator(mode="after")
    def validate_scope(self) -> "WorkerManifest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if not self.input_snapshot_digests:
            raise ValueError("input_snapshot_digests must not be empty")
        return self


class MarketBar(StrictModel):
    asset: str
    bar_date: date
    open_raw: Decimal
    high_raw: Decimal
    low_raw: Decimal
    close_raw: Decimal
    volume_raw: int
    trade_count_raw: int
    vwap_raw: Decimal
    provider: Literal["Alpaca"]
    feed: Literal["SIP"]
    ingestion_run_id: str
    split_factor: Decimal
    open_norm: Decimal
    high_norm: Decimal
    low_norm: Decimal
    close_norm: Decimal
    range_usable: bool
    close_usable: bool
    dq_refs: str | None
    source_window: str
    recorded_at_utc: str
    bar_key: str
    source_digest: str
    cache_status: str
    normalization_version: Literal["NORM-v1"]

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        return _allowed_asset(value)


class ReplayDailyRow(StrictModel):
    asset: str
    bar_date: date
    spec_version: Literal["REPLAY-v1.0"]
    close_norm: Decimal
    sma200: Decimal | None
    prior60_high: Decimal | None
    pullback_pct: Decimal | None
    prior_close: Decimal | None
    sma5: Decimal | None
    ret20: Decimal | None
    spy_ret20: Decimal | None
    distance_to_60d_high: Decimal | None
    trend_gate: bool | None
    pullback_gate: bool | None
    stabilization_gate: bool | None
    rs_gate: bool | None
    chase_gate: bool | None
    signal_state: Literal["ACCUMULATE", "WATCH", "WAIT", "TRIM/AVOID", "ABSTAIN"]
    episode_start: bool
    data_status: str
    calculation_run_id: str
    evidence_ref: str
    calculation_version: Literal["CALC-v1.2"]

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        return _allowed_asset(value)


class EpisodeOutcomeRow(StrictModel):
    episode_id: str
    asset: str
    signal_start_date: date
    signal_end_date: date
    signal_days: int
    entry_date: date
    entry_open: Decimal
    horizon_td: Literal[1, 5, 20, 60, 120, 250]
    asset_return: Decimal | None
    spy_return: Decimal | None
    excess_spy: Decimal | None
    cash_return: Decimal | None
    excess_cash: Decimal | None
    mae: Decimal | None
    mfe: Decimal | None
    max_drawdown: None = None
    friction_bps: Literal[0, 10, 25]
    return_net: Decimal | None
    dq_status: str
    calculation_run_id: str
    calculation_version: Literal["CALC-v1.2"]

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        return _allowed_asset(value)


class BaselineRow(StrictModel):
    baseline_record_id: str
    asset: str
    baseline_type: Literal["BUY_AND_HOLD", "MONTHLY_DCA", "SIMPLE_DIP"]
    signal_start_date: date | None
    signal_end_date: date | None
    signal_days: int | None
    entry_date: date | None
    entry_open: Decimal | None
    horizon_td: Literal[1, 5, 20, 60, 120, 250] | None
    asset_return: Decimal | None
    spy_return: Decimal | None
    excess_spy: Decimal | None
    cash_return: Decimal | None
    excess_cash: Decimal | None
    mae: Decimal | None
    mfe: Decimal | None
    friction_bps: Literal[0, 10, 25]
    return_net: Decimal | None
    terminal_value: Decimal | None
    contributed_capital: Decimal | None
    money_weighted_return: Decimal | None
    dq_status: str
    calculation_run_id: str
    calculation_version: Literal["CALC-v1.2"]

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        return _allowed_asset(value)
