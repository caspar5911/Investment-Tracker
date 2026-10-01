"""Tests for the fixed Generation-4 Phase-7 durability protocol primitives.

``quant/phase7/generation4_durability.py`` implements *only* the reusable
fixed-protocol calculation helpers. It never searches candidates, never accepts
strategy-coordinate overrides, never retrains inside chronological subperiods,
never touches a data provider, and never modifies the frozen Generation-2
strategy implementation.

Expected values are hand-computed from the frozen protocol semantics:

- the candidate is the exact frozen ``G2-A|lookback=189|skip=21|top_k=1|rebalance=21``
  grid position, verified against the frozen generation-2 grid;
- no public helper accepts ``candidate``/coordinate or ``candidates`` inputs;
- the friction cases are exactly ``0/3/10/25/50`` bps;
- the benchmark is exactly ``SPY``, aligned to the exact scored sessions;
- warmup sessions precede the scored boundary and are excluded from scored P&L,
  while the underlying portfolio state stays continuous (one replay, sliced);
- DQ-030-dependent drawdown/Calmar/recovery metrics stay UNKNOWN unless a bound
  resolution is supplied;
- metrics are deterministic for identical inputs;
- incomplete data fails closed to UNKNOWN/ABSTAIN rather than dropping rows.
"""

from __future__ import annotations

import inspect

import pandas as pd
import pytest

from investment_tracker.quant.generation2.accounting import (
    DECISION_ACCOUNTING_SCHEMA,
    DecisionReplayResult,
    DecisionState,
)
from investment_tracker.quant.phase7 import generation4_durability as dur


CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
FRICTION_CASES = (0, 3, 10, 25, 50)
UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _index(n: int, start: str = "2018-01-01") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n, tz="UTC")


def _fabricate(equity: list[float], exposures: list[float] | None = None) -> DecisionReplayResult:
    """Fabricate a ``DecisionReplayResult`` from a close-equity path.

    Mirrors the generation-2 performance-test fabrication convention so the
    scored-window primitives can be exercised with hand-computed values.
    """
    index = _index(len(equity) + 1)
    exposures = exposures if exposures is not None else [0.0] * len(equity)
    states = tuple(
        DecisionState(index[i + 1], 0.0, 0.0, equity[i], exposures[i], (), ())
        for i in range(len(equity))
    )
    return DecisionReplayResult(
        DECISION_ACCOUNTING_SCHEMA, 0, 100_000.0, tuple(index[1 : len(equity) + 1]), states, (), 0.0
    )


def _universe_bars(n: int = 320) -> dict[str, pd.DataFrame]:
    """Full research universe with enough sessions for the 189-session lookback.

    QQQ trends up so the fixed dual-momentum candidate rotates into it and the
    replay produces a real (non-degenerate) equity path.
    """
    index = _index(n)
    qqq_close = [100.0 * (1.002**i) for i in range(n)]
    frames: dict[str, pd.DataFrame] = {}
    for symbol in UNIVERSE:
        if symbol == "QQQ":
            close = qqq_close
        else:
            close = [100.0] * n
        frames[symbol] = pd.DataFrame(
            {"open": [value * 0.999 for value in close], "close": close}, index=index
        )
    return frames


# ---------------------------------------------------------------------------
# Fixed candidate only
# ---------------------------------------------------------------------------


def test_resolve_fixed_candidate_is_the_exact_frozen_position() -> None:
    candidate = dur.resolve_fixed_candidate()
    assert candidate.candidate_id == CANDIDATE_ID
    assert candidate.family == "G2-A"
    assert candidate.lookback == 189
    assert candidate.skip == 21
    assert candidate.top_k == 1
    assert candidate.rebalance == 21


def test_no_public_helper_accepts_strategy_coordinates() -> None:
    forbidden = {"candidate", "lookback", "skip", "top_k", "rebalance"}
    for name in ("build_fixed_targets", "compute_fixed_friction_cases"):
        params = set(inspect.signature(getattr(dur, name)).parameters)
        assert not (forbidden & params), f"{name} must not expose {forbidden & params}"


def test_no_public_helper_accepts_a_candidate_grid() -> None:
    for name in dir(dur):
        if name.startswith("_"):
            continue
        obj = getattr(dur, name)
        if callable(obj):
            assert "candidates" not in inspect.signature(obj).parameters, name


