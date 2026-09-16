"""Authoritative validation and deterministic projection of candidate evidence."""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import math
from statistics import median

import pandas as pd

from investment_tracker.quant.phase4.engine.durability import calculate_durability, expected_session_identity
from investment_tracker.quant.phase4.engine.metrics import calculate_metrics
from investment_tracker.quant.phase4.engine.models import (
    ExpectedSessionAuthority, FoldAuthority, FrictionCaseEvidence, FrictionEvidence,
    MetricValue, PortfolioReplay, UnavailableStatistics,
)
from investment_tracker.quant.phase4.engine.robustness import bootstrap_median_daily_return, slice_continuous_folds
from investment_tracker.quant.phase4.gate3.authorities import FOLD_IDS, REGIME_IDS, SYMBOLS
from investment_tracker.quant.phase4.gate3.seal import GATE1_MANIFEST_IDENTITY, GATE2_MANIFEST_IDENTITY, TRAIN_IDENTITY, VALIDATION_IDENTITY
from investment_tracker.quant.phase4.gate3_execution.campaign import POPULATION_SHA256
from investment_tracker.quant.phase4.gate3_execution.methodology import CORRECTED_GATE3_MANIFEST
from investment_tracker.quant.phase4.gate3_execution.regimes import attribute_regime_returns
from investment_tracker.quant.phase4.preregistration.canonical import canonical_sha256
from investment_tracker.quant.phase4.preregistration.policy import CandidateOOSOutcome, CandidateSurvivorEvidence

from .codec import canonical_bytes, digest, hydrate
from .dependencies import Dependencies, ResultAuthority
from .result_schema import (
    CandidateResult, ExecutedEvidence, NeighborObservation, NeighborSummary,
    Provenance, RegimeEvidence, RegimeRow, SurvivorProjection,
)

_TOL = 1e-9


def _available(value: float) -> MetricValue:
    return MetricValue(value=float(value), status='AVAILABLE', reason='OK')


def _same(left, right) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _fold_authority(sessions: tuple[pd.Timestamp, ...]) -> FoldAuthority:
    by_year = {year: tuple(s for s in sessions if s.year == year) for year in range(2019, 2023)}
    ends = tuple(by_year[year][-1] for year in range(2019, 2023))
    return FoldAuthority(fold_ids=FOLD_IDS, boundaries=((sessions[0], ends[0]), (ends[0], ends[1]), (ends[1], ends[2]), (ends[2], ends[3])))


def _expected(sessions: tuple[pd.Timestamp, ...]) -> ExpectedSessionAuthority:
    return ExpectedSessionAuthority(sessions=sessions, sha256=expected_session_identity(sessions))


