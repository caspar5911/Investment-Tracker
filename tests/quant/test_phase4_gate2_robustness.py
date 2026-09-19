from __future__ import annotations

from importlib import import_module
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from investment_tracker.quant.phase4.engine.market import MarketPanel
from investment_tracker.quant.phase4.engine.models import Gate2SealError

try:
    _robustness_module = import_module(
        "investment_tracker.quant.phase4.engine.robustness"
    )
    from investment_tracker.quant.phase4.engine.robustness import (
        bootstrap_median_daily_return,
        neighbor_trial_ids,
        partition_regimes,
        run_friction_cases,
        slice_continuous_folds,
    )
    from investment_tracker.quant.phase4.engine.models import (
        BootstrapEvidence,
        FoldAuthority,
        FrictionEvidence,
        RegimeAuthority,
    )

    _ROBUSTNESS_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as exc:
    _robustness_module = None
    bootstrap_median_daily_return = None
    neighbor_trial_ids = None
    partition_regimes = None
    run_friction_cases = None
    slice_continuous_folds = None
    BootstrapEvidence = None
    FoldAuthority = None
    FrictionEvidence = None
    RegimeAuthority = None
    _ROBUSTNESS_IMPORT_ERROR = exc


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def require_robustness_types(request: pytest.FixtureRequest) -> None:
    if (
        request.node.name != "test_robustness_types_are_available"
        and _ROBUSTNESS_IMPORT_ERROR is not None
    ):
        pytest.skip("robustness types are not implemented yet")


@pytest.fixture(scope="module")
def authority():
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )

    return load_gate2_authority(REPOSITORY_ROOT)


def _binding(authority) -> object:
    family = authority.family_definitions[0]
    candidate = family.candidates[0]
    from investment_tracker.quant.phase4.engine.models import FixedStrategyBinding

    return FixedStrategyBinding.from_authority(
        authority, candidate.candidate_id, "a" * 64
    )


def _sessions(start: str, *, periods: int) -> pd.DatetimeIndex:
    return pd.date_range(start, periods=periods, freq="D", tz="UTC")


def _scored(
    opens: dict[str, list[float]],
    closes: dict[str, list[float]],
    *,
    start: str = "2024-01-01",
) -> MarketPanel:
    symbols = tuple(sorted(opens))
    periods = len(next(iter(opens.values())))
    index = _sessions(start, periods=periods)
    open_frame = pd.DataFrame(
        {symbol: np.asarray(opens[symbol], dtype=np.float64) for symbol in symbols},
        index=index,
    )
    close_frame = pd.DataFrame(
        {symbol: np.asarray(closes[symbol], dtype=np.float64) for symbol in symbols},
        index=index,
    )
    return MarketPanel.from_frames(open_frame, close_frame, role="SCORED")


def _target(binding: object, signal, due, weights) -> object:
    from investment_tracker.quant.phase4.engine.models import TargetInstruction

    return TargetInstruction(
        signal_timestamp=signal,
        due_session=due,
        weights=weights,
        binding=binding,
    )


def _replay(authority, *, start="2024-01-01", periods=6):
    from investment_tracker.quant.phase4.engine.execution import replay_targets

    binding = _binding(authority)
    sessions = _sessions(start, periods=periods)
    opens = {"AAA": [10.0 + i for i in range(periods)]}
    closes = {"AAA": [11.0 + i for i in range(periods)]}
    scored = _scored(opens, closes, start=start)
    pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))
    targets = [pending] + [None] * (periods - 1)
    return sessions, replay_targets(scored, targets, friction_bps=3)


def test_robustness_types_are_available() -> None:
    assert _ROBUSTNESS_IMPORT_ERROR is None
    assert inspect.isfunction(run_friction_cases)
    assert inspect.isfunction(bootstrap_median_daily_return)
    assert inspect.isfunction(neighbor_trial_ids)
    assert inspect.isfunction(slice_continuous_folds)
    assert inspect.isfunction(partition_regimes)
    assert inspect.isclass(FrictionEvidence)
    assert inspect.isclass(BootstrapEvidence)


def test_friction_cases_cover_exact_set_and_primary_is_three(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=4)
    scored_panel = _scored(
        {"AAA": [10.0, 12.0, 15.0, 18.0]},
        {"AAA": [11.0, 13.0, 16.0, 19.0]},
    )
    pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))
    evidence = run_friction_cases(scored_panel, [pending, None, None, None])

    assert isinstance(evidence, FrictionEvidence)
    assert [case.friction_bps for case in evidence.cases] == [0, 3, 10, 25, 50]
    assert evidence.primary_bps == 3
    # identity-preserving across all friction cases
    assert len({case.candidate_id for case in evidence.cases}) == 1
    assert len({case.binding_sha256 for case in evidence.cases}) == 1
    assert evidence.candidate_id == binding.candidate_id


