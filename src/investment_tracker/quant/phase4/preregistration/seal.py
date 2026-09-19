from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import platform
import subprocess
from typing import Callable, Literal

import pydantic
from pydantic import Field, model_validator

from .artifacts import Gate1ArtifactStore
from .baselines import VerifiedBaselines, build_verified_baselines
from .campaign_definition import (
    ADMITTED_HYPOTHESES,
    REJECTED_HYPOTHESES,
    RESEARCH_SOURCES,
)
from .canonical import artifact_envelope_identity, canonical_json_bytes, canonical_sha256
from .grids import PHASE4_CAMPAIGN_ID, build_preregistered_grids
from .journal import Gate1Journal, Gate1JournalState
from .models import FrozenGate1Model, Gate1ArtifactIdentity
from .policy import (
    DQ030UnavailableMetrics,
    DURABILITY_POLICY,
    FAMILY_STOP_POLICY,
    PHASE5_CONTRACT,
    SURVIVOR_POLICY,
    enforce_research_cutoff,
    validate_hypothesis_registry,
)
from .report import build_gate1_report, build_research_notes


RESEARCH_CUTOFF = datetime(2026, 9, 13, 11, 9, 54, 62909, tzinfo=timezone.utc)
RECORDED_AT = "2026-09-13T11:09:54.062909Z"
READINESS_REVALIDATED_REVISION = "b116192d2f8bc814a0f7501b492b981a5ae8f8db"
GATE1_SCHEMA_VERSIONS = (
    "PHASE4-PREREGISTRATION-MANIFEST-v1",
    "PHASE4-JOURNAL-RECORD-v1", "PHASE4-JOURNAL-STATE-v1",
    "PHASE4-RESEARCH-SOURCE-v1", "PHASE4-HYPOTHESIS-v1",
    "PHASE4-BASELINE-DEFINITION-v1", "PHASE4-BASELINE-DEFINITION-SET-v1",
    "PHASE4-STRATEGY-FAMILY-DEFINITION-v1",
    "PHASE4-STRATEGY-FAMILY-DEFINITION-SET-v1",
    "PHASE4-STRATEGY-FAMILY-SEMANTIC-v1",
    "PHASE4-FAMILY-DEFINITION-IDENTITY-v1",
    "PHASE4-RULE-SET-IDENTITY-v1", "PHASE4-PARAMETER-TUPLE-IDENTITY-v1",
    "PHASE4-DETERMINISTIC-GRIDS-v1", "PHASE4-GRID-CANDIDATE-v1",
    "PHASE4-BUDGET-POLICY-v1", "PHASE4-FAMILY-STOP-POLICY-v1",
    "PHASE4-DURABILITY-POLICY-v1", "PHASE4-SURVIVOR-POLICY-v1",
    "PHASE4-GATE1-ACCESS-EVIDENCE-v1",
    "PHASE4-GATE1-RUNTIME-v1",
    "PHASE5-LONG-HISTORY-DURABILITY-CONTRACT-v1",
)


GATE1_FAILURE_CODES = (
    "READINESS_MANIFEST_MISMATCH", "FROZEN_SPLIT_MISMATCH",
    "BASELINE_PROVENANCE_UNRESOLVED", "SOURCE_CHAIN_INVALID",
    "SOURCE_EVIDENCE_INSUFFICIENT", "HYPOTHESIS_CHAIN_INVALID",
    "HYPOTHESIS_SOURCE_MISMATCH", "FAMILY_DEFINITION_MISMATCH",
    "GRID_INVALID", "FAMILY_BUDGET_EXCEEDED", "AGGREGATE_BUDGET_EXCEEDED",
    "DURABILITY_POLICY_INVALID", "SURVIVOR_POLICY_INVALID",
    "GATE1_INFORMATION_BOUNDARY_VIOLATION", "HISTORICAL_ARTIFACT_MUTATION",
    "IMMUTABLE_ARTIFACT_COLLISION", "SEAL_PUBLICATION_FAILED",
)


class Gate1SealError(RuntimeError):
    """Raised when any Gate 1 prerequisite or publication gate fails closed."""

    def __init__(self, message: str, code: str = "SEAL_PUBLICATION_FAILED") -> None:
        if code not in GATE1_FAILURE_CODES:
            raise ValueError("unknown Gate 1 failure code")
        self.code = code
        super().__init__(message)