def _validate_replay(replay: PortfolioReplay, *, binding, sessions, friction_bps: int, benchmark: bool = False) -> None:
    if replay.sessions != sessions or replay.initial_cash != 100000.0 or replay.friction_bps != friction_bps:
        raise ValueError('REPLAY_CONTEXT_MISMATCH')
    if benchmark:
        if replay.candidate_id is not None or replay.binding_sha256 is not None:
            raise ValueError('BENCHMARK_IDENTITY_LEAK')
    elif replay.candidate_id != binding.candidate_id or replay.binding_sha256 != binding.binding_sha256:
        raise ValueError('REPLAY_BINDING_MISMATCH')
    allowed_symbols = frozenset(SYMBOLS)
    if any(fill.symbol not in allowed_symbols for fill in replay.fills) or any(
        symbol not in allowed_symbols for state in replay.states for symbol, _ in state.units
    ):
        raise ValueError('REPLAY_SYMBOL_INVALID')
    session_index = {session: index for index, session in enumerate(sessions)}
    turnover = math.fsum(abs(fill.fill_notional) for fill in replay.fills)
    if not math.isclose(replay.total_turnover, turnover, rel_tol=1e-12, abs_tol=_TOL):
        raise ValueError('TURNOVER_LINKAGE_INVALID')
    cash = replay.initial_cash
    units: dict[str, float] = {}
    fills = iter(replay.fills)
    current = next(fills, None)
    previous_session = None
    for state in replay.states:
        while current is not None and current.fill_timestamp == state.session:
            if (
                current.signal_timestamp not in session_index
                or current.fill_timestamp not in session_index
                or session_index[current.fill_timestamp] != session_index[current.signal_timestamp] + 1
            ):
                raise ValueError('FILL_NEXT_SESSION_INVALID')
            expected_notional = current.units_delta * current.reference_open
            if not math.isclose(current.fill_notional, expected_notional, rel_tol=1e-12, abs_tol=_TOL):
                raise ValueError('FILL_NOTIONAL_INVALID')
            expected_friction = abs(current.fill_notional) * friction_bps / 10000.0
            if not math.isclose(current.friction, expected_friction, rel_tol=1e-12, abs_tol=_TOL):
                raise ValueError('FILL_FRICTION_INVALID')
            cash -= current.fill_notional + current.friction
            units[current.symbol] = units.get(current.symbol, 0.0) + current.units_delta
            if cash < -_TOL:
                raise ValueError('NEGATIVE_DERIVED_CASH')
            if units[current.symbol] < -_TOL:
                raise ValueError('NEGATIVE_DERIVED_UNITS')
            if abs(units[current.symbol]) <= 1e-12:
                del units[current.symbol]
            current = next(fills, None)
        if current is not None and current.fill_timestamp < state.session:
            raise ValueError('FILL_ORDER_INVALID')
        expected_units = tuple(sorted(units.items()))
        if len(expected_units) != len(state.units) or any(a != b or not math.isclose(x, y, rel_tol=1e-12, abs_tol=_TOL) for (a, x), (b, y) in zip(expected_units, state.units, strict=True)):
            raise ValueError('UNIT_LINKAGE_INVALID')
        expected_cash = 0.0 if -_TOL <= cash < 0.0 else cash
        if not math.isclose(state.cash, expected_cash, rel_tol=1e-12, abs_tol=_TOL):
            raise ValueError('CASH_LINKAGE_INVALID')
        realized = (state.close_equity - state.cash) / state.close_equity
        if not math.isclose(state.realized_gross_exposure, realized, rel_tol=1e-12, abs_tol=_TOL):
            raise ValueError('EXPOSURE_LINKAGE_INVALID')
        if previous_session is not None and state.session <= previous_session:
            raise ValueError('SESSION_ORDER_INVALID')
        previous_session = state.session
    if current is not None:
        raise ValueError('UNACCOUNTED_FILL')


def _validate_equal_weight_benchmark(replay: PortfolioReplay, sessions: tuple[pd.Timestamp, ...]) -> None:
    expected_symbols = tuple(sorted(SYMBOLS))
    if len(replay.fills) != len(expected_symbols):
        raise ValueError('BENCHMARK_METHOD_INVALID')
    if tuple(fill.symbol for fill in replay.fills) != expected_symbols:
        raise ValueError('BENCHMARK_METHOD_INVALID')
    if any(fill.signal_timestamp != sessions[0] or fill.fill_timestamp != sessions[1] or fill.units_delta <= 0 for fill in replay.fills):
        raise ValueError('BENCHMARK_METHOD_INVALID')
    notionals = tuple(fill.fill_notional for fill in replay.fills)
    if any(value <= 0 or not math.isclose(value, notionals[0], rel_tol=1e-12, abs_tol=_TOL) for value in notionals):
        raise ValueError('BENCHMARK_METHOD_INVALID')
    first = replay.states[0]
    if first.cash != 100000.0 or first.units or first.realized_gross_exposure != 0.0:
        raise ValueError('BENCHMARK_METHOD_INVALID')
    if any(not math.isclose(state.target_gross_exposure, 1.0, rel_tol=0.0, abs_tol=1e-12) for state in replay.states):
        raise ValueError('BENCHMARK_METHOD_INVALID')


def _friction(replays: tuple[PortfolioReplay, ...]) -> FrictionEvidence:
    cases = tuple(FrictionCaseEvidence(
        friction_bps=replay.friction_bps, candidate_id=replay.candidate_id,
        binding_sha256=replay.binding_sha256,
        total_return=_available(replay.close_equity[-1] / replay.close_equity[0] - 1.0),
        total_turnover=_available(replay.total_turnover), close_equity=replay.close_equity,
        unavailable_statistics=UnavailableStatistics(),
    ) for replay in replays)
    denominator = cases[1].total_return.value
    numerator = cases[3].total_return.value
    ratio = MetricValue(value=None, status='UNKNOWN', reason='NONPOSITIVE_DENOMINATOR') if denominator is None or denominator == 0 else _available(numerator / denominator)
    return FrictionEvidence(candidate_id=replays[0].candidate_id, binding_sha256=replays[0].binding_sha256,
                            cases=cases, friction_retention_ratio=ratio, unavailable_statistics=UnavailableStatistics())