def test_no_public_helper_performs_training_or_optimization() -> None:
    for name in dir(dur):
        if name.startswith("_"):
            continue
        obj = getattr(dur, name)
        if not callable(obj):
            continue
        lowered = name.lower()
        # "research" (e.g. the frozen research universe) is domain vocabulary,
        # not an optimization/training operation, so strip it before scanning.
        probe = lowered.replace("research", "")
        assert not any(token in probe for token in ("train", "fit", "optimi", "search")), name


# ---------------------------------------------------------------------------
# Exact friction cases
# ---------------------------------------------------------------------------


def test_compute_fixed_friction_cases_returns_exactly_the_five_cases() -> None:
    result = dur.compute_fixed_friction_cases(_universe_bars())
    assert set(result) == {str(bps) for bps in FRICTION_CASES}
    for case in result.values():
        assert set(case) == {
            "friction_bps",
            "replay_sha256",
            "session_count",
            "total_return",
            "cagr",
            "sharpe",
            "sortino",
            "annualized_one_way_turnover",
            "rolling_12m_positive_fraction",
            "max_drawdown",
            "calmar",
            "recovery",
            "exposure_invariant_passes",
        }
        assert case["replay_sha256"] is not None
        assert isinstance(case["session_count"], int) and case["session_count"] >= 2


def test_compute_fixed_friction_cases_rejects_a_wrong_set() -> None:
    with pytest.raises(dur.Generation4DurabilityError) as exc:
        dur.compute_fixed_friction_cases(_universe_bars(), friction_cases=(0, 3))
    assert exc.value.code == dur.GEN4_PHASE7_DURABILITY_FRICTION_INVALID
    with pytest.raises(dur.Generation4DurabilityError) as exc:
        dur.compute_fixed_friction_cases(_universe_bars(), friction_cases=(0, 3, 10, 25))
    assert exc.value.code == dur.GEN4_PHASE7_DURABILITY_FRICTION_INVALID


# ---------------------------------------------------------------------------
# Exact research universe
# ---------------------------------------------------------------------------


def test_validate_research_universe_accepts_the_exact_universe() -> None:
    dur.validate_research_universe(_universe_bars(40))


@pytest.mark.parametrize(
    "drop_symbol",
    ["GLD", "SPY", "XLP"],
)
def test_validate_research_universe_rejects_a_missing_symbol(drop_symbol: str) -> None:
    bars = _universe_bars(40)
    del bars[drop_symbol]
    with pytest.raises(dur.Generation4DurabilityError) as exc:
        dur.validate_research_universe(bars)
    assert exc.value.code == dur.GEN4_PHASE7_DURABILITY_UNIVERSE_INVALID


@pytest.mark.parametrize("holdout", ["QQQM", "FALN", "IIPR", "PSTL", "EFAS"])
def test_validate_research_universe_rejects_a_holdout_symbol(holdout: str) -> None:
    bars = _universe_bars(40)
    del bars["GLD"]
    bars[holdout] = bars["TLT"]
    with pytest.raises(dur.Generation4DurabilityError) as exc:
        dur.validate_research_universe(bars)
    assert exc.value.code == dur.GEN4_PHASE7_DURABILITY_UNIVERSE_INVALID


# ---------------------------------------------------------------------------
# Benchmark is SPY, aligned exactly
# ---------------------------------------------------------------------------


def test_benchmark_total_return_defaults_to_spy_and_matches_hand_computation() -> None:
    index = _index(5)
    bars = {"SPY": pd.DataFrame({"close": [100.0, 101.0, 99.0, 102.0, 104.0]}, index=index)}
    metric = dur.benchmark_total_return(bars, index)
    assert metric["status"] == "AVAILABLE"
    assert metric["reason"] == "OK"
    assert metric["value"] == pytest.approx(104.0 / 100.0 - 1.0, rel=1e-12)


def test_benchmark_total_return_rejects_a_non_spy_symbol() -> None:
    index = _index(5)
    bars = {"QQQ": pd.DataFrame({"close": [100.0, 101.0, 99.0, 102.0, 104.0]}, index=index)}
    with pytest.raises(dur.Generation4DurabilityError) as exc:
        dur.benchmark_total_return(bars, index, symbol="QQQ")
    assert exc.value.code == dur.GEN4_PHASE7_DURABILITY_BENCHMARK_INVALID


