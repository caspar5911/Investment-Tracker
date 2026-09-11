from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from investment_tracker.governance import LockedHoldoutError
from investment_tracker.quant.data.models import DataRequest
from investment_tracker.quant.data.moomoo_client import MoomooHistoricalDataSource


class FakeKLType:
    K_DAY = "K_DAY_VALUE"


class FakeAuType:
    QFQ = "qfq-value"


class FakeKLField:
    ALL = "all-fields-value"


class FakeSession:
    RTH = "rth-value"


class FakeSDK:
    RET_OK = 0
    KLType = FakeKLType
    AuType = FakeAuType
    KL_FIELD = FakeKLField
    Session = FakeSession
    __version__ = "10.10-test"


def request(symbol: str = "SPY") -> DataRequest:
    return DataRequest(
        symbol=symbol,
        start=date(2014, 1, 1),
        end=date(2022, 12, 31),
    )


def page(day: str, close: float = 101.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "code": "US.SPY",
                "time_key": f"{day} 00:00:00",
                "open": close - 1,
                "high": close + 1,
                "low": close - 2,
                "close": close,
                "volume": 1_000,
                "turnover": 100_000.0,
                "pe_ratio": 20.5,
            }
        ]
    )


class FakeContext:
    def __init__(self, *, history=(), state=(0, {}), calendar=(0, [])) -> None:
        self.history = list(history)
        self.state = state
        self.calendar = calendar
        self.history_calls: list[dict[str, object]] = []
        self.calendar_calls: list[dict[str, object]] = []
        self.global_state_calls = 0
        self.closed = False

    def request_history_kline(self, **kwargs):
        self.history_calls.append(kwargs)
        return self.history.pop(0)

    def request_trading_days(self, **kwargs):
        self.calendar_calls.append(kwargs)
        return self.calendar

    def get_global_state(self):
        self.global_state_calls += 1
        return self.state

    def close(self) -> None:
        self.closed = True


def source(context: FakeContext) -> MoomooHistoricalDataSource:
    return MoomooHistoricalDataSource(
        host="127.0.0.1",
        port=11111,
        context_factory=lambda **_: context,
        sdk_loader=lambda: FakeSDK,
    )


def test_fetch_evidence_preserves_complete_raw_pages_and_request_chain() -> None:
    context = FakeContext(
        history=[
            (0, page("2014-01-02"), b"next"),
            (0, page("2014-01-03", 102.0), None),
        ]
    )

    evidence = source(context).fetch_with_evidence(request())

    assert evidence.status == "SUCCESS"
    assert evidence.error is None
    assert len(evidence.pages) == 2
    assert evidence.pages[0].input_page_req_key is None
    assert evidence.pages[0].output_page_req_key == b"next"
    assert evidence.pages[1].input_page_req_key == b"next"
    assert evidence.pages[1].output_page_req_key is None
    assert evidence.pages[0].frame.loc[0, "code"] == "US.SPY"
    assert evidence.pages[0].frame.loc[0, "time_key"] == "2014-01-02 00:00:00"
    assert evidence.pages[0].frame.loc[0, "turnover"] == 100_000.0
    assert evidence.pages[0].frame.loc[0, "pe_ratio"] == 20.5
    assert evidence.request_parameters["code"] == "US.SPY"
    assert evidence.request_parameters["ktype"] == {
        "name": "K_DAY",
        "value": "K_DAY_VALUE",
    }
    assert evidence.request_parameters["autype"] == {"name": "QFQ", "value": "qfq-value"}
    assert evidence.request_parameters["fields"] == [
        {"name": "ALL", "value": "all-fields-value"}
    ]
    assert evidence.request_parameters["session"] == {"name": "RTH", "value": "rth-value"}
    assert evidence.request_parameters["max_count"] == 1000
    assert evidence.sdk_version == "10.10-test"
    assert evidence.normalized is not None
    assert evidence.normalized.index.tolist() == [
        pd.Timestamp("2014-01-02", tz="UTC"),
        pd.Timestamp("2014-01-03", tz="UTC"),
    ]
    assert [link.raw_time_key for link in evidence.row_links] == [
        "2014-01-02 00:00:00",
        "2014-01-03 00:00:00",
    ]
    assert context.closed


def test_provider_failure_returns_partial_auditable_evidence() -> None:
    context = FakeContext(
        history=[
            (0, page("2014-01-02"), b"next"),
            (1, "permission denied", None),
        ]
    )

    evidence = source(context).fetch_with_evidence(request())

    assert evidence.status == "ERROR"
    assert evidence.error == "Moomoo historical request failed: permission denied"
    assert len(evidence.pages) == 1
    assert evidence.pages[0].frame.loc[0, "time_key"] == "2014-01-02 00:00:00"
    assert evidence.normalized is None
    assert context.closed


def test_preflight_records_quote_state_and_closes_context() -> None:
    context = FakeContext(
        state=(
            0,
            {
                "server_ver": "10.10.7008",
                "qot_logined": True,
                "program_status_type": "READY",
                "program_status_desc": "",
                "trd_logined": False,
            },
        )
    )

    result = source(context).preflight("SPY")

    assert result.sdk_version == "10.10-test"
    assert result.opend_version == "10.10.7008"
    assert result.quote_logged_in is True
    assert result.program_status == "READY"
    assert result.host == "127.0.0.1"
    assert result.port == 11111
    assert context.global_state_calls == 1
    assert context.closed


def test_preflight_denies_locked_symbol_before_sdk_or_context() -> None:
    called = False

    def loader():
        nonlocal called
        called = True
        return FakeSDK

    with pytest.raises(LockedHoldoutError):
        MoomooHistoricalDataSource(sdk_loader=loader).preflight("GEV")
    assert called is False


def test_calendar_evidence_uses_code_and_fixed_dates_and_closes() -> None:
    returned = [
        {"time": "2014-01-02", "trade_date_type": "WHOLE"},
        {"time": "2014-01-03", "trade_date_type": "WHOLE"},
    ]
    context = FakeContext(calendar=(0, returned))

    evidence = source(context).fetch_calendar_evidence(request())

    assert evidence.status == "SUCCESS"
    assert evidence.data == returned
    assert evidence.request_parameters == {
        "provider": "MOOMOO",
        "code": "US.SPY",
        "start": "2014-01-01",
        "end": "2022-12-31",
        "host": "127.0.0.1",
        "port": 11111,
    }
    assert context.calendar_calls == [
        {"code": "US.SPY", "start": "2014-01-01", "end": "2022-12-31"}
    ]
    assert context.closed


def test_calendar_error_is_retained_and_context_closes() -> None:
    context = FakeContext(calendar=(1, "calendar unavailable"))

    evidence = source(context).fetch_calendar_evidence(request())

    assert evidence.status == "ERROR"
    assert evidence.error == "Moomoo trading-calendar request failed: calendar unavailable"
    assert evidence.data == "calendar unavailable"
    assert context.closed
