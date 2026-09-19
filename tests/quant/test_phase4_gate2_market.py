from __future__ import annotations

from decimal import Decimal
from importlib import import_module
import inspect

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.phase4.engine.models import Gate2SealError


try:
    _market_module = import_module("investment_tracker.quant.phase4.engine.market")
    MarketPanel = _market_module.MarketPanel
    ScoredMarketInput = _market_module.ScoredMarketInput
    _MARKET_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as exc:
    _market_module = None
    MarketPanel = None
    ScoredMarketInput = None
    _MARKET_IMPORT_ERROR = exc


@pytest.fixture(autouse=True)
def require_market_types(request: pytest.FixtureRequest) -> None:
    if request.node.name != "test_market_types_are_available" and (
        _MARKET_IMPORT_ERROR is not None
    ):
        pytest.skip("market types are not implemented yet")


def _sessions(start: str = "2024-01-02", *, periods: int = 3) -> pd.DatetimeIndex:
    return pd.date_range(start, periods=periods, freq="D", tz="UTC")


def _frames(
    *,
    index: pd.DatetimeIndex | None = None,
    columns: list[object] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    actual_index = _sessions() if index is None else index
    actual_columns = ["AAA", "BBB"] if columns is None else columns
    open_values = np.array(
        [[10.0, 20.0], [10.5, 19.5], [11.0, 21.0]], dtype=np.float64
    )[: len(actual_index), : len(actual_columns)]
    close_values = np.array(
        [[10.25, 19.75], [10.75, 20.5], [11.5, 21.25]], dtype=np.float64
    )[: len(actual_index), : len(actual_columns)]
    return (
        pd.DataFrame(open_values, index=actual_index, columns=actual_columns),
        pd.DataFrame(close_values, index=actual_index, columns=actual_columns),
    )


def _assert_invalid(
    open_prices: pd.DataFrame,
    close_prices: pd.DataFrame,
    *,
    role: str = "SCORED",
) -> None:
    with pytest.raises(Gate2SealError, match="market panel") as exc_info:
        MarketPanel.from_frames(open_prices, close_prices, role=role)
    assert exc_info.value.code == "MARKET_PANEL_INVALID"


def test_market_types_are_available() -> None:
    assert _MARKET_IMPORT_ERROR is None
    assert inspect.isclass(MarketPanel)
    assert inspect.isclass(ScoredMarketInput)


def test_panel_preserves_canonical_order_binary64_values_and_literal_identity() -> None:
    index = _sessions(periods=2)
    low = np.nextafter(np.float64(10.0), np.float64(0.0))
    high = np.nextafter(np.float64(20.0), np.float64(np.inf))
    open_prices = pd.DataFrame(
        [[low, high], [10.5, 20.5]], index=index, columns=["AAA", "BBB"]
    )
    close_prices = pd.DataFrame(
        [[10.25, 20.25], [10.75, 20.75]], index=index, columns=["AAA", "BBB"]
    )

    panel = MarketPanel.from_frames(open_prices, close_prices, role="SCORED")

    assert panel.symbols == ("AAA", "BBB")
    assert panel.sessions == tuple(index)
    assert panel.role == "SCORED"
    assert panel.open_prices.columns.tolist() == ["AAA", "BBB"]
    assert np.array_equal(
        panel.open_prices.to_numpy().view(np.uint64),
        open_prices.to_numpy().view(np.uint64),
    )
    assert np.array_equal(
        panel.close_prices.to_numpy().view(np.uint64),
        close_prices.to_numpy().view(np.uint64),
    )
    assert (
        panel.panel_sha256
        == "05b157845aaa84c38bb4fe010f010159a6703ec6abf0793708625856ca8536a2"
    )

    warmup = MarketPanel.from_frames(open_prices, close_prices, role="WARMUP")
    assert (
        warmup.panel_sha256
        == "d068922266cdbbc5fafb50782ceed0172e36886801bd40c0aa0d9ec5ec5df7dc"
    )
    assert warmup.panel_sha256 != panel.panel_sha256


def test_panel_owns_inputs_and_returns_defensive_frame_copies() -> None:
    open_prices, close_prices = _frames()
    expected_open = open_prices.copy(deep=True)
    expected_close = close_prices.copy(deep=True)
    panel = MarketPanel.from_frames(open_prices, close_prices, role="SCORED")
    original_hash = panel.panel_sha256

    open_prices.iloc[0, 0] = 999.0
    close_prices.iloc[0, 0] = 999.0
    returned_open = panel.open_prices
    returned_close = panel.close_prices
    returned_open.iloc[0, 0] = 777.0
    returned_close.iloc[0, 0] = 777.0

    pd.testing.assert_frame_equal(panel.open_prices, expected_open, check_freq=False)
    pd.testing.assert_frame_equal(panel.close_prices, expected_close, check_freq=False)
    assert panel.panel_sha256 == original_hash
    with pytest.raises((AttributeError, TypeError)):
        panel.role = "WARMUP"


@pytest.mark.parametrize(
    "bad_index",
    [
        pd.date_range("2024-01-02", periods=3, freq="D"),
        pd.date_range("2024-01-02", periods=3, freq="D", tz="America/New_York"),
        pd.DatetimeIndex(
            [
                pd.Timestamp("2024-01-02 00:00", tz="UTC"),
                pd.Timestamp("2024-01-03 01:00", tz="UTC"),
                pd.Timestamp("2024-01-04 00:00", tz="UTC"),
            ]
        ),
        pd.DatetimeIndex(
            [
                pd.Timestamp("2024-01-02", tz="UTC"),
                pd.Timestamp("2024-01-02", tz="UTC"),
                pd.Timestamp("2024-01-04", tz="UTC"),
            ]
        ),
        pd.DatetimeIndex(
            [
                pd.Timestamp("2024-01-03", tz="UTC"),
                pd.Timestamp("2024-01-02", tz="UTC"),
                pd.Timestamp("2024-01-04", tz="UTC"),
            ]
        ),
    ],
    ids=["timezone-naive", "non-UTC", "non-midnight", "duplicate", "decreasing"],
)
def test_panel_rejects_noncanonical_sessions(bad_index: pd.DatetimeIndex) -> None:
    open_prices, close_prices = _frames(index=bad_index)
    _assert_invalid(open_prices, close_prices)


def test_panel_rejects_mismatched_missing_or_extra_sessions() -> None:
    open_prices, close_prices = _frames()

    _assert_invalid(open_prices.iloc[:-1], close_prices)
    _assert_invalid(open_prices, close_prices.iloc[:-1])


@pytest.mark.parametrize(
    ("open_columns", "close_columns"),
    [
        (["BBB", "AAA"], ["BBB", "AAA"]),
        (["AAA", "AAA"], ["AAA", "AAA"]),
        (["AAA", "BBB"], ["AAA", "CCC"]),
        (["AAA", "BBB"], ["AAA"]),
        (["AAA", 2], ["AAA", 2]),
        (["", "BBB"], ["", "BBB"]),
    ],
    ids=[
        "noncanonical-order",
        "duplicate",
        "mismatched-symbol",
        "missing-symbol",
        "non-string",
        "empty-symbol",
    ],
)
def test_panel_rejects_noncanonical_or_mismatched_symbols(
    open_columns: list[object], close_columns: list[object]
) -> None:
    index = _sessions()
    open_values = np.full((len(index), len(open_columns)), 10.0, dtype=np.float64)
    close_values = np.full((len(index), len(close_columns)), 11.0, dtype=np.float64)
    open_prices = pd.DataFrame(open_values, index=index, columns=open_columns)
    close_prices = pd.DataFrame(close_values, index=index, columns=close_columns)
    _assert_invalid(open_prices, close_prices)


@pytest.mark.parametrize(
    "bad_value",
    [np.nan, np.inf, -np.inf, 0.0, -1.0],
    ids=["missing", "positive-infinity", "negative-infinity", "zero", "negative"],
)
@pytest.mark.parametrize("frame_name", ["open", "close"])
def test_panel_rejects_invalid_price_values(bad_value: float, frame_name: str) -> None:
    open_prices, close_prices = _frames()
    target = open_prices if frame_name == "open" else close_prices
    target.iloc[1, 1] = bad_value
    _assert_invalid(open_prices, close_prices)


@pytest.mark.parametrize(
    "bad_value",
    ["10.0", Decimal("10.1"), 2**53 + 1, True],
    ids=["numeric-string", "decimal-fraction", "inexact-large-integer", "boolean"],
)
def test_panel_rejects_ambiguous_non_binary64_coercion(bad_value: object) -> None:
    open_prices, close_prices = _frames()
    open_prices = open_prices.astype(object)
    open_prices.iloc[0, 0] = bad_value
    _assert_invalid(open_prices, close_prices)


def test_panel_accepts_only_exact_non_binary64_numeric_coercion() -> None:
    open_prices, close_prices = _frames()
    open_prices = open_prices.astype(object)
    open_prices.iloc[0, 0] = 10
    open_prices.iloc[0, 1] = np.float32(20.0)

    panel = MarketPanel.from_frames(open_prices, close_prices, role="SCORED")

    assert panel.open_prices.dtypes.tolist() == [np.dtype("float64")] * 2
    assert panel.open_prices.iloc[0].tolist() == [10.0, 20.0]


@pytest.mark.parametrize("integer_dtype", [np.int64, np.uint64])
def test_panel_rejects_homogeneous_numpy_integer_hash_collision(
    integer_dtype: type[np.integer],
) -> None:
    index = _sessions(periods=2)
    exactly_representable = 2**53
    rounded_collision = exactly_representable + 1
    exact_open = pd.DataFrame(
        np.array([[exactly_representable, 20], [30, 40]], dtype=integer_dtype),
        index=index,
        columns=["AAA", "BBB"],
    )
    lossy_open = exact_open.copy(deep=True)
    lossy_open.iloc[0, 0] = rounded_collision
    close_prices = pd.DataFrame(
        np.array([[50, 60], [70, 80]], dtype=integer_dtype),
        index=index,
        columns=["AAA", "BBB"],
    )

    exact_panel = MarketPanel.from_frames(exact_open, close_prices, role="SCORED")
    assert exact_panel.open_prices.iloc[0, 0] == float(exactly_representable)
    _assert_invalid(lossy_open, close_prices)


@pytest.mark.parametrize("integer_dtype", [np.int64, np.uint64])
def test_panel_accepts_exactly_representable_homogeneous_numpy_integers(
    integer_dtype: type[np.integer],
) -> None:
    index = _sessions(periods=2)
    open_prices = pd.DataFrame(
        np.array([[10, 20], [30, 40]], dtype=integer_dtype),
        index=index,
        columns=["AAA", "BBB"],
    )
    close_prices = pd.DataFrame(
        np.array([[11, 21], [31, 41]], dtype=integer_dtype),
        index=index,
        columns=["AAA", "BBB"],
    )

    panel = MarketPanel.from_frames(open_prices, close_prices, role="SCORED")

    assert panel.open_prices.dtypes.tolist() == [np.dtype("float64")] * 2
    assert panel.open_prices.iloc[0].tolist() == [10.0, 20.0]


@pytest.mark.parametrize("role", ["TRAIN", "VALIDATION", "", None])
def test_panel_rejects_unknown_role(role: object) -> None:
    open_prices, close_prices = _frames()
    _assert_invalid(open_prices, close_prices, role=role)


def test_scored_input_separates_warmup_and_scored_history_defensively() -> None:
    warmup_open, warmup_close = _frames(index=_sessions("2023-12-29", periods=3))
    scored_open, scored_close = _frames(index=_sessions("2024-01-02", periods=3))
    warmup = MarketPanel.from_frames(warmup_open, warmup_close, role="WARMUP")
    scored = MarketPanel.from_frames(scored_open, scored_close, role="SCORED")

    market_input = ScoredMarketInput.from_panels(warmup, scored)

    assert market_input.indicator_warmup is warmup
    assert market_input.scored is scored
    assert market_input.warmup_panel_sha256 == warmup.panel_sha256
    assert market_input.scored_panel_sha256 == scored.panel_sha256
    expected_history = pd.concat([warmup_close, scored_close])
    pd.testing.assert_frame_equal(market_input.combined_close_history, expected_history)

    returned_history = market_input.combined_close_history
    returned_history.iloc[0, 0] = 999.0
    pd.testing.assert_frame_equal(market_input.combined_close_history, expected_history)
    assert not hasattr(scored, "combined_close_history")
    with pytest.raises((AttributeError, TypeError)):
        market_input.scored = warmup


@pytest.mark.parametrize(
    ("warmup_role", "scored_role"),
    [("SCORED", "SCORED"), ("WARMUP", "WARMUP")],
)
def test_scored_input_rejects_incorrect_panel_roles(
    warmup_role: str, scored_role: str
) -> None:
    warmup_open, warmup_close = _frames(index=_sessions("2023-12-29", periods=3))
    scored_open, scored_close = _frames(index=_sessions("2024-01-02", periods=3))
    warmup = MarketPanel.from_frames(warmup_open, warmup_close, role=warmup_role)
    scored = MarketPanel.from_frames(scored_open, scored_close, role=scored_role)

    with pytest.raises(Gate2SealError) as exc_info:
        ScoredMarketInput.from_panels(warmup, scored)
    assert exc_info.value.code == "MARKET_PANEL_INVALID"


@pytest.mark.parametrize("case", ["overlap", "touch", "reversed"])
def test_scored_input_requires_warmup_strictly_before_scored(case: str) -> None:
    if case == "overlap":
        warmup_index = _sessions("2024-01-01", periods=3)
        scored_index = _sessions("2024-01-03", periods=3)
    elif case == "touch":
        warmup_index = _sessions("2024-01-01", periods=3)
        scored_index = _sessions("2024-01-03", periods=1)
    else:
        warmup_index = _sessions("2024-01-04", periods=2)
        scored_index = _sessions("2024-01-01", periods=2)
    warmup_open, warmup_close = _frames(index=warmup_index)
    scored_open, scored_close = _frames(index=scored_index)
    warmup = MarketPanel.from_frames(warmup_open, warmup_close, role="WARMUP")
    scored = MarketPanel.from_frames(scored_open, scored_close, role="SCORED")

    with pytest.raises(Gate2SealError) as exc_info:
        ScoredMarketInput.from_panels(warmup, scored)
    assert exc_info.value.code == "MARKET_PANEL_INVALID"


def test_scored_input_rejects_symbol_mismatch() -> None:
    warmup_open, warmup_close = _frames(index=_sessions("2023-12-29", periods=3))
    scored_open, scored_close = _frames(
        index=_sessions("2024-01-02", periods=3), columns=["AAA"]
    )
    warmup = MarketPanel.from_frames(warmup_open, warmup_close, role="WARMUP")
    scored = MarketPanel.from_frames(scored_open, scored_close, role="SCORED")

    with pytest.raises(Gate2SealError) as exc_info:
        ScoredMarketInput.from_panels(warmup, scored)
    assert exc_info.value.code == "MARKET_PANEL_INVALID"


def test_market_boundary_exposes_no_filesystem_loader() -> None:
    assert tuple(inspect.signature(MarketPanel.from_frames).parameters) == (
        "open_prices",
        "close_prices",
        "role",
    )
    assert not hasattr(MarketPanel, "from_path")
    assert not hasattr(MarketPanel, "load")
    assert not hasattr(_market_module, "load_market")
