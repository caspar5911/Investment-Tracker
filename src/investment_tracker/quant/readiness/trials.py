from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Literal

from pydantic import Field, model_validator

from investment_tracker.quant.experiments import ExperimentRecord

from .constants import PHASE2_CAMPAIGN_ID
from .hashing import (
    ArtifactIdentityError,
    artifact_identity,
    normalize_repository_path,
    trial_identity,
)
from .models import (
    AuthoritativeTrial,
    FrozenReadinessModel,
    ReadinessArtifactIdentity,
)


PRELIMINARY_SOURCE_REVISION = "d4b2dfc3bee03ad81e389cc2e21876f38fbf325f"
FINAL_SOURCE_REVISION = "c33fb0757f0ea8147749130fed90d278aed4fafe"
CORRECTED_ENGINE_VERSION = "QUANT-ENGINE-v1+SEARCH-POLICY-v2"
ORIGINAL_ENGINE_VERSION = "QUANT-ENGINE-v1"
EXPERIMENT_SCHEMA_VERSION = "QUANT-EXPERIMENT-v1"
CANDIDATE_MANIFEST_SCHEMA_VERSION = "RESEARCH-CANDIDATE-MANIFEST-v1"
REPRESENTATION_SELECTOR_VERSION = "PHASE2-REPRESENTATION-SELECTOR-v1"
HISTORICAL_PHASE2_TRIAL_COUNT = 136

RepresentationClass = Literal[
    "ORIGINAL",
    "PRELIMINARY_CORRECTED",
    "FINAL_AUTHORITATIVE",
    "OUT_OF_SCOPE",
    "AMBIGUOUS",
]


class TrialAuthorityError(RuntimeError):
    """Raised when preserved evidence cannot yield one authoritative trial set."""


class ExperimentEvidence(FrozenReadinessModel):
    record: ExperimentRecord
    artifact: ReadinessArtifactIdentity

    @model_validator(mode="after")
    def validate_phase2_artifact(self) -> "ExperimentEvidence":
        if self.artifact.kind != "phase2_experiment":
            raise ValueError("experiment evidence must use phase2_experiment identity")
        return self


def _artifact_key(identity: ReadinessArtifactIdentity) -> tuple[str, str, str, str]:
    return (
        identity.kind,
        identity.path,
        identity.content_sha256,
        identity.sha256,
    )


