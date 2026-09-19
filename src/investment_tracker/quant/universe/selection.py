from __future__ import annotations

from .artifacts import Phase3ArtifactStore
from .constants import EXPOSURE_SLOTS, MAX_UNIVERSE_SIZE, MIN_UNIVERSE_SIZE
from .models import (
    ArtifactIdentity,
    SelectedExposure,
    SelectionCandidateStatus,
    SelectionDecision,
    SelectionResult,
)


def select_universe(
    snapshot_identity: ArtifactIdentity,
    store: Phase3ArtifactStore,
) -> SelectionResult:
    snapshot = store.load_frozen_snapshot(snapshot_identity)
    statuses = {candidate.symbol: candidate.status for candidate in snapshot.candidates}
    decisions: list[SelectionDecision] = []
    selected: list[SelectedExposure] = []

    for slot in EXPOSURE_SLOTS:
        if len(selected) >= MAX_UNIVERSE_SIZE:
            break
        dq_statuses = tuple(
            SelectionCandidateStatus(symbol=symbol, status=statuses[symbol])
            for symbol in slot.candidates
        )
        chosen = next(
            (item.symbol for item in dq_statuses if item.status == "PASS"),
            None,
        )
        decisions.append(
            SelectionDecision(
                category=slot.name,
                ordered_candidates=slot.candidates,
                dq_statuses=dq_statuses,
                selected_symbol=chosen,
                reason=(
                    "SELECTED_FIRST_CLEAN" if chosen is not None else "NO_CLEAN_CANDIDATE"
                ),
            )
        )
        if chosen is not None:
            selected.append(SelectedExposure(category=slot.name, symbol=chosen))

    admitted = len(selected) >= MIN_UNIVERSE_SIZE
    return SelectionResult(
        snapshot=snapshot_identity,
        decisions=tuple(decisions),
        selected_exposures=tuple(selected),
        selected_symbols=tuple(item.symbol for item in selected),
        admitted=admitted,
        stop_reason=(
            "PHASE_3_UNIVERSE_FROZEN"
            if admitted
            else "INSUFFICIENT_CLEAN_DIVERSIFIED_UNIVERSE"
        ),
    )
