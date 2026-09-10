from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from investment_tracker.capabilities import CanonicalWriteDenied, canonical_writer_capability
from investment_tracker.models import EpisodeOutcomeRow
from investment_tracker.normalization import normalize_price, verify_normalized_price
from investment_tracker.validation import validate_session_coverage


def test_missing_and_duplicate_sessions_fail_closed():
    days = [date(2023, 1, 3), date(2023, 1, 4), date(2023, 1, 5)]
    assert validate_session_coverage(days, days).ok
    report = validate_session_coverage([days[0], days[0], days[2]], days)
    assert not report.ok
    assert report.counts["missing"] == 1
    assert report.counts["duplicates"] == 1


def test_split_normalization_requires_exact_frozen_arithmetic():
    assert normalize_price(Decimal("100"), Decimal("2")) == Decimal("50")
    with pytest.raises(ValueError, match="normalization mismatch"):
        verify_normalized_price(Decimal("100"), Decimal("2"), Decimal("100"))


def test_worker_cannot_obtain_canonical_write_capability():
    with pytest.raises(CanonicalWriteDenied):
        canonical_writer_capability("URA_WORKER")
    assert canonical_writer_capability("coordinator").role == "COORDINATOR"


def test_dq030_rejects_numeric_max_drawdown():
    with pytest.raises(ValidationError, match="max_drawdown"):
        EpisodeOutcomeRow(
            episode_id="e1", asset="URA", signal_start_date=date(2023, 1, 3),
            signal_end_date=date(2023, 1, 3), signal_days=1,
            entry_date=date(2023, 1, 4), entry_open=Decimal("10"), horizon_td=1,
            asset_return=Decimal("0.01"), spy_return=Decimal("0"),
            excess_spy=Decimal("0.01"), cash_return=Decimal("0"),
            excess_cash=Decimal("0.01"), mae=None, mfe=None,
            max_drawdown=Decimal("0.02"), friction_bps=0,
            return_net=Decimal("0.01"), dq_status="CLEAN",
            calculation_run_id="run", calculation_version="CALC-v1.2",
        )
