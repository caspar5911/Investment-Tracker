import pandas as pd

from investment_tracker.quant.phase5.dataset import RehabEvent
from investment_tracker.quant.phase5.methodology import SYMBOLS
from investment_tracker.quant.phase5.signals import causal_adjusted_history


def test_causal_signal_history_never_uses_future_rehab_event():
    index = pd.bdate_range("2020-01-01", periods=200, tz="UTC")
    frame = pd.DataFrame(
        {symbol: [100.0 + i for i in range(len(index))] for symbol in SYMBOLS},
        index=index,
    )
    future = index[180]
    rehab = {
        symbol: (
            RehabEvent(symbol, future, 1.0, -50.0, 50.0, None),
        )
        for symbol in SYMBOLS
    }
    as_of = index[170]
    adjusted = causal_adjusted_history(frame, rehab, as_of)
    pd.testing.assert_frame_equal(adjusted, frame.loc[:as_of])


def test_past_rehab_event_adjusts_only_pre_event_history():
    index = pd.bdate_range("2020-01-01", periods=20, tz="UTC")
    frame = pd.DataFrame({symbol: [100.0] * 20 for symbol in SYMBOLS}, index=index)
    event_date = index[10]
    rehab = {
        symbol: (RehabEvent(symbol, event_date, 1.0, -1.0, 1.0, None),)
        for symbol in SYMBOLS
    }
    adjusted = causal_adjusted_history(frame, rehab, index[-1])
    assert adjusted.loc[index[9], "SPY"] == 99.0
    assert adjusted.loc[index[10], "SPY"] == 100.0


def test_reference_session_equivalence_uses_sealed_dates_not_long_history_clock():
    from investment_tracker.quant.phase5.signals import (
        TargetDecision,
        generate_targets_for_reference_sessions,
    )

    index = pd.bdate_range("2018-01-02", periods=420, tz="UTC")
    frame = pd.DataFrame(
        {
            symbol: [100.0 + i * (1.0 + j / 100.0) for i in range(len(index))]
            for j, symbol in enumerate(SYMBOLS)
        },
        index=index,
    )
    rehab = {symbol: () for symbol in SYMBOLS}
    signal = index[300]
    due = index[301]
    reference = (TargetDecision(signal, due, ()),)
    generated = generate_targets_for_reference_sessions(frame, rehab, reference)
    assert generated[0].signal_session == signal
    assert generated[0].due_session == due
