from __future__ import annotations

import math
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

import investment_tracker.quant.phase4.engine.strategies as strategy_module
from investment_tracker.quant.phase4.engine.authority import load_gate2_authority
from investment_tracker.quant.phase4.engine.market import MarketPanel, ScoredMarketInput
from investment_tracker.quant.phase4.engine.models import (
    FixedStrategyBinding,
    Gate2SealError,
)
from investment_tracker.quant.phase4.engine.strategies import generate_target
from investment_tracker.quant.phase4.preregistration.canonical import (
    candidate_identity,
    canonical_json_bytes,
    parameter_tuple_identity,
    trial_identity,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_SHA256 = "a" * 64


@pytest.fixture(scope="module")
def authority():
    return load_gate2_authority(REPOSITORY_ROOT)


def _binding(authority, semantic_name: str, **parameters) -> FixedStrategyBinding:
    family = next(
        family
        for family in authority.family_definitions
        if family.family_semantic_name == semantic_name
    )
    candidate = next(
        candidate
        for candidate in family.candidates
        if candidate.raw_parameters == parameters
    )
    return FixedStrategyBinding.from_authority(
        authority, candidate.candidate_id, IMPLEMENTATION_SHA256
    )


def _market_input(
    close_values: np.ndarray,
    *,
    scored_count: int,
    open_multiplier: float = 1.0,
) -> ScoredMarketInput:
    close_values = np.asarray(close_values, dtype=np.float64)
    symbols = tuple(chr(ord("A") + index) * 3 for index in range(close_values.shape[1]))
    sessions = pd.date_range(
        "2020-01-01", periods=close_values.shape[0], freq="D", tz="UTC"
    )
    split = close_values.shape[0] - scored_count
    assert split > 0
    close = pd.DataFrame(close_values, index=sessions, columns=symbols)
    open_prices = close * open_multiplier
    warmup = MarketPanel.from_frames(
        open_prices.iloc[:split], close.iloc[:split], role="WARMUP"
    )
    scored = MarketPanel.from_frames(
        open_prices.iloc[split:], close.iloc[split:], role="SCORED"
    )
    return ScoredMarketInput.from_panels(warmup, scored)


def _cross_sectional_closes() -> np.ndarray:
    closes = np.full((86, 3), 100.0, dtype=np.float64)
    closes[63:, :] = (120.0, 120.0, 100.0)
    closes[84, :] = (1.0, 10_000.0, 50.0)
    closes[85, :] = (90_000.0, 2.0, 70_000.0)
    return closes


def _scaled_trailing_return_closes(
    *,
    signal_offset: int,
    amplitudes: tuple[float, ...],
    early_multipliers: tuple[float, ...],
    excluded_multipliers: tuple[float, ...],
) -> np.ndarray:
    rows = signal_offset + 2
    closes = np.full((rows, len(amplitudes)), 100.0, dtype=np.float64)
    closes[1:, :] *= np.asarray(early_multipliers, dtype=np.float64)
    excluded_offset = signal_offset - 20
    closes[excluded_offset:, :] *= np.asarray(excluded_multipliers, dtype=np.float64)
    for offset in range(excluded_offset + 1, signal_offset + 1):
        direction = 1.0 if (offset - excluded_offset) % 2 else -1.0
        closes[offset:, :] *= 1.0 + direction * np.asarray(amplitudes)
    return closes


def test_constructs_each_of_the_exact_180_sealed_candidates_once(authority) -> None:
    bindings = tuple(
        FixedStrategyBinding.from_authority(
            authority, candidate.candidate_id, IMPLEMENTATION_SHA256
        )
        for candidate in authority.grids.candidates
    )

    assert len(bindings) == 180
    assert len({binding.candidate_id for binding in bindings}) == 180
    assert tuple(binding.budget_position for binding in bindings) == tuple(
        range(1, 181)
    )
    assert tuple(binding.candidate_id for binding in bindings) == tuple(
        candidate.candidate_id for candidate in authority.grids.candidates
    )
    assert {binding.family_semantic_name for binding in bindings} == {
        "cross_sectional_absolute_momentum_rotation",
        "diversified_time_series_momentum",
        "trend_filtered_equal_risk_allocation",
        "volatility_managed_relative_momentum",
    }


def test_binding_preserves_every_sealed_identity(authority) -> None:
    candidate = authority.grids.candidates[0]
    family = next(
        family
        for family in authority.family_definitions
        if family.family_id == candidate.family_id
    )

    binding = FixedStrategyBinding.from_authority(
        authority, candidate.candidate_id, IMPLEMENTATION_SHA256
    )

    assert binding.campaign_id == candidate.campaign_id
    assert binding.candidate_id == candidate.candidate_id
    assert binding.trial_id == candidate.trial_id
    assert binding.family_id == candidate.family_id == family.family_id
    assert binding.hypothesis_id == candidate.hypothesis_id == family.hypothesis_id
    assert binding.family_definition_sha256 == family.family_definition_sha256
    assert binding.rule_set_sha256 == family.rule_set_sha256
    assert binding.parameter_tuple_sha256 == candidate.parameter_tuple_sha256
    assert binding.grid_spec_sha256 == family.grid_spec_sha256
    assert binding.implementation_sha256 == IMPLEMENTATION_SHA256
    assert binding.parameters_dict == candidate.raw_parameters


def test_binding_rejects_unknown_candidate_and_implementation_identity(
    authority,
) -> None:
    with pytest.raises(Gate2SealError) as unknown:
        FixedStrategyBinding.from_authority(
            authority, "phase4-" + "0" * 64, IMPLEMENTATION_SHA256
        )
    assert unknown.value.code == "FIXED_STRATEGY_INVARIANT_FAILURE"

    with pytest.raises(Gate2SealError) as invalid_sha:
        FixedStrategyBinding.from_authority(
            authority, authority.grids.candidates[0].candidate_id, "not-a-sha"
        )
    assert invalid_sha.value.code == "FIXED_STRATEGY_INVARIANT_FAILURE"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("candidate_id", "phase4-" + "0" * 64),
        ("trial_id", "0" * 64),
        ("family_id", "phase4-family-" + "0" * 64),
        ("hypothesis_id", "substituted-hypothesis"),
        ("family_definition_sha256", "0" * 64),
        ("rule_set_sha256", "0" * 64),
        ("parameter_tuple_sha256", "0" * 64),
        ("grid_spec_sha256", "0" * 64),
        ("implementation_sha256", "0" * 64),
        ("family_semantic_name", "substituted_family"),
    ],
)
def test_binding_rejects_any_identity_or_family_substitution(
    authority, field: str, replacement: str
) -> None:
    binding = FixedStrategyBinding.from_authority(
        authority, authority.grids.candidates[0].candidate_id, IMPLEMENTATION_SHA256
    )
    payload = binding.model_dump()
    payload[field] = replacement

    with pytest.raises(ValidationError):
        FixedStrategyBinding.model_validate(payload)


