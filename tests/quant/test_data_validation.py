from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.data.models import DataRequest
from investment_tracker.quant.data.validation import BarDataValidator


def request(start: str = "2024-07-03", end: str = "2024-07-05") -> DataRequest:
    return DataRequest(
        provider="MOOMOO",
        symbol="SPY",
        interval="1d",
        adjustment="QFQ",
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
    )


def bars(dates: list[str]) -> pd.DataFrame:
    count = len(dates)
    return pd.DataFrame(
        {
            "open": np.arange(100.0, 100.0 + count),
            "high": np.arange(102.0, 102.0 + count),
            "low": np.arange(99.0, 99.0 + count),
            "close": np.arange(101.0, 101.0 + count),
            "volume": np.arange(1_000, 1_000 + count),
        },
        index=pd.DatetimeIndex(dates, tz="UTC", name="timestamp"),
    )


def issue_codes(frame: pd.DataFrame, req: DataRequest | None = None) -> set[str]:
    report = BarDataValidator("XNYS").validate(frame, req or request())
    return {issue.code for issue in report.issues}


def test_exchange_holiday_is_not_reported_missing() -> None:
    frame = bars(["2024-07-03", "2024-07-05"])
    report = BarDataValidator("XNYS").validate(frame, request())
    assert report.clean
    assert report.issues == ()


def test_missing_exchange_session_fails_closed() -> None:
    frame = bars(["2024-07-01", "2024-07-03"])
    assert "MISSING_SESSION" in issue_codes(frame, request("2024-07-01", "2024-07-03"))


def test_duplicate_timestamp_fails_closed() -> None:
    frame = bars(["2024-07-03", "2024-07-05"])
    duplicate = pd.concat([frame, frame.iloc[[0]]])
    assert "DUPLICATE_TIMESTAMP" in issue_codes(duplicate)


def test_invalid_ohlc_relationship_fails_closed() -> None:
    frame = bars(["2024-07-03", "2024-07-05"])
    frame.loc[frame.index[0], "high"] = 50.0
    assert "INVALID_OHLC" in issue_codes(frame)


@pytest.mark.parametrize("column", ["open", "high", "low", "close"])
def test_negative_price_fails_closed(column: str) -> None:
    frame = bars(["2024-07-03", "2024-07-05"])
    frame.loc[frame.index[0], column] = -1.0
    assert "NEGATIVE_PRICE" in issue_codes(frame)


def test_negative_volume_fails_closed() -> None:
    frame = bars(["2024-07-03", "2024-07-05"])
    frame.loc[frame.index[0], "volume"] = -1
    assert "NEGATIVE_VOLUME" in issue_codes(frame)


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_non_finite_values_fail_closed(value: float) -> None:
    frame = bars(["2024-07-03", "2024-07-05"])
    frame.loc[frame.index[0], "close"] = value
    assert "NON_FINITE_VALUE" in issue_codes(frame)


def test_timezone_naive_index_fails_closed() -> None:
    frame = bars(["2024-07-03", "2024-07-05"])
    frame.index = frame.index.tz_localize(None)
    assert "TIMEZONE_CONFLICT" in issue_codes(frame)


def test_validator_does_not_repair_or_mutate_input() -> None:
    frame = bars(["2024-07-05", "2024-07-03"])
    before = frame.copy(deep=True)
    assert "NON_MONOTONIC_TIMESTAMP" in issue_codes(frame)
    pd.testing.assert_frame_equal(frame, before)


def test_request_dates_must_be_ordered() -> None:
    with pytest.raises(ValueError, match="end must be on or after start"):
        request("2024-07-05", "2024-07-03")