def _regimes(replay: PortfolioReplay, deps: Dependencies) -> RegimeEvidence:
    result = attribute_regime_returns(replay, deps.regime)
    return RegimeEvidence(first_session_label=result.first_session_label, first_session_return=None,
                          regimes=tuple(RegimeRow(**asdict(row)) for row in result.regimes))


def _neighborhood(observations: tuple[NeighborObservation, ...], benchmark: PortfolioReplay, deps: Dependencies, binding) -> NeighborSummary:
    expected = deps.neighbors(binding)
    if tuple(item.binding.trial_id for item in observations) != tuple(item.trial_id for item in expected):
        raise ValueError('NEIGHBOR_MEMBERSHIP_INVALID')
    metrics = []
    for item in observations:
        if item.binding not in expected:
            raise ValueError('NEIGHBOR_BINDING_INVALID')
        if item.replay is not None:
            _validate_replay(item.replay, binding=item.binding, sessions=deps.sessions, friction_bps=3)
            metrics.append(calculate_metrics(item.replay, benchmark))
    valid = [m for m in metrics if m.total_return.value is not None and m.benchmark_excess_return.value is not None]
    positive = sum(m.total_return.value > 0 for m in valid)
    if len(valid) < 2:
        return NeighborSummary(valid_count=len(valid), positive_count=positive, positive_fraction=None,
                               median_benchmark_excess=None, status='UNKNOWN', reason='INSUFFICIENT_VALID_NEIGHBORS', metrics=tuple(metrics))
    return NeighborSummary(valid_count=len(valid), positive_count=positive, positive_fraction=positive / len(valid),
                           median_benchmark_excess=median(m.benchmark_excess_return.value for m in valid),
                           status='AVAILABLE', reason='OK', metrics=tuple(metrics))


def derive_evidence(replays, benchmark, cash, neighbors, deps: Dependencies) -> ExecutedEvidence:
    replays = tuple(replays); neighbors = tuple(neighbors)
    if tuple(r.friction_bps for r in replays) != (0, 3, 10, 25, 50):
        raise ValueError('FRICTION_CASES_INVALID')
    binding = next(b for b in deps.bindings if b.candidate_id == replays[0].candidate_id)
    for replay in replays:
        _validate_replay(replay, binding=binding, sessions=deps.sessions, friction_bps=replay.friction_bps)
    _validate_replay(benchmark, binding=None, sessions=deps.sessions, friction_bps=3, benchmark=True)
    _validate_equal_weight_benchmark(benchmark, deps.sessions)
    _validate_replay(cash, binding=None, sessions=deps.sessions, friction_bps=0, benchmark=True)
    if cash.fills or cash.total_turnover != 0 or any(state.cash != 100000.0 or state.close_equity != 100000.0 for state in cash.states):
        raise ValueError('CASH_BENCHMARK_INVALID')
    primary = replays[1]
    metrics = calculate_metrics(primary, benchmark)
    durability = calculate_durability(primary, _expected(deps.sessions), horizons=(12, 36))
    fold_authority = _fold_authority(deps.sessions)
    candidate_folds = slice_continuous_folds(primary, fold_authority)
    benchmark_folds = slice_continuous_folds(benchmark, fold_authority)
    neighborhood = _neighborhood(neighbors, benchmark, deps, binding)
    bootstrap = bootstrap_median_daily_return(primary.daily_returns)
    return ExecutedEvidence(
        replays=replays, benchmark=benchmark, cash=cash, primary_replay_sha256=digest(primary),
        bootstrap_input_sha256=canonical_sha256({'schema_version':'PHASE4-BOOTSTRAP-INPUT-v1','returns':[float(v).hex() for v in primary.daily_returns]}),
        metrics=metrics, durability=durability, candidate_folds=candidate_folds,
        benchmark_folds=benchmark_folds, regimes=_regimes(primary, deps), friction=_friction(replays),
        neighbors=neighbors, neighborhood=neighborhood, bootstrap=bootstrap,
    )


def _context(provenance: dict) -> str:
    return canonical_sha256({'schema_version':'PHASE4-GATE3-RESULT-CONTEXT-v1', **{k:v for k,v in provenance.items() if k != 'evaluation_context_sha256'}})


