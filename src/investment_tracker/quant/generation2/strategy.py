"""Generation-2 frozen family signal logic (C3).

Implements the four frozen Generation-2 strategy families
(``2026-09-22-generation2-governance-preregistration.md``) on top of the
Phase-2 daily-bar frames. Every signal at session ``p`` reads only completed
information (indices strictly below ``p+1``); the target is *due* at session
``p+1`` and executed there by the decision ledger. Rebalancing is anchored to
the candidate's causal warm-up: the first signal position is
``candidate.max_lookback`` and subsequent signals step by ``rebalance``.

Family semantics (frozen):

- G2-A dual-momentum rotation: cross-sectional momentum score
  ``close[p-skip] / close[p-lookback] - 1``; an asset is eligible only if the
  score is strictly positive (absolute-momentum filter); equal weight over the
  top ``top_k`` eligible assets; all-cash when none are eligible.
- G2-B trend-filtered momentum: same momentum score, plus a moving-average
  trend gate ``close[p] > MA(trend_ma)`` over the most recent ``trend_ma``
  closes ending at the signal session.
- G2-C volatility-scaled momentum: rank by momentum (no sign filter), then
  weight the selected assets by inverse sample volatility over the last
  ``vol_lookback`` daily returns, normalized so gross is 1.0. An asset whose
  volatility is uncomputable or non-positive drops and the next-ranked asset
  fills the slot.
- G2-D multi-horizon ensemble: score is the equal-weight arithmetic mean of
  ``close[p-skip] / close[p-skip-h] - 1`` over the frozen horizons; eligible
  only if the mean is strictly positive. When the frozen grid's
  ``max_lookback`` (max of skip and largest horizon) is smaller than
  ``skip + max_h``, the first scheduled signal is necessarily all-cash
  (fail-closed warm-up gap, no lookahead).

Determinism: ranking ties break on ascending symbol. All-cash targets carry
an empty weight mapping.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from investment_tracker.quant.generation2.accounting import DecisionTarget
from investment_tracker.quant.generation2.grid import GridCandidate

__all__ = ["StrategyError", "build_targets"]


class StrategyError(ValueError):
    """Fail-closed strategy error carrying a stable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _validate_frames(
    bars: dict[str, pd.DataFrame],
) -> dict[str, np.ndarray]:
    """Validate frames and return per-symbol close arrays on aligned session order."""
    if not bars:
        raise StrategyError(
            "STRATEGY_FRAMES_EMPTY",
            "at least one symbol frame is required",
        )
    index_sets: list[set] = []
    for symbol, frame in bars.items():
        if "close" not in frame.columns:
            raise StrategyError(
                "STRATEGY_FRAME_INVALID",
                f"frame for {symbol!r} lacks the close column",
            )
        closes = pd.Series(frame["close"].to_numpy(dtype=float))
        if not closes.notna().all():
            raise StrategyError(
                "STRATEGY_CLOSE_INVALID",
                f"frame for {symbol!r} has missing closes",
            )
        if not np.isfinite(closes.to_numpy(dtype=float)).all():
            raise StrategyError(
                "STRATEGY_CLOSE_INVALID",
                f"frame for {symbol!r} has non-finite closes",
            )
        if (closes <= 0.0).any():
            raise StrategyError(
                "STRATEGY_CLOSE_INVALID",
                f"frame for {symbol!r} has non-positive closes",
            )
        index_sets.append(set(frame.index))
    common = sorted(set.intersection(*index_sets))
    if len(common) < 2:
        raise StrategyError(
            "STRATEGY_SESSIONS_INSUFFICIENT",
            "fewer than two common sessions across symbol frames",
        )
    common_index = pd.DatetimeIndex(common)
    closes_by_symbol = {
        symbol: bars[symbol].loc[common_index, "close"].to_numpy(dtype=float)
        for symbol in bars
    }
    return closes_by_symbol


def _eligible_positions(candidate: GridCandidate, n_sessions: int) -> list[int]:
    """Scheduled signal positions: start at the causal warm-up, step by rebalance."""
    start = candidate.max_lookback
    if start + 1 >= n_sessions:
        return []
    positions: list[int] = []
    position = start
    while position + 1 < n_sessions:
        positions.append(position)
        position += candidate.rebalance
    return positions


def _score_a_b_c(candidate: GridCandidate, closes: np.ndarray, p: int) -> float | None:
    """Momentum score close[p-skip] / close[p-lookback] - 1 (frozen lookback)."""
    if p - candidate.lookback < 0 or p - candidate.skip < 0:
        return None
    return float(closes[p - candidate.skip] / closes[p - candidate.lookback] - 1.0)


def _trend_passes(candidate: GridCandidate, closes: np.ndarray, p: int) -> bool:
    window = candidate.trend_ma
    if p - window + 1 < 0:
        return False
    moving_average = float(np.mean(closes[p - window + 1 : p + 1]))
    return closes[p] > moving_average


def _volatility(candidate: GridCandidate, closes: np.ndarray, p: int) -> float | None:
    window = candidate.vol_lookback
    if p - window < 0:
        return None
    returns = np.diff(closes[p - window : p + 1]) / closes[p - window : p]
    if returns.size < 2:
        return None
    sample_std = float(np.std(returns, ddof=1))
    if not math.isfinite(sample_std) or sample_std <= 0.0:
        return None
    return sample_std


