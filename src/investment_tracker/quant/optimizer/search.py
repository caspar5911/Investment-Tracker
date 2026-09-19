from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Final, Literal

from .candidate_generator import CandidateConfiguration, CandidateGenerator


SEARCH_POLICY_VERSION: Final = "SEARCH-POLICY-v2"


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate: CandidateConfiguration
    score: float | None
    out_of_sample_improved: bool
    robustness_deteriorated: bool


@dataclass(frozen=True)
class SearchBudget:
    max_candidates: int = 500
    patience: int = 50
    meaningful_improvement: float = 0.01

    def __post_init__(self) -> None:
        if not 1 <= self.max_candidates <= 500:
            raise ValueError("max_candidates must be in [1, 500]")
        if not 1 <= self.patience <= 50:
            raise ValueError("patience must be in [1, 50]")
        if self.meaningful_improvement < 0:
            raise ValueError("meaningful_improvement must be non-negative")


StopReason = Literal[
    "MAX_CANDIDATES",
    "NO_MEANINGFUL_IMPROVEMENT",
    "PERSISTENT_OOS_FAILURE",
    "EXHAUSTED",
]


@dataclass(frozen=True)
class SearchResult:
    evaluations: tuple[CandidateEvaluation, ...]
    best: CandidateEvaluation | None
    evaluated_count: int
    stop_reason: StopReason


def run_search(
    generator: CandidateGenerator,
    evaluator: Callable[[CandidateConfiguration], CandidateEvaluation],
    budget: SearchBudget,
) -> SearchResult:
    """Run one family search under consecutive-failure policies.

    PERSISTENT_OOS_FAILURE means exactly ``budget.patience`` consecutive
    candidates with ``out_of_sample_improved=False``. Any True observation
    resets that streak. Robustness deterioration rejects candidate eligibility
    but is never, by itself, a family stop.
    """
    evaluations: list[CandidateEvaluation] = []
    best: CandidateEvaluation | None = None
    stale = 0
    oos_stale = 0
    for candidate in generator:
        if len(evaluations) >= budget.max_candidates:
            return SearchResult(tuple(evaluations), best, len(evaluations), "MAX_CANDIDATES")
        evaluation = evaluator(candidate)
        evaluations.append(evaluation)

        if evaluation.out_of_sample_improved:
            oos_stale = 0
        else:
            oos_stale += 1
            if oos_stale >= budget.patience:
                return SearchResult(tuple(evaluations), best, len(evaluations), "PERSISTENT_OOS_FAILURE")

        improved = (
            not evaluation.robustness_deteriorated
            and evaluation.out_of_sample_improved
            and evaluation.score is not None
            and (best is None or best.score is None or evaluation.score > best.score + budget.meaningful_improvement)
        )
        if improved:
            best = evaluation
            stale = 0
        else:
            stale += 1
            if stale >= budget.patience:
                return SearchResult(tuple(evaluations), best, len(evaluations), "NO_MEANINGFUL_IMPROVEMENT")
    return SearchResult(tuple(evaluations), best, len(evaluations), "EXHAUSTED")
