from __future__ import annotations

import math

import numpy as np
import pandas as pd

from investment_tracker.quant.phase4.engine.robustness import bootstrap_median_daily_return

from .accounting import ReplayResult
from .benchmark import BenchmarkResult
from .dataset import Phase5Dataset, raw_close_frame
from .signals import causal_regime_label


def _period_returns(equity: pd.Series, frequency: str) -> pd.Series:
    returns = equity.pct_change().dropna()
    labels = returns.index.tz_localize(None).to_period(frequency)
    return returns.groupby(labels).apply(lambda values: float(np.prod(1.0 + values.to_numpy(dtype=float)) - 1.0))


def _rolling(monthly: pd.Series, months: int) -> tuple[dict[str, object], ...]:
    if len(monthly) < months:
        return ()
    values = monthly.to_numpy(dtype=float)
    return tuple({"ending_month": str(monthly.index[end]), "return": float(np.prod(1.0 + values[end - months + 1:end + 1]) - 1.0)} for end in range(months - 1, len(values)))


def calculate_durability(dataset: Phase5Dataset, replay: ReplayResult, benchmark: BenchmarkResult) -> dict[str, object]:
    if replay.sessions != benchmark.sessions or replay.friction_bps != benchmark.friction_bps:
        raise ValueError("PHASE5_BENCHMARK_ALIGNMENT_MISMATCH")
    equity = np.asarray(replay.close_equity, dtype=float)
    bench = np.asarray(benchmark.close_equity, dtype=float)
    returns = equity[1:] / equity[:-1] - 1.0
    ratio = float(equity[-1] / equity[0])
    bench_ratio = float(bench[-1] / bench[0])
    elapsed_days = (replay.sessions[-1] - replay.sessions[0]).total_seconds() / 86400.0
    cagr = ratio ** (365.25 / elapsed_days) - 1.0
    sample_std = float(np.std(returns, ddof=1)) if len(returns) >= 2 else 0.0
    sharpe = None if sample_std <= 0.0 else float(np.mean(returns) / sample_std * math.sqrt(252.0))
    downside_rms = float(math.sqrt(float(np.mean(np.minimum(returns, 0.0) ** 2))))
    sortino = None if downside_rms <= 0.0 else float(np.mean(returns) / downside_rms * math.sqrt(252.0))
    mean_equity = float(np.mean(equity))
    turnover = (replay.total_turnover / mean_equity) * (252.0 / len(returns))
    series = pd.Series(equity, index=pd.DatetimeIndex(replay.sessions))
    monthly = _period_returns(series, "M")
    yearly = _period_returns(series, "Y")
    positive_months = monthly[monthly > 0.0]
    negative_months = monthly[monthly < 0.0]
    streak = longest = 0
    for value in monthly.to_numpy(dtype=float):
        if value < 0.0:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0
    positive_total = float(positive_months.sum())
    top_three = float(positive_months.nlargest(3).sum()) if not positive_months.empty else 0.0
    bootstrap = bootstrap_median_daily_return(tuple(float(value) for value in returns))
    raw_close = raw_close_frame(dataset)
    regime_returns = {"broad_negative_trend": [], "broad_positive_trend": [], "mixed_cross_asset": []}
    for session, value in zip(replay.sessions[1:], replay.daily_returns, strict=True):
        regime_returns[causal_regime_label(raw_close, dataset.actions.rehab, session)].append(value)
    regimes = {
        name: {
            "observations": len(values),
            "positive_percentage": None if not values else sum(value > 0.0 for value in values) / len(values),
            "compounded_return": None if not values else float(np.prod(1.0 + np.asarray(values, dtype=float)) - 1.0),
        }
        for name, values in regime_returns.items()
    }
    exposures = [state.realized_gross_exposure for state in replay.states]
    return {
        "schema_version": "PHASE5-DURABILITY-v1",
        "friction_bps": replay.friction_bps,
        "total_return": ratio - 1.0,
        "cagr": float(cagr),
        "sharpe": sharpe,
        "sortino": sortino,
        "benchmark_total_return": bench_ratio - 1.0,
        "benchmark_excess_return": ratio - bench_ratio,
        "annualized_one_way_turnover": float(turnover),
        "average_gross_exposure": float(np.mean(exposures)),
        "maximum_gross_exposure": float(max(exposures)),
        "all_session_exposures_valid": all(0.0 <= value <= 1.0 + 1e-12 for value in exposures),
        "calendar_month_returns": {str(key): float(value) for key, value in monthly.items()},
        "calendar_year_returns": {str(key): float(value) for key, value in yearly.items()},
        "positive_month_percentage": float((monthly > 0.0).mean()),
        "positive_year_percentage": float((yearly > 0.0).mean()),
        "average_winning_month": None if positive_months.empty else float(positive_months.mean()),
        "average_losing_month": None if negative_months.empty else float(negative_months.mean()),
        "worst_month": None if monthly.empty else float(monthly.min()),
        "worst_year": None if yearly.empty else float(yearly.min()),
        "longest_losing_month_sequence": int(longest),
        "rolling_12_month": _rolling(monthly, 12),
        "rolling_36_month": _rolling(monthly, 36),
        "rolling_60_month": _rolling(monthly, 60),
        "top_three_positive_month_return_concentration": None if positive_total <= 0.0 else top_three / positive_total,
        "bootstrap_lower_endpoint": bootstrap.percentile_05.value,
        "bootstrap_upper_endpoint": bootstrap.percentile_95.value,
        "regime_consistency": regimes,
        "max_drawdown": None,
        "max_drawdown_status": "UNKNOWN",
        "calmar": None,
        "calmar_status": "UNKNOWN",
        "dsr": None,
        "dsr_status": "UNKNOWN",
        "dsr_reason": "NOT_IMPLEMENTED",
        "pbo": None,
        "pbo_status": "UNKNOWN",
        "pbo_reason": "NOT_IMPLEMENTED",
        "recovery_characteristics": {"status": "UNKNOWN", "reason": "DQ-030_UNRESOLVED"},
    }
