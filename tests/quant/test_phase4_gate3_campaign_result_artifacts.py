from dataclasses import replace
from importlib import import_module
from pathlib import Path
import os

import pytest

from investment_tracker.quant.phase4.engine.authority import load_gate2_authority
from investment_tracker.quant.phase4.engine.models import Phase4EngineManifest
from investment_tracker.quant.phase4.gate3_execution.campaign import TrialRecord, prepare_campaign_plan
from test_phase4_gate3_campaign_result_schema import case

ROOT = Path(__file__).resolve().parents[2]
GATE2 = ROOT / 'results/phase4/gate2/phase4_engine_manifest/sha256/c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6/manifest.json'


def store_api():
    return import_module('investment_tracker.quant.phase4.gate3_campaign.result_artifacts')


def test_immutable_result_store_api_exists():
    try:
        module = store_api()
    except ModuleNotFoundError:
        pytest.fail('Missing immutable result store')
    assert callable(module.ResultArtifactStore)


def test_result_store_roundtrip_collision_and_forged_envelope(tmp_path, case):
    authority, result = case
    store = store_api().ResultArtifactStore(tmp_path)
    identity = store.write_result(result, authority)
    assert store.write_result(result, authority) == identity
    assert store.read_result(identity, authority) == result
    forged = identity.model_copy(update={'sha256':'0'*64})
    with pytest.raises(ValueError, match='ARTIFACT_IDENTITY_INVALID'):
        store.read_result(forged, authority)
    destination = tmp_path.joinpath(*identity.path.split('/'))
    destination.write_bytes(b'different')
    with pytest.raises(ValueError, match='IMMUTABLE_ARTIFACT_COLLISION'):
        store.write_result(result, authority)


def test_store_revalidates_model_copy_before_any_write(tmp_path, case):
    authority, result = case
    forged = result.model_copy(update={'status':'UNKNOWN'})
    store = store_api().ResultArtifactStore(tmp_path)
    with pytest.raises(ValueError):
        store.write_result(forged, authority)
    assert not list(tmp_path.rglob('record.json'))


def test_store_rejects_symlink_and_reparse_redirect(tmp_path, case, monkeypatch):
    authority, result = case
    outside = tmp_path / 'outside'; outside.mkdir()
    os.symlink(outside, tmp_path / 'results', target_is_directory=True)
    with pytest.raises(ValueError, match='ARTIFACT_PATH_INVALID'):
        store_api().ResultArtifactStore(tmp_path)
    (tmp_path / 'results').unlink()
    store = store_api().ResultArtifactStore(tmp_path)
    from investment_tracker.quant.phase4.gate3 import filesystem
    original = filesystem.is_redirect
    monkeypatch.setattr(filesystem, 'is_redirect', lambda path: path == tmp_path/'results' or original(path))
    with pytest.raises(ValueError, match='ARTIFACT_PATH_INVALID'):
        store.write_result(result, authority)


def test_store_rejects_path_traversal_and_noncanonical_path(tmp_path, case):
    authority, result = case
    store = store_api().ResultArtifactStore(tmp_path)
    identity = store.write_result(result, authority)
    for path in ('../record.json', identity.path.replace('/record.json','/other.json')):
        with pytest.raises(ValueError, match='ARTIFACT_IDENTITY_INVALID'):
            store.read_result(identity.model_copy(update={'path':path}), authority)


def test_preparation_record_remains_unable_to_record_executed():
    authority = load_gate2_authority(ROOT)
    manifest = Phase4EngineManifest.model_validate_json(GATE2.read_bytes())
    row = prepare_campaign_plan(authority, manifest)[0]
    with pytest.raises(ValueError, match='PREPARATION_ONLY'):
        TrialRecord.from_reference(row, status='EXECUTED', reason='OK')