class FamilyRuleSetIdentity(FrozenGate1Model):
    family_id: str
    rule_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase4PreregistrationManifest(FrozenGate1Model):
    schema_version: Literal["PHASE4-PREREGISTRATION-MANIFEST-v1"] = (
        "PHASE4-PREREGISTRATION-MANIFEST-v1"
    )
    status: Literal["PHASE4_PREREGISTRATION_SEALED"] = "PHASE4_PREREGISTRATION_SEALED"
    campaign_id: str
    producing_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    runtime_dependency_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    universe_digest: str
    dq_snapshot_digest: str
    readiness_manifest: Gate1ArtifactIdentity
    trial_authority: Gate1ArtifactIdentity
    split_manifest: Gate1ArtifactIdentity
    source_journal: Gate1JournalState
    research_cutoff: datetime
    research_notes_path: Literal["results/research/research_notes.md"]
    research_notes_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hypothesis_journal: Gate1JournalState
    baseline_definitions: Gate1ArtifactIdentity
    strategy_family_definitions: Gate1ArtifactIdentity
    deterministic_grids: Gate1ArtifactIdentity
    family_budget_policy: Gate1ArtifactIdentity
    durability_policy: Gate1ArtifactIdentity
    survivor_policy: Gate1ArtifactIdentity
    information_access_policy: Gate1ArtifactIdentity
    observed_read_set: tuple[str, ...]
    research_report: Gate1ArtifactIdentity
    family_rule_set_identities: tuple[FamilyRuleSetIdentity, ...]
    family_rule_set_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_parameter_population_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_count: Literal[9]
    admitted_hypothesis_count: Literal[4]
    rejected_hypothesis_count: Literal[1]
    family_count: Literal[4]
    aggregate_candidate_count: Literal[180]
    baseline_provenance_class_counts: dict[str, int]
    baseline_provenance_status: Literal["VERIFIED"] = "VERIFIED"
    historical_phase2_trials: Literal[136] = 136
    phase4_initial_consumption: Literal[0] = 0
    first_phase4_budget_position: Literal[1] = 1
    fixed_deployment_objective: Literal["ONE_FIXED_LONG_ONLY_STRATEGY_NO_PERIODIC_RETUNING"] = (
        "ONE_FIXED_LONG_ONLY_STRATEGY_NO_PERIODIC_RETUNING"
    )
    deployment_strategy_count: Literal[1] = 1
    position_direction: Literal["LONG_ONLY"] = "LONG_ONLY"
    rule_set_mode: Literal["FIXED"] = "FIXED"
    parameter_tuple_mode: Literal["FIXED"] = "FIXED"
    annual_reoptimization: Literal[False] = False
    periodic_reoptimization: Literal[False] = False
    cagr_hard_target: None = None
    durability_precedes_fitted_cagr: Literal[True] = True
    signal_series: Literal["QFQ"] = "QFQ"
    qfq_execution_methodology: Literal["QFQ_NORMALIZED"] = "QFQ_NORMALIZED"
    qfq_methodology_identity: Literal[
        "ffee9bac3fe329b14d5aebb0f6152f00fc0a86b28d9186c254b5c8f6f8a322fb"
    ] = "ffee9bac3fe329b14d5aebb0f6152f00fc0a86b28d9186c254b5c8f6f8a322fb"
    decision_grade: Literal[False] = False
    schema_versions: tuple[str, ...] = GATE1_SCHEMA_VERSIONS
    max_drawdown_status: Literal["UNKNOWN"] = "UNKNOWN"
    max_drawdown: None = None
    calmar_status: Literal["UNKNOWN"] = "UNKNOWN"
    calmar: None = None
    dsr_status: Literal["UNKNOWN"] = "UNKNOWN"
    dsr_reason: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"
    dsr: None = None
    pbo_status: Literal["UNKNOWN"] = "UNKNOWN"
    pbo_reason: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"
    pbo: None = None
    validation_data_accessed: Literal[False] = False
    validation_metrics_accessed: Literal[False] = False
    campaign_results_accessed: Literal[False] = False
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()
    provider_calls: Literal[0] = 0
    strategy_search_executed: Literal[False] = False
    live_trading_capability: Literal[False] = False
    gate2_authorized: Literal[False] = False
    gate3_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_manifest_links(self) -> "Phase4PreregistrationManifest":
        expected_kinds = {
            "readiness_manifest": "phase4_readiness_manifest",
            "trial_authority": "trial_authority",
            "split_manifest": "phase4_split_manifest",
            "baseline_definitions": "baseline_definitions",
            "strategy_family_definitions": "strategy_family_definitions",
            "deterministic_grids": "deterministic_grids",
            "family_budget_policy": "family_budget_policy",
            "durability_policy": "durability_policy",
            "survivor_policy": "survivor_policy",
            "information_access_policy": "information_access_policy",
            "research_report": "research_report",
        }
        if any(getattr(self, field).kind != kind for field, kind in expected_kinds.items()):
            raise ValueError("manifest artifact-kind cross-link mismatch")
        if self.source_journal.path != "results/research/sources.jsonl" or self.source_journal.record_count != self.source_count:
            raise ValueError("source journal cross-link mismatch")
        if (
            self.hypothesis_journal.path != "results/research/hypothesis_registry.jsonl"
            or self.hypothesis_journal.record_count
            != self.admitted_hypothesis_count + self.rejected_hypothesis_count
        ):
            raise ValueError("hypothesis journal cross-link mismatch")
        if self.baseline_provenance_class_counts != {
            "EXECUTED_PHASE2_BASELINE": 2,
            "SOURCE_DEFINED_PHASE2_GRID_BASELINE": 2,
        }:
            raise ValueError("baseline provenance count mismatch")
        if len(self.family_rule_set_identities) != self.family_count:
            raise ValueError("family rule-set count mismatch")
        if self.family_rule_set_identities != tuple(
            sorted(self.family_rule_set_identities, key=lambda row: row.family_id)
        ) or len({row.family_id for row in self.family_rule_set_identities}) != self.family_count:
            raise ValueError("family rule-set identities must be unique and sorted")
        expected_rule_sets = canonical_sha256(
            tuple(row.model_dump(mode="json") for row in self.family_rule_set_identities)
        )
        if self.family_rule_set_identity_sha256 != expected_rule_sets:
            raise ValueError("family rule-set aggregate identity mismatch")
        from .access import Gate1AccessEvidence

        access_payload = Gate1AccessEvidence(observed_reads=self.observed_read_set)
        if sha256(canonical_json_bytes(access_payload.model_dump(mode="json"))).hexdigest() != self.information_access_policy.content_sha256:
            raise ValueError("observed read set disagrees with access evidence artifact")
        if self.schema_versions != GATE1_SCHEMA_VERSIONS:
            raise ValueError("schema versions do not match the frozen exact set")
        return self


