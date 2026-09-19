from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from investment_tracker.quant.backtest.benchmark import buy_and_hold
from investment_tracker.quant.backtest.engine import run_backtest
from investment_tracker.quant.backtest.metrics import metrics_for_backtest
from investment_tracker.quant.backtest.models import ExecutionAssumptions
from investment_tracker.quant.strategies.base import StrategyDefinition
from investment_tracker.quant.validation.robustness import robustness_summary

from .scorer import CandidateEvidence


def evaluate_strategy(
    strategy: StrategyDefinition,
    validation_bars: pd.DataFrame,
    assumptions: ExecutionAssumptions,
    *,
    neighbor_returns: Sequence[float],
    friction_returns: Mapping[float, float],
    walk_forward_returns: Sequence[float],
) -> CandidateEvidence:
    result = run_backtest(validation_bars, strategy.targets(validation_bars), assumptions)
    metrics = metrics_for_backtest(result)
    benchmark = buy_and_hold(validation_bars, assumptions)
    benchmark_metrics = metrics_for_backtest(benchmark)
    robust = robustness_summary(
        base_validation_return=metrics.total_return,
        neighbor_returns=list(neighbor_returns),
        friction_returns=friction_returns,
        fold_returns=list(walk_forward_returns),
    )
    excess = metrics.total_return - benchmark_metrics.total_return
    return CandidateEvidence(
        validation_cagr=metrics.cagr,
        sharpe=metrics.sharpe,
        sortino=metrics.sortino,
        calmar=metrics.calmar,
        benchmark_excess_return=excess,
        walk_forward_consistency=robust.walk_forward_consistency,
        parameter_stability=robust.parameter_stability,
        turnover=metrics.turnover,
        max_drawdown=metrics.max_drawdown,
        friction_sensitivity=robust.friction_sensitivity,
        period_concentration=robust.period_concentration,
        out_of_sample_improved=excess > 0,
        robustness_deteriorated=robust.deteriorated,
    )
