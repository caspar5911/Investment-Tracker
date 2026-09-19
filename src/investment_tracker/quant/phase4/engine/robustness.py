from __future__ import annotations

import math
from typing import Final, Sequence

import numpy as np

from investment_tracker.quant.phase4.engine.execution import replay_targets
from investment_tracker.quant.phase4.engine.models import (
    BootstrapEvidence,
    FoldAuthority,
    FoldSliceEvidence,
    FrictionCaseEvidence,
    FrictionEvidence,
    Gate2SealError,
    MetricValue,
    PortfolioReplay,
    RegimeAuthority,
    RegimePartitionEvidence,
    UnavailableStatistics,
)


FRICTION_CASE_BPS: Final = (0, 3, 10, 25, 50)
PRIMARY_FRICTION_BPS: Final = 3
BOOTSTRAP_DRAWS: Final = 2000
BOOTSTRAP_SEED: Final = 0
PERSISTENT_OOS_LIMIT: Final = 50


def _finite(value: float | None) -> MetricValue:
    numeric = None if value is None else float(value)
    if numeric is None or not math.isfinite(numeric):
        return MetricValue(value=None, status="UNKNOWN", reason="INVALID_INPUT")
    return MetricValue(value=numeric, status="AVAILABLE", reason="OK")


def run_friction_cases(
    scored: object,
    targets: Sequence[object | None],
) -> FrictionEvidence:
    """Replay the same sealed targets at the exact (0, 3, 10, 25, 50) bps cases."""

    if scored.role != "SCORED":  # type: ignore[attr-defined]
        raise Gate2SealError(
            "MARKET_PANEL_INVALID", "friction cases require a scored market panel"
        )
    cases: list[FrictionCaseEvidence] = []
    returns: dict[int, MetricValue] = {}
    identities: set[tuple[str | None, str | None]] = set()
    for bps in FRICTION_CASE_BPS:
        replay = replay_targets(scored, targets, friction_bps=bps)  # type: ignore[arg-type]
        equity = tuple(replay.close_equity)
        total_return_value = equity[-1] / equity[0] - 1.0
        total_return = _finite(total_return_value)
        returns[bps] = total_return
        identities.add((replay.candidate_id, replay.binding_sha256))
        cases.append(
            FrictionCaseEvidence(
                friction_bps=bps,
                candidate_id=replay.candidate_id,
                binding_sha256=replay.binding_sha256,
                total_return=total_return,
                total_turnover=_finite(float(replay.total_turnover)),
                close_equity=equity,
                unavailable_statistics=UnavailableStatistics(),
            )
        )
    if len(identities) != 1:
        raise Gate2SealError(
            "DURABILITY_EVIDENCE_INVALID",
            "friction cases must preserve one candidate/binding identity",
        )
    candidate_id, binding_sha256 = next(iter(identities))
    numerator = returns[25].value
    denominator = returns[3].value
    if (
        numerator is None
        or denominator is None
        or denominator == 0.0
        or not math.isfinite(denominator)
    ):
        ratio = MetricValue(
            value=None, status="UNKNOWN", reason="NONPOSITIVE_DENOMINATOR"
        )
    else:
        ratio = _finite(numerator / denominator)
    return FrictionEvidence(
        candidate_id=candidate_id,
        binding_sha256=binding_sha256,
        cases=tuple(cases),
        friction_retention_ratio=ratio,
        unavailable_statistics=UnavailableStatistics(),
    )


def bootstrap_median_daily_return(
    returns: Sequence[float],
) -> BootstrapEvidence:
    """Median-daily-return bootstrap with 2000 replacement draws, seed 0."""

    if len(returns) < 2:
        raise Gate2SealError(
            "DURABILITY_EVIDENCE_INVALID",
            "bootstrap requires at least two daily returns",
        )
    values = np.asarray(tuple(float(value) for value in returns), dtype=np.float64)
    if not bool(np.all(np.isfinite(values))):
        raise Gate2SealError(
            "DURABILITY_EVIDENCE_INVALID", "daily returns must be finite"
        )
    sample_size = int(values.size)
    generator = np.random.default_rng(BOOTSTRAP_SEED)
    indices = generator.integers(0, sample_size, size=(BOOTSTRAP_DRAWS, sample_size))
    resampled = np.take(values, indices, axis=0)
    draw_medians = np.median(resampled, axis=1)
    return BootstrapEvidence(
        sample_size=sample_size,
        observed_median=_finite(float(np.median(values))),
        percentile_05=_finite(float(np.percentile(draw_medians, 5))),
        percentile_95=_finite(float(np.percentile(draw_medians, 95))),
        unavailable_statistics=UnavailableStatistics(),
    )


