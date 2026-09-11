from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
import importlib
from importlib import metadata as importlib_metadata
from typing import Any, Literal

import pandas as pd

from investment_tracker.governance import assert_symbol_allowed

from .models import DataRequest
from .validation import REQUIRED_COLUMNS


class MoomooDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class MoomooRawPage:
    page_number: int
    input_page_req_key: bytes | str | None
    output_page_req_key: bytes | str | None
    frame: pd.DataFrame


@dataclass(frozen=True)
class MoomooRawRowLink:
    page_number: int
    row_number: int
    code: str
    raw_time_key: str
    normalized_date: date


@dataclass(frozen=True)
class MoomooFetchEvidence:
    status: Literal["SUCCESS", "ERROR"]
    request: DataRequest
    request_parameters: dict[str, object]
    retrieved_at: datetime
    sdk_version: str | None
    pages: tuple[MoomooRawPage, ...]
    normalized: pd.DataFrame | None
    row_links: tuple[MoomooRawRowLink, ...]
    error: str | None = None
    error_data: object | None = None


@dataclass(frozen=True)
class MoomooCalendarEvidence:
    status: Literal["SUCCESS", "ERROR"]
    request: DataRequest
    request_parameters: dict[str, object]
    retrieved_at: datetime
    sdk_version: str | None
    data: object
    error: str | None = None


@dataclass(frozen=True)
class MoomooPreflightResult:
    sdk_version: str | None
    opend_version: str | None
    quote_logged_in: bool
    program_status: str | None
    program_status_description: str | None
    host: str
    port: int
    retrieved_at: datetime
    raw_state: dict[str, object]


def _default_sdk_loader() -> Any:
    try:
        return importlib.import_module("moomoo")
    except ImportError as exc:
        raise MoomooDataError(
            "moomoo-api is not installed; install the 'moomoo' optional dependency"
        ) from exc