def test_binding_rejects_parameter_substitution(authority) -> None:
    binding = FixedStrategyBinding.from_authority(
        authority, authority.grids.candidates[0].candidate_id, IMPLEMENTATION_SHA256
    )
    payload = binding.model_dump()
    parameter = dict(payload["parameters"][0])
    parameter["value"] = "999999"
    payload["parameters"] = (parameter, *payload["parameters"][1:])

    with pytest.raises(ValidationError):
        FixedStrategyBinding.model_validate(payload)


def test_binding_copy_cannot_replace_a_sealed_identity(authority) -> None:
    binding = FixedStrategyBinding.from_authority(
        authority, authority.grids.candidates[0].candidate_id, IMPLEMENTATION_SHA256
    )

    with pytest.raises(TypeError):
        binding.model_copy(update={"candidate_id": "phase4-" + "0" * 64})
    with pytest.raises(TypeError):
        binding.copy(update={"candidate_id": "phase4-" + "0" * 64})


def test_cross_sectional_momentum_uses_strict_positive_skip_and_tie_breaking(
    authority,
) -> None:
    binding = _binding(
        authority,
        "cross_sectional_absolute_momentum_rotation",
        lookback_sessions=63,
        rebalance_sessions=21,
        skip_sessions=21,
        top_k=2,
    )
    market_input = _market_input(_cross_sectional_closes(), scored_count=2)

    target = generate_target(authority, binding, market_input, 0)

    assert target is not None
    assert target.weights == (("AAA", 0.5), ("BBB", 0.5))
    assert target.signal_timestamp == market_input.scored.sessions[0]
    assert target.due_session == market_input.scored.sessions[1]
    assert target.binding == binding


def test_cross_sectional_momentum_has_no_future_close_lookahead(authority) -> None:
    binding = _binding(
        authority,
        "cross_sectional_absolute_momentum_rotation",
        lookback_sessions=63,
        rebalance_sessions=21,
        skip_sessions=21,
        top_k=2,
    )
    original = _cross_sectional_closes()
    changed_future = original.copy()
    changed_future[85] = (3.0, 80_000.0, 90_000.0)

    original_target = generate_target(
        authority, binding, _market_input(original, scored_count=2), 0
    )
    changed_target = generate_target(
        authority, binding, _market_input(changed_future, scored_count=2), 0
    )

    assert original_target is not None and changed_target is not None
    assert changed_target.weights == original_target.weights


