from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from investment_tracker.quant import cli


def phase4_option_strings() -> set[str]:
    root = cli.parser()
    subparsers = next(
        action
        for action in root._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    phase4 = subparsers.choices["phase4-readiness"]
    return {
        option
        for action in phase4._actions
        for option in action.option_strings
    }


def test_cli_has_only_explicit_repository_and_results_roots() -> None:
    options = phase4_option_strings()

    assert options == {"-h", "--help", "--repository-root", "--results-root"}
    assert options.isdisjoint(
        {
            "--host",
            "--port",
            "--symbol",
            "--family",
            "--parameters",
            "--max-trials",
            "--provider",
            "--strategy",
        }
    )


def test_cli_reports_ready_without_strategy_or_provider_execution(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    import investment_tracker.quant.readiness as readiness

    observed: dict[str, Path] = {}

    class FakeOutcome:
        status = "PHASE_4_READY"

        def model_dump(self, *, mode: str):
            assert mode == "json"
            return {
                "status": self.status,
                "reason_code": None,
                "reason": None,
                "manifest": {"sha256": "a" * 64},
                "report": {"sha256": "b" * 64},
                "summary": None,
                "provider_calls": 0,
                "strategy_search_executed": False,
            }

    def fake_run(repository_root: Path, results_root: Path):
        observed["repository_root"] = repository_root
        observed["results_root"] = results_root
        return FakeOutcome()

    monkeypatch.setattr(readiness, "run_phase4_readiness", fake_run)
    repository = tmp_path / "repository"
    results = repository / "results"

    code = cli.main(
        [
            "phase4-readiness",
            "--repository-root",
            str(repository),
            "--results-root",
            str(results),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert observed == {
        "repository_root": repository,
        "results_root": results,
    }
    assert payload["status"] == "PHASE_4_READY"
    assert payload["provider_calls"] == 0
    assert payload["strategy_search_executed"] is False


def test_cli_import_is_lazy_and_provider_free() -> None:
    probe = (
        "import sys; "
        "import investment_tracker.quant.cli; "
        "forbidden = [name for name in sys.modules if "
        "name.startswith('investment_tracker.quant.readiness') or "
        "'moomoo_client' in name]; "
        "print(forbidden)"
    )

    completed = subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "[]"


def test_readiness_import_graph_has_no_forbidden_operational_dependencies() -> None:
    forbidden_modules = {
        "investment_tracker.quant.data.moomoo_client",
        "investment_tracker.quant.data.repository",
        "investment_tracker.quant.optimizer",
        "investment_tracker.quant.promotion",
        "investment_tracker.quant.moomoo.strategybase_exporter",
    }
    forbidden_symbols = {
        "OpenTradeContext",
        "OpenSecTradeContext",
        "OpenFutureTradeContext",
        "OpenCryptoTradeContext",
        "place_order",
        "modify_order",
        "cancel_order",
        "unlock_trade",
        "get_acc_list",
        "position_list_query",
        "accinfo_query",
        "canonical_tracker_write",
    }
    imported: set[str] = set()
    found_symbols: list[tuple[str, str]] = []
    for path in Path("src/investment_tracker/quant/readiness").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            if name in forbidden_symbols:
                found_symbols.append((str(path), name))

    assert imported.isdisjoint(forbidden_modules)
    assert found_symbols == []
