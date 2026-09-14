from __future__ import annotations

from hashlib import sha256
import json
import math
from numbers import Integral, Real
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.quant.phase4.preregistration.baselines import (
    BaselineDefinitionSet,
)
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    candidate_identity,
    canonical_json_bytes,
    parameter_tuple_identity,
    trial_identity,
)
from investment_tracker.quant.phase4.preregistration.grids import (
    PreregisteredGrids,
    StrategyFamilyDefinition,
)
from investment_tracker.quant.phase4.preregistration.models import (
    Gate1ArtifactIdentity,
)
from investment_tracker.quant.phase4.preregistration.seal import (
    Phase4PreregistrationManifest,
)


MarketRole = Literal["WARMUP", "SCORED"]


GATE2_FAILURE_CODES = (
    "GATE1_MANIFEST_MISMATCH",
    "GATE1_DEPENDENCY_MISMATCH",
    "CANDIDATE_POPULATION_MISMATCH",
    "EXECUTION_CONVENTION_MISMATCH",
    "IMPLEMENTATION_BINDING_MISMATCH",
    "INPUT_BOUNDARY_VIOLATION",
    "MARKET_PANEL_INVALID",
    "LONG_ONLY_INVARIANT_FAILURE",
    "ACCOUNTING_INVARIANT_FAILURE",
    "FIXED_STRATEGY_INVARIANT_FAILURE",
    "DURABILITY_EVIDENCE_INVALID",
    "BUDGET_ACCOUNTING_INVALID",
    "FOLD_AUTHORITY_MISSING",
    "REGIME_AUTHORITY_MISSING",
    "FORBIDDEN_CAPABILITY_PRESENT",
    "HISTORICAL_ARTIFACT_MUTATION",
    "IMMUTABLE_ARTIFACT_COLLISION",
    "SEAL_PUBLICATION_FAILED",
)


class Gate2SealError(RuntimeError):
    """Raised when a frozen Gate 2 precondition fails closed."""

    def __init__(self, code: str, message: str) -> None:
        if code not in GATE2_FAILURE_CODES:
            raise ValueError("unknown Gate 2 failure code")
        self.code = code
        super().__init__(message)


class FrozenGate2Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


DirectDependencyKind = Literal[
    "phase4_preregistration_manifest",
    "baseline_definitions",
    "deterministic_grids",
    "durability_policy",
    "family_budget_policy",
    "information_access_policy",
    "research_report",
    "strategy_family_definitions",
    "survivor_policy",
    "hypothesis_journal",
    "source_journal",
    "research_notes",
    "phase4_readiness_manifest",
    "phase4_split_manifest",
    "trial_authority",
]


class DirectDependencyIdentity(FrozenGate2Model):
    """Exact identity for one file in the terminal Gate 1 read set."""

    kind: DirectDependencyKind
    path: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_identity(self) -> "DirectDependencyIdentity":
        posix = PurePosixPath(self.path)
        windows = PureWindowsPath(self.path)
        if (
            "\\" in self.path
            or self.path.startswith("/")
            or windows.drive
            or windows.is_absolute()
            or any(part in {"", ".", ".."} for part in posix.parts)
        ):
            raise ValueError("dependency path must be repository-relative POSIX")
        exact_byte_only = self.kind in {
            "hypothesis_journal",
            "source_journal",
            "research_notes",
        }
        if exact_byte_only != (self.sha256 is None):
            raise ValueError("dependency envelope presence mismatch")
        if self.sha256 is not None and self.sha256 != artifact_envelope_identity(
            content_sha256=self.content_sha256,
            kind=self.kind,
            path=self.path,
        ):
            raise ValueError("dependency envelope identity mismatch")
        return self


class SafetyAccessState(FrozenGate2Model):
    real_phase4_campaign_executed: Literal[False] = False
    validation_strategy_executed: Literal[False] = False
    validation_metrics_accessed: Literal[False] = False
    candidates_ranked: Literal[False] = False
    survivor_selected: Literal[False] = False
    strategy_search_executed: Literal[False] = False
    external_strategy_research_performed: Literal[False] = False
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()
    provider_calls: Literal[0] = 0
    downloads: Literal[0] = 0
    live_trading_capability: Literal[False] = False
    phase4_trials_consumed: Literal[0] = 0


class UnavailableStatistics(FrozenGate2Model):
    max_drawdown: None = None
    max_drawdown_status: Literal["UNKNOWN"] = "UNKNOWN"
    calmar: None = None
    calmar_status: Literal["UNKNOWN"] = "UNKNOWN"
    dsr: None = None
    dsr_status: Literal["UNKNOWN"] = "UNKNOWN"
    dsr_reason: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"
    pbo: None = None
    pbo_status: Literal["UNKNOWN"] = "UNKNOWN"
    pbo_reason: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"


class TerminalArtifactIdentity(FrozenGate2Model):
    kind: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_identity(self) -> "TerminalArtifactIdentity":
        posix = PurePosixPath(self.path)
        windows = PureWindowsPath(self.path)
        if (
            "\\" in self.path
            or self.path.startswith("/")
            or windows.drive
            or windows.is_absolute()
            or any(part in {"", ".", ".."} for part in posix.parts)
        ):
            raise ValueError("terminal path must be repository-relative POSIX")
        if self.sha256 != artifact_envelope_identity(
            content_sha256=self.content_sha256,
            kind=self.kind,
            path=self.path,
        ):
            raise ValueError("terminal artifact envelope identity mismatch")
        return self


Gate2ArtifactKind = Literal[
    "engine_contract",
    "family_implementation_bindings",
    "candidate_implementation_bindings",
    "synthetic_conformance",
    "phase4_engine_report",
    "phase4_engine_manifest",
]


GATE2_ARTIFACT_FILENAMES: dict[str, str] = {
    "engine_contract": "contract.json",
    "family_implementation_bindings": "bindings.json",
    "candidate_implementation_bindings": "bindings.json",
    "synthetic_conformance": "conformance.json",
    "phase4_engine_report": "report.md",
    "phase4_engine_manifest": "manifest.json",
}


class Gate2ArtifactIdentity(FrozenGate2Model):
    """Exact identity for one immutable Gate 2 artifact."""

    kind: Gate2ArtifactKind
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_identity(self) -> "Gate2ArtifactIdentity":
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
        expected_path = (
            f"results/phase4/gate2/{self.kind}/sha256/{self.content_sha256}/"
            + GATE2_ARTIFACT_FILENAMES[self.kind]
        )
        if self.path != expected_path:
            raise ValueError("artifact path does not match the fixed Gate 2 layout")
        if self.sha256 != artifact_envelope_identity(
            content_sha256=self.content_sha256,
            kind=self.kind,
            path=self.path,
        ):
            raise ValueError("artifact envelope identity mismatch")
        return self


