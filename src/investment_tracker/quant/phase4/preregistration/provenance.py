from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .access import (
    Gate1AccessEvidence,
    Gate1GitObjectIdentity,
    Gate1ReadCapability,
)
from .canonical import canonical_json_bytes, canonical_sha256, trial_identity
from .models import FrozenGate1Model, Gate1ArtifactIdentity


BASELINE_GENERATOR_REVISION = "c33fb0757f0ea8147749130fed90d278aed4fafe"
PHASE2_CAMPAIGN_ID = "PHASE2-CORRECTED-2010-2022-c33fb075"


class BaselineProvenanceError(RuntimeError):
    """Raised when frozen baseline provenance cannot be reproduced exactly."""


READINESS_MANIFEST_IDENTITY = Gate1ArtifactIdentity(
    kind="phase4_readiness_manifest",
    content_sha256="4305845b627ed2d369f3e16b26eb0e9ec724c13ea50904fcf5fd4113f264a254",
    path=(
        "results/phase4/readiness/phase4_readiness_manifest/sha256/"
        "4305845b627ed2d369f3e16b26eb0e9ec724c13ea50904fcf5fd4113f264a254/"
        "manifest.json"
    ),
    sha256="25cea5b7cf490a4010244bd03968d342516bb27854b9488dbc9f9cdc2d375471",
)

PHASE2_TRIAL_AUTHORITY_IDENTITY = Gate1ArtifactIdentity(
    kind="trial_authority",
    content_sha256="fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994",
    path=(
        "results/phase4/readiness/trial_authority/sha256/"
        "fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994/"
        "authority.json"
    ),
    sha256="2ab77e480a61c57f1c29395d4e93c2d9302533ab2f67ce364037965d1e1eb3f3",
)

GENERATOR_GIT_OBJECT = Gate1GitObjectIdentity(
    revision=BASELINE_GENERATOR_REVISION,
    path="src/investment_tracker/quant/optimizer/candidate_generator.py",
    blob="39ae351c5b83d3f3477ed61f7f00a413fc1cb6d9",
    content_sha256="4db924185136c9ed702196407c62af37d9bdcb10bbbd486dc6984e33ff2e0cf0",
)


def _git_object(path: str, blob: str, content_sha256: str) -> Gate1GitObjectIdentity:
    return Gate1GitObjectIdentity(
        revision=BASELINE_GENERATOR_REVISION,
        path=path,
        blob=blob,
        content_sha256=content_sha256,
    )


STRATEGY_GIT_OBJECTS = {
    "base": _git_object(
        "src/investment_tracker/quant/strategies/base.py",
        "c360c1f03c98655e5208d00b765834bec53d9e12",
        "fa2cab2d588797dfe241022e9d28a6de12e4e1a1ecf21df9e289cebdcd5fad9c",
    ),
    "indicators": _git_object(
        "src/investment_tracker/quant/strategies/indicators.py",
        "3aeafa0216746fb404de3ec7b65d11dadaffab65",
        "fc7e7e78f22e9479846a0b32a45a5bb22a62629ddaf2437b227ce1052773a956",
    ),
    "registry": _git_object(
        "src/investment_tracker/quant/strategies/registry.py",
        "aedba60efbda99c5099a8bca951dc141c808dd67",
        "8f8e76bcb6bb53704274d3bad432691eee3b797d0cdf14de3d55ff260a3286a8",
    ),
    "trend": _git_object(
        "src/investment_tracker/quant/strategies/trend.py",
        "afe465d875b93f2f7fee63fc22d225d9f123e807",
        "ccc04b24913e607760e7533e6bbc9da42fc819d591f6f1ae5b22c5e0eac8a43b",
    ),
    "momentum": _git_object(
        "src/investment_tracker/quant/strategies/momentum.py",
        "6d9b6842eb5fdc53520d931d7cafeb0a1e790b8c",
        "434af7089b45a139b95e0bf0b04ac03b4369ec015b5b94bd65957103851e4949",
    ),
    "trend_momentum": _git_object(
        "src/investment_tracker/quant/strategies/trend_momentum.py",
        "373be3f422b73c01492708103f82171a5517149c",
        "230eb9eca3b080cb6599f53a2626d4cb8d6732fc72a45d769f20ffe4729d0fac",
    ),
    "risk_managed_trend": _git_object(
        "src/investment_tracker/quant/strategies/risk_managed.py",
        "93a9d68bba7457818c7a45a7cd96387bf580b95e",
        "17b96df6af1bfae76897e0c10720f8ff1179f49f1adf9769aa0f8a0b4618be30",
    ),
}

