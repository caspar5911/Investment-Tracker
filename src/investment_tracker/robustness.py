"""Frozen ROBUST-v1.0 analysis over coordinator-issued outcome snapshots.

This module deliberately does not read market data or canonical storage.  Callers
must provide immutable, already validated episode-level observations.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import random
from typing import Iterable, Mapping

from .governance import assert_symbol_allowed

ROBUST_VERSION = "ROBUST-v1.0"
REQUIRED_PHASE_A = frozenset({"ETN", "PWR", "VRT", "URA", "CIBR", "SMH", "COPX", "XLE"})
FRICTION_SCENARIOS = (0, 10, 25)


class RobustnessBlockedError(ValueError):
    """Raised before analysis when canonical Phase-A evidence is incomplete."""


@dataclass(frozen=True)
class RobustObservation:
    episode_id: str
    asset: str
    horizon_td: int
    friction_bps: int
    return_net: Decimal
    baseline_return_net: Decimal
    regime: str
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class RobustnessReport:
    version: str
    observation_count: int
    quarantined_count: int
    unique_episode_count: int
    dependence_disclosure: str
    means_by_asset: Mapping[str, Decimal]
    means_by_regime: Mapping[str, Decimal]
    means_by_horizon: Mapping[int, Decimal]
    means_by_friction: Mapping[int, Decimal]
    baseline_relative_mean: Decimal
    negative_tail_p05: Decimal
    top_episode_gain_concentration: Decimal
    leave_one_asset_out: Mapping[str, Decimal]
    block_bootstrap_p05: Decimal
    block_bootstrap_p95: Decimal


def _mean(values: Iterable[Decimal]) -> Decimal:
    items = list(values)
    if not items:
        raise RobustnessBlockedError("BLOCKED_REQUIRED_INPUT: empty robustness stratum")
    return sum(items, Decimal(0)) / Decimal(len(items))


def _group_means(rows: list[RobustObservation], field: str) -> dict[object, Decimal]:
    groups: dict[object, list[Decimal]] = defaultdict(list)
    for row in rows:
        groups[getattr(row, field)].append(row.return_net)
    return {key: _mean(groups[key]) for key in sorted(groups)}


def _percentile(values: list[Decimal], proportion: Decimal) -> Decimal:
    ordered = sorted(values)
    index = int((Decimal(len(ordered) - 1) * proportion).to_integral_value(rounding="ROUND_FLOOR"))
    return ordered[index]


def _bootstrap(rows: list[RobustObservation], *, draws: int, block_size: int) -> tuple[Decimal, Decimal]:
    # Seed is a digest of sorted immutable inputs, not runtime entropy.
    tokens = [f"{r.episode_id}|{r.asset}|{r.horizon_td}|{r.friction_bps}|{r.return_net}" for r in rows]
    seed = int.from_bytes(hashlib.sha256("\n".join(sorted(tokens)).encode()).digest()[:8], "big")
    rng = random.Random(seed)
    ordered = sorted(rows, key=lambda r: (r.asset, r.episode_id, r.horizon_td, r.friction_bps))
    means: list[Decimal] = []
    for _ in range(draws):
        sample: list[RobustObservation] = []
        while len(sample) < len(ordered):
            start = rng.randrange(len(ordered))
            sample.extend(ordered[(start + offset) % len(ordered)] for offset in range(block_size))
        means.append(_mean(row.return_net for row in sample[: len(ordered)]))
    return _percentile(means, Decimal("0.05")), _percentile(means, Decimal("0.95"))


def analyze_phase_a(
    observations: Iterable[RobustObservation],
    phase_states: Mapping[str, str],
    *,
    bootstrap_draws: int = 1000,
    block_size: int = 3,
) -> RobustnessReport:
    """Run deterministic analysis, failing closed until all Phase-A evidence is frozen."""
    normalized_states = {assert_symbol_allowed(k): v for k, v in phase_states.items()}
    missing = sorted(asset for asset in REQUIRED_PHASE_A if normalized_states.get(asset) != "BASELINES_COMPLETE")
    if missing:
        raise RobustnessBlockedError("BLOCKED_REQUIRED_INPUT: coordinator snapshots at BASELINES_COMPLETE for " + ", ".join(missing))
    if bootstrap_draws < 20 or block_size < 1:
        raise ValueError("bootstrap_draws must be >= 20 and block_size must be positive")

    supplied = list(observations)
    for row in supplied:
        assert_symbol_allowed(row.asset)
        if row.friction_bps not in FRICTION_SCENARIOS:
            raise ValueError("friction_bps must be one of 0, 10, 25")
        if not row.episode_id or not row.regime:
            raise ValueError("episode_id and preclassified regime are required")
    rows = [row for row in supplied if row.dq_status == "CLEAN"]
    if not rows:
        raise RobustnessBlockedError("BLOCKED_REQUIRED_INPUT: clean canonical Phase-A episode outcomes")
    represented = {row.asset for row in rows}
    absent = sorted(REQUIRED_PHASE_A - represented)
    if absent:
        raise RobustnessBlockedError("BLOCKED_REQUIRED_INPUT: clean episode outcomes for " + ", ".join(absent))
    scenarios = {row.friction_bps for row in rows}
    if scenarios != set(FRICTION_SCENARIOS):
        raise RobustnessBlockedError("BLOCKED_REQUIRED_INPUT: complete 0/10/25 bps friction outcomes")

    episode_gains: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for row in rows:
        episode_gains[(row.asset, row.episode_id)] += max(row.return_net, Decimal(0))
    gains = sorted(episode_gains.values(), reverse=True)
    total_gain = sum(gains, Decimal(0))
    concentration = Decimal(0) if not total_gain else sum(gains[: max(1, len(gains) // 10)], Decimal(0)) / total_gain
    leave_out = {asset: _mean(r.return_net for r in rows if r.asset != asset) for asset in sorted(REQUIRED_PHASE_A)}
    lo, hi = _bootstrap(rows, draws=bootstrap_draws, block_size=block_size)
    returns = [r.return_net for r in rows]
    return RobustnessReport(
        version=ROBUST_VERSION,
        observation_count=len(rows),
        quarantined_count=len(supplied) - len(rows),
        unique_episode_count=len({(r.asset, r.episode_id) for r in rows}),
        dependence_disclosure="Episode-level rows may repeat across horizons/friction; block bootstrap preserves local ordered dependence.",
        means_by_asset=_group_means(rows, "asset"),
        means_by_regime=_group_means(rows, "regime"),
        means_by_horizon=_group_means(rows, "horizon_td"),
        means_by_friction=_group_means(rows, "friction_bps"),
        baseline_relative_mean=_mean(r.return_net - r.baseline_return_net for r in rows),
        negative_tail_p05=_percentile(returns, Decimal("0.05")),
        top_episode_gain_concentration=concentration,
        leave_one_asset_out=leave_out,
        block_bootstrap_p05=lo,
        block_bootstrap_p95=hi,
    )
