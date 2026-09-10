from investment_tracker.replay import (
    ABSTAIN,
    ACCUMULATE,
    FAIL,
    PASS,
    TRIM_AVOID,
    UNKNOWN,
    WAIT,
    WATCH,
    chase_gate,
    is_episode_start,
    pullback_gate,
    relative_strength_gate,
    signal_state,
    stabilization_gate,
    trend_gate,
)


def test_frozen_price_gates_use_exact_inequalities():
    assert trend_gate(101.0, 100.0) == PASS
    assert trend_gate(100.0, 100.0) == FAIL

    assert pullback_gate(95.0, 100.0) == PASS
    assert pullback_gate(85.0, 100.0) == PASS
    assert pullback_gate(95.01, 100.0) == FAIL
    assert pullback_gate(84.99, 100.0) == FAIL

    assert stabilization_gate(101.0, 100.0, 101.0) == PASS
    assert stabilization_gate(100.0, 100.0, 99.0) == FAIL
    assert stabilization_gate(101.0, 100.0, 101.01) == FAIL

    assert relative_strength_gate(-0.02, 0.03) == PASS
    assert relative_strength_gate(-0.0201, 0.03) == FAIL

    assert chase_gate(98.0, 100.0, 0.08) == FAIL
    assert chase_gate(97.99, 100.0, 0.08) == PASS
    assert chase_gate(98.0, 100.0, 0.0799) == PASS


def test_missing_gate_inputs_are_unknown():
    assert trend_gate(100.0, None) == UNKNOWN
    assert pullback_gate(90.0, None) == UNKNOWN
    assert stabilization_gate(100.0, None, 99.0) == UNKNOWN
    assert relative_strength_gate(None, 0.01) == UNKNOWN
    assert chase_gate(99.0, None, 0.1) == UNKNOWN


def test_frozen_state_precedence():
    assert signal_state(FAIL, PASS, PASS, PASS, PASS, -0.11) == TRIM_AVOID
    assert signal_state(FAIL, PASS, PASS, PASS, PASS, -0.10) == WAIT
    assert signal_state(PASS, PASS, PASS, PASS, FAIL, 0.0) == WAIT
    assert signal_state(PASS, FAIL, PASS, PASS, PASS, 0.0) == WATCH
    assert signal_state(PASS, PASS, FAIL, PASS, PASS, 0.0) == WATCH
    assert signal_state(PASS, PASS, PASS, FAIL, PASS, 0.0) == WATCH
    assert signal_state(PASS, PASS, PASS, PASS, PASS, 0.0) == ACCUMULATE
    assert signal_state(PASS, PASS, UNKNOWN, PASS, PASS, 0.0) == ABSTAIN


def test_episode_start_only_on_transition_into_accumulate():
    assert is_episode_start(WATCH, ACCUMULATE) is True
    assert is_episode_start(ACCUMULATE, ACCUMULATE) is False
    assert is_episode_start(None, ACCUMULATE) is True
    assert is_episode_start(WAIT, WATCH) is False
