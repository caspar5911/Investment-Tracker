from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Final, Literal, Sequence

import numpy as np
import pandas as pd
from pydantic import ConfigDict, Field

from ..preregistration.canonical import canonical_sha256
from .benchmarks import equal_weight_buy_and_hold
from .budget import BudgetState
from .durability import calculate_durability, expected_session_identity
from .execution import replay_targets
from .market import MarketPanel, ScoredMarketInput
from .metrics import calculate_metrics
from .models import (
    ExpectedSessionAuthority,
    FixedStrategyBinding,
    FrozenGate2Model,
    Gate2Authority,
    Gate2SealError,
    PortfolioReplay,
    SafetyAccessState,
    UnavailableStatistics,
)
from .robustness import (
    bootstrap_median_daily_return,
    partition_regimes,
    run_friction_cases,
    slice_continuous_folds,
)
from .source_identity import GATE2_SOURCE_BUNDLES, SourceBundleIdentity
from .strategies import generate_target


_CONFORMANCE_SYMBOLS: Final = (
    "SYN-ALPHA",
    "SYN-BETA",
    "SYN-DELTA",
    "SYN-EPSTEIN",
    "SYN-GAMMA",
    "SYN-ZETA",
)
_WARMUP_SESSIONS: Final = 300
_SCORED_SESSIONS: Final = 400
_START_DATE: Final = "2035-01-01"
_BASE_PRICE: Final = 100.0
_WAVE_AMPLITUDE: Final = 0.25
_DAILY_DRIFT: Final = 0.0005
_PRIMARY_FRICTION_BPS: Final = 3
_FORBIDDEN_IMPORT_FRAGMENTS: Final = (
    ".backtest",
    ".data",
    ".experiments",
    ".moomoo",
    ".optimizer",
    ".promotion",
    ".reports",
    ".strategies",
    ".universe",
    ".validation",
    ".workflow",
)
_FORBIDDEN_IDENTIFIERS: Final = frozenset(
    {
        "OpenQuoteContext",
        "OpenSecTradeContext",
        "OpenFutureTradeContext",
        "OpenCryptoTradeContext",
        "place_order",
        "modify_order",
        "cancel_order",
        "unlock_trade",
        "rank_candidates",
        "select_survivor",
        "export_results",
        "promote_candidate",
        "write_tracker",
        "brokerage_account",
    }
)


