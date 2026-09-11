from __future__ import annotations

from collections.abc import Callable
import importlib
from importlib import metadata as importlib_metadata
from typing import Any

import pandas as pd

from investment_tracker.governance import assert_symbol_allowed

from .models import DataRequest
from .validation import REQUIRED_COLUMNS


class MoomooDataError(RuntimeError):
    pass


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

    def fetch(self, request: DataRequest) -> tuple[pd.DataFrame, str | None]:
        symbol = assert_symbol_allowed(request.symbol)
        guarded = request.model_copy(update={"symbol": symbol})
        sdk = self._sdk_loader()
        factory = self._context_factory or sdk.OpenQuoteContext
        context = factory(host=self._host, port=self._port)
        pages: list[pd.DataFrame] = []
        page_key = None
        seen_keys: set[bytes | str] = set()
        try:
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
                    raise MoomooDataError(f"Moomoo historical request failed: {data}")
                if not isinstance(data, pd.DataFrame):
                    raise MoomooDataError("Moomoo historical response is not a DataFrame")
                pages.append(data.copy(deep=True))
                if not next_key:
                    break
                identity = next_key if isinstance(next_key, (bytes, str)) else repr(next_key)
                if identity in seen_keys:
                    raise MoomooDataError("Moomoo historical pagination loop detected")
                seen_keys.add(identity)
                page_key = next_key
        finally:
            context.close()

        if not pages or all(page.empty for page in pages):
            raise MoomooDataError("Moomoo returned no historical bars")
        combined = pd.concat(pages, ignore_index=True)
        required_provider_columns = {"time_key", *REQUIRED_COLUMNS}
        missing = sorted(required_provider_columns.difference(combined.columns))
        if missing:
            raise MoomooDataError(f"Moomoo response missing columns: {', '.join(missing)}")

        timestamps = pd.to_datetime(combined["time_key"], errors="raise")
        if timestamps.dt.tz is None:
            timestamps = timestamps.dt.normalize().dt.tz_localize("UTC")
        else:
            timestamps = timestamps.dt.tz_convert("UTC").dt.normalize()
        normalized = combined.loc[:, REQUIRED_COLUMNS].copy()
        normalized.index = pd.DatetimeIndex(timestamps, name="timestamp")

        version = getattr(sdk, "__version__", None)
        if version is None:
            try:
                version = importlib_metadata.version("moomoo-api")
            except importlib_metadata.PackageNotFoundError:
                version = None
        return normalized, version
