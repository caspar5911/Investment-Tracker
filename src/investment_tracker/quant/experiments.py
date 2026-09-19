from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from investment_tracker.governance import assert_symbol_allowed


class ArtifactExistsError(FileExistsError):
    pass


class FrozenArtifactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResearchCandidateManifest(FrozenArtifactModel):
    schema_version: Literal["RESEARCH-CANDIDATE-MANIFEST-v1"] = "RESEARCH-CANDIDATE-MANIFEST-v1"
    status: Literal["RESEARCH_ONLY"] = "RESEARCH_ONLY"
    candidate_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    strategy_family: str = Field(min_length=1)
    strategy_code_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategy_parameters: dict[str, int | float | str | bool]
    universe_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_manifest_hashes: dict[str, str]
    split_definition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    engine_version: str = Field(min_length=1)
    fee_model: dict[str, int | float | str | bool]
    slippage_model: dict[str, int | float | str | bool]
    execution_convention: str = Field(min_length=1)
    dependency_lock_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    created_at: datetime
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def create(cls, **values: object) -> "ResearchCandidateManifest":
        payload = {
            "schema_version": "RESEARCH-CANDIDATE-MANIFEST-v1",
            "status": "RESEARCH_ONLY",
            **values,
        }
        return cls(**payload, digest=artifact_digest(payload))

    @model_validator(mode="after")
    def validate_identity(self) -> "ResearchCandidateManifest":
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if not self.strategy_parameters or not self.data_manifest_hashes:
            raise ValueError("strategy parameters and data manifests are required")
        for symbol, digest in self.data_manifest_hashes.items():
            assert_symbol_allowed(symbol)
            _require_hash(digest, f"data manifest for {symbol}")
        expected = artifact_digest(self.model_dump(mode="json", exclude={"digest"}))
        if self.digest != expected:
            raise ValueError("research candidate digest mismatch")
        return self


class ExperimentRecord(FrozenArtifactModel):
    schema_version: Literal["QUANT-EXPERIMENT-v1"] = "QUANT-EXPERIMENT-v1"
    experiment_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    status: Literal["RESEARCH_ONLY"]
    candidate_manifest: ResearchCandidateManifest
    symbols: tuple[str, ...] = Field(min_length=1)
    train_period: tuple[date, date]
    validation_period: tuple[date, date]
    metrics: dict[str, float | int | str | None]
    validation_metrics: dict[str, float | int | str | None]
    score: float | None
    accepted: bool
    reason: str = Field(min_length=1)
    stop_reason: str = Field(min_length=1)
    recorded_at: datetime

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(assert_symbol_allowed(value) for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("experiment symbols must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_record(self) -> "ExperimentRecord":
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.train_period[0] > self.train_period[1] or self.validation_period[0] > self.validation_period[1]:
            raise ValueError("experiment date ranges must be ordered")
        if self.train_period[1] >= self.validation_period[0]:
            raise ValueError("train and validation periods must be disjoint")
        for metrics in (self.metrics, self.validation_metrics):
            for name, value in metrics.items():
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError(f"metric must be finite or None: {name}")
        return self


class ExperimentStore:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def append(self, record: ExperimentRecord) -> Path:
        symbols = tuple(assert_symbol_allowed(symbol) for symbol in record.symbols)
        if symbols != record.symbols:
            raise ValueError("experiment symbols must be normalized")
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{record.experiment_id}.json"
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(
                    record.model_dump(mode="json"),
                    handle,
                    sort_keys=True,
                    separators=(",", ":"),
                )
        except FileExistsError as exc:
            raise ArtifactExistsError(f"experiment already exists: {record.experiment_id}") from exc
        return path


def artifact_digest(payload: object) -> str:
    return sha256(
        json.dumps(
            _canonicalize(payload),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _canonicalize(value: object) -> object:
    if isinstance(value, datetime):
        rendered = value.astimezone(timezone.utc).isoformat()
        return rendered.replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    return value


def _require_hash(value: str, name: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"invalid SHA-256 for {name}")
