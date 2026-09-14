from __future__ import annotations

from importlib import import_module
import inspect
from pathlib import Path

import pytest

from investment_tracker.quant.phase4.engine.models import Gate2SealError

try:
    _budget_module = import_module("investment_tracker.quant.phase4.engine.budget")
    from investment_tracker.quant.phase4.engine.budget import BudgetState

    _BUDGET_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as exc:
    _budget_module = None
    BudgetState = None
    _BUDGET_IMPORT_ERROR = exc


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def require_budget_types(request: pytest.FixtureRequest) -> None:
    if (
        request.node.name != "test_budget_types_are_available"
        and _BUDGET_IMPORT_ERROR is not None
    ):
        pytest.skip("budget types are not implemented yet")


@pytest.fixture(scope="module")
def authority():
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )

    return load_gate2_authority(REPOSITORY_ROOT)


@pytest.fixture(scope="module")
def family_sizes(authority):
    return [len(family.candidates) for family in authority.grids.families]


def test_budget_types_are_available() -> None:
    assert _BUDGET_IMPORT_ERROR is None
    assert inspect.isclass(BudgetState)


def test_start_state_is_lineage_only_and_zero_consumed(authority) -> None:
    state = BudgetState.from_authority(authority)

    assert state.historical_phase2_trials == 136
    assert state.historical_trials_are_lineage_only is True
    assert state.phase4_new_trials_consumed == 0
    assert state.phase4_new_trials_remaining == 3000
    assert state.first_phase4_budget_position == 1
    assert state.budget_positions[0] == 1
    assert state.candidate_ids == tuple(
        c.candidate_id for c in authority.grids.candidates
    )
    assert len(state.candidate_ids) == 180


def test_candidate_position_one_consumes_ordinal_one(authority) -> None:
    state = BudgetState.from_authority(authority)
    first_trial = state.trial_ids[0]

    state = state.consume_current(first_trial)

    assert state.consumption_ordinals[0] == 1
    assert state.phase4_new_trials_consumed == 1
    assert state.phase4_new_trials_remaining == 2999
    assert state.row_states[0] == "CONSUMED"
    # not ordinal 137 (historical lineage must not shift the ordinal)


def test_duplicate_representation_does_not_reconsume(authority) -> None:
    state = BudgetState.from_authority(authority)
    first_trial = state.trial_ids[0]
    state = state.consume_current(first_trial)
    repeated = state.consume_current(first_trial)

    assert repeated is not state or repeated.phase4_new_trials_consumed == 1
    assert repeated.phase4_new_trials_consumed == 1
    assert repeated.consumption_ordinals[0] == 1
    assert repeated.phase4_new_trials_remaining == 2999


def test_only_current_cursor_trial_can_start(authority) -> None:
    state = BudgetState.from_authority(authority)
    # the second candidate's trial may not be consumed before the first
    with pytest.raises(Gate2SealError) as exc_info:
        state.consume_current(state.trial_ids[1])
    assert exc_info.value.code == "BUDGET_ACCOUNTING_INVALID"


def test_baseline_or_phase2_trial_cannot_enter(authority) -> None:
    state = BudgetState.from_authority(authority)
    with pytest.raises(Gate2SealError) as exc_info:
        state.consume_current("baseline-equal-weight-buy-and-hold")
    assert exc_info.value.code == "BUDGET_ACCOUNTING_INVALID"


def test_exactly_50_consecutive_oos_failures_stop_family(authority) -> None:
    state = BudgetState.from_authority(authority)
    family0_size = len(authority.grids.families[0].candidates)
    assert family0_size == 54

    for index in range(50):
        state = state.consume_current(state.trial_ids[index])
        state = state.record_candidate_outcome(0.0)  # nonpositive

    assert state.last_family_reason == "PERSISTENT_OOS_FAILURE"
    # positions 51-54 (indices 50..53) are skipped without consumption
    assert all(
        state.row_states[index] == "SKIPPED_FAMILY_STOP"
        for index in range(50, 54)
    )
    assert all(
        state.consumption_ordinals[index] is None for index in range(50, 54)
    )
    assert state.phase4_new_trials_consumed == 50
    # cursor advanced to the first row of the next family
    assert state.traversal_cursor == 54
    # position 55 (index 54) consumes ordinal 51
    state = state.consume_current(state.trial_ids[54])
    assert state.consumption_ordinals[54] == 51
    assert state.phase4_new_trials_consumed == 51


