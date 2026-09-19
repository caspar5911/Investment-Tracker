from __future__ import annotations

from datetime import date
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.governance import assert_symbol_allowed


class DataStage(StrEnum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    FINAL_HOLDOUT = "FINAL_HOLDOUT"


class ResearchStage(StrEnum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"


class HoldoutAccessError(PermissionError):
    pass


class StageDataStore(Protocol):
    def load(self, symbol: str, stage: DataStage) -> Any: ...


class SplitDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1)
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    final_holdout_start: date
    final_holdout_end: date
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def create(cls, **values: object) -> "SplitDefinition":
        payload = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return cls(**values, digest=sha256(payload).hexdigest())

    @model_validator(mode="after")
    def validate_periods_and_digest(self) -> "SplitDefinition":
        if not (
            self.train_start <= self.train_end
            < self.validation_start <= self.validation_end
            < self.final_holdout_start <= self.final_holdout_end
        ):
            raise ValueError("TRAIN, VALIDATION and FINAL_HOLDOUT must be chronological and disjoint")
        values = self.model_dump(mode="json", exclude={"digest"})
        expected = sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if self.digest != expected:
            raise ValueError("split definition digest mismatch")
        return self

    def stage_for(self, value: date) -> DataStage | None:
        if self.train_start <= value <= self.train_end:
            return DataStage.TRAIN
        if self.validation_start <= value <= self.validation_end:
            return DataStage.VALIDATION
        if self.final_holdout_start <= value <= self.final_holdout_end:
            return DataStage.FINAL_HOLDOUT
        return None


class ResearchDataView:
    """Restricted view whose public stage type excludes FINAL_HOLDOUT."""

    def __init__(self, store: StageDataStore) -> None:
        self._store = store

    def load(self, symbol: str, stage: ResearchStage) -> Any:
        normalized = assert_symbol_allowed(symbol)
        if stage not in (ResearchStage.TRAIN, ResearchStage.VALIDATION):
            raise HoldoutAccessError("FINAL_HOLDOUT is sealed from research APIs")
        return self._store.load(normalized, DataStage(stage.value))
