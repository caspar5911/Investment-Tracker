"""Generation-2 frozen candidate grid and canonical manifest (C1).

This module materializes the *exact* parameter grids frozen in the
generation-2 governance preregistration and exposes a stable, content-addressed
manifest that must be committed **before** any generation-2 campaign runs.

The four frozen families (from
``2026-09-22-generation2-governance-preregistration.md``):

- ``G2-A`` dual-momentum rotation                     -> 48 candidates
- ``G2-B`` trend-filtered momentum                    -> 54 candidates
- ``G2-C`` volatility-scaled momentum                 -> 24 candidates
- ``G2-D`` multi-horizon momentum ensemble            -> 36 candidates

Total deterministic budget: 162 candidates. No grid value may be added,
removed, or changed after the first generation-2 candidate is evaluated, so the
enumeration here is the single source of truth for the campaign and the
manifest is the immutable evidence of that decision.

Candidate identities are deterministic, self-describing strings so the frozen
lexicographic tie-breaks ("ascending candidate_id") are well defined.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

FAMILY_LIMITS = {
    "G2-A": 48,
    "G2-B": 54,
    "G2-C": 24,
    "G2-D": 36,
}

TOTAL_CANDIDATE_BUDGET = 162

RESEARCH_SYMBOLS = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")

# Frozen decision-ledger economics (preregistration "Paper-only" section).
INITIAL_CASH = 100_000.0
PRIMARY_FRICTION_BPS = 3
REQUIRED_FRICTION_CASES_BPS = (0, 3, 10, 25, 50)

GRID_MANIFEST_SCHEMA = "GENERATION2-GRID-MANIFEST-v1"
GRID_MANIFEST_STATUS = "FROZEN_BEFORE_CAMPAIGN"

# Per-family frozen grid axes.
_G2A_LOOKBACK = (63, 126, 189, 252)
_G2A_SKIP = (0, 21)
_G2A_TOP_K = (1, 2, 3)
_G2A_REBALANCE = (21, 42)

_G2B_LOOKBACK = (63, 126, 252)
_G2B_TREND_MA = (126, 200, 252)
_G2B_TOP_K = (1, 2, 3)
_G2B_REBALANCE = (21, 42)
_G2B_SKIP = 21

_G2C_LOOKBACK = (63, 126, 252)
_G2C_VOL_LOOKBACK = (20, 63)
_G2C_TOP_K = (2, 3)
_G2C_REBALANCE = (21, 42)
_G2C_SKIP = 21

_G2D_HORIZON_SETS = ((21, 63, 126), (63, 126, 252), (21, 126, 252))
_G2D_SKIP = (0, 21)
_G2D_TOP_K = (1, 2, 3)
_G2D_REBALANCE = (21, 42)

__all__ = [
    "FAMILY_LIMITS",
    "GridCandidate",
    "REQUIRED_FRICTION_CASES_BPS",
    "RESEARCH_SYMBOLS",
    "TOTAL_CANDIDATE_BUDGET",
    "build_generation2_grid",
    "canonical_grid_manifest",
    "grid_manifest_sha256",
]


@dataclass(frozen=True)
class GridCandidate:
    """A single frozen generation-2 candidate (one grid position).

    ``family`` is one of ``G2-A``/``G2-B``/``G2-C``/``G2-D``. The remaining
    fields are the frozen grid coordinates for that family; unused coordinates
    are ``None``. ``candidate_id`` is a deterministic, self-describing string.
    """

    candidate_id: str
    family: str
    lookback: int | None = None
    skip: int | None = None
    top_k: int = None
    rebalance: int | None = None
    trend_ma: int | None = None
    vol_lookback: int | None = None
    horizon_set: tuple[int, ...] | None = None

    @property
    def max_lookback(self) -> int:
        """The furthest trailing session any signal for this candidate reads.

        This drives the causal warm-up length: a candidate is only "live" once
        this many prior sessions exist, and no signal may read further back.
        """
        offsets: list[int] = []
        if self.lookback is not None:
            offsets.append(self.lookback)
        if self.skip:
            offsets.append(self.skip)
        if self.trend_ma is not None:
            offsets.append(self.trend_ma)
        if self.vol_lookback is not None:
            offsets.append(self.vol_lookback)
        if self.horizon_set:
            offsets.append(max(self.horizon_set))
        if not offsets:
            raise ValueError(f"{self.candidate_id} has no lookback coordinates")
        return max(offsets)

    def to_manifest_dict(self) -> dict:
        payload = asdict(self)
        if payload.get("horizon_set") is not None:
            payload["horizon_set"] = list(payload["horizon_set"])
        return payload


def _id_a(lookback: int, skip: int, top_k: int, rebalance: int) -> str:
    return f"G2-A|lookback={lookback}|skip={skip}|top_k={top_k}|rebalance={rebalance}"


def _id_b(lookback: int, trend_ma: int, top_k: int, rebalance: int) -> str:
    return f"G2-B|lookback={lookback}|trend_ma={trend_ma}|top_k={top_k}|rebalance={rebalance}"


def _id_c(lookback: int, vol_lookback: int, top_k: int, rebalance: int) -> str:
    return f"G2-C|lookback={lookback}|vol_lookback={vol_lookback}|top_k={top_k}|rebalance={rebalance}"


def _id_d(horizon_set: tuple[int, ...], skip: int, top_k: int, rebalance: int) -> str:
    horizon = "+".join(str(h) for h in horizon_set)
    return f"G2-D|horizons={horizon}|skip={skip}|top_k={top_k}|rebalance={rebalance}"


def _family_a() -> list[GridCandidate]:
    candidates: list[GridCandidate] = []
    for lookback in _G2A_LOOKBACK:
        for skip in _G2A_SKIP:
            for top_k in _G2A_TOP_K:
                for rebalance in _G2A_REBALANCE:
                    candidates.append(
                        GridCandidate(
                            candidate_id=_id_a(lookback, skip, top_k, rebalance),
                            family="G2-A",
                            lookback=lookback,
                            skip=skip,
                            top_k=top_k,
                            rebalance=rebalance,
                        )
                    )
    return candidates


def _family_b() -> list[GridCandidate]:
    candidates: list[GridCandidate] = []
    for lookback in _G2B_LOOKBACK:
        for trend_ma in _G2B_TREND_MA:
            for top_k in _G2B_TOP_K:
                for rebalance in _G2B_REBALANCE:
                    candidates.append(
                        GridCandidate(
                            candidate_id=_id_b(lookback, trend_ma, top_k, rebalance),
                            family="G2-B",
                            lookback=lookback,
                            skip=_G2B_SKIP,
                            top_k=top_k,
                            rebalance=rebalance,
                            trend_ma=trend_ma,
                        )
                    )
    return candidates


def _family_c() -> list[GridCandidate]:
    candidates: list[GridCandidate] = []
    for lookback in _G2C_LOOKBACK:
        for vol_lookback in _G2C_VOL_LOOKBACK:
            for top_k in _G2C_TOP_K:
                for rebalance in _G2C_REBALANCE:
                    candidates.append(
                        GridCandidate(
                            candidate_id=_id_c(lookback, vol_lookback, top_k, rebalance),
                            family="G2-C",
                            lookback=lookback,
                            skip=_G2C_SKIP,
                            top_k=top_k,
                            rebalance=rebalance,
                            vol_lookback=vol_lookback,
                        )
                    )
    return candidates


def _family_d() -> list[GridCandidate]:
    candidates: list[GridCandidate] = []
    for horizon_set in _G2D_HORIZON_SETS:
        for skip in _G2D_SKIP:
            for top_k in _G2D_TOP_K:
                for rebalance in _G2D_REBALANCE:
                    candidates.append(
                        GridCandidate(
                            candidate_id=_id_d(horizon_set, skip, top_k, rebalance),
                            family="G2-D",
                            skip=skip,
                            top_k=top_k,
                            rebalance=rebalance,
                            horizon_set=horizon_set,
                        )
                    )
    return candidates


def build_generation2_grid() -> tuple[GridCandidate, ...]:
    """Enumerate the exact 162 frozen candidates, one per deterministic grid slot.

    The enumeration order is stable (family, then frozen axis order) so the
    resulting ``candidate_id`` set and the manifest are byte-for-byte
    reproducible.
    """
    candidates: list[GridCandidate] = [
        *(_family_a()),
        *(_family_b()),
        *(_family_c()),
        *(_family_d()),
    ]
    ids = [c.candidate_id for c in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("generation-2 grid produced duplicate candidate ids")
    for family, limit in FAMILY_LIMITS.items():
        seen = [c for c in candidates if c.family == family]
        if len(seen) != limit:
            raise ValueError(f"family {family} has {len(seen)} candidates, expected {limit}")
    if len(candidates) != TOTAL_CANDIDATE_BUDGET:
        raise ValueError(
            f"generation-2 grid has {len(candidates)} candidates, expected {TOTAL_CANDIDATE_BUDGET}"
        )
    return tuple(candidates)


def _manifest_payload() -> dict:
    grid = build_generation2_grid()
    families: dict[str, list[dict]] = {}
    for candidate in grid:
        families.setdefault(candidate.family, []).append(candidate.to_manifest_dict())
    return {
        "schema_version": GRID_MANIFEST_SCHEMA,
        "status": GRID_MANIFEST_STATUS,
        "generation": "GENERATION_2",
        "research_symbols": list(RESEARCH_SYMBOLS),
        "initial_cash": INITIAL_CASH,
        "primary_friction_bps": PRIMARY_FRICTION_BPS,
        "required_friction_cases_bps": list(REQUIRED_FRICTION_CASES_BPS),
        "family_candidate_counts": {
            family: len(families[family]) for family in sorted(families)
        },
        "total_candidates": len(grid),
        "candidates": [candidate.to_manifest_dict() for candidate in grid],
        "frozen_rules": {
            "long_only": True,
            "no_leverage": True,
            "no_short": True,
            "signal_from_completed_information_only": True,
            "earliest_fill_next_session": True,
            "no_same_bar_lookahead": True,
            "no_adaptive_grid_expansion": True,
            "no_result_dependent_family_replacement": True,
        },
    }


def grid_manifest_sha256() -> str:
    """Content identity of the canonical grid manifest (self-excluding hash)."""
    payload = _manifest_payload()
    return hashlib.sha256(canonical_grid_manifest_bytes(payload)).hexdigest()


def canonical_grid_manifest_bytes(payload: dict) -> bytes:
    """Canonical byte encoding shared by hashing and materialization."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_grid_manifest() -> dict:
    """The full manifest including its own content identity."""
    payload = _manifest_payload()
    return dict(payload, manifest_sha256=grid_manifest_sha256())
