from __future__ import annotations

from hashlib import sha256
import json
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.quant.phase4.preregistration.baselines import (
    BaselineDefinitionSet,
)
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
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
