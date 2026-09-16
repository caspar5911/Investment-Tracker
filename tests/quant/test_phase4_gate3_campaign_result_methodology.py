from importlib import import_module
from hashlib import sha256
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def api():
    return import_module('investment_tracker.quant.phase4.gate3_campaign.result_methodology')


def test_result_schema_methodology_api_exists():
    try:
        module = api()
    except ModuleNotFoundError:
        pytest.fail('Missing result-schema methodology authority')
    assert callable(module.preflight_result_schema)


def test_spec_contract_and_dependency_bindings_are_exact():
    module = api()
    spec = module.spec_identity(ROOT)
    assert spec.content_sha256 == module.SPEC_CONTENT_SHA256
    contract = module.schema_contract(ROOT)
    assert contract['schema_version'] == 'PHASE4-GATE3-RESULT-SCHEMA-CONTRACT-v1'
    assert contract['candidate_result_schema'] == 'PHASE4-GATE3-CANDIDATE-RESULT-v1'
    assert contract['survivor_hard_gate_count'] == 12
    assert contract['survivor_ordering_key_count'] == 22
    assert contract['authoritative_generic_result_dict'] is False
    assert contract['campaign_execution_entrypoint'] is False
    assert contract['decision_grade'] is False
    assert contract['replay_valuation_authority'] == 'FROZEN_SCORED_MARKET_PANEL'
    assert len(contract['scored_market_panel_sha256']) == 64
    assert contract['dq030'] == {'max_drawdown':'UNKNOWN','calmar':'UNKNOWN','dsr':'UNKNOWN/NOT_IMPLEMENTED','pbo':'UNKNOWN/NOT_IMPLEMENTED'}


def test_manifest_rejects_any_policy_or_prior_authority_substitution():
    module = api()
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    # Current commit may not yet contain uncommitted Task 3 files; use structural build without source bundle.
    manifest = module.declared_manifest(ROOT, revision, source_bundle=None)
    for field in ('gate1_manifest','gate2_manifest','gate3_authority_manifest','execution_methodology','survivor_policy','durability_policy','family_stop_policy_container'):
        original = getattr(manifest, field)
        forged = manifest.model_copy(update={field: original.model_copy(update={'content_sha256':'0'*64})})
        with pytest.raises(ValueError, match='RESULT_SCHEMA_DEPENDENCY_MISMATCH'):
            module.validate_declared_manifest(ROOT, forged, require_source=False)


def test_preflight_requires_explicit_hash_and_never_discovers_latest():
    for digest in ('latest','0'*64):
        with pytest.raises(ValueError, match='RESULT_SCHEMA_MANIFEST_MISSING'):
            api().preflight_result_schema(ROOT, digest)


def test_cli_defines_only_seal_and_preflight(monkeypatch):
    cli = import_module('investment_tracker.quant.phase4.gate3_campaign.cli')
    with pytest.raises(SystemExit):
        cli.main(['run-campaign'])
    with pytest.raises(SystemExit):
        cli.main(['select-survivor'])


def test_old_execution_methodology_source_bundle_still_preflights():
    from investment_tracker.quant.phase4.gate3_execution.methodology import preflight_execution_methodology
    state = preflight_execution_methodology(ROOT, '9c37e20ccc54132716c3e347b8005d097500a14aeba41d9eedeaf28de3ebe877')
    assert state.gate3 == 'GATE3_CAMPAIGN_READY_TO_EXECUTE'


def test_source_validation_rejects_cross_worktree_import_even_with_identical_bytes(
    monkeypatch, tmp_path
):
    module = api()
    bundle = SimpleNamespace(entries=tuple(
        SimpleNamespace(path=relative, content_sha256=sha256((ROOT / relative).read_bytes()).hexdigest())
        for relative in module.SOURCE_FILES
    ))
    imported = import_module('investment_tracker.quant.phase4.gate3_campaign.validation')
    foreign = tmp_path / 'validation.py'
    foreign.write_bytes(Path(imported.__file__).read_bytes())
    monkeypatch.setattr(imported, '__file__', str(foreign))

    with pytest.raises(ValueError, match='RESULT_SCHEMA_SOURCE_MISMATCH'):
        module._verify_imported_sources(ROOT, bundle)
