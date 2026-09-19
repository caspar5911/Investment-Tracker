from __future__ import annotations

from pathlib import Path

import pandas as pd

from .authority import load_phase4_authority
from .methodology import REBALANCE_SESSIONS, SELECTED_BINDING_SHA256
from .signals import TargetDecision


def extract_sealed_validation_targets(root: Path) -> tuple[TargetDecision, ...]:
    _, result, _ = load_phase4_authority(root)
    evidence = result["evidence"]
    assert isinstance(evidence, dict)
    replays = evidence["replays"]
    assert isinstance(replays, list)
    replay = next(item for item in replays if isinstance(item, dict) and item.get("friction_bps") == 0)
    states = replay.get("states")
    if not isinstance(states, list) or len(states) != 1008:
        raise ValueError("PHASE5_SEALED_REPLAY_STATE_COUNT_MISMATCH")
    targets: list[TargetDecision] = []
    for position in range(0, len(states), REBALANCE_SESSIONS):
        if position + 1 >= len(states):
            break
        signal_state = states[position]
        due_state = states[position + 1]
        if not isinstance(signal_state, dict) or not isinstance(due_state, dict):
            raise ValueError("PHASE5_SEALED_REPLAY_STATE_INVALID")
        binding = due_state.get("binding")
        if not isinstance(binding, dict) or binding.get("binding_sha256") != SELECTED_BINDING_SHA256:
            raise ValueError("PHASE5_SEALED_REPLAY_BINDING_MISMATCH")
        signal = pd.Timestamp(str(signal_state["session"]))
        due = pd.Timestamp(str(due_state["session"]))
        units = due_state.get("units")
        if not isinstance(units, list):
            raise ValueError("PHASE5_SEALED_REPLAY_UNITS_INVALID")
        selected = tuple(str(item[0]) for item in units if isinstance(item, list) and len(item) == 2 and float(item[1]) > 0.0)
        weights = () if not selected else tuple((symbol, 1.0 / len(selected)) for symbol in selected)
        targets.append(TargetDecision(signal, due, weights))
    if not targets:
        raise ValueError("PHASE5_SEALED_TARGET_SEQUENCE_EMPTY")
    return tuple(targets)
