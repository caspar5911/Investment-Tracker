from __future__ import annotations

import pandas as pd
import pytest

from investment_tracker.quant.validation.walk_forward import generate_walk_forward_folds


def test_walk_forward_folds_are_chronological_rolling_and_disjoint() -> None:
    sessions = pd.bdate_range("2010-01-01", "2018-12-31", tz="UTC")
    folds = generate_walk_forward_folds(sessions, train_years=5, test_years=1)
    assert len(folds) == 4
    assert folds[0].train_start.year == 2010
    assert folds[0].train_end.year == 2014
    assert folds[0].test_start.year == 2015
    assert folds[-1].train_start.year == 2013
    assert folds[-1].test_start.year == 2018
    assert all(fold.train_end < fold.test_start <= fold.test_end for fold in folds)
    assert all(left.test_end < right.test_start for left, right in zip(folds, folds[1:]))


def test_walk_forward_rejects_unsorted_or_duplicate_sessions() -> None:
    sessions = pd.DatetimeIndex(["2020-01-02", "2020-01-02"], tz="UTC")
    with pytest.raises(ValueError, match="unique and increasing"):
        generate_walk_forward_folds(sessions, train_years=1, test_years=1)


def test_walk_forward_requires_enough_history() -> None:
    sessions = pd.bdate_range("2020-01-01", "2022-12-31", tz="UTC")
    with pytest.raises(ValueError, match="insufficient history"):
        generate_walk_forward_folds(sessions, train_years=5, test_years=1)
