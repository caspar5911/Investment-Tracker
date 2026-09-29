"""Tests for the Generation-2 performance metric layer (C3, performance.py).

Expected values are hand-computed from the frozen semantics rather than
mirrored from the implementation:

- the equity series starts at the first due session;
- CAGR / annualized turnover annualize on 365.25 days / 252 sessions;
- Sharpe uses sample standard deviation (ddof=1) and sqrt(252);
- Sortino uses the RMS of negative returns as the denominator;
- rolling-12-month is unavailable when fewer than 253 equity observations
  exist (fail-closed INSUFFICIENT_DATA);
- MDD follows the DQ-030 convention with initial cash prepended;
- exposure invariant: every session's realized gross exposure in [0, 1].
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.generation2.accounting import (
    DECISION_ACCOUNTING_SCHEMA,
    DecisionReplayResult,
    DecisionState,
    DecisionTarget,
    replay_decision_targets,
)
from investment_tracker.quant.generation2.performance import (
    ANNUAL_SESSIONS,
    ROLLING_12M_SESSIONS,
    summarize,
)


def _index(n: int, start: str = "2018-01-01") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n, tz="UTC")


def _synthetic_bars() -> dict[str, pd.DataFrame]:
    index = _index(5)
    spy = pd.DataFrame({"open": [100.0] * 5, "close": [100.0] * 5}, index=index)
    qqq = pd.DataFrame(
        {"open": [100.0, 100.0, 105.0, 120.0, 114.0], "close": [100.0, 110.0, 105.0, 120.0, 114.0]},
        index=index,
    )
    return {"SPY": spy, "QQQ": qqq}


def _synthetic_replay(friction_bps: int = 0) -> DecisionReplayResult:
    bars = _synthetic_bars()
    index = bars["QQQ"].index
    target = DecisionTarget("CAND#r000", index[0], index[1], {"QQQ": 0.5})
    return replay_decision_targets(bars, [target], friction_bps=friction_bps, initial_cash=100_000.0)


def _fabricate(equity: list[float], exposures: list[float], sessions: int) -> DecisionReplayResult:
    index = _index(sessions + 1)
    states = tuple(
        DecisionState(index[i], 0.0, 0.0, equity[i], exposures[i], (), ())
        for i in range(sessions)
    )
    return DecisionReplayResult(
        DECISION_ACCOUNTING_SCHEMA,
        0,
        100_000.0,
        tuple(index[1 : sessions + 1]),
        states,
        (),
        0.0,
    )


# ---------------------------------------------------------------------------
# End-to-end on the synthetic replay (hand-computed)
# ---------------------------------------------------------------------------


def test_synthetic_replay_equity_and_metrics_match_hand_computation() -> None:
    replay = _synthetic_replay(friction_bps=0)
    # Buy 500 units of QQQ at open 100.0 on idx1; cash 50000; turnover 50000.
    assert replay.close_equity == (105_000.0, 102_500.0, 110_000.0, 107_000.0)
    assert replay.total_turnover == pytest.approx(50_000.0)

    ratio = 107_000.0 / 105_000.0
    equity_days = (replay.sessions[-1] - replay.sessions[0]).total_seconds() / 86_400.0
    assert equity_days == 3.0
    expected_total_return = ratio - 1.0
    expected_cagr = ratio ** (365.25 / equity_days) - 1.0

    returns = [102_500.0 / 105_000.0 - 1.0, 110_000.0 / 102_500.0 - 1.0, 107_000.0 / 110_000.0 - 1.0]
    expected_sharpe = (
        float(np.mean(returns)) / float(np.std(np.asarray(returns, float), ddof=1))
    ) * math.sqrt(252)
    downside = [min(r, 0.0) for r in returns]
    expected_sortino = (
        float(np.mean(returns)) / math.sqrt(float(np.mean([d**2 for d in downside])))
    ) * math.sqrt(252)
    mean_equity = (105_000.0 + 102_500.0 + 110_000.0 + 107_000.0) / 4.0
    expected_turnover = (50_000.0 / mean_equity) * (252.0 / equity_days)
    # DQ-030: prepend initial cash 100000; peak reaches 110000, then 107000.
    expected_mdd = (110_000.0 - 107_000.0) / 110_000.0
    expected_calmar = expected_cagr / expected_mdd

    summary = summarize(replay)
    assert summary.total_return.status == "AVAILABLE"
    assert summary.total_return.value == pytest.approx(expected_total_return, rel=1e-12)
    assert summary.cagr.status == "AVAILABLE"
    assert summary.cagr.value == pytest.approx(expected_cagr, rel=1e-12)
    assert summary.sharpe.status == "AVAILABLE"
    assert summary.sharpe.value == pytest.approx(expected_sharpe, rel=1e-12)
    assert summary.sortino.status == "AVAILABLE"
    assert summary.sortino.value == pytest.approx(expected_sortino, rel=1e-12)
    assert summary.annualized_one_way_turnover.status == "AVAILABLE"
    assert summary.annualized_one_way_turnover.value == pytest.approx(expected_turnover, rel=1e-12)
    assert summary.rolling_12m_positive_fraction.status == "UNKNOWN"
    assert summary.rolling_12m_positive_fraction.reason == "INSUFFICIENT_DATA"
    assert summary.max_drawdown.status == "AVAILABLE"
    assert summary.max_drawdown.value == pytest.approx(expected_mdd, rel=1e-12)
    assert summary.calmar.status == "AVAILABLE"
    assert summary.calmar.value == pytest.approx(expected_calmar, rel=1e-12)
    assert summary.exposure_invariant_passes is True
    assert summary.session_count == 4


def test_synthetic_replay_friction_3bps_reduces_equity() -> None:
    replay = _synthetic_replay(friction_bps=3)
    # Fee = 50000 * 0.0003 = 15.0 -> cash 49985.
    assert replay.close_equity[0] == pytest.approx(500.0 * 110.0 + 49_985.0, abs=1e-9)
    assert replay.close_equity[-1] == pytest.approx(500.0 * 114.0 + 49_985.0, abs=1e-9)
    assert replay.total_turnover == pytest.approx(50_000.0)
    summary = summarize(replay)
    assert summary.total_return.status == "AVAILABLE"
    assert summary.total_return.value == pytest.approx(106_985.0 / 104_985.0 - 1.0, rel=1e-12)


# ---------------------------------------------------------------------------
# Fail-closed edges (fabricated replays)
# ---------------------------------------------------------------------------


def test_single_session_replay_is_fail_closed_for_rates() -> None:
    replay = _fabricate([100_000.0], [0.5], 1)
    summary = summarize(replay)
    assert summary.total_return.status == "AVAILABLE"
    assert summary.total_return.value == 0.0
    for metric in (summary.cagr, summary.sharpe, summary.sortino, summary.annualized_one_way_turnover):
        assert metric.status == "UNKNOWN"
        assert metric.reason == "INSUFFICIENT_DATA"
    assert summary.rolling_12m_positive_fraction.status == "UNKNOWN"
    assert summary.max_drawdown.status == "AVAILABLE"
    assert summary.max_drawdown.value == 0.0
    # CAGR itself is unavailable -> Calmar fails closed as INVALID_INPUT.
    assert summary.calmar.status == "UNKNOWN"
    assert summary.calmar.reason == "INVALID_INPUT"
    assert summary.exposure_invariant_passes is True


def test_zero_drawdown_with_available_cagr_is_nonpositive_denominator() -> None:
    # Monotone equity: zero drawdown, CAGR available -> Calmar cannot divide.
    replay = _fabricate([100_000.0, 101_000.0, 102_000.0], [0.5, 0.5, 0.5], 3)
    summary = summarize(replay)
    assert summary.max_drawdown.status == "AVAILABLE"
    assert summary.max_drawdown.value == 0.0
    assert summary.cagr.status == "AVAILABLE"
    assert summary.calmar.status == "UNKNOWN"
    assert summary.calmar.reason == "NONPOSITIVE_DENOMINATOR"


def test_non_finite_equity_is_invalid_input_everywhere() -> None:
    replay = _fabricate([100_000.0, float("nan"), 101_000.0], [0.5, 0.5, 0.5], 3)
    summary = summarize(replay)
    for metric in (
        summary.total_return,
        summary.cagr,
        summary.sharpe,
        summary.sortino,
        summary.annualized_one_way_turnover,
        summary.rolling_12m_positive_fraction,
        summary.max_drawdown,
        summary.calmar,
    ):
        assert metric.status == "UNKNOWN"
        assert metric.reason == "INVALID_INPUT"


def test_exposure_beyond_one_fails_the_invariant() -> None:
    replay = _fabricate([100_000.0, 101_000.0], [0.5, 1.2], 2)
    summary = summarize(replay)
    assert summary.exposure_invariant_passes is False


def test_zero_return_series_sharpe_sortino_nonpositive_denominator() -> None:
    replay = _fabricate([100_000.0, 100_000.0, 100_000.0], [0.5, 0.5, 0.5], 3)
    summary = summarize(replay)
    assert summary.sharpe.status == "UNKNOWN"
    assert summary.sharpe.reason == "NONPOSITIVE_DENOMINATOR"
    assert summary.sortino.status == "UNKNOWN"
    assert summary.sortino.reason == "NONPOSITIVE_DENOMINATOR"


def test_rolling_12m_positive_fraction_on_sufficient_history() -> None:
    # 253 equity observations -> exactly one full 252-session window.
    equity = [100_000.0] + [101_000.0] * 252
    replay = _fabricate(equity, [0.5] * 253, 253)
    summary = summarize(replay)
    assert summary.rolling_12m_positive_fraction.status == "AVAILABLE"
    assert summary.rolling_12m_positive_fraction.value == pytest.approx(1.0)
    # Flip half of the 252 windows to negative 12-month returns.
    equity_half = [100_000.0] * 252 + [99_000.0]
    # t in 252..252: equity[252]/equity[0]-1 = 99/100-1 < 0 -> fraction 0.
    replay_half = _fabricate(equity_half, [0.5] * 253, 253)
    summary_half = summarize(replay_half)
    assert summary_half.rolling_12m_positive_fraction.status == "AVAILABLE"
    assert summary_half.rolling_12m_positive_fraction.value == pytest.approx(0.0)
    assert ROLLING_12M_SESSIONS == 252
    assert ANNUAL_SESSIONS == 252
