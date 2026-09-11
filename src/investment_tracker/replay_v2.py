"""REPLAY-v2.0 candidate rule, preregistered before v3 panel history access.

This is a single theory-driven hypothesis, not a threshold grid search.
REPLAY-v1.0 remains unchanged and its historical evidence is never rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

REPLAY_V2_VERSION = "REPLAY-v2.0"


class SignalState(StrEnum):
    ACCUMULATE = "ACCUMULATE"
    WATCH = "WATCH"
    WAIT = "WAIT"
    TRIM_AVOID = "TRIM/AVOID"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class ReplayV2Inputs:
    asset_close: Decimal | None
    asset_sma200: Decimal | None
    prior60_high: Decimal | None
    prior_close: Decimal | None
    asset_sma5: Decimal | None
    asset_ret20: Decimal | None
    spy_ret20: Decimal | None
    spy_close: Decimal | None
    spy_sma200: Decimal | None


@dataclass(frozen=True)
class ReplayV2Decision:
    version: str
    state: SignalState
    asset_trend_gate: bool | None
    market_regime_gate: bool | None
    pullback_gate: bool | None
    stabilization_gate: bool | None
    rs_gate: bool | None
    chase_gate: bool | None


def evaluate_replay_v2(inputs: ReplayV2Inputs) -> ReplayV2Decision:
    """Evaluate the preregistered v2 signal state.

    Relative-strength threshold is exactly zero: asset 20d return must be at
    least SPY 20d return. Market confirmation requires SPY close > SPY SMA200.
    Other REPLAY-v1.0 thresholds and precedence are preserved.
    """

    required = (
        inputs.asset_close,
        inputs.asset_sma200,
        inputs.prior60_high,
        inputs.prior_close,
        inputs.asset_sma5,
        inputs.asset_ret20,
        inputs.spy_ret20,
        inputs.spy_close,
        inputs.spy_sma200,
    )
    if any(value is None for value in required):
        return ReplayV2Decision(
            REPLAY_V2_VERSION,
            SignalState.ABSTAIN,
            None,
            None,
            None,
            None,
            None,
            None,
        )

    assert inputs.asset_close is not None
    assert inputs.asset_sma200 is not None
    assert inputs.prior60_high is not None
    assert inputs.prior_close is not None
    assert inputs.asset_sma5 is not None
    assert inputs.asset_ret20 is not None
    assert inputs.spy_ret20 is not None
    assert inputs.spy_close is not None
    assert inputs.spy_sma200 is not None

    asset_trend = inputs.asset_close > inputs.asset_sma200
    market_regime = inputs.spy_close > inputs.spy_sma200
    pullback = (
        inputs.asset_close >= Decimal("0.85") * inputs.prior60_high
        and inputs.asset_close <= Decimal("0.95") * inputs.prior60_high
    )
    stabilization = (
        inputs.asset_close > inputs.prior_close
        and inputs.asset_close >= inputs.asset_sma5
    )
    rs = inputs.asset_ret20 >= inputs.spy_ret20
    chase = not (
        inputs.asset_close >= Decimal("0.98") * inputs.prior60_high
        and inputs.asset_ret20 >= Decimal("0.08")
    )

    if not asset_trend and inputs.asset_ret20 < Decimal("-0.10"):
        state = SignalState.TRIM_AVOID
    elif not asset_trend or not market_regime or not chase:
        state = SignalState.WAIT
    elif not (pullback and stabilization and rs):
        state = SignalState.WATCH
    else:
        state = SignalState.ACCUMULATE

    return ReplayV2Decision(
        REPLAY_V2_VERSION,
        state,
        asset_trend,
        market_regime,
        pullback,
        stabilization,
        rs,
        chase,
    )