class TerminalProtectedTreeDigest(FrozenGate2Model):
    path: Literal[
        "results/experiments",
        "results/phase3",
        "data/cache/phase3",
    ]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReadinessTerminalMetadata(FrozenGate2Model):
    status: Literal["PHASE_4_READY"]
    source_revision: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    trial_authority: TerminalArtifactIdentity
    split_manifest: TerminalArtifactIdentity
    historical_phase2_trial_count: Literal[136]
    phase4_new_trials_consumed: Literal[0]
    phase4_new_trials_remaining: Literal[3000]
    signal_series: Literal["QFQ"]
    execution_series: Literal["QFQ_NORMALIZED"]
    decision_grade: Literal[False]
    provider_calls: Literal[0]
    external_strategy_research_performed: Literal[False]
    strategy_search_executed: Literal[False]
    strategy_discovery_authorized: Literal[False]
    final_holdout_accessed: Literal[False]
    protected_symbols_accessed: tuple[()] = ()
    live_trading_capability: Literal[False]
    protected_tree_digests: tuple[TerminalProtectedTreeDigest, ...] = Field(
        min_length=3, max_length=3
    )


class SplitTerminalMetadata(FrozenGate2Model):
    phase3_universe_artifact: TerminalArtifactIdentity
    phase3_universe_digest: Literal[
        "de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76"
    ]
    phase3_dq_snapshot_artifact: TerminalArtifactIdentity
    phase3_dq_snapshot_digest: Literal[
        "2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75"
    ]
    symbols: tuple[str, ...] = Field(min_length=8, max_length=8)
    partition_artifact_identities: tuple[TerminalArtifactIdentity, ...] = Field(
        min_length=16, max_length=16
    )
    provider_calls: Literal[0]
    final_holdout_accessed: Literal[False]
    protected_symbols_accessed: tuple[()] = ()


class HistoricalTrialIdentity(FrozenGate2Model):
    trial_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    campaign_id: Literal["PHASE2-CORRECTED-2010-2022-c33fb075"]
    candidate_id: str = Field(min_length=1)
    authoritative_artifact: TerminalArtifactIdentity
    non_authoritative_artifacts: tuple[TerminalArtifactIdentity, ...] = ()

    @model_validator(mode="after")
    def validate_trial(self) -> "HistoricalTrialIdentity":
        if self.trial_id != trial_identity(self.campaign_id, self.candidate_id):
            raise ValueError("historical trial identity mismatch")
        return self


class HistoricalTrialAuthorityMetadata(FrozenGate2Model):
    campaign_id: Literal["PHASE2-CORRECTED-2010-2022-c33fb075"]
    historical_phase2_trial_count: Literal[136]
    total_representation_count: int = Field(ge=136)
    original_representation_count: int = Field(ge=0)
    preliminary_representation_count: int = Field(ge=136)
    final_authoritative_representation_count: Literal[136]
    out_of_scope_representation_count: int = Field(ge=0)
    source_revisions: tuple[str, ...]
    non_authoritative_artifacts: tuple[TerminalArtifactIdentity, ...] = Field(
        min_length=136
    )
    trials: tuple[HistoricalTrialIdentity, ...] = Field(min_length=136, max_length=136)

    @model_validator(mode="after")
    def validate_population(self) -> "HistoricalTrialAuthorityMetadata":
        if (
            self.original_representation_count
            + self.preliminary_representation_count
            + self.final_authoritative_representation_count
            + self.out_of_scope_representation_count
            != self.total_representation_count
        ):
            raise ValueError("historical representation count mismatch")
        candidate_ids = tuple(item.candidate_id for item in self.trials)
        trial_ids = tuple(item.trial_id for item in self.trials)
        if (
            candidate_ids != tuple(sorted(candidate_ids))
            or len(set(candidate_ids)) != 136
        ):
            raise ValueError("historical candidate population mismatch")
        if len(set(trial_ids)) != 136:
            raise ValueError("historical trial population mismatch")
        if self.source_revisions != tuple(sorted(set(self.source_revisions))):
            raise ValueError("historical source revisions mismatch")
        return self


class TrialAuthorityTerminalMetadata(FrozenGate2Model):
    authority: HistoricalTrialAuthorityMetadata
    ordered_trial_ids: tuple[str, ...] = Field(min_length=136, max_length=136)

    @model_validator(mode="after")
    def validate_search_link(self) -> "TrialAuthorityTerminalMetadata":
        if self.ordered_trial_ids != tuple(
            item.trial_id for item in self.authority.trials
        ):
            raise ValueError("search-aware trial identities mismatch")
        return self


_PINNED_GATE1_MANIFEST_IDENTITY = Gate1ArtifactIdentity(
    kind="phase4_preregistration_manifest",
    path=(
        "results/phase4/gate1/phase4_preregistration_manifest/sha256/"
        "dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89/"
        "manifest.json"
    ),
    content_sha256=("dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89"),
    sha256="e43ccbb596a9f66222b4e2785b1c40c423e6bb43b54b788e1fdb6358e1cdf146",
)


def _manifest_direct_dependencies(
    manifest: Phase4PreregistrationManifest,
) -> tuple[DirectDependencyIdentity, ...]:
    artifact_fields = (
        manifest.baseline_definitions,
        manifest.deterministic_grids,
        manifest.durability_policy,
        manifest.family_budget_policy,
        manifest.information_access_policy,
        manifest.research_report,
        manifest.strategy_family_definitions,
        manifest.survivor_policy,
    )
    return (
        DirectDependencyIdentity(**_PINNED_GATE1_MANIFEST_IDENTITY.model_dump()),
        *(DirectDependencyIdentity(**item.model_dump()) for item in artifact_fields),
        DirectDependencyIdentity(
            kind="hypothesis_journal",
            path=manifest.hypothesis_journal.path,
            content_sha256=manifest.hypothesis_journal.file_sha256,
        ),
        DirectDependencyIdentity(
            kind="source_journal",
            path=manifest.source_journal.path,
            content_sha256=manifest.source_journal.file_sha256,
        ),
        DirectDependencyIdentity(
            kind="research_notes",
            path=manifest.research_notes_path,
            content_sha256=manifest.research_notes_content_sha256,
        ),
        DirectDependencyIdentity(**manifest.readiness_manifest.model_dump()),
        DirectDependencyIdentity(**manifest.split_manifest.model_dump()),
        DirectDependencyIdentity(**manifest.trial_authority.model_dump()),
    )


