from __future__ import annotations

import pandas as pd
import pytest
from pydantic import ValidationError

from investment_tracker.quant.phase4.engine.durability import (
    calculate_durability,
    expected_session_identity,
)
from investment_tracker.quant.phase4.engine.models import (
    DurabilityEvidence,
    ExpectedSessionAuthority,
    PortfolioReplay,
    SessionState,
)


def _replay(
    sessions: tuple[pd.Timestamp, ...], equity: tuple[float, ...]
) -> PortfolioReplay:
    states = tuple(
        SessionState(
            session=session,
            open_equity=value,
            close_equity=value,
            cash=value,
            units=(),
            realized_gross_exposure=0.0,
            target_gross_exposure=0.0,
            binding=None,
        )
        for session, value in zip(sessions, equity, strict=True)
    )
    return PortfolioReplay(
        friction_bps=3,
        initial_cash=equity[0],
        states=states,
        total_turnover=0.0,
    )


def _expected(sessions: tuple[pd.Timestamp, ...]) -> ExpectedSessionAuthority:
    return ExpectedSessionAuthority(
        sessions=sessions,
        sha256=expected_session_identity(sessions),
    )


def _levels(first: float, returns: tuple[float, ...]) -> tuple[float, ...]:
    values = [first]
    for value in returns:
        values.append(values[-1] * (1.0 + value))
    return tuple(values)


def test_expected_session_identity_binds_exact_ordered_utc_labels() -> None:
    sessions = tuple(pd.date_range("2020-01-02", periods=2, tz="UTC"))
    identity = expected_session_identity(sessions)
    authority = ExpectedSessionAuthority(sessions=sessions, sha256=identity)

    assert authority.sha256 == identity
    with pytest.raises(ValidationError):
        ExpectedSessionAuthority(sessions=sessions, sha256="0" * 64)
    with pytest.raises((ValidationError, ValueError)):
        expected_session_identity(tuple(reversed(sessions)))


def test_month_year_sign_streak_and_concentration_metrics_use_compounding() -> None:
    sessions = tuple(
        pd.Timestamp(value, tz="UTC")
        for value in (
            "2019-01-02",
            "2019-01-03",
            "2019-02-01",
            "2019-03-01",
            "2020-01-02",
        )
    )
    replay = _replay(sessions, _levels(100.0, (0.10, -0.05, -0.02, 0.03)))

    result = calculate_durability(replay, _expected(sessions))
    months = dict(zip(result.month_period_labels, result.month_returns, strict=True))
    years = dict(zip(result.year_period_labels, result.year_returns, strict=True))

    assert months["2019-01"].value == pytest.approx(0.10)
    assert months["2019-02"].value == pytest.approx(-0.05)
    assert months["2019-03"].value == pytest.approx(-0.02)
    assert months["2020-01"].value == pytest.approx(0.03)
    assert years["2019"].value == pytest.approx(1.10 * 0.95 * 0.98 - 1.0)
    assert result.positive_month_fraction.value == pytest.approx(0.5)
    assert result.positive_year_fraction.value == pytest.approx(1.0)
    assert result.average_positive_month.value == pytest.approx(0.065)
    assert result.average_negative_month.value == pytest.approx(-0.035)
    assert result.worst_month.value == pytest.approx(-0.05)
    assert result.worst_year.value == pytest.approx(1.10 * 0.95 * 0.98 - 1.0)
    assert result.longest_negative_month_streak.value == 2.0
    assert result.positive_month_concentration.value == pytest.approx(0.10 / 0.13)
    assert result.top_three_positive_month_concentration.value == pytest.approx(1.0)


def test_zero_month_breaks_losing_streak_and_empty_sign_subsets_are_unknown() -> None:
    sessions = tuple(
        pd.Timestamp(value, tz="UTC")
        for value in ("2020-01-02", "2020-02-03", "2020-03-02", "2020-04-01")
    )
    replay = _replay(sessions, _levels(100.0, (-0.01, 0.0, -0.02)))

    result = calculate_durability(replay, _expected(sessions))

    assert result.longest_negative_month_streak.value == 1.0
    assert result.average_positive_month.status == "UNKNOWN"
    assert result.average_positive_month.reason == "EMPTY_SUBSET"
    assert result.positive_month_concentration.status == "UNKNOWN"
    assert result.positive_month_concentration.reason == "NONPOSITIVE_DENOMINATOR"