def test_strategy_targets_are_independent_of_execution_open_prices(authority) -> None:
    binding = _binding(
        authority,
        "cross_sectional_absolute_momentum_rotation",
        lookback_sessions=63,
        rebalance_sessions=21,
        skip_sessions=21,
        top_k=2,
    )
    closes = _cross_sectional_closes()

    ordinary = generate_target(
        authority, binding, _market_input(closes, scored_count=2, open_multiplier=1.0), 0
    )
    substituted_opens = generate_target(
        authority, binding, _market_input(closes, scored_count=2, open_multiplier=17.0), 0
    )

    assert ordinary is not None and substituted_opens is not None
    assert substituted_opens.weights == ordinary.weights


def test_time_series_momentum_uses_exact_ddof1_trailing_return_window(
    authority,
) -> None:
    binding = _binding(
        authority,
        "diversified_time_series_momentum",
        lookback_sessions=63,
        maximum_asset_weight=0.5,
        rebalance_sessions=5,
        volatility_window=20,
    )
    closes = _scaled_trailing_return_closes(
        signal_offset=63,
        amplitudes=(0.005, 0.01, 0.02, 0.0),
        early_multipliers=(2.0, 2.0, 2.0, 0.5),
        excluded_multipliers=(1.5, 1.1, 1.01, 1.0),
    )

    target = generate_target(authority, binding, _market_input(closes, scored_count=2), 0)

    assert target is not None
    assert tuple(symbol for symbol, _ in target.weights) == ("AAA", "BBB", "CCC")
    assert tuple(weight for _, weight in target.weights) == pytest.approx(
        (0.5, 1.0 / 3.0, 1.0 / 6.0)
    )


def test_trend_filter_includes_t_and_uses_exact_ddof1_volatility_window(
    authority,
) -> None:
    binding = _binding(
        authority,
        "trend_filtered_equal_risk_allocation",
        maximum_asset_weight=0.5,
        rebalance_sessions=5,
        trend_window=100,
        volatility_window=20,
    )
    closes = np.full((102, 4), 100.0, dtype=np.float64)
    closes[0, 0] = 10_000.0
    closes[80:, :3] *= 2.0
    for offset in range(81, 101):
        direction = 1.0 if offset % 2 else -1.0
        closes[offset:, :3] *= 1.0 + direction * np.asarray((0.005, 0.01, 0.02))

    target = generate_target(authority, binding, _market_input(closes, scored_count=2), 0)

    assert target is not None
    assert tuple(symbol for symbol, _ in target.weights) == ("AAA", "BBB", "CCC")
    assert tuple(weight for _, weight in target.weights) == pytest.approx(
        (0.5, 1.0 / 3.0, 1.0 / 6.0)
    )


def test_volatility_managed_momentum_uses_tie_break_and_covariance_ending_at_t(
    authority,
) -> None:
    binding = _binding(
        authority,
        "volatility_managed_relative_momentum",
        lookback_sessions=63,
        target_portfolio_volatility=0.08,
        top_k=2,
        volatility_window=20,
    )
    amplitude = 0.16 / math.sqrt(252.0 * 20.0 / 19.0)
    closes = _scaled_trailing_return_closes(
        signal_offset=63,
        amplitudes=(amplitude, amplitude, amplitude / 2.0),
        early_multipliers=(2.0, 2.0, 1.5),
        excluded_multipliers=(1.4, 1.4, 1.01),
    )

    target = generate_target(authority, binding, _market_input(closes, scored_count=2), 0)

    assert target is not None
    assert tuple(symbol for symbol, _ in target.weights) == ("AAA", "BBB")
    assert tuple(weight for _, weight in target.weights) == pytest.approx((0.25, 0.25))


