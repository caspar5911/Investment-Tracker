from decimal import Decimal
from investment_tracker.replay_v2_1 import ReplayV21Inputs,SignalState,evaluate_replay_v2_1

def base(**kw):
    d=dict(asset_close=Decimal("90"),asset_sma200=Decimal("85"),prior60_high=Decimal("100"),prior_close=Decimal("89"),asset_sma5=Decimal("89"),asset_ret20=Decimal("0.03"),spy_ret20=Decimal("0.02"),spy_close=Decimal("510"),spy_sma200=Decimal("500"))
    d.update(kw); return ReplayV21Inputs(**d)

def test_accumulate_requires_five_percent_trend_cushion():
    assert evaluate_replay_v2_1(base()).state==SignalState.ACCUMULATE
    assert evaluate_replay_v2_1(base(asset_sma200=Decimal("86"))).state==SignalState.WATCH

def test_exact_five_percent_boundary_passes():
    assert evaluate_replay_v2_1(base(asset_close=Decimal("89.25"),asset_sma200=Decimal("85"),prior_close=Decimal("88"),asset_sma5=Decimal("88"),prior60_high=Decimal("99"))).trend_cushion_gate is True

def test_missing_input_abstains():
    assert evaluate_replay_v2_1(base(asset_sma200=None)).state==SignalState.ABSTAIN