def test_benchmark_total_return_is_unknown_when_a_session_is_missing() -> None:
    index = _index(5)
    bars = {"SPY": pd.DataFrame({"close": [100.0, 101.0, 99.0, 104.0]}, index=index[:4])}
    metric = dur.benchmark_total_return(bars, index)
    assert metric["status"] == "UNKNOWN"
    assert metric["reason"] == "GEN4_PHASE7_DURABILITY_ALIGNMENT_INVALID"


# ---------------------------------------------------------------------------
# Warmup excluded from scored P&L; continuous state
# ---------------------------------------------------------------------------


def test_scored_equity_window_slices_a_continuous_replay_without_reset() -> None:
    equity = [100_000.0, 102_000.0, 104_000.0, 106_000.0, 108_000.0]
    replay = _fabricate(equity)
    scored_sessions, scored_equity = dur.scored_equity_window(replay, replay.sessions[2])
    assert scored_sessions == replay.sessions[2:]
    assert tuple(scored_equity) == tuple(equity[2:])
    # The last scored equity is the full replay's last equity: no state reset.
    assert scored_equity[-1] == replay.close_equity[-1]


def test_scored_total_return_excludes_warmup_equity() -> None:
    equity = [100_000.0, 102_000.0, 104_000.0, 106_000.0, 108_000.0]
    replay = _fabricate(equity)
    sessions, equity_window = dur.scored_equity_window(replay, replay.sessions[2])
    metric = dur.scored_total_return(sessions, equity_window)
    # Warmup gain 100k -> 104k is excluded; scored gain is 104k -> 108k.
    assert metric["status"] == "AVAILABLE"
    assert metric["value"] == pytest.approx(108_000.0 / 104_000.0 - 1.0, rel=1e-12)


def test_scored_total_return_is_unknown_with_a_single_point() -> None:
    replay = _fabricate([100_000.0, 101_000.0])
    sessions, equity = dur.scored_equity_window(replay, replay.sessions[1])
    metric = dur.scored_total_return(sessions, equity)
    assert metric["status"] == "UNKNOWN"
    assert metric["reason"] == "INSUFFICIENT_DATA"


def test_scored_equity_window_rejects_a_boundary_that_is_not_a_session() -> None:
    replay = _fabricate([100_000.0, 101_000.0, 102_000.0])
    with pytest.raises(dur.Generation4DurabilityError) as exc:
        dur.scored_equity_window(replay, replay.sessions[0] + pd.Timedelta(hours=12))
    assert exc.value.code == dur.GEN4_PHASE7_DURABILITY_ALIGNMENT_INVALID


# ---------------------------------------------------------------------------
# Incomplete data fails closed to UNKNOWN rather than dropping rows
# ---------------------------------------------------------------------------


def test_period_positive_fraction_is_unknown_on_an_empty_window() -> None:
    metric = dur.period_positive_fraction({})
    assert metric["status"] == "UNKNOWN"
    assert metric["reason"] == "EMPTY_SUBSET"


def test_period_average_is_unknown_when_no_periods_match() -> None:
    assert dur.period_average({"2026-01": 0.05}, kind="losers")["reason"] == "EMPTY_SUBSET"
    assert dur.period_average({"2026-01": -0.05}, kind="winners")["reason"] == "EMPTY_SUBSET"


# ---------------------------------------------------------------------------
# DQ-030-dependent metrics stay UNKNOWN without a bound resolution
# ---------------------------------------------------------------------------


def test_drawdown_calmar_recovery_are_unknown_when_dq030_is_unresolved() -> None:
    index = _index(5)
    metrics = dur.drawdown_calmar_recovery(index, [100_000.0, 101_000.0, 99_000.0, 100_000.0, 102_000.0])
    for name in ("max_drawdown", "calmar", "recovery"):
        assert metrics[name] == {"status": "UNKNOWN", "value": None, "reason": "DQ-030_UNRESOLVED"}


# ---------------------------------------------------------------------------
# Subperiod primitives
# ---------------------------------------------------------------------------