IMPLEMENTATION_BUNDLE_SHA256 = {
    "trend": "018fc28b74700ed54fb1f8302bcf656edad462cf0f07377aa2d79cc4bc671af4",
    "momentum": "1917eaaf07b46e8ed7388441d61ee90756a7788054a4ebb815945cb6b1791960",
    "trend_momentum": "828846b6b6386cad33443631cbf2b4136084cee70e4b540b468ad3cc9c77684c",
    "risk_managed_trend": "646b46b349bcb608c5ef6a1142fa4588fb9e077dab57437cca729e49afc7504a",
}

PHASE2_GRIDS: dict[str, dict[str, tuple[int | float, ...]]] = {
    "trend": {
        "fast_window": (15, 20, 25),
        "slow_window": (40, 50, 60),
        "allocation": (0.25, 0.5, 1.0),
    },
    "momentum": {
        "lookback": (63, 126, 252),
        "allocation": (0.25, 0.5, 1.0),
    },
    "trend_momentum": {
        "fast_window": (15, 20, 25),
        "slow_window": (40, 50, 60),
        "momentum_lookback": (63, 126, 252),
        "allocation": (0.25, 0.5, 1.0),
    },
    "risk_managed_trend": {
        "trend_window": (100, 150, 200),
        "volatility_window": (20, 40, 60),
        "target_volatility": (0.08, 0.10, 0.12),
        "maximum_exposure": (0.25, 0.5, 1.0),
    },
}


class TrialIdentityProjection(FrozenGate1Model):
    candidate_id: str
    trial_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    authoritative_artifact: Gate1ArtifactIdentity


class TrialAuthorityProjection(FrozenGate1Model):
    schema_version: Literal["PHASE4-TRIAL-AUTHORITY-EVIDENCE-v1"]
    authority_schema_version: Literal["PHASE4-TRIAL-AUTHORITY-v1"]
    campaign_id: Literal["PHASE2-CORRECTED-2010-2022-c33fb075"]
    representation_selector_version: Literal["PHASE2-REPRESENTATION-SELECTOR-v1"]
    historical_phase2_trial_count: Literal[136]
    final_authoritative_representation_count: Literal[136]
    trials: tuple[TrialIdentityProjection, ...] = Field(min_length=136, max_length=136)

    @model_validator(mode="after")
    def validate_trial_set(self) -> "TrialAuthorityProjection":
        candidates = tuple(item.candidate_id for item in self.trials)
        trial_ids = tuple(item.trial_id for item in self.trials)
        if candidates != tuple(sorted(candidates)) or len(set(candidates)) != 136:
            raise ValueError("trial authority candidates must be unique and sorted")
        if len(set(trial_ids)) != 136:
            raise ValueError("trial authority trial IDs must be unique")
        for item in self.trials:
            if item.trial_id != trial_identity(self.campaign_id, item.candidate_id):
                raise ValueError("trial identity does not reproduce")
        return self


class ReadinessPrerequisiteProjection(FrozenGate1Model):
    schema_version: Literal["PHASE4-READINESS-MANIFEST-v1"]
    status: Literal["PHASE_4_READY"]
    trial_authority: Gate1ArtifactIdentity
    split_manifest: Gate1ArtifactIdentity
    historical_phase2_trial_count: Literal[136]
    phase4_new_trials_consumed: Literal[0]
    provider_calls: Literal[0]
    strategy_search_executed: Literal[False]
    final_holdout_accessed: Literal[False]
    protected_symbols_accessed: tuple[()] = ()
    live_trading_capability: Literal[False]
    signal_series: Literal["QFQ"]
    execution_series: Literal["QFQ_NORMALIZED"]
    decision_grade: Literal[False]


