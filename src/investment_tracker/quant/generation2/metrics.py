"""DQ-030 Generation-2 maximum drawdown and Calmar ratio.

Frozen semantics (2026-09-22-generation2-dq030-max-drawdown-resolution):
- the initial cash amount is prepended as observation 0;
- the running peak ``P_t = max(E_0..E_t)``;
- the maximum drawdown is the non-negative magnitude
  ``max_t(0, -(E_t / P_t - 1))``;
- any empty, non-finite, or non-positive input is ``UNKNOWN/INVALID_INPUT``;
- Calmar is ``CAGR / max_drawdown`` only when both are available and the
  drawdown is strictly positive; a zero drawdown yields
  ``UNKNOWN/NONPOSITIVE_DENOMINATOR``.

These functions return Phase-4 ``MetricValue`` objects so they slot into
``SupportedMetrics.max_drawdown`` / ``calmar`` without changing existing
Phase-4 behavior.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from investment_tracker.quant.phase4.engine.models import MetricValue

__all__ = [
    "calmar_from",
    "drawdown_calmar",
    "max_drawdown_from_equity",
]


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _unknown(reason: str, value: float | None = None) -> MetricValue:
    return MetricValue(value=value, status="UNKNOWN", reason=reason)


def _available(value: float) -> MetricValue:
    return MetricValue(value=float(value), status="AVAILABLE", reason="OK")


def max_drawdown_from_equity(equity: Sequence[float], *, initial_cash: float | None) -> MetricValue:
    """Maximum drawdown (non-negative magnitude) with initial cash prepended.

    ``equity`` is the ordered sequence of end-of-session close equities
    ``E_1..E_n``. The prepended initial cash is observation ``E_0``.
    """
    if not _is_finite_number(initial_cash) or float(initial_cash) <= 0.0:
        return _unknown("INVALID_INPUT")
    if not equity:
        return _unknown("INVALID_INPUT")
    values = [float(item) for item in equity]
    if any(not math.isfinite(v) or v <= 0.0 for v in values):
        return _unknown("INVALID_INPUT")

    series = [float(initial_cash)] + values
    peak = series[0]
    max_drawdown = 0.0
    for observation in series:
        peak = max(peak, observation)
        max_drawdown = max(max_drawdown, 0.0, -(observation / peak - 1.0))
    return _available(max_drawdown)


def calmar_from(cagr: float | None, max_drawdown: float | None) -> MetricValue:
    """Calmar ratio = CAGR / maximum drawdown.

    Returns ``UNKNOWN/NONPOSITIVE_DENOMINATOR`` when the drawdown is not
    strictly positive and ``UNKNOWN/INVALID_INPUT`` when either input is not a
    finite number. A negative CAGR with a positive drawdown is preserved
    (negative Calmar), never clipped.
    """
    if not _is_finite_number(max_drawdown) or not _is_finite_number(cagr):
        return _unknown("INVALID_INPUT")
    if float(max_drawdown) <= 0.0:
        return _unknown("NONPOSITIVE_DENOMINATOR")
    return _available(float(cagr) / float(max_drawdown))


def drawdown_calmar(
    equity: Sequence[float],
    *,
    initial_cash: float | None,
    cagr: float | None,
) -> tuple[MetricValue, MetricValue]:
    """Return the DQ-030 (max_drawdown, calmar) pair for an equity curve."""
    drawdown = max_drawdown_from_equity(equity, initial_cash=initial_cash)
    calmar = calmar_from(
        cagr,
        drawdown.value if drawdown.status == "AVAILABLE" else None,
    )
    return drawdown, calmar
