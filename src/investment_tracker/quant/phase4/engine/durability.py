from __future__ import annotations

from calendar import monthrange
from statistics import median

import math
import pandas as pd

from investment_tracker.quant.phase4.engine.models import (
    DurabilityEvidence,
    ExpectedSessionAuthority,
    Gate2SealError,
    MetricReason,
    MetricValue,
    PortfolioReplay,
    RollingWindowEvidence,
    UnavailableStatistics,
    _expected_session_identity,
)


def _available(value: float) -> MetricValue:
    return MetricValue(value=float(value), status="AVAILABLE", reason="OK")


def _unknown(reason: MetricReason) -> MetricValue:
    return MetricValue(value=None, status="UNKNOWN", reason=reason)


def expected_session_identity(sessions: tuple[pd.Timestamp, ...]) -> str:
    """Return the canonical identity of exact ordered expected session labels."""

    return _expected_session_identity(sessions)


def _compound(values: list[float]) -> float:
    level = 1.0
    for value in values:
        level *= 1.0 + value
    return level - 1.0


def _period_evidence(
    replay: PortfolioReplay,
    expected: ExpectedSessionAuthority,
    *,
    annual: bool,
) -> tuple[tuple[str, ...], tuple[MetricValue, ...]]:
    def key(value: pd.Timestamp) -> str:
        return f"{value.year:04d}" if annual else f"{value.year:04d}-{value.month:02d}"

    expected_by_period: dict[str, list[pd.Timestamp]] = {}
    for session in expected.sessions:
        expected_by_period.setdefault(key(session), []).append(session)
    actual_by_period: dict[str, list[pd.Timestamp]] = {}
    for session in replay.sessions:
        actual_by_period.setdefault(key(session), []).append(session)
    returns_by_session = dict(
        zip(replay.sessions[1:], replay.daily_returns, strict=True)
    )

    labels: list[str] = []
    values: list[MetricValue] = []
    for label in sorted(expected_by_period):
        labels.append(label)
        actual_sessions = tuple(actual_by_period.get(label, ()))
        expected_sessions = tuple(expected_by_period[label])
        if actual_sessions != expected_sessions:
            values.append(_unknown("INCOMPLETE_PERIOD"))
            continue
        period_returns = [
            returns_by_session[session]
            for session in actual_sessions
            if session in returns_by_session
        ]
        if any(not math.isfinite(value) or value <= -1.0 for value in period_returns):
            values.append(_unknown("INVALID_INPUT"))
        else:
            values.append(_available(_compound(period_returns)))
    return tuple(labels), tuple(values)


def _aggregate_fraction(values: list[float]) -> MetricValue:
    if not values:
        return _unknown("INSUFFICIENT_DATA")
    return _available(sum(value > 0.0 for value in values) / len(values))


def _signed_average(values: list[float], *, positive: bool) -> MetricValue:
    subset = [value for value in values if (value > 0.0 if positive else value < 0.0)]
    if not subset:
        return _unknown("EMPTY_SUBSET")
    return _available(sum(subset) / len(subset))


def _minimum(values: list[float]) -> MetricValue:
    return _available(min(values)) if values else _unknown("INSUFFICIENT_DATA")


def _concentration(values: list[float], *, top_three: bool = False) -> MetricValue:
    positives = sorted((value for value in values if value > 0.0), reverse=True)
    denominator = sum(positives)
    if denominator <= 0.0:
        return _unknown("NONPOSITIVE_DENOMINATOR")
    numerator = sum(positives[:3]) if top_three else positives[0]
    return _available(numerator / denominator)


def _subtract_months(value: pd.Timestamp, months: int) -> pd.Timestamp:
    month_index = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, monthrange(year, month)[1])
    return pd.Timestamp(year=year, month=month, day=day, tz="UTC")