def test_positive_benchmark_excess_resets_streak(authority) -> None:
    state = BudgetState.from_authority(authority)
    for index in range(49):
        state = state.consume_current(state.trial_ids[index])
        state = state.record_candidate_outcome(-0.01)
    assert state.oos_streak == 49
    state = state.consume_current(state.trial_ids[49])
    state = state.record_candidate_outcome(0.02)  # positive resets
    assert state.oos_streak == 0
    assert state.last_family_reason is None
    # a subsequent nonpositive starts a fresh streak
    state = state.consume_current(state.trial_ids[50])
    state = state.record_candidate_outcome(-0.01)
    assert state.oos_streak == 1


def test_unavailable_outcome_increments_streak(authority) -> None:
    state = BudgetState.from_authority(authority)
    state = state.consume_current(state.trial_ids[0])
    state = state.record_candidate_outcome(None)  # unavailable benchmark-excess
    assert state.oos_streak == 1


def test_isolated_robustness_failure_does_not_increment(authority) -> None:
    # Only the benchmark-excess outcome feeds the streak. A candidate with a
    # positive benchmark-excess resets the streak even when all other
    # robustness statistics would be unavailable/failing.
    state = BudgetState.from_authority(authority)
    for index in range(3):
        state = state.consume_current(state.trial_ids[index])
        state = state.record_candidate_outcome(0.01)  # positive every time
    assert state.oos_streak == 0
    assert state.phase4_new_trials_consumed == 3
    # there is no robustness-failure input to this transition
    assert not hasattr(state, "record_robustness_failure")


def test_exhausted_grid_after_all_rows_attempted(authority) -> None:
    state = BudgetState.from_authority(authority)
    family0_size = len(authority.grids.families[0].candidates)
    for index in range(family0_size):
        state = state.consume_current(state.trial_ids[index])
        state = state.record_candidate_outcome(0.05)  # positive, never stops
    assert state.last_family_reason == "EXHAUSTED_GRID"
    assert state.traversal_cursor == family0_size
    assert state.phase4_new_trials_consumed == family0_size
    # no rows were skipped on a clean exhaustion
    assert not any(
        row.startswith("SKIPPED") for row in state.row_states[:family0_size]
    )


def test_per_family_and_aggregate_budgets_are_unreachable(authority, family_sizes) -> None:
    # 180 sealed candidates from a zero baseline against a 3000 budget:
    # consuming the entire population leaves 2820 trials remaining, so the
    # aggregate limit can never be reached, and no single family can exceed
    # its own sealed size.
    state = BudgetState.from_authority(authority)
    for index in range(len(state.trial_ids)):
        state = state.consume_current(state.trial_ids[index])
        state = state.record_candidate_outcome(0.05)
    assert state.phase4_new_trials_consumed == 180
    assert state.phase4_new_trials_remaining == 2820
    assert state.campaign_status == "COMPLETE"
    assert state.last_family_reason == "EXHAUSTED_GRID"
    assert not state.campaign_terminated
    # no skipped rows exist for a fully attempted sealed population
    assert "SKIPPED" not in " ".join(state.row_states)


def test_campaign_system_error_keeps_consumed_and_terminates(authority) -> None:
    state = BudgetState.from_authority(authority)
    state = state.consume_current(state.trial_ids[0])
    failed = state.fail_campaign()

    assert failed.campaign_status == "CAMPAIGN_EXECUTION_FAILED"
    assert failed.campaign_terminated
    # the already-started candidate remains consumed with its ordinal
    assert failed.consumption_ordinals[0] == 1
    assert failed.phase4_new_trials_consumed == 1
    # no research stop reason is created
    assert failed.last_family_reason is None


def test_record_requires_a_consumed_current_row(authority) -> None:
    state = BudgetState.from_authority(authority)
    with pytest.raises(Gate2SealError) as exc_info:
        state.record_candidate_outcome(0.05)
    assert exc_info.value.code == "BUDGET_ACCOUNTING_INVALID"
