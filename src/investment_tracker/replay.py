from __future__ import annotations

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

ACCUMULATE = "ACCUMULATE"
WATCH = "WATCH"
WAIT = "WAIT"
TRIM_AVOID = "TRIM/AVOID"
ABSTAIN = "ABSTAIN"


def trend_gate(close: float, sma200: float | None) -> str:
    if sma200 is None:
        return UNKNOWN
    return PASS if close > sma200 else FAIL


def pullback_gate(close: float, prior60_high: float | None) -> str:
    if prior60_high is None or prior60_high <= 0:
        return UNKNOWN
    return PASS if 0.85 * prior60_high <= close <= 0.95 * prior60_high else FAIL


def stabilization_gate(close: float, prior_close: float | None, sma5: float | None) -> str:
    if prior_close is None or sma5 is None:
        return UNKNOWN
    return PASS if close > prior_close and close >= sma5 else FAIL


def relative_strength_gate(asset_ret20: float | None, spy_ret20: float | None) -> str:
    if asset_ret20 is None or spy_ret20 is None:
        return UNKNOWN
    return PASS if asset_ret20 >= spy_ret20 - 0.05 else FAIL


def chase_gate(close: float, prior60_high: float | None, ret20: float | None) -> str:
    if prior60_high is None or prior60_high <= 0 or ret20 is None:
        return UNKNOWN
    return FAIL if close >= 0.98 * prior60_high and ret20 >= 0.08 else PASS


def signal_state(
    trend: str,
    pullback: str,
    stabilization: str,
    relative_strength: str,
    chase: str,
    ret20: float | None,
) -> str:
    gates = (trend, pullback, stabilization, relative_strength, chase)
    if ret20 is None or UNKNOWN in gates:
        return ABSTAIN
    if trend == FAIL and ret20 < -0.10:
        return TRIM_AVOID
    if trend == FAIL or chase == FAIL:
        return WAIT
    if trend == PASS and any(gate == FAIL for gate in (pullback, stabilization, relative_strength)):
        return WATCH
    if all(gate == PASS for gate in gates):
        return ACCUMULATE
    return ABSTAIN


def is_episode_start(previous_state: str | None, current_state: str) -> bool:
    return current_state == ACCUMULATE and previous_state != ACCUMULATE
