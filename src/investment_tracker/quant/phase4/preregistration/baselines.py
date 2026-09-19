from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .access import Gate1AccessEvidence
from .models import FrozenGate1Model, Gate1ArtifactIdentity
from .provenance import (
    BASELINE_GENERATOR_REVISION,
    GENERATOR_GIT_OBJECT,
    IMPLEMENTATION_BUNDLE_SHA256,
    PHASE2_GRIDS,
    PHASE2_TRIAL_AUTHORITY_IDENTITY,
    READINESS_MANIFEST_IDENTITY,
    TrialAuthorityProjection,
    expected_phase2_candidate_id,
    full_provenance_capability,
    verify_full_provenance_inputs,
)


EXECUTED_PHASE2_BASELINE = "EXECUTED_PHASE2_BASELINE"
SOURCE_DEFINED_PHASE2_GRID_BASELINE = "SOURCE_DEFINED_PHASE2_GRID_BASELINE"
BaselineProvenanceClass = Literal[
    "EXECUTED_PHASE2_BASELINE", "SOURCE_DEFINED_PHASE2_GRID_BASELINE"
]
BaselineFamily = Literal[
    "trend", "momentum", "trend_momentum", "risk_managed_trend"
]

FROZEN_UNIVERSE = ("SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP")
UNIVERSE_DIGEST = "de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76"
DQ_SNAPSHOT_DIGEST = "2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75"
QFQ_METHODOLOGY_IDENTITY = "ffee9bac3fe329b14d5aebb0f6152f00fc0a86b28d9186c254b5c8f6f8a322fb"

EXECUTED_ARTIFACT_IDENTITIES = {
    "trend": Gate1ArtifactIdentity(
        kind="phase2_experiment",
        path=(
            "results/experiments/"
            "trend-c7473b1efeb67913-20260911T193719918435Z-d1014884.json"
        ),
        content_sha256="556bc481d3978cf028edd19dec1fc05d6becb5d6e09e7e0c0f16ed80bc08846c",
        sha256="330dd2c30e977376b844cbf50abfc9858f59a3df0b6ff53246ed5d13423174cb",
    ),
    "momentum": Gate1ArtifactIdentity(
        kind="phase2_experiment",
        path=(
            "results/experiments/"
            "momentum-beed7614cb8af377-20260911T193737197057Z-42f3156e.json"
        ),
        content_sha256="6495b221716f5f85a1b20fa16da79fe5521ee931119b8985aea9cafc30a6a8eb",
        sha256="fb902a7fbb6f0824461c6b005325fcec6717989eb34513c173c37ccc486d9f13",
    ),
}

BASELINE_PARAMETERS: dict[str, dict[str, int | float]] = {
    "trend": {"fast_window": 20, "slow_window": 50, "allocation": 1.0},
    "momentum": {"lookback": 126, "allocation": 1.0},
    "trend_momentum": {
        "fast_window": 20,
        "slow_window": 50,
        "momentum_lookback": 126,
        "allocation": 1.0,
    },
    "risk_managed_trend": {
        "trend_window": 150,
        "volatility_window": 40,
        "target_volatility": 0.10,
        "maximum_exposure": 1.0,
    },
}

BASELINE_IDS = {
    "trend": "baseline-trend-v1",
    "momentum": "baseline-momentum-v1",
    "trend_momentum": "baseline-trend-momentum-v1",
    "risk_managed_trend": "baseline-risk-managed-trend-v1",
}


class BaselineDefinition(FrozenGate1Model):
    schema_version: Literal["PHASE4-BASELINE-DEFINITION-v1"] = (
        "PHASE4-BASELINE-DEFINITION-v1"
    )
    baseline_id: str
    provenance_class: BaselineProvenanceClass
    family: BaselineFamily
    parameters: dict[str, int | float]
    candidate_id: str
    generator_revision: Literal["c33fb0757f0ea8147749130fed90d278aed4fafe"]
    generator_path: Literal[
        "src/investment_tracker/quant/optimizer/candidate_generator.py"
    ]
    generator_blob: Literal["39ae351c5b83d3f3477ed61f7f00a413fc1cb6d9"]
    generator_content_sha256: Literal[
        "4db924185136c9ed702196407c62af37d9bdcb10bbbd486dc6984e33ff2e0cf0"
    ]
    grid_definition: dict[str, tuple[int | float, ...]]
    implementation_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authoritative_trial_artifact: Gate1ArtifactIdentity | None
    readiness_manifest: Gate1ArtifactIdentity
    trial_authority: Gate1ArtifactIdentity
    split_manifest: Gate1ArtifactIdentity
    frozen_universe: tuple[str, ...]
    universe_digest: Literal[
        "de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76"
    ]
    dq_snapshot_digest: Literal[
        "2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75"
    ]
    qfq_methodology_identity: Literal[
        "ffee9bac3fe329b14d5aebb0f6152f00fc0a86b28d9186c254b5c8f6f8a322fb"
    ]
    signal_risk_parameter_rationale: Literal[
        "PRE_EXISTING_GRID_MIDPOINT_OR_CENTRAL_WHERE_APPLICABLE"
    ]
    exposure_parameter_rationale: Literal[
        "FROZEN_FULL_EXPOSURE_COMPARATOR_NOT_MIDPOINT"
    ]
    phase2_numeric_performance_used: Literal[False] = False
    phase4_validation_performance_used: Literal[False] = False
    phase4_family_slots_consumed: Literal[0] = 0
    phase4_candidate_trials_consumed: Literal[0] = 0
    grid: None = None
    eligible_for_selection: Literal[False] = False
    validation_driven_selection: Literal[False] = False

    @model_validator(mode="after")
    def validate_provenance_class(self) -> "BaselineDefinition":
        expected_executed = self.family in EXECUTED_ARTIFACT_IDENTITIES
        if expected_executed != (
            self.provenance_class == EXECUTED_PHASE2_BASELINE
        ):
            raise ValueError("baseline provenance class mismatch")
        expected_artifact = EXECUTED_ARTIFACT_IDENTITIES.get(self.family)
        if self.authoritative_trial_artifact != expected_artifact:
            raise ValueError("baseline trial-artifact claim mismatch")
        if self.candidate_id != expected_phase2_candidate_id(
            self.family, self.parameters
        ):
            raise ValueError("baseline candidate identity mismatch")
        if self.grid_definition != PHASE2_GRIDS[self.family]:
            raise ValueError("baseline grid definition mismatch")
        if self.implementation_bundle_sha256 != IMPLEMENTATION_BUNDLE_SHA256[
            self.family
        ]:
            raise ValueError("baseline implementation identity mismatch")
        return self


