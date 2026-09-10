from __future__ import annotations

from enum import Enum


class PhaseState(str, Enum):
    VALIDATED_NOT_CACHED = "VALIDATED_NOT_CACHED"
    PARTIAL_CACHE = "PARTIAL_CACHE"
    CACHED_CLEAN = "CACHED_CLEAN"
    QUARANTINED = "QUARANTINED"
    REPLAY_DAILY_COMPLETE = "REPLAY_DAILY_COMPLETE"
    EPISODES_COMPLETE = "EPISODES_COMPLETE"
    OUTCOMES_COMPLETE = "OUTCOMES_COMPLETE"
    BASELINES_COMPLETE = "BASELINES_COMPLETE"


class TransitionError(ValueError):
    pass


_ALLOWED_NEXT = {
    PhaseState.VALIDATED_NOT_CACHED: {PhaseState.PARTIAL_CACHE},
    PhaseState.PARTIAL_CACHE: {PhaseState.CACHED_CLEAN, PhaseState.QUARANTINED},
    PhaseState.CACHED_CLEAN: {PhaseState.REPLAY_DAILY_COMPLETE},
    PhaseState.QUARANTINED: {PhaseState.REPLAY_DAILY_COMPLETE},
    PhaseState.REPLAY_DAILY_COMPLETE: {PhaseState.EPISODES_COMPLETE},
    PhaseState.EPISODES_COMPLETE: {PhaseState.OUTCOMES_COMPLETE},
    PhaseState.OUTCOMES_COMPLETE: {PhaseState.BASELINES_COMPLETE},
    PhaseState.BASELINES_COMPLETE: set(),
}

_RANK = {
    PhaseState.VALIDATED_NOT_CACHED: 0,
    PhaseState.PARTIAL_CACHE: 1,
    PhaseState.CACHED_CLEAN: 2,
    PhaseState.QUARANTINED: 2,
    PhaseState.REPLAY_DAILY_COMPLETE: 3,
    PhaseState.EPISODES_COMPLETE: 4,
    PhaseState.OUTCOMES_COMPLETE: 5,
    PhaseState.BASELINES_COMPLETE: 6,
}


def assert_transition(
    current: PhaseState,
    target: PhaseState,
    evidence_readback_ok: bool,
    dq_reconciliation: bool = False,
) -> None:
    if not evidence_readback_ok:
        raise TransitionError("Phase Matrix advancement requires canonical readback evidence")
    if current == target:
        return
    if _RANK[target] < _RANK[current]:
        if dq_reconciliation:
            return
        raise TransitionError("phase regression requires explicit DQ reconciliation")
    if target not in _ALLOWED_NEXT[current]:
        raise TransitionError(f"invalid phase transition: {current.value} -> {target.value}")
