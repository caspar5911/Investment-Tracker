from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal


SCORING_VERSION = "QUANT-SCORE-v1"


@dataclass(frozen=True)
class CandidateEvidence:
    validation_cagr: float | None
    sharpe: float | None
    sortino: float | None
    calmar: float | None
    benchmark_excess_return: float | None
    walk_forward_consistency: float | None
    parameter_stability: float | None
    turnover: float | None
    max_drawdown: float | None
    friction_sensitivity: float | None
    period_concentration: float | None
    out_of_sample_improved: bool
    robustness_deteriorated: bool


@dataclass(frozen=True)
class ScoreBreakdown:
    version: str
    status: Literal["RANKED", "UNRANKABLE"]
    total: float | None
    rewards: dict[str, float]
    penalties: dict[str, float]
    reasons: tuple[str, ...]


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


def score_candidate(evidence: CandidateEvidence) -> ScoreBreakdown:
    required = {
        name: getattr(evidence, name)
        for name in (
            "validation_cagr", "sharpe", "sortino", "calmar",
            "benchmark_excess_return", "walk_forward_consistency",
            "parameter_stability", "turnover", "max_drawdown",
            "friction_sensitivity", "period_concentration",
        )
    }
    missing = tuple(
        name for name, value in required.items()
        if value is None or not math.isfinite(float(value))
    )
    if missing:
        return ScoreBreakdown(SCORING_VERSION, "UNRANKABLE", None, {}, {}, missing)

    rewards = {
        "validation_cagr": 20.0 * _clip(float(evidence.validation_cagr) / 0.15),
        "sharpe": 15.0 * _clip(float(evidence.sharpe) / 1.5),
        "sortino": 10.0 * _clip(float(evidence.sortino) / 2.0),
        "calmar": 10.0 * _clip(float(evidence.calmar) / 1.5),
        "benchmark_excess_return": 15.0 * _clip(float(evidence.benchmark_excess_return) / 0.10),
        "walk_forward_consistency": 10.0 * _clip(float(evidence.walk_forward_consistency)),
        "parameter_stability": 10.0 * _clip(float(evidence.parameter_stability)),
        "friction_sensitivity": 10.0 * _clip(float(evidence.friction_sensitivity)),
    }
    penalties = {
        "drawdown": 20.0 * _clip((abs(float(evidence.max_drawdown)) - 0.15) / 0.35),
        "turnover": 10.0 * _clip((float(evidence.turnover) - 1.0) / 4.0),
        "period_concentration": 10.0 * _clip((float(evidence.period_concentration) - 0.50) / 0.50),
    }
    total = sum(rewards.values()) - sum(penalties.values())
    return ScoreBreakdown(SCORING_VERSION, "RANKED", round(total, 8), rewards, penalties, ())
