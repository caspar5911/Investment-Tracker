from pathlib import Path

import pytest

from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity
from investment_tracker.quant.phase4.gate3_runner.models import (
    AttemptRecord,
    CampaignResultSet,
    PositionReceipt,
)
from investment_tracker.quant.phase4.gate3_runner.state import RunnerStateStore
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_sha256,
)


def identity(kind: str, path: str, content: str = "0" * 64) -> ArtifactIdentity:
    return ArtifactIdentity(
        kind=kind,
        content_sha256=content,
        path=path,
        sha256=artifact_envelope_identity(
            content_sha256=content,
            kind=kind,
            path=path,
        ),
    )


def attempt(manifest: ArtifactIdentity) -> AttemptRecord:
    return AttemptRecord(
        population_position=1,
        candidate_id="phase4-" + "1" * 64,
        trial_id="2" * 64,
        family_id="phase4-family-" + "3" * 64,
        runner_manifest=manifest,
    )


def test_position_state_is_no_overwrite_and_idempotent(tmp_path: Path):
    manifest = identity("gate3_campaign_runner_manifest", "runner/manifest.json")
    store = RunnerStateStore(tmp_path)
    record = attempt(manifest)
    first = store.write_attempt(record)
    assert store.write_attempt(record) == first
    assert store.read_attempt(1)[0] == record


def test_receipt_requires_matching_attempt_before_publish(tmp_path: Path):
    manifest = identity("gate3_campaign_runner_manifest", "runner/manifest.json")
    store = RunnerStateStore(tmp_path)
    record = attempt(manifest)
    store.write_attempt(record)
    forged = PositionReceipt(
        population_position=1,
        candidate_id="phase4-" + "9" * 64,
        trial_id=record.trial_id,
        result_artifact=identity(
            "phase4_gate3_candidate_result",
            "results/forged.json",
            "6" * 64,
        ),
        result_status="UNKNOWN",
    )
    with pytest.raises(ValueError, match="RUNNER_RECEIPT_ATTEMPT_MISMATCH"):
        store.write_receipt(forged)
    assert store.read_receipt(1) is None


def test_result_set_cannot_publish_with_missing_position_receipts(tmp_path: Path):
    manifest = identity("gate3_campaign_runner_manifest", "runner/manifest.json")
    artifacts = tuple(
        identity(
            "phase4_gate3_candidate_result",
            f"results/result-{position:04d}.json",
            f"{position:064x}"[-64:],
        )
        for position in range(1, 181)
    )
    aggregate = canonical_sha256(
        {
            "schema_version": "PHASE4-GATE3-CAMPAIGN-RESULT-SET-IDENTITY-v1",
            "runner_manifest": manifest.model_dump(mode="json"),
            "results": [item.model_dump(mode="json") for item in artifacts],
        }
    )
    result_set = CampaignResultSet(
        runner_manifest=manifest,
        result_artifacts=artifacts,
        aggregate_sha256=aggregate,
    )
    with pytest.raises(ValueError, match="RUNNER_ACCOUNTABILITY_INCOMPLETE"):
        RunnerStateStore(tmp_path).write_result_set(result_set)


def test_symlink_redirect_is_rejected(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "results").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="ARTIFACT_PATH_INVALID"):
        RunnerStateStore(tmp_path)