class Gate2Authority(FrozenGate2Model):
    starting_revision: Literal["fb1c30a6c9789bddf2033301977fc8e2f3ebc1a0"]
    head_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    manifest_identity: Gate1ArtifactIdentity
    manifest_payload: bytes
    deterministic_grids_payload: bytes
    family_definitions_payload: bytes
    baseline_definitions_payload: bytes
    direct_dependencies: tuple[DirectDependencyIdentity, ...] = Field(
        min_length=15, max_length=15
    )
    readiness_manifest: ReadinessTerminalMetadata
    split_manifest: SplitTerminalMetadata
    trial_authority: TrialAuthorityTerminalMetadata
    execution_convention: Literal["COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN"]
    execution_series: Literal["QFQ_NORMALIZED"]
    primary_friction_bps: Literal[3]
    decision_grade: Literal[False]
    qfq_methodology_identity: Literal[
        "ffee9bac3fe329b14d5aebb0f6152f00fc0a86b28d9186c254b5c8f6f8a322fb"
    ]
    historical_phase2_trials: Literal[136]
    phase4_trials_consumed: Literal[0]
    unavailable_statistics: UnavailableStatistics
    safety: SafetyAccessState

    @property
    def manifest(self) -> Phase4PreregistrationManifest:
        return Phase4PreregistrationManifest.model_validate_json(self.manifest_payload)

    @property
    def grids(self) -> PreregisteredGrids:
        return PreregisteredGrids.model_validate_json(self.deterministic_grids_payload)

    @property
    def family_definitions(self) -> tuple[StrategyFamilyDefinition, ...]:
        payload = json.loads(self.family_definitions_payload)
        return tuple(
            StrategyFamilyDefinition.model_validate(
                {**family_payload, "candidates": grid_family.candidates}
            )
            for family_payload, grid_family in zip(
                payload["families"], self.grids.families, strict=True
            )
        )

    @property
    def baselines(self) -> BaselineDefinitionSet:
        return BaselineDefinitionSet.model_validate_json(
            self.baseline_definitions_payload
        )

    @staticmethod
    def _parsed_canonical_payload(*, field_name: str, payload: bytes) -> object:
        try:
            parsed = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{field_name} must be valid JSON") from exc
        if canonical_json_bytes(parsed) != payload:
            raise ValueError(f"{field_name} must use exact canonical JSON bytes")
        return parsed

    def _validated_retained_payload(
        self,
        *,
        field_name: str,
        dependency_kind: DirectDependencyKind,
        payload: bytes,
    ) -> object:
        dependencies = tuple(
            item for item in self.direct_dependencies if item.kind == dependency_kind
        )
        if len(dependencies) != 1:
            raise ValueError(
                f"{field_name} must have exactly one corresponding direct dependency"
            )
        parsed = self._parsed_canonical_payload(
            field_name=field_name,
            payload=payload,
        )
        if sha256(payload).hexdigest() != dependencies[0].content_sha256:
            raise ValueError(f"{field_name} content digest mismatch")
        return parsed

    @model_validator(mode="after")
    def validate_authority_links(self) -> "Gate2Authority":
        if len({item.path for item in self.direct_dependencies}) != 15:
            raise ValueError("direct dependency paths must be unique")
        manifest_payload = self._parsed_canonical_payload(
            field_name="manifest_payload",
            payload=self.manifest_payload,
        )
        if self.manifest_identity != _PINNED_GATE1_MANIFEST_IDENTITY:
            raise ValueError("Gate 1 manifest identity is not the pinned authority")
        if sha256(self.manifest_payload).hexdigest() != (
            self.manifest_identity.content_sha256
        ):
            raise ValueError("manifest_payload content digest mismatch")
        manifest = Phase4PreregistrationManifest.model_validate(manifest_payload)
        if self.direct_dependencies != _manifest_direct_dependencies(manifest):
            raise ValueError(
                "direct dependencies differ from the pinned Gate 1 manifest"
            )
        baseline_payload = self._validated_retained_payload(
            field_name="baseline_definitions_payload",
            dependency_kind="baseline_definitions",
            payload=self.baseline_definitions_payload,
        )
        grids_payload = self._validated_retained_payload(
            field_name="deterministic_grids_payload",
            dependency_kind="deterministic_grids",
            payload=self.deterministic_grids_payload,
        )
        family_payload = self._validated_retained_payload(
            field_name="family_definitions_payload",
            dependency_kind="strategy_family_definitions",
            payload=self.family_definitions_payload,
        )
        BaselineDefinitionSet.model_validate(baseline_payload)
        grids = PreregisteredGrids.model_validate(grids_payload)
        expected_family_payload = {
            "schema_version": "PHASE4-STRATEGY-FAMILY-DEFINITION-SET-v1",
            "families": [
                family.model_dump(mode="json", exclude={"candidates"})
                for family in grids.families
            ],
        }
        if family_payload != expected_family_payload:
            raise ValueError(
                "retained family definitions differ from deterministic grids"
            )
        if manifest.candidate_parameter_population_sha256 != (
            grids.candidate_parameter_population_sha256
        ):
            raise ValueError("candidate population differs from Gate 1 manifest")
        if manifest.historical_phase2_trials != self.historical_phase2_trials:
            raise ValueError("historical trial count differs from Gate 1 manifest")
        if manifest.phase4_initial_consumption != self.phase4_trials_consumed:
            raise ValueError("Phase 4 consumption differs from Gate 1 manifest")
        return self


FamilySemanticName = Literal[
    "cross_sectional_absolute_momentum_rotation",
    "diversified_time_series_momentum",
    "trend_filtered_equal_risk_allocation",
    "volatility_managed_relative_momentum",
]


_SEALED_PARAMETER_VALUES: dict[str, dict[str, tuple[int | float, ...]]] = {
    "cross_sectional_absolute_momentum_rotation": {
        "lookback_sessions": (63, 126, 252),
        "rebalance_sessions": (21, 42, 63),
        "skip_sessions": (0, 21),
        "top_k": (1, 2, 3),
    },
    "diversified_time_series_momentum": {
        "lookback_sessions": (63, 126, 252),
        "maximum_asset_weight": (0.25, 0.5),
        "rebalance_sessions": (5, 21),
        "volatility_window": (20, 60, 120),
    },
    "trend_filtered_equal_risk_allocation": {
        "maximum_asset_weight": (0.25, 0.5),
        "rebalance_sessions": (5, 21),
        "trend_window": (100, 150, 200),
        "volatility_window": (20, 60, 120),
    },
    "volatility_managed_relative_momentum": {
        "lookback_sessions": (63, 126, 252),
        "target_portfolio_volatility": (0.08, 0.12, 0.16),
        "top_k": (1, 2, 3),
        "volatility_window": (20, 60),
    },
}


class SealedStrategyParameter(FrozenGate2Model):
    name: str = Field(min_length=1)
    type: Literal["int", "float64_hex"]
    value: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_canonical_value(self) -> "SealedStrategyParameter":
        if self.type == "int":
            try:
                decoded = int(self.value)
            except ValueError as exc:
                raise ValueError("invalid sealed integer parameter") from exc
            if str(decoded) != self.value:
                raise ValueError("noncanonical sealed integer parameter")
        else:
            try:
                decoded = float.fromhex(self.value)
            except ValueError as exc:
                raise ValueError("invalid sealed float parameter") from exc
            if not math.isfinite(decoded) or decoded.hex() != self.value:
                raise ValueError("noncanonical sealed float parameter")
        return self

    @property
    def decoded(self) -> int | float:
        if self.type == "int":
            return int(self.value)
        return float.fromhex(self.value)

    @property
    def typed_value(self) -> dict[str, object]:
        return {"type": self.type, "value": self.value}


def _binding_identity_payload(payload: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in payload.items() if key != "binding_sha256"}


