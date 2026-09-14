from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

try:
    import investment_tracker.quant.phase4.engine.cli as _cli_module

    _CLI_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as _exc:  # pragma: no cover - RED marker
    _cli_module = None
    _CLI_IMPORT_ERROR = _exc


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GATE2_RESULTS = REPOSITORY_ROOT / "results" / "phase4" / "gate2"


@pytest.fixture(autouse=True)
def require_cli_types(request: pytest.FixtureRequest) -> None:
    if _CLI_IMPORT_ERROR is not None and (
        "test_cli_types_are_available" not in request.node.name
    ):
        pytest.skip(f"Gate 2 CLI unavailable: {_CLI_IMPORT_ERROR}")


def test_cli_types_are_available() -> None:
    assert _CLI_IMPORT_ERROR is None, str(_CLI_IMPORT_ERROR)
    assert callable(_cli_module.main)


def test_cli_main_success_prints_sealed_manifest_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = _cli_module.main(["--repository-root", str(REPOSITORY_ROOT)])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "SEALED"
    manifest = payload["manifest"]
    assert manifest["kind"] == "phase4_engine_manifest"
    assert manifest["path"].startswith(
        "results/phase4/gate2/phase4_engine_manifest/sha256/"
    )
    assert set(manifest) == {"kind", "content_sha256", "path", "sha256"}
    # The seal must write only beneath results/phase4/gate2/.
    if GATE2_RESULTS.exists():
        for path in GATE2_RESULTS.rglob("*"):
            relative = path.relative_to(REPOSITORY_ROOT).as_posix()
            assert relative.startswith("results/phase4/gate2/")


def test_cli_requires_repository_root() -> None:
    with pytest.raises(SystemExit):
        _cli_module.main([])


def test_cli_rejects_unknown_options() -> None:
    with pytest.raises(SystemExit):
        _cli_module.main(
            ["--repository-root", str(REPOSITORY_ROOT), "--data", "bogus"]
        )


def test_cli_repeat_run_is_byte_identical(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _cli_module.main(["--repository-root", str(REPOSITORY_ROOT)]) == 0
    first = capsys.readouterr().out
    assert _cli_module.main(["--repository-root", str(REPOSITORY_ROOT)]) == 0
    second = capsys.readouterr().out
    assert first == second


def test_cli_source_exposes_no_forbidden_surface() -> None:
    source_path = _cli_module.__file__
    source = Path(source_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=source_path)
    imports: list[str] = []
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            identifiers.add(node.name)
    from investment_tracker.quant.phase4.engine.conformance import (
        _FORBIDDEN_IDENTIFIERS,
        _FORBIDDEN_IMPORT_FRAGMENTS,
    )

    for imported in imports:
        for fragment in _FORBIDDEN_IMPORT_FRAGMENTS:
            assert fragment not in imported, (imported, fragment)
    assert not (identifiers & _FORBIDDEN_IDENTIFIERS)
    for option in (
        "--data",
        "--candidate",
        "--parameter",
        "--provider",
        "--export",
        "--order",
        "--trading",
        "--rank",
        "--validation",
        "--universe",
    ):
        assert option not in source, option


def test_cli_subprocess_fails_clean_in_empty_git_repository(
    tmp_path: Path,
) -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPOSITORY_ROOT / "src")
    environment["GIT_CONFIG_GLOBAL"] = "NUL"
    environment["GIT_CONFIG_SYSTEM"] = "NUL"
    environment["HOME"] = str(tmp_path)

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            env=environment,
        )

    git("init", "-q", tmp_path.as_posix())
    git("config", "core.autocrlf", "false")
    git("config", "user.email", "gate2@example.test")
    git("config", "user.name", "Gate 2 Conformance")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "investment_tracker.quant.phase4.engine.cli",
            "--repository-root",
            tmp_path.as_posix(),
        ],
        capture_output=True,
        text=True,
        env=environment,
        cwd=str(REPOSITORY_ROOT),
    )
    assert completed.returncode != 0
    assert "GATE1_MANIFEST_MISMATCH" in completed.stderr
    assert not (tmp_path / "results" / "phase4" / "gate2").exists()
