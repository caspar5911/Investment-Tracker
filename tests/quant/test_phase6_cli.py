from __future__ import annotations

import json
from pathlib import Path

from investment_tracker.quant.phase6.cli import main


def test_preflight_cli_writes_compact_readiness_record(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "phase6-preflight.json"

    code = main(
        [
            "preflight",
            "--repository-root",
            ".",
            "--output",
            str(output),
        ]
    )

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "PHASE6_READY_FOR_INDEPENDENT_AUDIT_RELEASE"
    assert payload["safety"]["final_holdout_accessed"] is False
    assert payload["safety"]["protected_symbols_accessed"] == []

    rendered = json.loads(capsys.readouterr().out)
    assert rendered == payload


def test_preflight_cli_creates_missing_output_parent_directory(
    tmp_path: Path,
) -> None:
    output = tmp_path / "data" / "phase6" / "phase6-preflight.json"
    assert not output.parent.exists()

    code = main(
        [
            "preflight",
            "--repository-root",
            ".",
            "--output",
            str(output),
        ]
    )

    assert code == 0
    assert output.is_file()
