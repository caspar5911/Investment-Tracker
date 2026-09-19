"""Candidate-v3 preregistration.

Candidate v3 makes exactly one strategy hypothesis change from REPLAY-v1.0:
market confirmation plus non-negative 20-day relative strength versus SPY.
No parameter grid search is authorized.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json

from .governance import LOCKED_HOLDOUT

CANDIDATE_V3 = "CANDIDATE-v3.0"
V3_VERSIONS = {
    "tpc": "TPC-v1.2",
    "replay": "REPLAY-v2.0",
    "calc": "CALC-v2.0",
    "robust": "ROBUST-v2.0",
    "phase_b": "PHASEB-v2.0",
}
V3_VALIDATION_PANEL = ("XLV", "XLP", "XLY", "XLF", "XLRE", "XBI", "XRT", "ITB")
V3_BENCHMARK = "SPY"
V3_WARMUP_WINDOW = ("2017-01-01", "2017-12-31")
V3_PHASE_A_WINDOW = ("2018-01-01", "2023-12-31")
V3_PHASE_B_WINDOW = ("2024-01-01", "2025-09-07")


@dataclass(frozen=True)
class CandidateV3Preregistration:
    candidate_id: str
    versions: dict[str, str]
    hypothesis: str
    grid_search_allowed: bool
    replay_changes: tuple[str, ...]
    inherited_unchanged_rules: str
    validation_panel: tuple[str, ...]
    benchmark: str
    warmup_window: tuple[str, str]
    phase_a_window: tuple[str, str]
    phase_b_window: tuple[str, str]
    panel_substitution_after_history_access_allowed: bool
    candidate_v1_v2_data_eligible_as_unseen: bool
    replacement_holdout_symbols: tuple[str, ...]
    replacement_holdout_locked: bool
    created_at: datetime
    status: str
    preregistration_digest: str


def preregister_candidate_v3(*, created_at: datetime) -> CandidateV3Preregistration:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("preregistration timestamp must be timezone-aware")

    payload = {
        "candidate_id": CANDIDATE_V3,
        "versions": V3_VERSIONS,
        "hypothesis": (
            "ACCUMULATE quality improves when the broad market is above its "
            "200-day average and asset 20-day return is at least SPY 20-day return"
        ),
        "grid_search_allowed": False,
        "replay_changes": (
            "SPY close must be strictly above SPY SMA200 or state cannot ACCUMULATE",
            "RS PASS requires asset_ret20 >= SPY_ret20 instead of allowing -5% lag",
        ),
        "inherited_unchanged_rules": (
            "asset SMA200 trend; 5%-15% pullback; stabilization; chase prevention; "
            "TRIM/WAIT/WATCH precedence; episode dedupe; t+1 execution; horizons; "
            "SPY/cash comparison; friction; baselines; C24; C25"
        ),
        "validation_panel": V3_VALIDATION_PANEL,
        "benchmark": V3_BENCHMARK,
        "warmup_window": V3_WARMUP_WINDOW,
        "phase_a_window": V3_PHASE_A_WINDOW,
        "phase_b_window": V3_PHASE_B_WINDOW,
        "panel_substitution_after_history_access_allowed": False,
        "candidate_v1_v2_data_eligible_as_unseen": False,
        "replacement_holdout_symbols": tuple(sorted(LOCKED_HOLDOUT)),
        "replacement_holdout_locked": True,
        "created_at": created_at,
        "status": "PREREGISTERED_AWAITING_UNSEEN_PHASE_A",
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return CandidateV3Preregistration(**payload, preregistration_digest=digest)


def verify_preregistration(record: CandidateV3Preregistration) -> bool:
    payload = asdict(record)
    digest = payload.pop("preregistration_digest")
    expected = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return (
        digest == expected
        and record.grid_search_allowed is False
        and record.validation_panel == V3_VALIDATION_PANEL
        and record.panel_substitution_after_history_access_allowed is False
        and record.candidate_v1_v2_data_eligible_as_unseen is False
        and record.replacement_holdout_locked is True
        and set(record.replacement_holdout_symbols) == set(LOCKED_HOLDOUT)
    )