class FixedStrategyBinding(FrozenGate2Model):
    schema_version: Literal["PHASE4-FIXED-STRATEGY-BINDING-v1"] = (
        "PHASE4-FIXED-STRATEGY-BINDING-v1"
    )
    implementation_interface: Literal["PHASE4-FIXED-LONG-ONLY-STRATEGY-v1"]
    campaign_id: Literal["PHASE4-FIXED-LONG-ONLY-2014-2022-v1"]
    candidate_id: str = Field(pattern=r"^phase4-[0-9a-f]{64}$")
    trial_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget_position: int = Field(ge=1, le=180)
    family_id: str = Field(pattern=r"^phase4-family-[0-9a-f]{64}$")
    family_semantic_name: FamilySemanticName
    hypothesis_id: str = Field(min_length=1)
    family_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameter_tuple_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    grid_spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameters: tuple[SealedStrategyParameter, ...]
    structural_parameters: tuple[SealedStrategyParameter, ...] = ()
    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    def model_copy(
        self, *, update: dict[str, object] | None = None, deep: bool = False
    ) -> "FixedStrategyBinding":
        if update:
            raise TypeError("fixed strategy bindings do not permit replacement")
        return super().model_copy(deep=deep)

    def copy(
        self,
        *,
        include: object = None,
        exclude: object = None,
        update: dict[str, object] | None = None,
        deep: bool = False,
    ) -> "FixedStrategyBinding":
        if include is not None or exclude is not None or update:
            raise TypeError("fixed strategy bindings do not permit replacement")
        return self.model_copy(deep=deep)

    @classmethod
    def from_authority(
        cls,
        authority: Gate2Authority,
        candidate_id: str,
        implementation_sha256: str,
    ) -> "FixedStrategyBinding":
        if not isinstance(authority, Gate2Authority):
            raise Gate2SealError(
                "FIXED_STRATEGY_INVARIANT_FAILURE",
                "strategy binding requires the exact Gate 2 authority",
            )
        if re.fullmatch(r"[0-9a-f]{64}", implementation_sha256) is None:
            raise Gate2SealError(
                "FIXED_STRATEGY_INVARIANT_FAILURE",
                "strategy implementation identity must be lowercase SHA-256",
            )
        candidates = tuple(
            candidate
            for candidate in authority.grids.candidates
            if candidate.candidate_id == candidate_id
        )
        if len(candidates) != 1:
            raise Gate2SealError(
                "FIXED_STRATEGY_INVARIANT_FAILURE",
                "candidate is not present exactly once in the sealed population",
            )
        candidate = candidates[0]
        families = tuple(
            family
            for family in authority.family_definitions
            if family.family_id == candidate.family_id
        )
        if len(families) != 1 or candidate not in families[0].candidates:
            raise Gate2SealError(
                "FIXED_STRATEGY_INVARIANT_FAILURE",
                "candidate and family authority do not agree",
            )
        family = families[0]
        if family.family_semantic_name not in _SEALED_PARAMETER_VALUES:
            raise Gate2SealError(
                "FIXED_STRATEGY_INVARIANT_FAILURE",
                "family semantic name is not one of the four sealed implementations",
            )

        parameters = tuple(
            {
                "name": name,
                "type": candidate.parameters[name]["type"],
                "value": candidate.parameters[name]["value"],
            }
            for name in sorted(candidate.parameters)
        )
        structural_parameters = tuple(
            {
                "name": name,
                "type": family.structural_parameters[name]["type"],
                "value": family.structural_parameters[name]["value"],
            }
            for name in sorted(family.structural_parameters)
        )
        payload: dict[str, object] = {
            "schema_version": "PHASE4-FIXED-STRATEGY-BINDING-v1",
            "implementation_interface": family.implementation_interface,
            "campaign_id": candidate.campaign_id,
            "candidate_id": candidate.candidate_id,
            "trial_id": candidate.trial_id,
            "budget_position": candidate.budget_position,
            "family_id": candidate.family_id,
            "family_semantic_name": family.family_semantic_name,
            "hypothesis_id": candidate.hypothesis_id,
            "family_definition_sha256": family.family_definition_sha256,
            "rule_set_sha256": family.rule_set_sha256,
            "parameter_tuple_sha256": candidate.parameter_tuple_sha256,
            "grid_spec_sha256": family.grid_spec_sha256,
            "implementation_sha256": implementation_sha256,
            "parameters": parameters,
            "structural_parameters": structural_parameters,
        }
        payload["binding_sha256"] = sha256(
            canonical_json_bytes(_binding_identity_payload(payload))
        ).hexdigest()
        try:
            return cls.model_validate(payload)
        except ValueError as exc:
            raise Gate2SealError(
                "FIXED_STRATEGY_INVARIANT_FAILURE",
                "sealed strategy binding failed reconstruction",
            ) from exc

    @property
    def parameters_dict(self) -> dict[str, int | float]:
        return {parameter.name: parameter.decoded for parameter in self.parameters}

    @property
    def structural_parameters_dict(self) -> dict[str, int | float]:
        return {
            parameter.name: parameter.decoded
            for parameter in self.structural_parameters
        }

    @model_validator(mode="after")
    def validate_binding(self) -> "FixedStrategyBinding":
        if tuple(parameter.name for parameter in self.parameters) != tuple(
            sorted(parameter.name for parameter in self.parameters)
        ) or len({parameter.name for parameter in self.parameters}) != len(
            self.parameters
        ):
            raise ValueError("strategy parameters must be unique and name-sorted")
        if tuple(parameter.name for parameter in self.structural_parameters) != tuple(
            sorted(parameter.name for parameter in self.structural_parameters)
        ) or len({parameter.name for parameter in self.structural_parameters}) != len(
            self.structural_parameters
        ):
            raise ValueError("structural parameters must be unique and name-sorted")

        raw_parameters = self.parameters_dict
        expected_values = _SEALED_PARAMETER_VALUES[self.family_semantic_name]
        if tuple(raw_parameters) != tuple(expected_values) or any(
            raw_parameters[name] not in allowed
            for name, allowed in expected_values.items()
        ):
            raise ValueError("parameters are not one exact sealed tuple")
        expected_structural = (
            {"rebalance_sessions": 21}
            if self.family_semantic_name == "volatility_managed_relative_momentum"
            else {}
        )
        if self.structural_parameters_dict != expected_structural:
            raise ValueError("structural parameters differ from sealed authority")

        typed_parameters = {
            parameter.name: parameter.typed_value for parameter in self.parameters
        }
        if self.parameter_tuple_sha256 != parameter_tuple_identity(
            self.family_id, typed_parameters
        ):
            raise ValueError("strategy parameter tuple identity mismatch")
        if self.candidate_id != candidate_identity(
            campaign_id=self.campaign_id,
            hypothesis_id=self.hypothesis_id,
            family_id=self.family_id,
            parameters=typed_parameters,
        ):
            raise ValueError("strategy candidate identity mismatch")
        if self.trial_id != trial_identity(self.campaign_id, self.candidate_id):
            raise ValueError("strategy trial identity mismatch")
        payload = self.model_dump(mode="json")
        expected_binding_sha256 = sha256(
            canonical_json_bytes(_binding_identity_payload(payload))
        ).hexdigest()
        if self.binding_sha256 != expected_binding_sha256:
            raise ValueError("strategy binding identity mismatch")
        return self


