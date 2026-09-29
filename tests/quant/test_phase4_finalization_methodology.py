from __future__ import annotations

from pathlib import Path

import pytest

from investment_tracker.quant.phase4.finalization.methodology import (
    preflight_finalization,
    spec_identity,
)


def test_finalization_spec_identity_is_repository_relative() -> None:
    root = Path(__file__).resolve().parents[2]
    identity = spec_identity(root)
    assert identity.kind == "phase4_finalization_spec"
    assert identity.path == "docs/superpowers/specs/2026-09-18-phase-4-finalization-design.md"


def test_explicit_hash_preflight_rejects_missing_manifest() -> None:
    root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="FINALIZATION_MANIFEST_MISSING"):
        preflight_finalization(root, "0" * 64)


def test_finalization_source_has_no_execution_provider_holdout_or_trading_surface() -> None:
    root = Path(__file__).resolve().parents[2]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "src/investment_tracker/quant/phase4/finalization").glob("*.py"))
    )
    forbidden = (
        "OpenTradeContext",
        "unlock_trade",
        "place_order",
        "requests.",
        "httpx.",
        "moomoo",
        "run_campaign(",
        "_evaluate_binding(",
        "_generate_targets(",
    )
    for token in forbidden:
        assert token not in source