class TrialAuthorityManifest(FrozenReadinessModel):
    schema_version: Literal["PHASE4-TRIAL-AUTHORITY-v1"] = (
        "PHASE4-TRIAL-AUTHORITY-v1"
    )
    campaign_id: Literal["PHASE2-CORRECTED-2010-2022-c33fb075"] = (
        PHASE2_CAMPAIGN_ID
    )
    representation_selector_version: Literal[
        "PHASE2-REPRESENTATION-SELECTOR-v1"
    ] = REPRESENTATION_SELECTOR_VERSION
    historical_phase2_trial_count: Literal[136] = HISTORICAL_PHASE2_TRIAL_COUNT
    total_representation_count: int = Field(ge=136)
    original_representation_count: int = Field(ge=0)
    preliminary_representation_count: int = Field(ge=136)
    final_authoritative_representation_count: Literal[136] = (
        HISTORICAL_PHASE2_TRIAL_COUNT
    )
    out_of_scope_representation_count: int = Field(ge=0)
    source_revisions: tuple[str, ...] = Field(min_length=1)
    non_authoritative_artifacts: tuple[ReadinessArtifactIdentity, ...] = Field(
        min_length=136
    )
    trials: tuple[AuthoritativeTrial, ...] = Field(min_length=136, max_length=136)

    @model_validator(mode="after")
    def validate_authority(self) -> "TrialAuthorityManifest":
        counted = (
            self.original_representation_count
            + self.preliminary_representation_count
            + self.final_authoritative_representation_count
            + self.out_of_scope_representation_count
        )
        if counted != self.total_representation_count:
            raise ValueError("representation counts do not match total")
        candidate_ids = tuple(trial.candidate_id for trial in self.trials)
        trial_ids = tuple(trial.trial_id for trial in self.trials)
        if candidate_ids != tuple(sorted(candidate_ids)):
            raise ValueError("authoritative trials must be candidate-ID sorted")
        if len(set(candidate_ids)) != HISTORICAL_PHASE2_TRIAL_COUNT:
            raise ValueError("authoritative candidate IDs must be unique")
        if len(set(trial_ids)) != HISTORICAL_PHASE2_TRIAL_COUNT:
            raise ValueError("authoritative trial IDs must be unique")
        if any(trial.campaign_id != self.campaign_id for trial in self.trials):
            raise ValueError("authoritative trial campaign mismatch")
        if self.source_revisions != tuple(sorted(set(self.source_revisions))):
            raise ValueError("source revisions must be unique and sorted")
        non_authoritative_keys = tuple(
            _artifact_key(identity)
            for identity in self.non_authoritative_artifacts
        )
        if non_authoritative_keys != tuple(sorted(non_authoritative_keys)):
            raise ValueError("non-authoritative artifacts must be sorted")
        if len(set(non_authoritative_keys)) != len(non_authoritative_keys):
            raise ValueError("non-authoritative artifact identities must be unique")
        if len(non_authoritative_keys) != (
            self.total_representation_count
            - self.final_authoritative_representation_count
        ):
            raise ValueError("non-authoritative lineage does not match counts")
        trial_lineage_keys = {
            _artifact_key(identity)
            for trial in self.trials
            for identity in trial.non_authoritative_artifacts
        }
        if not trial_lineage_keys.issubset(set(non_authoritative_keys)):
            raise ValueError("per-trial lineage is absent from complete lineage")
        return self


def classify_representation(record: ExperimentRecord) -> RepresentationClass:
    manifest = record.candidate_manifest
    correct_schemas = (
        record.schema_version == EXPERIMENT_SCHEMA_VERSION
        and manifest.schema_version == CANDIDATE_MANIFEST_SCHEMA_VERSION
    )
    predicates: tuple[tuple[RepresentationClass, bool], ...] = (
        ("ORIGINAL", manifest.engine_version == ORIGINAL_ENGINE_VERSION),
        (
            "PRELIMINARY_CORRECTED",
            correct_schemas
            and manifest.engine_version == CORRECTED_ENGINE_VERSION
            and manifest.git_commit == PRELIMINARY_SOURCE_REVISION
            and "loss_rate" not in record.validation_metrics,
        ),
        (
            "FINAL_AUTHORITATIVE",
            correct_schemas
            and manifest.engine_version == CORRECTED_ENGINE_VERSION
            and manifest.git_commit == FINAL_SOURCE_REVISION
            and "loss_rate" in record.validation_metrics,
        ),
    )
    matches = tuple(name for name, matched in predicates if matched)
    if len(matches) > 1:
        return "AMBIGUOUS"
    if matches:
        return matches[0]
    return "OUT_OF_SCOPE"


