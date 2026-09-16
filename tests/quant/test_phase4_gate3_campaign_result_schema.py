"""Artificial replay evidence only; no strategy generation or market-data reads."""
from dataclasses import replace
from importlib import import_module
from pathlib import Path
import json
import math
import subprocess

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]


def api():
    return import_module('investment_tracker.quant.phase4.gate3_campaign.validation')


def test_authoritative_validation_api_exists():
    try:
        module = api()
    except ModuleNotFoundError:
        pytest.fail('Missing additive authoritative result validation API')
    assert callable(module.validate_result)


@pytest.fixture(scope='module')
def case():
    v = api()
    from investment_tracker.quant.phase4.gate3_campaign.dependencies import load_dependencies, ResultAuthority
    from investment_tracker.quant.phase4.gate3_campaign.result_schema import CandidateResult, NeighborObservation
    from investment_tracker.quant.phase4.engine.market import MarketPanel
    from investment_tracker.quant.phase4.engine.execution import replay_targets
    from investment_tracker.quant.phase4.engine.benchmarks import cash_benchmark, equal_weight_buy_and_hold
    from investment_tracker.quant.phase4.engine.models import TargetInstruction
    deps = load_dependencies(ROOT)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    authority = ResultAuthority(deps, revision)
    binding = deps.bindings[0]
    sessions = deps.sessions
    # Artificial arithmetic path, explicitly unrelated to real ETF prices.
    prices = [100.0 * math.exp(0.0005 * i + 0.01 * math.sin(i)) for i in range(1008)]
    frame = pd.DataFrame({'SPY': prices}, index=pd.DatetimeIndex(sessions))
    panel = MarketPanel.from_frames(frame, frame, role='SCORED')

    def replay(b, bps=3):
        target = TargetInstruction(signal_timestamp=sessions[0], due_session=sessions[1], weights=(('SPY', 0.8),), binding=b)
        return replay_targets(panel, (target,) + (None,) * 1007, friction_bps=bps)

    neighbors = tuple(NeighborObservation(binding=b, status='AVAILABLE', reason='OK', replay=replay(b)) for b in deps.neighbors(binding))
    evidence = v.derive_evidence(tuple(replay(binding, bps) for bps in (0, 3, 10, 25, 50)), equal_weight_buy_and_hold(panel, friction_bps=3), cash_benchmark(panel), neighbors, deps)
    result = CandidateResult(provenance=v.make_provenance(authority, 1), status='EXECUTED', reason='OK', evidence=evidence)
    return authority, result


def test_complete_typed_result_roundtrip_and_projection(case):
    authority, result = case
    v = api()
    accepted = v.validate_result(result, authority)
    assert accepted == result
    projection = v.survivor_projection(result, authority)
    assert projection.status == 'AVAILABLE'
    assert projection.evidence.candidate_id == result.provenance.candidate_id
    assert projection.evidence.signal_component_count == 5
    assert projection.evidence.fixed_identity_invariant is True
    assert projection.evidence.durability_evidence_complete is True
    assert projection.evidence.max_drawdown is None
    assert len(result.evidence.regimes.regimes) == 3
    assert sum(r.return_observation_count for r in result.evidence.regimes.regimes) == 1007
    from investment_tracker.quant.phase4.gate3_campaign.codec import canonical_bytes, decode
    assert decode(type(result), canonical_bytes(result)) == result


@pytest.mark.parametrize('field,value', [
    ('population_position', 2), ('candidate_id', 'phase4-'+'0'*64), ('trial_id', '0'*64),
    ('family_id', 'phase4-family-'+'0'*64), ('hypothesis_id', 'wrong'),
    ('family_definition_sha256', '0'*64), ('rule_set_sha256', '0'*64),
    ('parameter_tuple_sha256', '0'*64), ('candidate_population_sha256', '0'*64),
    ('source_revision', '0'*40), ('engine_implementation_sha256', '0'*64),
    ('evaluation_context_sha256', '0'*64),
])
def test_identity_substitution_rejected(case, field, value):
    authority, result = case
    forged = result.model_copy(update={'provenance': result.provenance.model_copy(update={field: value})})
    with pytest.raises(ValueError):
        api().validate_result(forged, authority)


