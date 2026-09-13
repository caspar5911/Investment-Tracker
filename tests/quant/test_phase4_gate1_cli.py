from __future__ import annotations

import json

from investment_tracker.quant.phase4.preregistration.cli import build_parser, main


def test_cli_exposes_only_exact_repository_root_and_no_research_or_execution_controls() -> None:
    parser = build_parser()
    options = {option for action in parser._actions for option in action.option_strings}
    assert options == {"-h", "--help", "--repository-root"}
    forbidden = {"--symbol", "--start", "--end", "--provider", "--validation", "--trade", "--search"}
    assert not options & forbidden


def test_cli_returns_structured_failure_for_invalid_root(capsys, tmp_path) -> None:
    missing = tmp_path / "missing"
    assert main(["--repository-root", str(missing)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "GATE1_FAILED"
    assert payload["error_code"] == "READINESS_MANIFEST_MISMATCH"
