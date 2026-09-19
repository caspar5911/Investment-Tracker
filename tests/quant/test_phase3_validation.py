from __future__ import annotations

from datetime import date, datetime, timezone

import exchange_calendars as xcals
import pandas as pd
import pytest

from investment_tracker.quant.data.models import DataRequest
from investment_tracker.quant.data.moomoo_client import (
    MoomooCalendarEvidence,
    MoomooFetchEvidence,
    MoomooRawPage,
    MoomooRawRowLink,
)
from investment_tracker.quant.universe.constants import CAMPAIGN_END, CAMPAIGN_START
from investment_tracker.quant.universe.models import ArtifactIdentity
from investment_tracker.quant.universe.validation import Phase3DQValidator


NOW = datetime(2026, 9, 12, 2, 0, tzinfo=timezone.utc)


def request() -> DataRequest:
    return DataRequest(symbol="SPY", start=CAMPAIGN_START, end=CAMPAIGN_END)


def identity(kind: str, value: str) -> ArtifactIdentity:
    return ArtifactIdentity(kind=kind, sha256=value * 64, path=f"{kind}/{value * 64}")


def xnys_dates() -> list[date]:
    sessions = xcals.get_calendar("XNYS").sessions_in_range(CAMPAIGN_START, CAMPAIGN_END)
    return [timestamp.date() for timestamp in sessions]


def fetch_for_dates(dates: list[date]) -> MoomooFetchEvidence:
    raw = pd.DataFrame(
        {
            "code": ["US.SPY"] * len(dates),
            "time_key": [f"{day.isoformat()} 00:00:00" for day in dates],
            "open": [100.0] * len(dates),
            "high": [102.0] * len(dates),
            "low": [99.0] * len(dates),
            "close": [101.0] * len(dates),
            "volume": [1_000] * len(dates),
        }
    )
    normalized = raw.loc[:, ["open", "high", "low", "close", "volume"]].copy()
    normalized.index = pd.DatetimeIndex(dates, tz="UTC", name="timestamp")
    links = tuple(
        MoomooRawRowLink(
            page_number=1,
            row_number=index,
            code="US.SPY",
            raw_time_key=f"{day.isoformat()} 00:00:00",
            normalized_date=day,
        )
        for index, day in enumerate(dates)
    )
    return MoomooFetchEvidence(
        status="SUCCESS",
        request=request(),
        request_parameters={
            "provider": "MOOMOO",
            "code": "US.SPY",
            "start": "2014-01-01",
            "end": "2022-12-31",
            "ktype": {"name": "K_DAY", "value": "K_DAY"},
            "autype": {"name": "QFQ", "value": "qfq"},
            "fields": [{"name": "ALL", "value": ""}],
            "max_count": 1000,
            "extended_time": False,
            "session": {"name": "RTH", "value": "RTH"},
            "host": "127.0.0.1",
            "port": 11111,
        },
        retrieved_at=NOW,
        sdk_version="10.10.7008",
        pages=(MoomooRawPage(1, None, None, raw),),
        normalized=normalized,
        row_links=links,
    )


def calendar_evidence(open_dates: list[date], status: str = "SUCCESS") -> MoomooCalendarEvidence:
    data: object = [
        {"time": day.isoformat(), "trade_date_type": "WHOLE"} for day in open_dates
    ]
    error = None
    if status == "ERROR":
        data = "calendar unavailable"
        error = "Moomoo trading-calendar request failed: calendar unavailable"
    return MoomooCalendarEvidence(
        status=status,
        request=request(),
        request_parameters={
            "provider": "MOOMOO",
            "code": "US.SPY",
            "start": "2014-01-01",
            "end": "2022-12-31",
            "host": "127.0.0.1",
            "port": 11111,
        },
        retrieved_at=NOW,
        sdk_version="10.10.7008",
        data=data,
        error=error,
    )


def assess(
    fetch: MoomooFetchEvidence,
    calendar: MoomooCalendarEvidence | None = None,
):
    return Phase3DQValidator().assess(
        fetch,
        raw_identity=identity("raw_provider_evidence", "a"),
        normalized_identity=identity("normalized_dataset", "b"),
        opend_version="10.10.7008",
        calendar_evidence=calendar,
        calendar_identity=(
            identity("calendar_provider_evidence", "c") if calendar is not None else None
        ),
    )


def test_missing_session_has_null_raw_time_key_and_exact_neighbor_evidence() -> None:
    dates = xnys_dates()
    missing_date = date(2014, 1, 3)
    fetch = fetch_for_dates([day for day in dates if day != missing_date])
    before = fetch.normalized.copy(deep=True)

    result = assess(fetch, calendar_evidence([day for day in dates if day != missing_date]))

    assert result.status == "FAIL"
    assert len(result.missing_sessions) == 1
    missing = result.missing_sessions[0]
    assert missing.classification == "MISSING_SESSION"
    assert missing.session_date == missing_date
    assert missing.xnys_expected_open is True
    assert missing.raw_time_key is None
    assert missing.normalized_date is None
    assert missing.preceding is not None
    assert missing.preceding.raw_time_key == "2014-01-02 00:00:00"
    assert missing.preceding.normalized_date == date(2014, 1, 2)
    assert missing.following is not None
    assert missing.following.raw_time_key == "2014-01-06 00:00:00"
    assert missing.following.normalized_date == date(2014, 1, 6)
    assert missing.calendar.state == "DISAGREE"
    assert missing.calendar.provider_reported_open is False
    assert missing.cause == "UNKNOWN"
    pd.testing.assert_frame_equal(fetch.normalized, before)
    assert len(fetch.normalized) == len(dates) - 1