class BaselineDefinitionSet(FrozenGate1Model):
    schema_version: Literal["PHASE4-BASELINE-DEFINITION-SET-v1"] = (
        "PHASE4-BASELINE-DEFINITION-SET-v1"
    )
    baseline_provenance_status: Literal["VERIFIED"] = "VERIFIED"
    provenance_class_counts: dict[BaselineProvenanceClass, int]
    baselines: tuple[BaselineDefinition, ...] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def validate_set(self) -> "BaselineDefinitionSet":
        if tuple(item.baseline_id for item in self.baselines) != tuple(
            sorted(item.baseline_id for item in self.baselines)
        ):
            raise ValueError("baselines must be baseline-ID sorted")
        if len({item.family for item in self.baselines}) != 4:
            raise ValueError("baseline families must be unique")
        counts = dict(Counter(item.provenance_class for item in self.baselines))
        expected = {
            EXECUTED_PHASE2_BASELINE: 2,
            SOURCE_DEFINED_PHASE2_GRID_BASELINE: 2,
        }
        if counts != expected or self.provenance_class_counts != expected:
            raise ValueError("baseline provenance class counts must be exactly 2/2")
        return self


class VerifiedBaselines(FrozenGate1Model):
    schema_version: Literal["PHASE4-VERIFIED-BASELINES-v1"] = (
        "PHASE4-VERIFIED-BASELINES-v1"
    )
    baseline_set: BaselineDefinitionSet
    trial_authority: TrialAuthorityProjection
    access_evidence: Gate1AccessEvidence


def build_verified_baselines(repository_root: Path) -> VerifiedBaselines:
    capability = full_provenance_capability(repository_root)
    readiness, authority, bundles = verify_full_provenance_inputs(capability)
    membership = {item.candidate_id: item for item in authority.trials}
    definitions: list[BaselineDefinition] = []
    for family in sorted(BASELINE_PARAMETERS, key=lambda item: BASELINE_IDS[item]):
        parameters = BASELINE_PARAMETERS[family]
        candidate_id = expected_phase2_candidate_id(family, parameters)
        artifact = EXECUTED_ARTIFACT_IDENTITIES.get(family)
        if artifact is not None:
            trial = membership.get(candidate_id)
            if trial is None or trial.authoritative_artifact != artifact:
                raise ValueError("executed baseline is absent from trial authority")
            capability.read_admitted_artifact(artifact)
            provenance_class = EXECUTED_PHASE2_BASELINE
        else:
            if candidate_id in membership:
                raise ValueError("source-defined baseline appears in trial authority")
            provenance_class = SOURCE_DEFINED_PHASE2_GRID_BASELINE
        definitions.append(
            BaselineDefinition(
                baseline_id=BASELINE_IDS[family],
                provenance_class=provenance_class,
                family=family,
                parameters=parameters,
                candidate_id=candidate_id,
                generator_revision=BASELINE_GENERATOR_REVISION,
                generator_path=GENERATOR_GIT_OBJECT.path,
                generator_blob=GENERATOR_GIT_OBJECT.blob,
                generator_content_sha256=GENERATOR_GIT_OBJECT.content_sha256,
                grid_definition=PHASE2_GRIDS[family],
                implementation_bundle_sha256=bundles[family],
                authoritative_trial_artifact=artifact,
                readiness_manifest=READINESS_MANIFEST_IDENTITY,
                trial_authority=PHASE2_TRIAL_AUTHORITY_IDENTITY,
                split_manifest=readiness.split_manifest,
                frozen_universe=FROZEN_UNIVERSE,
                universe_digest=UNIVERSE_DIGEST,
                dq_snapshot_digest=DQ_SNAPSHOT_DIGEST,
                qfq_methodology_identity=QFQ_METHODOLOGY_IDENTITY,
                signal_risk_parameter_rationale=(
                    "PRE_EXISTING_GRID_MIDPOINT_OR_CENTRAL_WHERE_APPLICABLE"
                ),
                exposure_parameter_rationale=(
                    "FROZEN_FULL_EXPOSURE_COMPARATOR_NOT_MIDPOINT"
                ),
            )
        )
    baseline_set = BaselineDefinitionSet(
        provenance_class_counts={
            EXECUTED_PHASE2_BASELINE: 2,
            SOURCE_DEFINED_PHASE2_GRID_BASELINE: 2,
        },
        baselines=tuple(definitions),
    )
    return VerifiedBaselines(
        baseline_set=baseline_set,
        trial_authority=authority,
        access_evidence=capability.evidence(),
    )
