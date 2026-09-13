from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.quant.phase4.preregistration.baselines import (
    BaselineDefinitionSet,
)
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
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


class Gate2Authority(FrozenGate2Model):
    starting_revision: Literal["fb1c30a6c9789bddf2033301977fc8e2f3ebc1a0"]
    head_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    manifest_identity: Gate1ArtifactIdentity
    manifest: Phase4PreregistrationManifest
    grids: PreregisteredGrids
    family_definitions: tuple[StrategyFamilyDefinition, ...]
    baselines: BaselineDefinitionSet
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

    @model_validator(mode="after")
    def validate_authority_links(self) -> "Gate2Authority":
        if self.family_definitions != self.grids.families:
            raise ValueError("family definitions differ from deterministic grids")
        if len({item.path for item in self.direct_dependencies}) != 15:
            raise ValueError("direct dependency paths must be unique")
        if self.manifest.candidate_parameter_population_sha256 != (
            self.grids.candidate_parameter_population_sha256
        ):
            raise ValueError("candidate population differs from Gate 1 manifest")
        if self.manifest.historical_phase2_trials != self.historical_phase2_trials:
            raise ValueError("historical trial count differs from Gate 1 manifest")
        if self.manifest.phase4_initial_consumption != self.phase4_trials_consumed:
            raise ValueError("Phase 4 consumption differs from Gate 1 manifest")
        return self
