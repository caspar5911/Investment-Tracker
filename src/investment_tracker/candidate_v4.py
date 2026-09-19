"""Candidate-v4 preregistration contract.

Candidate v4 tests exactly one theory-driven change after v3: a portfolio-level
global opportunity selector/cooldown. It does not alter REPLAY-v2.0 per-asset
technical thresholds and does not authorize a parameter search.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json

from .governance import LOCKED_HOLDOUT

CANDIDATE_V4="CANDIDATE-v4.0"
V4_VERSIONS={
    "tpc":"TPC-v1.2",
    "replay":"REPLAY-v3.0",
    "calc":"CALC-v2.0",
    "robust":"ROBUST-v2.0",
    "phase_b":"PHASEB-v3.0",
}
V4_VALIDATION_PANEL=("QQQ","IWM","MDY","EFA","EEM","VNQ","RSP","IJH")
V4_BENCHMARK="SPY"
V4_WARMUP_WINDOW=("2017-01-01","2017-12-31")
V4_PHASE_A_WINDOW=("2018-01-01","2023-12-31")
V4_PHASE_B_WINDOW=("2024-01-01","2025-09-07")


@dataclass(frozen=True)
class CandidateV4Preregistration:
    candidate_id:str
    versions:dict[str,str]
    hypothesis:str
    grid_search_allowed:bool
    replay_v2_thresholds_changed:bool
    selector_rule:str
    cooldown_sessions:int
    validation_panel:tuple[str,...]
    benchmark:str
    warmup_window:tuple[str,str]
    phase_a_window:tuple[str,str]
    phase_b_window:tuple[str,str]
    panel_substitution_after_history_access_allowed:bool
    prior_candidate_data_eligible_as_unseen:bool
    replacement_holdout_symbols:tuple[str,...]
    replacement_holdout_locked:bool
    created_at:datetime
    status:str
    preregistration_digest:str


def preregister_candidate_v4(*,created_at:datetime)->CandidateV4Preregistration:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("preregistration timestamp must be timezone-aware")
    payload={
        "candidate_id":CANDIDATE_V4,
        "versions":V4_VERSIONS,
        "hypothesis":(
            "The apparent edge is weakened by correlated overlapping entries; "
            "portfolio quality improves when simultaneous/overlapping ACCUMULATE "
            "signals are treated as one opportunity and capital is allocated only "
            "to the strongest contemporaneous relative-strength candidate."
        ),
        "grid_search_allowed":False,
        "replay_v2_thresholds_changed":False,
        "selector_rule":(
            "Among same-session REPLAY-v2.0 ACCUMULATE candidates choose maximum "
            "asset_ret20-minus-SPY_ret20, lexical asset tie-break; after selection "
            "enforce 20 benchmark trading sessions before another global entry."
        ),
        "cooldown_sessions":20,
        "validation_panel":V4_VALIDATION_PANEL,
        "benchmark":V4_BENCHMARK,
        "warmup_window":V4_WARMUP_WINDOW,
        "phase_a_window":V4_PHASE_A_WINDOW,
        "phase_b_window":V4_PHASE_B_WINDOW,
        "panel_substitution_after_history_access_allowed":False,
        "prior_candidate_data_eligible_as_unseen":False,
        "replacement_holdout_symbols":tuple(sorted(LOCKED_HOLDOUT)),
        "replacement_holdout_locked":True,
        "created_at":created_at,
        "status":"PREREGISTERED_AWAITING_UNSEEN_PHASE_A",
    }
    digest=sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    return CandidateV4Preregistration(**payload,preregistration_digest=digest)


def verify_preregistration(record:CandidateV4Preregistration)->bool:
    payload=asdict(record)
    digest=payload.pop("preregistration_digest")
    expected=sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    return (
        digest==expected
        and record.versions==V4_VERSIONS
        and record.grid_search_allowed is False
        and record.replay_v2_thresholds_changed is False
        and record.cooldown_sessions==20
        and record.validation_panel==V4_VALIDATION_PANEL
        and record.panel_substitution_after_history_access_allowed is False
        and record.prior_candidate_data_eligible_as_unseen is False
        and record.replacement_holdout_locked is True
        and set(record.replacement_holdout_symbols)==set(LOCKED_HOLDOUT)
    )
