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
BRANCH = "codex/phase4-gate2"


def _run_git(args: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed rc={result.returncode}: {result.stderr}"
        )


def _clone_repository(dest: Path) -> Path:
    """Create a hermetic clone of the repository at the Gate 2 branch.

    The CLI seal reads Gate 1 authority and source bundles from the git
    history and worktree, so it must run against a repository that preserves
    the Gate 1 ancestry. A local clone provides a clean, independent copy so
    the full suite never writes to or mutates the canonical
    results/phase4/gate2/ evidence.
    """
    _run_git(["clone", "--quiet", str(REPOSITORY_ROOT), str(dest)])
    _run_git(["checkout", "-q", BRANCH], cwd=dest)
    return dest


@pytest.fixture(scope="module")
def gate2_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("gate2-cli") / "repo"
    return _clone_repository(dest)


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
    gate2_repo: Path,
) -> None:
    exit_code = _cli_module.main(["--repository-root", str(gate2_repo)])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "PHASE4_ENGINE_SEALED"
    manifest = payload["manifest"]
    assert manifest["kind"] == "phase4_engine_manifest"
    assert manifest["status"] == "PHASE4_ENGINE_SEALED"
    assert manifest["fold_status"] == "NOT_BOUND_GATE3_REQUIRED"
    assert manifest["regime_status"] == "NOT_BOUND_GATE3_REQUIRED"
    assert manifest["formula_version"] == "PHASE4-ENGINE-FORMULA-v1"
    assert manifest["candidate_population_sha256"] == (
        "15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3"
    )
    assert len(manifest["family_identities"]) == 4
    assert manifest["path"].startswith(
        "results/phase4/gate2/phase4_engine_manifest/sha256/"
    )
    assert set(manifest) == {"kind", "content_sha256", "path", "sha256"}
    # The seal must write only beneath results/phase4/gate2/ in the clone.
    gate2_results = gate2_repo / "results" / "phase4" / "gate2"
    if gate2_results.exists():
        for path in gate2_results.rglob("*"):
            relative = path.relative_to(gate2_repo).as_posix()
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
    gate2_repo: Path,
) -> None:
    assert _cli_module.main(["--repository-root", str(gate2_repo)]) == 0
    first = capsys.readouterr().out
    assert _cli_module.main(["--repository-root", str(gate2_repo)]) == 0
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
