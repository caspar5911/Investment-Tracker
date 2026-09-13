from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import platform
import subprocess
from typing import Callable, Literal

import pydantic
from pydantic import Field

from .artifacts import Gate1ArtifactStore
from .baselines import VerifiedBaselines, build_verified_baselines
from .campaign_definition import (
    ADMITTED_HYPOTHESES,
    REJECTED_HYPOTHESES,
    RESEARCH_SOURCES,
)
from .canonical import canonical_sha256
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


RESEARCH_CUTOFF = datetime(2026, 9, 13, 8, 0, 0, tzinfo=timezone.utc)
RECORDED_AT = "2026-09-13T08:00:00.000000Z"


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
    qfq_execution_methodology: Literal["QFQ_NORMALIZED"] = "QFQ_NORMALIZED"
    decision_grade: Literal[False] = False
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
    )
    manifest_identity = store.commit_json(
        "phase4_preregistration_manifest", "manifest.json", manifest.model_dump(mode="json")
    )
    observer("phase4_preregistration_manifest")
    return Gate1SealResult(manifest=manifest, manifest_identity=manifest_identity)


def seal_gate1(repository_root: Path) -> Gate1SealResult:
    try:
        root = Path(repository_root).resolve(strict=True)
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        if len(revision) != 40:
            raise Gate1SealError("producing revision is invalid")
        verified = build_verified_baselines(root)
        return seal_preverified_gate1(root, verified, revision)
    except Gate1SealError:
        raise
    except Exception as exc:
        raise Gate1SealError(
            "Gate 1 prerequisite verification failed",
            "READINESS_MANIFEST_MISMATCH",
        ) from exc
