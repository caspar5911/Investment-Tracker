"""Quote-free, exact-byte Gate 3 execution-methodology seal and preflight."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import Field

from investment_tracker.quant.phase4.engine.authority import load_gate2_authority
from investment_tracker.quant.phase4.engine.source_identity import (
    SourceBundleIdentity,
    source_bundle_identity,
)
from investment_tracker.quant.phase4.gate3.filesystem import contained_path, resolve_repository_root
from investment_tracker.quant.phase4.gate3.models import (
    ArtifactIdentity,
    DataPartitionIdentity,
    FrozenGate3Model,
    SafetyState,
)
from investment_tracker.quant.phase4.gate3.seal import (
    GATE1_MANIFEST_IDENTITY,
    GATE2_MANIFEST_IDENTITY,
    TRAIN_IDENTITY,
    VALIDATION_IDENTITY,
    _validate_source_revision,
    preflight_gate3,
)
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    canonical_sha256,
)

from .artifacts import MethodologyEvidenceStore
from .campaign import POPULATION_SHA256
from .regimes import FROZEN_REGIME_DEFINITION_SHA256


SPEC_PATH = "docs/superpowers/specs/2026-09-15-phase-4-gate-3-execution-methodology-design.md"
SPEC_CONTENT_SHA256 = "33b5c3d32b2f17aafdc30265b9f59a4a68455afb9b2b0a1df285d893ab0493ec"
CORRECTED_GATE3_MANIFEST = ArtifactIdentity(
    kind="gate3_authority_manifest",
    content_sha256="705935c9b06b8f592e66e5e71e4541d910b585be6e9a30e46b99fe97b7591d4f",
    path="results/phase4/gate3/gate3_authority_manifest/sha256/705935c9b06b8f592e66e5e71e4541d910b585be6e9a30e46b99fe97b7591d4f/manifest.json",
    sha256="646a7c004c13db3e5f9561d46897a15c27e7f305303559d04d2dc8828ee7f049",
)
SOURCE_FILES = tuple(sorted(
    "src/investment_tracker/quant/phase4/gate3_execution/" + name
    for name in (
        "__init__.py", "baselines.py", "regimes.py", "campaign.py",
        "artifacts.py", "methodology.py", "cli.py",
    )
))


class ExecutionMethodologyManifest(FrozenGate3Model):
    schema_version: Literal["PHASE4-GATE3-EXECUTION-METHODOLOGY-v1"] = "PHASE4-GATE3-EXECUTION-METHODOLOGY-v1"
    status: Literal["GATE3_EXECUTION_METHODOLOGY_SEALED"] = "GATE3_EXECUTION_METHODOLOGY_SEALED"
    spec: ArtifactIdentity
    baseline_method: ArtifactIdentity
    regime_method: ArtifactIdentity
    gate1_manifest: ArtifactIdentity
    gate2_manifest: ArtifactIdentity
    gate3_authority_manifest: ArtifactIdentity
    candidate_population_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_count: Literal[180] = 180
    train_identity: DataPartitionIdentity
    validation_identity: DataPartitionIdentity
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_bundle: SourceBundleIdentity
    safety: SafetyState = SafetyState()


class MethodologyReferenceValidation(FrozenGate3Model):
    gate1: Literal["VALID"] = "VALID"
    gate2: Literal["VALID"] = "VALID"
    gate3_authorities: Literal["VALID"] = "VALID"
    baseline_methodology: Literal["BOUND"] = "BOUND"
    regime_attribution_methodology: Literal["BOUND"] = "BOUND"
    candidate_population: Literal[180] = 180
    source_bundle: Literal["DECLARED"] = "DECLARED"
    execution_methodology: Literal["DECLARED"] = "DECLARED"
    gate3: Literal["STRUCTURALLY_BOUND"] = "STRUCTURALLY_BOUND"
    manifest: ArtifactIdentity
    safety: SafetyState = SafetyState()


class MethodologyPreflight(FrozenGate3Model):
    gate1: Literal["VALID"] = "VALID"
    gate2: Literal["VALID"] = "VALID"
    gate3_authorities: Literal["VALID"] = "VALID"
    baseline_methodology: Literal["BOUND"] = "BOUND"
    regime_attribution_methodology: Literal["BOUND"] = "BOUND"
    candidate_population: Literal[180] = 180
    source_bundle: Literal["BOUND"] = "BOUND"
    execution_methodology: Literal["BOUND"] = "BOUND"
    gate3: Literal["GATE3_CAMPAIGN_READY_TO_EXECUTE"] = "GATE3_CAMPAIGN_READY_TO_EXECUTE"
    manifest: ArtifactIdentity
    safety: SafetyState = SafetyState()


def spec_identity(repository_root: Path) -> ArtifactIdentity:
    root = resolve_repository_root(repository_root, code="SPEC_IDENTITY_MISMATCH")
    try:
        path = contained_path(root, tuple(SPEC_PATH.split("/")), code="SPEC_IDENTITY_MISMATCH")
        content = sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("SPEC_IDENTITY_MISMATCH: exact specification missing") from exc
    if content != SPEC_CONTENT_SHA256:
        raise ValueError("SPEC_IDENTITY_MISMATCH: exact specification bytes changed")
    return ArtifactIdentity(
        kind="phase4_gate3_execution_spec", content_sha256=content, path=SPEC_PATH,
        sha256=artifact_envelope_identity(content_sha256=content, kind="phase4_gate3_execution_spec", path=SPEC_PATH),
    )


def semantic_method_records(repository_root: Path) -> tuple[dict[str, object], dict[str, object]]:
    """Freeze semantic methods from sealed controls, never from performance."""

    authority = load_gate2_authority(repository_root)
    baseline = {
        "schema_version": "PHASE4-GATE3-BASELINE-SLEEVE-METHOD-v1",
        "kind": "baseline_sleeve_method",
        "baseline_definitions_content_sha256": sha256(authority.baseline_definitions_payload).hexdigest(),
        "baselines": [
            {
                "baseline_id": item.baseline_id,
                "family": item.family,
                "parameters": item.parameters,
                "provenance_class": item.provenance_class,
                "implementation_bundle_sha256": item.implementation_bundle_sha256,
                "generator_revision": item.generator_revision,
                "generator_content_sha256": item.generator_content_sha256,
                "parameter_tuple_sha256": canonical_sha256({"family": item.family, "parameters": item.parameters}),
                "rule_set_sha256": canonical_sha256({
                    "family": item.family,
                    "generator_content_sha256": item.generator_content_sha256,
                    "implementation_bundle_sha256": item.implementation_bundle_sha256,
                }),
                "eligible_for_selection": False,
            }
            for item in authority.baselines.baselines
        ],
        "symbols": ["SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP"],
        "sleeves_per_baseline": 8,
        "initial_cash_per_sleeve": 12500.0,
        "aggregate_initial_cash": 100000.0,
        "sleeve_state_isolation": True,
        "cross_sleeve_transfers": False,
        "aggregate_equity_rule": "SUM_INDEPENDENT_CLOSE_EQUITIES_AFTER_REPLAY",
        "signal_input": "CAUSAL_QFQ_CLOSE_WITH_STRICTLY_EARLIER_TRAIN_INDICATOR_WARMUP",
        "validation_reset": "EACH_SLEEVE_CASH_12500_ZERO_UNITS_PENDING_AND_PNL",
        "target_change_detector": "np.isclose(atol=1e-12,rtol=0)",
        "execution_timing": "NEXT_ELIGIBLE_VALIDATION_SESSION_OPEN",
        "execution_series": "QFQ_NORMALIZED",
        "friction_bps": 3,
        "long_only": True,
        "leverage": False,
        "decision_grade": False,
        "eligible_for_selection": False,
        "output_identity_fields": [
            "baseline_definition_sha256", "parameter_tuple_sha256", "rule_set_sha256",
            "implementation_bundle_sha256", "replay_sha256", "sleeve_sha256",
            "aggregate_equity_sha256", "aggregate_returns_sha256",
        ],
    }
    regime = {
        "schema_version": "PHASE4-GATE3-RETURN-ENDING-REGIME-METHOD-v1",
        "kind": "regime_return_method",
        "regime_authority_content_sha256": "9d6e1d81c1e5fdac2fbf50d6e2e1f933ea2bb1d20d6f6e277574704028449454",
        "regime_definition_sha256": FROZEN_REGIME_DEFINITION_SHA256,
        "validation_session_count": 1008,
        "actual_return_count": 1007,
        "first_session_labelled": True,
        "first_session_return": None,
        "return_rule": "CONTINUOUS_CLOSE_EQUITY_PCT_CHANGE_NO_RESET_BOUNDARY_RETURN",
        "attribution_rule": "EACH_ACTUAL_RETURN_TO_ITS_ENDING_SESSION_FROZEN_REGIME",
        "partition_rule": "THREE_CHRONOLOGICAL_CONDITIONAL_VECTORS_PARTITION_ALL_1007_RETURNS",
        "regime_labels_affect_execution": False,
        "conditional_metrics": [
            "return_observation_count", "positive_return_count",
            "positive_return_percentage", "arithmetic_mean_session_return",
            "conditional_compounded_return",
        ],
        "empty_subset_status": "UNKNOWN/NO_RETURN_OBSERVATIONS",
        "noncontiguous_path_metrics": "OMITTED",
        "max_drawdown": "UNKNOWN",
        "calmar": "UNKNOWN",
        "dsr": "UNKNOWN/NOT_IMPLEMENTED",
        "pbo": "UNKNOWN/NOT_IMPLEMENTED",
    }
    return baseline, regime


def _record_identity(store: MethodologyEvidenceStore, kind: str, record: object) -> ArtifactIdentity:
    return store._identity(kind, sha256(canonical_json_bytes(record)).hexdigest())


def _source_bundle(root: Path, revision: str) -> SourceBundleIdentity:
    _validate_source_revision(root, revision)
    for relative in SOURCE_FILES:
        contained_path(root, tuple(relative.split("/")), code="SOURCE_BUNDLE_MISMATCH")
    return source_bundle_identity(root, revision, SOURCE_FILES)


def validate_execution_methodology(
    repository_root: Path, manifest: ExecutionMethodologyManifest
) -> MethodologyReferenceValidation:
    """Validate pinned semantics; the integrated preflight also verifies bytes/Git."""

    root = resolve_repository_root(repository_root, code="METHODOLOGY_DEPENDENCY_MISMATCH")
    try:
        typed = ExecutionMethodologyManifest.model_validate(manifest.model_dump(mode="json"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("METHODOLOGY_DEPENDENCY_MISMATCH: malformed manifest") from exc
    store = MethodologyEvidenceStore(root)
    baseline, regime = semantic_method_records(root)
    if (
        typed.spec != spec_identity(root)
        or typed.baseline_method != _record_identity(store, "baseline_sleeve_method", baseline)
        or typed.regime_method != _record_identity(store, "regime_return_method", regime)
        or typed.gate1_manifest != GATE1_MANIFEST_IDENTITY
        or typed.gate2_manifest != GATE2_MANIFEST_IDENTITY
        or typed.gate3_authority_manifest != CORRECTED_GATE3_MANIFEST
        or typed.candidate_population_sha256 != POPULATION_SHA256
        or typed.train_identity != TRAIN_IDENTITY
        or typed.validation_identity != VALIDATION_IDENTITY
        or typed.safety != SafetyState()
        or typed.source_bundle.producing_revision != typed.source_revision
        or tuple(item.path for item in typed.source_bundle.entries) != SOURCE_FILES
    ):
        raise ValueError("METHODOLOGY_DEPENDENCY_MISMATCH: frozen identity changed")
    authority_check = preflight_gate3(root, CORRECTED_GATE3_MANIFEST.content_sha256)
    if authority_check.gate3 != "READY" or authority_check.candidate_population != 180:
        raise ValueError("METHODOLOGY_DEPENDENCY_MISMATCH: prerequisite authorities invalid")
    manifest_identity = _record_identity(store, "gate3_execution_methodology_manifest", typed.model_dump(mode="json"))
    return MethodologyReferenceValidation(manifest=manifest_identity)


def seal_execution_methodology(repository_root: Path, source_revision: str) -> ArtifactIdentity:
    root = resolve_repository_root(repository_root, code="METHODOLOGY_DEPENDENCY_MISMATCH")
    source = _source_bundle(root, source_revision)
    store = MethodologyEvidenceStore(root)
    baseline, regime = semantic_method_records(root)
    manifest = ExecutionMethodologyManifest(
        spec=spec_identity(root),
        baseline_method=_record_identity(store, "baseline_sleeve_method", baseline),
        regime_method=_record_identity(store, "regime_return_method", regime),
        gate1_manifest=GATE1_MANIFEST_IDENTITY,
        gate2_manifest=GATE2_MANIFEST_IDENTITY,
        gate3_authority_manifest=CORRECTED_GATE3_MANIFEST,
        candidate_population_sha256=POPULATION_SHA256,
        train_identity=TRAIN_IDENTITY,
        validation_identity=VALIDATION_IDENTITY,
        source_revision=source_revision,
        source_bundle=source,
    )
    validate_execution_methodology(root, manifest)
    written_baseline = store.write_json("baseline_sleeve_method", baseline)
    written_regime = store.write_json("regime_return_method", regime)
    if written_baseline != manifest.baseline_method or written_regime != manifest.regime_method:
        raise ValueError("METHODOLOGY_DEPENDENCY_MISMATCH: semantic record write mismatch")
    identity = store.write_json(
        "gate3_execution_methodology_manifest", manifest.model_dump(mode="json"), final=True
    )
    if identity != _record_identity(store, "gate3_execution_methodology_manifest", manifest.model_dump(mode="json")):
        raise ValueError("METHODOLOGY_DEPENDENCY_MISMATCH: final manifest identity mismatch")
    return identity


def preflight_execution_methodology(
    repository_root: Path, manifest_content_sha256: str
) -> MethodologyPreflight:
    if re.fullmatch(r"[0-9a-f]{64}", manifest_content_sha256) is None:
        raise ValueError("METHODOLOGY_MANIFEST_MISSING: explicit canonical SHA-256 required")
    root = resolve_repository_root(repository_root, code="METHODOLOGY_MANIFEST_MISSING")
    store = MethodologyEvidenceStore(root)
    identity = store._identity("gate3_execution_methodology_manifest", manifest_content_sha256)
    try:
        parsed = json.loads(store.verify(identity))
        manifest = ExecutionMethodologyManifest.model_validate(parsed)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise ValueError("METHODOLOGY_MANIFEST_MISSING: exact canonical manifest unavailable") from exc
    result = validate_execution_methodology(root, manifest)
    if result.manifest != identity:
        raise ValueError("METHODOLOGY_DEPENDENCY_MISMATCH: manifest identity altered")
    baseline, regime = semantic_method_records(root)
    if (
        store.verify(manifest.baseline_method) != canonical_json_bytes(baseline)
        or store.verify(manifest.regime_method) != canonical_json_bytes(regime)
        or _source_bundle(root, manifest.source_revision) != manifest.source_bundle
    ):
        raise ValueError("METHODOLOGY_DEPENDENCY_MISMATCH: method or source bytes changed")
    return MethodologyPreflight(manifest=identity)