def test_incomplete_calendar_period_is_retained_and_excluded() -> None:
    expected_sessions = tuple(pd.date_range("2020-01-02", periods=2, tz="UTC"))
    replay = _replay((expected_sessions[0],), (100.0,))

    result = calculate_durability(replay, _expected(expected_sessions))

    assert result.month_period_labels == ("2020-01",)
    assert result.month_returns[0].status == "UNKNOWN"
    assert result.month_returns[0].reason == "INCOMPLETE_PERIOD"
    assert result.positive_month_fraction.status == "UNKNOWN"
    assert result.positive_month_fraction.reason == "INSUFFICIENT_DATA"


def test_unknown_month_breaks_a_losing_month_sequence() -> None:
    expected_sessions = tuple(
        pd.Timestamp(value, tz="UTC")
        for value in ("2020-01-02", "2020-01-03", "2020-02-03", "2020-03-02")
    )
    actual_sessions = (
        expected_sessions[0],
        expected_sessions[1],
        expected_sessions[3],
    )
    replay = _replay(actual_sessions, _levels(100.0, (-0.10, -0.10)))

    result = calculate_durability(replay, _expected(expected_sessions))

    assert result.month_returns[1].reason == "INCOMPLETE_PERIOD"
    assert result.longest_negative_month_streak.value == 1.0


def test_rolling_windows_use_gregorian_anchors_and_support_phase5_sixty_months() -> (
    None
):
    sessions = tuple(pd.date_range("2017-01-31", "2022-01-31", freq="ME", tz="UTC"))
    replay = _replay(sessions, tuple(100.0 * (1.01**i) for i in range(len(sessions))))

    result = calculate_durability(replay, _expected(sessions), horizons=(12, 36, 60))

    assert result.rolling_12.anchors[0] == pd.Timestamp("2017-01-31", tz="UTC")
    assert result.rolling_12.endpoints[0] == pd.Timestamp("2018-01-31", tz="UTC")
    assert result.rolling_12.observations[0].value == pytest.approx(1.01**12 - 1.0)
    assert result.rolling_36.anchors[0] == pd.Timestamp("2017-01-31", tz="UTC")
    assert result.rolling_36.endpoints[0] == pd.Timestamp("2020-01-31", tz="UTC")
    assert result.rolling_60 is not None
    assert result.rolling_60.anchors[0] == pd.Timestamp("2017-01-31", tz="UTC")
    assert result.rolling_60.endpoints[0] == pd.Timestamp("2022-01-31", tz="UTC")
    assert result.rolling_12.minimum.status == "AVAILABLE"
    assert result.rolling_12.median.status == "AVAILABLE"
    assert result.rolling_12.positive_fraction.value == 1.0


def test_leap_day_anchor_clamps_to_target_month_end() -> None:
    sessions = (
        pd.Timestamp("2019-02-28", tz="UTC"),
        pd.Timestamp("2020-02-29", tz="UTC"),
    )
    replay = _replay(sessions, (100.0, 110.0))

    result = calculate_durability(replay, _expected(sessions))

    assert result.rolling_12.anchors == (pd.Timestamp("2019-02-28", tz="UTC"),)
    assert result.rolling_12.endpoints == (pd.Timestamp("2020-02-29", tz="UTC"),)
    assert result.rolling_12.observations[0].value == pytest.approx(0.10)


def test_missing_expected_session_marks_rolling_window_incomplete() -> None:
    expected_sessions = tuple(
        pd.date_range("2020-01-31", "2021-01-31", freq="ME", tz="UTC")
    )
    actual_sessions = tuple(
        session
        for session in expected_sessions
        if session != pd.Timestamp("2020-06-30", tz="UTC")
    )
    replay = _replay(
        actual_sessions,
        tuple(100.0 * (1.01**i) for i in range(len(actual_sessions))),
    )

    result = calculate_durability(replay, _expected(expected_sessions))

    assert result.rolling_12.observations[-1].status == "UNKNOWN"
    assert result.rolling_12.observations[-1].reason == "INCOMPLETE_WINDOW"
    assert result.rolling_12.minimum.status == "UNKNOWN"
    assert result.rolling_12.minimum.reason == "INCOMPLETE_WINDOW"


def test_durability_models_reject_misaligned_period_and_rolling_evidence() -> None:
    sessions = tuple(pd.date_range("2020-01-31", "2021-01-31", freq="ME", tz="UTC"))
    result = calculate_durability(
        _replay(sessions, tuple(100.0 + i for i in range(len(sessions)))),
        _expected(sessions),
    )
    payload = result.model_dump()
    payload["month_period_labels"] = ()

    with pytest.raises(ValidationError):
        DurabilityEvidence.model_validate(payload)
