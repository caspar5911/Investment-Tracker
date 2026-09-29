from __future__ import annotations

import json
from pathlib import Path

from investment_tracker.independent_audit.generation2 import cli


def test_generation2_cli_exposes_release_and_one_time_evaluation(monkeypatch, tmp_path: Path, capsys):
    release = tmp_path / "release.json"
    release.write_text('{"status":"FINAL_HOLDOUT_RELEASE_AUTHORIZED","release_id":"R"}', encoding="utf-8")
    seen: list[str] = []

    def fake_release(**kwargs):
        seen.append("release")
        return release

    def fake_evaluate(**kwargs):
        seen.append("evaluate")
        return {
            "status": "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE",
            "release_id": "R",
            "holdout_id": "H",
            "one_time_consumed": True,
        }

    monkeypatch.setattr(cli, "issue_release", fake_release)
    monkeypatch.setattr(cli, "evaluate_released_holdout", fake_evaluate)
    assert cli.main(
        [
            "issue-final-holdout-release",
            "--receipt", "receipt.json",
            "--bundle", "bundle.bin",
            "--key", "key.txt",
            "--output", str(release),
            "--receipt-evidence-output", str(tmp_path / "receipt-evidence.json"),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "FINAL_HOLDOUT_RELEASE_AUTHORIZED"

    assert cli.main(
        [
            "evaluate-final-holdout",
            "--release", str(release),
            "--receipt", "receipt.json",
            "--bundle", "bundle.bin",
            "--key", "key.txt",
            "--marker-directory", str(tmp_path / "markers"),
            "--output", str(tmp_path / "result.json"),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["one_time_consumed"] is True
    assert seen == ["release", "evaluate"]