@pytest.mark.parametrize(
    ("semantic_name", "parameters"),
    [
        (
            "cross_sectional_absolute_momentum_rotation",
            dict(
                lookback_sessions=63,
                rebalance_sessions=21,
                skip_sessions=21,
                top_k=2,
            ),
        ),
        (
            "diversified_time_series_momentum",
            dict(
                lookback_sessions=63,
                maximum_asset_weight=0.5,
                rebalance_sessions=5,
                volatility_window=20,
            ),
        ),
        (
            "trend_filtered_equal_risk_allocation",
            dict(
                maximum_asset_weight=0.5,
                rebalance_sessions=5,
                trend_window=100,
                volatility_window=20,
            ),
        ),
        (
            "volatility_managed_relative_momentum",
            dict(
                lookback_sessions=63,
                target_portfolio_volatility=0.08,
                top_k=2,
                volatility_window=20,
            ),
        ),
    ],
)
def test_insufficient_history_produces_an_on_clock_cash_target(
    authority, semantic_name: str, parameters: dict[str, int | float]
) -> None:
    binding = _binding(authority, semantic_name, **parameters)
    market_input = _market_input(np.full((3, 3), 100.0), scored_count=2)

    target = generate_target(authority, binding, market_input, 0)

    assert target is not None
    assert target.weights == ()
    assert target.due_session == market_input.scored.sessions[1]


@pytest.mark.parametrize(
    ("semantic_name", "parameters", "interval", "history_rows"),
    [
        (
            "cross_sectional_absolute_momentum_rotation",
            dict(
                lookback_sessions=63,
                rebalance_sessions=21,
                skip_sessions=0,
                top_k=1,
            ),
            21,
            100,
        ),
        (
            "diversified_time_series_momentum",
            dict(
                lookback_sessions=63,
                maximum_asset_weight=0.5,
                rebalance_sessions=5,
                volatility_window=20,
            ),
            5,
            100,
        ),
        (
            "trend_filtered_equal_risk_allocation",
            dict(
                maximum_asset_weight=0.5,
                rebalance_sessions=5,
                trend_window=100,
                volatility_window=20,
            ),
            5,
            120,
        ),
        (
            "volatility_managed_relative_momentum",
            dict(
                lookback_sessions=63,
                target_portfolio_volatility=0.08,
                top_k=1,
                volatility_window=20,
            ),
            21,
            100,
        ),
    ],
)
def test_rebalance_clocks_are_anchored_to_the_first_scored_session(
    authority,
    semantic_name: str,
    parameters: dict[str, int | float],
    interval: int,
    history_rows: int,
) -> None:
    binding = _binding(authority, semantic_name, **parameters)
    scored_count = interval + 2
    market_input = _market_input(
        np.full((history_rows + scored_count, 3), 100.0),
        scored_count=scored_count,
    )

    assert generate_target(authority, binding, market_input, 0) is not None
    assert generate_target(authority, binding, market_input, 1) is None
    assert generate_target(authority, binding, market_input, interval - 1) is None
    assert generate_target(authority, binding, market_input, interval) is not None


def test_final_session_target_has_no_due_session(authority) -> None:
    binding = _binding(
        authority,
        "cross_sectional_absolute_momentum_rotation",
        lookback_sessions=63,
        rebalance_sessions=21,
        skip_sessions=21,
        top_k=2,
    )
    market_input = _market_input(_cross_sectional_closes()[:85], scored_count=1)

    target = generate_target(authority, binding, market_input, 0)

    assert target is not None
    assert target.due_session is None


@pytest.mark.parametrize("scored_offset", [-1, 2, 1.5, True])
def test_generate_target_rejects_invalid_scored_offsets(
    authority, scored_offset: object
) -> None:
    binding = _binding(
        authority,
        "cross_sectional_absolute_momentum_rotation",
        lookback_sessions=63,
        rebalance_sessions=21,
        skip_sessions=21,
        top_k=2,
    )
    market_input = _market_input(_cross_sectional_closes(), scored_count=2)

    with pytest.raises(Gate2SealError) as caught:
        generate_target(authority, binding, market_input, scored_offset)
    assert caught.value.code == "FIXED_STRATEGY_INVARIANT_FAILURE"


def test_strategy_layer_exposes_no_adaptive_or_selection_surface(authority) -> None:
    binding = FixedStrategyBinding.from_authority(
        authority, authority.grids.candidates[0].candidate_id, IMPLEMENTATION_SHA256
    )

    for forbidden_name in ("fit", "calibrate", "optimize", "select"):
        assert not hasattr(binding, forbidden_name)
        assert not hasattr(strategy_module, forbidden_name)


# ============================================================
# Forged binding rejection regression test
# ============================================================


