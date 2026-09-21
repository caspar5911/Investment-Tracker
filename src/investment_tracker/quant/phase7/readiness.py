from __future__ import annotations

import json
from pathlib import Path


PHASE6_SUCCESS_STATUS = "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"


class Phase7EntryError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase7EntryError(f"PHASE7_EVIDENCE_INVALID:{path}") from exc
    if not isinstance(value, dict):
        raise Phase7EntryError(f"PHASE7_EVIDENCE_INVALID:{path}")
    return value


def assert_phase7_entry(
    *,
    phase6_result_path: Path,
    generation_terminal_path: Path | None = None,
) -> dict[str, object]:
    result = _load_json(phase6_result_path)
    status = result.get("status")
    if status != PHASE6_SUCCESS_STATUS:
        raise Phase7EntryError(
            f"PHASE7_ENTRY_FORBIDDEN:PHASE6_STATUS={status or 'MISSING'}"
        )
    if result.get("one_time_consumed") is not True:
        raise Phase7EntryError("PHASE7_ENTRY_FORBIDDEN:PHASE6_NOT_CONSUMED")
    if result.get("phase7_started") is not False:
        raise Phase7EntryError("PHASE7_ENTRY_FORBIDDEN:PHASE6_PHASE7_STATE_INVALID")
    if result.get("production_readiness_approved") is not False:
        raise Phase7EntryError(
            "PHASE7_ENTRY_FORBIDDEN:PHASE6_PRODUCTION_STATE_INVALID"
        )

    if generation_terminal_path is not None:
        terminal = _load_json(generation_terminal_path)
        if terminal.get("phase7_entry_allowed") is not True:
            raise Phase7EntryError("PHASE7_ENTRY_FORBIDDEN:GENERATION_TERMINAL_BLOCK")
        if terminal.get("candidate_id") != result.get("candidate_id"):
            raise Phase7EntryError("PHASE7_ENTRY_FORBIDDEN:CANDIDATE_IDENTITY_MISMATCH")

    return result