class TargetInstruction(FrozenGate2Model):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["PHASE4-TARGET-INSTRUCTION-v1"] = (
        "PHASE4-TARGET-INSTRUCTION-v1"
    )
    signal_timestamp: pd.Timestamp
    due_session: pd.Timestamp | None
    weights: tuple[tuple[str, float], ...]
    binding: FixedStrategyBinding

    @model_validator(mode="after")
    def validate_target(self) -> "TargetInstruction":
        for field_name, timestamp in (
            ("signal_timestamp", self.signal_timestamp),
            ("due_session", self.due_session),
        ):
            if timestamp is None:
                continue
            if not isinstance(timestamp, pd.Timestamp):
                raise ValueError(f"{field_name} must be a pandas Timestamp")
            if timestamp.tz is None or str(timestamp.tz) != "UTC":
                raise ValueError(f"{field_name} must use UTC")
            if timestamp != timestamp.normalize():
                raise ValueError(f"{field_name} must be a UTC-midnight session")
        if self.due_session is not None and self.due_session <= self.signal_timestamp:
            raise ValueError("due session must be strictly after signal timestamp")

        symbols = tuple(symbol for symbol, _ in self.weights)
        if symbols != tuple(sorted(symbols)) or len(set(symbols)) != len(symbols):
            raise ValueError("target symbols must be unique and ascending")
        if any(not isinstance(symbol, str) or not symbol for symbol in symbols):
            raise ValueError("target symbols must be nonempty strings")
        numeric_weights = tuple(float(weight) for _, weight in self.weights)
        if any(not math.isfinite(weight) or weight < 0.0 for weight in numeric_weights):
            raise ValueError("target weights must be finite and nonnegative")
        total = math.fsum(numeric_weights)
        if total > 1.0 + 1e-12:
            raise ValueError("target gross exposure exceeds one")
        canonical_weights = tuple(
            (symbol, weight)
            for (symbol, _), weight in zip(self.weights, numeric_weights, strict=True)
            if weight > 0.0
        )
        if total > 1.0:
            canonical_weights = tuple(
                (symbol, weight / total) for symbol, weight in canonical_weights
            )
        canonical_total = math.fsum(weight for _, weight in canonical_weights)
        if canonical_total > 1.0 and canonical_weights:
            scale = 1.0 / canonical_total
            canonical_weights = tuple(
                (symbol, weight * scale) for symbol, weight in canonical_weights
            )
        object.__setattr__(self, "weights", canonical_weights)

        reconstructed = FixedStrategyBinding.model_validate(self.binding.model_dump())
        if reconstructed != self.binding:
            raise ValueError("target binding is not an exact fixed binding")
        return self


def _utc_midnight(value: object, *, field_name: str) -> bool:
    return (
        isinstance(value, pd.Timestamp)
        and value.tz is not None
        and str(value.tz) == "UTC"
        and bool(value == value.normalize())
    )


def _finite_real(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, Real)
        and math.isfinite(float(value))
    )


