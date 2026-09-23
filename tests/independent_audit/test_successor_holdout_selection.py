from __future__ import annotations

from datetime import date

import pandas as pd

from investment_tracker.independent_audit.successor.holdout_selection import (
    select_from_static_frame,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"code": "US.AAA", "name": "Alpha ETF", "listing_date": "2010-01-01", "delisting": False},
            {"code": "US.BBB", "name": "Beta ETF", "listing_date": "2011-01-01", "delisting": False},
            {"code": "US.CCC", "name": "Gamma ETF", "listing_date": "2012-01-01", "delisting": False},
            {"code": "US.DDD", "name": "Delta ETF", "listing_date": "2013-01-01", "delisting": False},
            {"code": "US.EEE", "name": "Epsilon ETF", "listing_date": "2014-01-01", "delisting": False},
            {"code": "US.FFF", "name": "Zeta ETF", "listing_date": "2015-01-01", "delisting": False},
            {"code": "US.GGG", "name": "Eta ETF", "listing_date": "2024-01-01", "delisting": False},
            {"code": "US.HHH", "name": "Theta ETF", "listing_date": "2016-01-01", "delisting": True},
        ]
    )


def test_selection_is_deterministic_and_static_only() -> None:
    kwargs = dict(
        permanent_exclusions=frozenset({"AAA"}),
        provider_history_symbols={"BBB"},
        retained_log_history_symbols={"CCC"},
        listing_cutoff=date(2022, 1, 1),
        selection_count=3,
        seed_sha256="1" * 64,
    )
    first, counts = select_from_static_frame(_frame(), **kwargs)
    second, _ = select_from_static_frame(_frame(), **kwargs)
    assert first == second
    assert len(first) == 3
    assert {item.symbol for item in first}.isdisjoint({"AAA", "BBB", "CCC", "GGG", "HHH"})
    assert counts["permanent_exclusion_registry"] == 1
    assert counts["provider_history_ledger"] == 1
    assert counts["retained_log_history_context"] == 1
    assert counts["listing_date_missing_or_too_late"] == 1
    assert counts["delisted"] == 1


def test_selection_count_can_fail_closed_by_returning_short_result() -> None:
    selected, _ = select_from_static_frame(
        _frame(),
        permanent_exclusions=frozenset({"AAA", "BBB", "CCC", "DDD", "EEE", "FFF"}),
        provider_history_symbols=set(),
        retained_log_history_symbols=set(),
        listing_cutoff=date(2022, 1, 1),
        selection_count=5,
        seed_sha256="2" * 64,
    )
    assert len(selected) == 0


def test_rank_key_changes_with_seed_without_using_market_data() -> None:
    a, _ = select_from_static_frame(
        _frame(),
        permanent_exclusions=frozenset(),
        provider_history_symbols=set(),
        retained_log_history_symbols=set(),
        listing_cutoff=date(2022, 1, 1),
        selection_count=4,
        seed_sha256="a" * 64,
    )
    b, _ = select_from_static_frame(
        _frame(),
        permanent_exclusions=frozenset(),
        provider_history_symbols=set(),
        retained_log_history_symbols=set(),
        listing_cutoff=date(2022, 1, 1),
        selection_count=4,
        seed_sha256="b" * 64,
    )
    assert tuple(item.rank_key for item in a) != tuple(item.rank_key for item in b)
