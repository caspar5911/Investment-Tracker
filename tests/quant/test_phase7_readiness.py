from __future__ import annotations

import json
from pathlib import Path

import pytest

from investment_tracker.quant.phase7.readiness import (
    PHASE6_SUCCESS_STATUS,
    Phase7EntryError,
    assert_phase7_entry,
)


ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, value: dict[str, object]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_generation1_terminal_state_forbids_phase7():
    with pytest.raises(Phase7EntryError, match="PHASE6_STATUS=PHASE6_UNKNOWN_ABSTAIN"):
        assert_phase7_entry(
            phase6_result_path=ROOT / "data/phase6/phase6-final-holdout-closure.json",
            generation_terminal_path=ROOT / "data/governance/generation1-terminal.json",
        )


def test_unknown_phase6_result_cannot_enter_phase7(tmp_path: Path):
    result = _write(
        tmp_path / "phase6.json",
        {
            "status": "PHASE6_UNKNOWN_ABSTAIN",
            "one_time_consumed": True,
            "phase7_started": False,
            "production_readiness_approved": False,
        },
    )
    with pytest.raises(Phase7EntryError, match="PHASE6_STATUS=PHASE6_UNKNOWN_ABSTAIN"):
        assert_phase7_entry(phase6_result_path=result)


def test_success_requires_explicit_generation_permission(tmp_path: Path):
    candidate = "phase4-" + "a" * 64
    result = _write(
        tmp_path / "phase6.json",
        {
            "status": PHASE6_SUCCESS_STATUS,
            "candidate_id": candidate,
            "one_time_consumed": True,
            "phase7_started": False,
            "production_readiness_approved": False,
        },
    )
    terminal = _write(
        tmp_path / "terminal.json",
        {
            "candidate_id": candidate,
            "phase7_entry_allowed": False,
        },
    )
    with pytest.raises(Phase7EntryError, match="GENERATION_TERMINAL_BLOCK"):
        assert_phase7_entry(
            phase6_result_path=result,
            generation_terminal_path=terminal,
        )


def test_success_can_enter_only_with_matching_explicit_permission(tmp_path: Path):
    candidate = "phase4-" + "a" * 64
    result = _write(
        tmp_path / "phase6.json",
        {
            "status": PHASE6_SUCCESS_STATUS,
            "candidate_id": candidate,
            "one_time_consumed": True,
            "phase7_started": False,
            "production_readiness_approved": False,
        },
    )
    terminal = _write(
        tmp_path / "terminal.json",
        {
            "candidate_id": candidate,
            "phase7_entry_allowed": True,
        },
    )
    loaded = assert_phase7_entry(
        phase6_result_path=result,
        generation_terminal_path=terminal,
    )
    assert loaded["candidate_id"] == candidate
