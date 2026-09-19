from __future__ import annotations

from pathlib import Path

import pytest

from investment_tracker.quant.phase4.preregistration.baselines import (
    EXECUTED_PHASE2_BASELINE,
    SOURCE_DEFINED_PHASE2_GRID_BASELINE,
    BaselineDefinitionSet,
    build_verified_baselines,
)
from investment_tracker.quant.phase4.preregistration.provenance import (
    BASELINE_GENERATOR_REVISION,
    GENERATOR_GIT_OBJECT,
    PHASE2_TRIAL_AUTHORITY_IDENTITY,
    READINESS_MANIFEST_IDENTITY,
    expected_phase2_candidate_id,
    implementation_bundle_sha256,
    verify_trial_authority,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


EXPECTED_CANDIDATES = {
    "trend": "trend-c7473b1efeb67913",
    "momentum": "momentum-beed7614cb8af377",
    "trend_momentum": "trend_momentum-83046debb18906e9",
    "risk_managed_trend": "risk_managed_trend-797646e3271d03bb",
}


def test_pinned_readiness_and_trial_authority_identities_are_exact() -> None:
    assert READINESS_MANIFEST_IDENTITY.model_dump(mode="json") == {
        "kind": "phase4_readiness_manifest",
        "content_sha256": "4305845b627ed2d369f3e16b26eb0e9ec724c13ea50904fcf5fd4113f264a254",
        "path": "results/phase4/readiness/phase4_readiness_manifest/sha256/4305845b627ed2d369f3e16b26eb0e9ec724c13ea50904fcf5fd4113f264a254/manifest.json",
        "sha256": "25cea5b7cf490a4010244bd03968d342516bb27854b9488dbc9f9cdc2d375471",
    }
    assert PHASE2_TRIAL_AUTHORITY_IDENTITY.model_dump(mode="json") == {
        "kind": "trial_authority",
        "content_sha256": "fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994",
        "path": "results/phase4/readiness/trial_authority/sha256/fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994/authority.json",
        "sha256": "2ab77e480a61c57f1c29395d4e93c2d9302533ab2f67ce364037965d1e1eb3f3",
    }
    assert BASELINE_GENERATOR_REVISION == "c33fb0757f0ea8147749130fed90d278aed4fafe"
    assert GENERATOR_GIT_OBJECT.path == (
        "src/investment_tracker/quant/optimizer/candidate_generator.py"
    )
    assert GENERATOR_GIT_OBJECT.blob == "39ae351c5b83d3f3477ed61f7f00a413fc1cb6d9"
    assert GENERATOR_GIT_OBJECT.content_sha256 == (
        "4db924185136c9ed702196407c62af37d9bdcb10bbbd486dc6984e33ff2e0cf0"
    )


def test_trial_authority_projection_has_exact_136_identity_rows_only() -> None:
    authority, access = verify_trial_authority(REPOSITORY_ROOT)

    assert authority.schema_version == "PHASE4-TRIAL-AUTHORITY-EVIDENCE-v1"
    assert authority.authority_schema_version == "PHASE4-TRIAL-AUTHORITY-v1"
    assert authority.historical_phase2_trial_count == 136
    assert len(authority.trials) == len({row.candidate_id for row in authority.trials}) == 136
    assert tuple(row.candidate_id for row in authority.trials) == tuple(
        sorted(row.candidate_id for row in authority.trials)
    )
    membership = {row.candidate_id: row for row in authority.trials}
    assert EXPECTED_CANDIDATES["trend"] in membership
    assert EXPECTED_CANDIDATES["momentum"] in membership
    assert EXPECTED_CANDIDATES["trend_momentum"] not in membership
    assert EXPECTED_CANDIDATES["risk_managed_trend"] not in membership
    assert not hasattr(authority.trials[0], "metrics")
    assert not hasattr(authority.trials[0], "validation_metrics")
    assert access.safety.strategy_search_executed is False
    assert access.observed_reads == (
        "artifact:trial_authority:"
        f"{PHASE2_TRIAL_AUTHORITY_IDENTITY.path}:"
        f"{PHASE2_TRIAL_AUTHORITY_IDENTITY.content_sha256}",
    )


@pytest.mark.parametrize(
    ("family", "parameters", "candidate_id"),
    (
        (
            "trend",
            {"fast_window": 20, "slow_window": 50, "allocation": 1.0},
            EXPECTED_CANDIDATES["trend"],
        ),
        (
            "momentum",
            {"lookback": 126, "allocation": 1.0},
            EXPECTED_CANDIDATES["momentum"],
        ),
        (
            "trend_momentum",
            {
                "fast_window": 20,
                "slow_window": 50,
                "momentum_lookback": 126,
                "allocation": 1.0,
            },
            EXPECTED_CANDIDATES["trend_momentum"],
        ),
        (
            "risk_managed_trend",
            {
                "trend_window": 150,
                "volatility_window": 40,
                "target_volatility": 0.10,
                "maximum_exposure": 1.0,
            },
            EXPECTED_CANDIDATES["risk_managed_trend"],
        ),
    ),
)
def test_phase2_candidate_ids_reproduce_from_exact_grid_member(
    family: str, parameters: dict[str, int | float], candidate_id: str
) -> None:
    assert expected_phase2_candidate_id(family, parameters) == candidate_id


@pytest.mark.parametrize(
    ("family", "expected"),
    (
        ("trend", "018fc28b74700ed54fb1f8302bcf656edad462cf0f07377aa2d79cc4bc671af4"),
        ("momentum", "1917eaaf07b46e8ed7388441d61ee90756a7788054a4ebb815945cb6b1791960"),
        ("trend_momentum", "828846b6b6386cad33443631cbf2b4136084cee70e4b540b468ad3cc9c77684c"),
        ("risk_managed_trend", "646b46b349bcb608c5ef6a1142fa4588fb9e077dab57437cca729e49afc7504a"),
    ),
)
def test_implementation_bundle_identity_reproduces(
    family: str, expected: str
) -> None:
    assert implementation_bundle_sha256(REPOSITORY_ROOT, family) == expected


def test_baseline_set_truthfully_freezes_two_provenance_classes() -> None:
    verified = build_verified_baselines(REPOSITORY_ROOT)
    baseline_set = verified.baseline_set
    assert isinstance(baseline_set, BaselineDefinitionSet)
    assert baseline_set.baseline_provenance_status == "VERIFIED"
    assert baseline_set.provenance_class_counts == {
        EXECUTED_PHASE2_BASELINE: 2,
        SOURCE_DEFINED_PHASE2_GRID_BASELINE: 2,
    }
    assert len(baseline_set.baselines) == 4
    by_family = {baseline.family: baseline for baseline in baseline_set.baselines}

    for family in ("trend", "momentum"):
        baseline = by_family[family]
        assert baseline.provenance_class == EXECUTED_PHASE2_BASELINE
        assert baseline.authoritative_trial_artifact is not None
        assert baseline.authoritative_trial_artifact.kind == "phase2_experiment"
    for family in ("trend_momentum", "risk_managed_trend"):
        baseline = by_family[family]
        assert baseline.provenance_class == SOURCE_DEFINED_PHASE2_GRID_BASELINE
        assert baseline.authoritative_trial_artifact is None

    for baseline in baseline_set.baselines:
        assert baseline.candidate_id == EXPECTED_CANDIDATES[baseline.family]
        assert baseline.signal_risk_parameter_rationale == (
            "PRE_EXISTING_GRID_MIDPOINT_OR_CENTRAL_WHERE_APPLICABLE"
        )
        assert baseline.exposure_parameter_rationale == (
            "FROZEN_FULL_EXPOSURE_COMPARATOR_NOT_MIDPOINT"
        )
        assert baseline.phase2_numeric_performance_used is False
        assert baseline.phase4_validation_performance_used is False
        assert baseline.phase4_family_slots_consumed == 0
        assert baseline.phase4_candidate_trials_consumed == 0
        assert baseline.grid is None
        assert baseline.eligible_for_selection is False
        assert baseline.validation_driven_selection is False

    assert verified.trial_authority.historical_phase2_trial_count == 136
    assert verified.access_evidence.safety.provider_calls == 0
    assert verified.access_evidence.safety.strategy_search_executed is False
    assert all("metrics" not in read for read in verified.access_evidence.observed_reads)


def test_executed_artifact_paths_are_exact_and_source_defined_claims_are_null() -> None:
    baseline_set = build_verified_baselines(REPOSITORY_ROOT).baseline_set
    by_family = {baseline.family: baseline for baseline in baseline_set.baselines}
    assert by_family["trend"].authoritative_trial_artifact.path == (
        "results/experiments/"
        "trend-c7473b1efeb67913-20260911T193719918435Z-d1014884.json"
    )
    assert by_family["momentum"].authoritative_trial_artifact.path == (
        "results/experiments/"
        "momentum-beed7614cb8af377-20260911T193737197057Z-42f3156e.json"
    )
    assert by_family["trend_momentum"].authoritative_trial_artifact is None
    assert by_family["risk_managed_trend"].authoritative_trial_artifact is None
