from __future__ import annotations

from dataclasses import replace
from importlib import import_module
from pathlib import Path
import os

import pytest

from investment_tracker.quant.phase4.engine.authority import load_gate2_authority
from investment_tracker.quant.phase4.engine.models import Phase4EngineManifest


ROOT = Path(__file__).resolve().parents[2]
GATE2_MANIFEST = ROOT / "results/phase4/gate2/phase4_engine_manifest/sha256/c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6/manifest.json"


def _campaign():
    return import_module("investment_tracker.quant.phase4.gate3_execution.campaign")


def _artifacts():
    return import_module("investment_tracker.quant.phase4.gate3_execution.artifacts")


@pytest.fixture(scope="module")
def authority():
    return load_gate2_authority(ROOT)


@pytest.fixture(scope="module")
def gate2_manifest():
    return Phase4EngineManifest.model_validate_json(GATE2_MANIFEST.read_bytes())


def test_campaign_plan_is_only_the_180_sealed_trial_identities(authority, gate2_manifest):
    rows = _campaign().prepare_campaign_plan(authority, gate2_manifest)
    assert len(rows) == 180
    assert tuple(row.population_position for row in rows) == tuple(range(1, 181))
    assert len({row.candidate_id for row in rows}) == 180
    assert len({row.trial_id for row in rows}) == 180
    assert all(row.status == "UNATTEMPTED" for row in rows)
    assert authority.phase4_trials_consumed == 0
    assert gate2_manifest.phase4_trials_consumed == 0


def test_duplicate_gap_extra_or_mutated_trial_cannot_enter_plan(authority, gate2_manifest):
    api = _campaign()
    rows = api.prepare_campaign_plan(authority, gate2_manifest)
    changed = (
        rows[:1] + rows[:1] + rows[2:],
        rows[1:],
        rows + (replace(rows[-1], population_position=181),),
        (replace(rows[0], trial_id="0" * 64),) + rows[1:],
    )
    for altered in changed:
        with pytest.raises(ValueError, match="CANDIDATE_POPULATION"):
            api.validate_candidate_population(authority, gate2_manifest, altered)


def test_unknown_and_abstain_evidence_are_distinct_and_append_only(authority, gate2_manifest, tmp_path):
    campaign = _campaign()
    artifacts = _artifacts()
    row = campaign.prepare_campaign_plan(authority, gate2_manifest)[0]
    store = artifacts.TrialEvidenceStore(tmp_path)
    unknown = campaign.TrialRecord.from_reference(row, status="UNKNOWN", reason="MISSING_METRIC")
    abstain = campaign.TrialRecord.from_reference(row, status="ABSTAIN", reason="DQ_FAIL_CLOSED")
    unknown_identity = store.write(unknown)
    abstain_identity = store.write(abstain)
    assert unknown_identity != abstain_identity
    assert store.verify(unknown_identity) == unknown.model_dump(mode="json")
    assert store.verify(abstain_identity) == abstain.model_dump(mode="json")
    assert store.write(unknown) == unknown_identity
    assert unknown_identity.path.startswith("results/phase4/gate3/campaign/trial_record/sha256/")
    assert "rank" not in unknown.model_dump()
    assert "winner" not in unknown.model_dump()
    with pytest.raises(ValueError, match="REASON"):
        campaign.TrialRecord.from_reference(row, status="ABSTAIN", reason="")


def test_existing_content_address_with_different_bytes_is_rejected(authority, gate2_manifest, tmp_path):
    campaign = _campaign()
    artifacts = _artifacts()
    row = campaign.prepare_campaign_plan(authority, gate2_manifest)[0]
    record = campaign.TrialRecord.from_reference(row, status="UNKNOWN", reason="MISSING_METRIC")
    store = artifacts.TrialEvidenceStore(tmp_path)
    identity = store.write(record)
    destination = tmp_path.joinpath(*identity.path.split("/"))
    destination.write_bytes(b"different")
    with pytest.raises(ValueError, match="IMMUTABLE_ARTIFACT_COLLISION"):
        store.write(record)


def test_mutated_artifact_envelope_cannot_verify_trial(authority, gate2_manifest, tmp_path):
    campaign = _campaign()
    row = campaign.prepare_campaign_plan(authority, gate2_manifest)[0]
    store = _artifacts().TrialEvidenceStore(tmp_path)
    identity = store.write(campaign.TrialRecord.from_reference(row, status="UNKNOWN", reason="MISSING_METRIC"))
    forged = identity.model_copy(update={"sha256": "0" * 64})
    with pytest.raises(ValueError, match="TRIAL_ARTIFACT_INVALID"):
        store.verify(forged)


def test_symlink_redirect_is_rejected_before_trial_evidence_write(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = tmp_path / "results"
    os.symlink(outside, target, target_is_directory=True)
    with pytest.raises(ValueError, match="ARTIFACT_PATH_INVALID"):
        _artifacts().TrialEvidenceStore(tmp_path)