def test_compound_month_returns_are_hand_computable_and_deterministic() -> None:
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-05", tz="UTC"),
            pd.Timestamp("2026-01-20", tz="UTC"),
            pd.Timestamp("2026-02-03", tz="UTC"),
            pd.Timestamp("2026-02-20", tz="UTC"),
        ]
    )
    equity = [100_000.0, 110_000.0, 121_000.0, 96_800.0]
    month_returns = dur.compound_month_returns(index, equity)
    # January: 110k/100k - 1. February is partitioned from the last January
    # session's equity (110k), so no return between the two months is dropped.
    assert month_returns["2026-01"] == pytest.approx(0.10, rel=1e-12)
    assert month_returns["2026-02"] == pytest.approx(96_800.0 / 110_000.0 - 1.0, rel=1e-12)
    assert dur.compound_month_returns(index, equity) == month_returns


def test_compound_year_returns_collapse_to_a_single_year() -> None:
    index = pd.DatetimeIndex(
        [pd.Timestamp("2026-01-05", tz="UTC"), pd.Timestamp("2026-06-05", tz="UTC")]
    )
    year_returns = dur.compound_year_returns(index, [100_000.0, 115_000.0])
    assert year_returns == {"2026": 115_000.0 / 100_000.0 - 1.0}


def test_longest_losing_month_sequence_counts_consecutive_negative_months() -> None:
    months = {
        "2026-01": 0.05,
        "2026-02": -0.02,
        "2026-03": -0.03,
        "2026-04": 0.04,
        "2026-05": -0.01,
    }
    assert dur.longest_losing_month_sequence(months)["value"] == 2


def test_worst_period_reports_the_minimum_return() -> None:
    assert dur.worst_period({"2026-01": 0.05, "2026-02": -0.03, "2026-03": 0.01})["value"] == pytest.approx(
        -0.03, rel=1e-12
    )


def test_return_concentration_is_unknown_when_there_is_no_positive_return() -> None:
    metric = dur.return_concentration({"2026-01": -0.02, "2026-02": -0.03})
    assert metric["status"] == "UNKNOWN"
    assert metric["reason"] == "EMPTY_SUBSET"


def test_rolling_12m_return_is_empty_without_a_complete_window() -> None:
    index = _index(5)
    assert dur.rolling_period_returns(index, [100.0, 101.0, 102.0, 103.0, 104.0], 12) == ()


def test_rolling_12m_return_reports_a_complete_window() -> None:
    n = 270
    index = _index(n, start="2020-01-01")
    equity = [100_000.0 * (1.01**i) for i in range(n)]
    rolling = dur.rolling_period_returns(index, equity, 12)
    assert len(rolling) > 0
    last = rolling[-1]
    assert last["ending_session"].date() == index[-1].date()
    assert isinstance(last["return"], float)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_compute_fixed_friction_cases_is_deterministic() -> None:
    bars = _universe_bars()
    first = dur.compute_fixed_friction_cases(bars)
    second = dur.compute_fixed_friction_cases(bars)
    assert first == second


# ---------------------------------------------------------------------------
# Historical diagnostic lane (reused history only)
# ---------------------------------------------------------------------------


def _history_bars(n: int) -> dict[str, pd.DataFrame]:
    """A reused long-history universe. QQQ trends up; the rest is flat.

    ``n`` business days from 2015, long enough (``n >= ~1550``) to complete the
    60-month window or short enough (``n`` just past the 189-session warmup)
    that no historical window is complete.
    """
    index = pd.bdate_range("2015-01-01", periods=n, tz="UTC")
    qqq_close = [100.0 * (1.001**i) for i in range(n)]
    frames: dict[str, pd.DataFrame] = {}
    for symbol in UNIVERSE:
        close = qqq_close if symbol == "QQQ" else [100.0] * n
        frames[symbol] = pd.DataFrame(
            {"open": [value * 0.999 for value in close], "close": close}, index=index
        )
    return frames


def _historical_report(n: int, corporate_actions_complete: bool = True) -> dict:
    return dur.historical_durability_report(
        dur.ReusedHistoryDataset(_history_bars(n), corporate_actions_complete)
    )


def test_historical_report_schema_classification_and_candidate() -> None:
    report = _historical_report(210)
    assert report["schema"] == "GENERATION4-PHASE7-HISTORICAL-DURABILITY-v1"
    assert report["classification"] == "REUSED_HISTORY_DIAGNOSTIC_ONLY"
    assert report["candidate_id"] == CANDIDATE_ID


