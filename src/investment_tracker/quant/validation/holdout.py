from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.governance import assert_symbol_allowed

from .access import DataStage, StageDataStore


class HoldoutReuseError(RuntimeError):
    pass


class FrozenCandidateManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["FROZEN-CANDIDATE-MANIFEST-v1"] = "FROZEN-CANDIDATE-MANIFEST-v1"
    status: Literal["FROZEN_CANDIDATE"] = "FROZEN_CANDIDATE"
    candidate_id: str = Field(min_length=1)
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
    frozen_at: datetime
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def create(cls, **values: object) -> "FrozenCandidateManifest":
        base = {
            "schema_version": "FROZEN-CANDIDATE-MANIFEST-v1",
            "status": "FROZEN_CANDIDATE",
            **values,
        }
        digest = _digest(base)
        return cls(**base, digest=digest)

    @model_validator(mode="after")
    def validate_complete_identity(self) -> "FrozenCandidateManifest":
        if self.frozen_at.tzinfo is None or self.frozen_at.utcoffset() is None:
            raise ValueError("frozen_at must be timezone-aware")
        if not self.strategy_parameters or not self.data_manifest_hashes:
            raise ValueError("strategy parameters and data manifests are required")
        for symbol, digest in self.data_manifest_hashes.items():
            assert_symbol_allowed(symbol)
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError(f"invalid data manifest hash for {symbol}")
        expected = _digest(self.model_dump(mode="json", exclude={"digest"}))
        if self.digest != expected:
            raise ValueError("candidate manifest digest mismatch")
        return self


class HoldoutEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_digest: str
    status: Literal["FROZEN_CANDIDATE_NOT_PRODUCTION_APPROVED"]
    metrics: dict[str, float | int | str | None]


class SealedHoldoutEvaluator:
    def __init__(
        self,
        store: StageDataStore,
        evaluator: Callable[[FrozenCandidateManifest, Mapping[str, Any]], Mapping[str, float | int | str | None]],
    ) -> None:
        self._store = store
        self._evaluator = evaluator

    def evaluate(self, candidate: FrozenCandidateManifest, audit_directory: Path) -> HoldoutEvaluationResult:
        symbols = tuple(assert_symbol_allowed(symbol) for symbol in candidate.data_manifest_hashes)
        audit_directory = Path(audit_directory)
        started_path = audit_directory / f"{candidate.digest}.started.json"
        result_path = audit_directory / f"{candidate.digest}.result.json"
        audit_directory.mkdir(parents=True, exist_ok=True)
        started = {
            "candidate_digest": candidate.digest,
            "status": "FINAL_HOLDOUT_EVALUATION_STARTED",
            "frozen_at": candidate.frozen_at.isoformat(),
        }
        try:
            with started_path.open("x", encoding="utf-8") as handle:
                json.dump(started, handle, sort_keys=True, separators=(",", ":"))
        except FileExistsError as exc:
            raise HoldoutReuseError(f"candidate final holdout already consumed: {candidate.digest}") from exc

        data_by_symbol = {
            symbol: self._store.load(symbol, DataStage.FINAL_HOLDOUT)
            for symbol in symbols
        }
        metrics = dict(self._evaluator(candidate, data_by_symbol))
        for name, value in metrics.items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"holdout metric must be finite or None: {name}")
        result = HoldoutEvaluationResult(
            candidate_digest=candidate.digest,
            status="FROZEN_CANDIDATE_NOT_PRODUCTION_APPROVED",
            metrics=metrics,
        )
        with result_path.open("x", encoding="utf-8") as handle:
            json.dump(result.model_dump(mode="json"), handle, sort_keys=True, separators=(",", ":"))
        return result


def _digest(payload: object) -> str:
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
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    return value
