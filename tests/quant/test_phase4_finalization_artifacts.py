from __future__ import annotations

from pathlib import Path

import pytest

from investment_tracker.quant.phase4.finalization.artifacts import FinalizationArtifactStore
from investment_tracker.quant.phase4.finalization.models import (
    FinalizationSafetyState,
    Phase4Decision,
)


def _decision(identity_factory) -> Phase4Decision:
    return Phase4Decision(
        status="NO_CREDIBLE_STRATEGY_FOUND",
        audit_artifact=identity_factory("phase4_finalization_audit", "results/audit.json"),
        campaign_result_set=identity_factory("phase4_gate3_campaign_result_set", "results/result-set.json"),
        survivor_policy=identity_factory("survivor_policy", "results/survivor.json"),
        durability_policy=identity_factory("durability_policy", "results/durability.json"),
        safety=FinalizationSafetyState(),
    )


def test_decision_publication_is_content_addressed_and_idempotent(tmp_path: Path, identity_factory) -> None:
    store = FinalizationArtifactStore(tmp_path)
    decision = _decision(identity_factory)
    first = store.write_decision(decision)
    second = store.write_decision(decision)
    assert first == second
    assert first.kind == "phase4_finalization_decision"
    assert first.path == (
        f"results/phase4/finalization/decision/sha256/{first.content_sha256}/decision.json"
    )
    assert store.read_decision(first) == decision


def test_decision_unequal_collision_is_rejected(tmp_path: Path, identity_factory) -> None:
    store = FinalizationArtifactStore(tmp_path)
    decision = _decision(identity_factory)
    identity = store.write_decision(decision)
    path = tmp_path / identity.path
    path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="IMMUTABLE_ARTIFACT_COLLISION|ARTIFACT_BYTES_INVALID"):
        store.write_decision(decision)
