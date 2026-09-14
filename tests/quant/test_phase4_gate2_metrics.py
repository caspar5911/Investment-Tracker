from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from investment_tracker.quant.phase4.engine.metrics import calculate_metrics
from investment_tracker.quant.phase4.engine.models import (
    FixedStrategyBinding,
    Gate2SealError,
    PortfolioReplay,
    SessionState,
)


def _replay(
    equity: tuple[float, ...],
    *,
    friction_bps: int = 3,
    turnover: float = 0.0,
    target: tuple[float, ...] | None = None,
    realized: tuple[float, ...] | None = None,
    binding: FixedStrategyBinding | None = None,
) -> PortfolioReplay:
    sessions = tuple(pd.date_range("2020-01-01", periods=len(equity), tz="UTC"))
    target_values = target or tuple(0.0 for _ in equity)
    realized_values = realized or tuple(0.0 for _ in equity)
    states = tuple(
        SessionState(
            session=session,
            open_equity=value,
            close_equity=value,
            cash=value * (1.0 - exposure),
            units=() if exposure == 0.0 else (("AAA", exposure),),
            realized_gross_exposure=exposure,
            target_gross_exposure=target_exposure,
            binding=binding,
        )
        for session, value, exposure, target_exposure in zip(
            sessions, equity, realized_values, target_values, strict=True
        )
    )
    return PortfolioReplay(
        candidate_id=None if binding is None else binding.candidate_id,
        binding_sha256=None if binding is None else binding.binding_sha256,
        friction_bps=friction_bps,
        initial_cash=equity[0],
        states=states,
        fills=(),
        total_turnover=turnover,
    )


def test_metrics_match_literal_scored_close_calculations() -> None:
    replay = _replay(
        (100.0, 110.0, 99.0),
        turnover=50.0,
        target=(0.0, 0.5, 0.5),
        realized=(0.0, 0.4, 0.6),
    )
    benchmark = _replay((100.0, 105.0, 99.0))

    result = calculate_metrics(replay, benchmark)

    daily = (0.10, -0.10)
    sample_std = math.sqrt(0.02)
    assert result.total_return.value == pytest.approx(-0.01)
    assert result.cagr.value == pytest.approx(0.99 ** (365.25 / 2.0) - 1.0)
    assert result.annualized_volatility.value == pytest.approx(
        sample_std * math.sqrt(252.0)
    )
    assert result.sharpe.value == pytest.approx(
        (sum(daily) / 2.0) / sample_std * math.sqrt(252.0)
    )
    assert result.sortino.value == pytest.approx(0.0)
    assert result.benchmark_excess_return.value == pytest.approx(0.0)
    assert result.total_one_way_turnover.value == pytest.approx(50.0)
    assert result.annualized_one_way_turnover.value == pytest.approx(
        (50.0 / 103.0) * (252.0 / 2.0)
    )
    assert result.average_target_gross_exposure.value == pytest.approx(1.0 / 3.0)
    assert result.average_realized_gross_exposure.value == pytest.approx(1.0 / 3.0)
    assert result.time_in_market.value == pytest.approx(2.0 / 3.0)
    assert result.target_gross_exposure_series == (0.0, 0.5, 0.5)
    assert result.realized_gross_exposure_series == (0.0, 0.4, 0.6)
    assert result.sharpe.status == "AVAILABLE"
    assert result.sortino.status == "AVAILABLE"


