from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Literal

from pydantic import Field, model_validator

from investment_tracker.governance import assert_symbol_allowed

from .experiments import (
    ArtifactExistsError,
    ExperimentRecord,
    FrozenArtifactModel,
    ResearchCandidateManifest,
    artifact_digest,
)
from .validation.holdout import FrozenCandidateManifest


class PromotionBlockedError(RuntimeError):
    pass


class PromotionGate(FrozenArtifactModel):
    research_passed: bool
    validation_passed: bool
    walk_forward_passed: bool
    robustness_passed: bool
    benchmark_passed: bool
    tests_passed: bool

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(name for name, value in self.model_dump().items() if not value)


class ValidatedSnapshot(FrozenArtifactModel):
    schema_version: Literal["VALIDATED-SNAPSHOT-v1"] = "VALIDATED-SNAPSHOT-v1"
    status: Literal["VALIDATED_SNAPSHOT"] = "VALIDATED_SNAPSHOT"
    source_experiment_id: str = Field(min_length=1)
    candidate_manifest: ResearchCandidateManifest
    promotion_gate: PromotionGate
    created_at: datetime
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def create(
        cls,
        experiment: ExperimentRecord,
        gate: PromotionGate,
    ) -> "ValidatedSnapshot":
        payload = {
            "schema_version": "VALIDATED-SNAPSHOT-v1",
            "status": "VALIDATED_SNAPSHOT",
            "source_experiment_id": experiment.experiment_id,
            "candidate_manifest": experiment.candidate_manifest,
            "promotion_gate": gate,
            "created_at": experiment.recorded_at,
        }
        return cls(**payload, digest=artifact_digest(payload))

    @model_validator(mode="after")
    def validate_snapshot(self) -> "ValidatedSnapshot":
        if self.promotion_gate.failures:
            raise ValueError("validated snapshot contains failed promotion gates")
        expected = artifact_digest(self.model_dump(mode="json", exclude={"digest"}))
        if self.digest != expected:
            raise ValueError("validated snapshot digest mismatch")
        return self

    def freeze_for_holdout(self, frozen_at: datetime) -> FrozenCandidateManifest:
        manifest = self.candidate_manifest
        return FrozenCandidateManifest.create(
            candidate_id=manifest.candidate_id,
            strategy_family=manifest.strategy_family,
            strategy_code_hash=manifest.strategy_code_hash,
            strategy_parameters=manifest.strategy_parameters,
            universe_config_hash=manifest.universe_config_hash,
            data_manifest_hashes=manifest.data_manifest_hashes,
            split_definition_hash=manifest.split_definition_hash,
            engine_version=manifest.engine_version,
            fee_model=manifest.fee_model,
            slippage_model=manifest.slippage_model,
            execution_convention=manifest.execution_convention,
            dependency_lock_hash=manifest.dependency_lock_hash,
            git_commit=manifest.git_commit,
            frozen_at=frozen_at,
        )


class BaselineRegistry:
    """Additive local registry; existing versions are never edited in place."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def add(self, snapshot: ValidatedSnapshot) -> Path:
        for symbol in snapshot.candidate_manifest.data_manifest_hashes:
            assert_symbol_allowed(symbol)
        self._root.mkdir(parents=True, exist_ok=True)
        final_path = self._root / snapshot.digest
        if final_path.exists():
            raise ArtifactExistsError(f"baseline snapshot already exists: {snapshot.digest}")
        temp_path = Path(tempfile.mkdtemp(prefix=".tmp-", dir=self._root))
        try:
            with (temp_path / "snapshot.json").open("x", encoding="utf-8") as handle:
                json.dump(snapshot.model_dump(mode="json"), handle, sort_keys=True, separators=(",", ":"))
            os.replace(temp_path, final_path)
        finally:
            if temp_path.exists():
                resolved = temp_path.resolve()
                if not resolved.is_relative_to(self._root.resolve()):
                    raise RuntimeError("temporary baseline path escaped registry root")
                shutil.rmtree(resolved)
        return final_path / "snapshot.json"

    def load_all(self) -> tuple[ValidatedSnapshot, ...]:
        if not self._root.exists():
            return ()
        snapshots = []
        for path in sorted(self._root.glob("*/snapshot.json")):
            snapshots.append(ValidatedSnapshot.model_validate_json(path.read_text(encoding="utf-8")))
        return tuple(snapshots)


def promote_candidate(
    experiment: ExperimentRecord,
    gate: PromotionGate,
    registry: BaselineRegistry,
) -> ValidatedSnapshot:
    failures = list(gate.failures)
    if not experiment.accepted:
        failures.append("experiment_accepted")
    if failures:
        raise PromotionBlockedError("promotion blocked: " + ", ".join(failures))
    snapshot = ValidatedSnapshot.create(experiment, gate)
    registry.add(snapshot)
    return snapshot
