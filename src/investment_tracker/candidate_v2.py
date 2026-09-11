"""Candidate-v2 preregistration contract.

Candidate v2 is a governance/calculation protocol revision, not a post-hoc
performance repair. REPLAY-v1.0 signal thresholds are inherited unchanged.
Legacy Phase A and Phase B evidence are development/diagnostic evidence only
for v2 and can never be relabelled as unseen validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json

from .governance import LOCKED_HOLDOUT

CANDIDATE_V2 = "CANDIDATE-v2.0"
V2_VERSIONS = {
    "tpc": "TPC-v1.2",
    "replay": "REPLAY-v1.0",
    "calc": "CALC-v2.0",
    "robust": "ROBUST-v2.0",
}
LEGACY_SEEN_PARTITIONS = (
    "PHASE_A_2018-01-01_2023-12-31",
    "PHASE_B_2024-01-01_2025-09-07",
)


@dataclass(frozen=True)
class CandidateV2Preregistration:
    candidate_id: str
    versions: dict[str, str]
    replay_thresholds_changed: bool
    replay_threshold_source: str
    max_drawdown_convention: str
    rb09_same_session_rule: str
    rb09_supportive_threshold: str
    legacy_seen_partitions: tuple[str, ...]
    legacy_seen_partitions_eligible_as_unseen_oos: bool
    replacement_holdout_symbols: tuple[str, ...]
    replacement_holdout_locked: bool
    prospective_evidence_not_before: datetime
    created_at: datetime
    status: str
    preregistration_digest: str


def preregister_candidate_v2(
    *,
    created_at: datetime,
    prospective_evidence_not_before: datetime,
) -> CandidateV2Preregistration:
    _require_aware(created_at)
    _require_aware(prospective_evidence_not_before)
    if prospective_evidence_not_before < created_at:
        raise ValueError("prospective evidence boundary cannot predate preregistration")

    payload = {
        "candidate_id": CANDIDATE_V2,
        "versions": V2_VERSIONS,
        "replay_thresholds_changed": False,
        "replay_threshold_source": "INHERIT_REPLAY-v1.0_UNCHANGED",
        "max_drawdown_convention": "C25_CLOSE_MARKED_ENTRY_OPEN_HIGH_WATER",
        "rb09_same_session_rule": (
            "equal-weight median across clean same-entry-session proxy episodes "
            "before chronological global 20-session non-overlap selection"
        ),
        "rb09_supportive_threshold": (
            ">=20 non-overlap clusters and median 20d excess versus SPY >= 0"
        ),
        "legacy_seen_partitions": LEGACY_SEEN_PARTITIONS,
        "legacy_seen_partitions_eligible_as_unseen_oos": False,
        "replacement_holdout_symbols": tuple(sorted(LOCKED_HOLDOUT)),
        "replacement_holdout_locked": True,
        "prospective_evidence_not_before": prospective_evidence_not_before,
        "created_at": created_at,
        "status": "PREREGISTERED_AWAITING_GENUINELY_UNSEEN_EVIDENCE",
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return CandidateV2Preregistration(
        **payload,
        preregistration_digest=digest,
    )


def verify_preregistration(record: CandidateV2Preregistration) -> bool:
    payload = asdict(record)
    digest = payload.pop("preregistration_digest")
    expected = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return (
        digest == expected
        and record.versions == V2_VERSIONS
        and record.replay_thresholds_changed is False
        and record.legacy_seen_partitions_eligible_as_unseen_oos is False
        and record.replacement_holdout_locked is True
        and set(record.replacement_holdout_symbols) == set(LOCKED_HOLDOUT)
    )


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("preregistration timestamps must be timezone-aware")
