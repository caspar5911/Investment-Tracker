"""Generation-2 performance metrics over the decision-ledger replay.

The metrics consume a ``DecisionReplayResult`` (the
``UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS`` equity series) and return
Phase-4 ``MetricValue`` objects with fail-closed statuses:

- ``AVAILABLE`` with a finite value when computable;
- ``UNKNOWN/INSUFFICIENT_DATA`` when the replay window is too short;
- ``UNKNOWN/INVALID_INPUT`` when the equity series is empty, non-finite, or
  non-positive;
- ``UNKNOWN/NONPOSITIVE_DENOMINATOR`` when a dispersion term is zero.

Annualization constants: 252 sessions per year for rate metrics, 365.25
days for calendar CAGR. The rolling-12-month positive fraction requires a
full 252-session lookback per window and is unavailable on shorter spans.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from investment_tracker.quant.generation2.accounting import DecisionReplayResult
from investment_tracker.quant.generation2.metrics import drawdown_calmar
from investment_tracker.quant.phase4.engine.models import MetricValue

ANNUAL_SESSIONS = 252
ROLLING_12M_SESSIONS = 252

__all__ = [
    "ANNUAL_SESSIONS",
    "PerformanceSummary",
    "ROLLING_12M_SESSIONS",
    "annualized_one_way_turnover",
    "cagr",
    "calmar",
    "exposure_invariant_passes",
    "max_drawdown",
    "rolling_12m_positive_fraction",
    "sharpe",
    "sortino",
    "summarize",
    "total_return",
]


def _unknown(reason: str) -> MetricValue:
    return MetricValue(value=None, status="UNKNOWN", reason=reason)


def _available(value: float) -> MetricValue:
    return MetricValue(value=float(value), status="AVAILABLE", reason="OK")


def _equity(replay: DecisionReplayResult) -> tuple[float, ...] | None:
    equity = replay.close_equity
    if not equity:
        return None
    if any(not math.isfinite(value) or value <= 0.0 for value in equity):
        return None
    return equity


def total_return(replay: DecisionReplayResult) -> MetricValue:
    equity = _equity(replay)
    if equity is None:
        return _unknown("INVALID_INPUT")
    return _available(equity[-1] / equity[0] - 1.0)


def _equity_days(replay: DecisionReplayResult) -> float:
    return (replay.sessions[-1] - replay.sessions[0]).total_seconds() / 86_400.0


def cagr(replay: DecisionReplayResult) -> MetricValue:
    equity = _equity(replay)
    if equity is None:
        return _unknown("INVALID_INPUT")
    days = _equity_days(replay)
    if len(equity) < 2 or days <= 0.0:
        return _unknown("INSUFFICIENT_DATA")
    ratio = equity[-1] / equity[0]
    return _available(ratio ** (365.25 / days) - 1.0)


def _annualized(mean: float, denominator: float) -> MetricValue:
    if denominator <= 0.0:
        return _unknown("NONPOSITIVE_DENOMINATOR")
    return _available(mean / denominator * math.sqrt(ANNUAL_SESSIONS))


def sharpe(replay: DecisionReplayResult) -> MetricValue:
    equity = _equity(replay)
    if equity is None:
        return _unknown("INVALID_INPUT")
    values = np.asarray(equity, dtype=float)
    returns = values[1:] / values[:-1] - 1.0
    if returns.size < 2:
        return _unknown("INSUFFICIENT_DATA")
    return _annualized(float(np.mean(returns)), float(np.std(returns, ddof=1)))


def sortino(replay: DecisionReplayResult) -> MetricValue:
    equity = _equity(replay)
    if equity is None:
        return _unknown("INVALID_INPUT")
    values = np.asarray(equity, dtype=float)
    returns = values[1:] / values[:-1] - 1.0
    if returns.size < 2:
        return _unknown("INSUFFICIENT_DATA")
    downside = np.minimum(returns, 0.0)
    return _annualized(float(np.mean(returns)), float(np.sqrt(np.mean(downside**2))))


def annualized_one_way_turnover(replay: DecisionReplayResult) -> MetricValue:
    equity = _equity(replay)
    if equity is None:
        return _unknown("INVALID_INPUT")
    days = _equity_days(replay)
    if len(equity) < 2 or days <= 0.0:
        return _unknown("INSUFFICIENT_DATA")
    mean_equity = float(np.mean(equity))
    if not math.isfinite(mean_equity) or mean_equity <= 0.0:
        return _unknown("INVALID_INPUT")
    turnover_rate = replay.total_turnover / mean_equity
    if not math.isfinite(turnover_rate) or turnover_rate < 0.0:
        return _unknown("INVALID_INPUT")
    return _available(turnover_rate * (ANNUAL_SESSIONS / days))


def rolling_12m_positive_fraction(replay: DecisionReplayResult) -> MetricValue:
    equity = _equity(replay)
    if equity is None:
        return _unknown("INVALID_INPUT")
    if len(equity) < ROLLING_12M_SESSIONS + 1:
        return _unknown("INSUFFICIENT_DATA")
    windows = len(equity) - ROLLING_12M_SESSIONS
    positive = 0
    for end in range(ROLLING_12M_SESSIONS, len(equity)):
        if equity[end] / equity[end - ROLLING_12M_SESSIONS] - 1.0 > 0.0:
            positive += 1
    return _available(positive / windows)


def exposure_invariant_passes(replay: DecisionReplayResult) -> bool:
    for state in replay.states:
        if not math.isfinite(state.realized_gross_exposure):
            return False
        if not 0.0 <= state.realized_gross_exposure <= 1.0 + 1e-12:
            return False
    return True


def max_drawdown(replay: DecisionReplayResult) -> MetricValue:
    equity = _equity(replay)
    if equity is None:
        return _unknown("INVALID_INPUT")
    drawdown, _ = drawdown_calmar(equity, initial_cash=replay.initial_cash, cagr=None)
    return drawdown


def calmar(replay: DecisionReplayResult) -> MetricValue:
    equity = _equity(replay)
    if equity is None:
        return _unknown("INVALID_INPUT")
    cagr_metric = cagr(replay)
    drawdown, calmar_metric = drawdown_calmar(
        equity,
        initial_cash=replay.initial_cash,
        cagr=cagr_metric.value if cagr_metric.status == "AVAILABLE" else None,
    )
    return calmar_metric


@dataclass(frozen=True)
class PerformanceSummary:
    """All Generation-2 decision-critical metrics for one replay."""

    total_return: MetricValue
    cagr: MetricValue
    sharpe: MetricValue
    sortino: MetricValue
    annualized_one_way_turnover: MetricValue
    rolling_12m_positive_fraction: MetricValue
    max_drawdown: MetricValue
    calmar: MetricValue
    exposure_invariant_passes: bool
    session_count: int


def summarize(replay: DecisionReplayResult) -> PerformanceSummary:
    return PerformanceSummary(
        total_return=total_return(replay),
        cagr=cagr(replay),
        sharpe=sharpe(replay),
        sortino=sortino(replay),
        annualized_one_way_turnover=annualized_one_way_turnover(replay),
        rolling_12m_positive_fraction=rolling_12m_positive_fraction(replay),
        max_drawdown=max_drawdown(replay),
        calmar=calmar(replay),
        exposure_invariant_passes=exposure_invariant_passes(replay),
        session_count=len(replay.close_equity),
    )
