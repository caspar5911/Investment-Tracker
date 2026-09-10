from __future__ import annotations

from dataclasses import dataclass

from .governance import LOCKED_HOLDOUT


@dataclass(frozen=True)
class LeakageEvidence:
    candidate_frozen_before_phase_b: bool
    phase_b_excluded_from_tuning: bool
    signals_use_completed_day_t_only: bool
    execution_is_t_plus_one_open: bool
    c22_warmup_only: bool
    original_contaminated_holdout_excluded: bool
    queried_symbols: frozenset[str]


@dataclass(frozen=True)
class LeakageAuditReport:
    passed: bool
    failures: tuple[str, ...]
    status: str


def audit_leakage(evidence: LeakageEvidence) -> LeakageAuditReport:
    failures = tuple(
        name for name in (
            "candidate_frozen_before_phase_b", "phase_b_excluded_from_tuning",
            "signals_use_completed_day_t_only", "execution_is_t_plus_one_open",
            "c22_warmup_only", "original_contaminated_holdout_excluded",
        ) if not getattr(evidence, name)
    )
    normalized = {symbol.strip().upper() for symbol in evidence.queried_symbols}
    exposed = sorted(normalized & LOCKED_HOLDOUT)
    if exposed:
        failures += ("locked_holdout_access:" + ",".join(exposed),)
    return LeakageAuditReport(
        passed=not failures,
        failures=failures,
        status="AUDIT_EVIDENCE_COMPLETE" if not failures else "BLOCKED_OR_CONTAMINATED",
    )
