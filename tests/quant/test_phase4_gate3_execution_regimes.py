from __future__ import annotations

from dataclasses import replace
from importlib import import_module
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.phase4.engine.benchmarks import cash_benchmark, equal_weight_buy_and_hold
from investment_tracker.quant.phase4.engine.market import MarketPanel
from investment_tracker.quant.phase4.gate3.artifacts import Gate3ArtifactStore
from investment_tracker.quant.phase4.gate3.authorities import (
    LaggedReturnRegimeAuthority, REGIME_IDS, canonical_authority_sha256,
)
from investment_tracker.quant.phase4.gate3.seal import preflight_gate3, load_and_verify_gate3_authority


ROOT = Path(__file__).resolve().parents[2]
PINNED_MANIFEST = "705935c9b06b8f592e66e5e71e4541d910b585be6e9a30e46b99fe97b7591d4f"
PINNED_REGIME_DEFINITION = "f8f78a3eff8c5785b6da3a8079b4e3d44c6a186459ae180074d9c40b65e4499b"


def _regimes():
    return import_module("investment_tracker.quant.phase4.gate3_execution.regimes")


@pytest.fixture(scope="module")
def frozen_authority() -> LaggedReturnRegimeAuthority:
    assert preflight_gate3(ROOT, PINNED_MANIFEST).gate3 == "READY"
    manifest = load_and_verify_gate3_authority(ROOT, PINNED_MANIFEST)
    document = json.loads(Gate3ArtifactStore(ROOT).verify(manifest.regime_authority))
    fields = document["authority"]
    fields["symbols"] = tuple(fields["symbols"])
    fields["regime_ids"] = tuple(fields["regime_ids"])
    fields["session_to_regime"] = tuple(tuple(pair) for pair in fields["session_to_regime"])
    authority = LaggedReturnRegimeAuthority(**fields)
    assert canonical_authority_sha256(authority) == PINNED_REGIME_DEFINITION
    return authority


def _panel(closes: list[float], authority: LaggedReturnRegimeAuthority) -> MarketPanel:
    index = pd.DatetimeIndex([pd.Timestamp(session, tz="UTC") for session, _ in authority.session_to_regime])
    assert len(closes) == len(index) == 1008
    opens = pd.DataFrame({"SPY": np.full(len(closes), 10.0)}, index=index)
    close_frame = pd.DataFrame({"SPY": closes}, index=index)
    return MarketPanel.from_frames(opens, close_frame, role="SCORED")


def test_first_session_is_labelled_without_a_synthetic_return(frozen_authority):
    replay = cash_benchmark(_panel([10.0] * 1008, frozen_authority))
    result = _regimes().attribute_regime_returns(replay, frozen_authority)
    assert len(replay.sessions) == 1008
    assert len(replay.daily_returns) == 1007
    assert result.first_session_label == frozen_authority.session_to_regime[0][1]
    assert result.first_session_return is None
    assert sum(item.return_observation_count for item in result.regimes) == 1007
    assert sum(len(item.return_vector) for item in result.regimes) == 1007
    assert all("cagr" not in item.__dict__ and "calmar" not in item.__dict__ for item in result.regimes)


def test_return_uses_frozen_ending_session_label_and_conditional_compounding(frozen_authority):
    labels = tuple(label for _, label in frozen_authority.session_to_regime)
    position = next(i for i in range(4, 1007) if labels[i] == labels[i + 1])
    closes = [10.0] * 1008
    closes[position] = 11.0
    closes[position + 1] = 9.9
    closes[position + 2:] = [9.9] * (1008 - position - 2)
    replay = equal_weight_buy_and_hold(_panel(closes, frozen_authority), friction_bps=0)
    result = _regimes().attribute_regime_returns(replay, frozen_authority)
    assigned = next(item for item in result.regimes if item.regime_id == labels[position])
    assert replay.sessions[position] in assigned.ending_sessions
    assert replay.sessions[position + 1] in assigned.ending_sessions
    assert tuple(value for value in assigned.return_vector if abs(value) > 1e-8) == pytest.approx((0.1, -0.1))
    assert assigned.conditional_compounded_return == pytest.approx(-0.01)
    assert assigned.positive_return_count == 1
    assert assigned.positive_return_percentage == pytest.approx(1 / assigned.return_observation_count)


def test_empty_conditional_subset_is_unknown_without_imputed_zero():
    summary = _regimes()._conditional_metrics(())
    assert summary == (0, 0, None, None, None, "UNKNOWN", "NO_RETURN_OBSERVATIONS")


def test_missing_duplicate_changed_label_or_changed_definition_fails_closed(frozen_authority):
    replay = cash_benchmark(_panel([10.0] * 1008, frozen_authority))
    pairs = frozen_authority.session_to_regime
    changed_label = REGIME_IDS[(REGIME_IDS.index(pairs[10][1]) + 1) % 3]
    altered = (
        replace(frozen_authority, session_to_regime=pairs[:-1]),
        replace(frozen_authority, session_to_regime=pairs + pairs[-1:]),
        replace(frozen_authority, session_to_regime=pairs[:10] + ((pairs[10][0], changed_label),) + pairs[11:]),
        replace(frozen_authority, algorithm="ALTERED_WITH_SAME_LABELS"),
    )
    for authority in altered:
        with pytest.raises(ValueError, match="REGIME_AUTHORITY_INVALID"):
            _regimes().attribute_regime_returns(replay, authority)
