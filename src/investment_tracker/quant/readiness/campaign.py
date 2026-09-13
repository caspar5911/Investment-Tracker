from __future__ import annotations

from hashlib import sha256
from importlib import metadata as importlib_metadata
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from investment_tracker.quant.experiments import ExperimentRecord

from .artifacts import ReadinessArtifactIntegrityError, ReadinessArtifactStore
from .bootstrap_audit import (
    BootstrapAudit,
    BootstrapEvidenceError,
    BootstrapInputVector,
    audit_bootstrap_vector,
    load_pinned_bootstrap_source,
    reconstruct_bootstrap_vector,
)
from .hashing import (
    ArtifactIdentityError,
    artifact_identity,
    canonical_json_bytes,
    canonical_sha256,
    normalize_repository_path,
)
from .models import FrozenReadinessModel, ReadinessArtifactIdentity
from .report import (
    Phase4ReadinessSummary,
    ProtectedTreeDigest,
    ReadinessReportError,
    render_readiness_report,
)
from .split import (
    Phase3DependencyError,
    Phase4CampaignConfiguration,
    Phase4SplitManifest,
    build_campaign_configuration,
    build_split_manifest,
    verify_phase3_dependencies,
)
from .statistics import (
    SearchAwareInputError,
    SearchAwareInputSet,
    SearchAwareStatisticResult,
    build_search_aware_inputs,
    unimplemented_search_statistic,
)
from .trials import (
    TrialAuthorityError,
    TrialAuthorityManifest,
    build_trial_authority,
)


PROTECTED_HISTORICAL_TREES = (
    "data/cache/phase3",
    "results/experiments",
    "results/phase3",
)


class TrialAuthorityEvidence(FrozenReadinessModel):
    schema_version: Literal["PHASE4-TRIAL-AUTHORITY-EVIDENCE-v1"] = (
        "PHASE4-TRIAL-AUTHORITY-EVIDENCE-v1"
    )
    authority: TrialAuthorityManifest
    search_aware_inputs: SearchAwareInputSet

    @model_validator(mode="after")
    def validate_trial_linkage(self) -> "TrialAuthorityEvidence":
        authority_ids = tuple(trial.trial_id for trial in self.authority.trials)
        if self.search_aware_inputs.ordered_sharpe_trial_ids != authority_ids:
            raise ValueError("search-aware inputs differ from trial authority")
        return self