def test_friction_retention_ratio_is_25_over_3(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=4)
    scored = _scored(
        {"AAA": [10.0, 12.0, 15.0, 18.0]},
        {"AAA": [11.0, 13.0, 16.0, 19.0]},
    )
    pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))
    evidence = run_friction_cases(scored, [pending, None, None, None])

    by_bps = {case.friction_bps: case.total_return for case in evidence.cases}
    expected = by_bps[25].value / by_bps[3].value
    assert evidence.friction_retention_ratio.status == "AVAILABLE"
    assert evidence.friction_retention_ratio.value == pytest.approx(expected)


def test_friction_records_turnover_and_equity_per_case(authority) -> None:
    binding = _binding(authority)
    sessions = _sessions("2024-01-01", periods=3)
    scored = _scored(
        {"AAA": [10.0, 12.0, 15.0]},
        {"AAA": [11.0, 13.0, 16.0]},
    )
    pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))
    evidence = run_friction_cases(scored, [pending, None, None])

    zero = next(case for case in evidence.cases if case.friction_bps == 0)
    assert zero.total_turnover.status == "AVAILABLE"
    assert zero.total_return.status == "AVAILABLE"
    assert len(zero.close_equity) == 3
    # zero friction conserves equity on flat prices
    flat = _scored(
        {"AAA": [10.0, 10.0, 10.0]},
        {"AAA": [10.0, 10.0, 10.0]},
    )
    flat_pending = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))
    flat_evidence = run_friction_cases(flat, [flat_pending, None, None])
    zero_flat = next(
        case for case in flat_evidence.cases if case.friction_bps == 0
    )
    assert zero_flat.total_return.value == pytest.approx(0.0)


def test_bootstrap_is_deterministic_and_statistic_scoped(authority) -> None:
    returns = (0.01, -0.02, 0.03, -0.01, 0.005)
    evidence = bootstrap_median_daily_return(returns)

    assert isinstance(evidence, BootstrapEvidence)
    assert evidence.statistic == "median_daily_return"
    assert evidence.n_bootstrap_draws == 2000
    assert evidence.seed == 0
    assert evidence.sample_size == len(returns)
    assert evidence.observed_median.status == "AVAILABLE"
    assert evidence.observed_median.value == pytest.approx(float(np.median(returns)))
    assert evidence.percentile_05.value <= evidence.percentile_95.value

    repeated = bootstrap_median_daily_return(returns)
    assert evidence.percentile_05.value == pytest.approx(repeated.percentile_05.value)
    assert evidence.percentile_95.value == pytest.approx(repeated.percentile_95.value)


def test_bootstrap_insufficient_samples_fail_closed() -> None:
    with pytest.raises(Gate2SealError) as exc_info:
        bootstrap_median_daily_return((0.01,))
    assert exc_info.value.code == "DURABILITY_EVIDENCE_INVALID"


def test_neighbor_trial_ids_use_only_sealed_adjacent_values(authority) -> None:
    family = None
    chosen = None
    for candidate in authority.grids.candidates:
        for family in authority.grids.families:
            if candidate in family.candidates:
                neighbors = family.neighbors(candidate.parameter_tuple_sha256)
                if neighbors:
                    chosen = candidate
                    break
        if chosen is not None:
            break
    assert chosen is not None

    expected = tuple(
        c.trial_id for c in family.neighbors(chosen.parameter_tuple_sha256)
    )
    result = neighbor_trial_ids(family, chosen.parameter_tuple_sha256)
    assert sorted(result) == sorted(expected)
    # no synthesized trial identifiers
    real_trials = {c.trial_id for c in family.candidates}
    assert set(result) <= real_trials
    assert chosen.trial_id not in result


def test_slice_folds_missing_authority_fails_closed(authority) -> None:
    _, replay = _replay(authority, periods=4)
    with pytest.raises(Gate2SealError) as exc_info:
        slice_continuous_folds(replay, None)
    assert exc_info.value.code == "FOLD_AUTHORITY_MISSING"


def test_slice_folds_use_continuous_equity_without_reset(authority) -> None:
    sessions, replay = _replay(authority, periods=5)
    authority_model = FoldAuthority(
        fold_ids=("fold-0", "fold-1", "fold-2", "fold-3"),
        boundaries=(
            (sessions[0], sessions[1]),
            (sessions[1], sessions[2]),
            (sessions[2], sessions[3]),
            (sessions[3], sessions[4]),
        ),
    )
    evidence = slice_continuous_folds(replay, authority_model)

    equity = replay.close_equity
    assert evidence.fold_returns[0].value == pytest.approx(
        equity[1] / equity[0] - 1.0
    )
    assert evidence.fold_returns[1].value == pytest.approx(
        equity[2] / equity[1] - 1.0
    )
    # slicing the same continuous series: no discontinuity or reset at the seam
    assert evidence.fold_equity_start[1] == pytest.approx(equity[1])
    assert evidence.fold_equity_end[0] == pytest.approx(equity[1])


def test_fold_authority_rejects_two_fold_or_noncontiguous_interface(authority) -> None:
    sessions, _ = _replay(authority, periods=5)

    with pytest.raises(ValidationError):
        FoldAuthority(
            fold_ids=("fold-0", "fold-1"),
            boundaries=((sessions[0], sessions[1]), (sessions[1], sessions[2])),
        )
    with pytest.raises(ValidationError):
        FoldAuthority(
            fold_ids=("fold-0", "fold-1", "fold-2", "fold-3"),
            boundaries=(
                (sessions[0], sessions[1]),
                (sessions[2], sessions[3]),
                (sessions[3], sessions[4]),
                (sessions[4], sessions[4] + pd.Timedelta(days=1)),
            ),
        )


