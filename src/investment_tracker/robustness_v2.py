"""Prospective ROBUST-v2.0 dependence-sensitivity rule.

ROBUST-v1.0 remains frozen and INCONCLUSIVE for RB09. This module defines a
new, outcome-independent same-session tie treatment for future Candidate-v2
validation. It must never be used to relabel the v1 robustness result.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Iterable, Sequence

from .governance import assert_symbol_allowed

ROBUST_V2_VERSION = "ROBUST-v2.0"
RB09_MIN_NONOVERLAP_CLUSTERS = 20
RB09_WINDOW_SESSIONS = 20


class RB09Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class DependenceObservation:
    episode_id: str
    asset: str
    entry_date: date
    excess_spy_20d: Decimal
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class SameSessionCluster:
    entry_date: date
    assets: tuple[str, ...]
    episode_ids: tuple[str, ...]
    representative_excess_spy_20d: Decimal


@dataclass(frozen=True)
class RB09V2Report:
    version: str
    status: RB09Status
    clean_observation_count: int
    same_session_cluster_count: int
    nonoverlap_cluster_count: int
    median_nonoverlap_excess_spy_20d: Decimal | None
    rule: str


def _median(values: Sequence[Decimal]) -> Decimal:
    if not values:
        raise ValueError("median requires at least one value")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def build_same_session_clusters(
    observations: Iterable[DependenceObservation],
) -> list[SameSessionCluster]:
    """Collapse same-session cross-proxy entries without an arbitrary asset tie-break.

    All clean episodes that enter on the same trading session form one cluster.
    The cluster representative is the equal-weight median of 20-day SPY excess
    returns. This rule is fixed before Candidate-v2 unseen validation.
    """

    grouped: dict[date, list[DependenceObservation]] = defaultdict(list)
    for row in observations:
        asset = assert_symbol_allowed(row.asset)
        if not row.episode_id:
            raise ValueError("episode_id is required")
        if row.dq_status != "CLEAN":
            continue
        grouped[row.entry_date].append(
            DependenceObservation(
                episode_id=row.episode_id,
                asset=asset,
                entry_date=row.entry_date,
                excess_spy_20d=row.excess_spy_20d,
                dq_status=row.dq_status,
            )
        )

    clusters: list[SameSessionCluster] = []
    for entry_date in sorted(grouped):
        rows = sorted(grouped[entry_date], key=lambda r: (r.asset, r.episode_id))
        clusters.append(
            SameSessionCluster(
                entry_date=entry_date,
                assets=tuple(row.asset for row in rows),
                episode_ids=tuple(row.episode_id for row in rows),
                representative_excess_spy_20d=_median(
                    [row.excess_spy_20d for row in rows]
                ),
            )
        )
    return clusters


def select_nonoverlap_clusters(
    clusters: Iterable[SameSessionCluster],
    benchmark_sessions: Sequence[date],
) -> list[SameSessionCluster]:
    """Greedy chronological 20-session selection with a fully specified tie rule.

    Select the earliest eligible same-session cluster, then the next cluster
    whose benchmark-session index is at least 20 sessions later. A 20-day
    episode entering at index i occupies entry sessions i..i+19, therefore the
    next non-overlapping entry may occur at i+20.
    """

    sessions = list(benchmark_sessions)
    if sessions != sorted(set(sessions)):
        raise ValueError("benchmark_sessions must be unique and strictly increasing")
    index = {session: i for i, session in enumerate(sessions)}

    ordered = sorted(clusters, key=lambda row: row.entry_date)
    selected: list[SameSessionCluster] = []
    next_allowed = 0
    for cluster in ordered:
        if cluster.entry_date not in index:
            raise ValueError(
                f"cluster entry date absent from benchmark calendar: {cluster.entry_date}"
            )
        position = index[cluster.entry_date]
        if position < next_allowed:
            continue
        selected.append(cluster)
        next_allowed = position + RB09_WINDOW_SESSIONS
    return selected


def evaluate_rb09_v2(
    observations: Iterable[DependenceObservation],
    benchmark_sessions: Sequence[date],
) -> RB09V2Report:
    clusters = build_same_session_clusters(observations)
    clean_count = sum(len(cluster.episode_ids) for cluster in clusters)
    selected = select_nonoverlap_clusters(clusters, benchmark_sessions)

    if len(selected) < RB09_MIN_NONOVERLAP_CLUSTERS:
        status = RB09Status.INCONCLUSIVE
        median = None if not selected else _median(
            [row.representative_excess_spy_20d for row in selected]
        )
    else:
        median = _median(
            [row.representative_excess_spy_20d for row in selected]
        )
        status = RB09Status.PASS if median >= 0 else RB09Status.FAIL

    return RB09V2Report(
        version=ROBUST_V2_VERSION,
        status=status,
        clean_observation_count=clean_count,
        same_session_cluster_count=len(clusters),
        nonoverlap_cluster_count=len(selected),
        median_nonoverlap_excess_spy_20d=median,
        rule=(
            "same-session episodes -> equal-weight median cluster; chronological "
            "greedy selection; next eligible entry >=20 benchmark sessions later; "
            ">=20 clusters required; median 20d SPY excess >=0 required for PASS"
        ),
    )