class Gate1SealResult(FrozenGate1Model):
    manifest: Phase4PreregistrationManifest
    manifest_identity: Gate1ArtifactIdentity


def _write_immutable_research_file(root: Path, relative: str, payload: bytes) -> None:
    destination = root.joinpath(*relative.split("/"))
    current = root
    for component in destination.relative_to(root).parts:
        current = current / component
        if current.is_symlink():
            raise Gate1SealError("research path contains a symlink")
    if destination.exists():
        if not destination.is_file() or destination.read_bytes() != payload:
            raise Gate1SealError("immutable research file collision")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            destination,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
            0o600,
        )
        try:
            written = 0
            while written < len(payload):
                count = os.write(descriptor, payload[written:])
                if count <= 0:
                    raise Gate1SealError("research file write made no progress")
                written += count
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except Gate1SealError:
        raise
    except OSError as exc:
        raise Gate1SealError("immutable research file write failed") from exc
    try:
        read_back = destination.read_bytes()
    except OSError as exc:
        raise Gate1SealError("research file read-back failed", "SOURCE_CHAIN_INVALID") from exc
    if read_back != payload:
        raise Gate1SealError("research file read-back mismatch", "SOURCE_CHAIN_INVALID")


def verify_readiness_ancestry(
    repository_root: Path,
    head_revision: str,
    *,
    runner: Callable[..., object] = subprocess.run,
) -> None:
    completed = runner(
        [
            "git", "merge-base", "--is-ancestor",
            READINESS_REVALIDATED_REVISION, head_revision,
        ],
        cwd=repository_root,
        check=False,
        capture_output=True,
    )
    if getattr(completed, "returncode", 1) != 0:
        raise Gate1SealError(
            "readiness revalidation revision is not an ancestor of HEAD",
            "READINESS_MANIFEST_MISMATCH",
        )


