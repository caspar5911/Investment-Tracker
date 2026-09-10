from __future__ import annotations

from pydantic import Field

from .models import StrictModel

WEIGHTS = {
    "phase_a": 20, "robustness": 15, "phase_b": 15, "prospective": 15,
    "portfolio_risk": 10, "reconciliation": 10, "operations": 10, "governance": 5,
}


class ReadinessEvidence(StrictModel):
    phase_a: int = Field(ge=0, le=20)
    robustness: int = Field(ge=0, le=15)
    phase_b: int = Field(ge=0, le=15)
    prospective: int = Field(ge=0, le=15)
    portfolio_risk: int = Field(ge=0, le=10)
    reconciliation: int = Field(ge=0, le=10)
    operations: int = Field(ge=0, le=10)
    governance: int = Field(ge=0, le=5)
    phase_a_complete: bool
    robustness_passed: bool
    phase_b_passed: bool
    prospective_gate_met: bool
    critical_controls_clear: bool
    independent_audit_approved: bool


class ReadinessResult(StrictModel):
    raw_score: int
    capped_score: int
    applied_cap: int | None
    label: str
    hard_gate_failures: list[str]


def score_readiness(evidence: ReadinessEvidence) -> ReadinessResult:
    raw = sum(evidence.model_dump()[key] for key in WEIGHTS)
    caps = []
    failures = []
    for field, cap in (("phase_a_complete", 69), ("robustness_passed", 74),
                       ("phase_b_passed", 79), ("prospective_gate_met", 84),
                       ("critical_controls_clear", 84)):
        if not getattr(evidence, field):
            caps.append(cap)
            failures.append(field)
    if not evidence.independent_audit_approved:
        failures.append("independent_audit_approved")
    cap = min(caps) if caps else None
    return ReadinessResult(raw_score=raw, capped_score=min(raw, cap) if cap else raw,
                           applied_cap=cap, label="NON_OFFICIAL_ENGINEERING_EVIDENCE_SCORE",
                           hard_gate_failures=failures)
