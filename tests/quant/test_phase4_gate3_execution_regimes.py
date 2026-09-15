from __future__ import annotations

from importlib import import_module

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.phase4.engine.benchmarks import cash_benchmark, equal_weight_buy_and_hold
from investment_tracker.quant.phase4.engine.market import MarketPanel
from investment_tracker.quant.phase4.gate3.authorities import (
    LaggedReturnRegimeAuthority,
    REGIME_IDS,
)


def _attribute():
    return import_module(
        "investment_tracker.quant.phase4.gate3_execution.regimes"
    ).attribute_regime_returns


def _panel(closes: list[float]) -> MarketPanel:
    index = pd.date_range("2024-01-01", periods=len(closes), freq="D", tz="UTC")
    opens = pd.DataFrame({"SPY": np.full(len(closes), 10.0)}, index=index)
    closes_frame = pd.DataFrame({"SPY": closes}, index=index)
    return MarketPanel.from_frames(opens, closes_frame, role="SCORED")


def _authority(
    sessions: tuple[pd.Timestamp, ...],
    labels: tuple[str, ...],
) -> LaggedReturnRegimeAuthority:
    return LaggedReturnRegimeAuthority(
        schema_version="PHASE4-GATE3-REGIME-AUTHORITY-v1",
        algorithm="TEST_FIXED_LABELS",
        symbols=("SPY",),
        regime_ids=REGIME_IDS,
        lookback_sessions=126,
        numerator_offset=1,
        denominator_offset=127,
        positive_threshold=1,
        negative_threshold=1,
        zero_semantics="TEST",
        session_to_regime=tuple(
            (session.strftime("%Y-%m-%d"), label)
            for session, label in zip(sessions, labels, strict=True)
        ),
    )


def test_first_session_is_labelled_without_a_synthetic_return():
    replay = cash_benchmark(_panel([10.0] * 1008))
    labels = tuple(REGIME_IDS[i % 3] for i in range(1008))
    result = _attribute()(replay, _authority(replay.sessions, labels))
    assert len(replay.sessions) == 1008
    assert len(replay.daily_returns) == 1007
    assert result.first_session_label == labels[0]
    assert result.first_session_return is None
    assert sum(item.return_observation_count for item in result.regimes) == 1007
    assert sum(len(item.return_vector) for item in result.regimes) == 1007
    assert all("cagr" not in item.__dict__ for item in result.regimes)
    assert all("calmar" not in item.__dict__ for item in result.regimes)


def test_return_uses_ending_session_label_and_conditional_compounding():
    replay = equal_weight_buy_and_hold(_panel([10.0, 10.0, 11.0, 9.9]), friction_bps=0)
    labels = (
        "mixed_cross_asset",
        "broad_negative_trend",
        "broad_positive_trend",
        "broad_positive_trend",
    )
    result = _attribute()(replay, _authority(replay.sessions, labels))
    by_id = {item.regime_id: item for item in result.regimes}
    positive = by_id["broad_positive_trend"]
    negative = by_id["broad_negative_trend"]
    mixed = by_id["mixed_cross_asset"]
    assert positive.ending_sessions == replay.sessions[2:]
    assert positive.return_vector == pytest.approx((0.1, -0.1))
    assert positive.conditional_compounded_return == pytest.approx(-0.01)
    assert positive.positive_return_count == 1
    assert positive.positive_return_percentage == 0.5
    assert negative.return_vector == (0.0,)
    assert mixed.return_observation_count == 0
    assert mixed.status == "UNKNOWN"
    assert mixed.reason == "NO_RETURN_OBSERVATIONS"
    assert mixed.conditional_compounded_return is None


def test_missing_or_duplicate_regime_mapping_fails_closed():
    replay = cash_benchmark(_panel([10.0] * 4))
    labels = tuple(REGIME_IDS[i % 3] for i in range(4))
    missing = _authority(replay.sessions[:-1], labels[:-1])
    duplicated = _authority(replay.sessions + replay.sessions[-1:], labels + labels[-1:])
    with pytest.raises(ValueError, match="REGIME"):
        _attribute()(replay, missing)
    with pytest.raises(ValueError, match="REGIME"):
        _attribute()(replay, duplicated)
