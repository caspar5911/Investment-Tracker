from __future__ import annotations

from importlib import import_module
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.phase4.engine.market import MarketPanel

try:
    _execution_module = import_module("investment_tracker.quant.phase4.engine.execution")
    from investment_tracker.quant.phase4.engine.execution import replay_targets
    from investment_tracker.quant.phase4.engine.models import (
        Fill,
        Gate2SealError,
        PortfolioReplay,
        SessionState,
        TargetInstruction,
    )

    _EXECUTION_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as exc:
    _execution_module = None
    replay_targets = None
    Fill = None
    Gate2SealError = None
    PortfolioReplay = None
    SessionState = None
    TargetInstruction = None
    _EXECUTION_IMPORT_ERROR = exc


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def require_execution_types(request: pytest.FixtureRequest) -> None:
    if (
        request.node.name != "test_execution_types_are_available"
        and _EXECUTION_IMPORT_ERROR is not None
    ):
        pytest.skip("execution types are not implemented yet")


@pytest.fixture(scope="module")
def authority():
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )

    return load_gate2_authority(REPOSITORY_ROOT)


def _binding(authority) -> object:
    family = next(
        family
        for family in authority.family_definitions
        if family.family_semantic_name == "cross_sectional_absolute_momentum_rotation"
    )
    candidate = family.candidates[0]
    from investment_tracker.quant.phase4.engine.models import (
        FixedStrategyBinding,
    )

    return FixedStrategyBinding.from_authority(
        authority, candidate.candidate_id, "a" * 64
    )


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


def _target(
    binding: object,
    signal: pd.Timestamp,
    due: pd.Timestamp | None,
    weights: tuple[tuple[str, float], ...],
) -> object:
    return TargetInstruction(
        signal_timestamp=signal,
        due_session=due,
        weights=weights,
        binding=binding,
    )


def test_execution_types_are_available() -> None:
    assert _EXECUTION_IMPORT_ERROR is None
    assert inspect.isfunction(replay_targets)
    assert inspect.isclass(PortfolioReplay)
    assert inspect.isclass(SessionState)
    assert inspect.isclass(Fill)


def test_single_fill_at_next_open_marks_open_and_close(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 12.0, 15.0]},
        {"AAA": [11.0, 13.0, 16.0]},
    )
    pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))
    targets = [pending, None, None]

    replay = replay_targets(scored, targets, friction_bps=0)

    assert isinstance(replay, PortfolioReplay)
    assert replay.close_equity == pytest.approx(
        (100000.0, 100000.0 * 13.0 / 12.0, 100000.0 * 16.0 / 12.0)
    )
    assert len(replay.fills) == 1
    fill = replay.fills[0]
    assert isinstance(fill, Fill)
    assert fill.symbol == "AAA"
    assert fill.signal_timestamp == sessions[0]
    assert fill.fill_timestamp == sessions[1]
    assert fill.reference_open == 12.0
    assert fill.fill_notional == pytest.approx(100000.0)
    assert fill.units_delta == pytest.approx(100000.0 / 12.0)
    assert fill.friction == 0.0
    assert replay.total_turnover == pytest.approx(100000.0)


def test_first_scored_equity_equals_reset_initial_cash(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 12.0, 15.0]},
        {"AAA": [11.0, 13.0, 16.0]},
    )
    pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))

    replay = replay_targets(scored, [pending, None, None], friction_bps=0)

    assert replay.states[0].close_equity == 100000.0
    assert replay.states[0].open_equity == 100000.0
    assert replay.states[0].cash == 100000.0
    assert replay.states[0].units == ()
    assert replay.states[0].realized_gross_exposure == 0.0


