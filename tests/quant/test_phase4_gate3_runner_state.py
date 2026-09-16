from pathlib import Path

import pytest

from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity
from investment_tracker.quant.phase4.gate3_runner.models import AttemptRecord, PositionReceipt
from investment_tracker.quant.phase4.gate3_runner.state import RunnerStateStore
from investment_tracker.quant.phase4.preregistration.canonical import artifact_envelope_identity


def identity(kind: str, path: str, content: str = "0" * 64) -> ArtifactIdentity:
    return ArtifactIdentity(
        kind=kind,
        content_sha256=content,
        path=path,
        sha256=artifact_envelope_identity(content_sha256=content, kind=kind, path=path),
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

    receipt = PositionReceipt(
        population_position=1,
        candidate_id=record.candidate_id,
        trial_id=record.trial_id,
        result_artifact=identity("phase4_gate3_candidate_result", "results/result.json", "4" * 64),
        result_status="UNKNOWN",
    )
    receipt_identity = store.write_receipt(receipt)
    assert store.write_receipt(receipt) == receipt_identity
    assert store.read_receipt(1)[0] == receipt


def test_unequal_fixed_position_collision_fails(tmp_path: Path):
    manifest = identity("gate3_campaign_runner_manifest", "runner/manifest.json")
    store = RunnerStateStore(tmp_path)
    store.write_attempt(attempt(manifest))
    path = tmp_path / "results/phase4/gate3/campaign/attempt/position-0001.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="IMMUTABLE_ARTIFACT_COLLISION"):
        store.write_attempt(attempt(manifest))


def test_symlink_redirect_is_rejected(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "results").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="ARTIFACT_PATH_INVALID"):
        RunnerStateStore(tmp_path)