@pytest.mark.parametrize('field', ['gate1_manifest', 'gate2_manifest', 'gate3_manifest', 'execution_methodology'])
def test_manifest_identity_substitution_rejected(case, field):
    authority, result = case
    original = getattr(result.provenance, field)
    provenance = result.provenance.model_copy(update={field: original.model_copy(update={'content_sha256': '0'*64})})
    with pytest.raises(ValueError):
        api().validate_result(result.model_copy(update={'provenance': provenance}), authority)


@pytest.mark.parametrize('mutation', ['generic', 'extra', 'missing', 'string_position', 'bool_position', 'nonfinite', 'string_metric'])
def test_strict_wire_boundary_rejects_untyped_or_coerced_evidence(case, mutation):
    authority, result = case
    from investment_tracker.quant.phase4.gate3_campaign.codec import canonical_bytes, decode
    document = json.loads(canonical_bytes(result))
    if mutation == 'generic': document['evidence'] = {'result': 1}
    if mutation == 'extra': document['winner'] = True
    if mutation == 'missing': del document['evidence']['durability']
    if mutation == 'string_position': document['provenance']['population_position'] = '1'
    if mutation == 'bool_position': document['provenance']['population_position'] = True
    if mutation == 'nonfinite': document['evidence']['metrics']['total_return']['value'] = float('nan')
    if mutation == 'string_metric': document['evidence']['metrics']['total_return']['value'] = '0.3'
    with pytest.raises((ValueError, TypeError)):
        api().validate_result(decode(type(result), json.dumps(document).encode()), authority)


@pytest.mark.parametrize('field', ['max_drawdown', 'calmar', 'dsr', 'pbo'])
def test_numeric_unavailable_statistic_rejected(case, field):
    authority, result = case
    stats = result.evidence.metrics.unavailable_statistics.model_copy(update={field: 0.0})
    metrics = result.evidence.metrics.model_copy(update={'unavailable_statistics': stats})
    forged = result.model_copy(update={'evidence': result.evidence.model_copy(update={'metrics': metrics})})
    with pytest.raises(ValueError): api().validate_result(forged, authority)


@pytest.mark.parametrize('component,field,value', [
    ('bootstrap', 'seed', 1), ('bootstrap', 'n_bootstrap_draws', 1999),
    ('bootstrap', 'sample_size', 1008), ('candidate_folds', 'fold_ids', ('FOLD_2019',)*4),
    ('durability', 'month_period_labels', ()),
])
def test_component_contract_mutations_rejected(case, component, field, value):
    authority, result = case
    original = getattr(result.evidence, component)
    changed = original.model_copy(update={field: value})
    with pytest.raises(ValueError):
        api().validate_result(result.model_copy(update={'evidence': result.evidence.model_copy(update={component: changed})}), authority)


@pytest.mark.parametrize('target', ['metric', 'retention', 'bootstrap', 'neighbor', 'regime', 'fold', 'durability', 'turnover', 'context'])
def test_derived_values_cannot_override_underlying_evidence(case, target):
    authority, result = case
    ev = result.evidence
    metric = ev.metrics.total_return.model_copy(update={'value': 99.0})
    if target == 'metric': ev = ev.model_copy(update={'metrics': ev.metrics.model_copy(update={'total_return': metric})})
    if target == 'retention': ev = ev.model_copy(update={'friction': ev.friction.model_copy(update={'friction_retention_ratio': metric})})
    if target == 'bootstrap': ev = ev.model_copy(update={'bootstrap': ev.bootstrap.model_copy(update={'percentile_05': metric})})
    if target == 'neighbor': ev = ev.model_copy(update={'neighbors': ev.neighbors + ev.neighbors[:1]})
    if target == 'regime': ev = ev.model_copy(update={'regimes': ev.regimes.model_copy(update={'first_session_return': 0.0})})
    if target == 'fold': ev = ev.model_copy(update={'candidate_folds': ev.candidate_folds.model_copy(update={'fold_returns': (metric,)*4})})
    if target == 'durability': ev = ev.model_copy(update={'durability': ev.durability.model_copy(update={'positive_month_fraction': metric})})
    if target == 'turnover': ev = ev.model_copy(update={'replays': (ev.replays[0].model_copy(update={'total_turnover': 0.0}),)+ev.replays[1:]})
    if target == 'context': ev = ev.model_copy(update={'primary_replay_sha256': '0'*64})
    with pytest.raises(ValueError): api().validate_result(result.model_copy(update={'evidence': ev}), authority)