def test_zero_denominators_and_insufficient_observations_are_explicit_unknowns() -> (
    None
):
    replay = _replay((100.0, 100.0, 100.0))
    result = calculate_metrics(replay, replay)

    assert result.total_return.value == 0.0
    assert result.benchmark_excess_return.value == 0.0
    assert result.annualized_volatility.value == 0.0
    assert result.annualized_volatility.status == "AVAILABLE"
    for metric in (result.sharpe, result.sortino):
        assert metric.model_dump() == {
            "schema_version": "PHASE4-METRIC-VALUE-v1",
            "value": None,
            "status": "UNKNOWN",
            "reason": "NONPOSITIVE_DENOMINATOR",
        }

    single = calculate_metrics(_replay((100.0,)), _replay((100.0,)))
    assert single.total_return.value == 0.0
    assert single.total_return.status == "AVAILABLE"
    assert single.benchmark_excess_return.value == 0.0
    assert single.cagr.status == "UNKNOWN"
    assert single.annualized_one_way_turnover.status == "UNKNOWN"
    assert single.total_one_way_turnover.value == 0.0
    assert single.average_realized_gross_exposure.value == 0.0


def test_benchmark_must_use_identical_sessions_and_friction() -> None:
    replay = _replay((100.0, 101.0), friction_bps=3)
    wrong_friction = _replay((100.0, 101.0), friction_bps=25)

    with pytest.raises(Gate2SealError) as exc_info:
        calculate_metrics(replay, wrong_friction)

    assert exc_info.value.code == "DURABILITY_EVIDENCE_INVALID"


def test_metrics_preserve_the_exact_strategy_binding_identity() -> None:
    from investment_tracker.quant.phase4.engine.authority import load_gate2_authority

    authority = load_gate2_authority(Path(__file__).resolve().parents[2])
    binding = FixedStrategyBinding.from_authority(
        authority, authority.grids.candidates[0].candidate_id, "a" * 64
    )
    replay = _replay((100.0, 101.0), binding=binding)

    result = calculate_metrics(replay, _replay((100.0, 101.0)))

    assert result.candidate_id == binding.candidate_id
    assert result.binding_sha256 == binding.binding_sha256


def test_nonfinite_or_nonpositive_constructed_input_fails_closed_to_unknown() -> None:
    valid = _replay((100.0, 101.0, 102.0))
    invalid_state = valid.states[1].model_copy()
    object.__setattr__(invalid_state, "close_equity", float("nan"))
    invalid = valid.model_copy()
    object.__setattr__(
        invalid, "states", (valid.states[0], invalid_state, valid.states[2])
    )

    result = calculate_metrics(invalid, valid)

    assert result.total_return.status == "UNKNOWN"
    assert result.total_return.reason == "INVALID_INPUT"
    assert result.cagr.status == "UNKNOWN"
    assert result.annualized_volatility.status == "UNKNOWN"


def test_nonfinite_derived_values_fail_closed_instead_of_raising() -> None:
    extreme = _replay((1e-300, 1e300, 1e300))

    result = calculate_metrics(extreme, extreme)

    assert result.total_return.status == "UNKNOWN"
    assert result.total_return.reason == "INVALID_INPUT"
    assert result.cagr.status == "UNKNOWN"
    assert result.benchmark_excess_return.status == "UNKNOWN"


def test_nonfinite_annualized_turnover_fails_closed() -> None:
    extreme = _replay((1e-300, 1e-300), turnover=1e300)

    result = calculate_metrics(extreme, extreme)

    assert result.total_one_way_turnover.value == 1e300
    assert result.annualized_one_way_turnover.status == "UNKNOWN"
    assert result.annualized_one_way_turnover.reason == "INVALID_INPUT"


def test_governed_drawdown_and_search_aware_statistics_remain_exactly_unavailable() -> (
    None
):
    result = calculate_metrics(_replay((100.0, 101.0)), _replay((100.0, 101.0)))

    assert result.unavailable_statistics.model_dump() == {
        "max_drawdown": None,
        "max_drawdown_status": "UNKNOWN",
        "calmar": None,
        "calmar_status": "UNKNOWN",
        "dsr": None,
        "dsr_status": "UNKNOWN",
        "dsr_reason": "NOT_IMPLEMENTED",
        "pbo": None,
        "pbo_status": "UNKNOWN",
        "pbo_reason": "NOT_IMPLEMENTED",
    }
    assert not hasattr(result, "max_drawdown")
    assert not hasattr(result, "calmar")
