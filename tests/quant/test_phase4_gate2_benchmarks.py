from __future__ import annotations

from importlib import import_module
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.phase4.engine.market import MarketPanel
from investment_tracker.quant.phase4.engine.models import Gate2SealError

try:
    _benchmarks_module = import_module(
        "investment_tracker.quant.phase4.engine.benchmarks"
    )
    from investment_tracker.quant.phase4.engine.benchmarks import (
        cash_benchmark,
        equal_weight_buy_and_hold,
    )
    from investment_tracker.quant.phase4.engine.models import PortfolioReplay

    _BENCHMARKS_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as exc:
    _benchmarks_module = None
    cash_benchmark = None
    equal_weight_buy_and_hold = None
    PortfolioReplay = None
    _BENCHMARKS_IMPORT_ERROR = exc


def _sessions(start: str, *, periods: int) -> pd.DatetimeIndex:
    return pd.date_range(start, periods=periods, freq="D", tz="UTC")


def _scored(
    opens: dict[str, list[float]],
    closes: dict[str, list[float]],
    *,
    start: str = "2024-01-01",
) -> MarketPanel:
    symbols = tuple(sorted(opens))
    periods = len(next(iter(opens.values())))
    index = _sessions(start, periods=periods)
    open_frame = pd.DataFrame(
        {symbol: np.asarray(opens[symbol], dtype=np.float64) for symbol in symbols},
        index=index,
    )
    close_frame = pd.DataFrame(
        {symbol: np.asarray(closes[symbol], dtype=np.float64) for symbol in symbols},
        index=index,
    )
    return MarketPanel.from_frames(open_frame, close_frame, role="SCORED")


@pytest.fixture(autouse=True)
def require_benchmark_types(request: pytest.FixtureRequest) -> None:
    if (
        request.node.name != "test_benchmark_types_are_available"
        and _BENCHMARKS_IMPORT_ERROR is not None
    ):
        pytest.skip("benchmark types are not implemented yet")


def test_benchmark_types_are_available() -> None:
    assert _BENCHMARKS_IMPORT_ERROR is None
    assert inspect.isfunction(cash_benchmark)
    assert inspect.isfunction(equal_weight_buy_and_hold)
    assert inspect.isclass(PortfolioReplay)


def test_cash_benchmark_is_constant_initial_cash() -> None:
    scored = _scored(
        {"AAA": [10.0, 11.0, 12.0, 13.0], "BBB": [20.0, 19.0, 18.0, 17.0]},
        {"AAA": [10.5, 11.5, 12.5, 13.5], "BBB": [19.5, 18.5, 17.5, 16.5]},
    )

    replay = cash_benchmark(scored)

    assert isinstance(replay, PortfolioReplay)
    assert replay.candidate_id is None
    assert replay.binding_sha256 is None
    assert replay.friction_bps == 0
    assert replay.initial_cash == 100000.0
    assert replay.fills == ()
    assert replay.total_turnover == 0.0
    assert replay.close_equity == pytest.approx(
        (100000.0, 100000.0, 100000.0, 100000.0)
    )
    assert all(state.realized_gross_exposure == 0.0 for state in replay.states)
    assert all(state.units == () for state in replay.states)


def test_equal_weight_buy_and_hold_one_purchase_fill_per_symbol() -> None:
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 10.0, 11.0], "BBB": [20.0, 20.0, 22.0]},
        {"AAA": [10.0, 10.0, 11.0], "BBB": [20.0, 20.0, 22.0]},
    )

    replay = equal_weight_buy_and_hold(scored, friction_bps=0)

    assert replay.candidate_id is None
    assert len(replay.fills) == 2
    assert tuple(fill.fill_timestamp for fill in replay.fills) == (sessions[1], sessions[1])
    assert tuple(fill.symbol for fill in replay.fills) == ("AAA", "BBB")
    assert all(fill.fill_notional > 0.0 for fill in replay.fills)
    assert all(fill.signal_timestamp == sessions[0] for fill in replay.fills)
    by_symbol = {fill.symbol: fill.units_delta for fill in replay.fills}
    assert by_symbol["AAA"] == pytest.approx(50000.0 / 10.0)
    assert by_symbol["BBB"] == pytest.approx(50000.0 / 20.0)
    # No subsequent rebalance at the final open even as prices drift.
    assert not any(fill.fill_timestamp == sessions[2] for fill in replay.fills)
    assert replay.close_equity[0] == 100000.0
    assert replay.close_equity[-1] == pytest.approx(5000.0 * 11.0 + 2500.0 * 22.0)


def test_equal_weight_buy_and_hold_scales_single_purchase_under_friction() -> None:
    scored = _scored(
        {"AAA": [10.0, 10.0], "BBB": [20.0, 20.0]},
        {"AAA": [10.0, 10.0], "BBB": [20.0, 20.0]},
    )

    replay = equal_weight_buy_and_hold(scored, friction_bps=1000)

    assert len(replay.fills) == 2
    assert replay.states[-1].cash >= 0.0
    assert replay.states[-1].realized_gross_exposure <= 1.0
    buy_notional = sum(fill.fill_notional for fill in replay.fills)
    friction = sum(fill.friction for fill in replay.fills)
    assert buy_notional + friction <= 100000.0


def test_equal_weight_buy_and_hold_single_session_creates_no_fill() -> None:
    scored = _scored({"AAA": [10.0]}, {"AAA": [10.0]})

    replay = equal_weight_buy_and_hold(scored, friction_bps=0)

    assert replay.fills == ()
    assert replay.close_equity == pytest.approx((100000.0,))
    assert replay.total_turnover == 0.0


def test_benchmarks_reject_warmup_role_panel() -> None:
    sessions = _sessions("2024-01-01", periods=2)
    warmup = MarketPanel.from_frames(
        pd.DataFrame(
            np.array([[10.0], [12.0]]), index=sessions, columns=["AAA"]
        ),
        pd.DataFrame(
            np.array([[11.0], [13.0]]), index=sessions, columns=["AAA"]
        ),
        role="WARMUP",
    )

    with pytest.raises(Gate2SealError) as exc_info:
        cash_benchmark(warmup)
    assert exc_info.value.code == "ACCOUNTING_INVARIANT_FAILURE"
    with pytest.raises(Gate2SealError) as exc_info:
        equal_weight_buy_and_hold(warmup, friction_bps=0)
    assert exc_info.value.code == "ACCOUNTING_INVARIANT_FAILURE"


def test_benchmarks_reject_invalid_friction() -> None:
    scored = _scored({"AAA": [10.0, 10.0]}, {"AAA": [10.0, 10.0]})

    with pytest.raises(Gate2SealError) as exc_info:
        equal_weight_buy_and_hold(scored, friction_bps=-1)
    assert exc_info.value.code == "ACCOUNTING_INVARIANT_FAILURE"


def test_benchmarks_expose_no_filesystem_loader() -> None:
    assert not hasattr(_benchmarks_module, "load_market")
    assert not hasattr(_benchmarks_module, "load")
    assert "initial_cash" not in inspect.signature(cash_benchmark).parameters
    assert "initial_cash" not in inspect.signature(equal_weight_buy_and_hold).parameters
