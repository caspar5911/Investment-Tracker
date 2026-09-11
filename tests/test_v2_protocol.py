from decimal import Decimal

import pytest

from investment_tracker.v2_protocol import (
    MAX_DRAWDOWN_CONVENTION,
    RB09_TIE_CONVENTION,
    SessionOutcome,
    max_drawdown_close_gross,
    rb09_equal_weight_nonoverlap,
)


def test_max_drawdown_close_gross_uses_entry_open_and_prior_peak():
    result = max_drawdown_close_gross(
        Decimal("100"),
        [Decimal("110"), Decimal("105"), Decimal("120"), Decimal("90")],
    )
    assert result == Decimal("-0.25")


def test_max_drawdown_never_becomes_positive():
    assert max_drawdown_close_gross(
        Decimal("100"), [Decimal("101"), Decimal("102"), Decimal("103")]
    ) == Decimal("0")


def test_max_drawdown_rejects_invalid_prices():
    with pytest.raises(ValueError):
        max_drawdown_close_gross(Decimal("0"), [Decimal("100")])
    with pytest.raises(ValueError):
        max_drawdown_close_gross(Decimal("100"), [Decimal("-1")])


def test_rb09_same_session_ties_are_equal_weight_and_order_invariant():
    rows = [
        SessionOutcome("ETN", 10, Decimal("0.10")),
        SessionOutcome("PWR", 10, Decimal("-0.02")),
        SessionOutcome("URA", 31, Decimal("0.03")),
    ]
    forward = rb09_equal_weight_nonoverlap(rows, horizon_sessions=20)
    reverse = rb09_equal_weight_nonoverlap(reversed(rows), horizon_sessions=20)

    assert forward == reverse
    assert forward[0].entry_session_index == 10
    assert forward[0].assets == ("ETN", "PWR")
    assert forward[0].excess_spy == Decimal("0.04")
    assert forward[1].entry_session_index == 31


def test_rb09_nonoverlap_uses_benchmark_session_distance():
    rows = [
        SessionOutcome("ETN", 5, Decimal("0.01")),
        SessionOutcome("PWR", 24, Decimal("0.02")),
        SessionOutcome("URA", 25, Decimal("0.03")),
    ]
    selected = rb09_equal_weight_nonoverlap(rows, horizon_sessions=20)
    assert [row.entry_session_index for row in selected] == [5, 25]


def test_rb09_locked_holdout_is_rejected_before_analysis():
    with pytest.raises(ValueError, match="locked replacement holdout"):
        rb09_equal_weight_nonoverlap(
            [SessionOutcome("HACK", 10, Decimal("0.01"))]
        )


def test_v2_conventions_are_explicit_text_contracts():
    assert "entry open" in MAX_DRAWDOWN_CONVENTION
    assert "equal-weight" in RB09_TIE_CONVENTION
