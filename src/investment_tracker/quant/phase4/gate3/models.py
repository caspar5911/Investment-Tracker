from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.quant.phase4.preregistration.canonical import artifact_envelope_identity


class Gate3AuthorityError(RuntimeError):
    """The pre-campaign Gate 3 authority layer failed closed."""


class FrozenGate3Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactIdentity(FrozenGate3Model):
    kind: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_identity(self) -> "ArtifactIdentity":
        posix = PurePosixPath(self.path)
        windows = PureWindowsPath(self.path)
        if (
            "\\" in self.path
            or self.path.startswith("/")
            or windows.drive
            or windows.is_absolute()
            or any(part in {"", ".", ".."} for part in posix.parts)
        ):
            raise ValueError("artifact path must be repository-relative POSIX")
        if self.sha256 != artifact_envelope_identity(
            content_sha256=self.content_sha256, kind=self.kind, path=self.path
        ):
            raise ValueError("artifact envelope identity mismatch")
        return self


class DataPartitionIdentity(FrozenGate3Model):
    stage: Literal["TRAIN", "VALIDATION"]
    actual_start: str
    actual_end: str
    row_count: int = Field(gt=0)
    sessions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_content_sha256_by_symbol: tuple[tuple[str, str], ...] = Field(
        min_length=8, max_length=8
    )
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SafetyState(FrozenGate3Model):
    candidate_executed: Literal[False] = False
    validation_candidate_performance_accessed: Literal[False] = False
    candidate_metrics_calculated: Literal[False] = False
    benchmark_performance_calculated: Literal[False] = False
    candidates_ranked: Literal[False] = False
    survivor_selected: Literal[False] = False
    strategy_search_executed: Literal[False] = False
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()
    provider_calls: Literal[0] = 0
    downloads: Literal[0] = 0
    live_trading_capability: Literal[False] = False
    phase4_trials_consumed: Literal[0] = 0


class Gate3AuthorityManifest(FrozenGate3Model):
    schema_version: Literal["PHASE4-GATE3-AUTHORITY-MANIFEST-v1"] = (
        "PHASE4-GATE3-AUTHORITY-MANIFEST-v1"
    )
    status: Literal["GATE3_AUTHORITIES_SEALED"] = "GATE3_AUTHORITIES_SEALED"
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    gate1_manifest: ArtifactIdentity
    gate2_manifest: ArtifactIdentity
    universe_manifest: ArtifactIdentity
    split_manifest: ArtifactIdentity
    train_identity: DataPartitionIdentity
    validation_identity: DataPartitionIdentity
    fold_authority: ArtifactIdentity
    regime_authority: ArtifactIdentity
    friction_authority: Literal["BOUND"] = "BOUND"
    neighborhood_authority: Literal["BOUND"] = "BOUND"
    bootstrap_authority: Literal["BOUND"] = "BOUND"
    durability_authority: Literal["BOUND"] = "BOUND"
    candidate_population: Literal[180] = 180
    safety: SafetyState


class Gate3Preflight(FrozenGate3Model):
    fold_authority: Literal["BOUND"] = "BOUND"
    regime_authority: Literal["BOUND"] = "BOUND"
    friction_authority: Literal["BOUND"] = "BOUND"
    neighborhood_authority: Literal["BOUND"] = "BOUND"
    bootstrap_authority: Literal["BOUND"] = "BOUND"
    durability_authority: Literal["BOUND"] = "BOUND"
    gate1: Literal["VALID"] = "VALID"
    gate2: Literal["VALID"] = "VALID"
    candidate_population: Literal[180] = 180
    gate3: Literal["READY"] = "READY"
    safety: SafetyState

