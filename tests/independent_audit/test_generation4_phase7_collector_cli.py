"""CLI guardrails for structural Phase-7 collection and provider-free status."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from investment_tracker.independent_audit.post_generation3 import phase7_collector
from investment_tracker.independent_audit.post_generation3 import phase7_collector_cli
from investment_tracker.independent_audit.post_generation3 import phase7_first_checkpoint


def test_status_cli_is_provider_free_and_has_no_performance_fields(
    bound_evidence, tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    auth_path = tmp_path / "authorization.json"
    auth_path.write_text(json.dumps(bound_evidence.authorization), encoding="utf-8")
    monkeypatch.setattr(phase7_collector, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(phase7_collector, "_AUTHORIZATION_PATH", auth_path)
    monkeypatch.setattr(phase7_collector, "_OUTPUT_DIR", tmp_path / "prospective")
    monkeypatch.setattr(
        phase7_collector, "_utc_now",
        lambda: datetime.fromisoformat("2026-09-29T19:00:00+00:00"),
    )
    monkeypatch.setattr(
        phase7_collector, "acquire_prospective_phase7_data",
        lambda **kwargs: pytest.fail("status contacted provider path"),
    )

    exit_code = phase7_collector_cli.main(["prospective-status"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "PHASE7_COLLECTION_PENDING"
    assert payload["scored_session_count"] == 0
    assert payload["latest_completed_session"] == "2026-09-28"
    assert not any(
        field in payload for field in
        ("returns", "positions", "signals", "sharpe", "drawdown", "alpha")
    )


def test_cli_invalid_authorization_returns_unknown_abstain(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    auth_path = tmp_path / "invalid.json"
    auth_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(phase7_collector, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(phase7_collector, "_AUTHORIZATION_PATH", auth_path)
    monkeypatch.setattr(
        phase7_collector, "acquire_prospective_phase7_data",
        lambda **kwargs: pytest.fail("invalid authorization reached provider path"),
    )

    exit_code = phase7_collector_cli.main(["collect-prospective-data"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "PHASE7_UNKNOWN_ABSTAIN"


@pytest.mark.parametrize(
    "extra",
    [
        ["--symbols", "QQQM"],
        ["--requested-end", "2026-09-29"],
        ["--now", "2026-09-30T00:00:00Z"],
        ["--output-dir", "other"],
        ["--candidate", "other"],
    ],
)
def test_cli_rejects_scope_and_clock_overrides(extra: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        phase7_collector_cli.build_parser().parse_args(
            ["collect-prospective-data", *extra]
        )
    assert excinfo.value.code == 2


def test_collect_cli_returns_only_structural_status(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(
        phase7_collector,
        "collect_prospective_data",
        lambda: {
            "status": "NO_NEW_COMPLETED_SESSION",
            "latest_completed_session": "2026-09-28",
            "latest_acquired_session": "2026-09-28",
            "scored_session_count": 1,
            "next_checkpoint_sessions": 63,
            "sessions_remaining": 62,
        },
    )

    assert phase7_collector_cli.main(["collect-prospective-data"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "NO_NEW_COMPLETED_SESSION"


def test_first_checkpoint_readiness_cli_is_structural_only(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(
        phase7_first_checkpoint, "first_checkpoint_readiness",
        lambda: {"status": "PHASE7_CHECKPOINT_PENDING", "checkpoint_scored_sessions": 63,
                 "evaluation_authorized": False, "performance_computed": False},
    )
    assert phase7_collector_cli.main(["first-checkpoint-readiness"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PHASE7_CHECKPOINT_PENDING"
    assert payload["evaluation_authorized"] is False
    assert "friction_cases" not in payload