def make_provenance(authority: ResultAuthority, position: int) -> Provenance:
    deps = authority.dependencies
    binding = deps.bindings[position - 1]
    values = dict(campaign_id=binding.campaign_id, population_position=position, candidate_id=binding.candidate_id,
                  trial_id=binding.trial_id, family_id=binding.family_id, hypothesis_id=binding.hypothesis_id,
                  family_definition_sha256=binding.family_definition_sha256, rule_set_sha256=binding.rule_set_sha256,
                  parameter_tuple_sha256=binding.parameter_tuple_sha256, candidate_population_sha256=POPULATION_SHA256,
                  train_identity=TRAIN_IDENTITY, validation_identity=VALIDATION_IDENTITY,
                  gate1_manifest=GATE1_MANIFEST_IDENTITY, gate2_manifest=GATE2_MANIFEST_IDENTITY,
                  gate3_manifest=CORRECTED_GATE3_MANIFEST, execution_methodology=deps.execution,
                  engine_implementation_sha256=deps.engine_sha256, source_revision=authority.source_revision,
                  initial_cash=100000.0, primary_friction_bps=3,
                  execution_convention='COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN', execution_series='QFQ_NORMALIZED', decision_grade=False)
    values['evaluation_context_sha256'] = _context({k:(v.model_dump(mode='json') if hasattr(v,'model_dump') else v) for k,v in values.items()})
    return Provenance(**values)


def _metric(metric, reason, reasons):
    if metric.status != 'AVAILABLE' or metric.value is None:
        reasons.append(reason)
        return None
    return metric.value


def survivor_projection(result: CandidateResult, authority: ResultAuthority) -> SurvivorProjection:
    if result.status != 'EXECUTED' or result.evidence is None:
        return SurvivorProjection(status='UNKNOWN', reasons=('PRIMARY_EVIDENCE_UNAVAILABLE',), evidence=None)
    ev = result.evidence; reasons=[]
    total = _metric(ev.metrics.total_return,'TOTAL_RETURN_UNKNOWN',reasons)
    cagr = _metric(ev.metrics.cagr,'CAGR_UNKNOWN',reasons)
    sharpe = _metric(ev.metrics.sharpe,'SHARPE_UNKNOWN',reasons)
    sortino = _metric(ev.metrics.sortino,'SORTINO_UNKNOWN',reasons)
    excess = _metric(ev.metrics.benchmark_excess_return,'BENCHMARK_EXCESS_UNKNOWN',reasons)
    turnover = _metric(ev.metrics.annualized_one_way_turnover,'TURNOVER_UNKNOWN',reasons)
    exposure = _metric(ev.metrics.average_realized_gross_exposure,'EXPOSURE_UNKNOWN',reasons)
    years = _metric(ev.durability.positive_year_fraction,'POSITIVE_YEARS_UNKNOWN',reasons)
    r36 = _metric(ev.durability.rolling_36.minimum,'ROLLING_36_UNKNOWN',reasons)
    r12 = _metric(ev.durability.rolling_12.minimum,'ROLLING_12_UNKNOWN',reasons)
    streak = _metric(ev.durability.longest_negative_month_streak,'LOSING_STREAK_UNKNOWN',reasons)
    worst_year = _metric(ev.durability.worst_year,'WORST_YEAR_UNKNOWN',reasons)
    worst_month = _metric(ev.durability.worst_month,'WORST_MONTH_UNKNOWN',reasons)
    year_conc = _metric(ev.durability.positive_year_concentration,'YEAR_CONCENTRATION_UNKNOWN',reasons)
    month3 = _metric(ev.durability.top_three_positive_month_concentration,'MONTH_CONCENTRATION_UNKNOWN',reasons)
    months = _metric(ev.durability.positive_month_fraction,'POSITIVE_MONTHS_UNKNOWN',reasons)
    lower = _metric(ev.bootstrap.percentile_05,'BOOTSTRAP_UNKNOWN',reasons)
    retention = _metric(ev.friction.friction_retention_ratio,'FRICTION_RETENTION_UNKNOWN',reasons)
    fold_values = [item.value for item in ev.candidate_folds.fold_returns]
    benchmark_values = [item.value for item in ev.benchmark_folds.fold_returns]
    if any(value is None for value in (*fold_values,*benchmark_values)):
        reasons.append('FOLD_EVIDENCE_UNKNOWN')
    if ev.neighborhood.status != 'AVAILABLE': reasons.append('INSUFFICIENT_VALID_NEIGHBORS')
    if reasons:
        return SurvivorProjection(status='UNKNOWN', reasons=tuple(sorted(set(reasons))), evidence=None)
    binding = authority.dependencies.bindings[result.provenance.population_position-1]
    family = next(f for f in authority.dependencies.gate2.family_definitions if f.family_id == binding.family_id)
    folds=tuple(float(v) for v in fold_values); fold_excess=tuple(float(a-b) for a,b in zip(fold_values,benchmark_values,strict=True))
    evidence = CandidateSurvivorEvidence(
        candidate_id=binding.candidate_id,is_baseline=False,validation_total_return=total,
        cash_return=ev.cash.close_equity[-1]/ev.cash.close_equity[0]-1,benchmark_excess_return=excess,
        sharpe=sharpe,sortino=sortino,walk_forward_returns=folds,walk_forward_benchmark_excess=fold_excess,
        neighborhood_valid_count=ev.neighborhood.valid_count,neighborhood_positive_fraction=ev.neighborhood.positive_fraction,
        neighborhood_median_benchmark_excess=ev.neighborhood.median_benchmark_excess,
        friction_returns_bps={case.friction_bps:case.total_return.value for case in ev.friction.cases},
        annualized_one_way_turnover=turnover,average_gross_exposure=exposure,
        all_session_exposures_valid=all(0<=x<=1 for x in (*ev.metrics.target_gross_exposure_series,*ev.metrics.realized_gross_exposure_series)),
        bootstrap_lower_endpoint=lower,fixed_identity_invariant=True,durability_evidence_complete=True,
        walk_forward_joint_consistency=sum(a>0 and b>0 for a,b in zip(folds,fold_excess,strict=True)),
        positive_year_percentage=years,minimum_rolling_36_month_return=r36,minimum_rolling_12_month_return=r12,
        longest_losing_month_sequence=int(streak),worst_year=worst_year,worst_month=worst_month,
        positive_year_return_concentration=year_conc,top_three_positive_month_return_concentration=month3,
        positive_month_percentage=months,friction_25bps_retention_ratio=retention,
        signal_component_count=family.component_count,cagr=cagr,max_drawdown=None,calmar=None,dsr=None,pbo=None)
    return SurvivorProjection(status='AVAILABLE', reasons=(), evidence=evidence)