def _rolling_evidence(
    replay: PortfolioReplay,
    expected: ExpectedSessionAuthority,
    horizon: int,
) -> RollingWindowEvidence:
    actual_set = set(replay.sessions)
    expected_sessions = expected.sessions
    expected_set = set(expected_sessions)
    equity = dict(zip(replay.sessions, replay.close_equity, strict=True))
    anchors: list[pd.Timestamp] = []
    endpoints: list[pd.Timestamp] = []
    observations: list[MetricValue] = []

    for endpoint in replay.sessions:
        target = _subtract_months(endpoint, horizon)
        eligible_anchors = [
            session for session in expected_sessions if session <= target
        ]
        if not eligible_anchors:
            continue
        anchor = eligible_anchors[-1]
        anchors.append(anchor)
        endpoints.append(endpoint)
        expected_window = {
            session for session in expected_set if anchor <= session <= endpoint
        }
        actual_window = {
            session for session in actual_set if anchor <= session <= endpoint
        }
        if (
            anchor not in actual_set
            or endpoint not in actual_set
            or not expected_window
            or actual_window != expected_window
        ):
            observations.append(_unknown("INCOMPLETE_WINDOW"))
            continue
        denominator = float(equity[anchor])
        numerator = float(equity[endpoint])
        if (
            not math.isfinite(denominator)
            or not math.isfinite(numerator)
            or denominator <= 0.0
            or numerator <= 0.0
        ):
            observations.append(_unknown("INVALID_INPUT"))
        else:
            observations.append(_available(numerator / denominator - 1.0))

    available_values = [
        item.value
        for item in observations
        if item.status == "AVAILABLE" and item.value is not None
    ]
    if available_values:
        minimum = _available(min(available_values))
        median_value = _available(median(available_values))
        positive_fraction = _available(
            sum(value > 0.0 for value in available_values) / len(available_values)
        )
    else:
        reason: MetricReason = (
            "INCOMPLETE_WINDOW" if observations else "INSUFFICIENT_DATA"
        )
        minimum = _unknown(reason)
        median_value = _unknown(reason)
        positive_fraction = _unknown(reason)

    return RollingWindowEvidence(
        horizon_months=horizon,
        anchors=tuple(anchors),
        endpoints=tuple(endpoints),
        observations=tuple(observations),
        minimum=minimum,
        median=median_value,
        positive_fraction=positive_fraction,
    )


def calculate_durability(
    replay: PortfolioReplay,
    expected: ExpectedSessionAuthority,
    *,
    horizons: tuple[int, ...] = (12, 36),
) -> DurabilityEvidence:
    """Calculate fixed-strategy calendar durability from scored close equity."""

    if not isinstance(replay, PortfolioReplay) or not isinstance(
        expected, ExpectedSessionAuthority
    ):
        raise Gate2SealError(
            "DURABILITY_EVIDENCE_INVALID",
            "durability requires a replay and exact expected-session authority",
        )
    if (
        not horizons
        or any(
            isinstance(value, bool) or value not in (12, 36, 60) for value in horizons
        )
        or len(set(horizons)) != len(horizons)
    ):
        raise Gate2SealError(
            "DURABILITY_EVIDENCE_INVALID",
            "durability horizons must be unique members of 12, 36, and 60",
        )
    if any(session not in set(expected.sessions) for session in replay.sessions):
        raise Gate2SealError(
            "DURABILITY_EVIDENCE_INVALID",
            "replay contains a session absent from expected-session authority",
        )
    if any(not math.isfinite(value) or value <= 0.0 for value in replay.close_equity):
        raise Gate2SealError(
            "DURABILITY_EVIDENCE_INVALID",
            "durability replay equity must be finite and positive",
        )

    month_labels, month_returns = _period_evidence(replay, expected, annual=False)
    year_labels, year_returns = _period_evidence(replay, expected, annual=True)
    month_values = [
        item.value
        for item in month_returns
        if item.status == "AVAILABLE" and item.value is not None
    ]
    year_values = [
        item.value
        for item in year_returns
        if item.status == "AVAILABLE" and item.value is not None
    ]

    streak = 0
    longest = 0
    for item in month_returns:
        if item.status != "AVAILABLE" or item.value is None:
            streak = 0
            continue
        streak = streak + 1 if item.value < 0.0 else 0
        longest = max(longest, streak)
    longest_metric = (
        _available(float(longest)) if month_values else _unknown("INSUFFICIENT_DATA")
    )

    rolling_12 = _rolling_evidence(replay, expected, 12)
    rolling_36 = _rolling_evidence(replay, expected, 36)
    rolling_60 = _rolling_evidence(replay, expected, 60) if 60 in horizons else None

    return DurabilityEvidence(
        candidate_id=replay.candidate_id,
        binding_sha256=replay.binding_sha256,
        expected_sessions_authority_sha256=expected.sha256,
        month_period_labels=month_labels,
        month_returns=month_returns,
        year_period_labels=year_labels,
        year_returns=year_returns,
        positive_month_fraction=_aggregate_fraction(month_values),
        positive_year_fraction=_aggregate_fraction(year_values),
        average_positive_month=_signed_average(month_values, positive=True),
        average_negative_month=_signed_average(month_values, positive=False),
        worst_month=_minimum(month_values),
        worst_year=_minimum(year_values),
        longest_negative_month_streak=longest_metric,
        positive_month_concentration=_concentration(month_values),
        positive_year_concentration=_concentration(year_values),
        top_three_positive_month_concentration=_concentration(
            month_values, top_three=True
        ),
        rolling_12=rolling_12,
        rolling_36=rolling_36,
        rolling_60=rolling_60,
        unavailable_statistics=UnavailableStatistics(),
    )


__all__ = ("calculate_durability", "expected_session_identity")
