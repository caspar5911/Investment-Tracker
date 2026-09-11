from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from investment_tracker.governance import LockedHoldoutError
from investment_tracker.quant.data.models import DataRequest
from investment_tracker.quant.data.moomoo_client import (
    MoomooDataError,
    MoomooHistoricalDataSource,
)


class FakeKLType:
    K_DAY = "K_DAY"


class FakeAuType:
    QFQ = "QFQ"


class FakeKLField:
    ALL = "ALL"


class FakeSession:
    RTH = "RTH"


class FakeSDK:
    RET_OK = 0
    KLType = FakeKLType
    AuType = FakeAuType
    KL_FIELD = FakeKLField
    Session = FakeSession
    __version__ = "10.10-test"


def request(symbol: str = "SPY") -> DataRequest:
    return DataRequest(
        provider="MOOMOO",
        symbol=symbol,
        interval="1d",
        adjustment="QFQ",
        start=date(2024, 7, 3),
        end=date(2024, 7, 5),
    )


def page(day: str, close: float) -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "code": "US.SPY",
            "time_key": f"{day} 00:00:00",
            "open": close - 1,
            "high": close + 1,
            "low": close - 2,
            "close": close,
            "volume": 1000,
            "turnover": 100_000,
        }]
    )


class FakeContext:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []
        self.closed = False

    def request_history_kline(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)

    def close(self):
        self.closed = True


def test_constructor_does_not_import_sdk() -> None:
    calls = 0

    def loader():
        nonlocal calls
        calls += 1
        return FakeSDK

    MoomooHistoricalDataSource(sdk_loader=loader)
    assert calls == 0


def test_locked_symbol_is_denied_before_sdk_or_context_creation() -> None:
    def loader():
        raise AssertionError("SDK imported")

    with pytest.raises(LockedHoldoutError):
        MoomooHistoricalDataSource(sdk_loader=loader).fetch(request("NLR"))


def test_fetch_pages_daily_qfq_regular_session_and_closes_context() -> None:
    context = FakeContext([
        (0, page("2024-07-03", 101.0), b"next"),
        (0, page("2024-07-05", 102.0), None),
    ])
    created_with: dict[str, object] = {}

    def context_factory(**kwargs):
        created_with.update(kwargs)
        return context

    source = MoomooHistoricalDataSource(
        host="127.0.0.1",
        port=11111,
        context_factory=context_factory,
        sdk_loader=lambda: FakeSDK,
    )
    frame, version = source.fetch(request())

    assert created_with == {"host": "127.0.0.1", "port": 11111}
    assert len(context.calls) == 2
    assert context.calls[0] == {
        "code": "US.SPY",
        "start": "2024-07-03",
        "end": "2024-07-05",
        "ktype": "K_DAY",
        "autype": "QFQ",
        "fields": ["ALL"],
        "max_count": 1000,
        "page_req_key": None,
        "extended_time": False,
        "session": "RTH",
    }
    assert context.calls[1]["page_req_key"] == b"next"
    assert frame.index.tolist() == [
        pd.Timestamp("2024-07-03", tz="UTC"),
        pd.Timestamp("2024-07-05", tz="UTC"),
    ]
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert version == "10.10-test"
    assert context.closed


def test_provider_error_fails_closed_and_closes_context() -> None:
    context = FakeContext([(1, "permission denied", None)])
    source = MoomooHistoricalDataSource(
        context_factory=lambda **_: context,
        sdk_loader=lambda: FakeSDK,
    )
    with pytest.raises(MoomooDataError, match="permission denied"):
        source.fetch(request())
    assert context.closed


def test_repeated_pagination_key_fails_closed() -> None:
    context = FakeContext([
        (0, page("2024-07-03", 101.0), b"repeat"),
        (0, page("2024-07-05", 102.0), b"repeat"),
    ])
    source = MoomooHistoricalDataSource(
        context_factory=lambda **_: context,
        sdk_loader=lambda: FakeSDK,
    )
    with pytest.raises(MoomooDataError, match="pagination loop"):
        source.fetch(request())
    assert context.closed


def test_empty_or_malformed_provider_payload_fails_closed() -> None:
    context = FakeContext([(0, pd.DataFrame([{"time_key": "2024-07-03"}]), None)])
    source = MoomooHistoricalDataSource(
        context_factory=lambda **_: context,
        sdk_loader=lambda: FakeSDK,
    )
    with pytest.raises(MoomooDataError, match="missing columns"):
        source.fetch(request())
    assert context.closed


def test_provider_payload_for_a_different_symbol_fails_closed() -> None:
    wrong = page("2024-07-03", 101.0).assign(code="US.QQQ")
    context = FakeContext([(0, wrong, None)])
    source = MoomooHistoricalDataSource(
        context_factory=lambda **_: context,
        sdk_loader=lambda: FakeSDK,
    )

    with pytest.raises(MoomooDataError, match="symbol identity mismatch"):
        source.fetch(request("SPY"))
    assert context.closed


def test_us_provider_timestamp_uses_eastern_market_date_for_session_label() -> None:
    payload = page("2024-07-03", 101.0)
    payload.loc[0, "time_key"] = "2024-07-04T03:30:00+00:00"
    context = FakeContext([(0, payload, None)])
    source = MoomooHistoricalDataSource(
        context_factory=lambda **_: context,
        sdk_loader=lambda: FakeSDK,
    )

    frame, _ = source.fetch(request("SPY"))

    assert frame.index.tolist() == [pd.Timestamp("2024-07-03", tz="UTC")]