def _validate_provenance(result, authority):
    expected = make_provenance(authority, result.provenance.population_position)
    if result.provenance != expected:
        raise ValueError('RESULT_PROVENANCE_MISMATCH')


def validate_result(result: CandidateResult, authority: ResultAuthority, resolver=None) -> CandidateResult:
    if not isinstance(authority, ResultAuthority): raise ValueError('RESULT_AUTHORITY_REQUIRED')
    result = hydrate(CandidateResult, result)
    _validate_provenance(result, authority)
    if result.status == 'EXECUTED':
        ev = derive_evidence(result.evidence.replays, result.evidence.benchmark, result.evidence.cash,
                             result.evidence.neighbors, authority.dependencies)
        if not _same(ev, result.evidence): raise ValueError('DERIVED_EVIDENCE_MISMATCH')
        projection = survivor_projection(result.model_copy(update={'evidence':ev,'stored_projection':None}), authority)
        if result.stored_projection is not None and not _same(result.stored_projection, projection):
            raise ValueError('SURVIVOR_PROJECTION_MISMATCH')
    elif result.status == 'SKIPPED_FAMILY_STOP':
        if result.reason != 'PERSISTENT_OOS_FAILURE':
            raise ValueError('STOP_REASON_INVALID')
        if resolver is None: raise ValueError('STOP_WITNESS_UNRESOLVED')
        resolved = tuple(resolver(identity) for identity in result.stop_witness.prior_results)
        trigger = result.stop_witness.trigger_position
        positions = tuple(row.provenance.population_position for row in resolved)
        if len(resolved)!=50 or positions != tuple(range(trigger-49,trigger+1)) or trigger >= result.provenance.population_position:
            raise ValueError('STOP_WITNESS_INVALID')
        if any(row.provenance.family_id != result.provenance.family_id or row.status not in ('EXECUTED','UNKNOWN','ABSTAIN') for row in resolved):
            raise ValueError('STOP_WITNESS_INVALID')
        if any((outcome:=oos_outcome(row)).benchmark_excess_return is not None and outcome.benchmark_excess_return>0 for row in resolved):
            raise ValueError('STOP_WITNESS_INVALID')
    return result


def oos_outcome(result: CandidateResult) -> CandidateOOSOutcome:
    if result.status == 'CAMPAIGN_EXECUTION_FAILED': raise ValueError('CAMPAIGN_EXECUTION_FAILED')
    if result.status == 'SKIPPED_FAMILY_STOP': raise ValueError('SKIPPED_NOT_OBSERVATION')
    if result.status in ('UNKNOWN','ABSTAIN'): return CandidateOOSOutcome(benchmark_excess_return=None)
    value = result.evidence.metrics.benchmark_excess_return.value
    return CandidateOOSOutcome(benchmark_excess_return=value)
