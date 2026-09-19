import pandas as pd
import pytest

from investment_tracker.quant.phase5.accounting import replay_targets
from investment_tracker.quant.phase5.benchmark import build_benchmark
from investment_tracker.quant.phase5.dataset import (
    CorporateActionBook,
    DividendEvent,
    Phase5Dataset,
    SplitEvent,
)
from investment_tracker.quant.phase5.methodology import SYMBOLS
from investment_tracker.quant.phase5.signals import TargetDecision


def _dataset():
    sessions = tuple(pd.bdate_range("2020-01-02", periods=7, tz="UTC"))
    bars = {}
    for symbol in SYMBOLS:
        prices = [100.0] * 7
        if symbol == "GLD":
            prices[3:] = [50.0] * 4
        bars[symbol] = pd.DataFrame(
            {
                "open": prices,
                "high": prices,
                "low": prices,
                "close": prices,
                "volume": [1000.0] * 7,
            },
            index=pd.DatetimeIndex(sessions),
        )
    empty = {symbol: () for symbol in SYMBOLS}
    dividends = dict(empty)
    splits = dict(empty)
    dividends["GLD"] = (
        DividendEvent("GLD", sessions[2], sessions[4], 1.0, "USD"),
    )
    splits["GLD"] = (
        SplitEvent("GLD", sessions[3], 2.0),
    )
    return Phase5Dataset(
        bars=bars,
        common_sessions=sessions,
        actions=CorporateActionBook(
            rehab={symbol: () for symbol in SYMBOLS},
            dividends=dividends,
            splits=splits,
        ),
        provider_manifest_sha256="0" * 64,
        first_common_session=sessions[0].strftime("%Y-%m-%d"),
        last_common_session=sessions[-1].strftime("%Y-%m-%d"),
        common_history_years=1.0,
    )


def test_next_open_fill_dividend_receivable_paydate_and_split_continuity():
    dataset = _dataset()
    sessions = dataset.common_sessions
    target = TargetDecision(sessions[0], sessions[1], (("GLD", 1.0),))
    result = replay_targets(
        dataset,
        (target,),
        friction_bps=0,
        symbols=("GLD",),
        start_session=sessions[0],
    )
    assert result.fills[0].fill_session == sessions[1]
    assert result.fills[0].fill_session > result.fills[0].signal_session
    assert result.states[2].receivable == pytest.approx(1000.0)
    assert result.states[2].cash == pytest.approx(0.0)
    assert dict(result.states[3].units)["GLD"] == pytest.approx(2000.0)
    assert result.states[3].close_equity == pytest.approx(101000.0)
    assert result.states[4].receivable == pytest.approx(0.0)
    assert result.states[4].cash == pytest.approx(1000.0)
    assert all(state.realized_gross_exposure <= 1.0 + 1e-12 for state in result.states)


def test_benchmark_can_start_at_dq_boundary_without_resetting_frozen_clock():
    dataset = _dataset()
    sessions = dataset.common_sessions
    targets = (
        TargetDecision(
            pd.Timestamp("2019-12-30", tz="UTC"),
            pd.Timestamp("2019-12-31", tz="UTC"),
            (("QQQ", 1.0),),
        ),
        TargetDecision(sessions[0], sessions[1], (("QQQ", 1.0),)),
    )

    result = build_benchmark(
        dataset,
        targets,
        friction_bps=0,
        start_session=sessions[0],
    )

    assert result.sessions[0] == sessions[0]
    assert result.sessions[-1] == sessions[-1]
    assert result.total_turnover == pytest.approx(100000.0)
