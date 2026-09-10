import pytest

from investment_tracker.governance import (
    FROZEN_VERSIONS,
    LOCKED_HOLDOUT,
    LockedHoldoutError,
    PHASE_A_END,
    PHASE_B_END,
    assert_symbol_allowed,
)


def test_frozen_governance_is_exact():
    assert FROZEN_VERSIONS.tpc == "TPC-v1.2"
    assert FROZEN_VERSIONS.replay == "REPLAY-v1.0"
    assert FROZEN_VERSIONS.calc == "CALC-v1.2"
    assert FROZEN_VERSIONS.robust == "ROBUST-v1.0"
    assert LOCKED_HOLDOUT == frozenset({"HACK", "SOXX", "NLR", "URNM", "GEV"})
    assert PHASE_A_END.isoformat() == "2023-12-31"
    assert PHASE_B_END.isoformat() == "2025-09-07"


def test_locked_holdout_is_rejected_before_use():
    with pytest.raises(LockedHoldoutError):
        assert_symbol_allowed("hack")


def test_allowed_symbol_is_normalized():
    assert assert_symbol_allowed("ura") == "URA"
