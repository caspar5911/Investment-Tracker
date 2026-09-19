from decimal import Decimal

import pytest

from investment_tracker.drawdown_v2 import max_drawdown_close_path


def test_drawdown_uses_entry_open_as_initial_high_water_and_later_peaks():
    result = max_drawdown_close_path(
        Decimal("100"),
        [Decimal("105"), Decimal("102"), Decimal("108"), Decimal("90")],
    )
    assert result == Decimal("90") / Decimal("108") - Decimal(1)


def test_drawdown_captures_loss_from_entry_before_any_new_high():
    result = max_drawdown_close_path(
        Decimal("100"),
        [Decimal("95"), Decimal("97"), Decimal("96")],
    )
    assert result == Decimal("-0.05")


def test_missing_close_or_censored_horizon_is_unknown():
    assert max_drawdown_close_path(
        Decimal("100"), [Decimal("99"), None, Decimal("101")]
    ) is None
    assert max_drawdown_close_path(
        Decimal("100"), [Decimal("99")], censored=True
    ) is None


def test_nonpositive_price_is_rejected():
    with pytest.raises(ValueError, match="entry_open"):
        max_drawdown_close_path(Decimal("0"), [Decimal("1")])
    with pytest.raises(ValueError, match="close"):
        max_drawdown_close_path(Decimal("1"), [Decimal("0")])
