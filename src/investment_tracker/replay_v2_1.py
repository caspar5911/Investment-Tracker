"""REPLAY-v2.1 candidate rule.

REPLAY-v2.1 inherits Candidate-v3 REPLAY-v2.0 and adds one research-derived,
pre-registered requirement: an ACCUMULATE candidate must be at least 5% above
its own 200-session moving average. This is intended to avoid weak/choppy
uptrends near the long-term trend boundary.

The 5% cushion was selected from already-seen development data only. It must be
validated once on a new, frozen panel before any qualification claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

REPLAY_V2_1_VERSION="REPLAY-v2.1"
TREND_CUSHION=Decimal("0.05")


class SignalState(StrEnum):
    ACCUMULATE="ACCUMULATE"
    WATCH="WATCH"
    WAIT="WAIT"
    TRIM_AVOID="TRIM/AVOID"
    ABSTAIN="ABSTAIN"


@dataclass(frozen=True)
class ReplayV21Inputs:
    asset_close:Decimal|None
    asset_sma200:Decimal|None
    prior60_high:Decimal|None
    prior_close:Decimal|None
    asset_sma5:Decimal|None
    asset_ret20:Decimal|None
    spy_ret20:Decimal|None
    spy_close:Decimal|None
    spy_sma200:Decimal|None


@dataclass(frozen=True)
class ReplayV21Decision:
    version:str
    state:SignalState
    asset_trend_gate:bool|None
    trend_cushion_gate:bool|None
    market_regime_gate:bool|None
    pullback_gate:bool|None
    stabilization_gate:bool|None
    rs_gate:bool|None
    chase_gate:bool|None


def evaluate_replay_v2_1(inputs:ReplayV21Inputs)->ReplayV21Decision:
    required=(
        inputs.asset_close,inputs.asset_sma200,inputs.prior60_high,
        inputs.prior_close,inputs.asset_sma5,inputs.asset_ret20,
        inputs.spy_ret20,inputs.spy_close,inputs.spy_sma200,
    )
    if any(v is None for v in required):
        return ReplayV21Decision(
            REPLAY_V2_1_VERSION,SignalState.ABSTAIN,
            None,None,None,None,None,None,None,
        )

    ac=inputs.asset_close; sma200=inputs.asset_sma200; ph=inputs.prior60_high
    pc=inputs.prior_close; sma5=inputs.asset_sma5; ar20=inputs.asset_ret20
    sr20=inputs.spy_ret20; sc=inputs.spy_close; ss200=inputs.spy_sma200
    assert all(v is not None for v in (ac,sma200,ph,pc,sma5,ar20,sr20,sc,ss200))

    asset_trend=ac>sma200
    trend_cushion=ac>=sma200*(Decimal(1)+TREND_CUSHION)
    market_regime=sc>ss200
    pullback=ac>=Decimal("0.85")*ph and ac<=Decimal("0.95")*ph
    stabilization=ac>pc and ac>=sma5
    rs=ar20>=sr20
    chase=not (ac>=Decimal("0.98")*ph and ar20>=Decimal("0.08"))

    if not asset_trend and ar20<Decimal("-0.10"):
        state=SignalState.TRIM_AVOID
    elif not asset_trend or not market_regime or not chase:
        state=SignalState.WAIT
    elif not (trend_cushion and pullback and stabilization and rs):
        state=SignalState.WATCH
    else:
        state=SignalState.ACCUMULATE

    return ReplayV21Decision(
        REPLAY_V2_1_VERSION,state,asset_trend,trend_cushion,market_regime,
        pullback,stabilization,rs,chase,
    )
