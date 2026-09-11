from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import pandas as pd

from investment_tracker.governance import assert_symbol_allowed

from .cache import CachedDataset, ImmutableParquetCache
from .models import DataRequest
from .validation import BarDataValidator


class HistoricalDataSource(Protocol):
    def fetch(self, request: DataRequest) -> tuple[pd.DataFrame, str | None]: ...


class HistoricalDataRepository:
    def __init__(
        self,
        cache: ImmutableParquetCache,
        provider_factory: Callable[[], HistoricalDataSource],
        validator: BarDataValidator,
    ) -> None:
        self._cache = cache
        self._provider_factory = provider_factory
        self._validator = validator

    def load(self, request: DataRequest, *, refresh: bool = False) -> CachedDataset:
        symbol = assert_symbol_allowed(request.symbol)
        guarded = request.model_copy(update={"symbol": symbol})
        if not refresh:
            cached = self._cache.find(guarded)
            if cached is not None:
                return cached
        provider = self._provider_factory()
        frame, provider_version = provider.fetch(guarded)
        report = self._validator.validate(frame, guarded)
        return self._cache.admit(guarded, frame, report, provider_version)
