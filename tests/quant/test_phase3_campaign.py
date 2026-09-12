from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from investment_tracker.quant.data.models import DataRequest
from investment_tracker.quant.data.moomoo_client import (
    MoomooCalendarEvidence,
    MoomooFetchEvidence,
    MoomooPreflightResult,
    MoomooRawPage,
    MoomooRawRowLink,
)
from investment_tracker.quant.universe.artifacts import Phase3ArtifactStore
from investment_tracker.quant.universe.campaign import run_phase3_campaign
from investment_tracker.quant.universe.constants import (
    CAMPAIGN_END,
    CAMPAIGN_START,
    CANDIDATE_POOL,
    NORMALIZATION_VERSION,
    VALIDATOR_VERSION,
)
from investment_tracker.quant.universe.models import UniverseManifest


NOW = datetime(2026, 9, 12, 4, 0, tzinfo=timezone.utc)


def session_dates() -> tuple[date, ...]:
    sessions = xcals.get_calendar("XNYS").sessions_in_range(CAMPAIGN_START, CAMPAIGN_END)
    return tuple(timestamp.date() for timestamp in sessions)


class FakeQuoteSource:
    def __init__(
        self,
        *,
        provider_failures: set[str] | None = None,
        missing_sessions: dict[str, date] | None = None,
    ) -> None:
        self.provider_failures = provider_failures or set()
        self.missing_sessions = missing_sessions or {}
        self.preflight_calls: list[str] = []
        self.fetch_calls: list[DataRequest] = []
        self.calendar_calls: list[DataRequest] = []
        self._sessions = session_dates()

    def preflight(self, symbol: str) -> MoomooPreflightResult:
        self.preflight_calls.append(symbol)
        return MoomooPreflightResult(
            sdk_version="10.10.7008",
            opend_version="10.10.7008",
            quote_logged_in=True,
            program_status="READY",
            program_status_description="",
            host="127.0.0.1",
            port=11111,
            retrieved_at=NOW,
            raw_state={
                "server_ver": "10.10.7008",
                "qot_logined": True,
                "program_status_type": "READY",
            },
        )

    def history_request_parameters(self, request: DataRequest) -> dict[str, object]:
        return {
            "provider": "MOOMOO",
            "code": f"US.{request.symbol}",
            "start": request.start.isoformat(),
            "end": request.end.isoformat(),
            "ktype": {"name": "K_DAY", "value": "K_DAY"},
            "autype": {"name": "QFQ", "value": "qfq"},
            "fields": [{"name": "ALL", "value": ""}],
            "max_count": 1000,
            "extended_time": False,
            "session": {"name": "RTH", "value": "RTH"},
            "host": "127.0.0.1",
            "port": 11111,
        }

    def fetch_with_evidence(self, request: DataRequest) -> MoomooFetchEvidence:
        self.fetch_calls.append(request)
        dates = [
            day
            for day in self._sessions
            if day != self.missing_sessions.get(request.symbol)
        ]
        if request.symbol in self.provider_failures:
            dates = dates[:1]
        raw = pd.DataFrame(
            {
                "code": [f"US.{request.symbol}"] * len(dates),
                "time_key": [f"{day.isoformat()} 00:00:00" for day in dates],
                "open": [100.0] * len(dates),
                "high": [102.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [101.0] * len(dates),
                "volume": [1_000] * len(dates),
                "turnover": [100_000.0] * len(dates),
            }
        )
        page = MoomooRawPage(1, None, None, raw)
        if request.symbol in self.provider_failures:
            return MoomooFetchEvidence(
                status="ERROR",
                request=request,
                request_parameters=self.history_request_parameters(request),
                retrieved_at=NOW,
                sdk_version="10.10.7008",
                pages=(page,),
                normalized=None,
                row_links=(),
                error="Moomoo historical request failed: fixture provider failure",
                error_data="fixture provider failure",
            )
        normalized = raw.loc[:, ["open", "high", "low", "close", "volume"]].copy()
        normalized.index = pd.DatetimeIndex(dates, tz="UTC", name="timestamp")
        links = tuple(
            MoomooRawRowLink(
                page_number=1,
                row_number=index,
                code=f"US.{request.symbol}",
                raw_time_key=f"{day.isoformat()} 00:00:00",
                normalized_date=day,
            )
            for index, day in enumerate(dates)
        )
        return MoomooFetchEvidence(
            status="SUCCESS",
            request=request,
            request_parameters=self.history_request_parameters(request),
            retrieved_at=NOW,
            sdk_version="10.10.7008",
            pages=(page,),
            normalized=normalized,
            row_links=links,
        )

    def fetch_calendar_evidence(self, request: DataRequest) -> MoomooCalendarEvidence:
        self.calendar_calls.append(request)
        return MoomooCalendarEvidence(
            status="SUCCESS",
            request=request,
            request_parameters={
                "provider": "MOOMOO",
                "code": f"US.{request.symbol}",
                "start": request.start.isoformat(),
                "end": request.end.isoformat(),
                "host": "127.0.0.1",
                "port": 11111,
            },
            retrieved_at=NOW,
            sdk_version="10.10.7008",
            data=[
                {"time": day.isoformat(), "trade_date_type": "WHOLE"}
                for day in self._sessions
            ],
        )


def artifact_store(tmp_path: Path) -> Phase3ArtifactStore:
    return Phase3ArtifactStore(tmp_path / "cache", tmp_path / "results")


def test_campaign_freezes_all_dq_before_mechanical_selection_and_manifest(tmp_path: Path) -> None:
    source = FakeQuoteSource()
    store = artifact_store(tmp_path)

    outcome = run_phase3_campaign(
        source,
        store,
        campaign_id="phase3-clean-test",
        created_at=NOW,
        source_revision="f" * 40,
        dependency_identity="e" * 64,
    )

    assert source.preflight_calls == ["SPY"]
    assert [request.symbol for request in source.fetch_calls] == list(CANDIDATE_POOL)
    assert {
        (request.start.isoformat(), request.end.isoformat()) for request in source.fetch_calls
    } == {("2014-01-01", "2022-12-31")}
    snapshot = store.load_frozen_snapshot(outcome.dq_snapshot)
    assert len(snapshot.candidates) == 16
    assert all(candidate.status == "PASS" for candidate in snapshot.candidates)
    assert outcome.selection.snapshot == outcome.dq_snapshot
    assert outcome.selection.selected_symbols == (
        "SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP"
    )
    assert outcome.stop_reason == "PHASE_3_UNIVERSE_FROZEN"
    assert outcome.universe_manifest is not None

    manifest = UniverseManifest.model_validate(store.read_json(outcome.universe_manifest))
    assert manifest.dq_snapshot == outcome.dq_snapshot
    assert manifest.dq_report == outcome.dq_report
    assert len(manifest.candidates) == 16
    assert len(manifest.raw_evidence) == 16
    assert manifest.selected_symbols == outcome.selection.selected_symbols
    assert manifest.normalization_version == NORMALIZATION_VERSION
    assert manifest.validator_version == VALIDATOR_VERSION
    assert manifest.decision_grade is False
    assert manifest.strategy_performance_used is False
    assert manifest.strategy_backtests_executed == 0
    assert manifest.bars_repaired == 0
    assert manifest.final_holdout_accessed is False
    assert manifest.protected_symbols_accessed == ()
    assert manifest.live_trading_capability is False


def test_failed_provider_and_missing_session_evidence_are_quarantined(tmp_path: Path) -> None:
    missing_date = date(2014, 1, 3)
    source = FakeQuoteSource(
        provider_failures={"IWM"},
        missing_sessions={"VNQ": missing_date},
    )
    store = artifact_store(tmp_path)

    outcome = run_phase3_campaign(
        source,
        store,
        campaign_id="phase3-failures-test",
        created_at=NOW,
        source_revision="f" * 40,
        dependency_identity="e" * 64,
    )

    snapshot = store.load_frozen_snapshot(outcome.dq_snapshot)
    by_symbol = {candidate.symbol: candidate for candidate in snapshot.candidates}
    assert by_symbol["IWM"].status == "FAIL"
    assert by_symbol["IWM"].raw_evidence is not None
    assert by_symbol["IWM"].quarantine is not None
    assert by_symbol["IWM"].normalized_dataset is None
    assert [issue.code for issue in by_symbol["IWM"].issues] == ["PROVIDER_ERROR"]
    assert by_symbol["VNQ"].status == "FAIL"
    assert by_symbol["VNQ"].quarantine is not None
    missing = by_symbol["VNQ"].missing_sessions[0]
    assert missing.session_date == missing_date
    assert missing.raw_time_key is None
    assert missing.preceding is not None
    assert missing.following is not None
    assert missing.calendar.state == "AGREE_OPEN"
    assert missing.calendar.evidence is not None
    assert [request.symbol for request in source.calendar_calls] == ["VNQ"]
    assert len(snapshot.candidates) == 16


def test_verified_candidate_cache_avoids_new_history_and_calendar_calls(tmp_path: Path) -> None:
    store = artifact_store(tmp_path)
    first_source = FakeQuoteSource(missing_sessions={"VNQ": date(2014, 1, 3)})
    run_phase3_campaign(
        first_source,
        store,
        campaign_id="phase3-first",
        created_at=NOW,
        source_revision="f" * 40,
        dependency_identity="e" * 64,
    )
    second_source = FakeQuoteSource(missing_sessions={"VNQ": date(2014, 1, 3)})

    outcome = run_phase3_campaign(
        second_source,
        store,
        campaign_id="phase3-second",
        created_at=NOW,
        source_revision="f" * 40,
        dependency_identity="e" * 64,
    )

    assert second_source.preflight_calls == ["SPY"]
    assert second_source.fetch_calls == []
    assert second_source.calendar_calls == []
    assert len(store.load_frozen_snapshot(outcome.dq_snapshot).candidates) == 16


def test_dq_report_covers_every_candidate_without_strategy_metrics(tmp_path: Path) -> None:
    store = artifact_store(tmp_path)
    outcome = run_phase3_campaign(
        FakeQuoteSource(provider_failures={"XLE"}),
        store,
        campaign_id="phase3-report-test",
        created_at=NOW,
        source_revision="f" * 40,
        dependency_identity="e" * 64,
    )

    report = store.read_text(outcome.dq_report)
    assert all(f"| {symbol} |" in report for symbol in CANDIDATE_POOL)
    assert "PROVIDER_ERROR" in report
    xle_row = next(line for line in report.splitlines() if line.startswith("| XLE |"))
    assert xle_row.endswith("| NOT_SELECTED_DQ_FAIL |")
    assert "## Technical summary" in report
    assert "15 `PASS` and 1 `FAIL`" in report
    assert "## Fixed scope and admission definitions" in report
    assert "## Validation and provenance method" in report
    assert "## Limitations and governed next step" in report
    assert "DQ snapshot SHA-256" in report
    forbidden = ("CAGR", "Sharpe", "Sortino", "Calmar", "drawdown", "strategy score")
    assert all(term not in report for term in forbidden)


def test_below_six_clean_slots_writes_report_but_no_manifest(tmp_path: Path) -> None:
    clean = {"SPY", "QQQ", "TLT", "IEF", "GLD"}
    failures = set(CANDIDATE_POOL).difference(clean)
    store = artifact_store(tmp_path)

    outcome = run_phase3_campaign(
        FakeQuoteSource(provider_failures=failures),
        store,
        campaign_id="phase3-insufficient-test",
        created_at=NOW,
        source_revision="f" * 40,
        dependency_identity="e" * 64,
    )

    assert outcome.stop_reason == "INSUFFICIENT_CLEAN_DIVERSIFIED_UNIVERSE"
    assert outcome.universe_manifest is None
    assert store.resolve(outcome.dq_snapshot).exists()
    assert store.resolve(outcome.dq_report).exists()
