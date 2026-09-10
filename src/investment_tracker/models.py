from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .governance import FROZEN_VERSIONS, assert_symbol_allowed


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrozenVersionsModel(StrictModel):
    tpc: str
    replay: str
    calc: str
    robust: str

    @model_validator(mode="after")
    def require_frozen_versions(self) -> "FrozenVersionsModel":
        if self.model_dump() != FROZEN_VERSIONS.as_dict():
            raise ValueError("version set does not match frozen tracker versions")
        return self


class InputSnapshot(StrictModel):
    snapshot_id: str = Field(min_length=1)
    dispatch_run_id: str = Field(min_length=1)
    versions: FrozenVersionsModel
    asset: str
    start_date: date
    end_date: date
    spy_digest: str = Field(min_length=1)
    dq_refs: list[str]
    phase_matrix_state: str = Field(min_length=1)
    input_digests: dict[str, str]
    dispatch_timestamp: datetime
    locked_holdout_excluded: Literal[True]

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        return assert_symbol_allowed(value)

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
    versions: FrozenVersionsModel
    source_provider: Literal["Alpaca"]
    source_feed: Literal["SIP"]
    input_refs: list[str]
    output_digests: dict[str, str]
    locked_holdout_excluded: Literal[True]
    completion_status: Literal["READY_FOR_COORDINATOR_REVIEW"]

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        return assert_symbol_allowed(value)

    @model_validator(mode="after")
    def validate_scope(self) -> "WorkerManifest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if not self.input_snapshot_digests:
            raise ValueError("input_snapshot_digests must not be empty")
        return self
