import pytest

from investment_tracker.phase_state import PhaseState, TransitionError, assert_transition


def test_phase_progression_requires_adjacent_state_and_readback():
    assert_transition(PhaseState.VALIDATED_NOT_CACHED, PhaseState.PARTIAL_CACHE, True)
    assert_transition(PhaseState.PARTIAL_CACHE, PhaseState.CACHED_CLEAN, True)
    assert_transition(PhaseState.PARTIAL_CACHE, PhaseState.QUARANTINED, True)
    assert_transition(PhaseState.CACHED_CLEAN, PhaseState.REPLAY_DAILY_COMPLETE, True)
    assert_transition(PhaseState.QUARANTINED, PhaseState.REPLAY_DAILY_COMPLETE, True)
    assert_transition(PhaseState.REPLAY_DAILY_COMPLETE, PhaseState.EPISODES_COMPLETE, True)
    assert_transition(PhaseState.EPISODES_COMPLETE, PhaseState.OUTCOMES_COMPLETE, True)
    assert_transition(PhaseState.OUTCOMES_COMPLETE, PhaseState.BASELINES_COMPLETE, True)


def test_skip_ahead_and_missing_readback_fail():
    with pytest.raises(TransitionError):
        assert_transition(PhaseState.VALIDATED_NOT_CACHED, PhaseState.CACHED_CLEAN, True)
    with pytest.raises(TransitionError):
        assert_transition(PhaseState.PARTIAL_CACHE, PhaseState.CACHED_CLEAN, False)


def test_regression_requires_explicit_dq_reconciliation():
    with pytest.raises(TransitionError):
        assert_transition(PhaseState.OUTCOMES_COMPLETE, PhaseState.EPISODES_COMPLETE, True)
    assert_transition(
        PhaseState.OUTCOMES_COMPLETE,
        PhaseState.EPISODES_COMPLETE,
        True,
        dq_reconciliation=True,
    )