def test_partition_regimes_missing_authority_fails_closed(authority) -> None:
    _, replay = _replay(authority, periods=4)
    with pytest.raises(Gate2SealError) as exc_info:
        partition_regimes(replay, None)
    assert exc_info.value.code == "REGIME_AUTHORITY_MISSING"


def test_partition_regimes_complete_and_nonoverlapping(authority) -> None:
    sessions, replay = _replay(authority, periods=4)
    mapping = tuple(
        (session, "bull" if i % 2 == 0 else "bear")
        for i, session in enumerate(sessions)
    )
    regime_authority = RegimeAuthority(
        regime_ids=("bear", "bull"), session_regime=mapping
    )
    evidence = partition_regimes(replay, regime_authority)

    assert sum(evidence.regime_session_counts) == len(sessions)
    assert list(evidence.regime_session_counts) == [2, 2]
    # every session is assigned to exactly one regime (complete + nonoverlapping)
    all_sessions: set = set()
    for regime_id, regime_sessions in zip(
        evidence.regime_ids, evidence.regime_sessions
    ):
        index = list(evidence.regime_ids).index(regime_id)
        assert len(regime_sessions) == evidence.regime_session_counts[index]
        for session in regime_sessions:
            assert session not in all_sessions
            all_sessions.add(session)
    assert all_sessions == set(sessions)


def test_partition_regimes_partial_authority_fails_closed(authority) -> None:
    sessions, replay = _replay(authority, periods=4)
    # omit the final session -> partial coverage
    mapping = tuple((session, "bull") for session in sessions[:-1])
    regime_authority = RegimeAuthority(
        regime_ids=("bull",), session_regime=mapping
    )
    with pytest.raises(Gate2SealError) as exc_info:
        partition_regimes(replay, regime_authority)
    assert exc_info.value.code == "REGIME_AUTHORITY_MISSING"


def test_every_evidence_schema_preserves_unavailable_statistics(authority) -> None:
    binding = _binding(authority)
    sessions, replay = _replay(authority, periods=5)
    scored = _scored(
        {"AAA": [10.0, 10.5, 11.0, 11.5]}, {"AAA": [10.0, 10.4, 10.9, 11.4]}
    )
    first = _target(binding, sessions[0], sessions[1], (("AAA", 1.0),))
    friction = run_friction_cases(scored, (first, None, None, None))
    bootstrap = bootstrap_median_daily_return([0.001, -0.002, 0.003])
    fold_authority = FoldAuthority(
        fold_ids=("fold-0", "fold-1", "fold-2", "fold-3"),
        boundaries=(
            (sessions[0], sessions[1]),
            (sessions[1], sessions[2]),
            (sessions[2], sessions[3]),
            (sessions[3], sessions[4]),
        ),
    )
    fold = slice_continuous_folds(replay, fold_authority)
    regime_authority = RegimeAuthority(
        regime_ids=("bear", "bull"),
        session_regime=tuple(
            (session, "bull" if i % 2 == 0 else "bear")
            for i, session in enumerate(sessions)
        ),
    )
    regime = partition_regimes(replay, regime_authority)

    for evidence in (friction, *friction.cases, bootstrap, fold, regime):
        stats = evidence.unavailable_statistics
        assert stats.max_drawdown is None
        assert stats.max_drawdown_status == "UNKNOWN"
        assert stats.calmar is None
        assert stats.calmar_status == "UNKNOWN"
        assert stats.dsr is None
        assert stats.dsr_status == "UNKNOWN"
        assert stats.dsr_reason == "NOT_IMPLEMENTED"
        assert stats.pbo is None
        assert stats.pbo_status == "UNKNOWN"
        assert stats.pbo_reason == "NOT_IMPLEMENTED"


def test_fold_slice_evidence_rejects_misaligned_lengths(authority) -> None:
    from investment_tracker.quant.phase4.engine.models import (
        FoldSliceEvidence,
        MetricValue,
        UnavailableStatistics,
    )

    _, replay = _replay(authority, periods=4)
    # fold_ids == fold_returns (2) and fold_equity_start == fold_equity_end (1),
    # so the existing start-vs-end length check alone cannot catch the
    # returns-vs-start/end misalignment; only a fully chained length check can.
    with pytest.raises(ValueError):
        FoldSliceEvidence(
            candidate_id=replay.candidate_id,
            binding_sha256=replay.binding_sha256,
            fold_ids=("fold-0", "fold-1"),
            fold_returns=(
                MetricValue(value=0.1, status="AVAILABLE", reason="OK"),
                MetricValue(value=0.2, status="AVAILABLE", reason="OK"),
            ),
            fold_equity_start=(1.0,),
            fold_equity_end=(1.1,),
            unavailable_statistics=UnavailableStatistics(),
        )
