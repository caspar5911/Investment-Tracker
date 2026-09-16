from pathlib import Path

import pytest

from investment_tracker.quant.phase4.gate3_runner.dependencies import (
    RESULT_SCHEMA_CONTENT,
    SCORED_PANEL_SHA256,
)
from investment_tracker.quant.phase4.gate3_runner.methodology import (
    declared_manifest,
    preflight_runner,
    spec_identity,
)


ROOT = Path(__file__).resolve().parents[2]


def test_declared_runner_manifest_binds_prior_sealed_authorities_without_execution():
    manifest = declared_manifest(ROOT, "0" * 40, None)
    assert manifest.candidate_count == 180
    assert manifest.scored_market_panel_sha256 == SCORED_PANEL_SHA256
    assert manifest.result_schema_manifest.content_sha256 == RESULT_SCHEMA_CONTENT
    assert manifest.safety.candidate_executed is False
    assert manifest.safety.validation_candidate_performance_accessed is False
    assert manifest.source_bundle is None


def test_runner_spec_identity_is_exact_repository_relative_content():
    identity = spec_identity(ROOT)
    assert identity.kind == "phase4_gate3_runner_spec"
    assert identity.path == (
        "docs/superpowers/specs/"
        "2026-09-16-phase-4-gate-3-campaign-orchestrator-design.md"
    )
    assert len(identity.content_sha256) == 64


def test_explicit_hash_preflight_rejects_missing_runner_manifest():
    with pytest.raises(ValueError, match="RUNNER_MANIFEST_MISSING"):
        preflight_runner(ROOT, "0" * 64)
