from __future__ import annotations

import math

import numpy as np

from investment_tracker.quant.phase4.engine.models import (
    Gate2SealError,
    MetricReason,
    MetricValue,
    PortfolioReplay,
    SupportedMetrics,
    UnavailableStatistics,
)


def _available(value: float) -> MetricValue:
    numeric = float(value)
    if not math.isfinite(numeric):
        return MetricValue(value=None, status="UNKNOWN", reason="INVALID_INPUT")
    return MetricValue(value=numeric, status="AVAILABLE", reason="OK")


def _unknown(reason: MetricReason) -> MetricValue:
    return MetricValue(value=None, status="UNKNOWN", reason=reason)


def _invalid_replay(replay: PortfolioReplay) -> bool:
    equity = np.asarray(replay.close_equity, dtype=np.float64)
    return (
        equity.size == 0
        or not bool(np.all(np.isfinite(equity)))
        or bool(np.any(equity <= 0.0))
    )


def calculate_metrics(
    replay: PortfolioReplay,
    benchmark: PortfolioReplay,
) -> SupportedMetrics:
    """Calculate only the supported Gate 2 close-equity statistics."""

    if not isinstance(replay, PortfolioReplay) or not isinstance(
        benchmark, PortfolioReplay
    ):
        raise Gate2SealError(
            "DURABILITY_EVIDENCE_INVALID", "metrics require two portfolio replays"
        )
    if (
        replay.sessions != benchmark.sessions
        or replay.friction_bps != benchmark.friction_bps
    ):
        raise Gate2SealError(
            "DURABILITY_EVIDENCE_INVALID",
            "benchmark sessions and friction must exactly match the candidate",
        )

    target_series = tuple(float(value) for value in replay.target_gross_exposure)
    realized_series = tuple(float(value) for value in replay.realized_gross_exposure)
    invalid = _invalid_replay(replay)
    benchmark_invalid = _invalid_replay(benchmark)
    equity = np.asarray(replay.close_equity, dtype=np.float64)
    benchmark_equity = np.asarray(benchmark.close_equity, dtype=np.float64)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        total_ratio = float(equity[-1] / equity[0]) if not invalid else float("nan")
        benchmark_ratio = (
            float(benchmark_equity[-1] / benchmark_equity[0])
            if not benchmark_invalid
            else float("nan")
        )

    if invalid:
        total_return = _unknown("INVALID_INPUT")
        cagr = _unknown("INVALID_INPUT")
        volatility = _unknown("INVALID_INPUT")
        sharpe = _unknown("INVALID_INPUT")
        sortino = _unknown("INVALID_INPUT")
    elif not math.isfinite(total_ratio):
        total_return = _unknown("INVALID_INPUT")
        cagr = _unknown("INVALID_INPUT")
        volatility = _unknown("INVALID_INPUT")
        sharpe = _unknown("INVALID_INPUT")
        sortino = _unknown("INVALID_INPUT")
    else:
        total_return = _available(total_ratio - 1.0)
        if len(equity) < 2:
            cagr = _unknown("INSUFFICIENT_DATA")
        else:
            elapsed_days = (
                replay.sessions[-1] - replay.sessions[0]
            ).total_seconds() / 86_400.0
            if elapsed_days <= 0.0:
                cagr = _unknown("NONPOSITIVE_DENOMINATOR")
            else:
                try:
                    cagr_value = total_ratio ** (365.25 / elapsed_days) - 1.0
                except OverflowError:
                    cagr_value = float("inf")
                cagr = (
                    _available(cagr_value)
                    if math.isfinite(cagr_value)
                    else _unknown("INVALID_INPUT")
                )

        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            returns = equity[1:] / equity[:-1] - 1.0
        if not bool(np.all(np.isfinite(returns))):
            volatility = _unknown("INVALID_INPUT")
            sharpe = _unknown("INVALID_INPUT")
            sortino = _unknown("INVALID_INPUT")
        elif len(returns) < 2:
            volatility = _unknown("INSUFFICIENT_DATA")
            sharpe = _unknown("INSUFFICIENT_DATA")
            sortino = _unknown("INSUFFICIENT_DATA")
        else:
            sample_std = float(np.std(returns, ddof=1))
            mean_return = float(np.mean(returns))
            if not math.isfinite(sample_std) or sample_std < 0.0:
                volatility = _unknown("INVALID_INPUT")
                sharpe = _unknown("INVALID_INPUT")
            elif sample_std == 0.0:
                volatility = _available(0.0)
                sharpe = _unknown("NONPOSITIVE_DENOMINATOR")
            else:
                volatility = _available(sample_std * math.sqrt(252.0))
                sharpe = _available(mean_return / sample_std * math.sqrt(252.0))
            downside_rms = float(
                math.sqrt(float(np.mean(np.minimum(returns, 0.0) ** 2)))
            )
            if downside_rms <= 0.0 or not math.isfinite(downside_rms):
                sortino = _unknown("NONPOSITIVE_DENOMINATOR")
            else:
                sortino = _available(mean_return / downside_rms * math.sqrt(252.0))

    if (
        invalid
        or benchmark_invalid
        or not math.isfinite(total_ratio)
        or not math.isfinite(benchmark_ratio)
    ):
        benchmark_excess = _unknown("INVALID_INPUT")
    else:
        benchmark_excess = _available(total_ratio - benchmark_ratio)

    turnover_value = float(replay.total_turnover)
    if not math.isfinite(turnover_value) or turnover_value < 0.0:
        total_turnover = _unknown("INVALID_INPUT")
        annualized_turnover = _unknown("INVALID_INPUT")
    else:
        total_turnover = _available(turnover_value)
        if invalid:
            annualized_turnover = _unknown("INVALID_INPUT")
        elif len(equity) < 2:
            annualized_turnover = _unknown("INSUFFICIENT_DATA")
        else:
            mean_equity = float(np.mean(equity))
            if mean_equity <= 0.0 or not math.isfinite(mean_equity):
                annualized_turnover = _unknown("NONPOSITIVE_DENOMINATOR")
            else:
                annualized_turnover = _available(
                    (turnover_value / mean_equity) * (252.0 / (len(equity) - 1))
                )

    exposure_valid = (
        len(target_series) == len(realized_series) == len(replay.states)
        and all(
            math.isfinite(value) and 0.0 <= value <= 1.0 + 1e-12
            for value in target_series
        )
        and all(
            math.isfinite(value) and 0.0 <= value <= 1.0 + 1e-12
            for value in realized_series
        )
    )
    if not exposure_valid or not replay.states:
        average_target = _unknown("INVALID_INPUT")
        average_realized = _unknown("INVALID_INPUT")
        time_in_market = _unknown("INVALID_INPUT")
        target_series = ()
        realized_series = ()
    else:
        average_target = _available(float(np.mean(target_series)))
        average_realized = _available(float(np.mean(realized_series)))
        time_in_market = _available(
            sum(value > 0.0 for value in realized_series) / len(realized_series)
        )

    return SupportedMetrics(
        candidate_id=replay.candidate_id,
        binding_sha256=replay.binding_sha256,
        total_return=total_return,
        cagr=cagr,
        annualized_volatility=volatility,
        sharpe=sharpe,
        sortino=sortino,
        benchmark_excess_return=benchmark_excess,
        total_one_way_turnover=total_turnover,
        annualized_one_way_turnover=annualized_turnover,
        average_target_gross_exposure=average_target,
        average_realized_gross_exposure=average_realized,
        time_in_market=time_in_market,
        target_gross_exposure_series=target_series,
        realized_gross_exposure_series=realized_series,
        unavailable_statistics=UnavailableStatistics(),
    )


__all__ = ("calculate_metrics",)