def test_old_units_earn_close_to_next_open_new_units_earn_open_to_close(authority):
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 12.0, 15.0]},
        {"AAA": [11.0, 13.0, 16.0]},
    )
    pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))

    replay = replay_targets(scored, [pending, None, None], friction_bps=0)

    state1, state2 = replay.states[1], replay.states[2]
    units = dict(state1.units)["AAA"]
    # New units are marked at the S1 open (12) and then earn open-to-close (13).
    assert state1.open_equity == pytest.approx(100000.0)
    assert state1.close_equity == pytest.approx(units * 13.0)
    # Held units earn close-to-next-open from S1 close (13) to S2 open (15).
    assert state2.open_equity == pytest.approx(units * 15.0)
    assert state2.close_equity == pytest.approx(units * 16.0)


def test_final_session_signal_never_fills(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 12.0, 15.0]},
        {"AAA": [11.0, 13.0, 16.0]},
    )
    early = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))
    final = _target(binding, sessions[2], None, (("AAA", 1.0),))

    replay = replay_targets(scored, [early, None, final], friction_bps=0)

    assert len(replay.fills) == 1
    assert all(fill.fill_timestamp != sessions[2] for fill in replay.fills)
    assert replay.close_equity == pytest.approx(
        (100000.0, 100000.0 * 13.0 / 12.0, 100000.0 * 16.0 / 12.0)
    )


def test_sells_precede_buys_in_ascending_symbol_order(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 10.0, 10.0], "BBB": [20.0, 20.0, 20.0]},
        {"AAA": [10.0, 10.0, 10.0], "BBB": [20.0, 20.0, 20.0]},
    )
    to_aaa = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))
    to_bbb = _target(binding, sessions[1], sessions[2], (("BBB", 1.0),))

    replay = replay_targets(scored, [to_aaa, to_bbb, None], friction_bps=0)

    second_day = tuple(fill for fill in replay.fills if fill.fill_timestamp == sessions[2])
    assert tuple(fill.symbol for fill in second_day) == ("AAA", "BBB")
    assert second_day[0].fill_notional < 0.0
    assert second_day[1].fill_notional > 0.0
    assert all(fill.signal_timestamp < fill.fill_timestamp for fill in replay.fills)
    # Flat prices with no friction conserve equity exactly.
    assert replay.close_equity[-1] == pytest.approx(100000.0)


def test_reference_open_notional_drives_one_way_friction(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=2)
    scored = _scored(
        {"AAA": [10.0, 20.0]},
        {"AAA": [10.0, 30.0]},
    )
    pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))

    replay = replay_targets(scored, [pending, None], friction_bps=300)

    fill = replay.fills[0]
    assert fill.reference_open == 20.0
    # A 100% buy at 300 bps is proportionally scaled so notional + friction
    # cannot exceed available cash: notional = 100000 / (1 + 300 / 10000).
    expected_notional = 100000.0 / (1.0 + 300 / 10000.0)
    assert fill.fill_notional == pytest.approx(expected_notional)
    assert fill.friction == pytest.approx(expected_notional * 300 / 10000.0)
    assert replay.candidate_id is not None


def test_high_friction_scales_buys_proportionally_without_negative_cash(authority):
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=2)
    scored = _scored(
        {"AAA": [10.0, 10.0], "BBB": [20.0, 20.0]},
        {"AAA": [10.0, 10.0], "BBB": [20.0, 20.0]},
    )
    pending = _target(
        binding, sessions[0], sessions[1], (("AAA", 0.5), ("BBB", 0.5))
    )

    replay = replay_targets(scored, [pending, None], friction_bps=1000)

    assert len(replay.fills) == 2
    buy_notional = sum(fill.fill_notional for fill in replay.fills)
    friction = sum(fill.friction for fill in replay.fills)
    assert buy_notional + friction <= 100000.0
    assert replay.states[-1].cash >= 0.0
    assert replay.states[-1].realized_gross_exposure <= 1.0
    # Proportional scaling keeps the two equal targets in equal notional ratio.
    by_symbol = {fill.symbol: fill.fill_notional for fill in replay.fills}
    expected_scale = 1.0 / (1.0 + 1000 / 10000.0)
    assert by_symbol["AAA"] == pytest.approx(50000.0 * expected_scale)
    assert by_symbol["BBB"] == pytest.approx(50000.0 * expected_scale)


