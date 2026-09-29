from __future__ import annotations

import pytest

from investment_tracker.quant.phase4.finalization.models import (
    FinalizationSafetyState,
    Phase4Decision,
)


def test_finalization_safety_state_is_fail_closed() -> None:
    safety = FinalizationSafetyState()
    assert safety.candidate_executed is False
    assert safety.candidate_rerun is False
    assert safety.strategy_search_executed is False
    assert safety.candidate_parameters_changed is False
    assert safety.survivor_policy_changed is False
    assert safety.final_holdout_accessed is False
    assert safety.protected_symbols_accessed == ()
    assert safety.provider_calls == 0
    assert safety.downloads == 0
    assert safety.live_trading_capability is False
    assert safety.phase5_started is False


def test_no_survivor_decision_forbids_selected_fields(identity_factory) -> None:
    identity = identity_factory("phase4_finalization_audit", "results/audit.json")
    policy = identity_factory("survivor_policy", "results/survivor.json")
    durability = identity_factory("durability_policy", "results/durability.json")
    decision = Phase4Decision(
        status="NO_CREDIBLE_STRATEGY_FOUND",
        audit_artifact=identity,
        campaign_result_set=identity_factory("phase4_gate3_campaign_result_set", "results/result-set.json"),
        survivor_policy=policy,
        durability_policy=durability,
    )
    assert decision.selected_candidate_id is None

    with pytest.raises(ValueError):
        Phase4Decision(
            status="NO_CREDIBLE_STRATEGY_FOUND",
            audit_artifact=identity,
            campaign_result_set=identity_factory("phase4_gate3_campaign_result_set", "results/result-set.json"),
            survivor_policy=policy,
            durability_policy=durability,
            selected_candidate_id="phase4-" + "1" * 64,
            selected_result_artifact=identity_factory("phase4_gate3_candidate_result", "results/result.json"),
            selected_population_position=1,
            selected_family_id="phase4-family-" + "2" * 64,
            selected_hypothesis_id="phase4-hypothesis-" + "3" * 64,
            selected_rule_set_sha256="4" * 64,
            selected_parameter_tuple_sha256="5" * 64,
            selected_family_definition_sha256="6" * 64,
        )
