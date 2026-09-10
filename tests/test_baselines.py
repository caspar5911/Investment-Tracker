from datetime import date

from investment_tracker.baselines import (
    first_executable_session,
    monthly_dca_sessions,
    simple_dip_episode_starts,
    simple_dip_qualifies,
)


def test_buy_and_hold_starts_at_first_eligible_trading_session():
    dates = [date(2020, 11, 20), date(2020, 11, 23), date(2020, 11, 24)]
    assert first_executable_session(dates, date(2020, 11, 23)) == date(2020, 11, 23)


def test_monthly_dca_uses_first_trading_session_of_each_month():
    dates = [
        date(2021, 1, 4),
        date(2021, 1, 5),
        date(2021, 2, 1),
        date(2021, 2, 2),
        date(2021, 3, 1),
    ]
    assert monthly_dca_sessions(dates) == [date(2021, 1, 4), date(2021, 2, 1), date(2021, 3, 1)]


def test_simple_dip_is_10_percent_below_prior60_high_and_deduplicated():
    assert simple_dip_qualifies(90.0, 100.0) is True
    assert simple_dip_qualifies(90.01, 100.0) is False
    assert simple_dip_qualifies(90.0, None) is None
    flags = [False, True, True, False, True, False]
    assert simple_dip_episode_starts(flags) == [False, True, False, False, True, False]
