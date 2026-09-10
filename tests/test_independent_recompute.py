from datetime import date, timedelta
from decimal import Decimal

import pytest

from investment_tracker.independent_recompute import (
    AuditBar,
    compare_records,
    recompute_baseline_entries,
    recompute_outcomes,
    recompute_replay,
)


def bars(asset: str, count: int = 262):
    start = date(2020, 1, 1)
    return [AuditBar(asset, start + timedelta(days=i), Decimal(100 + i) / 2, Decimal(102 + i) / 2, Decimal(98 + i) / 2, Decimal(100 + i) / 2) for i in range(count)]


def test_independent_sma200_is_inclusive_and_benchmark_dates_must_match():
    asset, spy = bars("URA", 200), bars("SPY", 200)
    result = recompute_replay(asset, spy)
    assert result[-1].sma200 == sum((b.close for b in asset), Decimal(0)) / 200
    with pytest.raises(ValueError, match="benchmark dates"):
        recompute_replay(asset, spy[:-1])


def test_outcome_uses_next_open_exact_spy_date_friction_and_quarantine():
    asset, spy = bars("URA"), bars("SPY")
    replay = recompute_replay(asset, spy)
    # Force one independently represented episode; calculations still use raw bars.
    episode = [replay[220].__class__(**{**replay[220].__dict__, "episode_start": True})]
    outcomes = recompute_outcomes(episode, asset, spy)
    one = next(r for r in outcomes if r.horizon_td == 1 and r.friction_bps == 10)
    assert one.entry_date == asset[221].bar_date
    assert one.asset_return == asset[221].close / asset[221].open - 1
    assert one.return_net == one.asset_return - Decimal("0.001")

    quarantined = list(asset)
    quarantined[221] = AuditBar(**{**quarantined[221].__dict__, "range_usable": False})
    q = recompute_outcomes(episode, quarantined, spy)[0]
    assert q.mae is None and q.mfe is None
    assert q.asset_return is not None


def test_independent_baselines_and_strict_comparison():
    source = bars("URA", 65)
    source[60] = AuditBar(**{**source[60].__dict__, "close": Decimal("1")})
    entries = recompute_baseline_entries(source)
    assert entries["C17_BUY_AND_HOLD"] == [source[0].bar_date]
    assert entries["C19_SIMPLE_DIP"] == [source[61].bar_date]
    assert len(entries["C18_MONTHLY_DCA"]) >= 2

    canonical = [{"asset": "URA", "bar_date": date(2020, 1, 1), "state": "WAIT"}]
    recomputed = [{"asset": "URA", "bar_date": date(2020, 1, 1), "state": "WATCH"}]
    mismatch = compare_records("replay", canonical, recomputed, ("asset", "bar_date"))
    assert [(m.section, m.field) for m in mismatch] == [("replay", "state")]


def test_locked_holdout_is_rejected_before_recomputation():
    with pytest.raises(ValueError, match="locked replacement holdout"):
        recompute_replay(bars("HACK", 2), bars("SPY", 2))
