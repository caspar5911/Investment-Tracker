from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class WalkForwardFold:
    fold_id: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def generate_walk_forward_folds(
    sessions: pd.DatetimeIndex,
    *,
    train_years: int,
    test_years: int,
) -> tuple[WalkForwardFold, ...]:
    if train_years <= 0 or test_years <= 0:
        raise ValueError("train_years and test_years must be positive")
    if sessions.has_duplicates or not sessions.is_monotonic_increasing:
        raise ValueError("sessions must be unique and increasing")
    if sessions.empty:
        raise ValueError("insufficient history for walk-forward folds")

    first_year = sessions[0].year
    last_year = sessions[-1].year
    first_test_year = first_year + train_years
    last_test_year = last_year - test_years + 1
    if first_test_year > last_test_year:
        raise ValueError("insufficient history for walk-forward folds")

    folds: list[WalkForwardFold] = []
    for test_start_year in range(first_test_year, last_test_year + 1, test_years):
        train_start_year = test_start_year - train_years
        test_end_year = test_start_year + test_years - 1
        train_sessions = sessions[(sessions.year >= train_start_year) & (sessions.year < test_start_year)]
        test_sessions = sessions[(sessions.year >= test_start_year) & (sessions.year <= test_end_year)]
        if train_sessions.empty or test_sessions.empty:
            continue
        folds.append(
            WalkForwardFold(
                fold_id=f"WF-{test_start_year}-{test_end_year}",
                train_start=train_sessions[0],
                train_end=train_sessions[-1],
                test_start=test_sessions[0],
                test_end=test_sessions[-1],
            )
        )
    if not folds:
        raise ValueError("insufficient history for walk-forward folds")
    return tuple(folds)
