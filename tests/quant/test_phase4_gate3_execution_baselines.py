from __future__ import annotations

from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.phase4.engine.authority import load_gate2_authority
from investment_tracker.quant.phase4.engine.market import MarketPanel, ScoredMarketInput
from investment_tracker.quant.phase4.preregistration.canonical import canonical_sha256


ROOT = Path(__file__).resolve().parents[2]
SYMBOLS = ("SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP")
BASELINES = (
    "baseline-trend-v1",
    "baseline-momentum-v1",
    "baseline-trend-momentum-v1",
    "baseline-risk-managed-trend-v1",
)


def _simulate():
    return import_module(
        "investment_tracker.quant.phase4.gate3_execution.baselines"
    ).simulate_baseline


@pytest.fixture(scope="module")
def authority():
    return load_gate2_authority(ROOT)


def _market(*, crash: bool = False, glc_change: float = 0.0) -> ScoredMarketInput:
    warmup_index = pd.date_range("2023-01-01", periods=200, freq="D", tz="UTC")
    scored_index = pd.date_range(warmup_index[-1] + pd.Timedelta(days=1), periods=4, freq="D", tz="UTC")
    warmup_close = pd.DataFrame(
        {symbol: np.linspace(100.0, 120.0, 200) for symbol in sorted(SYMBOLS)},
        index=warmup_index,
    )
    scored_close_values = [130.0, 80.0, 70.0, 70.0] if crash else [130.0, 131.0, 132.0, 133.0]
    scored_open_values = [130.0, 130.0, 80.0, 70.0] if crash else [130.0, 130.0, 131.0, 132.0]
    scored_close = pd.DataFrame(
        {symbol: list(scored_close_values) for symbol in sorted(SYMBOLS)},
        index=scored_index,
    )
    scored_open = pd.DataFrame(
        {symbol: list(scored_open_values) for symbol in sorted(SYMBOLS)},
        index=scored_index,
    )
    scored_close.loc[scored_index[-1], "GLD"] += glc_change
    warmup = MarketPanel.from_frames(warmup_close, warmup_close, role="WARMUP")
    scored = MarketPanel.from_frames(scored_open, scored_close, role="SCORED")
    return ScoredMarketInput.from_panels(warmup, scored)


@pytest.mark.parametrize("baseline_id", BASELINES)
def test_each_baseline_has_eight_self_financing_sleeves(authority, baseline_id):
    result = _simulate()(authority, _market(), baseline_id)
    definition = next(item for item in authority.baselines.baselines if item.baseline_id == baseline_id)
    assert tuple(item.symbol for item in result.sleeves) == SYMBOLS
    assert len(result.sleeves) == 8
    assert all(item.replay.initial_cash == 12500.0 for item in result.sleeves)
    assert all(item.replay.states[0].cash == 12500.0 for item in result.sleeves)
    assert all(item.replay.candidate_id is None for item in result.sleeves)
    assert all(item.replay.binding_sha256 is None for item in result.sleeves)
    assert all(item.replay.friction_bps == 3 for item in result.sleeves)
    assert result.close_equity[0] == 100000.0
    assert result.close_equity == tuple(
        sum(item.replay.close_equity[i] for item in result.sleeves)
        for i in range(len(result.close_equity))
    )
    assert len(result.daily_returns) == len(result.close_equity) - 1
    assert result.eligible_for_selection is False
    assert result.family == definition.family
    assert result.parameters == tuple(sorted(definition.parameters.items()))
    assert result.phase2_comparator_candidate_id == definition.candidate_id
    assert result.baseline_definition_sha256 == canonical_sha256(definition.model_dump(mode="json"))
    assert result.implementation_bundle_sha256 == definition.implementation_bundle_sha256
    assert result.generator_revision == definition.generator_revision
    assert result.generator_path == definition.generator_path
    assert result.generator_blob == definition.generator_blob
    assert result.generator_content_sha256 == definition.generator_content_sha256
    assert result.parameter_tuple_sha256 == canonical_sha256({
        "family": definition.family, "parameters": definition.parameters,
    })
    assert result.rule_set_sha256 == canonical_sha256({
        "family": definition.family,
        "generator_content_sha256": definition.generator_content_sha256,
        "implementation_bundle_sha256": definition.implementation_bundle_sha256,
    })
    assert result.execution_series == "QFQ_NORMALIZED"
    assert result.decision_grade is False
    assert result.primary_friction_bps == 3
    assert result.aggregate_equity_sha256 == canonical_sha256(result.close_equity)
    assert result.aggregate_returns_sha256 == canonical_sha256(result.daily_returns)
    assert len({item.sleeve_sha256 for item in result.sleeves}) == 8
    for item in result.sleeves:
        assert item.replay_sha256 == canonical_sha256(item.replay.model_dump(mode="json"))
        assert item.sleeve_sha256 == canonical_sha256({
            "baseline_id": baseline_id,
            "symbol": item.symbol,
            "replay_sha256": item.replay_sha256,
            "initial_cash": 12500.0,
            "execution_series": "QFQ_NORMALIZED",
        })


def test_baseline_fill_uses_next_open_and_zero_target_liquidates(authority):
    result = _simulate()(authority, _market(crash=True), "baseline-trend-v1")
    spy = next(item.replay for item in result.sleeves if item.symbol == "SPY")
    assert len(spy.fills) >= 2
    buy, sell = spy.fills[:2]
    assert buy.signal_timestamp == spy.sessions[0]
    assert buy.fill_timestamp == spy.sessions[1]
    assert buy.reference_open == 130.0
    assert buy.units_delta > 0
    assert sell.signal_timestamp == spy.sessions[1]
    assert sell.fill_timestamp == spy.sessions[2]
    assert sell.reference_open == 80.0
    assert sell.units_delta < 0
    assert all(fill.signal_timestamp < fill.fill_timestamp for fill in spy.fills)
    assert all(state.cash >= 0 for state in spy.states)


def test_one_sleeve_change_does_not_mutate_another_sleeve(authority):
    first = _simulate()(authority, _market(), "baseline-trend-v1")
    changed = _simulate()(authority, _market(glc_change=200.0), "baseline-trend-v1")
    spy_first = next(item.replay for item in first.sleeves if item.symbol == "SPY")
    spy_changed = next(item.replay for item in changed.sleeves if item.symbol == "SPY")
    assert spy_first == spy_changed
    assert first.close_equity != changed.close_equity


def test_unsealed_baseline_id_is_rejected(authority):
    with pytest.raises(ValueError, match="BASELINE"):
        _simulate()(authority, _market(), "baseline-unsealed-v1")


def test_changed_current_strategy_source_cannot_claim_frozen_implementation(authority, monkeypatch):
    original = Path.read_bytes
    pinned_path = ROOT / "src/investment_tracker/quant/strategies/trend.py"

    def read_with_tampered_strategy(path):
        if Path(path) == pinned_path:
            return b"tampered strategy bytes"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_with_tampered_strategy)
    with pytest.raises(ValueError, match="BASELINE_IMPLEMENTATION_MISMATCH"):
        _simulate()(authority, _market(), "baseline-trend-v1")