class Phase4ReadinessManifest(FrozenReadinessModel):
    schema_version: Literal["PHASE4-READINESS-MANIFEST-v1"] = (
        "PHASE4-READINESS-MANIFEST-v1"
    )
    status: Literal["PHASE_4_READY"] = "PHASE_4_READY"
    source_revision: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    dependency_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    bootstrap_input_vector: ReadinessArtifactIdentity
    bootstrap_audit: ReadinessArtifactIdentity
    trial_authority: ReadinessArtifactIdentity
    split_manifest: ReadinessArtifactIdentity
    campaign_configuration: ReadinessArtifactIdentity
    readiness_report: ReadinessArtifactIdentity
    historical_phase2_trial_count: Literal[136] = 136
    phase4_new_trials_consumed: Literal[0] = 0
    phase4_new_trials_remaining: Literal[3000] = 3000
    dsr: SearchAwareStatisticResult
    pbo: SearchAwareStatisticResult
    signal_series: Literal["QFQ"] = "QFQ"
    execution_series: Literal["QFQ_NORMALIZED"] = "QFQ_NORMALIZED"
    decision_grade: Literal[False] = False
    provider_calls: Literal[0] = 0
    external_strategy_research_performed: Literal[False] = False
    strategy_search_executed: Literal[False] = False
    strategy_discovery_authorized: Literal[False] = False
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()
    live_trading_capability: Literal[False] = False
    protected_tree_digests: tuple[ProtectedTreeDigest, ...] = Field(
        min_length=3,
        max_length=3,
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> "Phase4ReadinessManifest":
        expected_kinds = {
            "bootstrap_input_vector": "bootstrap_input_vector",
            "bootstrap_audit": "bootstrap_audit",
            "trial_authority": "trial_authority",
            "split_manifest": "phase4_split_manifest",
            "campaign_configuration": "phase4_campaign_configuration",
            "readiness_report": "phase4_readiness_report",
        }
        if any(
            getattr(self, name).kind != kind
            for name, kind in expected_kinds.items()
        ):
            raise ValueError("readiness manifest artifact kind mismatch")
        if self.dsr.name != "DSR" or self.pbo.name != "PBO":
            raise ValueError("readiness manifest statistic mismatch")
        return self


class Phase4ReadinessOutcome(FrozenReadinessModel):
    status: Literal["PHASE_4_READY", "READINESS_FAILED"]
    reason_code: str | None = None
    reason: str | None = None
    manifest: ReadinessArtifactIdentity | None = None
    report: ReadinessArtifactIdentity | None = None
    summary: Phase4ReadinessSummary | None = None
    provider_calls: Literal[0] = 0
    strategy_search_executed: Literal[False] = False

    @model_validator(mode="after")
    def validate_outcome(self) -> "Phase4ReadinessOutcome":
        if self.status == "PHASE_4_READY":
            if (
                self.reason_code is not None
                or self.reason is not None
                or self.manifest is None
                or self.report is None
                or self.summary is None
            ):
                raise ValueError("ready outcome requires complete evidence")
        elif self.reason_code is None or self.reason is None or self.manifest is not None:
            raise ValueError("failed outcome requires a reason and no ready manifest")
        return self


def _failed(reason_code: str, exc: Exception) -> Phase4ReadinessOutcome:
    return Phase4ReadinessOutcome(
        status="READINESS_FAILED",
        reason_code=reason_code,
        reason=str(exc) or exc.__class__.__name__,
    )


def _runtime_source_revision(repository_root: Path) -> str:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReadinessArtifactIntegrityError(
            "source revision is unavailable for the configured repository"
        ) from exc
    if re.fullmatch(r"[0-9a-f]{40,64}", revision) is None:
        raise ReadinessArtifactIntegrityError("source revision is not canonical")
    return revision


def _runtime_dependency_identity() -> str:
    packages = sorted(
        (
            distribution.metadata.get("Name", "UNKNOWN"),
            distribution.version,
        )
        for distribution in importlib_metadata.distributions()
    )
    return canonical_sha256(
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": packages,
        }
    )


def _verified_runtime_identities(
    repository_root: Path,
    *,
    source_revision: str | None,
    dependency_identity: str | None,
) -> tuple[str, str]:
    revision = (
        _runtime_source_revision(repository_root)
        if source_revision is None
        else source_revision
    )
    dependencies = (
        _runtime_dependency_identity()
        if dependency_identity is None
        else dependency_identity
    )
    if not isinstance(revision, str) or re.fullmatch(
        r"[0-9a-f]{40,64}", revision
    ) is None:
        raise ReadinessArtifactIntegrityError("source revision is not canonical")
    if not isinstance(dependencies, str) or re.fullmatch(
        r"[0-9a-f]{64}", dependencies
    ) is None:
        raise ReadinessArtifactIntegrityError("dependency identity is not canonical")
    return revision, dependencies


def _scan_protected_tree_digest(repository_root: Path, relative_path: str) -> str:
    try:
        normalized = normalize_repository_path(
            repository_root,
            Path(*PurePosixPath(relative_path).parts),
        )
    except (ArtifactIdentityError, OSError, ValueError) as exc:
        raise ReadinessArtifactIntegrityError(
            f"protected historical tree path is invalid: {relative_path}"
        ) from exc
    if normalized != relative_path:
        raise ReadinessArtifactIntegrityError(
            f"protected historical tree path changed: {relative_path}"
        )
    root = repository_root.joinpath(*PurePosixPath(relative_path).parts)
    if not root.is_dir() or root.is_symlink():
        raise ReadinessArtifactIntegrityError(
            f"protected historical tree is missing or non-regular: {relative_path}"
        )
    entries: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ReadinessArtifactIntegrityError(
                f"protected historical tree contains a symlink: {relative_path}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise ReadinessArtifactIntegrityError(
                f"protected historical tree contains a non-regular entry: {relative_path}"
            )
        entries.append(
            (
                path.relative_to(root).as_posix(),
                sha256(path.read_bytes()).hexdigest(),
            )
        )
    if not entries:
        raise ReadinessArtifactIntegrityError(
            f"protected historical tree is empty: {relative_path}"
        )
    return canonical_sha256(entries)


