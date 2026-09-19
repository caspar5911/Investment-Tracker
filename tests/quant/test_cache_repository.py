from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from investment_tracker.governance import LockedHoldoutError
from investment_tracker.quant.data.cache import (
    CacheIntegrityError,
    ImmutableParquetCache,
    content_hash,
)
from investment_tracker.quant.data.models import DataRequest
from investment_tracker.quant.data.repository import HistoricalDataRepository
from investment_tracker.quant.data.validation import BarDataValidator, DataQualityError


def request(symbol: str = "SPY") -> DataRequest:
    return DataRequest(
        provider="MOOMOO",
        symbol=symbol,
        interval="1d",
        adjustment="QFQ",
        start=date(2024, 7, 3),
        end=date(2024, 7, 5),
    )


def frame(close_offset: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0 + close_offset, 102.0],
            "volume": [1000, 1100],
        },
        index=pd.DatetimeIndex(["2024-07-03", "2024-07-05"], tz="UTC", name="timestamp"),
    )


class ExplodingCache:
    def find(self, req):
        raise AssertionError("cache accessed")


def test_repository_denies_locked_symbol_before_cache_or_provider() -> None:
    provider_calls = 0

    def provider_factory():
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider created")

    repo = HistoricalDataRepository(
        cache=ExplodingCache(),
        provider_factory=provider_factory,
        validator=BarDataValidator("XNYS"),
    )
    with pytest.raises(LockedHoldoutError):
        repo.load(request("HACK"))
    assert provider_calls == 0


def test_cache_denies_locked_symbol_before_filesystem_access(tmp_path: Path) -> None:
    invalid_root = tmp_path / "not-a-directory"
    invalid_root.write_text("occupied", encoding="utf-8")
    cache = ImmutableParquetCache(invalid_root)
    with pytest.raises(LockedHoldoutError):
        cache.find(request("SOXX"))


def test_content_hash_is_stable_and_changes_with_content() -> None:
    first = frame()
    assert content_hash(first) == content_hash(first.copy(deep=True))
    assert content_hash(first) != content_hash(frame(close_offset=0.25))


def test_clean_dataset_is_admitted_atomically_with_sidecar(tmp_path: Path) -> None:
    cache = ImmutableParquetCache(tmp_path)
    req = request()
    bars = frame()
    report = BarDataValidator("XNYS").validate(bars, req)
    admitted = cache.admit(
        req,
        bars,
        report,
        provider_api_version="10.10",
        retrieved_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )
    assert admitted.data_path.name == "bars.parquet"
    assert admitted.metadata_path.name == "metadata.json"
    assert admitted.metadata.content_hash == content_hash(bars)
    assert admitted.metadata.row_count == 2
    assert list(tmp_path.rglob(".tmp-*")) == []


def test_equivalent_refresh_reuses_existing_immutable_version(tmp_path: Path) -> None:
    cache = ImmutableParquetCache(tmp_path)
    req = request()
    bars = frame()
    report = BarDataValidator("XNYS").validate(bars, req)
    first = cache.admit(req, bars, report, "10.10", datetime(2026, 9, 11, tzinfo=timezone.utc))
    second = cache.admit(req, bars.copy(), report, "10.10", datetime(2026, 9, 12, tzinfo=timezone.utc))
    assert first.dataset_path == second.dataset_path


def test_different_refresh_creates_new_immutable_version(tmp_path: Path) -> None:
    cache = ImmutableParquetCache(tmp_path)
    req = request()
    validator = BarDataValidator("XNYS")
    first_bars = frame()
    second_bars = frame(close_offset=0.25)
    first = cache.admit(req, first_bars, validator.validate(first_bars, req), "10.10", datetime(2026, 9, 11, tzinfo=timezone.utc))
    second = cache.admit(req, second_bars, validator.validate(second_bars, req), "10.10", datetime(2026, 9, 12, tzinfo=timezone.utc))
    assert first.dataset_path != second.dataset_path
    assert first.metadata.content_hash != second.metadata.content_hash
    assert first.dataset_path.exists()
    assert second.dataset_path.exists()


def test_materially_invalid_data_is_quarantined_not_admitted(tmp_path: Path) -> None:
    cache = ImmutableParquetCache(tmp_path)
    req = request()
    broken = frame()
    broken.loc[broken.index[0], "close"] = -1.0
    report = BarDataValidator("XNYS").validate(broken, req)
    with pytest.raises(DataQualityError):
        cache.admit(req, broken, report, "10.10", datetime(2026, 9, 11, tzinfo=timezone.utc))
    assert len(list((tmp_path / "quarantine").glob("*.json"))) == 1
    assert list(tmp_path.rglob("bars.parquet")) == []


def test_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    cache = ImmutableParquetCache(tmp_path)
    req = request()
    bars = frame()
    report = BarDataValidator("XNYS").validate(bars, req)
    admitted = cache.admit(req, bars, report, "10.10", datetime(2026, 9, 11, tzinfo=timezone.utc))
    tampered = pd.read_parquet(admitted.data_path)
    tampered.loc[tampered.index[0], "close"] = 999.0
    tampered.to_parquet(admitted.data_path)
    with pytest.raises(CacheIntegrityError, match="content hash mismatch"):
        cache.find(req)


def test_repository_uses_cache_before_creating_provider(tmp_path: Path) -> None:
    cache = ImmutableParquetCache(tmp_path)
    req = request()
    bars = frame()
    report = BarDataValidator("XNYS").validate(bars, req)
    cached = cache.admit(req, bars, report, "10.10", datetime(2026, 9, 11, tzinfo=timezone.utc))

    def provider_factory():
        raise AssertionError("provider should not be created on cache hit")

    repo = HistoricalDataRepository(cache, provider_factory, BarDataValidator("XNYS"))
    assert repo.load(req).dataset_path == cached.dataset_path
