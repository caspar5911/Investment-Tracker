"""Fixed Generation-4 Phase-7 durability protocol primitives.

This module implements *only* the reusable fixed-protocol calculation helpers
for the Generation-4 Phase-7 durability evaluation. It is deliberately narrow:

- the strategy candidate is the exact frozen ``G2-A|lookback=189|skip=21|
  top_k=1|rebalance=21`` grid position; no helper accepts a candidate or any
  strategy-coordinate override, and no helper enumerates a candidate grid;
- no helper performs training, fitting, or reoptimization inside chronological
  subperiods;
- the friction cases are exactly ``0/3/10/25/50`` bps;
- the benchmark is exactly ``SPY``, aligned to the exact scored sessions;
- warmup sessions precede the scored boundary and are excluded from scored P&L,
  while the underlying portfolio state stays continuous (a single replay that
  is sliced, never reset);
- DQ-030-dependent drawdown/Calmar/recovery metrics stay UNKNOWN unless a bound
  resolution is explicitly supplied;
- incomplete data fails closed to UNKNOWN/ABSTAIN rather than dropping rows.

It contains no data-provider code and does not duplicate or modify the frozen
Generation-2 strategy implementation; it reuses the generation-2 accounting,
strategy, performance and DQ-030 primitives.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from investment_tracker.quant.generation2.accounting import (
    DECISION_ACCOUNTING_SCHEMA,
    DecisionReplayResult,
    DecisionState,
    DecisionTarget,
    DividendEvent,
    SplitEvent,
    replay_decision_targets,
)
from investment_tracker.quant.generation2.campaign import assert_frozen_candidate
from investment_tracker.quant.generation2.grid import GridCandidate
from investment_tracker.quant.generation2.metrics import drawdown_calmar
from investment_tracker.quant.generation2.performance import (
    annualized_one_way_turnover,
    cagr,
    exposure_invariant_passes,
    rolling_12m_positive_fraction,
    sharpe,
    sortino,
    total_return,
)
from investment_tracker.quant.generation2.strategy import build_targets

__all__ = [
    "BENCHMARK_SYMBOL",
    "CANDIDATE_ID",
    "CHECKPOINT_PENDING",
    "CHECKPOINT_SESSIONS_EARLY",
    "CHECKPOINT_SESSIONS_INTERIM",
    "CHECKPOINT_SESSIONS_PRIMARY",
    "EARLY_DIAGNOSTIC",
    "FRICTION_CASES_BPS",
    "GEN4_PHASE7_DURABILITY_ALIGNMENT_INVALID",
    "GEN4_PHASE7_DURABILITY_BENCHMARK_INVALID",
    "GEN4_PHASE7_DURABILITY_FRICTION_INVALID",
    "GEN4_PHASE7_DURABILITY_METRIC_INVALID",
    "GEN4_PHASE7_DURABILITY_UNIVERSE_INVALID",
    "Generation4DurabilityError",
    "INITIAL_CASH",
    "INTERIM_DIAGNOSTIC",
    "PHASE7_GOVERNANCE_FAILURE",
    "PHASE7_PROSPECTIVE_EVIDENCE_COMPLETE",
    "PHASE7_PROSPECTIVE_EVIDENCE_PENDING",
    "PHASE7_UNKNOWN_ABSTAIN",
    "PRIMARY_FRICTION_BPS",
    "PRIMARY_PHASE7_ASSESSMENT",
    "ProspectiveCheckpoint",
    "RESEARCH_UNIVERSE",
    "ReusedHistoryDataset",
    "benchmark_total_return",
    "build_fixed_targets",
    "compound_month_returns",
    "compound_year_returns",
    "compute_fixed_friction_cases",
    "drawdown_calmar_recovery",
    "excess_return",
    "historical_durability_report",
    "longest_losing_month_sequence",
    "period_average",
    "period_positive_fraction",
    "prospective_checkpoint_report",
    "resolve_fixed_candidate",
    "return_concentration",
    "rolling_period_returns",
    "scored_equity_window",
    "scored_total_return",
    "validate_research_universe",
    "worst_period",
]

# ---------------------------------------------------------------------------
# Frozen identities
# ---------------------------------------------------------------------------

CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
LOOKBACK_SESSIONS = 189
SKIP_SESSIONS = 21
TOP_K = 1
REBALANCE_SESSIONS = 21

RESEARCH_UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
BENCHMARK_SYMBOL = "SPY"

FRICTION_CASES_BPS = (0, 3, 10, 25, 50)
PRIMARY_FRICTION_BPS = 3
INITIAL_CASH = 100_000.0

# Prospective checkpoint thresholds (scored sessions) and labels.
CHECKPOINT_SESSIONS_EARLY = 63
CHECKPOINT_SESSIONS_INTERIM = 126
CHECKPOINT_SESSIONS_PRIMARY = 252
EARLY_DIAGNOSTIC = "EARLY_DIAGNOSTIC"
INTERIM_DIAGNOSTIC = "INTERIM_DIAGNOSTIC"
PRIMARY_PHASE7_ASSESSMENT = "PRIMARY_PHASE7_ASSESSMENT"
CHECKPOINT_PENDING = "PENDING"

# Prospective result status semantics (evidence-oriented, not a verdict).
PHASE7_PROSPECTIVE_EVIDENCE_PENDING = "PHASE7_PROSPECTIVE_EVIDENCE_PENDING"
PHASE7_PROSPECTIVE_EVIDENCE_COMPLETE = "PHASE7_PROSPECTIVE_EVIDENCE_COMPLETE"
PHASE7_UNKNOWN_ABSTAIN = "PHASE7_UNKNOWN_ABSTAIN"
PHASE7_GOVERNANCE_FAILURE = "PHASE7_GOVERNANCE_FAILURE"

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

GEN4_PHASE7_DURABILITY_UNIVERSE_INVALID = "GEN4_PHASE7_DURABILITY_UNIVERSE_INVALID"
GEN4_PHASE7_DURABILITY_FRICTION_INVALID = "GEN4_PHASE7_DURABILITY_FRICTION_INVALID"
GEN4_PHASE7_DURABILITY_BENCHMARK_INVALID = "GEN4_PHASE7_DURABILITY_BENCHMARK_INVALID"
GEN4_PHASE7_DURABILITY_ALIGNMENT_INVALID = "GEN4_PHASE7_DURABILITY_ALIGNMENT_INVALID"
GEN4_PHASE7_DURABILITY_METRIC_INVALID = "GEN4_PHASE7_DURABILITY_METRIC_INVALID"

_DQ030_REASON = "DQ-030_UNRESOLVED"


class Generation4DurabilityError(RuntimeError):
    """Fail-closed fixed-protocol error carrying a stable ``code``."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}:{detail}")
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# Strict helpers
# ---------------------------------------------------------------------------


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False
    ).encode("utf-8")