def test_missing_session_calendar_agreement_open_remains_a_failure() -> None:
    dates = xnys_dates()
    missing_date = date(2014, 1, 3)
    fetch = fetch_for_dates([day for day in dates if day != missing_date])

    result = assess(fetch, calendar_evidence(dates))

    assert result.status == "FAIL"
    assert result.missing_sessions[0].calendar.state == "AGREE_OPEN"
    assert result.missing_sessions[0].calendar.provider_reported_open is True


def test_unexpected_session_preserves_exact_raw_timestamp_and_neighbors() -> None:
    dates = xnys_dates()
    unexpected_date = date(2014, 1, 4)
    with_unexpected = sorted([*dates, unexpected_date])

    result = assess(fetch_for_dates(with_unexpected), calendar_evidence(dates))

    assert result.status == "FAIL"
    assert len(result.unexpected_sessions) == 1
    unexpected = result.unexpected_sessions[0]
    assert unexpected.classification == "UNEXPECTED_SESSION"
    assert unexpected.session_date == unexpected_date
    assert unexpected.xnys_expected_open is False
    assert unexpected.raw_time_key == "2014-01-04 00:00:00"
    assert unexpected.normalized_date == unexpected_date
    assert unexpected.preceding is not None
    assert unexpected.preceding.raw_time_key == "2014-01-03 00:00:00"
    assert unexpected.following is not None
    assert unexpected.following.raw_time_key == "2014-01-06 00:00:00"
    assert unexpected.calendar.state == "AGREE_CLOSED"
    assert unexpected.calendar.provider_reported_open is False
    assert unexpected.cause == "UNKNOWN"


def test_unexpected_session_calendar_disagreement_cannot_override_failure() -> None:
    dates = xnys_dates()
    unexpected_date = date(2014, 1, 4)

    result = assess(
        fetch_for_dates(sorted([*dates, unexpected_date])),
        calendar_evidence([*dates, unexpected_date]),
    )

    assert result.status == "FAIL"
    assert result.unexpected_sessions[0].calendar.state == "DISAGREE"
    assert result.unexpected_sessions[0].calendar.provider_reported_open is True


def test_unavailable_calendar_is_explicit_and_does_not_change_dq() -> None:
    dates = xnys_dates()
    missing_date = date(2014, 1, 3)
    result = assess(
        fetch_for_dates([day for day in dates if day != missing_date]),
        calendar_evidence([], status="ERROR"),
    )

    assert result.status == "FAIL"
    assert result.missing_sessions[0].calendar.state == "UNAVAILABLE"
    assert result.missing_sessions[0].calendar.provider_reported_open is None


def test_clean_fixed_window_passes_and_can_finalize_without_quarantine() -> None:
    result = assess(fetch_for_dates(xnys_dates()))

    assert result.status == "PASS"
    assert result.issues == ()
    assert result.missing_sessions == ()
    assert result.unexpected_sessions == ()
    finalized = result.finalize(quarantine=None)
    assert finalized.status == "PASS"
    assert finalized.quarantine is None


def test_failed_assessment_requires_quarantine_before_snapshot_result() -> None:
    dates = xnys_dates()
    result = assess(fetch_for_dates(dates[:-1]))

    with pytest.raises(ValueError, match="quarantine"):
        result.finalize(quarantine=None)
    finalized = result.finalize(quarantine=identity("quarantine", "d"))
    assert finalized.status == "FAIL"
    assert finalized.quarantine == identity("quarantine", "d")


def test_provider_error_is_a_fail_closed_assessment_with_raw_evidence() -> None:
    successful = fetch_for_dates(xnys_dates())
    failed = MoomooFetchEvidence(
        status="ERROR",
        request=successful.request,
        request_parameters=successful.request_parameters,
        retrieved_at=NOW,
        sdk_version="10.10.7008",
        pages=successful.pages[:1],
        normalized=None,
        row_links=(),
        error="Moomoo historical request failed: permission denied",
        error_data="permission denied",
    )

    result = Phase3DQValidator().assess(
        failed,
        raw_identity=identity("raw_provider_evidence", "a"),
        normalized_identity=None,
        opend_version="10.10.7008",
    )

    assert result.status == "FAIL"
    assert result.row_count == 0
    assert [(issue.code, issue.detail) for issue in result.issues] == [
        ("PROVIDER_ERROR", "Moomoo historical request failed: permission denied")
    ]
