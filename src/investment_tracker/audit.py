from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import Field, model_validator

from .models import StrictModel

REQUIRED_REPORTS = frozenset({
    "phase_matrix", "dq_run_ledger", "phase_a", "robustness", "independent_recompute",
    "candidate_freeze", "phase_b", "prospective", "portfolio_risk", "operations",
    "security", "adversarial", "readiness",
})


class ArtifactReference(StrictModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)


class AuditPackageManifest(StrictModel):
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    dependency_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_snapshot_digests: dict[str, str]
    reports: dict[str, ArtifactReference]
    unresolved_limitations: list[str] = Field(min_length=1)
    independent_audit_status: str
    real_money_human_approval_required: bool

    @model_validator(mode="after")
    def enforce_governance(self) -> "AuditPackageManifest":
        missing = REQUIRED_REPORTS - self.reports.keys()
        if missing:
            raise ValueError("missing audit reports: " + ", ".join(sorted(missing)))
        if not self.canonical_snapshot_digests:
            raise ValueError("canonical snapshot digests are required")
        if self.independent_audit_status not in {"PENDING", "APPROVED", "REJECTED"}:
            raise ValueError("invalid Independent Audit status")
        if self.real_money_human_approval_required is not True:
            raise ValueError("human approval must remain required")
        return self


def verify_artifact(root: Path, reference: ArtifactReference) -> bool:
    candidate = (root / reference.path).resolve()
    root = root.resolve()
    if root not in candidate.parents or candidate.is_symlink() or not candidate.is_file():
        return False
    return hashlib.sha256(candidate.read_bytes()).hexdigest() == reference.sha256

