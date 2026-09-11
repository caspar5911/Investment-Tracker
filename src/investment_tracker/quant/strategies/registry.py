from __future__ import annotations

from collections.abc import Mapping

from .base import StrategyDefinition
from .momentum import MomentumStrategy
from .risk_managed import RiskManagedTrendStrategy
from .trend import TrendStrategy
from .trend_momentum import TrendMomentumStrategy


def build_strategy(family: str, parameters: Mapping[str, int | float]) -> StrategyDefinition:
    factories = {
        "trend": TrendStrategy,
        "momentum": MomentumStrategy,
        "trend_momentum": TrendMomentumStrategy,
        "risk_managed_trend": RiskManagedTrendStrategy,
    }
    try:
        factory = factories[family]
    except KeyError as exc:
        raise ValueError(f"unsupported strategy family: {family}") from exc
    return factory(**parameters)