def test_historical_report_claims_no_new_oos_or_virgin_evidence() -> None:
    report = _historical_report(210)
    assert report["new_out_of_sample_evidence"] is False
    assert report["virgin_holdout_evidence"] is False


def test_historical_report_sets_no_production_or_live_authority() -> None:
    report = _historical_report(210)
    assert report["production_authority"] is False
    assert report["live_trading_authority"] is False


def test_historical_report_changes_no_candidate_or_methodology() -> None:
    report = _historical_report(210)
    assert report["candidate_changed"] is False
    assert report["methodology_changed"] is False


def test_historical_report_cannot_produce_a_production_pass() -> None:
    report = _historical_report(210)
    assert report["production_pass"] is False


def test_historical_report_flags_incomplete_corporate_actions_as_unknown() -> None:
    report = _historical_report(210, corporate_actions_complete=False)
    assert report["corporate_action_evidence"]["status"] == "UNKNOWN"
    assert report["corporate_action_evidence"]["reason"] == "INCOMPLETE_CORPORATE_ACTIONS"


def test_historical_report_corporate_actions_available_when_complete() -> None:
    report = _historical_report(210, corporate_actions_complete=True)
    assert report["corporate_action_evidence"]["status"] == "AVAILABLE"
    assert report["corporate_action_evidence"]["reason"] == "OK"


def test_historical_windows_are_unknown_when_incomplete() -> None:
    report = _historical_report(210)
    for label in ("12m", "36m", "60m"):
        window = report["historical_windows"][label]
        assert window["status"] == "UNKNOWN"
        assert window["reason"] == "INCOMPLETE_WINDOW"


def test_historical_windows_are_available_when_complete() -> None:
    report = _historical_report(1550)
    for label in ("12m", "36m", "60m"):
        window = report["historical_windows"][label]
        assert window["status"] == "AVAILABLE"
        assert window["reason"] == "OK"
        assert isinstance(window["value"], float)


def test_historical_report_is_deterministic() -> None:
    dataset = dur.ReusedHistoryDataset(_history_bars(210), True)
    assert dur.historical_durability_report(dataset) == dur.historical_durability_report(dataset)


# ---------------------------------------------------------------------------
# Prospective checkpoint lane (post-start primary evidence)
# ---------------------------------------------------------------------------

# The scored window begins after the (already-committed) Phase-7 start
# timestamp. These synthetic snapshots use 210 causal warmup sessions
# (the maximum permitted) so the 189-lookback + 21-skip target engine has full
# context before the first scored session. The scored region is the SPY
# benchmark calendar from ``scored_start`` forward, capped at the checkpoint.
PROSPECTIVE_WARMUP = 210


def _prospective_bars(total: int) -> tuple[dict[str, pd.DataFrame], pd.Timestamp]:
    """A prospective universe spanning ``total`` sessions from 2024.

    QQQ trends up fastest, SPY trends gently (so the benchmark total return is
    non-trivial and hand-computable), the rest are flat. The scored window
    starts at session index ``PROSPECTIVE_WARMUP``.
    """
    index = pd.bdate_range("2024-01-01", periods=total, tz="UTC")
    frames: dict[str, pd.DataFrame] = {}
    for symbol in UNIVERSE:
        if symbol == "QQQ":
            close = [100.0 * (1.002**i) for i in range(total)]
        elif symbol == "SPY":
            close = [100.0 * (1.001**i) for i in range(total)]
        else:
            close = [100.0] * total
        frames[symbol] = pd.DataFrame(
            {"open": [value * 0.999 for value in close], "close": close}, index=index
        )
    return frames, index[PROSPECTIVE_WARMUP]


def _prospective_report(total: int, checkpoint_cutoff: int = 252) -> dict:
    bars, start = _prospective_bars(total)
    snapshot = dur.ProspectiveCheckpoint(bars, start, checkpoint_cutoff)
    return dur._prospective_checkpoint_report_unchecked(snapshot)


def test_prospective_report_schema() -> None:
    report = _prospective_report(270)
    assert report["schema"] == "GENERATION4-PHASE7-PROSPECTIVE-CHECKPOINT-v1"


def test_prospective_fewer_than_sixty_three_sessions_remains_pending() -> None:
    report = _prospective_report(270)  # 60 scored sessions
    assert report["scored_session_count"] == 60
    assert report["checkpoint_label"] == "PENDING"
    assert report["status"] == dur.PHASE7_PROSPECTIVE_EVIDENCE_PENDING


