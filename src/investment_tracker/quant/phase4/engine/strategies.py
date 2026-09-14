from __future__ import annotations

import math
from numbers import Integral
from typing import Callable, Final

import numpy as np
import pandas as pd

from investment_tracker.quant.phase4.engine.allocation import (
    capped_inverse_volatility,
    equal_weights,
    portfolio_volatility_scale,
)
from investment_tracker.quant.phase4.engine.market import ScoredMarketInput
from investment_tracker.quant.phase4.engine.models import (
    FixedStrategyBinding,
    Gate2Authority,
    Gate2SealError,
    TargetInstruction,
)


Weights = tuple[tuple[str, float], ...]
TargetAlgorithm = Callable[[FixedStrategyBinding, pd.DataFrame], Weights]


def _invariant_failure(message: str) -> Gate2SealError:
    return Gate2SealError("FIXED_STRATEGY_INVARIANT_FAILURE", message)


def _validated_binding(
    binding: FixedStrategyBinding, authority: Gate2Authority
) -> FixedStrategyBinding:
    if not isinstance(binding, FixedStrategyBinding):
        raise _invariant_failure("target generation requires a fixed strategy binding")
    if not isinstance(authority, Gate2Authority):
        raise _invariant_failure(
            "target generation requires the exact Gate 2 authority"
        )
    if binding.candidate_id not in {
        candidate.candidate_id for candidate in authority.grids.candidates
    }:
        raise _invariant_failure(
            "candidate is not a member of the sealed Gate 1 population"
        )
    try:
        reconstructed = FixedStrategyBinding.model_validate(binding.model_dump())
    except ValueError as exc:
        raise _invariant_failure("fixed strategy binding identity changed") from exc
    if reconstructed != binding:
        raise _invariant_failure("fixed strategy binding reconstruction mismatch")
    authoritative = FixedStrategyBinding.from_authority(
        authority,
        binding.candidate_id,
        binding.implementation_sha256,
    )
    if reconstructed != authoritative:
        raise _invariant_failure("fixed strategy binding differs from sealed authority")
    return reconstructed


def _trailing_returns(closes: pd.DataFrame, window: int) -> pd.DataFrame | None:
    if len(closes) < window + 1:
        return None
    values = closes.iloc[-(window + 1) :].to_numpy(dtype=np.float64, copy=True)
    returns = values[1:] / values[:-1] - 1.0
    return pd.DataFrame(returns, columns=closes.columns)


def _positive_trailing_scores(
    closes: pd.DataFrame, lookback_sessions: int
) -> dict[str, float]:
    if len(closes) < lookback_sessions + 1:
        return {}
    current = closes.iloc[-1]
    earlier = closes.iloc[-(lookback_sessions + 1)]
    scores = current / earlier - 1.0
    return {
        symbol: float(score)
        for symbol, score in scores.items()
        if math.isfinite(float(score)) and float(score) > 0.0
    }


def _cross_sectional_absolute_momentum(
    binding: FixedStrategyBinding, closes: pd.DataFrame
) -> Weights:
    parameters = binding.parameters_dict
    lookback = int(parameters["lookback_sessions"])
    skip = int(parameters["skip_sessions"])
    if len(closes) < lookback + skip + 1:
        return ()
    numerator = closes.iloc[-(skip + 1)]
    denominator = closes.iloc[-(lookback + skip + 1)]
    raw_scores = numerator / denominator - 1.0
    scores = {
        symbol: float(score)
        for symbol, score in raw_scores.items()
        if math.isfinite(float(score)) and float(score) > 0.0
    }
    ranked = sorted(scores, key=lambda symbol: (-scores[symbol], symbol))
    chosen = ranked[: int(parameters["top_k"])]
    return equal_weights(chosen)


def _diversified_time_series_momentum(
    binding: FixedStrategyBinding, closes: pd.DataFrame
) -> Weights:
    parameters = binding.parameters_dict
    scores = _positive_trailing_scores(closes, int(parameters["lookback_sessions"]))
    return_window = _trailing_returns(closes, int(parameters["volatility_window"]))
    if not scores or return_window is None:
        return ()
    volatilities = {
        symbol: float(return_window[symbol].std(ddof=1)) for symbol in sorted(scores)
    }
    return capped_inverse_volatility(
        volatilities,
        maximum_asset_weight=float(parameters["maximum_asset_weight"]),
    )


