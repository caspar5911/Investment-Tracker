from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict, BaseModel, Field, model_validator


class FrozenDataModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DataRequest(FrozenDataModel):
    provider: Literal["MOOMOO"] = "MOOMOO"
    symbol: str = Field(min_length=1)
    interval: Literal["1d"] = "1d"
    adjustment: Literal["QFQ"] = "QFQ"
    start: date
    end: date

    @model_validator(mode="after")
    def validate_dates(self) -> "DataRequest":
        if self.end < self.start:
            raise ValueError("end must be on or after start")
        return self


class DatasetMetadata(FrozenDataModel):
    schema_version: Literal["DATASET-METADATA-v1"] = "DATASET-METADATA-v1"
    provider: Literal["MOOMOO"]
    provider_api_version: str | None
    symbol: str
    interval: Literal["1d"]
    adjustment: Literal["QFQ"]
    requested_start: date
    requested_end: date
    retrieved_at: datetime
    first_timestamp: datetime
    last_timestamp: datetime
    row_count: int = Field(gt=0)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_status: Literal["CLEAN"] = "CLEAN"
