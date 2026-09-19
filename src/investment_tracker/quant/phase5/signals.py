from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from investment_tracker.quant.phase4.engine.strategies import _cross_sectional_absolute_momentum
from investment_tracker.quant.phase4.gate3.authorities import SYMBOLS as PHASE4_REGIME_SYMBOLS

from .dataset import RehabEvent
from .methodology import FIRST_SIGNAL_POSITION, REBALANCE_SESSIONS, SYMBOLS, frozen_binding


@dataclass(frozen=True)
class TargetDecision:
    signal_session: pd.Timestamp
    due_session: pd.Timestamp | None
    weights: tuple[tuple[str, float], ...]

    @property
    def selected_symbols(self) -> tuple[str, ...]:
        return tuple(symbol for symbol, weight in self.weights if weight > 0.0)


def causal_adjusted_history(raw_close: pd.DataFrame, rehab: dict[str, tuple[RehabEvent, ...]], as_of: pd.Timestamp) -> pd.DataFrame:
    if tuple(raw_close.columns) != SYMBOLS or as_of not in raw_close.index:
        raise ValueError("PHASE5_SIGNAL_INPUT_MISMATCH")
    history = raw_close.loc[:as_of].copy(deep=True)
    for symbol in SYMBOLS:
        values = history[symbol].astype(float).copy()
        for event in rehab[symbol]:
            if event.ex_date > as_of:
                break
            mask = history.index < event.ex_date
            values.loc[mask] = values.loc[mask] * event.forward_a + event.forward_b
        if not all(math.isfinite(float(value)) and float(value) > 0.0 for value in values):
            raise ValueError(f"PHASE5_CAUSAL_ADJUSTMENT_INVALID:{symbol}:{as_of.date()}")
        history[symbol] = values
    return history


def generate_targets(raw_close: pd.DataFrame, rehab: dict[str, tuple[RehabEvent, ...]]) -> tuple[TargetDecision, ...]:
    if tuple(raw_close.columns) != SYMBOLS:
        raise ValueError("PHASE5_SIGNAL_SYMBOL_ORDER_MISMATCH")
    sessions = tuple(raw_close.index)
    binding = frozen_binding()
    targets: list[TargetDecision] = []
    for position in range(FIRST_SIGNAL_POSITION, len(sessions), REBALANCE_SESSIONS):
        signal = sessions[position]
        adjusted = causal_adjusted_history(raw_close, rehab, signal)
        weights = _cross_sectional_absolute_momentum(binding, adjusted)
        due = sessions[position + 1] if position + 1 < len(sessions) else None
        targets.append(TargetDecision(signal, due, tuple(weights)))
    return tuple(targets)


def target_equivalence(generated: tuple[TargetDecision, ...], sealed: tuple[TargetDecision, ...]) -> dict[str, object]:
    generated_by_signal = {item.signal_session: item for item in generated}
    mismatches: list[dict[str, object]] = []
    compared = 0
    for expected in sealed:
        actual = generated_by_signal.get(expected.signal_session)
        if actual is None:
            mismatches.append({"signal_session": expected.signal_session.isoformat(), "reason": "SIGNAL_MISSING"})
            continue
        compared += 1
        if set(actual.selected_symbols) != set(expected.selected_symbols):
            mismatches.append({"signal_session": expected.signal_session.isoformat(), "expected": sorted(expected.selected_symbols), "actual": sorted(actual.selected_symbols)})
    return {"status": "MATCH" if not mismatches and compared == len(sealed) else "MISMATCH", "compared": compared, "expected": len(sealed), "mismatches": mismatches}


def causal_regime_label(raw_close: pd.DataFrame, rehab: dict[str, tuple[RehabEvent, ...]], session: pd.Timestamp) -> str:
    adjusted = causal_adjusted_history(raw_close, rehab, session)
    position = adjusted.index.get_loc(session)
    if not isinstance(position, int) or position < 127:
        raise ValueError("PHASE5_REGIME_HISTORY_INSUFFICIENT")
    positive = negative = 0
    for symbol in PHASE4_REGIME_SYMBOLS:
        numerator = float(adjusted.iloc[position - 1][symbol])
        denominator = float(adjusted.iloc[position - 127][symbol])
        value = numerator / denominator - 1.0
        if value > 0.0:
            positive += 1
        elif value < 0.0:
            negative += 1
    if positive >= 6:
        return "broad_positive_trend"
    if negative >= 6:
        return "broad_negative_trend"
    return "mixed_cross_asset"