class Fill(FrozenGate2Model):
    """One deterministic fill executed at a scored session's QFQ-normalized open."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["PHASE4-FILL-v1"] = "PHASE4-FILL-v1"
    symbol: str = Field(min_length=1)
    signal_timestamp: pd.Timestamp
    fill_timestamp: pd.Timestamp
    reference_open: float
    units_delta: float
    fill_notional: float
    friction: float
    binding: FixedStrategyBinding | None = None

    @model_validator(mode="after")
    def validate_fill(self) -> "Fill":
        if not _utc_midnight(self.signal_timestamp, field_name="signal_timestamp"):
            raise ValueError("fill signal timestamp must be a UTC-midnight session")
        if not _utc_midnight(self.fill_timestamp, field_name="fill_timestamp"):
            raise ValueError("fill timestamp must be a UTC-midnight session")
        if self.signal_timestamp >= self.fill_timestamp:
            raise ValueError("fill must occur strictly after its signal")
        if not _finite_real(self.reference_open) or self.reference_open <= 0.0:
            raise ValueError("fill reference open must be finite and strictly positive")
        for field_name in ("units_delta", "fill_notional", "friction"):
            if not _finite_real(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be a finite real")
        if self.friction < 0.0:
            raise ValueError("fill friction must be nonnegative")
        return self


class SessionState(FrozenGate2Model):
    """Post-fill, close-marked portfolio state for one scored session."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["PHASE4-SESSION-STATE-v1"] = "PHASE4-SESSION-STATE-v1"
    session: pd.Timestamp
    open_equity: float
    close_equity: float
    cash: float
    units: tuple[tuple[str, float], ...]
    realized_gross_exposure: float
    target_gross_exposure: float
    binding: FixedStrategyBinding | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "SessionState":
        if not _utc_midnight(self.session, field_name="session"):
            raise ValueError("session state must reference a UTC-midnight session")
        for field_name in (
            "open_equity",
            "close_equity",
            "cash",
            "realized_gross_exposure",
            "target_gross_exposure",
        ):
            if not _finite_real(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be a finite real")
        if self.open_equity <= 0.0 or self.close_equity <= 0.0:
            raise ValueError("session equity must be strictly positive")
        if self.cash < 0.0:
            raise ValueError("session cash must be nonnegative")
        if not 0.0 <= self.realized_gross_exposure <= 1.0 + 1e-12:
            raise ValueError(
                "realized gross exposure must stay long-only and unlevered"
            )
        if not 0.0 <= self.target_gross_exposure <= 1.0 + 1e-12:
            raise ValueError("target gross exposure must stay within one")
        symbols = tuple(symbol for symbol, _ in self.units)
        if symbols != tuple(sorted(symbols)) or len(set(symbols)) != len(symbols):
            raise ValueError("held symbols must be unique and ascending")
        for symbol, units in self.units:
            if not isinstance(symbol, str) or not symbol:
                raise ValueError("held symbol must be a nonempty string")
            if not _finite_real(units) or units <= 0.0:
                raise ValueError("held units must be finite and strictly positive")
        return self


class PortfolioReplay(FrozenGate2Model):
    """The complete self-financing scored-session replay for one evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["PHASE4-PORTFOLIO-REPLAY-v1"] = "PHASE4-PORTFOLIO-REPLAY-v1"
    candidate_id: str | None = Field(default=None, pattern=r"^phase4-[0-9a-f]{64}$")
    binding_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    friction_bps: int
    initial_cash: float
    states: tuple[SessionState, ...] = Field(min_length=1)
    fills: tuple[Fill, ...] = ()
    total_turnover: float

    @model_validator(mode="after")
    def validate_replay(self) -> "PortfolioReplay":
        if (
            isinstance(self.friction_bps, bool)
            or not isinstance(self.friction_bps, Integral)
            or self.friction_bps < 0
        ):
            raise ValueError("friction_bps must be a nonnegative integer")
        if not _finite_real(self.initial_cash) or self.initial_cash <= 0.0:
            raise ValueError("initial_cash must be a finite positive real")
        if not _finite_real(self.total_turnover) or self.total_turnover < 0.0:
            raise ValueError("total_turnover must be a finite nonnegative real")
        sessions = tuple(state.session for state in self.states)
        if sessions != tuple(sorted(sessions)) or len(set(sessions)) != len(sessions):
            raise ValueError("replay sessions must be unique and increasing")
        session_set = set(sessions)
        previous: pd.Timestamp | None = None
        for fill in self.fills:
            if fill.fill_timestamp not in session_set:
                raise ValueError("fill must occur on a replay scored session")
            if previous is not None and fill.fill_timestamp < previous:
                raise ValueError("fills must occur in scored-session order")
            previous = fill.fill_timestamp
        if (self.candidate_id is None) != (self.binding_sha256 is None):
            raise ValueError(
                "candidate and binding identities must both be present or absent"
            )
        nested_bindings = tuple(item.binding for item in (*self.states, *self.fills))
        if self.candidate_id is None:
            if any(binding is not None for binding in nested_bindings):
                raise ValueError("benchmark replay cannot carry strategy identities")
        else:
            if any(binding is None for binding in nested_bindings):
                raise ValueError(
                    "strategy identity must accompany every state and fill"
                )
            if any(
                binding.candidate_id != self.candidate_id
                or binding.binding_sha256 != self.binding_sha256
                for binding in nested_bindings
                if binding is not None
            ):
                raise ValueError("nested strategy identities must match the replay")
        return self

    @property
    def sessions(self) -> tuple[pd.Timestamp, ...]:
        return tuple(state.session for state in self.states)

    @property
    def close_equity(self) -> tuple[float, ...]:
        return tuple(state.close_equity for state in self.states)

    @property
    def realized_gross_exposure(self) -> tuple[float, ...]:
        return tuple(state.realized_gross_exposure for state in self.states)

    @property
    def target_gross_exposure(self) -> tuple[float, ...]:
        return tuple(state.target_gross_exposure for state in self.states)

    @property
    def daily_returns(self) -> tuple[float, ...]:
        series = pd.Series(self.close_equity).pct_change()
        return tuple(float(value) for value in series.iloc[1:].to_numpy())


MetricStatus = Literal["AVAILABLE", "UNKNOWN"]
MetricReason = Literal[
    "OK",
    "INSUFFICIENT_DATA",
    "INCOMPLETE_WINDOW",
    "INCOMPLETE_PERIOD",
    "EMPTY_SUBSET",
    "NONPOSITIVE_DENOMINATOR",
    "INVALID_INPUT",
]


class MetricValue(FrozenGate2Model):
    schema_version: Literal["PHASE4-METRIC-VALUE-v1"] = "PHASE4-METRIC-VALUE-v1"
    value: float | None
    status: MetricStatus
    reason: MetricReason

    @model_validator(mode="after")
    def validate_metric(self) -> "MetricValue":
        if self.status == "AVAILABLE":
            if self.value is None or not _finite_real(self.value):
                raise ValueError("available metric must contain one finite value")
            if self.reason != "OK":
                raise ValueError("available metric reason must be OK")
        elif self.value is not None or self.reason == "OK":
            raise ValueError("unknown metric must be null with a non-OK reason")
        return self


class SupportedMetrics(FrozenGate2Model):
    schema_version: Literal["PHASE4-SUPPORTED-METRICS-v1"] = (
        "PHASE4-SUPPORTED-METRICS-v1"
    )
    candidate_id: str | None = Field(default=None, pattern=r"^phase4-[0-9a-f]{64}$")
    binding_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    total_return: MetricValue
    cagr: MetricValue
    annualized_volatility: MetricValue
    sharpe: MetricValue
    sortino: MetricValue
    benchmark_excess_return: MetricValue
    total_one_way_turnover: MetricValue
    annualized_one_way_turnover: MetricValue
    average_target_gross_exposure: MetricValue
    average_realized_gross_exposure: MetricValue
    time_in_market: MetricValue
    target_gross_exposure_series: tuple[float, ...]
    realized_gross_exposure_series: tuple[float, ...]
    unavailable_statistics: UnavailableStatistics

    @model_validator(mode="after")
    def validate_supported_metrics(self) -> "SupportedMetrics":
        if (self.candidate_id is None) != (self.binding_sha256 is None):
            raise ValueError(
                "candidate and binding identities must both be present or absent"
            )
        if len(self.target_gross_exposure_series) != len(
            self.realized_gross_exposure_series
        ):
            raise ValueError("target and realized exposure series must align")
        for series in (
            self.target_gross_exposure_series,
            self.realized_gross_exposure_series,
        ):
            if any(
                not _finite_real(value) or not 0.0 <= value <= 1.0 + 1e-12
                for value in series
            ):
                raise ValueError(
                    "exposure series must be finite, long-only, and unlevered"
                )
        return self


def _expected_session_identity(sessions: tuple[pd.Timestamp, ...]) -> str:
    if not sessions or any(
        not _utc_midnight(value, field_name="session") for value in sessions
    ):
        raise ValueError("expected sessions must be nonempty UTC-midnight labels")
    if sessions != tuple(sorted(sessions)) or len(set(sessions)) != len(sessions):
        raise ValueError("expected sessions must be unique and increasing")
    return sha256(
        canonical_json_bytes(
            {
                "schema_version": "PHASE4-EXPECTED-SESSION-AUTHORITY-v1",
                "sessions": [value.isoformat() for value in sessions],
            }
        )
    ).hexdigest()


class ExpectedSessionAuthority(FrozenGate2Model):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["PHASE4-EXPECTED-SESSION-AUTHORITY-v1"] = (
        "PHASE4-EXPECTED-SESSION-AUTHORITY-v1"
    )
    sessions: tuple[pd.Timestamp, ...] = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_expected_sessions(self) -> "ExpectedSessionAuthority":
        if self.sha256 != _expected_session_identity(self.sessions):
            raise ValueError(
                "expected-session identity does not bind the ordered labels"
            )
        return self


class RollingWindowEvidence(FrozenGate2Model):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["PHASE4-ROLLING-WINDOW-v1"] = "PHASE4-ROLLING-WINDOW-v1"
    horizon_months: int
    anchors: tuple[pd.Timestamp, ...] = ()
    endpoints: tuple[pd.Timestamp, ...] = ()
    observations: tuple[MetricValue, ...] = ()
    minimum: MetricValue
    median: MetricValue
    positive_fraction: MetricValue

    @model_validator(mode="after")
    def validate_rolling_window(self) -> "RollingWindowEvidence":
        if isinstance(self.horizon_months, bool) or self.horizon_months < 1:
            raise ValueError("rolling horizon must be a positive integer")
        if not len(self.anchors) == len(self.endpoints) == len(self.observations):
            raise ValueError("rolling anchors, endpoints, and observations must align")
        if self.endpoints != tuple(sorted(self.endpoints)) or len(
            set(self.endpoints)
        ) != len(self.endpoints):
            raise ValueError("rolling endpoints must be unique and increasing")
        for anchor, endpoint in zip(self.anchors, self.endpoints, strict=True):
            if not _utc_midnight(anchor, field_name="anchor") or not _utc_midnight(
                endpoint, field_name="endpoint"
            ):
                raise ValueError("rolling labels must be UTC-midnight sessions")
            if anchor >= endpoint:
                raise ValueError("rolling anchor must precede its endpoint")
        return self


class DurabilityEvidence(FrozenGate2Model):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["PHASE4-DURABILITY-EVIDENCE-v1"] = (
        "PHASE4-DURABILITY-EVIDENCE-v1"
    )
    candidate_id: str | None = Field(default=None, pattern=r"^phase4-[0-9a-f]{64}$")
    binding_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    expected_sessions_authority_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    month_period_labels: tuple[str, ...]
    month_returns: tuple[MetricValue, ...]
    year_period_labels: tuple[str, ...]
    year_returns: tuple[MetricValue, ...]
    positive_month_fraction: MetricValue
    positive_year_fraction: MetricValue
    average_positive_month: MetricValue
    average_negative_month: MetricValue
    worst_month: MetricValue
    worst_year: MetricValue
    longest_negative_month_streak: MetricValue
    positive_month_concentration: MetricValue
    positive_year_concentration: MetricValue
    top_three_positive_month_concentration: MetricValue
    rolling_12: RollingWindowEvidence
    rolling_36: RollingWindowEvidence
    rolling_60: RollingWindowEvidence | None = None
    unavailable_statistics: UnavailableStatistics

    @model_validator(mode="after")
    def validate_durability(self) -> "DurabilityEvidence":
        if (self.candidate_id is None) != (self.binding_sha256 is None):
            raise ValueError(
                "candidate and binding identities must both be present or absent"
            )
        if len(self.month_period_labels) != len(self.month_returns):
            raise ValueError("month labels and returns must align")
        if len(self.year_period_labels) != len(self.year_returns):
            raise ValueError("year labels and returns must align")
        if self.month_period_labels != tuple(sorted(set(self.month_period_labels))):
            raise ValueError("month period labels must be unique and increasing")
        if self.year_period_labels != tuple(sorted(set(self.year_period_labels))):
            raise ValueError("year period labels must be unique and increasing")
        if self.rolling_12.horizon_months != 12 or self.rolling_36.horizon_months != 36:
            raise ValueError("Phase 4 rolling evidence must contain 12 and 36 months")
        if self.rolling_60 is not None and self.rolling_60.horizon_months != 60:
            raise ValueError("Phase 5 rolling evidence must contain 60 months")
        return self


# --- Task 6: robustness and budget ---


class FrictionCaseEvidence(FrozenGate2Model):
    schema_version: Literal["PHASE4-FRICTION-CASE-v1"] = "PHASE4-FRICTION-CASE-v1"
    friction_bps: int
    candidate_id: str | None = Field(default=None, pattern=r"^phase4-[0-9a-f]{64}$")
    binding_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    total_return: MetricValue
    total_turnover: MetricValue
    close_equity: tuple[float, ...]
    unavailable_statistics: UnavailableStatistics

    @model_validator(mode="after")
    def validate_friction_case(self) -> "FrictionCaseEvidence":
        if isinstance(self.friction_bps, bool) or self.friction_bps < 0:
            raise ValueError("friction bps must be a nonnegative integer")
        if (self.candidate_id is None) != (self.binding_sha256 is None):
            raise ValueError("candidate and binding identities must align")
        if not all(_finite_real(value) for value in self.close_equity):
            raise ValueError("close equity must be finite")
        return self


class FrictionEvidence(FrozenGate2Model):
    schema_version: Literal["PHASE4-FRICTION-EVIDENCE-v1"] = (
        "PHASE4-FRICTION-EVIDENCE-v1"
    )
    candidate_id: str | None = Field(default=None, pattern=r"^phase4-[0-9a-f]{64}$")
    binding_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cases: tuple[FrictionCaseEvidence, ...] = Field(min_length=5)
    primary_bps: Literal[3] = 3
    friction_retention_ratio: MetricValue
    unavailable_statistics: UnavailableStatistics

    @model_validator(mode="after")
    def validate_friction_evidence(self) -> "FrictionEvidence":
        if [case.friction_bps for case in self.cases] != [0, 3, 10, 25, 50]:
            raise ValueError("friction cases must be exactly (0, 3, 10, 25, 50)")
        if len({case.candidate_id for case in self.cases}) != 1:
            raise ValueError("friction cases must share one candidate identity")
        if len({case.binding_sha256 for case in self.cases}) != 1:
            raise ValueError("friction cases must share one binding identity")
        if (self.candidate_id is None) != (self.binding_sha256 is None):
            raise ValueError("candidate and binding identities must align")
        return self


class BootstrapEvidence(FrozenGate2Model):
    schema_version: Literal["PHASE4-BOOTSTRAP-EVIDENCE-v1"] = (
        "PHASE4-BOOTSTRAP-EVIDENCE-v1"
    )
    statistic: Literal["median_daily_return"] = "median_daily_return"
    n_bootstrap_draws: Literal[2000] = 2000
    seed: Literal[0] = 0
    sample_size: int = Field(ge=2)
    observed_median: MetricValue
    percentile_05: MetricValue
    percentile_95: MetricValue
    unavailable_statistics: UnavailableStatistics


class FoldAuthority(FrozenGate2Model):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["PHASE4-FOLD-AUTHORITY-v1"] = "PHASE4-FOLD-AUTHORITY-v1"
    fold_ids: tuple[str, ...] = Field(min_length=1)
    boundaries: tuple[tuple[pd.Timestamp, pd.Timestamp], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_fold_authority(self) -> "FoldAuthority":
        if len(self.fold_ids) != len(self.boundaries):
            raise ValueError("fold ids and boundaries must align")
        if len(set(self.fold_ids)) != len(self.fold_ids):
            raise ValueError("fold ids must be unique")
        for start, end in self.boundaries:
            if start >= end:
                raise ValueError("fold start must precede its end")
        for previous, current in zip(self.boundaries, self.boundaries[1:], strict=False):
            if previous[1] > current[0]:
                raise ValueError("folds must not overlap")
        return self


class FoldSliceEvidence(FrozenGate2Model):
    schema_version: Literal["PHASE4-FOLD-SLICE-EVIDENCE-v1"] = (
        "PHASE4-FOLD-SLICE-EVIDENCE-v1"
    )
    candidate_id: str | None = Field(default=None, pattern=r"^phase4-[0-9a-f]{64}$")
    binding_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    fold_ids: tuple[str, ...] = Field(min_length=1)
    fold_returns: tuple[MetricValue, ...]
    fold_equity_start: tuple[float, ...]
    fold_equity_end: tuple[float, ...]
    unavailable_statistics: UnavailableStatistics

    @model_validator(mode="after")
    def validate_fold_slice(self) -> "FoldSliceEvidence":
        if not (
            len(self.fold_ids)
            == len(self.fold_returns)
            == len(self.fold_equity_start)
            == len(self.fold_equity_end)
        ):
            raise ValueError("fold ids, returns, and equity endpoints must align")
        if not all(_finite_real(v) for v in (*self.fold_equity_start, *self.fold_equity_end)):
            raise ValueError("fold equity endpoints must be finite")
        if (self.candidate_id is None) != (self.binding_sha256 is None):
            raise ValueError("candidate and binding identities must align")
        return self


class RegimeAuthority(FrozenGate2Model):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["PHASE4-REGIME-AUTHORITY-v1"] = "PHASE4-REGIME-AUTHORITY-v1"
    regime_ids: tuple[str, ...] = Field(min_length=1)
    session_regime: tuple[tuple[pd.Timestamp, str], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_regime_authority(self) -> "RegimeAuthority":
        if len(set(self.regime_ids)) != len(self.regime_ids):
            raise ValueError("regime ids must be unique")
        if self.regime_ids != tuple(sorted(self.regime_ids)):
            raise ValueError("regime ids must be sorted")
        seen: set = set()
        for session, regime in self.session_regime:
            if regime not in self.regime_ids:
                raise ValueError("session regime must be a declared regime")
            if session in seen:
                raise ValueError("regime sessions must be unique")
            seen.add(session)
        return self


class RegimePartitionEvidence(FrozenGate2Model):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["PHASE4-REGIME-PARTITION-EVIDENCE-v1"] = (
        "PHASE4-REGIME-PARTITION-EVIDENCE-v1"
    )
    candidate_id: str | None = Field(default=None, pattern=r"^phase4-[0-9a-f]{64}$")
    binding_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    regime_ids: tuple[str, ...] = Field(min_length=1)
    regime_session_counts: tuple[int, ...]
    regime_sessions: tuple[tuple[pd.Timestamp, ...], ...]
    unavailable_statistics: UnavailableStatistics

    @model_validator(mode="after")
    def validate_regime_partition(self) -> "RegimePartitionEvidence":
        if (
            len(self.regime_ids)
            != len(self.regime_session_counts)
            != len(self.regime_sessions)
        ):
            raise ValueError("regime ids, counts, and sessions must align")
        if len(set(self.regime_ids)) != len(self.regime_ids):
            raise ValueError("regime ids must be unique")
        for count, sessions in zip(self.regime_session_counts, self.regime_sessions):
            if count != len(sessions):
                raise ValueError("regime counts must match their sessions")
        if sum(self.regime_session_counts) == 0:
            raise ValueError("regime partition must be nonempty")
        if (self.candidate_id is None) != (self.binding_sha256 is None):
            raise ValueError("candidate and binding identities must align")
        return self


BudgetRowState = Literal[
    "UNATTEMPTED",
    "CONSUMED",
    "SKIPPED_FAMILY_STOP",
    "SKIPPED_PER_FAMILY_BUDGET",
    "SKIPPED_AGGREGATE_BUDGET",
]

BudgetCampaignStatus = Literal[
    "ACTIVE",
    "CAMPAIGN_EXECUTION_FAILED",
    "AGGREGATE_BUDGET_EXHAUSTED",
    "COMPLETE",
]

BudgetFamilyReason = Literal[
    "PERSISTENT_OOS_FAILURE",
    "EXHAUSTED_GRID",
    "PER_FAMILY_BUDGET_EXHAUSTED",
]

_VALID_ROW_STATES = frozenset(
    {
        "UNATTEMPTED",
        "CONSUMED",
        "SKIPPED_FAMILY_STOP",
        "SKIPPED_PER_FAMILY_BUDGET",
        "SKIPPED_AGGREGATE_BUDGET",
    }
)
_VALID_CAMPAIGN_STATUSES = frozenset(
    {
        "ACTIVE",
        "CAMPAIGN_EXECUTION_FAILED",
        "AGGREGATE_BUDGET_EXHAUSTED",
        "COMPLETE",
    }
)


class BudgetState(FrozenGate2Model):
    schema_version: Literal["PHASE4-BUDGET-STATE-v1"] = "PHASE4-BUDGET-STATE-v1"
    campaign_id: Literal["PHASE4-FIXED-LONG-ONLY-2014-2022-v1"] = (
        "PHASE4-FIXED-LONG-ONLY-2014-2022-v1"
    )
    historical_phase2_trials: Literal[136] = 136
    historical_trials_are_lineage_only: Literal[True] = True
    phase4_new_trials_consumed: int = Field(default=0, ge=0, le=3000)
    phase4_new_trials_remaining: int = Field(default=3000, ge=0, le=3000)
    first_phase4_budget_position: Literal[1] = 1
    candidate_ids: tuple[str, ...] = ()
    trial_ids: tuple[str, ...] = ()
    budget_positions: tuple[int, ...] = ()
    family_ranges: tuple[tuple[int, int], ...] = ()
    row_states: tuple[BudgetRowState, ...] = ()
    consumption_ordinals: tuple[int | None, ...] = ()
    next_consumption_ordinal: int = Field(default=1, ge=1)
    traversal_cursor: int = Field(default=0, ge=0)
    active_family_index: int = Field(default=0, ge=0)
    oos_streak: int = Field(default=0, ge=0)
    campaign_status: BudgetCampaignStatus = "ACTIVE"
    campaign_terminated: bool = False
    last_family_reason: BudgetFamilyReason | None = None

    @model_validator(mode="after")
    def validate_budget_state(self) -> "BudgetState":
        total = len(self.candidate_ids)
        if not (
            len(self.candidate_ids)
            == len(self.trial_ids)
            == len(self.budget_positions)
            == len(self.row_states)
            == len(self.consumption_ordinals)
        ):
            raise ValueError("budget row fields must align")
        if total and self.budget_positions != tuple(range(1, total + 1)):
            raise ValueError("budget positions must be contiguous from one")
        if self.phase4_new_trials_consumed + self.phase4_new_trials_remaining != 3000:
            raise ValueError("Phase 4 budget must sum to 3000")
        if not 0 <= self.traversal_cursor <= total:
            raise ValueError("traversal cursor is out of range")
        if self.next_consumption_ordinal != self.phase4_new_trials_consumed + 1:
            raise ValueError("next consumption ordinal must follow the counter")
        covered = 0
        for start, end in self.family_ranges:
            if start != covered or end <= start:
                raise ValueError("family ranges must be contiguous and increasing")
            covered = end
        if covered != total:
            raise ValueError("family ranges must cover the population")
        if not 0 <= self.active_family_index <= len(self.family_ranges):
            raise ValueError("active family index is out of range")
        if any(state not in _VALID_ROW_STATES for state in self.row_states):
            raise ValueError("unknown row state")
        if self.campaign_status not in _VALID_CAMPAIGN_STATUSES:
            raise ValueError("unknown campaign status")
        return self


EvidenceKind = Literal[
    "friction",
    "bootstrap",
    "neighbor",
    "fold",
    "regime",
    "primary",
]


class Gate2EvaluationContext(FrozenGate2Model):
    """Identity inputs shared by every Gate 2 evaluation case."""

    campaign_id: str = Field(min_length=1)
    market_panel_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    warmup_panel_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scored_panel_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scored_reset_configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_sessions_authority_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fold_authority_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    fold_authority_status: str = Field(min_length=1)
    regime_authority_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    regime_authority_status: str = Field(min_length=1)
    initial_cash_float64_hex: str = Field(
        pattern=r"^0x[0-9a-f]+(\.[0-9a-f]+)?p[+-]?[0-9]+$"
    )
    primary_friction_bps: int
    execution_convention: str = Field(min_length=1)
    execution_series: str = Field(min_length=1)
    decision_grade: bool


class Gate2EvidenceRecord(FrozenGate2Model):
    """One evaluation-case record bound to unchanged candidate identities."""

    candidate_id: str = Field(min_length=1)
    family_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameter_tuple_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    engine_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_case_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_kind: EvidenceKind
    case_id: str = Field(min_length=1)
    unavailable_statistics: UnavailableStatistics

    @model_validator(mode="after")
    def validate_case_identity(self) -> "Gate2EvidenceRecord":
        from investment_tracker.quant.phase4.engine.evidence import (
            evaluation_case_identity,
        )

        if self.evaluation_case_sha256 != evaluation_case_identity(
            candidate_id=self.candidate_id,
            family_definition_sha256=self.family_definition_sha256,
            rule_set_sha256=self.rule_set_sha256,
            parameter_tuple_sha256=self.parameter_tuple_sha256,
            engine_implementation_sha256=self.engine_implementation_sha256,
            evaluation_context_sha256=self.evaluation_context_sha256,
            evidence_kind=self.evidence_kind,
            case_id=self.case_id,
        ):
            raise ValueError("evidence record case identity mismatch")
        return self