def build_authority_from_records(
    representations: Iterable[ExperimentEvidence],
) -> TrialAuthorityManifest:
    evidence = tuple(representations)
    if not evidence:
        raise TrialAuthorityError("historical experiment evidence is empty")

    artifact_keys = tuple(_artifact_key(item.artifact) for item in evidence)
    if len(artifact_keys) != len(set(artifact_keys)):
        raise TrialAuthorityError("ambiguous duplicate artifact identity")

    classified = tuple((item, classify_representation(item.record)) for item in evidence)
    if any(category == "AMBIGUOUS" for _, category in classified):
        raise TrialAuthorityError("ambiguous historical representation")

    preliminary_ids = {
        item.record.candidate_manifest.candidate_id
        for item, category in classified
        if category == "PRELIMINARY_CORRECTED"
    }
    if len(preliminary_ids) != HISTORICAL_PHASE2_TRIAL_COUNT:
        raise TrialAuthorityError(
            "preliminary corrected evidence must contain exactly 136 candidate IDs"
        )

    finals: dict[str, list[ExperimentEvidence]] = defaultdict(list)
    for item, category in classified:
        if category == "FINAL_AUTHORITATIVE":
            finals[item.record.candidate_manifest.candidate_id].append(item)
    if set(finals) != preliminary_ids:
        raise TrialAuthorityError(
            "final authoritative candidate IDs differ from preliminary evidence"
        )
    if any(len(items) != 1 for items in finals.values()):
        raise TrialAuthorityError(
            "each candidate requires exactly one authoritative representation"
        )

    by_candidate: dict[str, list[tuple[ExperimentEvidence, RepresentationClass]]] = (
        defaultdict(list)
    )
    for item, category in classified:
        by_candidate[item.record.candidate_manifest.candidate_id].append(
            (item, category)
        )

    all_non_authoritative = tuple(
        sorted(
            (
                item.artifact
                for item, category in classified
                if category != "FINAL_AUTHORITATIVE"
            ),
            key=_artifact_key,
        )
    )

    trials = []
    for candidate_id in sorted(preliminary_ids):
        authoritative = finals[candidate_id][0]
        non_authoritative = tuple(
            sorted(
                (
                    item.artifact
                    for item, category in by_candidate[candidate_id]
                    if category != "FINAL_AUTHORITATIVE"
                ),
                key=_artifact_key,
            )
        )
        trials.append(
            AuthoritativeTrial(
                trial_id=trial_identity(PHASE2_CAMPAIGN_ID, candidate_id),
                campaign_id=PHASE2_CAMPAIGN_ID,
                candidate_id=candidate_id,
                authoritative_artifact=authoritative.artifact,
                non_authoritative_artifacts=non_authoritative,
            )
        )

    counts = Counter(category for _, category in classified)
    return TrialAuthorityManifest(
        total_representation_count=len(classified),
        original_representation_count=counts["ORIGINAL"],
        preliminary_representation_count=counts["PRELIMINARY_CORRECTED"],
        final_authoritative_representation_count=counts["FINAL_AUTHORITATIVE"],
        out_of_scope_representation_count=counts["OUT_OF_SCOPE"],
        source_revisions=tuple(
            sorted(
                {
                    item.record.candidate_manifest.git_commit
                    for item, _ in classified
                }
            )
        ),
        non_authoritative_artifacts=all_non_authoritative,
        trials=tuple(trials),
    )


def build_trial_authority(
    repository_root: Path,
    experiments_root: Path,
) -> TrialAuthorityManifest:
    repository = Path(repository_root)
    experiments = Path(experiments_root)
    if not experiments.is_absolute():
        experiments = repository / experiments
    try:
        normalize_repository_path(repository, experiments)
    except ArtifactIdentityError as exc:
        raise TrialAuthorityError(f"experiment root is unsafe: {exc}") from exc
    if not experiments.is_dir() or experiments.is_symlink():
        raise TrialAuthorityError("experiment root must be a regular directory")

    loaded: list[ExperimentEvidence] = []
    for path in experiments.glob("*.json"):
        if not path.is_file() or path.is_symlink():
            raise TrialAuthorityError(f"experiment artifact is not regular: {path}")
        try:
            identity = artifact_identity(repository, path, "phase2_experiment")
            payload = path.read_bytes()
            if sha256(payload).hexdigest() != identity.content_sha256:
                raise TrialAuthorityError(
                    f"experiment artifact changed while reading: {identity.path}"
                )
            parsed = json.loads(payload)
            record = ExperimentRecord.model_validate(parsed)
        except TrialAuthorityError:
            raise
        except Exception as exc:
            raise TrialAuthorityError(f"invalid experiment artifact: {path}") from exc
        loaded.append(ExperimentEvidence(record=record, artifact=identity))
    return build_authority_from_records(loaded)
