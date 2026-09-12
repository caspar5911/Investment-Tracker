"""Provider-free Phase 4 readiness contracts."""

from .constants import ArtifactKind, PHASE2_CAMPAIGN_ID
from .hashing import (
    ArtifactIdentityError,
    artifact_identity,
    canonical_json_bytes,
    canonical_sha256,
    exact_file_sha256,
    normalize_repository_path,
    trial_identity,
)
from .models import AuthoritativeTrial, ReadinessArtifactIdentity
from .campaign import Phase4ReadinessOutcome, run_phase4_readiness
from .report import Phase4ReadinessSummary, render_readiness_report

__all__ = [
    "ArtifactIdentityError",
    "ArtifactKind",
    "AuthoritativeTrial",
    "PHASE2_CAMPAIGN_ID",
    "Phase4ReadinessOutcome",
    "Phase4ReadinessSummary",
    "ReadinessArtifactIdentity",
    "artifact_identity",
    "canonical_json_bytes",
    "canonical_sha256",
    "exact_file_sha256",
    "normalize_repository_path",
    "render_readiness_report",
    "run_phase4_readiness",
    "trial_identity",
]