def test_prospective_sixty_three_sessions_is_early_diagnostic() -> None:
    report = _prospective_report(273)  # 63 scored sessions
    assert report["scored_session_count"] == 63
    assert report["checkpoint_label"] == dur.EARLY_DIAGNOSTIC
    assert report["status"] == dur.PHASE7_PROSPECTIVE_EVIDENCE_PENDING


def test_prospective_126_sessions_is_interim_diagnostic() -> None:
    report = _prospective_report(336)  # 126 scored sessions
    assert report["scored_session_count"] == 126
    assert report["checkpoint_label"] == dur.INTERIM_DIAGNOSTIC
    assert report["status"] == dur.PHASE7_PROSPECTIVE_EVIDENCE_PENDING


def test_prospective_252_sessions_is_primary_assessment_eligibility() -> None:
    report = _prospective_report(462)  # 252 scored sessions
    assert report["scored_session_count"] == 252
    assert report["checkpoint_label"] == dur.PRIMARY_PHASE7_ASSESSMENT


def test_prospective_fewer_than_252_never_returns_complete() -> None:
    for total in (273, 336):
        report = _prospective_report(total)
        assert report["status"] != dur.PHASE7_PROSPECTIVE_EVIDENCE_COMPLETE


def test_prospective_does_not_synthesize_missing_sessions() -> None:
    # Only 60 sessions are available; requesting the 252 checkpoint must not
    # pad or estimate the missing sessions.
    report = _prospective_report(270, checkpoint_cutoff=252)
    assert report["scored_session_count"] == 60
    assert report["checkpoint_label"] == "PENDING"


def test_prospective_reports_all_five_friction_cases() -> None:
    report = _prospective_report(462)
    assert set(report["friction_cases"]) == {"0", "3", "10", "25", "50"}


def test_prospective_spy_benchmark_alignment_is_exact() -> None:
    total, warmup = 462, PROSPECTIVE_WARMUP
    bars, start = _prospective_bars(total)
    spy_close = bars["SPY"]["close"]
    scored = [s for s in spy_close.index if s >= start][:252]
    expected = float(spy_close.loc[scored[-1]]) / float(spy_close.loc[scored[0]]) - 1.0
    snapshot = dur.ProspectiveCheckpoint(bars, start, 252)
    report = dur._prospective_checkpoint_report_unchecked(snapshot)
    assert report["benchmark_total_return"]["status"] == "AVAILABLE"
    assert report["benchmark_total_return"]["value"] == pytest.approx(expected, rel=1e-12)


def test_prospective_excess_return_vs_cash_is_exact() -> None:
    report = _prospective_report(462)
    primary = report["friction_cases"]["3"]["total_return"]
    # Cash earns 0%; the excess-versus-cash return is the primary total return.
    assert report["excess_return_vs_cash"]["status"] == "AVAILABLE"
    assert report["excess_return_vs_cash"]["value"] == pytest.approx(primary["value"], rel=1e-12)


def test_prospective_missing_required_evidence_abstains() -> None:
    # 252 scored sessions on the SPY calendar, but GLD is missing one scored
    # session: the evidence cannot be reconciled -> ABSTAIN.
    bars, start = _prospective_bars(462)
    gap = bars["GLD"].index[PROSPECTIVE_WARMUP + 100]
    bars["GLD"] = bars["GLD"].drop(index=gap)
    snapshot = dur.ProspectiveCheckpoint(bars, start, 252)
    report = dur._prospective_checkpoint_report_unchecked(snapshot)
    assert report["status"] == dur.PHASE7_UNKNOWN_ABSTAIN


def test_prospective_complete_252_session_evidence_is_complete() -> None:
    report = _prospective_report(462)
    assert report["status"] == dur.PHASE7_PROSPECTIVE_EVIDENCE_COMPLETE


def test_prospective_completion_grants_no_production_or_live_authority() -> None:
    report = _prospective_report(462)
    assert report["status"] == dur.PHASE7_PROSPECTIVE_EVIDENCE_COMPLETE
    assert report["production_authority"] is False
    assert report["live_trading_authority"] is False
    assert report["production_pass"] is False
    assert report["paper_only"] is True