def _protected_tree_digest(repository_root: Path, relative_path: str) -> str:
    try:
        return _scan_protected_tree_digest(repository_root, relative_path)
    except ReadinessArtifactIntegrityError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise ReadinessArtifactIntegrityError(
            f"protected historical tree cannot be read: {relative_path}: {exc}"
        ) from exc


def _protected_tree_digests(
    repository_root: Path,
) -> tuple[ProtectedTreeDigest, ...]:
    return tuple(
        ProtectedTreeDigest(
            path=relative_path,
            sha256=_protected_tree_digest(repository_root, relative_path),
        )
        for relative_path in PROTECTED_HISTORICAL_TREES
    )


def _authoritative_records(
    repository_root: Path,
    authority: TrialAuthorityManifest,
) -> dict[str, ExperimentRecord]:
    records: dict[str, ExperimentRecord] = {}
    for trial in authority.trials:
        identity = trial.authoritative_artifact
        path = repository_root.joinpath(*PurePosixPath(identity.path).parts)
        try:
            if artifact_identity(
                repository_root,
                path,
                "phase2_experiment",
            ) != identity:
                raise TrialAuthorityError(
                    f"authoritative experiment identity changed: {identity.path}"
                )
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != identity.content_sha256:
                raise TrialAuthorityError(
                    f"authoritative experiment changed while reading: {identity.path}"
                )
            records[trial.trial_id] = ExperimentRecord.model_validate_json(raw)
        except TrialAuthorityError:
            raise
        except Exception as exc:
            raise TrialAuthorityError(
                f"authoritative experiment is invalid: {identity.path}"
            ) from exc
    return records