def _load_json(payload: bytes, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(payload.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineProvenanceError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict) or canonical_json_bytes(parsed) != payload:
        raise BaselineProvenanceError(f"{label} is not canonical JSON")
    return parsed


def _project_trial_authority(payload: bytes) -> TrialAuthorityProjection:
    parsed = _load_json(payload, "trial authority")
    try:
        authority = parsed["authority"]
        assert isinstance(authority, dict)
        raw_trials = authority["trials"]
        assert isinstance(raw_trials, list)
        trials = tuple(
            TrialIdentityProjection(
                candidate_id=row["candidate_id"],
                trial_id=row["trial_id"],
                authoritative_artifact=Gate1ArtifactIdentity.model_validate(
                    row["authoritative_artifact"]
                ),
            )
            for row in raw_trials
        )
        return TrialAuthorityProjection(
            schema_version=parsed["schema_version"],
            authority_schema_version=authority["schema_version"],
            campaign_id=authority["campaign_id"],
            representation_selector_version=authority[
                "representation_selector_version"
            ],
            historical_phase2_trial_count=authority[
                "historical_phase2_trial_count"
            ],
            final_authoritative_representation_count=authority[
                "final_authoritative_representation_count"
            ],
            trials=trials,
        )
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        raise BaselineProvenanceError("trial authority projection is invalid") from exc


def verify_trial_authority(
    repository_root: Path,
) -> tuple[TrialAuthorityProjection, Gate1AccessEvidence]:
    capability = Gate1ReadCapability(
        repository_root, artifacts=(PHASE2_TRIAL_AUTHORITY_IDENTITY,)
    )
    payload = capability.read_admitted_artifact(PHASE2_TRIAL_AUTHORITY_IDENTITY)
    return _project_trial_authority(payload), capability.evidence()


def _project_readiness(payload: bytes) -> ReadinessPrerequisiteProjection:
    parsed = _load_json(payload, "readiness manifest")
    fields = {
        key: parsed[key]
        for key in (
            "schema_version",
            "status",
            "trial_authority",
            "split_manifest",
            "historical_phase2_trial_count",
            "phase4_new_trials_consumed",
            "provider_calls",
            "strategy_search_executed",
            "final_holdout_accessed",
            "protected_symbols_accessed",
            "live_trading_capability",
            "signal_series",
            "execution_series",
            "decision_grade",
        )
    }
    try:
        projection = ReadinessPrerequisiteProjection.model_validate(fields)
    except Exception as exc:
        raise BaselineProvenanceError("readiness prerequisite is invalid") from exc
    if projection.trial_authority != PHASE2_TRIAL_AUTHORITY_IDENTITY:
        raise BaselineProvenanceError("readiness trial-authority link mismatch")
    return projection


def expected_phase2_candidate_id(
    family: str, parameters: dict[str, int | float]
) -> str:
    if family not in PHASE2_GRIDS:
        raise BaselineProvenanceError(f"unknown Phase 2 family: {family}")
    grid = PHASE2_GRIDS[family]
    if set(parameters) != set(grid):
        raise BaselineProvenanceError("parameter tuple does not match grid dimensions")
    if any(parameters[name] not in grid[name] for name in grid):
        raise BaselineProvenanceError("parameter tuple is not a Phase 2 grid member")
    encoded = json.dumps(
        {"family": family, "parameters": parameters},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{family}-{sha256(encoded).hexdigest()[:16]}"


def _family_git_objects(family: str) -> tuple[Gate1GitObjectIdentity, ...]:
    if family not in IMPLEMENTATION_BUNDLE_SHA256:
        raise BaselineProvenanceError(f"unknown baseline family: {family}")
    return tuple(
        sorted(
            (
                STRATEGY_GIT_OBJECTS["base"],
                STRATEGY_GIT_OBJECTS["indicators"],
                STRATEGY_GIT_OBJECTS["registry"],
                STRATEGY_GIT_OBJECTS[family],
            ),
            key=lambda item: item.path,
        )
    )


def _bundle_from_capability(
    capability: Gate1ReadCapability, family: str
) -> str:
    members = {
        identity.path: sha256(
            capability.read_admitted_git_object(identity)
        ).hexdigest()
        for identity in _family_git_objects(family)
    }
    digest = canonical_sha256(members)
    if digest != IMPLEMENTATION_BUNDLE_SHA256[family]:
        raise BaselineProvenanceError("implementation bundle identity mismatch")
    return digest


def implementation_bundle_sha256(repository_root: Path, family: str) -> str:
    objects = _family_git_objects(family)
    capability = Gate1ReadCapability(repository_root, git_objects=objects)
    return _bundle_from_capability(capability, family)


def full_provenance_capability(repository_root: Path) -> Gate1ReadCapability:
    from .baselines import EXECUTED_ARTIFACT_IDENTITIES

    git_objects = tuple(
        sorted(
            {GENERATOR_GIT_OBJECT, *STRATEGY_GIT_OBJECTS.values()},
            key=lambda item: (item.path, item.blob),
        )
    )
    return Gate1ReadCapability(
        repository_root,
        artifacts=(
            READINESS_MANIFEST_IDENTITY,
            PHASE2_TRIAL_AUTHORITY_IDENTITY,
            *EXECUTED_ARTIFACT_IDENTITIES.values(),
        ),
        git_objects=git_objects,
    )


def verify_full_provenance_inputs(
    capability: Gate1ReadCapability,
) -> tuple[
    ReadinessPrerequisiteProjection,
    TrialAuthorityProjection,
    dict[str, str],
]:
    readiness = _project_readiness(
        capability.read_admitted_artifact(READINESS_MANIFEST_IDENTITY)
    )
    authority = _project_trial_authority(
        capability.read_admitted_artifact(PHASE2_TRIAL_AUTHORITY_IDENTITY)
    )
    capability.read_admitted_git_object(GENERATOR_GIT_OBJECT)
    bundles = {
        family: _bundle_from_capability(capability, family)
        for family in sorted(IMPLEMENTATION_BUNDLE_SHA256)
    }
    return readiness, authority, bundles
