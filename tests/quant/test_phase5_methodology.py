from investment_tracker.quant.phase5.methodology import (
    PROTECTED_SYMBOLS,
    SELECTED_BINDING_SHA256,
    SELECTED_CANDIDATE_ID,
    SYMBOLS,
    assert_allowed_symbols,
    frozen_binding,
)


def test_phase5_binds_exact_phase4_survivor():
    binding = frozen_binding()
    assert binding.candidate_id == SELECTED_CANDIDATE_ID
    assert binding.binding_sha256 == SELECTED_BINDING_SHA256
    assert binding.budget_position == 150
    assert binding.parameters_dict == {
        "lookback_sessions": 126,
        "rebalance_sessions": 21,
        "skip_sessions": 21,
        "top_k": 3,
    }


def test_phase5_universe_contains_no_protected_symbol():
    assert not (set(SYMBOLS) & PROTECTED_SYMBOLS)
    assert assert_allowed_symbols(SYMBOLS) == tuple(sorted(SYMBOLS))


def test_protected_symbol_fails_closed():
    try:
        assert_allowed_symbols((*SYMBOLS[:-1], "HACK"))
    except ValueError as exc:
        assert "PROTECTED_SYMBOL" in str(exc)
    else:
        raise AssertionError("protected symbol was admitted")
