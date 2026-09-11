"""Candidate-v5 preregistration contract.

Candidate v5 is the one allowed research-to-qualification iteration after the
documented v1-v4 diagnosis. It changes one technical condition from Candidate
v3: ACCUMULATE requires price >= 1.05 * SMA200. No grid search, panel
substitution, or repeated v5 variants are authorized.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json

from .governance import LOCKED_HOLDOUT

CANDIDATE_V5="CANDIDATE-v5.0"
V5_VERSIONS={
    "tpc":"TPC-v1.2",
    "replay":"REPLAY-v2.1",
    "calc":"CALC-v2.0",
    "robust":"ROBUST-v2.0",
    "phase_b":"PHASEB-v4.0",
}
V5_VALIDATION_PANEL=("DIA","IJR","VTI","IWF","IWD","QUAL","MTUM","USMV")
V5_BENCHMARK="SPY"
V5_WARMUP_WINDOW=("2017-01-01","2017-12-31")
V5_PHASE_A_WINDOW=("2018-01-01","2023-12-31")
V5_PHASE_B_WINDOW=("2024-01-01","2025-09-07")


@dataclass(frozen=True)
class CandidateV5Preregistration:
    candidate_id:str
    versions:dict[str,str]
    hypothesis:str
    grid_search_allowed:bool
    prior_research_only:bool
    replay_changes:tuple[str,...]
    validation_panel:tuple[str,...]
    benchmark:str
    warmup_window:tuple[str,str]
    phase_a_window:tuple[str,str]
    phase_b_window:tuple[str,str]
    panel_substitution_after_history_access_allowed:bool
    repeated_v5_variants_allowed:bool
    prior_candidate_data_eligible_as_unseen:bool
    replacement_holdout_symbols:tuple[str,...]
    replacement_holdout_locked:bool
    created_at:datetime
    status:str
    preregistration_digest:str


def preregister_candidate_v5(*,created_at:datetime)->CandidateV5Preregistration:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("preregistration timestamp must be timezone-aware")
    payload={
        "candidate_id":CANDIDATE_V5,
        "versions":V5_VERSIONS,
        "hypothesis":(
            "Pullback entries are more reliable when the asset remains in a "
            "clear long-term uptrend, operationalized as close at least 5% "
            "above SMA200 at the completed signal close."
        ),
        "grid_search_allowed":False,
        "prior_research_only":True,
        "replay_changes":(
            "ACCUMULATE additionally requires asset_close >= 1.05 * asset_sma200",
        ),
        "validation_panel":V5_VALIDATION_PANEL,
        "benchmark":V5_BENCHMARK,
        "warmup_window":V5_WARMUP_WINDOW,
        "phase_a_window":V5_PHASE_A_WINDOW,
        "phase_b_window":V5_PHASE_B_WINDOW,
        "panel_substitution_after_history_access_allowed":False,
        "repeated_v5_variants_allowed":False,
        "prior_candidate_data_eligible_as_unseen":False,
        "replacement_holdout_symbols":tuple(sorted(LOCKED_HOLDOUT)),
        "replacement_holdout_locked":True,
        "created_at":created_at,
        "status":"PREREGISTERED_AWAITING_UNSEEN_PHASE_A",
    }
    digest=sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    return CandidateV5Preregistration(**payload,preregistration_digest=digest)


def verify_preregistration(record:CandidateV5Preregistration)->bool:
    payload=asdict(record)
    digest=payload.pop("preregistration_digest")
    expected=sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    return (
        digest==expected
        and record.versions==V5_VERSIONS
        and record.grid_search_allowed is False
        and record.prior_research_only is True
        and record.validation_panel==V5_VALIDATION_PANEL
        and record.panel_substitution_after_history_access_allowed is False
        and record.repeated_v5_variants_allowed is False
        and record.prior_candidate_data_eligible_as_unseen is False
        and record.replacement_holdout_locked is True
        and set(record.replacement_holdout_symbols)==set(LOCKED_HOLDOUT)
    )
