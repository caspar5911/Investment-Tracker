from __future__ import annotations

import pandas as pd
import pytest

from investment_tracker.quant.generation2.accounting import (
    DECISION_ACCOUNTING_SCHEMA,
    DecisionError,
    DecisionTarget,
    DividendEvent,
    SplitEvent,
    replay_decision_targets,
)

N = 5
S = pd.date_range("2020-01-01", periods=N, freq="D")
T0, T1, T2, T3, T4 = S


def df(opens, closes, **extra) -> pd.DataFrame:
    data = {"open": list(opens), "close": list(closes)}
    data.update(extra)
    return pd.DataFrame(data, index=S)


def flat(price: float) -> pd.DataFrame:
    return df([price] * N, [price] * N)


def buy_target(weight: float = 1.0, due=T1, signal=T0, target_id="T1") -> DecisionTarget:
    return DecisionTarget(target_id, signal, due, {"A": weight})


def one_symbol(bars: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"A": bars}


def test_schema_version_and_simple_buy() -> None:
    result = replay_decision_targets(one_symbol(flat(100.0)), [buy_target()])
    assert result.schema_version == "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1"
    assert result.sessions == (T1, T2, T3, T4)
    state = result.states[0]
    assert state.close_equity == pytest.approx(100_000.0)
    assert state.cash == pytest.approx(0.0)
    assert state.realized_gross_exposure == pytest.approx(1.0)
    assert ("A", pytest.approx(1000.0)) in state.units
    assert state.pending_orders == ("T1",)
    fill = result.fills[0]
    assert fill.unadjusted_open == pytest.approx(100.0)
    assert fill.notional == pytest.approx(100_000.0)
    assert fill.source_target_id == "T1"
    assert result.close_equity == (100_000.0, 100_000.0, 100_000.0, 100_000.0)


def test_turnover_is_recorded() -> None:
    result = replay_decision_targets(one_symbol(flat(100.0)), [buy_target()])
    assert result.total_turnover == pytest.approx(100_000.0)


def test_equity_tracks_price_move() -> None:
    opens = [100.0, 100.0, 110.0, 120.0, 130.0]
    closes = [100.0, 100.0, 110.0, 120.0, 130.0]
    result = replay_decision_targets(one_symbol(df(opens, closes)), [buy_target()])
    assert result.close_equity[1] == pytest.approx(110_000.0)
    assert result.daily_returns[0] == pytest.approx(0.10)


def test_no_same_bar_target_rejected() -> None:
    target = DecisionTarget("T", T1, T1, {"A": 1.0})
    with pytest.raises(DecisionError, match="DECISION_NONCAUSAL_TARGET"):
        replay_decision_targets(one_symbol(flat(100.0)), [target])


def test_gross_weight_over_one_rejected() -> None:
    with pytest.raises(DecisionError, match="DECISION_GROSS_WEIGHT_INVALID"):
        replay_decision_targets(one_symbol(flat(100.0)), [buy_target(weight=1.2)])


def test_negative_weight_rejected() -> None:
    with pytest.raises(DecisionError, match="DECISION_TARGET_WEIGHT_INVALID"):
        replay_decision_targets(one_symbol(flat(100.0)), [buy_target(weight=-0.1)])


def test_trimming_reduces_shares_and_raises_cash() -> None:
    target1 = buy_target(1.0, due=T1, signal=T0, target_id="T1")
    target2 = DecisionTarget("T2", T1, T2, {"A": 0.5})
    result = replay_decision_targets(one_symbol(flat(100.0)), [target1, target2])
    state = result.states[1]  # session T2
    assert state.cash == pytest.approx(50_000.0)
    assert ("A", pytest.approx(500.0)) in state.units
    assert state.realized_gross_exposure == pytest.approx(0.5)


def test_split_doubles_share_count_continuously() -> None:
    opens = [100.0, 100.0, 50.0, 50.0, 50.0]
    closes = [100.0, 100.0, 50.0, 50.0, 50.0]
    split = SplitEvent("A", T2, 2.0, "SPLIT-2FOR1")
    result = replay_decision_targets(one_symbol(df(opens, closes)), [buy_target()], splits=[split])
    state = result.states[1]  # T2, after split
    assert ("A", pytest.approx(2000.0)) in state.units
    assert state.close_equity == pytest.approx(100_000.0)
    assert state.cash == pytest.approx(0.0)


def test_reverse_split_quarters_share_count_continuously() -> None:
    opens = [100.0, 100.0, 400.0, 400.0, 400.0]
    closes = [100.0, 100.0, 400.0, 400.0, 400.0]
    split = SplitEvent("A", T2, 0.25, "SPLIT-1FOR4")
    result = replay_decision_targets(one_symbol(df(opens, closes)), [buy_target()], splits=[split])
    state = result.states[1]
    assert ("A", pytest.approx(250.0)) in state.units
    assert state.close_equity == pytest.approx(100_000.0)


def test_dividend_receivable_created_at_ex_date() -> None:
    div = DividendEvent("A", ex_date=T2, pay_date=T4, amount_per_unit=1.0, source_identity="DIV-1")
    result = replay_decision_targets(one_symbol(flat(100.0)), [buy_target()], dividends=[div])
    state = result.states[1]  # T2
    assert state.receivable == pytest.approx(1000.0)
    assert state.cash == pytest.approx(0.0)
    assert state.close_equity == pytest.approx(101_000.0)


def test_dividend_credits_cash_at_pay_date() -> None:
    div = DividendEvent("A", ex_date=T2, pay_date=T3, amount_per_unit=1.0, source_identity="DIV-1")
    result = replay_decision_targets(one_symbol(flat(100.0)), [buy_target()], dividends=[div])
    state = result.states[2]  # T3, pay date
    assert state.cash == pytest.approx(1000.0)
    assert state.receivable == pytest.approx(0.0)
    assert state.close_equity == pytest.approx(101_000.0)


def test_friction_reduces_buy_and_never_breaches_cash() -> None:
    result = replay_decision_targets(
        one_symbol(flat(100.0)), [buy_target()], friction_bps=100
    )
    assert result.fills[0].friction > 0.0
    assert result.states[0].close_equity < 100_000.0
    assert all(state.cash >= -1e-9 for state in result.states)


def test_empty_target_sequence_rejected() -> None:
    with pytest.raises(DecisionError, match="DECISION_TARGET_SEQUENCE_EMPTY"):
        replay_decision_targets(one_symbol(flat(100.0)), [])


def test_duplicate_due_target_rejected() -> None:
    target1 = buy_target(target_id="A")
    target2 = DecisionTarget("B", T0, T1, {"A": 0.5})
    with pytest.raises(DecisionError, match="DECISION_DUPLICATE_DUE_TARGET"):
        replay_decision_targets(one_symbol(flat(100.0)), [target1, target2])


def test_execution_uses_unadjusted_price_not_adjusted_column() -> None:
    # An adjusted column exists but must NOT be used for execution.
    bars = flat(100.0).assign(adj_close=50.0)
    result = replay_decision_targets(one_symbol(bars), [buy_target()])
    assert result.fills[0].unadjusted_open == pytest.approx(100.0)
    assert result.fills[0].notional == pytest.approx(100_000.0)