class ConformanceInvariant(FrozenGate2Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[A-Z0-9_]+$")
    status: Literal["PASS"] = "PASS"


class SyntheticConformanceRecord(FrozenGate2Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "PHASE4-SYNTHETIC-CONFORMANCE-v1"
    label: str = "SYNTHETIC_CONFORMANCE_ONLY"
    phase4_trials_consumed: int = 0
    candidate_count: int = Field(ge=1)
    family_count: int = Field(ge=1)
    fixture_symbols: tuple[str, ...] = Field(min_length=1)
    fixture_configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    warmup_panel_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    post_warmup_panel_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fold_authority_status: str = "FOLD_AUTHORITY_MISSING"
    regime_authority_status: str = "REGIME_AUTHORITY_MISSING"
    execution_convention: str = "COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN"
    execution_series: str = "QFQ_NORMALIZED"
    decision_grade: bool = False
    invariants: tuple[ConformanceInvariant, ...] = Field(min_length=1)
    source_bundle_sha256s: tuple[tuple[str, str], ...] = Field(min_length=1)
    safety: SafetyAccessState
    unavailable_statistics: UnavailableStatistics

    @property
    def scored_panel_sha256(self) -> str:
        return self.post_warmup_panel_sha256


def _fixture_configuration() -> dict[str, object]:
    return {
        "schema_version": "PHASE4-SYNTHETIC-CONFORMANCE-v1",
        "symbols": list(_CONFORMANCE_SYMBOLS),
        "warmup_sessions": _WARMUP_SESSIONS,
        "scored_sessions": _SCORED_SESSIONS,
        "start_date": _START_DATE,
        "base_price": _BASE_PRICE,
        "wave_amplitude": _WAVE_AMPLITUDE,
        "daily_drift": _DAILY_DRIFT,
    }


def _build_synthetic_market_input() -> ScoredMarketInput:
    sessions = pd.date_range(
        _START_DATE,
        periods=_WARMUP_SESSIONS + _SCORED_SESSIONS,
        freq="D",
        tz="UTC",
    )
    total = _WARMUP_SESSIONS + _SCORED_SESSIONS
    closes = pd.DataFrame(
        index=sessions,
        columns=list(_CONFORMANCE_SYMBOLS),
        dtype=np.float64,
    )
    for index in range(total):
        for symbol_index, symbol in enumerate(_CONFORMANCE_SYMBOLS):
            wave = float(np.sin(0.03 * index + 0.5 * symbol_index))
            price = (
                _BASE_PRICE
                * (1.0 + 0.05 * symbol_index)
                * (
                    1.0
                    + _WAVE_AMPLITUDE * wave
                    + _DAILY_DRIFT * index
                )
            )
            closes.at[sessions[index], symbol] = price
    opens = closes.shift(1)
    opens.iloc[0] = closes.iloc[0]
    warmup = MarketPanel.from_frames(
        opens.iloc[:_WARMUP_SESSIONS].copy(),
        closes.iloc[:_WARMUP_SESSIONS].copy(),
        role="WARMUP",
    )
    scored = MarketPanel.from_frames(
        opens.iloc[_WARMUP_SESSIONS:].copy(),
        closes.iloc[_WARMUP_SESSIONS:].copy(),
        role="SCORED",
    )
    return ScoredMarketInput.from_panels(warmup, scored)


def _validated_bundle_set(
    bundle_set: dict[str, SourceBundleIdentity],
) -> dict[str, SourceBundleIdentity]:
    if not isinstance(bundle_set, dict):
        raise Gate2SealError(
            "INPUT_BOUNDARY_VIOLATION",
            "INPUT_BOUNDARY_VIOLATION: bundle set must be a mapping",
        )
    expected_names = set(GATE2_SOURCE_BUNDLES)
    supplied_names = set(bundle_set)
    if supplied_names != expected_names:
        raise Gate2SealError(
            "INPUT_BOUNDARY_VIOLATION",
            "INPUT_BOUNDARY_VIOLATION: bundle set keys do not match the sealed "
            "Gate 2 source bundle population",
        )
    for name, identity in bundle_set.items():
        if not isinstance(identity, SourceBundleIdentity):
            raise Gate2SealError(
                "INPUT_BOUNDARY_VIOLATION",
                "INPUT_BOUNDARY_VIOLATION: every bundle must be a source bundle "
                "identity",
            )
        supplied_paths = set(entry.path for entry in identity.entries)
        expected_paths = set(GATE2_SOURCE_BUNDLES[name])
        if supplied_paths != expected_paths:
            raise Gate2SealError(
                "IMPLEMENTATION_BINDING_MISMATCH",
                "IMPLEMENTATION_BINDING_MISMATCH: bundle "
                f"{name} does not bind its sealed path set",
            )
    return bundle_set


# Memoization over fully immutable, digested inputs: the authority head
# revision plus the sealed binding identity pin the binding bytes, and the
# panel digests pin the market data, so cached results are bit-identical to
# recomputation. This keeps repeated conformance runs cheap without relaxing
# any invariant; the first run performs every check.
_BINDING_CACHE: dict[tuple[str, str], FixedStrategyBinding] = {}
_TARGET_CACHE: dict[tuple[str, str, str, str, int], "object"] = {}


def _candidate_implementation_sha256(
    authority: Gate2Authority,
    candidate_id: str,
    family_implementation_sha256: dict[str, str],
) -> str:
    """The candidate's implementation identity is its family source bundle.

    A candidate binds to the exact committed family source bundle that defines
    its implementation; the candidate id alone is not an implementation
    identity.
    """
    candidate = next(
        (
            item
            for item in authority.grids.candidates
            if item.candidate_id == candidate_id
        ),
        None,
    )
    if candidate is None:
        raise Gate2SealError(
            "FIXED_STRATEGY_INVARIANT_FAILURE",
            "candidate is not a member of the sealed Gate 1 population",
        )
    implementation = family_implementation_sha256.get(candidate.family_id)
    if implementation is None:
        raise Gate2SealError(
            "IMPLEMENTATION_BINDING_MISMATCH",
            "candidate family has no bound source-bundle implementation "
            "identity",
        )
    return implementation


def _cached_binding(
    authority: Gate2Authority,
    candidate_id: str,
    family_implementation_sha256: dict[str, str],
) -> FixedStrategyBinding:
    key = (authority.head_revision, candidate_id)
    cached = _BINDING_CACHE.get(key)
    if cached is None:
        cached = FixedStrategyBinding.from_authority(
            authority,
            candidate_id,
            _candidate_implementation_sha256(
                authority, candidate_id, family_implementation_sha256
            ),
        )
        _BINDING_CACHE[key] = cached
    return cached


def _cached_target(
    authority: Gate2Authority,
    binding: FixedStrategyBinding,
    market_input: ScoredMarketInput,
    offset: int,
) -> "object":
    key = (
        authority.head_revision,
        market_input.warmup_panel_sha256,
        market_input.scored_panel_sha256,
        binding.binding_sha256,
        offset,
    )
    cached = _TARGET_CACHE.get(key)
    if cached is None and key not in _TARGET_CACHE:
        cached = generate_target(authority, binding, market_input, offset)
        _TARGET_CACHE[key] = cached
    return cached


def _assert_all_bindings_construct(
    authority: Gate2Authority,
    family_implementation_sha256: dict[str, str],
) -> dict[str, FixedStrategyBinding]:
    bindings = {
        candidate.candidate_id: _cached_binding(
            authority,
            candidate.candidate_id,
            family_implementation_sha256,
        )
        for candidate in authority.grids.candidates
    }
    if len(bindings) != 180:
        raise Gate2SealError(
            "FIXED_STRATEGY_INVARIANT_FAILURE",
            "FIXED_STRATEGY_INVARIANT_FAILURE: sealed population must bind "
            "exactly 180 candidates",
        )
    return bindings


def _check_on_clock_target(
    target: object,
    binding: FixedStrategyBinding,
    scored: MarketPanel,
    offset: int,
    symbol_set: set[str],
) -> None:
    if target is None:
        raise Gate2SealError(
            "FIXED_STRATEGY_INVARIANT_FAILURE",
            "FIXED_STRATEGY_INVARIANT_FAILURE: rebalance clock "
            "skipped a due target",
        )
    if target.signal_timestamp != scored.sessions[offset]:
        raise Gate2SealError(
            "FIXED_STRATEGY_INVARIANT_FAILURE",
            "FIXED_STRATEGY_INVARIANT_FAILURE: target signal does "
            "not sit on the completed bar",
        )
    expected_due = (
        scored.sessions[offset + 1]
        if offset + 1 < len(scored.sessions)
        else None
    )
    if target.due_session != expected_due:
        raise Gate2SealError(
            "FIXED_STRATEGY_INVARIANT_FAILURE",
            "FIXED_STRATEGY_INVARIANT_FAILURE: target due session "
            "is not the next bar open",
        )
    for symbol, weight in target.weights:
        if symbol not in symbol_set:
            raise Gate2SealError(
                "LONG_ONLY_INVARIANT_FAILURE",
                "LONG_ONLY_INVARIANT_FAILURE: target references a "
                "symbol absent from the panel",
            )
        if not np.isfinite(float(weight)):
            raise Gate2SealError(
                "FIXED_STRATEGY_INVARIANT_FAILURE",
                "FIXED_STRATEGY_INVARIANT_FAILURE: target weight is "
                "not finite",
            )
    if (
        target.binding.candidate_id != binding.candidate_id
        or target.binding.binding_sha256 != binding.binding_sha256
    ):
        raise Gate2SealError(
            "FIXED_STRATEGY_INVARIANT_FAILURE",
            "FIXED_STRATEGY_INVARIANT_FAILURE: target carries a "
            "different binding identity",
        )


def _off_clock_sample_offsets(total: int, rebalance_sessions: int) -> tuple[int, ...]:
    candidates = (rebalance_sessions - 1, rebalance_sessions + 1, total - 1)
    return tuple(
        offset
        for offset in dict.fromkeys(candidates)
        if 0 <= offset < total and offset % rebalance_sessions != 0
    )


def _on_clock_sample_offsets(total: int, rebalance_sessions: int) -> tuple[int, ...]:
    mid = (total // 2) // rebalance_sessions * rebalance_sessions
    largest = (total - 1) // rebalance_sessions * rebalance_sessions
    return tuple(dict.fromkeys((0, mid, largest)))


def _representative_candidate(candidates: Sequence[Any], family: Any) -> Any:
    for candidate in candidates:
        if candidate.family_id == family.family_id:
            return candidate
    raise Gate2SealError(
        "FIXED_STRATEGY_INVARIANT_FAILURE",
        "FIXED_STRATEGY_INVARIANT_FAILURE: sealed family has no candidates for "
        "rebalance-clock verification",
    )


def _assert_rebalance_clock(
    authority: Gate2Authority,
    market_input: ScoredMarketInput,
    bindings: dict[str, FixedStrategyBinding],
) -> tuple[dict[str, FixedStrategyBinding], tuple]:
    """Verify each family's sealed rebalance clock; return one full sequence.

    The first family produces the complete 400-entry target sequence used for
    the replay invariant: every on-clock offset is generated and fully
    checked, and the off-clock ``None`` rule (pure arithmetic
    ``offset % rebalance_sessions != 0`` inside :func:`generate_target`) is
    verified on a deterministic sample of off-clock offsets, with the
    remaining off-clock entries recorded as ``None``. The remaining families
    are spot-checked on deterministic on- and off-clock samples.
    """
    scored = market_input.scored
    total = len(scored.sessions)
    families = authority.grids.families
    by_family: dict[str, FixedStrategyBinding] = {}
    for family in families:
        member = _representative_candidate(authority.grids.candidates, family)
        by_family[family.family_id] = bindings[member.candidate_id]
    symbol_set = set(scored.symbols)
    sequence: list[object] | None = None
    for index, family in enumerate(families):
        binding = by_family[family.family_id]
        structural = binding.structural_parameters_dict
        parameters = binding.parameters_dict
        rebalance_sessions = int(
            structural.get(
                "rebalance_sessions", parameters.get("rebalance_sessions", 0)
            )
        )
        if rebalance_sessions <= 0:
            raise Gate2SealError(
                "FIXED_STRATEGY_INVARIANT_FAILURE",
                "FIXED_STRATEGY_INVARIANT_FAILURE: sealed rebalance interval is "
                "unavailable",
            )
        off_clock_samples = set(
            _off_clock_sample_offsets(total, rebalance_sessions)
        )
        if index == 0:
            targets: list[object] = []
            for offset in range(total):
                if offset % rebalance_sessions == 0:
                    target = _cached_target(
                        authority, binding, market_input, offset
                    )
                    _check_on_clock_target(
                        target, binding, scored, offset, symbol_set
                    )
                else:
                    if offset in off_clock_samples:
                        sample = _cached_target(
                            authority, binding, market_input, offset
                        )
                        if sample is not None:
                            raise Gate2SealError(
                                "FIXED_STRATEGY_INVARIANT_FAILURE",
                                "FIXED_STRATEGY_INVARIANT_FAILURE: target "
                                "generated off the sealed rebalance clock",
                            )
                    target = None
                targets.append(target)
            sequence = targets
        else:
            for offset in _on_clock_sample_offsets(total, rebalance_sessions):
                target = _cached_target(
                    authority, binding, market_input, offset
                )
                _check_on_clock_target(target, binding, scored, offset, symbol_set)
            for offset in sorted(off_clock_samples):
                sample = _cached_target(
                    authority, binding, market_input, offset
                )
                if sample is not None:
                    raise Gate2SealError(
                        "FIXED_STRATEGY_INVARIANT_FAILURE",
                        "FIXED_STRATEGY_INVARIANT_FAILURE: target generated "
                        "off the sealed rebalance clock",
                    )
    if sequence is None:
        raise Gate2SealError(
            "FIXED_STRATEGY_INVARIANT_FAILURE",
            "FIXED_STRATEGY_INVARIANT_FAILURE: no family produced targets",
        )
    return by_family, tuple(sequence)


def _assert_budget_machine(authority: Gate2Authority) -> None:
    fresh = BudgetState.from_authority(authority)
    if (
        fresh.phase4_new_trials_consumed != 0
        or fresh.phase4_new_trials_remaining != 3000
        or fresh.next_consumption_ordinal != 1
        or fresh.traversal_cursor != 0
        or fresh.campaign_status != "ACTIVE"
    ):
        raise Gate2SealError(
            "BUDGET_ACCOUNTING_INVALID",
            "BUDGET_ACCOUNTING_INVALID: budget state did not start at the "
            "sealed origin",
        )
    try:
        fresh.record_candidate_outcome(1.0)
    except Gate2SealError as exc:
        if exc.code != "BUDGET_ACCOUNTING_INVALID":
            raise
    else:
        raise Gate2SealError(
            "BUDGET_ACCOUNTING_INVALID",
            "BUDGET_ACCOUNTING_INVALID: outcome was recorded before the "
            "current trial was consumed",
        )
    consumed = fresh.consume_current(fresh.trial_ids[0])
    if (
        consumed.phase4_new_trials_consumed != 1
        or consumed.traversal_cursor != 0
        or consumed.consumption_ordinals[0] != 1
        or consumed.row_states[0] != "CONSUMED"
        or consumed.phase4_new_trials_consumed
        + consumed.phase4_new_trials_remaining
        != 3000
    ):
        raise Gate2SealError(
            "BUDGET_ACCOUNTING_INVALID",
            "BUDGET_ACCOUNTING_INVALID: budget counters did not advance "
            "exactly once",
        )
    advanced = consumed.record_candidate_outcome(0.01)
    if advanced.traversal_cursor != 1 or advanced.oos_streak != 0:
        raise Gate2SealError(
            "BUDGET_ACCOUNTING_INVALID",
            "BUDGET_ACCOUNTING_INVALID: traversal cursor did not advance on "
            "the recorded outcome",
        )


def _assert_unbound_fold_and_regime(replay: object) -> None:
    if not isinstance(replay, PortfolioReplay):
        raise Gate2SealError(
            "ACCOUNTING_INVARIANT_FAILURE",
            "ACCOUNTING_INVARIANT_FAILURE: conformance replay is malformed",
        )
    try:
        slice_continuous_folds(replay, None)
    except Gate2SealError as exc:
        if exc.code != "FOLD_AUTHORITY_MISSING":
            raise
    else:
        raise Gate2SealError(
            "FOLD_AUTHORITY_MISSING",
            "FOLD_AUTHORITY_MISSING: fold slicing must refuse without an "
            "exact fold authority",
        )
    try:
        partition_regimes(replay, None)
    except Gate2SealError as exc:
        if exc.code != "REGIME_AUTHORITY_MISSING":
            raise
    else:
        raise Gate2SealError(
            "REGIME_AUTHORITY_MISSING",
            "REGIME_AUTHORITY_MISSING: regime partitioning must refuse without "
            "an exact regime authority",
        )


def _assert_baselines_comparison_only(authority: Gate2Authority) -> None:
    baselines = authority.baselines
    items = baselines.baselines
    if len(items) != 4:
        raise Gate2SealError(
            "IMMUTABLE_ARTIFACT_COLLISION",
            "IMMUTABLE_ARTIFACT_COLLISION: the sealed baseline set must hold "
            "exactly four baselines",
        )
    baseline_ids = tuple(item.baseline_id for item in items)
    if baseline_ids != tuple(sorted(baseline_ids)) or len(set(baseline_ids)) != 4:
        raise Gate2SealError(
            "IMMUTABLE_ARTIFACT_COLLISION",
            "IMMUTABLE_ARTIFACT_COLLISION: baselines must be unique and "
            "baseline-id sorted",
        )
    families = tuple(item.family for item in items)
    if len(set(families)) != 4:
        raise Gate2SealError(
            "IMMUTABLE_ARTIFACT_COLLISION",
            "IMMUTABLE_ARTIFACT_COLLISION: baselines must span four distinct "
            "families",
        )
    expected_counts = {
        "EXECUTED_PHASE2_BASELINE": 2,
        "SOURCE_DEFINED_PHASE2_GRID_BASELINE": 2,
    }
    counts: dict[str, int] = {}
    for item in items:
        counts[item.provenance_class] = counts.get(item.provenance_class, 0) + 1
    if counts != expected_counts:
        raise Gate2SealError(
            "IMMUTABLE_ARTIFACT_COLLISION",
            "IMMUTABLE_ARTIFACT_COLLISION: baseline provenance classes must be "
            "exactly 2 executed and 2 source-defined",
        )


def _assert_static_scan_clean() -> None:
    package_root = Path(__file__).resolve().parent
    for path in sorted(package_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: list[str] = []
        identifiers: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Name):
                identifiers.add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                identifiers.add(node.name)
        hit_fragment = next(
            (
                fragment
                for fragment in _FORBIDDEN_IMPORT_FRAGMENTS
                for imported in imports
                if fragment in imported
            ),
            None,
        )
        if hit_fragment is not None:
            raise Gate2SealError(
                "FORBIDDEN_CAPABILITY_PRESENT",
                f"FORBIDDEN_CAPABILITY_PRESENT: {path.name} imports a "
                f"forbidden module fragment {hit_fragment}",
            )
        hit_identifier = identifiers & _FORBIDDEN_IDENTIFIERS
        if hit_identifier:
            raise Gate2SealError(
                "FORBIDDEN_CAPABILITY_PRESENT",
                "FORBIDDEN_CAPABILITY_PRESENT: "
                f"{path.name} references forbidden identifiers "
                f"{sorted(hit_identifier)}",
            )


def run_synthetic_conformance(
    authority: Gate2Authority,
    bundle_set: dict[str, SourceBundleIdentity],
) -> SyntheticConformanceRecord:
    """Run the deterministic synthetic-only Gate 2 conformance invariants."""

    if not isinstance(authority, Gate2Authority):
        raise Gate2SealError(
            "INPUT_BOUNDARY_VIOLATION",
            "INPUT_BOUNDARY_VIOLATION: conformance requires the exact Gate 2 "
            "authority",
        )
    validated_bundles = _validated_bundle_set(bundle_set)
    market_input = _build_synthetic_market_input()
    scored = market_input.scored
    sessions = scored.sessions

    family_implementation_sha256 = {
        family.family_id: validated_bundles[
            f"family:{family.family_semantic_name}"
        ].bundle_sha256
        for family in authority.grids.families
    }
    bindings = _assert_all_bindings_construct(
        authority, family_implementation_sha256
    )
    by_family, targets = _assert_rebalance_clock(authority, market_input, bindings)

    replay = replay_targets(scored, targets, friction_bps=_PRIMARY_FRICTION_BPS)
    if len(replay.states) != len(sessions):
        raise Gate2SealError(
            "ACCOUNTING_INVARIANT_FAILURE",
            "ACCOUNTING_INVARIANT_FAILURE: replay states do not align one per "
            "scored session",
        )
    if not all(
        np.isfinite(value) and value > 0.0 for value in replay.close_equity
    ):
        raise Gate2SealError(
            "ACCOUNTING_INVARIANT_FAILURE",
            "ACCOUNTING_INVARIANT_FAILURE: replay equity is not finite and "
            "positive",
        )

    friction = run_friction_cases(scored, targets)
    if tuple(case.friction_bps for case in friction.cases) != (0, 3, 10, 25, 50):
        raise Gate2SealError(
            "DURABILITY_EVIDENCE_INVALID",
            "DURABILITY_EVIDENCE_INVALID: friction cases must cover the sealed "
            "(0, 3, 10, 25, 50) bps ladder",
        )

    benchmark = equal_weight_buy_and_hold(scored, friction_bps=_PRIMARY_FRICTION_BPS)
    calculate_metrics(replay, benchmark)

    expected_sessions = ExpectedSessionAuthority(
        sessions=sessions,
        sha256=expected_session_identity(sessions),
    )
    calculate_durability(replay, expected_sessions)

    bootstrap_median_daily_return(replay.daily_returns)

    _assert_budget_machine(authority)
    _assert_unbound_fold_and_regime(replay)
    _assert_baselines_comparison_only(authority)
    _assert_static_scan_clean()

    invariants = tuple(
        ConformanceInvariant(name=name, status="PASS")
        for name in (
            "ALL_BINDINGS_CONSTRUCT",
            "TARGET_GENERATION_REBALANCE_CLOCK",
            "REPLAY_ACCOUNTING",
            "FRICTION_CASES",
            "METRICS",
            "DURABILITY",
            "BOOTSTRAP",
            "BUDGET_STATE_MACHINE",
            "FOLD_AUTHORITY_UNBOUND",
            "REGIME_AUTHORITY_UNBOUND",
            "BASELINE_COMPARISON_ONLY",
            "STATIC_SCAN",
        )
    )

    return SyntheticConformanceRecord(
        candidate_count=len(bindings),
        family_count=len(by_family),
        fixture_symbols=_CONFORMANCE_SYMBOLS,
        fixture_configuration_sha256=canonical_sha256(_fixture_configuration()),
        warmup_panel_sha256=market_input.warmup_panel_sha256,
        post_warmup_panel_sha256=market_input.scored_panel_sha256,
        invariants=invariants,
        source_bundle_sha256s=tuple(
            (name, validated_bundles[name].bundle_sha256)
            for name in sorted(GATE2_SOURCE_BUNDLES)
        ),
        safety=authority.safety,
        unavailable_statistics=UnavailableStatistics(),
    )


__all__ = (
    "ConformanceInvariant",
    "SyntheticConformanceRecord",
    "run_synthetic_conformance",
)
