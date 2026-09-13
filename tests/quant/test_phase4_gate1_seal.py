from __future__ import annotations

import json
from pathlib import Path

import pytest

from investment_tracker.quant.phase4.preregistration.baselines import build_verified_baselines
from investment_tracker.quant.phase4.preregistration.campaign_definition import RETRIEVED_AT
from investment_tracker.quant.phase4.preregistration.seal import (
    GATE1_FAILURE_CODES,
    Gate1SealError,
    RESEARCH_CUTOFF,
    seal_preverified_gate1,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def verified_baselines():
    return build_verified_baselines(REPOSITORY_ROOT)


def test_preverified_seal_links_every_frozen_authority_and_writes_manifest_last(tmp_path, verified_baselines) -> None:
    events: list[str] = []
    result = seal_preverified_gate1(
        repository_root=tmp_path,
        verified_baselines=verified_baselines,
        producing_revision="a" * 40,
        write_observer=events.append,
    )
    assert result.manifest.status == "PHASE4_PREREGISTRATION_SEALED"
    assert events[-1] == "phase4_preregistration_manifest"
    assert result.manifest.source_count == 9
    assert result.manifest.admitted_hypothesis_count == 4
    assert result.manifest.rejected_hypothesis_count == 1
    assert result.manifest.family_count == 4
    assert result.manifest.aggregate_candidate_count == 180
    assert result.manifest.baseline_provenance_class_counts == {
        "EXECUTED_PHASE2_BASELINE": 2,
        "SOURCE_DEFINED_PHASE2_GRID_BASELINE": 2,
    }
    assert result.manifest.baseline_provenance_status == "VERIFIED"
    assert result.manifest.readiness_manifest == verified_baselines.baseline_set.baselines[0].readiness_manifest
    assert result.manifest.trial_authority == verified_baselines.baseline_set.baselines[0].trial_authority
    assert result.manifest.durability_policy.kind == "durability_policy"
    assert result.manifest.fixed_deployment_objective == "ONE_FIXED_LONG_ONLY_STRATEGY_NO_PERIODIC_RETUNING"
    assert result.manifest.qfq_execution_methodology == "QFQ_NORMALIZED"
    assert result.manifest.decision_grade is False
    assert result.manifest.dsr_status == result.manifest.pbo_status == "UNKNOWN"
    assert result.manifest.dsr_reason == result.manifest.pbo_reason == "NOT_IMPLEMENTED"
    assert result.manifest.max_drawdown is result.manifest.calmar is None
    assert result.manifest.dsr is result.manifest.pbo is None
    assert result.manifest.validation_data_accessed is False
    assert result.manifest.validation_metrics_accessed is False
    assert result.manifest.final_holdout_accessed is False
    assert result.manifest.protected_symbols_accessed == ()
    assert result.manifest.provider_calls == 0
    assert result.manifest.strategy_search_executed is False
    assert result.manifest.live_trading_capability is False
    assert result.manifest_identity.path.endswith("/manifest.json")
    raw = (tmp_path / result.manifest_identity.path).read_bytes()
    assert json.loads(raw)["status"] == "PHASE4_PREREGISTRATION_SEALED"
    assert RETRIEVED_AT <= RESEARCH_CUTOFF


def test_journals_notes_and_population_are_bound(tmp_path, verified_baselines) -> None:
    result = seal_preverified_gate1(tmp_path, verified_baselines, "b" * 40)
    assert result.manifest.source_journal.record_count == 9
    assert result.manifest.hypothesis_journal.record_count == 5
    assert (tmp_path / result.manifest.research_notes_path).read_bytes()
    assert len(result.manifest.family_rule_set_identities) == 4
    assert result.manifest.candidate_parameter_population_sha256
    assert result.manifest.phase4_initial_consumption == 0
    assert result.manifest.historical_phase2_trials == 136
    assert result.manifest.first_phase4_budget_position == 1


@pytest.mark.parametrize(
    "failure_point",
    [
        "baseline_definitions", "strategy_family_definitions", "deterministic_grids",
        "family_budget_policy", "durability_policy", "survivor_policy",
        "information_access_policy", "research_report",
    ],
)
def test_failure_before_final_commit_cannot_coexist_with_a_new_seal(tmp_path, verified_baselines, failure_point) -> None:
    with pytest.raises(Gate1SealError, match=failure_point):
        seal_preverified_gate1(
            tmp_path, verified_baselines, "c" * 40,
            fail_after_kind=failure_point,
        )
    assert not list((tmp_path / "results/phase4/gate1/phase4_preregistration_manifest").rglob("manifest.json"))


def test_manifest_binds_report_and_every_policy_identity(tmp_path, verified_baselines) -> None:
    result = seal_preverified_gate1(tmp_path, verified_baselines, "d" * 40)
    identities = result.manifest.model_dump(mode="json")
    for name in (
        "baseline_definitions", "strategy_family_definitions", "deterministic_grids",
        "family_budget_policy", "durability_policy", "survivor_policy",
        "information_access_policy", "research_report",
    ):
        assert identities[name]["content_sha256"]
        assert identities[name]["sha256"]


def test_fail_closed_code_vocabulary_is_exact_and_closed() -> None:
    assert GATE1_FAILURE_CODES == (
        "READINESS_MANIFEST_MISMATCH", "FROZEN_SPLIT_MISMATCH",
        "BASELINE_PROVENANCE_UNRESOLVED", "SOURCE_CHAIN_INVALID",
        "SOURCE_EVIDENCE_INSUFFICIENT", "HYPOTHESIS_CHAIN_INVALID",
        "HYPOTHESIS_SOURCE_MISMATCH", "FAMILY_DEFINITION_MISMATCH",
        "GRID_INVALID", "FAMILY_BUDGET_EXCEEDED", "AGGREGATE_BUDGET_EXCEEDED",
        "DURABILITY_POLICY_INVALID", "SURVIVOR_POLICY_INVALID",
        "GATE1_INFORMATION_BOUNDARY_VIOLATION", "HISTORICAL_ARTIFACT_MUTATION",
        "IMMUTABLE_ARTIFACT_COLLISION", "SEAL_PUBLICATION_FAILED",
    )
    with pytest.raises(ValueError, match="unknown Gate 1 failure code"):
        Gate1SealError("bad", "NOT_A_GATE1_CODE")