def _ensemble_score(
    candidate: GridCandidate, closes: np.ndarray, p: int
) -> float | None:
    if not candidate.horizon_set:
        return None
    if p - candidate.skip < 0:
        return None
    scores: list[float] = []
    for horizon in candidate.horizon_set:
        if horizon <= 0 or p - candidate.skip - horizon < 0:
            return None
        scores.append(float(closes[p - candidate.skip] / closes[p - candidate.skip - horizon] - 1.0))
    return float(np.mean(scores))


def _ranked(
    scores: dict[str, float | None]
) -> list[tuple[str, float]]:
    ranked = [(symbol, value) for symbol, value in scores.items() if value is not None]
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return ranked


def _select_weights_a_b_d(
    candidate: GridCandidate, ranked: list[tuple[str, float]]
) -> dict[str, float]:
    eligible = [symbol for symbol, value in ranked if value > 0.0][: candidate.top_k]
    if not eligible:
        return {}
    weight = 1.0 / len(eligible)
    return {symbol: weight for symbol in eligible}


def _select_weights_c(
    candidate: GridCandidate,
    closes_by_symbol: dict[str, np.ndarray],
    ranked: list[tuple[str, float]],
    p: int,
) -> dict[str, float]:
    selected: list[str] = []
    for symbol, _ in ranked:
        if len(selected) >= candidate.top_k:
            break
        volatility = _volatility(candidate, closes_by_symbol[symbol], p)
        if volatility is None:
            continue  # uncomputable/zero vol: drop, next-ranked fills the slot
        selected.append(symbol)
    if not selected:
        return {}
    inverse = {symbol: 1.0 / _volatility(candidate, closes_by_symbol[symbol], p) for symbol in selected}
    gross = sum(inverse.values())
    return {symbol: weight / gross for symbol, weight in inverse.items()}


def build_targets(
    candidate: GridCandidate,
    bars: dict[str, pd.DataFrame],
    *,
    due_from: pd.Timestamp | None = None,
    due_until: pd.Timestamp | None = None,
    align_start: pd.Timestamp | None = None,
) -> tuple[DecisionTarget, ...]:
    """Build the deterministic decision-target sequence for one candidate.

    - ``due_from`` / ``due_until``: optional inclusive due-session window used
      to slice a scheduled target sequence (e.g. the frozen VALIDATION span).
    - ``align_start``: optional all-cash alignment target prepended only when
      it precedes the first scheduled due session (or no target is scheduled);
      it guarantees the decision ledger starts at the first common session
      with causal warm-up intact.
    """
    closes_by_symbol = _validate_frames(bars)
    symbols = tuple(sorted(closes_by_symbol))
    sessions = tuple(
        sorted(set.intersection(*(set(frame.index) for frame in bars.values())))
    )
    n = len(sessions)

    scheduled: list[DecisionTarget] = []
    for position_index, p in enumerate(_eligible_positions(candidate, n)):
        if candidate.family == "G2-D":
            scores = {symbol: _ensemble_score(candidate, closes_by_symbol[symbol], p) for symbol in symbols}
            ranked = [(symbol, value) for symbol, value in scores.items() if value is not None]
            ranked.sort(key=lambda item: (-item[1], item[0]))
            weights = _select_weights_a_b_d(candidate, ranked)
        elif candidate.family in {"G2-A", "G2-B"}:
            raw = {symbol: _score_a_b_c(candidate, closes_by_symbol[symbol], p) for symbol in symbols}
            if candidate.family == "G2-B":
                raw = {
                    symbol: value
                    for symbol, value in raw.items()
                    if value is not None
                    and _trend_passes(candidate, closes_by_symbol[symbol], p)
                }
            ranked = _ranked(raw)
            weights = _select_weights_a_b_d(candidate, ranked)
        elif candidate.family == "G2-C":
            raw = {symbol: _score_a_b_c(candidate, closes_by_symbol[symbol], p) for symbol in symbols}
            ranked = _ranked(raw)
            weights = _select_weights_c(candidate, closes_by_symbol, ranked, p)
        else:
            raise StrategyError(
                "STRATEGY_FAMILY_UNKNOWN",
                f"unknown strategy family {candidate.family!r}",
            )
        scheduled.append(
            DecisionTarget(
                f"{candidate.candidate_id}#r{position_index:03d}",
                sessions[p],
                sessions[p + 1],
                dict(weights),
            )
        )

    if due_from is not None or due_until is not None:
        scheduled = [
            target
            for target in scheduled
            if (due_from is None or target.due_session >= due_from)
            and (due_until is None or target.due_session <= due_until)
        ]

    if align_start is not None:
        positions = {session: index for index, session in enumerate(sessions)}
        if align_start not in positions:
            raise StrategyError(
                "STRATEGY_ALIGN_SESSION_MISSING",
                "alignment session is not a common session",
            )
        align_index = positions[align_start]
        if align_index < 1:
            raise StrategyError(
                "STRATEGY_ALIGN_SESSION_INSUFFICIENT",
                "alignment session has no preceding signal session",
            )
        first_due = scheduled[0].due_session if scheduled else None
        if not scheduled or (first_due is not None and align_start < first_due):
            scheduled.insert(
                0,
                DecisionTarget(
                    f"{candidate.candidate_id}#align000",
                    sessions[align_index - 1],
                    sessions[align_index],
                    {},
                ),
            )

    return tuple(scheduled)