def neighbor_trial_ids(
    family: object,
    parameter_tuple_sha256: str,
) -> tuple[str, ...]:
    """Sealed adjacent-value trial identifiers for one parameter tuple only."""

    candidates = getattr(family, "candidates")
    by_tuple = {item.parameter_tuple_sha256: item for item in candidates}
    if parameter_tuple_sha256 not in by_tuple:
        raise Gate2SealError(
            "FIXED_STRATEGY_INVARIANT_FAILURE",
            "parameter tuple is not present in the sealed family",
        )
    neighbors = family.neighbors(parameter_tuple_sha256)  # type: ignore[attr-defined]
    return tuple(sorted(item.trial_id for item in neighbors))


def _require_replay(replay: object, *, field: str) -> PortfolioReplay:
    if not isinstance(replay, PortfolioReplay) or not replay.states:
        raise Gate2SealError(field, "robustness slicing requires a portfolio replay")
    return replay


def slice_continuous_folds(
    replay: object,
    fold_authority: FoldAuthority | None,
) -> FoldSliceEvidence:
    """Slice one continuous replay into folds without resetting the series."""

    portfolio = _require_replay(replay, field="FOLD_AUTHORITY_MISSING")
    if fold_authority is None or not isinstance(fold_authority, FoldAuthority):
        raise Gate2SealError(
            "FOLD_AUTHORITY_MISSING", "fold slicing requires an exact fold authority"
        )
    sessions = portfolio.sessions
    index_of = {session: i for i, session in enumerate(sessions)}
    fold_returns: list[MetricValue] = []
    equity_start: list[float] = []
    equity_end: list[float] = []
    equity = portfolio.close_equity
    for start, end in fold_authority.boundaries:
        if start not in index_of or end not in index_of:
            raise Gate2SealError(
                "FOLD_AUTHORITY_MISSING", "fold anchors must be scored sessions"
            )
        start_index = index_of[start]
        end_index = index_of[end]
        start_equity = equity[start_index]
        end_equity = equity[end_index]
        equity_start.append(start_equity)
        equity_end.append(end_equity)
        fold_returns.append(_finite(end_equity / start_equity - 1.0))
    return FoldSliceEvidence(
        candidate_id=portfolio.candidate_id,
        binding_sha256=portfolio.binding_sha256,
        fold_ids=fold_authority.fold_ids,
        fold_returns=tuple(fold_returns),
        fold_equity_start=tuple(equity_start),
        fold_equity_end=tuple(equity_end),
        unavailable_statistics=UnavailableStatistics(),
    )


def partition_regimes(
    replay: object,
    regime_authority: RegimeAuthority | None,
) -> RegimePartitionEvidence:
    """Partition scored sessions into exact, nonoverlapping regimes."""

    portfolio = _require_replay(replay, field="REGIME_AUTHORITY_MISSING")
    if regime_authority is None or not isinstance(regime_authority, RegimeAuthority):
        raise Gate2SealError(
            "REGIME_AUTHORITY_MISSING",
            "regime partitioning requires an exact regime authority",
        )
    expected = set(portfolio.sessions)
    supplied = {session for session, _ in regime_authority.session_regime}
    if supplied != expected:
        raise Gate2SealError(
            "REGIME_AUTHORITY_MISSING",
            "regime authority must cover the scored sessions exactly",
        )
    by_session = dict(regime_authority.session_regime)
    regime_ids = regime_authority.regime_ids
    sessions_by_regime: dict[str, list] = {regime: [] for regime in regime_ids}
    for session in portfolio.sessions:
        sessions_by_regime[by_session[session]].append(session)
    return RegimePartitionEvidence(
        candidate_id=portfolio.candidate_id,
        binding_sha256=portfolio.binding_sha256,
        regime_ids=regime_ids,
        regime_session_counts=tuple(
            len(sessions_by_regime[regime]) for regime in regime_ids
        ),
        regime_sessions=tuple(
            tuple(sessions_by_regime[regime]) for regime in regime_ids
        ),
        unavailable_statistics=UnavailableStatistics(),
    )


__all__ = (
    "BOOTSTRAP_DRAWS",
    "BOOTSTRAP_SEED",
    "FRICTION_CASE_BPS",
    "PERSISTENT_OOS_LIMIT",
    "PRIMARY_FRICTION_BPS",
    "bootstrap_median_daily_return",
    "neighbor_trial_ids",
    "partition_regimes",
    "run_friction_cases",
    "slice_continuous_folds",
)
