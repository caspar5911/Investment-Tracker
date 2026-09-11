from decimal import Decimal

from investment_tracker.replay_v2 import (
    ReplayV2Inputs,
    SignalState,
    evaluate_replay_v2,
)


def base(**changes):
    values=dict(
        asset_close=Decimal("90"),
        asset_sma200=Decimal("80"),
        prior60_high=Decimal("100"),
        prior_close=Decimal("89"),
        asset_sma5=Decimal("89"),
        asset_ret20=Decimal("0.03"),
        spy_ret20=Decimal("0.02"),
        spy_close=Decimal("510"),
        spy_sma200=Decimal("500"),
    )
    values.update(changes)
    return ReplayV2Inputs(**values)


def test_accumulate_requires_market_confirmation_and_nonnegative_relative_strength():
    assert evaluate_replay_v2(base()).state == SignalState.ACCUMULATE
    assert evaluate_replay_v2(base(spy_close=Decimal("499"))).state == SignalState.WAIT
    assert evaluate_replay_v2(base(asset_ret20=Decimal("0.019"))).state == SignalState.WATCH


def test_v1_pullback_stabilization_chase_and_precedence_are_preserved():
    assert evaluate_replay_v2(base(asset_close=Decimal("97"))).state == SignalState.WATCH
    assert evaluate_replay_v2(base(prior_close=Decimal("91"))).state == SignalState.WATCH
    assert evaluate_replay_v2(
        base(asset_close=Decimal("99"), asset_ret20=Decimal("0.09"), spy_ret20=Decimal("0.01"))
    ).state == SignalState.WAIT
    assert evaluate_replay_v2(
        base(asset_close=Decimal("70"), asset_sma200=Decimal("80"), asset_ret20=Decimal("-0.11"))
    ).state == SignalState.TRIM_AVOID


def test_missing_required_input_abstains():
    assert evaluate_replay_v2(base(spy_sma200=None)).state == SignalState.ABSTAIN
