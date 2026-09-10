from __future__ import annotations

from datetime import date
from collections.abc import Iterable


def first_executable_session(trading_dates: Iterable[date], eligibility_date: date) -> date:
    eligible = [value for value in trading_dates if value >= eligibility_date]
    if not eligible:
        raise ValueError("no executable trading session at or after eligibility date")
    return min(eligible)


def monthly_dca_sessions(trading_dates: Iterable[date]) -> list[date]:
    selected: dict[tuple[int, int], date] = {}
    for value in sorted(trading_dates):
        selected.setdefault((value.year, value.month), value)
    return list(selected.values())


def simple_dip_qualifies(close: float, prior60_high: float | None) -> bool | None:
    if prior60_high is None or prior60_high <= 0:
        return None
    return close <= 0.90 * prior60_high


def simple_dip_episode_starts(qualifying_flags: Iterable[bool]) -> list[bool]:
    starts: list[bool] = []
    previous = False
    for current in qualifying_flags:
        starts.append(bool(current) and not previous)
        previous = bool(current)
    return starts
