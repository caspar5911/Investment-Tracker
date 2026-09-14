from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


_WEIGHT_TOLERANCE = 1e-12


def _validated_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    observed = tuple(symbols)
    if any(not isinstance(symbol, str) or not symbol for symbol in observed):
        raise ValueError("allocation symbols must be nonempty strings")
    if len(set(observed)) != len(observed):
        raise ValueError("allocation symbols must be unique")
    return tuple(sorted(observed))


def _canonical_weights(
    weights: Sequence[tuple[str, float]],
) -> tuple[tuple[str, float], ...]:
    symbols = _validated_symbols(tuple(symbol for symbol, _ in weights))
    by_symbol: dict[str, float] = {}
    for symbol, value in weights:
        if isinstance(value, bool):
            raise ValueError("allocation weights must be real numbers")
        try:
            weight = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("allocation weights must be real numbers") from exc
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError("allocation weights must be finite and nonnegative")
        by_symbol[symbol] = weight
    total = math.fsum(by_symbol.values())
    if total > 1.0 + _WEIGHT_TOLERANCE:
        raise ValueError("allocation gross exposure exceeds one")
    if total > 1.0:
        by_symbol = {symbol: weight / total for symbol, weight in by_symbol.items()}
    result = tuple(
        (symbol, by_symbol[symbol]) for symbol in symbols if by_symbol[symbol] > 0.0
    )
    canonical_total = math.fsum(weight for _, weight in result)
    if canonical_total > 1.0 and result:
        symbol, weight = result[-1]
        result = (*result[:-1], (symbol, weight - (canonical_total - 1.0)))
    return result


def equal_weights(symbols: Sequence[str]) -> tuple[tuple[str, float], ...]:
    """Return deterministic equal risky weights, leaving an empty input as cash."""

    ordered = _validated_symbols(symbols)
    if not ordered:
        return ()
    weight = 1.0 / len(ordered)
    return _canonical_weights(tuple((symbol, weight) for symbol in ordered))


def capped_inverse_volatility(
    volatilities: Mapping[str, float],
    *,
    maximum_asset_weight: float,
) -> tuple[tuple[str, float], ...]:
    """Allocate by inverse volatility with deterministic iterative cap filling."""

    if not isinstance(volatilities, Mapping):
        raise ValueError("volatilities must be a mapping")
    ordered = _validated_symbols(tuple(volatilities))
    if isinstance(maximum_asset_weight, bool):
        raise ValueError("maximum asset weight must be finite and positive")
    cap = float(maximum_asset_weight)
    if not math.isfinite(cap) or cap <= 0.0 or cap > 1.0:
        raise ValueError("maximum asset weight must be in (0, 1]")

    inverse_scores: dict[str, float] = {}
    for symbol in ordered:
        value = volatilities[symbol]
        if isinstance(value, bool):
            raise ValueError("volatility estimates must be real numbers")
        try:
            volatility = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("volatility estimates must be real numbers") from exc
        if math.isfinite(volatility) and volatility > 0.0:
            inverse_scores[symbol] = 1.0 / volatility
    if not inverse_scores or any(
        not math.isfinite(score) or score <= 0.0 for score in inverse_scores.values()
    ):
        return ()

    target_mass = min(1.0, len(inverse_scores) * cap)
    remaining_mass = target_mass
    uncapped = list(inverse_scores)
    assigned: dict[str, float] = {}
    while uncapped:
        score_total = math.fsum(inverse_scores[symbol] for symbol in uncapped)
        proposed = {
            symbol: remaining_mass * inverse_scores[symbol] / score_total
            for symbol in uncapped
        }
        newly_capped = tuple(
            symbol for symbol in uncapped if proposed[symbol] > cap + _WEIGHT_TOLERANCE
        )
        if not newly_capped:
            for symbol in uncapped:
                assigned[symbol] = min(proposed[symbol], cap)
            break
        for symbol in newly_capped:
            assigned[symbol] = cap
            remaining_mass -= cap
        uncapped = [symbol for symbol in uncapped if symbol not in newly_capped]
        if remaining_mass <= _WEIGHT_TOLERANCE:
            break

    return _canonical_weights(tuple(assigned.items()))


def portfolio_volatility_scale(
    weights: Sequence[tuple[str, float]],
    covariance: pd.DataFrame,
    *,
    target_portfolio_volatility: float,
) -> tuple[tuple[str, float], ...]:
    """Scale fixed long-only weights to a finite positive annual volatility."""

    canonical = _canonical_weights(weights)
    if not canonical:
        return ()
    if isinstance(target_portfolio_volatility, bool):
        raise ValueError("target portfolio volatility must be a real number")
    target = float(target_portfolio_volatility)
    if not math.isfinite(target) or target < 0.0:
        raise ValueError("target portfolio volatility must be finite and nonnegative")
    if target == 0.0:
        return ()
    if not isinstance(covariance, pd.DataFrame):
        raise ValueError("covariance must be a pandas DataFrame")

    symbols = tuple(symbol for symbol, _ in canonical)
    if (
        not covariance.index.is_unique
        or not covariance.columns.is_unique
        or set(covariance.index) != set(symbols)
        or set(covariance.columns) != set(symbols)
    ):
        raise ValueError("covariance labels must exactly match risky weights")
    try:
        matrix = covariance.loc[list(symbols), list(symbols)].to_numpy(
            dtype=np.float64, copy=True
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("covariance values must be binary64-compatible") from exc
    if matrix.shape != (len(symbols), len(symbols)):
        raise ValueError("covariance shape mismatch")
    if not bool(np.all(np.isfinite(matrix))):
        return ()
    if not bool(np.allclose(matrix, matrix.T, rtol=0.0, atol=_WEIGHT_TOLERANCE)):
        raise ValueError("covariance must be symmetric")

    vector = np.asarray([weight for _, weight in canonical], dtype=np.float64)
    variance = float(vector @ matrix @ vector)
    if not math.isfinite(variance) or variance <= 0.0:
        return ()
    annualized_volatility = math.sqrt(252.0 * variance)
    if not math.isfinite(annualized_volatility) or annualized_volatility <= 0.0:
        return ()
    scale = min(1.0, target / annualized_volatility)
    if not math.isfinite(scale) or scale <= 0.0:
        return ()
    return _canonical_weights(
        tuple((symbol, weight * scale) for symbol, weight in canonical)
    )


__all__ = (
    "capped_inverse_volatility",
    "equal_weights",
    "portfolio_volatility_scale",
)