def test_increasing_friction_strictly_reduces_flat_price_equity(authority):
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 10.0, 10.0], "BBB": [20.0, 20.0, 20.0]},
        {"AAA": [10.0, 10.0, 10.0], "BBB": [20.0, 20.0, 20.0]},
    )
    to_aaa = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))
    to_bbb = _target(binding, sessions[1], sessions[2], (("BBB", 1.0),))
    targets = [to_aaa, to_bbb, None]

    finals = []
    for friction_bps in (0, 3, 25):
        replay = replay_targets(scored, targets, friction_bps=friction_bps)
        finals.append(replay.close_equity[-1])
    assert finals[0] == pytest.approx(100000.0)
    assert finals[0] > finals[1] > finals[2]


def test_unchanged_target_rebalances_drifted_open_holdings(authority):
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 10.0, 20.0]},
        {"AAA": [10.0, 10.0, 20.0]},
    )
    first = _target(binding, sessions[0], sessions[1], (("AAA", 0.5),))
    second = _target(binding, sessions[1], sessions[2], (("AAA", 0.5),))

    replay = replay_targets(scored, [first, second, None], friction_bps=0)

    assert len(replay.fills) == 2
    rebalance = replay.fills[1]
    assert rebalance.signal_timestamp == sessions[1]
    assert rebalance.fill_timestamp == sessions[2]
    assert rebalance.fill_notional < 0.0
    assert replay.states[2].realized_gross_exposure == pytest.approx(0.5)


def test_increased_target_buys_only_the_positive_trade_delta(authority):
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 10.0, 10.0]},
        {"AAA": [10.0, 10.0, 10.0]},
    )
    first = _target(binding, sessions[0], sessions[1], (("AAA", 0.25),))
    second = _target(binding, sessions[1], sessions[2], (("AAA", 0.5),))

    replay = replay_targets(scored, [first, second, None], friction_bps=0)

    assert [fill.fill_notional for fill in replay.fills] == pytest.approx(
        [25000.0, 25000.0]
    )
    assert replay.states[2].cash == pytest.approx(50000.0)
    assert replay.states[2].realized_gross_exposure == pytest.approx(0.5)


def test_last_target_intent_is_carried_between_signal_rebalances(authority):
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=4)
    scored = _scored(
        {"AAA": [10.0, 10.0, 10.0, 10.0]},
        {"AAA": [10.0, 10.0, 10.0, 10.0]},
    )
    first = _target(binding, sessions[0], sessions[1], (("AAA", 0.5),))

    replay = replay_targets(scored, [first, None, None, None], friction_bps=0)

    assert replay.target_gross_exposure == pytest.approx((0.5, 0.5, 0.5, 0.5))


def test_open_without_due_target_preserves_units_without_fill(authority):
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 10.0, 20.0]},
        {"AAA": [10.0, 10.0, 20.0]},
    )
    first = _target(binding, sessions[0], sessions[1], (("AAA", 0.5),))

    replay = replay_targets(scored, [first, None, None], friction_bps=0)

    assert len(replay.fills) == 1
    held_units = dict(replay.states[1].units)["AAA"]
    assert held_units == pytest.approx(5000.0)
    assert replay.states[2].open_equity == pytest.approx(50000.0 + held_units * 20.0)
    assert replay.states[2].close_equity == pytest.approx(50000.0 + held_units * 20.0)


