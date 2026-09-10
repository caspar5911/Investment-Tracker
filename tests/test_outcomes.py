from datetime import date

import pytest

from investment_tracker.outcomes import (
    MAE_MFE_UNKNOWN,
    MAE_MFE_USABLE,
    apply_friction,
    cash_hurdle,
    horizon_return,
    is_censored,
    range_metrics_status,
)


def test_horizon_return_uses_entry_open_and_horizon_close():
    assert horizon_return(100.0, 110.0) == pytest.approx(0.10)


def test_frozen_round_trip_friction_is_subtracted_once():
    assert apply_friction(0.10, 0) == pytest.approx(0.10)
    assert apply_friction(0.10, 10) == pytest.approx(0.099)
    assert apply_friction(0.10, 25) == pytest.approx(0.0975)
    with pytest.raises(ValueError):
        apply_friction(0.10, 5)


def test_cash_hurdle_uses_actual_calendar_days():
    expected = (1.0325 ** (365 / 365)) - 1
    assert cash_hurdle(date(2020, 1, 1), date(2020, 12, 31)) == pytest.approx(expected)


def test_c24_phase_boundaries_censor_only_crossing_horizons():
    assert is_censored(date(2023, 12, 31), "PHASE_A") is False
    assert is_censored(date(2024, 1, 2), "PHASE_A") is True
    assert is_censored(date(2025, 9, 7), "PHASE_B") is False
    assert is_censored(date(2025, 9, 8), "PHASE_B") is True


def test_range_quarantine_only_blocks_mae_mfe():
    assert range_metrics_status([True, True, True]) == MAE_MFE_USABLE
    assert range_metrics_status([True, False, True]) == MAE_MFE_UNKNOWN
