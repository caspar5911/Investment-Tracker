from __future__ import annotations

import inspect

import pytest

from investment_tracker.quant.phase4.preregistration.campaign_definition import ADMITTED_HYPOTHESES
from investment_tracker.quant.phase4.preregistration.canonical import (
    candidate_identity,
    candidate_parameter_population_identity,
    parameter_tuple_identity,
    rule_set_identity,
    trial_identity,
)
from investment_tracker.quant.phase4.preregistration.grids import (
    PHASE4_CAMPAIGN_ID,
    BudgetLimitError,
    build_preregistered_grids,
    validate_budget_counts,
)


EXPECTED_COUNTS = {
    "cross_sectional_absolute_momentum_rotation": 54,
    "diversified_time_series_momentum": 36,
    "volatility_managed_relative_momentum": 54,
    "trend_filtered_equal_risk_allocation": 36,
}


def test_one_family_per_hypothesis_with_complete_algorithm_identity() -> None:
    result = build_preregistered_grids(ADMITTED_HYPOTHESES)
    assert len(result.families) == len(ADMITTED_HYPOTHESES) == 4
    assert {row.hypothesis_id for row in result.families} == {
        row.hypothesis_id for row in ADMITTED_HYPOTHESES
    }
    for family in result.families:
        assert family.family_id.startswith("phase4-family-")
        assert family.rule_set_sha256 == rule_set_identity(
            family.family_id, family.model_dump(mode="json")
        )
        assert family.maximum_gross_exposure == 1.0
        assert family.long_only is True
        assert family.leverage_allowed is False
        assert family.rule_set_mode == "FIXED"
        assert family.parameter_tuple_mode == "FIXED"
        assert family.annual_reoptimization is False
        assert family.periodic_reoptimization is False
        assert family.baseline_distinction
        assert family.grid_spec_sha256


def test_exact_counts_and_deterministic_order_are_independent_of_input_order() -> None:
    forward = build_preregistered_grids(ADMITTED_HYPOTHESES)
    reverse = build_preregistered_grids(tuple(reversed(ADMITTED_HYPOTHESES)))
    assert forward == reverse
    assert tuple(row.family_id for row in forward.families) == tuple(
        sorted(row.family_id for row in forward.families)
    )
    assert {row.family_semantic_name: len(row.candidates) for row in forward.families} == EXPECTED_COUNTS
    assert len(forward.candidates) == 180
    assert forward.budget_policy.aggregate_candidate_count == 180


def test_cartesian_rows_use_typed_values_and_rederive_all_identities() -> None:
    result = build_preregistered_grids(ADMITTED_HYPOTHESES)
    assert [row.budget_position for row in result.candidates] == list(range(1, 181))
    assert len({row.candidate_id for row in result.candidates}) == 180
    assert len({row.trial_id for row in result.candidates}) == 180
    by_id = {family.family_id: family for family in result.families}
    for row in result.candidates:
        family = by_id[row.family_id]
        assert row.parameter_tuple_sha256 == parameter_tuple_identity(row.family_id, row.parameters)
        assert row.candidate_id == candidate_identity(
            campaign_id=PHASE4_CAMPAIGN_ID,
            hypothesis_id=family.hypothesis_id,
            family_id=row.family_id,
            parameters=row.parameters,
        )
        assert row.trial_id == trial_identity(PHASE4_CAMPAIGN_ID, row.candidate_id)
        for value in row.parameters.values():
            assert value["type"] in {"int", "float64_hex"}
            if value["type"] == "float64_hex":
                float.fromhex(value["value"])
    assert result.candidate_parameter_population_sha256 == candidate_parameter_population_identity(
        tuple({"candidate_id": row.candidate_id,
               "parameter_tuple_sha256": row.parameter_tuple_sha256}
              for row in result.candidates)
    )


def test_dimensions_and_structural_predicates_are_frozen() -> None:
    result = build_preregistered_grids(ADMITTED_HYPOTHESES)
    by_name = {row.family_semantic_name: row for row in result.families}
    vmrm = by_name["volatility_managed_relative_momentum"]
    assert vmrm.structural_parameters == {"rebalance_sessions": {"type": "int", "value": "21"}}
    assert "rebalance_sessions" not in vmrm.parameter_dimensions
    for family in result.families:
        assert tuple(family.parameter_dimensions) == tuple(sorted(family.parameter_dimensions))
        assert family.neighborhood_rule == "ADJACENT_DECLARED_VALUE_IN_EXACTLY_ONE_DIMENSION"


def test_neighborhoods_are_adjacent_only() -> None:
    result = build_preregistered_grids(ADMITTED_HYPOTHESES)
    family = next(row for row in result.families if row.family_semantic_name == "cross_sectional_absolute_momentum_rotation")
    interior = next(row for row in family.candidates if all(
        row.raw_parameters[name] == value for name, value in {
            "lookback_sessions": 126, "skip_sessions": 21,
            "top_k": 2, "rebalance_sessions": 42,
        }.items()
    ))
    neighbors = {item.parameter_tuple_sha256 for item in family.neighbors(interior.parameter_tuple_sha256)}
    assert len(neighbors) == 7
    for item in family.neighbors(interior.parameter_tuple_sha256):
        changed = sum(item.raw_parameters[key] != interior.raw_parameters[key] for key in interior.raw_parameters)
        assert changed == 1


def test_budget_is_phase4_only_and_duplicates_do_not_inflate() -> None:
    result = build_preregistered_grids(ADMITTED_HYPOTHESES)
    policy = result.budget_policy
    assert policy.historical_phase2_trials == 136
    assert policy.initial_phase4_consumption == 0
    assert policy.baseline_candidate_trials_consumed == 0
    assert policy.first_future_budget_position == 1
    assert validate_budget_counts(4, ["a", "a", "b"], {"f": ["a", "a", "b"]}) == 2


@pytest.mark.parametrize(
    ("families", "aggregate", "per_family", "message"),
    [
        (11, 1, {"f": ["a"]}, "family limit"),
        (1, 501, {"f": [str(i) for i in range(501)]}, "per-family"),
        (10, 3001, {str(i): [f"{i}-{j}" for j in range(301)] for i in range(10)}, "aggregate"),
    ],
)
def test_limits_fail_closed_before_any_append(families, aggregate, per_family, message) -> None:
    candidates = [str(i) for i in range(aggregate)]
    with pytest.raises(BudgetLimitError, match=message):
        validate_budget_counts(families, candidates, per_family)


def test_no_adaptive_generation_api_exists() -> None:
    import investment_tracker.quant.phase4.preregistration.grids as grids
    source = inspect.getsource(grids)
    assert not hasattr(grids, "generate_next_candidate")
    assert "validation_metric" not in source
    assert "optimizer" not in source