def test_missing_friction_case_and_wrong_case_binding_rejected(case):
    authority, result = case
    with pytest.raises(ValueError):
        api().validate_result(result.model_copy(update={'evidence': result.evidence.model_copy(update={'replays': result.evidence.replays[:-1]})}), authority)
    bad = result.evidence.replays[0].model_copy(update={'candidate_id': authority.dependencies.bindings[1].candidate_id})
    with pytest.raises(ValueError):
        api().validate_result(result.model_copy(update={'evidence': result.evidence.model_copy(update={'replays': (bad,)+result.evidence.replays[1:]})}), authority)


def test_insufficient_neighbors_preserve_unknown_and_known_primary_oos(case):
    authority, result = case
    unavailable = tuple(n.model_copy(update={'status': 'UNKNOWN', 'reason': 'MISSING_PRIMARY', 'replay': None}) for n in result.evidence.neighbors)
    v = api()
    ev = v.derive_evidence(result.evidence.replays, result.evidence.benchmark, result.evidence.cash, unavailable, authority.dependencies)
    changed = result.model_copy(update={'evidence': ev})
    projected = v.survivor_projection(changed, authority)
    assert projected.status == 'UNKNOWN'
    assert 'INSUFFICIENT_VALID_NEIGHBORS' in projected.reasons
    assert projected.evidence is None
    assert v.oos_outcome(changed).benchmark_excess_return == result.evidence.metrics.benchmark_excess_return.value


@pytest.mark.parametrize('status', ['UNKNOWN', 'ABSTAIN', 'CAMPAIGN_EXECUTION_FAILED', 'SKIPPED_FAMILY_STOP'])
def test_unavailable_statuses_cannot_carry_fabricated_metrics(case, status):
    authority, result = case
    with pytest.raises(ValueError): api().validate_result(result.model_copy(update={'status': status}), authority)


def test_system_failure_and_skip_never_become_oos_research_failure(case):
    authority, result = case
    failed = result.model_copy(update={'status': 'CAMPAIGN_EXECUTION_FAILED', 'reason': 'SYSTEM_ERROR', 'evidence': None})
    assert api().validate_result(failed, authority).status == 'CAMPAIGN_EXECUTION_FAILED'
    with pytest.raises(ValueError, match='CAMPAIGN_EXECUTION_FAILED'): api().oos_outcome(failed)
    skipped = failed.model_copy(update={'status': 'SKIPPED_FAMILY_STOP'})
    with pytest.raises(ValueError, match='SKIPPED_NOT_OBSERVATION'): api().oos_outcome(skipped)


def test_unavailable_observations_have_no_numeric_result(case):
    authority, result = case
    for status in ('UNKNOWN', 'ABSTAIN'):
        row = result.model_copy(update={'status': status, 'reason': 'MISSING_PRIMARY', 'evidence': None})
        assert api().validate_result(row, authority).status == status
        assert api().oos_outcome(row).benchmark_excess_return is None


def test_baseline_identity_cannot_validate_as_candidate(case):
    authority, result = case
    baseline_id = authority.dependencies.gate2.baselines.baselines[0].baseline_id
    with pytest.raises(ValueError):
        api().validate_result(result.model_copy(update={'provenance': result.provenance.model_copy(update={'candidate_id': baseline_id})}), authority)