class MoomooHistoricalDataSource:
    """Historical daily-bar source using only Moomoo's quote context."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 11111,
        context_factory: Callable[..., Any] | None = None,
        sdk_loader: Callable[[], Any] = _default_sdk_loader,
    ) -> None:
        self._host = host
        self._port = port
        self._context_factory = context_factory
        self._sdk_loader = sdk_loader

    @staticmethod
    def _sdk_version(sdk: Any) -> str | None:
        version = getattr(sdk, "__version__", None)
        if version is not None:
            return str(version)
        try:
            return importlib_metadata.version("moomoo-api")
        except importlib_metadata.PackageNotFoundError:
            return None

    def _history_parameters(self, sdk: Any, request: DataRequest) -> dict[str, object]:
        return {
            "provider": "MOOMOO",
            "code": f"US.{request.symbol}",
            "start": request.start.isoformat(),
            "end": request.end.isoformat(),
            "ktype": {"name": "K_DAY", "value": str(sdk.KLType.K_DAY)},
            "autype": {"name": "QFQ", "value": str(sdk.AuType.QFQ)},
            "fields": [{"name": "ALL", "value": str(sdk.KL_FIELD.ALL)}],
            "max_count": 1000,
            "extended_time": False,
            "session": {"name": "RTH", "value": str(sdk.Session.RTH)},
            "host": self._host,
            "port": self._port,
        }

    def history_request_parameters(self, request: DataRequest) -> dict[str, object]:
        symbol = assert_symbol_allowed(request.symbol)
        guarded = request.model_copy(update={"symbol": symbol})
        return self._history_parameters(self._sdk_loader(), guarded)

    @staticmethod
    def _normalize_pages(
        pages: list[MoomooRawPage], expected_code: str
    ) -> tuple[pd.DataFrame, tuple[MoomooRawRowLink, ...]]:
        if not pages or all(page.frame.empty for page in pages):
            raise MoomooDataError("Moomoo returned no historical bars")
        combined = pd.concat([page.frame for page in pages], ignore_index=True)
        required_provider_columns = {"code", "time_key", *REQUIRED_COLUMNS}
        missing = sorted(required_provider_columns.difference(combined.columns))
        if missing:
            raise MoomooDataError(f"Moomoo response missing columns: {', '.join(missing)}")
        actual_codes = set(combined["code"].astype(str))
        if actual_codes != {expected_code}:
            raise MoomooDataError(
                f"Moomoo response symbol identity mismatch: expected {expected_code}"
            )

        raw_timestamps = pd.to_datetime(combined["time_key"], errors="raise")
        if raw_timestamps.dt.tz is None:
            eastern_timestamps = raw_timestamps.dt.tz_localize("America/New_York")
        else:
            eastern_timestamps = raw_timestamps.dt.tz_convert("America/New_York")
        normalized_dates = tuple(eastern_timestamps.dt.date)
        timestamps = pd.to_datetime(normalized_dates, utc=True)
        normalized = combined.loc[:, REQUIRED_COLUMNS].copy()
        normalized.index = pd.DatetimeIndex(timestamps, name="timestamp")

        links: list[MoomooRawRowLink] = []
        offset = 0
        for page in pages:
            for row_number, (_, row) in enumerate(page.frame.iterrows()):
                links.append(
                    MoomooRawRowLink(
                        page_number=page.page_number,
                        row_number=row_number,
                        code=str(row.get("code")),
                        raw_time_key=str(row.get("time_key")),
                        normalized_date=normalized_dates[offset],
                    )
                )
                offset += 1
        return normalized, tuple(links)

    def fetch_with_evidence(self, request: DataRequest) -> MoomooFetchEvidence:
        symbol = assert_symbol_allowed(request.symbol)
        guarded = request.model_copy(update={"symbol": symbol})
        retrieved_at = datetime.now(timezone.utc)
        sdk = self._sdk_loader()
        sdk_version = self._sdk_version(sdk)
        parameters = self._history_parameters(sdk, guarded)
        factory = self._context_factory or sdk.OpenQuoteContext
        pages: list[MoomooRawPage] = []
        page_key = None
        seen_keys: set[bytes | str] = set()
        context = None
        try:
            context = factory(host=self._host, port=self._port)
            while True:
                ret, data, next_key = context.request_history_kline(
                    code=f"US.{guarded.symbol}",
                    start=guarded.start.isoformat(),
                    end=guarded.end.isoformat(),
                    ktype=sdk.KLType.K_DAY,
                    autype=sdk.AuType.QFQ,
                    fields=[sdk.KL_FIELD.ALL],
                    max_count=1000,
                    page_req_key=page_key,
                    extended_time=False,
                    session=sdk.Session.RTH,
                )
                if ret != sdk.RET_OK:
                    return MoomooFetchEvidence(
                        status="ERROR",
                        request=guarded,
                        request_parameters=parameters,
                        retrieved_at=retrieved_at,
                        sdk_version=sdk_version,
                        pages=tuple(pages),
                        normalized=None,
                        row_links=(),
                        error=f"Moomoo historical request failed: {data}",
                        error_data=data,
                    )
                if not isinstance(data, pd.DataFrame):
                    raise MoomooDataError("Moomoo historical response is not a DataFrame")
                pages.append(
                    MoomooRawPage(
                        page_number=len(pages) + 1,
                        input_page_req_key=page_key,
                        output_page_req_key=next_key,
                        frame=data.copy(deep=True),
                    )
                )
                if not next_key:
                    break
                identity = next_key if isinstance(next_key, (bytes, str)) else repr(next_key)
                if identity in seen_keys:
                    raise MoomooDataError("Moomoo historical pagination loop detected")
                seen_keys.add(identity)
                page_key = next_key
            normalized, row_links = self._normalize_pages(pages, f"US.{guarded.symbol}")
            return MoomooFetchEvidence(
                status="SUCCESS",
                request=guarded,
                request_parameters=parameters,
                retrieved_at=retrieved_at,
                sdk_version=sdk_version,
                pages=tuple(pages),
                normalized=normalized,
                row_links=row_links,
            )
        except Exception as exc:
            error = str(exc) if isinstance(exc, MoomooDataError) else f"{type(exc).__name__}: {exc}"
            return MoomooFetchEvidence(
                status="ERROR",
                request=guarded,
                request_parameters=parameters,
                retrieved_at=retrieved_at,
                sdk_version=sdk_version,
                pages=tuple(pages),
                normalized=None,
                row_links=(),
                error=error,
                error_data=None,
            )
        finally:
            if context is not None:
                context.close()

    def fetch(self, request: DataRequest) -> tuple[pd.DataFrame, str | None]:
        evidence = self.fetch_with_evidence(request)
        if evidence.status != "SUCCESS" or evidence.normalized is None:
            raise MoomooDataError(evidence.error or "Moomoo historical request failed")
        return evidence.normalized, evidence.sdk_version

    def fetch_calendar_evidence(self, request: DataRequest) -> MoomooCalendarEvidence:
        symbol = assert_symbol_allowed(request.symbol)
        guarded = request.model_copy(update={"symbol": symbol})
        retrieved_at = datetime.now(timezone.utc)
        sdk = self._sdk_loader()
        sdk_version = self._sdk_version(sdk)
        parameters = {
            "provider": "MOOMOO",
            "code": f"US.{guarded.symbol}",
            "start": guarded.start.isoformat(),
            "end": guarded.end.isoformat(),
            "host": self._host,
            "port": self._port,
        }
        factory = self._context_factory or sdk.OpenQuoteContext
        context = None
        try:
            context = factory(host=self._host, port=self._port)
            ret, data = context.request_trading_days(
                code=f"US.{guarded.symbol}",
                start=guarded.start.isoformat(),
                end=guarded.end.isoformat(),
            )
            if ret != sdk.RET_OK:
                return MoomooCalendarEvidence(
                    status="ERROR",
                    request=guarded,
                    request_parameters=parameters,
                    retrieved_at=retrieved_at,
                    sdk_version=sdk_version,
                    data=data,
                    error=f"Moomoo trading-calendar request failed: {data}",
                )
            return MoomooCalendarEvidence(
                status="SUCCESS",
                request=guarded,
                request_parameters=parameters,
                retrieved_at=retrieved_at,
                sdk_version=sdk_version,
                data=data,
            )
        except Exception as exc:
            return MoomooCalendarEvidence(
                status="ERROR",
                request=guarded,
                request_parameters=parameters,
                retrieved_at=retrieved_at,
                sdk_version=sdk_version,
                data=None,
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            if context is not None:
                context.close()

    def preflight(self, symbol: str) -> MoomooPreflightResult:
        assert_symbol_allowed(symbol)
        retrieved_at = datetime.now(timezone.utc)
        sdk = self._sdk_loader()
        factory = self._context_factory or sdk.OpenQuoteContext
        context = None
        try:
            context = factory(host=self._host, port=self._port)
            ret, state = context.get_global_state()
            if ret != sdk.RET_OK:
                raise MoomooDataError(f"Moomoo global-state request failed: {state}")
            if not isinstance(state, dict):
                raise MoomooDataError("Moomoo global-state response is not a mapping")
            quote_logged_in = bool(state.get("qot_logined"))
            program_status = state.get("program_status_type")
            if not quote_logged_in:
                raise MoomooDataError("Moomoo quote service is not authenticated")
            if program_status != "READY":
                raise MoomooDataError(f"OpenD is not ready: {program_status}")
            return MoomooPreflightResult(
                sdk_version=self._sdk_version(sdk),
                opend_version=str(state["server_ver"]) if state.get("server_ver") else None,
                quote_logged_in=quote_logged_in,
                program_status=str(program_status),
                program_status_description=(
                    str(state["program_status_desc"])
                    if state.get("program_status_desc") is not None
                    else None
                ),
                host=self._host,
                port=self._port,
                retrieved_at=retrieved_at,
                raw_state=dict(state),
            )
        finally:
            if context is not None:
                context.close()
