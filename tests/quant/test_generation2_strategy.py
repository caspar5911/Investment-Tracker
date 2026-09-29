"""Tests for the Generation-2 frozen family signal logic (C3, strategy.py).

These tests pin the frozen family definitions from
``2026-09-22-generation2-governance-preregistration.md``:

- G2-A: cross-sectional momentum + absolute-momentum eligibility,
  equal-weight top_k, all-cash when none eligible.
- G2-B: momentum ranking gated by a moving-average trend eligibility filter.
- G2-C: momentum ranking, inverse-volatility weights among the selected,
  gross normalized to 1.0; uncomputable/zero volatility drops to next rank.
- G2-D: equal-weight mean of trailing total returns over the frozen horizons;
  positive ensemble required.

All signals must read only completed information (no same-bar lookahead) and
rebalancing is anchored to the candidate's causal warm-up.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.generation2.grid import GridCandidate
from investment_tracker.quant.generation2.strategy import (
    StrategyError,
    build_targets,
)


def make_index(n: int, start: str = "2018-01-01") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n, tz="UTC")


def make_bars(closes: dict[str, list[float]], start: str = "2018-01-01") -> dict[str, pd.DataFrame]:
    n = len(next(iter(closes.values())))
    for symbol, values in closes.items():
        assert len(values) == n, f"{symbol} length mismatch"
    index = make_index(n, start)
    bars: dict[str, pd.DataFrame] = {}
    for symbol, values in closes.items():
        bars[symbol] = pd.DataFrame(
            {"open": list(values), "close": list(values)},
            index=index,
        )
    return bars


def cand_a(lookback: int, skip: int, top_k: int, rebalance: int) -> GridCandidate:
    return GridCandidate(
        candidate_id=f"G2-A|lookback={lookback}|skip={skip}|top_k={top_k}|rebalance={rebalance}",
        family="G2-A",
        lookback=lookback,
        skip=skip,
        top_k=top_k,
        rebalance=rebalance,
    )


# ---------------------------------------------------------------------------
# G2-A
# ---------------------------------------------------------------------------


def test_family_a_momentum_ranking_and_equal_weight_top_k() -> None:
    bars = make_bars(
        {
            "SPY": [100.0, 101.0, 101.0],
            "QQQ": [100.0, 105.0, 105.0],
            "TLT": [100.0, 99.0, 99.0],  # negative momentum -> ineligible
        }
    )
    targets = build_targets(cand_a(1, 0, 2, 1), bars)
    index = bars["SPY"].index
    assert len(targets) == 1
    target = targets[0]
    assert target.signal_session == index[1]
    assert target.due_session == index[2]
    assert target.weights == {"QQQ": 0.5, "SPY": 0.5}
    assert target.target_id == "G2-A|lookback=1|skip=0|top_k=2|rebalance=1#r000"


def test_family_a_none_eligible_stays_in_cash() -> None:
    bars = make_bars(
        {
            "SPY": [100.0, 99.0, 99.0],
            "QQQ": [100.0, 98.0, 98.0],
        }
    )
    targets = build_targets(cand_a(1, 0, 2, 1), bars)
    assert len(targets) == 1
    assert targets[0].weights == {}


def test_family_a_skip_uses_lagged_close() -> None:
    # lookback=2, skip=1 -> momentum at p is close[p-1] / close[p-2] - 1
    bars = make_bars(
        {
            "SPY": [100.0, 105.0, 105.0, 105.0],
            "QQQ": [100.0, 110.0, 110.0, 110.0],
        }
    )
    targets = build_targets(cand_a(2, 1, 1, 2), bars)
    assert len(targets) == 1
    assert targets[0].weights == {"QQQ": 1.0}


# ---------------------------------------------------------------------------
# G2-B
# ---------------------------------------------------------------------------


def _b_frames() -> dict[str, list[float]]:
    # 23 sessions; signal position p = 21 (max_lookback = 21).
    qqq = [100.0 - 5.0 * i / 17.0 for i in range(18)]  # idx 0..17: 100 -> 95
    qqq += [95.0, 95.0, 95.0, 96.0, 97.0]  # idx 18..22
    spy = [100.0 - 2.0 * i / 18.0 for i in range(19)]  # idx 0..18: 100 -> 98
    spy += [99.0, 98.0, 97.5]  # idx 19..21 (then idx 22)
    spy += [97.0]
    return {"QQQ": qqq, "SPY": spy, "TLT": [50.0] * 23}


def test_family_b_trend_filter_blocks_positive_momentum() -> None:
    bars = make_bars(_b_frames())
    candidate = GridCandidate(
        candidate_id="G2-B|lookback=3|trend_ma=3|top_k=2|rebalance=2",
        family="G2-B",
        lookback=3,
        skip=21,
        top_k=2,
        rebalance=2,
        trend_ma=3,
    )
    assert candidate.max_lookback == 21
    targets = build_targets(candidate, bars)
    index = bars["QQQ"].index
    assert len(targets) == 1
    target = targets[0]
    assert target.signal_session == index[21]
    assert target.due_session == index[22]
    # QQQ: momentum c0/c18 = 100/95 - 1 > 0 and close 97 > MA3(95,96,97)=96.
    # SPY: momentum c0/c18 = 100/98 - 1 > 0 but close 97.5 < MA3(99,98,97.5).
    # TLT: flat -> momentum 0, not positive.
    assert target.weights == {"QQQ": 1.0}


# ---------------------------------------------------------------------------
# G2-C
# ---------------------------------------------------------------------------


def _sample_std(values: list[float]) -> float:
    return float(np.std(np.asarray(values, dtype=float), ddof=1))


def _c_frames() -> dict[str, list[float]]:
    # 23 sessions; signal position p = 21.
    qqq = [110.0] + [101.0] * 16 + [100.0, 101.0, 100.0, 101.0, 100.0, 101.0]
    spy = [110.0] + [103.0] * 16 + [99.0, 103.0, 99.0, 103.0, 99.0, 103.0]
    tlt = [100.0] + [120.0] * 22
    return {"QQQ": qqq, "SPY": spy, "TLT": tlt}


def test_family_c_inverse_volatility_weights_sum_to_one() -> None:
    bars = make_bars(_c_frames())
    candidate = GridCandidate(
        candidate_id="G2-C|lookback=3|vol_lookback=5|top_k=2|rebalance=2",
        family="G2-C",
        lookback=3,
        skip=21,
        top_k=2,
        rebalance=2,
        vol_lookback=5,
    )
    targets = build_targets(candidate, bars)
    assert len(targets) == 1
    target = targets[0]
    # TLT has negative momentum and is ranked out.
    qqq_rets = [100.0 / 101.0 - 1.0, 101.0 / 100.0 - 1.0, 100.0 / 101.0 - 1.0,
                101.0 / 100.0 - 1.0, 100.0 / 101.0 - 1.0]
    spy_rets = [99.0 / 103.0 - 1.0, 103.0 / 99.0 - 1.0, 99.0 / 103.0 - 1.0,
                103.0 / 99.0 - 1.0, 99.0 / 103.0 - 1.0]
    v_q = _sample_std(qqq_rets)
    v_s = _sample_std(spy_rets)
    expected_q = (1.0 / v_q) / ((1.0 / v_q) + (1.0 / v_s))
    expected_s = 1.0 - expected_q
    assert set(target.weights) == {"QQQ", "SPY"}
    assert target.weights["QQQ"] == pytest.approx(expected_q, rel=1e-12)
    assert target.weights["SPY"] == pytest.approx(expected_s, rel=1e-12)
    assert target.weights["QQQ"] > target.weights["SPY"]  # lower vol -> larger weight
    assert sum(target.weights.values()) == pytest.approx(1.0)


def test_family_c_uncomputable_vol_drops_to_next_rank() -> None:
    alpha = [120.0] + [100.0] * 16 + [99.0, 100.0, 99.0, 100.0, 99.0, 100.0]
    beta = [110.0] + [100.0] * 16 + [98.0, 100.0, 98.0, 100.0, 98.0, 100.0]
    gamma = [100.0] * 23  # flat: momentum 0, volatility std 0 -> dropped
    delta = [100.0] * 18 + [105.0, 104.0, 105.0, 104.0, 105.0]
    bars = make_bars({"ALPHA": alpha, "BETA": beta, "GAMMA": gamma, "DELTA": delta})
    candidate = GridCandidate(
        candidate_id="G2-C|lookback=3|vol_lookback=5|top_k=3|rebalance=2",
        family="G2-C",
        lookback=3,
        skip=21,
        top_k=3,
        rebalance=2,
        vol_lookback=5,
    )
    targets = build_targets(candidate, bars)
    assert len(targets) == 1
    target = targets[0]
    # Momentum ranking: ALPHA 20%, BETA 10%, GAMMA 0%, DELTA ~ -4.8%.
    # GAMMA has zero sample volatility and is dropped; DELTA fills slot 3.
    assert set(target.weights) == {"ALPHA", "BETA", "DELTA"}
    assert all(weight > 0.0 for weight in target.weights.values())
    assert sum(target.weights.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# G2-D
# ---------------------------------------------------------------------------


def cand_d(horizons: tuple[int, ...], skip: int, top_k: int, rebalance: int) -> GridCandidate:
    horizon = "+".join(str(h) for h in horizons)
    return GridCandidate(
        candidate_id=f"G2-D|horizons={horizon}|skip={skip}|top_k={top_k}|rebalance={rebalance}",
        family="G2-D",
        skip=skip,
        top_k=top_k,
        rebalance=rebalance,
        horizon_set=horizons,
    )


def test_family_d_ensemble_ranking() -> None:
    # At p=3: QQQ e = mean(100/98-1, 100/96-1) > SPY e = mean(101/100-1,
    # 101/98-1) > TLT e = mean(98/100-1, 98/104-1) < 0 (excluded).
    bars = make_bars(
        {
            "QQQ": [96.0, 100.0, 98.0, 100.0, 105.0],
            "SPY": [98.0, 100.0, 100.0, 101.0, 103.0],
            "TLT": [104.0, 102.0, 100.0, 98.0, 97.0],
        }
    )
    targets = build_targets(cand_d((1, 3), 0, 2, 1), bars)
    index = bars["QQQ"].index
    assert len(targets) == 1
    target = targets[0]
    assert target.signal_session == index[3]
    assert target.due_session == index[4]
    assert target.weights == {"QQQ": 0.5, "SPY": 0.5}


def test_family_d_negative_ensemble_stays_in_cash() -> None:
    bars = make_bars(
        {
            "QQQ": [100.0, 100.0, 100.0, 100.0, 99.0],
            "SPY": [100.0, 101.0, 100.0, 99.0, 98.0],
        }
    )
    targets = build_targets(cand_d((1, 3), 0, 2, 1), bars)
    assert len(targets) == 1
    assert targets[0].weights == {}


def test_family_d_skip_shifts_window_and_warmup_gap_is_all_cash() -> None:
    # skip=21 shifts the ensemble window to close[p-21] / close[p-21-h]; at
    # p = max_lookback = 21 the window reaches before the data start, so the
    # first scheduled signal must be all-cash (no lookahead, fail-closed).
    bars = make_bars({"QQQ": [100.0] * 23, "SPY": [100.0] * 23})
    targets = build_targets(cand_d((3,), 21, 1, 3), bars)
    assert len(targets) == 1
    index = bars["QQQ"].index
    assert targets[0].signal_session == index[21]
    assert targets[0].due_session == index[22]
    assert targets[0].weights == {}


# ---------------------------------------------------------------------------
# Scheduling and causality
# ---------------------------------------------------------------------------


def test_rebalance_schedule_anchors_to_warmup_and_steps_by_rebalance() -> None:
    bars = make_bars({"SPY": [100.0] * 7, "QQQ": [100.0] * 7})
    targets = build_targets(cand_a(1, 0, 1, 2), bars)
    index = bars["SPY"].index
    assert [t.due_session for t in targets] == [index[2], index[4], index[6]]
    assert [t.signal_session for t in targets] == [index[1], index[3], index[5]]


def test_insufficient_history_produces_no_targets() -> None:
    bars = make_bars({"SPY": [100.0, 101.0], "QQQ": [100.0, 100.5]})
    assert build_targets(cand_a(1, 0, 1, 1), bars) == ()


def test_signals_read_no_information_after_signal_session() -> None:
    def frames(qqq_late: float) -> dict[str, list[float]]:
        return {
            "SPY": [100.0, 101.0, 101.0, 101.0],
            "QQQ": [100.0, 105.0, 104.0, qqq_late],
        }

    before = build_targets(cand_a(1, 0, 2, 1), make_bars(frames(103.0)))
    after = build_targets(cand_a(1, 0, 2, 1), make_bars(frames(500.0)))
    assert [(t.signal_session, t.due_session, t.weights) for t in before] == [
        (t.signal_session, t.due_session, t.weights) for t in after
    ]


def test_due_window_filters_targets() -> None:
    bars = make_bars({"SPY": [100.0] * 8, "QQQ": [100.0] * 8})
    index = bars["SPY"].index
    candidate = cand_a(3, 0, 1, 3)  # max_lookback 3 -> due idx 4 and 7
    targets = build_targets(candidate, bars, due_from=index[4], due_until=index[6])
    assert [t.due_session for t in targets] == [index[4]]


def test_alignment_target_prepended_when_earlier_than_first_due() -> None:
    bars = make_bars({"SPY": [100.0] * 8, "QQQ": [100.0] * 8})
    index = bars["SPY"].index
    candidate = cand_a(3, 0, 1, 3)  # scheduled due idx 4 and 7
    targets = build_targets(candidate, bars, align_start=index[2])
    assert [t.due_session for t in targets] == [index[2], index[4], index[7]]
    assert targets[0].target_id == "G2-A|lookback=3|skip=0|top_k=1|rebalance=3#align000"
    assert targets[0].weights == {}
    assert targets[0].signal_session == index[1]


def test_no_alignment_target_when_not_earlier_than_first_due() -> None:
    bars = make_bars({"SPY": [100.0] * 8, "QQQ": [100.0] * 8})
    index = bars["SPY"].index
    candidate = cand_a(3, 0, 1, 3)
    assert len(build_targets(candidate, bars, align_start=index[4])) == 2
    assert len(build_targets(candidate, bars, align_start=index[7])) == 2


def test_alignment_target_missing_session_fails_closed() -> None:
    bars = make_bars({"SPY": [100.0] * 8, "QQQ": [100.0] * 8})
    with pytest.raises(StrategyError) as excinfo:
        build_targets(cand_a(3, 0, 1, 3), bars, align_start=pd.Timestamp("2030-01-01", tz="UTC"))
    assert excinfo.value.code == "STRATEGY_ALIGN_SESSION_MISSING"


def test_alignment_target_at_first_session_fails_closed() -> None:
    bars = make_bars({"SPY": [100.0] * 8, "QQQ": [100.0] * 8})
    index = bars["SPY"].index
    with pytest.raises(StrategyError) as excinfo:
        build_targets(cand_a(3, 0, 1, 3), bars, align_start=index[0])
    assert excinfo.value.code == "STRATEGY_ALIGN_SESSION_INSUFFICIENT"


def test_single_common_session_fails_closed() -> None:
    index = make_index(2)
    bars = {
        "SPY": pd.DataFrame(
            {"open": [100.0, 101.0], "close": [100.0, 101.0]}, index=index
        ),
        "QQQ": pd.DataFrame(
            {"open": [50.0], "close": [50.0]}, index=index[:1]
        ),
    }
    with pytest.raises(StrategyError) as excinfo:
        build_targets(cand_a(1, 0, 1, 1), bars)
    assert excinfo.value.code == "STRATEGY_SESSIONS_INSUFFICIENT"


def test_non_positive_close_fails_closed() -> None:
    bars = make_bars({"SPY": [100.0, 0.0, 101.0], "QQQ": [100.0, 100.0, 100.0]})
    with pytest.raises(StrategyError) as excinfo:
        build_targets(cand_a(1, 0, 1, 1), bars)
    assert excinfo.value.code == "STRATEGY_CLOSE_INVALID"