def _metric(metric_value: Any) -> dict[str, Any]:
    return {"status": metric_value.status, "value": metric_value.value, "reason": metric_value.reason}


def _unknown(reason: str) -> dict[str, Any]:
    return {"status": "UNKNOWN", "value": None, "reason": reason}


def _window_replay(
    sessions: Sequence[pd.Timestamp],
    equity: Sequence[float],
    *,
    friction_bps: int = 0,
    initial_cash: float = INITIAL_CASH,
    total_turnover: float = 0.0,
) -> DecisionReplayResult:
    """Wrap an equity path in a ``DecisionReplayResult`` for the performance helpers."""
    states = tuple(
        DecisionState(session, 0.0, 0.0, value, 0.0, (), ())
        for session, value in zip(sessions, equity)
    )
    return DecisionReplayResult(
        DECISION_ACCOUNTING_SCHEMA,
        int(friction_bps),
        float(initial_cash),
        tuple(sessions),
        states,
        (),
        float(total_turnover),
    )


def _replay_sha256(replay: DecisionReplayResult) -> str:
    payload = {
        "schema": replay.schema_version,
        "friction_bps": replay.friction_bps,
        "initial_cash": replay.initial_cash,
        "sessions": [session.isoformat() for session in replay.sessions],
        "close_equity": [float(value) for value in replay.close_equity],
        "total_turnover": float(replay.total_turnover),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


# ---------------------------------------------------------------------------
# Fixed candidate
# ---------------------------------------------------------------------------


def resolve_fixed_candidate() -> GridCandidate:
    """Return the exact frozen candidate, verified against the frozen grid.

    No arguments are accepted, so the strategy coordinates cannot be changed.
    """
    candidate = GridCandidate(
        candidate_id=CANDIDATE_ID,
        family="G2-A",
        lookback=LOOKBACK_SESSIONS,
        skip=SKIP_SESSIONS,
        top_k=TOP_K,
        rebalance=REBALANCE_SESSIONS,
    )
    assert_frozen_candidate(candidate)
    return candidate


# ---------------------------------------------------------------------------
# Fixed targets
# ---------------------------------------------------------------------------


def build_fixed_targets(
    bars: dict[str, pd.DataFrame],
    *,
    due_from: pd.Timestamp | None = None,
    due_until: pd.Timestamp | None = None,
    align_start: pd.Timestamp | None = None,
) -> tuple:
    """Build decision targets for the fixed candidate over the supplied bars.

    Only the session window may be constrained; the strategy coordinates are
    always the frozen ones.
    """
    return build_targets(
        resolve_fixed_candidate(),
        bars,
        due_from=due_from,
        due_until=due_until,
        align_start=align_start,
    )


# ---------------------------------------------------------------------------
# Universe / friction validation
# ---------------------------------------------------------------------------


def validate_research_universe(bars: dict[str, pd.DataFrame]) -> None:
    """Reject any bars that do not cover exactly the frozen research universe."""
    if frozenset(bars) != frozenset(RESEARCH_UNIVERSE):
        raise Generation4DurabilityError(
            GEN4_PHASE7_DURABILITY_UNIVERSE_INVALID,
            "bars must cover exactly the frozen research universe",
        )


def compute_fixed_friction_cases(
    bars: dict[str, pd.DataFrame],
    targets: Sequence | None = None,
    *,
    friction_cases: Sequence[int] = FRICTION_CASES_BPS,
) -> dict[str, dict[str, Any]]:
    """Replay the fixed candidate at exactly the five frozen friction cases.

    DQ-030-dependent metrics (``max_drawdown``/``calmar``/``recovery``) are
    emitted UNKNOWN unless a bound resolution is supplied by a higher layer.
    """
    if tuple(friction_cases) != FRICTION_CASES_BPS:
        raise Generation4DurabilityError(
            GEN4_PHASE7_DURABILITY_FRICTION_INVALID,
            "friction cases must be exactly 0/3/10/25/50 bps",
        )
    validate_research_universe(bars)
    if targets is None:
        targets = build_fixed_targets(bars)
    cases: dict[str, dict[str, Any]] = {}
    for bps in FRICTION_CASES_BPS:
        replay = replay_decision_targets(
            bars, tuple(targets), friction_bps=bps, initial_cash=INITIAL_CASH
        )
        cases[str(bps)] = _case_payload(replay, bps)
    return cases


def _case_payload(replay: DecisionReplayResult, bps: int) -> dict[str, Any]:
    return {
        "friction_bps": int(bps),
        "replay_sha256": _replay_sha256(replay),
        "session_count": int(len(replay.close_equity)),
        "total_return": _metric(total_return(replay)),
        "cagr": _metric(cagr(replay)),
        "sharpe": _metric(sharpe(replay)),
        "sortino": _metric(sortino(replay)),
        "annualized_one_way_turnover": _metric(annualized_one_way_turnover(replay)),
        "rolling_12m_positive_fraction": _metric(rolling_12m_positive_fraction(replay)),
        "max_drawdown": _unknown(_DQ030_REASON),
        "calmar": _unknown(_DQ030_REASON),
        "recovery": _unknown(_DQ030_REASON),
        "exposure_invariant_passes": bool(exposure_invariant_passes(replay)),
    }


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------


def benchmark_total_return(
    bars: dict[str, pd.DataFrame],
    sessions: Sequence[pd.Timestamp],
    *,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Total return of the SPY benchmark over exactly the scored sessions.

    The benchmark is fixed to ``SPY``; every scored session must be present in
    the SPY frame (exact alignment) or the metric fails closed to UNKNOWN.
    """
    if symbol is None:
        symbol = BENCHMARK_SYMBOL
    if symbol != BENCHMARK_SYMBOL:
        raise Generation4DurabilityError(
            GEN4_PHASE7_DURABILITY_BENCHMARK_INVALID,
            f"benchmark must be {BENCHMARK_SYMBOL}",
        )
    frame = bars.get(BENCHMARK_SYMBOL)
    if frame is None:
        raise Generation4DurabilityError(
            GEN4_PHASE7_DURABILITY_UNIVERSE_INVALID, "SPY benchmark frame is missing"
        )
    closes = frame["close"]
    missing = [session for session in sessions if session not in closes.index]
    if missing:
        return _unknown(GEN4_PHASE7_DURABILITY_ALIGNMENT_INVALID)
    values = [float(closes.loc[session]) for session in sessions]
    if len(values) < 2 or any(not math.isfinite(value) or value <= 0.0 for value in values):
        return _unknown("INVALID_INPUT")
    value = values[-1] / values[0] - 1.0
    if not math.isfinite(value):
        return _unknown("INVALID_INPUT")
    return {"status": "AVAILABLE", "value": float(value), "reason": "OK"}


def excess_return(strategy_metric: Mapping[str, Any], benchmark_metric: Mapping[str, Any]) -> dict[str, Any]:
    """Strategy total return minus the benchmark total return.

    Both inputs must be AVAILABLE numeric metrics, or the result fails closed.
    """
    for name, metric in (("strategy", strategy_metric), ("benchmark", benchmark_metric)):
        if (
            not isinstance(metric, Mapping)
            or metric.get("status") != "AVAILABLE"
            or not isinstance(metric.get("value"), (int, float))
        ):
            raise Generation4DurabilityError(
                GEN4_PHASE7_DURABILITY_METRIC_INVALID,
                f"{name} metric must be an AVAILABLE numeric metric",
            )
    value = float(strategy_metric["value"]) - float(benchmark_metric["value"])
    if not math.isfinite(value):
        return _unknown("INVALID_INPUT")
    return {"status": "AVAILABLE", "value": value, "reason": "OK"}


# ---------------------------------------------------------------------------
# Scored window
# ---------------------------------------------------------------------------


def scored_equity_window(
    replay: DecisionReplayResult, scored_start: pd.Timestamp
) -> tuple[tuple[pd.Timestamp, ...], tuple[float, ...]]:
    """Slice the scored sessions/equity out of a continuous replay.

    The boundary must align exactly to a session; at least one scored session
    must remain. A one-session slice is returned as-is so that the metric
    primitives can fail closed to UNKNOWN/INSUFFICIENT_DATA rather than the
    slicer raising. The underlying portfolio state is continuous because the
    slice comes from a single replay; warmup P&L is excluded because the first
    scored session's equity is the baseline.
    """
    sessions = replay.sessions
    positions = [index for index, session in enumerate(sessions) if session >= scored_start]
    if not positions:
        raise Generation4DurabilityError(
            GEN4_PHASE7_DURABILITY_ALIGNMENT_INVALID,
            "no scored session at or after the boundary",
        )
    start_index = positions[0]
    if sessions[start_index] != scored_start:
        raise Generation4DurabilityError(
            GEN4_PHASE7_DURABILITY_ALIGNMENT_INVALID,
            "the scored boundary must align exactly to a session",
        )
    return sessions[start_index:], tuple(replay.close_equity[start_index:])


def scored_total_return(
    sessions: Sequence[pd.Timestamp], equity: Sequence[float]
) -> dict[str, Any]:
    """Total return over the scored window only (warmup excluded)."""
    equity = tuple(equity)
    if len(equity) < 2:
        return _unknown("INSUFFICIENT_DATA")
    return _metric(total_return(_window_replay(tuple(sessions), equity)))


# ---------------------------------------------------------------------------
# Subperiod primitives
# ---------------------------------------------------------------------------


def _period_returns(
    sessions: Sequence[pd.Timestamp], equity: Sequence[float], period: str
) -> dict[str, float]:
    sessions = tuple(sessions)
    equity = tuple(equity)
    if not sessions or len(sessions) != len(equity):
        return {}
    if any(not math.isfinite(value) or value <= 0.0 for value in equity):
        return {}
    groups: dict[str, list[int]] = {}
    for index, timestamp in enumerate(sessions):
        # Drop the timezone before periodizing: calendar labels are tz-agnostic
        # and converting a tz-aware timestamp to a Period emits a UserWarning.
        label = str(pd.Timestamp(timestamp).tz_localize(None).to_period(period))
        groups.setdefault(label, []).append(index)
    result: dict[str, float] = {}
    previous_last_equity = equity[0]
    for label in groups:
        last_index = groups[label][-1]
        result[label] = equity[last_index] / previous_last_equity - 1.0
        previous_last_equity = equity[last_index]
    return result


def compound_month_returns(
    sessions: Sequence[pd.Timestamp], equity: Sequence[float]
) -> dict[str, float]:
    """Compounded return per calendar month, partitioned with no overlap/gap."""
    return _period_returns(sessions, equity, "M")


def compound_year_returns(
    sessions: Sequence[pd.Timestamp], equity: Sequence[float]
) -> dict[str, float]:
    """Compounded return per calendar year, partitioned with no overlap/gap."""
    return _period_returns(sessions, equity, "Y")


def period_positive_fraction(periods: Mapping[str, float]) -> dict[str, Any]:
    if not periods:
        return _unknown("EMPTY_SUBSET")
    positive = sum(1 for value in periods.values() if value > 0.0)
    return {"status": "AVAILABLE", "value": positive / len(periods), "reason": "OK"}


def period_average(periods: Mapping[str, float], *, kind: str) -> dict[str, Any]:
    if kind not in ("winners", "losers"):
        raise Generation4DurabilityError(GEN4_PHASE7_DURABILITY_METRIC_INVALID, f"unknown kind {kind!r}")
    if kind == "winners":
        selected = [value for value in periods.values() if value > 0.0]
    else:
        selected = [value for value in periods.values() if value < 0.0]
    if not selected:
        return _unknown("EMPTY_SUBSET")
    mean = sum(selected) / len(selected)
    if not math.isfinite(mean):
        return _unknown("INVALID_INPUT")
    return {"status": "AVAILABLE", "value": float(mean), "reason": "OK"}


def longest_losing_month_sequence(months: Mapping[str, float]) -> dict[str, Any]:
    if not months:
        return _unknown("EMPTY_SUBSET")
    ordered = list(months.values())
    longest = 0
    current = 0
    for value in ordered:
        if value < 0.0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return {"status": "AVAILABLE", "value": float(longest), "reason": "OK"}


def worst_period(periods: Mapping[str, float]) -> dict[str, Any]:
    if not periods:
        return _unknown("EMPTY_SUBSET")
    value = min(periods.values())
    if not math.isfinite(value):
        return _unknown("INVALID_INPUT")
    return {"status": "AVAILABLE", "value": float(value), "reason": "OK"}


def return_concentration(periods: Mapping[str, float]) -> dict[str, Any]:
    positive = [value for value in periods.values() if value > 0.0]
    total = sum(positive)
    if not positive or total <= 0.0:
        return _unknown("EMPTY_SUBSET")
    top_three = sum(sorted(positive, reverse=True)[:3])
    value = top_three / total
    if not math.isfinite(value):
        return _unknown("INVALID_INPUT")
    return {"status": "AVAILABLE", "value": float(value), "reason": "OK"}


def rolling_period_returns(
    sessions: Sequence[pd.Timestamp], equity: Sequence[float], months: int
) -> tuple[dict[str, Any], ...]:
    """Rolling N-calendar-month returns, only where a complete window exists."""
    sessions = tuple(sessions)
    equity = tuple(equity)
    if not sessions or len(sessions) != len(equity) or months <= 0:
        return ()
    if any(not math.isfinite(value) or value <= 0.0 for value in equity):
        return ()
    results: list[dict[str, Any]] = []
    first_session = pd.Timestamp(sessions[0])
    for index in range(len(sessions)):
        boundary_target = pd.Timestamp(sessions[index]) - pd.DateOffset(months=months)
        # A complete N-month window requires data reaching back to the boundary;
        # if the earliest session is after it, the window is truncated -> skip.
        if first_session > boundary_target:
            continue
        boundary = None
        for j in range(index + 1):
            if pd.Timestamp(sessions[j]) >= boundary_target:
                boundary = j
                break
        if boundary is None:
            continue
        value = equity[index] / equity[boundary] - 1.0
        if not math.isfinite(value):
            continue
        results.append({"ending_session": sessions[index], "return": float(value)})
    return tuple(results)


# ---------------------------------------------------------------------------
# DQ-030-dependent metrics
# ---------------------------------------------------------------------------


def drawdown_calmar_recovery(
    sessions: Sequence[pd.Timestamp],
    equity: Sequence[float],
    *,
    initial_cash: float | None = INITIAL_CASH,
    cagr_value: float | None = None,
    dq030_resolved: bool = False,
) -> dict[str, dict[str, Any]]:
    """Max drawdown / Calmar / recovery, UNKNOWN unless DQ-030 is bound.

    The Generation-4 Phase-7 contract freezes DQ-030 as UNRESOLVED, so by
    default these metrics stay UNKNOWN with the explicit ``DQ-030_UNRESOLVED``
    reason. A caller that supplies a separately authoritative resolution sets
    ``dq030_resolved=True`` and the generation-2 convention is applied.
    """
    if not dq030_resolved:
        return {
            "max_drawdown": _unknown(_DQ030_REASON),
            "calmar": _unknown(_DQ030_REASON),
            "recovery": _unknown(_DQ030_REASON),
        }
    equity = tuple(float(value) for value in equity)
    if not equity or any(not math.isfinite(value) or value <= 0.0 for value in equity):
        return {
            "max_drawdown": _unknown("INVALID_INPUT"),
            "calmar": _unknown("INVALID_INPUT"),
            "recovery": _unknown("INSUFFICIENT_DATA"),
        }
    drawdown, calmar = drawdown_calmar(
        equity, initial_cash=initial_cash, cagr=cagr_value
    )
    return {
        "max_drawdown": _metric(drawdown),
        "calmar": _metric(calmar),
        "recovery": _unknown("INSUFFICIENT_DATA"),
    }


# ---------------------------------------------------------------------------
# Historical diagnostic lane (reused history only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReusedHistoryDataset:
    """A caller-supplied, already-validated reused-history dataset.

    This is the *reused* long-history lane: bars already acquired in a prior
    generation, re-expressed over the frozen research universe. It is NOT the
    Generation-4 final holdout. The caller is responsible for validation and for
    reporting an accurate ``corporate_actions_complete`` flag; this module only
    consumes the supplied dataset and never accesses a data provider.
    """

    bars: dict[str, pd.DataFrame]
    corporate_actions_complete: bool


def _trailing_window(
    sessions: Sequence[pd.Timestamp], equity: Sequence[float], months: int
) -> dict[str, Any]:
    """Trailing ``months``-calendar-month return ending at the last session.

    Emits a value only when a complete window is available (the history reaches
    back a full ``months`` from the last session); otherwise the metric fails
    closed to ``UNKNOWN``/``INCOMPLETE_WINDOW`` rather than estimating.
    """
    windows = rolling_period_returns(sessions, equity, months)
    if not windows:
        return _unknown("INCOMPLETE_WINDOW")
    return {"status": "AVAILABLE", "value": float(windows[-1]["return"]), "reason": "OK"}


def historical_durability_report(dataset: ReusedHistoryDataset) -> dict[str, Any]:
    """Build the reused-history durability diagnostic report.

    The report is strictly ``REUSED_HISTORY_DIAGNOSTIC_ONLY``: it reuses the
    fixed-protocol primitives over an already-validated reused-history dataset.
    It can never claim new out-of-sample/virgin evidence, never set production
    or live-trading authority, never change the candidate or methodology, and can
    never produce a production PASS. Any metric the older history cannot support
    is emitted UNKNOWN with an explicit reason. No provider is accessed here.
    """
    bars = dataset.bars
    cases = compute_fixed_friction_cases(bars)
    targets = build_fixed_targets(bars)
    primary_replay = replay_decision_targets(
        bars, tuple(targets), friction_bps=PRIMARY_FRICTION_BPS, initial_cash=INITIAL_CASH
    )
    sessions = primary_replay.sessions
    equity = [float(value) for value in primary_replay.close_equity]
    benchmark = benchmark_total_return(bars, sessions)
    historical_windows = {
        label: _trailing_window(sessions, equity, months)
        for label, months in (("12m", 12), ("36m", 36), ("60m", 60))
    }
    corporate_action_evidence = (
        {"status": "AVAILABLE", "value": None, "reason": "OK"}
        if dataset.corporate_actions_complete
        else _unknown("INCOMPLETE_CORPORATE_ACTIONS")
    )
    return {
        "schema": "GENERATION4-PHASE7-HISTORICAL-DURABILITY-v1",
        "classification": "REUSED_HISTORY_DIAGNOSTIC_ONLY",
        "candidate_id": CANDIDATE_ID,
        "candidate_changed": False,
        "methodology_changed": False,
        "new_out_of_sample_evidence": False,
        "virgin_holdout_evidence": False,
        "production_authority": False,
        "live_trading_authority": False,
        "production_pass": False,
        "friction_cases": cases,
        "benchmark_total_return": benchmark,
        "historical_windows": historical_windows,
        "corporate_action_evidence": corporate_action_evidence,
    }


# ---------------------------------------------------------------------------
# Prospective checkpoint lane (post-start primary evidence)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProspectiveCheckpoint:
    """Caller-supplied prospective checkpoint inputs.

    ``bars`` are the QFQ signal bars. ``execution_bars`` are the
    unadjusted execution/accounting bars. Split and dividend events are the
    reconciled corporate-action ledger. This matches the frozen Phase-6
    convention: adjusted history for signals, raw prices plus explicit
    corporate actions for fills/P&L.
    """

    bars: dict[str, pd.DataFrame]
    scored_start: pd.Timestamp
    checkpoint_cutoff: int = CHECKPOINT_SESSIONS_PRIMARY
    execution_bars: dict[str, pd.DataFrame] | None = None
    splits: tuple[SplitEvent, ...] = ()
    dividends: tuple[DividendEvent, ...] = ()
    corporate_action_reconciliation: tuple[Mapping[str, Any], ...] = ()
    evidence_bindings: Mapping[str, str] | None = None


def _checkpoint_label(scored_count: int) -> str:
    """Descriptive checkpoint label for a given number of scored sessions.

    Fewer than 63 scored sessions has no descriptive checkpoint and remains
    pending; 63/126 are descriptive only; 252+ reaches the primary assessment.
    """
    if scored_count >= CHECKPOINT_SESSIONS_PRIMARY:
        return PRIMARY_PHASE7_ASSESSMENT
    if scored_count >= CHECKPOINT_SESSIONS_INTERIM:
        return INTERIM_DIAGNOSTIC
    if scored_count >= CHECKPOINT_SESSIONS_EARLY:
        return EARLY_DIAGNOSTIC
    return CHECKPOINT_PENDING


def _prospective_governance_flags() -> dict[str, Any]:
    return {
        "paper_only": True,
        "production_authority": False,
        "live_trading_authority": False,
        "production_pass": False,
        "no_tuning_performed": True,
        "no_final_holdout_reuse": True,
        "candidate_changed": False,
        "methodology_changed": False,
    }


def _prospective_benchmark_total_return(
    execution_bars: dict[str, pd.DataFrame],
    *,
    scored_start: pd.Timestamp,
    scored_sessions: Sequence[pd.Timestamp],
    splits: Sequence[SplitEvent],
    dividends: Sequence[DividendEvent],
) -> dict[str, Any]:
    spy = execution_bars[BENCHMARK_SYMBOL]
    all_sessions = tuple(pd.DatetimeIndex(spy["close"].index))
    try:
        scored_index = all_sessions.index(scored_start)
    except ValueError:
        return _unknown(GEN4_PHASE7_DURABILITY_ALIGNMENT_INVALID)
    if scored_index <= 0:
        return _unknown("INSUFFICIENT_DATA")
    benchmark_target = DecisionTarget(
        "GEN4-PHASE7-BENCHMARK",
        all_sessions[scored_index - 1],
        scored_start,
        {BENCHMARK_SYMBOL: 1.0},
    )
    replay = replay_decision_targets(
        {BENCHMARK_SYMBOL: spy},
        [benchmark_target],
        splits=tuple(item for item in splits if item.symbol == BENCHMARK_SYMBOL),
        dividends=tuple(
            item for item in dividends if item.symbol == BENCHMARK_SYMBOL
        ),
        friction_bps=PRIMARY_FRICTION_BPS,
        initial_cash=INITIAL_CASH,
        symbols=(BENCHMARK_SYMBOL,),
    )
    sessions, equity = scored_equity_window(replay, scored_start)
    sessions = tuple(sessions)[: len(scored_sessions)]
    equity = tuple(equity)[: len(scored_sessions)]
    if tuple(sessions) != tuple(scored_sessions):
        return _unknown(GEN4_PHASE7_DURABILITY_ALIGNMENT_INVALID)
    return scored_total_return(sessions, equity)


def _prospective_checkpoint_report_unchecked(snapshot: ProspectiveCheckpoint) -> dict[str, Any]:
    """Pure frozen replay, called only after the public checkpoint gate."""
    signal_bars = snapshot.bars
    execution_bars = (
        snapshot.execution_bars if snapshot.execution_bars is not None else signal_bars
    )
    validate_research_universe(signal_bars)
    validate_research_universe(execution_bars)
    cutoff = int(snapshot.checkpoint_cutoff)
    if cutoff <= 0:
        raise Generation4DurabilityError(
            GEN4_PHASE7_DURABILITY_METRIC_INVALID, "checkpoint cutoff must be positive"
        )
    scored_start = pd.Timestamp(snapshot.scored_start)
    splits = tuple(snapshot.splits)
    dividends = tuple(snapshot.dividends)

    spy_index = sorted(pd.DatetimeIndex(execution_bars[BENCHMARK_SYMBOL]["close"].index))
    scored_calendar = [session for session in spy_index if session >= scored_start][:cutoff]
    scored_count = len(scored_calendar)
    report: dict[str, Any] = {
        "schema": "GENERATION4-PHASE7-PROSPECTIVE-CHECKPOINT-v1",
        "candidate_id": CANDIDATE_ID,
        "checkpoint_cutoff": int(cutoff),
        "scored_session_count": int(scored_count),
        "checkpoint_label": _checkpoint_label(scored_count),
        "scored_start": scored_start.isoformat(),
        "signal_price_convention": "QFQ",
        "execution_price_convention": "UNADJUSTED",
        "corporate_action_reconciliation": list(
            snapshot.corporate_action_reconciliation
        ),
        "evidence_bindings": dict(snapshot.evidence_bindings or {}),
    }
    report.update(_prospective_governance_flags())

    if scored_count == 0:
        report.update(
            status=PHASE7_PROSPECTIVE_EVIDENCE_PENDING,
            reason="NO_SCORED_SESSIONS",
            friction_cases={},
            benchmark_total_return=_unknown("INSUFFICIENT_DATA"),
            excess_return_vs_spy=_unknown("INSUFFICIENT_DATA"),
            excess_return_vs_cash=_unknown("INSUFFICIENT_DATA"),
            exposure_invariant_passes=False,
        )
        return report

    misaligned: dict[str, list[str]] = {}
    for universe_name, universe_bars in (
        ("signal", signal_bars),
        ("execution", execution_bars),
    ):
        for symbol in RESEARCH_UNIVERSE:
            index = set(pd.DatetimeIndex(universe_bars[symbol]["close"].index))
            missing = [session for session in scored_calendar if session not in index]
            if missing:
                misaligned[f"{universe_name}:{symbol}"] = [
                    session.isoformat() for session in missing
                ]
    if misaligned:
        report.update(
            status=PHASE7_UNKNOWN_ABSTAIN,
            reason="INCONSISTENT_ALIGNMENT",
            misaligned_symbols=sorted(misaligned),
            friction_cases={},
            benchmark_total_return=_unknown("INCONSISTENT_ALIGNMENT"),
            excess_return_vs_spy=_unknown("INCONSISTENT_ALIGNMENT"),
            excess_return_vs_cash=_unknown("INCONSISTENT_ALIGNMENT"),
            exposure_invariant_passes=False,
        )
        return report

    targets = build_fixed_targets(
        signal_bars,
        due_from=scored_start,
        due_until=scored_calendar[-1],
        align_start=scored_start,
    )
    replays = {
        bps: replay_decision_targets(
            execution_bars,
            tuple(targets),
            splits=splits,
            dividends=dividends,
            friction_bps=bps,
            initial_cash=INITIAL_CASH,
            symbols=RESEARCH_UNIVERSE,
        )
        for bps in FRICTION_CASES_BPS
    }
    primary_sessions, primary_equity = scored_equity_window(
        replays[PRIMARY_FRICTION_BPS], scored_start
    )
    primary_sessions = tuple(primary_sessions)[:cutoff]
    primary_equity = tuple(primary_equity)[:cutoff]
    if len(primary_sessions) != scored_count:
        report.update(
            status=PHASE7_UNKNOWN_ABSTAIN,
            reason="CANNOT_RECONCILE",
            friction_cases={},
            benchmark_total_return=_unknown("CANNOT_RECONCILE"),
            excess_return_vs_spy=_unknown("CANNOT_RECONCILE"),
            excess_return_vs_cash=_unknown("CANNOT_RECONCILE"),
            exposure_invariant_passes=False,
        )
        return report
    scored_sessions = primary_sessions

    cases: dict[str, dict[str, Any]] = {}
    for bps in FRICTION_CASES_BPS:
        sessions, equity = scored_equity_window(replays[bps], scored_start)
        sessions = tuple(sessions)[:cutoff]
        equity = tuple(equity)[:cutoff]
        cases[str(bps)] = {
            "friction_bps": int(bps),
            "scored_session_count": int(len(sessions)),
            "total_return": scored_total_return(sessions, equity),
        }

    primary_total = cases[str(PRIMARY_FRICTION_BPS)]["total_return"]
    benchmark = _prospective_benchmark_total_return(
        execution_bars,
        scored_start=scored_start,
        scored_sessions=scored_sessions,
        splits=splits,
        dividends=dividends,
    )
    if primary_total["status"] == "AVAILABLE" and benchmark["status"] == "AVAILABLE":
        excess_spy = excess_return(primary_total, benchmark)
    else:
        excess_spy = _unknown("INSUFFICIENT_DATA")
    if primary_total["status"] == "AVAILABLE":
        excess_cash = {
            "status": "AVAILABLE",
            "value": float(primary_total["value"]),
            "reason": "OK",
        }
    else:
        excess_cash = _unknown(primary_total["reason"])

    exposure_ok = bool(exposure_invariant_passes(replays[PRIMARY_FRICTION_BPS]))
    months = compound_month_returns(scored_sessions, primary_equity)
    dq = drawdown_calmar_recovery(scored_sessions, primary_equity)

    required_available = (
        all(case["total_return"]["status"] == "AVAILABLE" for case in cases.values())
        and benchmark["status"] == "AVAILABLE"
        and excess_spy["status"] == "AVAILABLE"
        and excess_cash["status"] == "AVAILABLE"
        and exposure_ok
    )
    if scored_count < CHECKPOINT_SESSIONS_PRIMARY:
        status = PHASE7_PROSPECTIVE_EVIDENCE_PENDING
    elif required_available:
        status = PHASE7_PROSPECTIVE_EVIDENCE_COMPLETE
    else:
        status = PHASE7_UNKNOWN_ABSTAIN

    report.update(
        status=status,
        friction_cases=cases,
        benchmark_total_return=benchmark,
        excess_return_vs_spy=excess_spy,
        excess_return_vs_cash=excess_cash,
        exposure_invariant_passes=exposure_ok,
        calendar_month_returns=months,
        positive_month_fraction=period_positive_fraction(months),
        worst_complete_month=worst_period(months),
        rolling_12m_return=_trailing_window(scored_sessions, primary_equity, 12),
        max_drawdown=dq["max_drawdown"],
        calmar=dq["calmar"],
        recovery=dq["recovery"],
    )
    return report


def prospective_checkpoint_report(
    snapshot: ProspectiveCheckpoint, *, permit: object | None = None
) -> dict[str, Any]:
    """Reject preconstructed snapshots at the public Python boundary."""
    from investment_tracker.independent_audit.post_generation3.phase7_checkpoint_gate import (
        CheckpointGateError,
        PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED,
    )

    raise CheckpointGateError(PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED)


def _governed_prospective_checkpoint_report(
    snapshot: ProspectiveCheckpoint, *, permit: object
) -> dict[str, Any]:
    """Internal report step for a snapshot loaded after capability consumption."""
    from investment_tracker.independent_audit.post_generation3.phase7_checkpoint_gate import (
        begin_checkpoint_report,
        complete_checkpoint_report,
    )

    begin_checkpoint_report(permit, snapshot)
    report = _prospective_checkpoint_report_unchecked(snapshot)
    complete_checkpoint_report(permit, snapshot, report)
    return report
