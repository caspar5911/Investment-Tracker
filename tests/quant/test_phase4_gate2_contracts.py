from __future__ import annotations

import ast
import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError


PACKAGE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "investment_tracker"
    / "quant"
    / "phase4"
    / "engine"
)

FROZEN_FAILURE_CODES = (
    "GATE1_MANIFEST_MISMATCH",
    "GATE1_DEPENDENCY_MISMATCH",
    "CANDIDATE_POPULATION_MISMATCH",
    "EXECUTION_CONVENTION_MISMATCH",
    "IMPLEMENTATION_BINDING_MISMATCH",
    "INPUT_BOUNDARY_VIOLATION",
    "MARKET_PANEL_INVALID",
    "LONG_ONLY_INVARIANT_FAILURE",
    "ACCOUNTING_INVARIANT_FAILURE",
    "FIXED_STRATEGY_INVARIANT_FAILURE",
    "DURABILITY_EVIDENCE_INVALID",
    "BUDGET_ACCOUNTING_INVALID",
    "FOLD_AUTHORITY_MISSING",
    "REGIME_AUTHORITY_MISSING",
    "FORBIDDEN_CAPABILITY_PRESENT",
    "HISTORICAL_ARTIFACT_MUTATION",
    "IMMUTABLE_ARTIFACT_COLLISION",
    "SEAL_PUBLICATION_FAILED",
)


def test_gate2_contract_models_exist_and_are_closed() -> None:
    package = importlib.import_module("investment_tracker.quant.phase4.engine")
    assert package.GATE2_FAILURE_CODES == FROZEN_FAILURE_CODES
    error = package.Gate2SealError("GATE1_DEPENDENCY_MISMATCH", "dependency")
    assert error.code == "GATE1_DEPENDENCY_MISMATCH"
    assert str(error) == "dependency"
    with pytest.raises(ValueError, match="unknown Gate 2 failure code"):
        package.Gate2SealError("NOT_A_GATE2_CODE", "bad")

    safety = package.SafetyAccessState()
    with pytest.raises(ValidationError, match="frozen"):
        safety.provider_calls = 1
    with pytest.raises(ValidationError, match="extra"):
        package.SafetyAccessState.model_validate(
            {**safety.model_dump(), "unexpected": True}
        )
    with pytest.raises(ValidationError):
        package.SafetyAccessState(provider_calls=1)


def test_direct_dependency_paths_are_portable_and_envelopes_validate() -> None:
    package = importlib.import_module("investment_tracker.quant.phase4.engine")
    with pytest.raises(ValidationError):
        package.DirectDependencyIdentity(
            kind="unadmitted_dependency",
            path="results/fixture.json",
            content_sha256="a" * 64,
        )
    with pytest.raises(ValidationError, match="repository-relative POSIX"):
        package.DirectDependencyIdentity(
            kind="research_notes",
            path="../escape.json",
            content_sha256="a" * 64,
        )
    with pytest.raises(ValidationError, match="envelope"):
        package.DirectDependencyIdentity(
            kind="baseline_definitions",
            path="results/fixture.json",
            content_sha256="a" * 64,
            sha256="b" * 64,
        )


def test_gate2_authority_package_has_no_forbidden_capability_imports_or_symbols() -> (
    None
):
    forbidden_import_fragments = (
        ".backtest",
        ".data",
        ".experiments",
        ".moomoo",
        ".optimizer",
        ".promotion",
        ".reports",
        ".strategies",
        ".universe",
        ".validation",
        ".workflow",
    )
    forbidden_identifiers = {
        "OpenQuoteContext",
        "OpenSecTradeContext",
        "OpenFutureTradeContext",
        "OpenCryptoTradeContext",
        "place_order",
        "modify_order",
        "cancel_order",
        "unlock_trade",
        "rank_candidates",
        "select_survivor",
        "export_results",
        "promote_candidate",
        "write_tracker",
        "brokerage_account",
    }
    for path in sorted(PACKAGE_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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
        assert not any(
            fragment in imported
            for fragment in forbidden_import_fragments
            for imported in imports
        ), path
        assert identifiers.isdisjoint(forbidden_identifiers), path


def test_importing_gate2_authority_does_not_load_provider_or_experiment_modules() -> (
    None
):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PACKAGE_ROOT.parents[3])
    script = """
import sys
import investment_tracker.quant.phase4.engine
forbidden = (
    'investment_tracker.quant.data',
    'investment_tracker.quant.experiments',
    'investment_tracker.quant.moomoo',
    'investment_tracker.quant.optimizer',
    'investment_tracker.quant.promotion',
    'investment_tracker.quant.validation',
    'investment_tracker.quant.workflow',
)
loaded = sorted(name for name in sys.modules if name.startswith(forbidden))
if loaded:
    raise SystemExit(','.join(loaded))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PACKAGE_ROOT.parents[4],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