def _verify_written_artifacts(
    store: ReadinessArtifactStore,
    *,
    vector: ReadinessArtifactIdentity,
    audit: ReadinessArtifactIdentity,
    authority: ReadinessArtifactIdentity,
    split: ReadinessArtifactIdentity,
    configuration: ReadinessArtifactIdentity,
) -> tuple[
    BootstrapInputVector,
    BootstrapAudit,
    TrialAuthorityEvidence,
    Phase4SplitManifest,
    Phase4CampaignConfiguration,
]:
    try:
        return (
            BootstrapInputVector.model_validate(store.read_json(vector)),
            BootstrapAudit.model_validate(store.read_json(audit)),
            TrialAuthorityEvidence.model_validate(store.read_json(authority)),
            Phase4SplitManifest.model_validate(store.read_json(split)),
            Phase4CampaignConfiguration.model_validate(
                store.read_json(configuration)
            ),
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise ReadinessArtifactIntegrityError(
            "written readiness artifact failed model revalidation"
        ) from exc


def run_phase4_readiness(
    repository_root: Path,
    results_root: Path,
    *,
    source_revision: str | None = None,
    dependency_identity: str | None = None,
) -> Phase4ReadinessOutcome:
    try:
        configured_repository = Path(repository_root)
        configured_results = Path(results_root)
        store = ReadinessArtifactStore(configured_repository, configured_results)
        repository = configured_repository.resolve(strict=True)
        if not configured_results.is_absolute():
            configured_results = repository / configured_results
        if normalize_repository_path(repository, configured_results) != "results":
            raise ReadinessArtifactIntegrityError(
                "results root must be the repository results directory"
            )
        before_trees = _protected_tree_digests(repository)
    except Exception as exc:
        return _failed("ROOT_VALIDATION_FAILED", exc)

    try:
        verified_source_revision, verified_dependency_identity = (
            _verified_runtime_identities(
                repository,
                source_revision=source_revision,
                dependency_identity=dependency_identity,
            )
        )
    except ReadinessArtifactIntegrityError as exc:
        return _failed("RUNTIME_IDENTITY_FAILED", exc)

    try:
        source = load_pinned_bootstrap_source(repository)
    except BootstrapEvidenceError as exc:
        return _failed("PINNED_BOOTSTRAP_SOURCE_MISMATCH", exc)

    try:
        vector_model = reconstruct_bootstrap_vector(repository, source)
        vector_identity = store.write_json(
            "bootstrap_input_vector",
            "vector.json",
            vector_model.model_dump(mode="json"),
        )
    except BootstrapEvidenceError as exc:
        return _failed("BOOTSTRAP_VECTOR_MISMATCH", exc)
    except ReadinessArtifactIntegrityError as exc:
        return _failed("ARTIFACT_INTEGRITY_MISMATCH", exc)

    try:
        audit_model = audit_bootstrap_vector(vector_model, source)
        audit_identity = store.write_json(
            "bootstrap_audit",
            "audit.json",
            audit_model.model_dump(mode="json"),
        )
    except BootstrapEvidenceError as exc:
        return _failed("BOOTSTRAP_AUDIT_MISMATCH", exc)
    except ReadinessArtifactIntegrityError as exc:
        return _failed("ARTIFACT_INTEGRITY_MISMATCH", exc)

    try:
        authority_model = build_trial_authority(
            repository,
            repository / "results" / "experiments",
        )
        records = _authoritative_records(repository, authority_model)
        search_inputs = build_search_aware_inputs(authority_model, records)
        authority_evidence = TrialAuthorityEvidence(
            authority=authority_model,
            search_aware_inputs=search_inputs,
        )
        authority_identity = store.write_json(
            "trial_authority",
            "authority.json",
            authority_evidence.model_dump(mode="json"),
        )
    except (TrialAuthorityError, SearchAwareInputError, ValidationError) as exc:
        return _failed("TRIAL_AUTHORITY_MISMATCH", exc)
    except ReadinessArtifactIntegrityError as exc:
        return _failed("ARTIFACT_INTEGRITY_MISMATCH", exc)

    dsr = unimplemented_search_statistic(
        "DSR",
        "Deflated Sharpe Ratio is not implemented for this readiness audit.",
    )
    pbo = unimplemented_search_statistic(
        "PBO",
        "Probability of Backtest Overfitting is not implemented for this readiness audit.",
    )

    try:
        verified_phase3 = verify_phase3_dependencies(repository)
    except Phase3DependencyError as exc:
        return _failed("PHASE3_DEPENDENCY_MISMATCH", exc)

    try:
        split_model = build_split_manifest(verified_phase3)
        split_identity = store.write_json(
            "phase4_split_manifest",
            "manifest.json",
            split_model.model_dump(mode="json"),
        )
        configuration_model = build_campaign_configuration(split_identity)
        configuration_identity = store.write_json(
            "phase4_campaign_configuration",
            "configuration.json",
            configuration_model.model_dump(mode="json"),
        )
    except Phase3DependencyError as exc:
        return _failed("SPLIT_OR_CONFIGURATION_MISMATCH", exc)
    except ReadinessArtifactIntegrityError as exc:
        return _failed("ARTIFACT_INTEGRITY_MISMATCH", exc)

    try:
        (
            verified_vector,
            verified_audit,
            verified_authority,
            verified_split,
            verified_configuration,
        ) = _verify_written_artifacts(
            store,
            vector=vector_identity,
            audit=audit_identity,
            authority=authority_identity,
            split=split_identity,
            configuration=configuration_identity,
        )
    except ReadinessArtifactIntegrityError as exc:
        return _failed("ARTIFACT_INTEGRITY_MISMATCH", exc)

    try:
        after_trees = _protected_tree_digests(repository)
        if after_trees != before_trees:
            raise ReadinessArtifactIntegrityError(
                "protected historical artifact tree changed during readiness audit"
            )
    except (
        ReadinessArtifactIntegrityError,
        OSError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        return _failed("PROTECTED_TREE_MUTATION", exc)

    try:
        if (
            verified_vector.sha256 != vector_model.sha256
            or verified_audit != audit_model
            or verified_authority.authority.historical_phase2_trial_count != 136
            or verified_authority.search_aware_inputs.historical_trial_count != 136
            or verified_split.provider_calls != 0
            or verified_split.final_holdout_accessed is not False
            or verified_split.protected_symbols_accessed != ()
            or verified_configuration.provider_calls != 0
            or verified_configuration.external_strategy_research_performed is not False
            or verified_configuration.strategy_search_executed is not False
            or verified_configuration.final_holdout_accessed is not False
            or verified_configuration.protected_symbols_accessed != ()
            or verified_configuration.live_trading_capability is not False
            or verified_configuration.decision_grade is not False
            or dsr.interpretation != "UNKNOWN"
            or pbo.interpretation != "UNKNOWN"
        ):
            raise ValueError("in-process readiness safety assertion failed")
    except (AttributeError, TypeError, ValueError) as exc:
        return _failed("SAFETY_ASSERTION_FAILED", exc)

    first_partition = verified_split.partitions[0]
    try:
        summary = Phase4ReadinessSummary(
            bootstrap_source=source.artifact,
            phase3_universe=verified_split.phase3_universe_artifact,
            phase3_dq_snapshot=verified_split.phase3_dq_snapshot_artifact,
            bootstrap_input_vector=vector_identity,
            bootstrap_audit=audit_identity,
            trial_authority=authority_identity,
            split_manifest=split_identity,
            campaign_configuration=configuration_identity,
            bootstrap_negative_count=verified_vector.negative_count,
            bootstrap_zero_count=verified_vector.zero_count,
            bootstrap_positive_count=verified_vector.positive_count,
            bootstrap_interval=verified_audit.interval,
            bootstrap_draws=verified_audit.draws,
            bootstrap_seed=verified_audit.seed,
            bootstrap_lower_percentile=verified_audit.lower_percentile,
            bootstrap_upper_percentile=verified_audit.upper_percentile,
            bootstrap_zero_resampled_medians=(
                verified_audit.zero_resampled_medians
            ),
            historical_phase2_trial_count=(
                verified_authority.authority.historical_phase2_trial_count
            ),
            phase4_new_trials_consumed=(
                verified_configuration.phase4_new_trials_consumed
            ),
            phase4_new_trials_remaining=(
                verified_configuration.phase4_new_trials_remaining
            ),
            maximum_new_strategy_families=(
                verified_configuration.maximum_new_strategy_families
            ),
            maximum_candidate_trials_per_family=(
                verified_configuration.maximum_candidate_trials_per_family
            ),
            maximum_aggregate_new_candidate_trials=(
                verified_configuration.maximum_aggregate_new_candidate_trials
            ),
            dsr=dsr,
            pbo=pbo,
            symbols=verified_split.symbols,
            train_declared_start=first_partition.train.declared_start,
            train_declared_end=first_partition.train.declared_end,
            train_actual_start=first_partition.train.actual_start,
            train_actual_end=first_partition.train.actual_end,
            train_row_count=first_partition.train.row_count,
            validation_declared_start=first_partition.validation.declared_start,
            validation_declared_end=first_partition.validation.declared_end,
            validation_actual_start=first_partition.validation.actual_start,
            validation_actual_end=first_partition.validation.actual_end,
            validation_row_count=first_partition.validation.row_count,
            protected_tree_digests=after_trees,
        )
        report_text = render_readiness_report(summary)
        report_identity = store.write_text(
            "phase4_readiness_report",
            "report.md",
            report_text,
        )
        if store.read_text(report_identity) != report_text:
            raise ReadinessArtifactIntegrityError(
                "written readiness report does not match rendered summary"
            )
        manifest_model = Phase4ReadinessManifest(
            source_revision=verified_source_revision,
            dependency_identity=verified_dependency_identity,
            bootstrap_input_vector=summary.bootstrap_input_vector,
            bootstrap_audit=summary.bootstrap_audit,
            trial_authority=summary.trial_authority,
            split_manifest=summary.split_manifest,
            campaign_configuration=summary.campaign_configuration,
            readiness_report=report_identity,
            dsr=summary.dsr,
            pbo=summary.pbo,
            protected_tree_digests=summary.protected_tree_digests,
        )
        manifest_payload = manifest_model.model_dump(mode="json")
        Phase4ReadinessManifest.model_validate(manifest_payload)
        manifest_bytes = canonical_json_bytes(manifest_payload)
        manifest_content_sha256 = sha256(manifest_bytes).hexdigest()
        manifest_path = (
            "results/phase4/readiness/phase4_readiness_manifest/sha256/"
            f"{manifest_content_sha256}/manifest.json"
        )
        expected_manifest_identity = ReadinessArtifactIdentity(
            kind="phase4_readiness_manifest",
            content_sha256=manifest_content_sha256,
            path=manifest_path,
            sha256=canonical_sha256(
                {
                    "content_sha256": manifest_content_sha256,
                    "kind": "phase4_readiness_manifest",
                    "path": manifest_path,
                }
            ),
        )
        ready_outcome = Phase4ReadinessOutcome(
            status="PHASE_4_READY",
            manifest=expected_manifest_identity,
            report=report_identity,
            summary=summary,
        )
        store.write_json(
            "phase4_readiness_manifest",
            "manifest.json",
            manifest_payload,
        )
    except (
        ReadinessArtifactIntegrityError,
        ReadinessReportError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        return _failed("FINAL_READINESS_EVIDENCE_FAILED", exc)

    return ready_outcome
