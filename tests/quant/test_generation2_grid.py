from __future__ import annotations

import hashlib
import json
from pathlib import Path

from investment_tracker.quant.generation2.grid import (
    canonical_grid_manifest_bytes,
    FAMILY_LIMITS,
    RESEARCH_SYMBOLS,
    TOTAL_CANDIDATE_BUDGET,
    GridCandidate,
    build_generation2_grid,
    canonical_grid_manifest,
    grid_manifest_sha256,
)


def test_grid_has_162_candidates_with_frozen_family_counts() -> None:
    grid = build_generation2_grid()
    assert len(grid) == TOTAL_CANDIDATE_BUDGET == 162
    counts = {}
    for candidate in grid:
        counts[candidate.family] = counts.get(candidate.family, 0) + 1
    assert counts == FAMILY_LIMITS


def test_candidate_ids_are_unique_and_deterministic() -> None:
    grid = build_generation2_grid()
    ids = [c.candidate_id for c in grid]
    assert len(ids) == len(set(ids))
    again = build_generation2_grid()
    assert [c.candidate_id for c in again] == ids


def test_every_candidate_is_frozen() -> None:
    for candidate in build_generation2_grid():
        assert isinstance(candidate, GridCandidate)
        try:
            candidate.family = "X"  # type: ignore[misc]
        except Exception:
            pass
        else:  # pragma: no cover - dataclasses(frozen=True) must raise
            raise AssertionError("GridCandidate is not frozen")


def test_g2a_axis_coverage() -> None:
    a = [c for c in build_generation2_grid() if c.family == "G2-A"]
    combos = {(c.lookback, c.skip, c.top_k, c.rebalance) for c in a}
    expected = {
        (lb, sk, k, rb)
        for lb in (63, 126, 189, 252)
        for sk in (0, 21)
        for k in (1, 2, 3)
        for rb in (21, 42)
    }
    assert combos == expected and len(combos) == 48


def test_g2b_axis_coverage() -> None:
    b = [c for c in build_generation2_grid() if c.family == "G2-B"]
    combos = {(c.lookback, c.trend_ma, c.skip, c.top_k, c.rebalance) for c in b}
    expected = {
        (lb, tm, 21, k, rb)
        for lb in (63, 126, 252)
        for tm in (126, 200, 252)
        for k in (1, 2, 3)
        for rb in (21, 42)
    }
    assert combos == expected and len(combos) == 54
    assert all(c.skip == 21 for c in b)
    assert all(c.lookback != 189 for c in b)


def test_g2c_axis_coverage() -> None:
    c = [cand for cand in build_generation2_grid() if cand.family == "G2-C"]
    combos = {(x.lookback, x.vol_lookback, x.top_k, x.rebalance) for x in c}
    expected = {
        (lb, vl, k, rb)
        for lb in (63, 126, 252)
        for vl in (20, 63)
        for k in (2, 3)
        for rb in (21, 42)
    }
    assert combos == expected and len(combos) == 24
    assert all(x.top_k in (2, 3) for x in c)
    assert all(x.skip == 21 for x in c)


def test_g2d_axis_coverage() -> None:
    d = [c for c in build_generation2_grid() if c.family == "G2-D"]
    combos = {(c.horizon_set, c.skip, c.top_k, c.rebalance) for c in d}
    expected = {
        (hs, sk, k, rb)
        for hs in ((21, 63, 126), (63, 126, 252), (21, 126, 252))
        for sk in (0, 21)
        for k in (1, 2, 3)
        for rb in (21, 42)
    }
    assert combos == expected and len(combos) == 36


def test_max_lookback_per_family() -> None:
    grid = build_generation2_grid()
    by_id = {c.candidate_id: c for c in grid}
    # G2-B with skip=21 fixed; lookback=63, trend=252 -> max(63,21,252)=252
    b = by_id["G2-B|lookback=63|trend_ma=252|top_k=1|rebalance=21"]
    assert b.max_lookback == 252
    b2 = by_id["G2-B|lookback=252|trend_ma=126|top_k=1|rebalance=21"]
    assert b2.max_lookback == 252
    # G2-D max_lookback is the largest horizon (skip does not extend it unless > max horizon)
    d = by_id["G2-D|horizons=21+126+252|skip=21|top_k=1|rebalance=21"]
    assert d.max_lookback == 252
    # G2-C lookback=252, vol=20 -> 252
    c = by_id["G2-C|lookback=252|vol_lookback=20|top_k=2|rebalance=21"]
    assert c.max_lookback == 252


def test_manifest_is_stable_and_self_hash_consistent() -> None:
    manifest = canonical_grid_manifest()
    expected = grid_manifest_sha256()
    assert manifest["manifest_sha256"] == expected
    # Two independent calls must produce byte-identical manifests.
    assert canonical_grid_manifest() == manifest
    assert grid_manifest_sha256() == expected


def test_manifest_records_frozen_economics_and_symbols() -> None:
    manifest = canonical_grid_manifest()
    assert manifest["schema_version"] == "GENERATION2-GRID-MANIFEST-v1"
    assert manifest["status"] == "FROZEN_BEFORE_CAMPAIGN"
    assert manifest["research_symbols"] == list(RESEARCH_SYMBOLS)
    assert manifest["initial_cash"] == 100_000.0
    assert manifest["primary_friction_bps"] == 3
    assert manifest["required_friction_cases_bps"] == [0, 3, 10, 25, 50]
    assert manifest["total_candidates"] == 162
    assert manifest["frozen_rules"]["no_adaptive_grid_expansion"] is True


def test_committed_grid_manifest_is_stable_and_self_consistent() -> None:
    """Drift guard: the committed manifest must match the module exactly.

    This pins the frozen 162-candidate grid: any edit to the grid axes or
    candidate set changes the self-hash and fails this test, forcing a
    deliberate re-materialization before any campaign runs.
    """
    manifest_path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "governance"
        / "generation2-grid-manifest.json"
    )
    assert manifest_path.exists(), "committed grid manifest is missing"
    on_disk = json.loads(manifest_path.read_bytes())
    # Byte-stability: re-deriving the canonical bytes reproduces the file.
    assert canonical_grid_manifest_bytes(on_disk) == manifest_path.read_bytes()
    # Self-excluding content hash is valid.
    payload = {k: v for k, v in on_disk.items() if k != "manifest_sha256"}
    recomputed = hashlib.sha256(canonical_grid_manifest_bytes(payload)).hexdigest()
    assert recomputed == on_disk["manifest_sha256"]
    # The committed candidate set is the module's frozen grid.
    assert [c["candidate_id"] for c in on_disk["candidates"]] == [
        c.candidate_id for c in build_generation2_grid()
    ]
