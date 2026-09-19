from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from investment_tracker.quant.phase4.engine.models import FixedStrategyBinding

from .methodology import (
    PHASE4_DECISION_CONTENT_SHA256,
    SELECTED_BINDING_SHA256,
    SELECTED_CANDIDATE_ID,
    SELECTED_RESULT_CONTENT_SHA256,
    frozen_binding,
)

DECISION_PATH = (
    "results/phase4/finalization/decision/sha256/"
    f"{PHASE4_DECISION_CONTENT_SHA256}/decision.json"
)
RESULT_PATH = (
    "results/phase4/gate3/campaign/candidate_result/sha256/"
    f"{SELECTED_RESULT_CONTENT_SHA256}/record.json"
)


def _read_exact_json(root: Path, relative: str, expected_sha256: str) -> dict[str, object]:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("PHASE5_AUTHORITY_PATH_ESCAPE") from exc
    payload = path.read_bytes()
    if sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("PHASE5_AUTHORITY_CONTENT_IDENTITY_MISMATCH")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("PHASE5_AUTHORITY_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise ValueError("PHASE5_AUTHORITY_JSON_INVALID")
    return value


def load_phase4_authority(root: Path) -> tuple[dict[str, object], dict[str, object], FixedStrategyBinding]:
    repository = Path(root).resolve()
    decision = _read_exact_json(repository, DECISION_PATH, PHASE4_DECISION_CONTENT_SHA256)
    result = _read_exact_json(repository, RESULT_PATH, SELECTED_RESULT_CONTENT_SHA256)
    if (
        decision.get("status") != "ONE_FROZEN_SURVIVOR"
        or decision.get("selected_candidate_id") != SELECTED_CANDIDATE_ID
        or decision.get("selected_population_position") != 150
    ):
        raise ValueError("PHASE5_FINALIZATION_DECISION_MISMATCH")
    evidence = result.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("PHASE5_SELECTED_RESULT_SCHEMA_MISMATCH")
    replays = evidence.get("replays")
    if not isinstance(replays, list):
        raise ValueError("PHASE5_SELECTED_RESULT_SCHEMA_MISMATCH")
    zero = [item for item in replays if isinstance(item, dict) and item.get("friction_bps") == 0]
    if len(zero) != 1 or not isinstance(zero[0].get("states"), list) or not zero[0]["states"]:
        raise ValueError("PHASE5_ZERO_BPS_REPLAY_MISSING")
    binding_payload = zero[0]["states"][0].get("binding")
    if not isinstance(binding_payload, dict):
        raise ValueError("PHASE5_SELECTED_BINDING_MISSING")
    binding = FixedStrategyBinding.model_validate(binding_payload)
    if binding != frozen_binding() or binding.binding_sha256 != SELECTED_BINDING_SHA256:
        raise ValueError("PHASE5_SELECTED_BINDING_MISMATCH")
    return decision, result, binding
