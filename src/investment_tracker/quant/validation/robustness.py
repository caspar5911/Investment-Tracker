from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Mapping


@dataclass(frozen=True)
class RobustnessSummary:
    parameter_stability: float
    friction_sensitivity: float
    walk_forward_consistency: float
    period_concentration: float
    deteriorated: bool


def neighbor_parameters(
    family: str,
    parameters: Mapping[str, int | float],
) -> tuple[dict[str, int | float], ...]:
    base = dict(parameters)
    if family in {"trend", "trend_momentum"}:
        fast = int(base["fast_window"])
        slow = int(base["slow_window"])
        dimensions: dict[str, tuple[int | float, ...]] = {
            "fast_window": tuple(sorted({max(1, fast - 5), fast, fast + 5})),
            "slow_window": tuple(sorted({max(2, slow - 10), slow, slow + 10})),
        }
        if family == "trend_momentum":
            lookback = int(base["momentum_lookback"])
            dimensions["momentum_lookback"] = tuple(sorted({max(1, lookback - 21), lookback, lookback + 21}))
    elif family == "momentum":
        lookback = int(base["lookback"])
        dimensions = {"lookback": tuple(sorted({max(1, lookback - 21), lookback, lookback + 21}))}
    elif family == "risk_managed_trend":
        trend = int(base["trend_window"])
        volatility = int(base["volatility_window"])
        dimensions = {
            "trend_window": tuple(sorted({max(1, trend - 10), trend, trend + 10})),
            "volatility_window": tuple(sorted({max(2, volatility - 5), volatility, volatility + 5})),
        }
    else:
        raise ValueError(f"unsupported strategy family: {family}")

    keys = tuple(sorted(dimensions))
    neighbors: list[dict[str, int | float]] = []
    for values in product(*(dimensions[key] for key in keys)):
        candidate = {**base, **dict(zip(keys, values))}
        if candidate == base:
            continue
        if "fast_window" in candidate and candidate["fast_window"] >= candidate["slow_window"]:
            continue
        neighbors.append(candidate)
    return tuple(neighbors)


def friction_scenarios(base_bps: float) -> tuple[float, ...]:
    if base_bps < 0:
        raise ValueError("base friction must be non-negative")
    return tuple(sorted({0.0, float(base_bps), 25.0, 50.0}))


def robustness_summary(
    *,
    base_validation_return: float,
    neighbor_returns: list[float],
    friction_returns: Mapping[float, float],
    fold_returns: list[float],
) -> RobustnessSummary:
    if not neighbor_returns or not friction_returns or not fold_returns:
        raise ValueError("neighbor, friction and fold evidence are required")
    parameter_stability = sum(value > 0 for value in neighbor_returns) / len(neighbor_returns)
    ordered_costs = sorted(friction_returns)
    low_cost = friction_returns[ordered_costs[0]]
    high_cost = friction_returns[ordered_costs[-1]]
    friction_sensitivity = 0.0 if low_cost <= 0 else max(0.0, min(1.0, high_cost / low_cost))
    walk_forward_consistency = sum(value > 0 for value in fold_returns) / len(fold_returns)
    net_fold_return = sum(fold_returns)
    period_concentration = 1.0 if net_fold_return <= 0 else max(fold_returns) / net_fold_return
    period_concentration = max(0.0, min(1.0, period_concentration))
    deteriorated = (
        base_validation_return <= 0
        or parameter_stability < 0.5
        or friction_sensitivity <= 0
        or walk_forward_consistency < 0.5
        or period_concentration > 0.75
    )
    return RobustnessSummary(
        parameter_stability=parameter_stability,
        friction_sensitivity=friction_sensitivity,
        walk_forward_consistency=walk_forward_consistency,
        period_concentration=period_concentration,
        deteriorated=deteriorated,
    )
