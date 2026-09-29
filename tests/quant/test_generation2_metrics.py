from __future__ import annotations

import math

import pytest

from investment_tracker.quant.generation2.metrics import (
    calmar_from,
    drawdown_calmar,
    max_drawdown_from_equity,
)

ALL_CLOSE = [100.0, 110.0, 90.0, 95.0]


def test_max_drawdown_prepend_initial_cash_and_non_negative_magnitude() -> None:
    # series becomes [100, 110, 90, 95]; peak 110; trough 90 -> 20/110
    value = max_drawdown_from_equity(ALL_CLOSE, initial_cash=100.0)
    assert value.status == "AVAILABLE"
    assert value.reason == "OK"
    assert value.value == pytest.approx(20.0 / 110.0)
    assert value.value >= 0.0


def test_max_drawdown_flat_is_zero() -> None:
    value = max_drawdown_from_equity([100.0, 120.0, 150.0], initial_cash=100.0)
    assert value.status == "AVAILABLE"
    assert value.value == 0.0


def test_max_drawdown_uses_initial_cash_as_first_observation() -> None:
    # First close already below initial cash: drawdown measured from the
    # prepended initial-cash observation, not from the first close.
    value = max_drawdown_from_equity([90.0], initial_cash=100.0)
    assert value.status == "AVAILABLE"
    assert value.value == pytest.approx(0.10)


def test_max_drawdown_empty_is_unknown() -> None:
    value = max_drawdown_from_equity([], initial_cash=100.0)
    assert value.status == "UNKNOWN"
    assert value.reason == "INVALID_INPUT"
    assert value.value is None


def test_max_drawdown_missing_initial_cash_is_unknown() -> None:
    value = max_drawdown_from_equity(ALL_CLOSE, initial_cash=None)  # type: ignore[arg-type]
    assert value.status == "UNKNOWN"
    assert value.reason == "INVALID_INPUT"


def test_max_drawdown_nonfinite_initial_cash_is_unknown() -> None:
    for bad in (math.nan, math.inf, -math.inf):
        value = max_drawdown_from_equity(ALL_CLOSE, initial_cash=bad)
        assert value.status == "UNKNOWN"
        assert value.reason == "INVALID_INPUT"


def test_max_drawdown_non_positive_initial_cash_is_unknown() -> None:
    for bad in (0.0, -1.0):
        value = max_drawdown_from_equity(ALL_CLOSE, initial_cash=bad)
        assert value.status == "UNKNOWN"
        assert value.reason == "INVALID_INPUT"


def test_max_drawdown_non_finite_equity_is_unknown() -> None:
    for bad in (math.nan, math.inf, -math.inf):
        value = max_drawdown_from_equity([110.0, bad, 95.0], initial_cash=100.0)
        assert value.status == "UNKNOWN"
        assert value.reason == "INVALID_INPUT"


def test_max_drawdown_non_positive_equity_is_unknown() -> None:
    value = max_drawdown_from_equity([110.0, 0.0, 95.0], initial_cash=100.0)
    assert value.status == "UNKNOWN"
    assert value.reason == "INVALID_INPUT"


def test_calmar_positive_denominator() -> None:
    value = calmar_from(0.10, 0.2)
    assert value.status == "AVAILABLE"
    assert value.reason == "OK"
    assert value.value == pytest.approx(0.5)


def test_calmar_zero_drawdown_is_unknown_nonpositive_denominator() -> None:
    value = calmar_from(0.10, 0.0)
    assert value.status == "UNKNOWN"
    assert value.reason == "NONPOSITIVE_DENOMINATOR"
    assert value.value is None


def test_calmar_negative_cagr_is_not_clipped() -> None:
    value = calmar_from(-0.10, 0.2)
    assert value.status == "AVAILABLE"
    assert value.value == pytest.approx(-0.5)


def test_calmar_unavailable_cagr_is_unknown() -> None:
    for cagr in (None, math.nan, math.inf, -math.inf):
        value = calmar_from(cagr, 0.2)  # type: ignore[arg-type]
        assert value.status == "UNKNOWN"
        assert value.reason == "INVALID_INPUT"


def test_calmar_unavailable_mdd_is_unknown() -> None:
    for mdd in (None, math.nan, math.inf, -math.inf):
        value = calmar_from(0.10, mdd)  # type: ignore[arg-type]
        assert value.status == "UNKNOWN"
        assert value.reason == "INVALID_INPUT"


def test_calmar_negative_drawdown_is_unknown() -> None:
    # The drawdown is a non-negative magnitude; a negative input is a
    # non-positive denominator.
    value = calmar_from(0.10, -0.2)
    assert value.status == "UNKNOWN"
    assert value.reason == "NONPOSITIVE_DENOMINATOR"


def test_drawdown_calmar_end_to_end() -> None:
    mdd, calmar = drawdown_calmar(ALL_CLOSE, initial_cash=100.0, cagr=0.10)
    assert mdd.status == "AVAILABLE"
    assert mdd.value == pytest.approx(20.0 / 110.0)
    assert calmar.status == "AVAILABLE"
    assert calmar.value == pytest.approx(0.10 / (20.0 / 110.0))


def test_drawdown_calmar_flat_equity_calmar_unknown() -> None:
    mdd, calmar = drawdown_calmar([100.0, 120.0], initial_cash=100.0, cagr=0.05)
    assert mdd.status == "AVAILABLE"
    assert mdd.value == 0.0
    assert calmar.status == "UNKNOWN"
    assert calmar.reason == "NONPOSITIVE_DENOMINATOR"
