from __future__ import annotations

from typing import Literal


PHASE2_CAMPAIGN_ID = "PHASE2-CORRECTED-2010-2022-c33fb075"

ArtifactKind = Literal[
    "phase2_experiment",
    "phase3_universe_manifest",
    "phase3_dq_snapshot",
    "phase3_normalized_dataset",
    "bootstrap_input_vector",
    "bootstrap_audit",
    "trial_authority",
    "phase4_split_manifest",
    "phase4_campaign_configuration",
    "phase4_readiness_manifest",
    "phase4_readiness_report",
]