def _trend_filtered_equal_risk(
    binding: FixedStrategyBinding, closes: pd.DataFrame
) -> Weights:
    parameters = binding.parameters_dict
    trend_window = int(parameters["trend_window"])
    if len(closes) < trend_window:
        return ()
    trailing_mean = closes.iloc[-trend_window:].mean(axis=0)
    current = closes.iloc[-1]
    eligible = tuple(
        symbol
        for symbol in closes.columns
        if math.isfinite(float(trailing_mean[symbol]))
        and float(current[symbol]) > float(trailing_mean[symbol])
    )
    return_window = _trailing_returns(closes, int(parameters["volatility_window"]))
    if not eligible or return_window is None:
        return ()
    volatilities = {
        symbol: float(return_window[symbol].std(ddof=1)) for symbol in eligible
    }
    return capped_inverse_volatility(
        volatilities,
        maximum_asset_weight=float(parameters["maximum_asset_weight"]),
    )


def _volatility_managed_relative_momentum(
    binding: FixedStrategyBinding, closes: pd.DataFrame
) -> Weights:
    parameters = binding.parameters_dict
    scores = _positive_trailing_scores(closes, int(parameters["lookback_sessions"]))
    ranked = sorted(scores, key=lambda symbol: (-scores[symbol], symbol))
    chosen = tuple(ranked[: int(parameters["top_k"])])
    if not chosen:
        return ()
    return_window = _trailing_returns(closes, int(parameters["volatility_window"]))
    if return_window is None:
        return ()
    covariance = return_window.loc[:, list(chosen)].cov(ddof=1)
    return portfolio_volatility_scale(
        equal_weights(chosen),
        covariance,
        target_portfolio_volatility=float(parameters["target_portfolio_volatility"]),
    )


_TARGET_ALGORITHMS: Final[dict[str, TargetAlgorithm]] = {
    "cross_sectional_absolute_momentum_rotation": (_cross_sectional_absolute_momentum),
    "diversified_time_series_momentum": _diversified_time_series_momentum,
    "trend_filtered_equal_risk_allocation": _trend_filtered_equal_risk,
    "volatility_managed_relative_momentum": _volatility_managed_relative_momentum,
}


def generate_target(
    authority: Gate2Authority,
    binding: FixedStrategyBinding,
    market_input: ScoredMarketInput,
    scored_offset: int,
) -> TargetInstruction | None:
    """Generate one causal close target on a fixed sealed rebalance clock."""

    fixed_binding = _validated_binding(binding, authority)
    if not isinstance(market_input, ScoredMarketInput):
        raise _invariant_failure("target generation requires a scored market input")
    if (
        isinstance(scored_offset, bool)
        or not isinstance(scored_offset, Integral)
        or scored_offset < 0
        or scored_offset >= len(market_input.scored.sessions)
    ):
        raise _invariant_failure("scored offset is outside the scored panel")
    offset = int(scored_offset)
    parameters = fixed_binding.parameters_dict
    structural = fixed_binding.structural_parameters_dict
    rebalance_sessions = int(
        structural.get("rebalance_sessions", parameters.get("rebalance_sessions", 0))
    )
    if rebalance_sessions <= 0:
        raise _invariant_failure("sealed rebalance interval is unavailable")
    if offset % rebalance_sessions != 0:
        return None

    try:
        algorithm = _TARGET_ALGORITHMS[fixed_binding.family_semantic_name]
    except KeyError as exc:
        raise _invariant_failure("no implementation exists for sealed family") from exc
    combined = market_input.combined_close_history
    history_end = len(market_input.indicator_warmup.sessions) + offset
    causal_closes = combined.iloc[: history_end + 1].copy(deep=True)
    weights = algorithm(fixed_binding, causal_closes)
    signal_timestamp = market_input.scored.sessions[offset]
    due_session = (
        market_input.scored.sessions[offset + 1]
        if offset + 1 < len(market_input.scored.sessions)
        else None
    )
    try:
        return TargetInstruction(
            signal_timestamp=signal_timestamp,
            due_session=due_session,
            weights=weights,
            binding=fixed_binding,
        )
    except ValueError as exc:
        raise _invariant_failure(
            "generated target violates fixed strategy invariants"
        ) from exc


__all__ = ("generate_target",)