def test_zero_delta_produces_no_fill_within_notional_tolerance(authority):
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 10.0, 10.0], "BBB": [20.0, 20.0, 20.0]},
        {"AAA": [10.0, 10.0, 10.0], "BBB": [20.0, 20.0, 20.0]},
    )
    first = _target(binding, sessions[0], sessions[1], (("AAA", 0.5), ("BBB", 0.5)))
    second = _target(
        binding, sessions[1], sessions[2], (("AAA", 0.5), ("BBB", 0.5))
    )

    replay = replay_targets(scored, [first, second, None], friction_bps=0)

    assert len(replay.fills) == 2
    assert all(
        fill.fill_timestamp == sessions[1] for fill in replay.fills
    )
    assert replay.close_equity == pytest.approx((100000.0, 100000.0, 100000.0))


def test_daily_returns_use_scored_close_equity_pct_change(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 12.0, 15.0]},
        {"AAA": [11.0, 13.0, 16.0]},
    )
    pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))

    replay = replay_targets(scored, [pending, None, None], friction_bps=0)

    series = pd.Series(replay.close_equity, index=sessions)
    expected = series.pct_change().dropna().tolist()
    assert len(replay.close_equity) - 1 == 2
    assert replay.daily_returns == pytest.approx(tuple(expected))


@pytest.mark.parametrize(
    ("case", "friction_bps"),
    [
        ("negative", -1),
        ("boolean", True),
    ],
)
def test_replay_rejects_invalid_friction(case: str, friction_bps: object, authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=1)
    scored = _scored({"AAA": [10.0]}, {"AAA": [10.0]})

    with pytest.raises(Gate2SealError) as exc_info:
        replay_targets(scored, [], friction_bps=friction_bps)  # type: ignore[arg-type]
    assert exc_info.value.code == "ACCOUNTING_INVARIANT_FAILURE"


def test_replay_rejects_misaligned_target_symbols(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=2)
    scored = _scored({"AAA": [10.0, 12.0]}, {"AAA": [11.0, 13.0]})
    foreign = _target(binding, sessions[0], sessions[1], (("ZZZ", 1.0),))

    with pytest.raises(Gate2SealError) as exc_info:
        replay_targets(scored, [foreign, None], friction_bps=0)
    assert exc_info.value.code == "ACCOUNTING_INVARIANT_FAILURE"


def test_replay_rejects_target_due_session_mismatch(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 12.0, 15.0]},
        {"AAA": [11.0, 13.0, 16.0]},
    )
    # Signal is on session 0 but claims to be due on session 2.
    skewed = _target(binding, sessions[0], sessions[2], (("AAA", 1.0),))

    with pytest.raises(Gate2SealError) as exc_info:
        replay_targets(scored, [skewed, None, None], friction_bps=0)
    assert exc_info.value.code == "ACCOUNTING_INVARIANT_FAILURE"


def test_replay_rejects_missing_due_session_before_final_close(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 10.0, 10.0]},
        {"AAA": [10.0, 10.0, 10.0]},
    )
    invalid = _target(binding, sessions[0], None, (("AAA", 0.5),))

    with pytest.raises(Gate2SealError) as exc_info:
        replay_targets(scored, [invalid, None, None], friction_bps=0)

    assert exc_info.value.code == "ACCOUNTING_INVARIANT_FAILURE"


def test_replay_rejects_warmup_role_panel(authority) -> None:
    binding = _binding(authority)
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
        replay_targets(warmup, [], friction_bps=0)
    assert exc_info.value.code == "ACCOUNTING_INVARIANT_FAILURE"


def test_replay_preserves_strategy_identity_on_replay(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=2)
    scored = _scored(
        {"AAA": [10.0, 12.0]},
        {"AAA": [11.0, 13.0]},
    )
    pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))

    replay = replay_targets(scored, [pending, None], friction_bps=3)

    assert replay.candidate_id == binding.candidate_id
    assert replay.binding_sha256 == binding.binding_sha256
    assert replay.friction_bps == 3
    assert replay.initial_cash == 100000.0
    assert all(state.binding == binding for state in replay.states)
    assert all(fill.binding == binding for fill in replay.fills)