def _forge_binding() -> FixedStrategyBinding:
    """Construct a FixedStrategyBinding with self-consistent hashes but a
    family_id that is NOT one of the four sealed family IDs."""
    forged_family_id = "phase4-family-" + sha256(b"forged-family-payload").hexdigest()
    forged_hypothesis_id = "phase4-hypothesis-" + sha256(
        b"forged-hypothesis"
    ).hexdigest()

    parameters = {
        "lookback_sessions": 63,
        "maximum_asset_weight": 0.25,
        "rebalance_sessions": 5,
        "volatility_window": 20,
    }
    typed_parameters = {
        name: {
            "type": "int" if isinstance(val, int) else "float64_hex",
            "value": str(val) if isinstance(val, int) else float(val).hex(),
        }
        for name, val in parameters.items()
    }

    campaign_id = "PHASE4-FIXED-LONG-ONLY-2014-2022-v1"
    candidate_id = candidate_identity(
        campaign_id=campaign_id,
        hypothesis_id=forged_hypothesis_id,
        family_id=forged_family_id,
        parameters=typed_parameters,
    )
    trial_id = trial_identity(campaign_id, candidate_id)
    parameter_tuple_sha256 = parameter_tuple_identity(
        forged_family_id, typed_parameters
    )

    payload = {
        "schema_version": "PHASE4-FIXED-STRATEGY-BINDING-v1",
        "implementation_interface": "PHASE4-FIXED-LONG-ONLY-STRATEGY-v1",
        "campaign_id": campaign_id,
        "candidate_id": candidate_id,
        "trial_id": trial_id,
        "budget_position": 1,
        "family_id": forged_family_id,
        "family_semantic_name": "diversified_time_series_momentum",
        "hypothesis_id": forged_hypothesis_id,
        "family_definition_sha256": "b" * 64,
        "rule_set_sha256": "c" * 64,
        "parameter_tuple_sha256": parameter_tuple_sha256,
        "grid_spec_sha256": "d" * 64,
        "implementation_sha256": IMPLEMENTATION_SHA256,
        "parameters": [
            {"name": "lookback_sessions", "type": "int", "value": "63"},
            {
                "name": "maximum_asset_weight",
                "type": "float64_hex",
                "value": float(0.25).hex(),
            },
            {"name": "rebalance_sessions", "type": "int", "value": "5"},
            {"name": "volatility_window", "type": "int", "value": "20"},
        ],
        "structural_parameters": [],
    }
    payload["binding_sha256"] = sha256(
        canonical_json_bytes(
            {k: v for k, v in payload.items() if k != "binding_sha256"}
        )
    ).hexdigest()

    return FixedStrategyBinding.model_validate(payload)


class TestForgedBindingRejection:
    """Regression test: a forged binding must be rejected by generate_target."""

    def test_forged_binding_passes_model_validation(self) -> None:
        """A binding with a fabricated family_id but valid parameter values
        and correctly computed hashes passes model_validate without error."""
        binding = _forge_binding()
        assert binding.family_semantic_name == "diversified_time_series_momentum"
        assert binding.candidate_id.startswith("phase4-")
        assert binding.family_id == "phase4-family-" + sha256(
            b"forged-family-payload"
        ).hexdigest()

    def test_forged_binding_rejected_by_generate_target(self, authority) -> None:
        """A forged binding with self-consistent hashes but a family_id outside
        the sealed population MUST be rejected by generate_target with
        FIXED_STRATEGY_INVARIANT_FAILURE."""
        forged = _forge_binding()
        scored_count = 5
        warmup_count = 100
        total = warmup_count + scored_count
        symbols = ("AAA", "BBB", "CCC")
        sessions = pd.date_range("2020-01-01", periods=total, freq="D", tz="UTC")
        closes = pd.DataFrame(
            np.full((total, 3), 100.0, dtype=np.float64),
            index=sessions,
            columns=symbols,
        )
        closes.iloc[:, 0] = np.linspace(100.0, 120.0, total)
        closes.iloc[:, 1] = np.linspace(100.0, 110.0, total)
        closes.iloc[:, 2] = np.linspace(100.0, 105.0, total)
        opens = closes.copy()
        warmup = MarketPanel.from_frames(
            opens.iloc[:warmup_count], closes.iloc[:warmup_count], role="WARMUP"
        )
        scored = MarketPanel.from_frames(
            opens.iloc[warmup_count:], closes.iloc[warmup_count:], role="SCORED"
        )
        market_input = ScoredMarketInput.from_panels(warmup, scored)

        with pytest.raises(Gate2SealError) as exc_info:
            generate_target(authority, forged, market_input, 0)
        assert exc_info.value.code == "FIXED_STRATEGY_INVARIANT_FAILURE"
        assert "not a member of the sealed" in str(exc_info.value)
