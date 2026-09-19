"""Governed Phase 3 ETF universe data-quality research."""

from .artifacts import Phase3ArtifactStore
from .campaign import run_phase3_campaign
from .models import CampaignOutcome

__all__ = ["CampaignOutcome", "Phase3ArtifactStore", "run_phase3_campaign"]