def _runtime_identity() -> str:
    return canonical_sha256({
        "schema_version": "PHASE4-GATE1-RUNTIME-v1",
        "python": platform.python_version(),
        "pydantic": pydantic.__version__,
    })


def _publish(
    store: Gate1ArtifactStore,
    kind: str,
    filename: str,
    payload: object | bytes,
    observer: Callable[[str], None],
    fail_after_kind: str | None,
) -> Gate1ArtifactIdentity:
    identity = (
        store.write_bytes(kind, filename, payload)
        if isinstance(payload, bytes)
        else store.write_json(kind, filename, payload)
    )
    observer(kind)
    if fail_after_kind == kind:
        raise Gate1SealError(f"injected failure after {kind}")
    return identity


def seal_preverified_gate1(
    repository_root: Path,
    verified_baselines: VerifiedBaselines,
    producing_revision: str,
    *,
    fail_after_kind: str | None = None,
    write_observer: Callable[[str], None] | None = None,
) -> Gate1SealResult:
    root = Path(repository_root).resolve(strict=True)
    if len(producing_revision) != 40 or any(
        character not in "0123456789abcdef" for character in producing_revision
    ):
        raise Gate1SealError(
            "producing revision is invalid", "READINESS_MANIFEST_MISMATCH"
        )
    observer = write_observer or (lambda _: None)
    sources = enforce_research_cutoff(RESEARCH_SOURCES, RESEARCH_CUTOFF)
    hypotheses = validate_hypothesis_registry(
        sources, ADMITTED_HYPOTHESES + REJECTED_HYPOTHESES
    )
    grids = build_preregistered_grids(ADMITTED_HYPOTHESES)

    source_journal = Gate1Journal(root, root / "results/research/sources.jsonl", record_kind="SOURCE")
    for source in sorted(sources, key=lambda item: item.source_id):
        source_journal.append(source.source_id, source.model_dump(mode="json"), RECORDED_AT)
    source_state = source_journal.verify()
    observer("source_journal")

    hypothesis_journal = Gate1Journal(
        root, root / "results/research/hypothesis_registry.jsonl", record_kind="HYPOTHESIS"
    )
    for hypothesis in sorted(hypotheses, key=lambda item: item.hypothesis_id):
        hypothesis_journal.append(
            hypothesis.hypothesis_id, hypothesis.model_dump(mode="json"), RECORDED_AT
        )
    hypothesis_state = hypothesis_journal.verify()
    observer("hypothesis_journal")

    notes = build_research_notes()
    notes_path = "results/research/research_notes.md"
    _write_immutable_research_file(root, notes_path, notes)
    observer("research_notes")

    store = Gate1ArtifactStore(root, root / "results")
    baseline_identity = _publish(
        store, "baseline_definitions", "baselines.json",
        verified_baselines.baseline_set.model_dump(mode="json"), observer, fail_after_kind,
    )
    family_payload = {
        "schema_version": "PHASE4-STRATEGY-FAMILY-DEFINITION-SET-v1",
        "families": tuple(
            family.model_dump(mode="json", exclude={"candidates"})
            for family in grids.families
        ),
    }
    family_identity_artifact = _publish(
        store, "strategy_family_definitions", "families.json", family_payload,
        observer, fail_after_kind,
    )
    grid_identity = _publish(
        store, "deterministic_grids", "grids.json", grids.model_dump(mode="json"),
        observer, fail_after_kind,
    )
    budget_identity = _publish(
        store, "family_budget_policy", "policy.json",
        {"budget_policy": grids.budget_policy.model_dump(mode="json"),
         "family_stop_policy": FAMILY_STOP_POLICY.model_dump(mode="json")},
        observer, fail_after_kind,
    )
    durability_identity = _publish(
        store, "durability_policy", "policy.json",
        {"durability_policy": DURABILITY_POLICY.model_dump(mode="json"),
         "phase5_downstream_contract": PHASE5_CONTRACT.model_dump(mode="json")},
        observer, fail_after_kind,
    )
    survivor_identity = _publish(
        store, "survivor_policy", "policy.json",
        {"survivor_policy": SURVIVOR_POLICY.model_dump(mode="json"),
         "unavailable_metrics": DQ030UnavailableMetrics().model_dump(mode="json")},
        observer, fail_after_kind,
    )
    access_identity = _publish(
        store, "information_access_policy", "policy.json",
        verified_baselines.access_evidence.model_dump(mode="json"), observer, fail_after_kind,
    )
    report_identity = _publish(
        store, "research_report", "report.md",
        build_gate1_report(verified_baselines.baseline_set, grids), observer, fail_after_kind,
    )

    rule_sets = tuple(
        FamilyRuleSetIdentity(family_id=row.family_id, rule_set_sha256=row.rule_set_sha256)
        for row in grids.families
    )
    first_baseline = verified_baselines.baseline_set.baselines[0]
    manifest = Phase4PreregistrationManifest(
        campaign_id=PHASE4_CAMPAIGN_ID,
        producing_revision=producing_revision,
        runtime_dependency_sha256=_runtime_identity(),
        universe_digest=first_baseline.universe_digest,
        dq_snapshot_digest=first_baseline.dq_snapshot_digest,
        readiness_manifest=first_baseline.readiness_manifest,
        trial_authority=first_baseline.trial_authority,
        split_manifest=first_baseline.split_manifest,
        source_journal=source_state,
        research_cutoff=RESEARCH_CUTOFF,
        research_notes_path=notes_path,
        research_notes_content_sha256=sha256(notes).hexdigest(),
        hypothesis_journal=hypothesis_state,
        baseline_definitions=baseline_identity,
        strategy_family_definitions=family_identity_artifact,
        deterministic_grids=grid_identity,
        family_budget_policy=budget_identity,
        durability_policy=durability_identity,
        survivor_policy=survivor_identity,
        information_access_policy=access_identity,
        observed_read_set=verified_baselines.access_evidence.observed_reads,
        research_report=report_identity,
        family_rule_set_identities=rule_sets,
        family_rule_set_identity_sha256=canonical_sha256(
            tuple(row.model_dump(mode="json") for row in rule_sets)
        ),
        candidate_parameter_population_sha256=grids.candidate_parameter_population_sha256,
        source_count=len(sources),
        admitted_hypothesis_count=len(ADMITTED_HYPOTHESES),
        rejected_hypothesis_count=len(REJECTED_HYPOTHESES),
        family_count=len(grids.families),
        aggregate_candidate_count=len(grids.candidates),
        baseline_provenance_class_counts=verified_baselines.baseline_set.provenance_class_counts,
        qfq_methodology_identity=first_baseline.qfq_methodology_identity,
    )
    manifest_payload = manifest.model_dump(mode="json")
    manifest_content_sha256 = sha256(canonical_json_bytes(manifest_payload)).hexdigest()
    manifest_path = (
        "results/phase4/gate1/phase4_preregistration_manifest/sha256/"
        f"{manifest_content_sha256}/manifest.json"
    )
    expected_manifest_identity = Gate1ArtifactIdentity(
        kind="phase4_preregistration_manifest",
        content_sha256=manifest_content_sha256,
        path=manifest_path,
        sha256=artifact_envelope_identity(
            content_sha256=manifest_content_sha256,
            kind="phase4_preregistration_manifest",
            path=manifest_path,
        ),
    )
    result = Gate1SealResult(
        manifest=manifest, manifest_identity=expected_manifest_identity
    )
    observer("phase4_preregistration_manifest")
    store.commit_json(
        "phase4_preregistration_manifest", "manifest.json", manifest.model_dump(mode="json")
    )
    return result


def seal_gate1(repository_root: Path) -> Gate1SealResult:
    try:
        root = Path(repository_root).resolve(strict=True)
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        if len(revision) != 40:
            raise Gate1SealError("producing revision is invalid")
        verify_readiness_ancestry(root, revision)
        verified = build_verified_baselines(root)
        return seal_preverified_gate1(root, verified, revision)
    except Gate1SealError:
        raise
    except Exception as exc:
        raise Gate1SealError(
            "Gate 1 prerequisite verification failed",
            "READINESS_MANIFEST_MISMATCH",
        ) from exc
