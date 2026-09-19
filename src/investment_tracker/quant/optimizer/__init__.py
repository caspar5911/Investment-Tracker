"""Bounded deterministic candidate research."""

from .candidate_generator import CandidateConfiguration, CandidateGenerator
from .scorer import CandidateEvidence, ScoreBreakdown, score_candidate
from .search import SearchBudget, SearchResult, run_search

__all__ = [
    "CandidateConfiguration",
    "CandidateEvidence",
    "CandidateGenerator",
    "ScoreBreakdown",
    "SearchBudget",
    "SearchResult",
    "run_search",
    "score_candidate",
]
