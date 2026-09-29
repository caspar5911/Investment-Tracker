from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from investment_tracker.quant.data.cache import content_hash
from investment_tracker.quant.generation2.research_boundary import (
    RESEARCH_SYMBOLS,
    SymbolDataset,
    build_research_boundary,
    load_research_boundary,
)
from investment_tracker.quant.universe.constants import CAMPAIGN_END, CAMPAIGN_START
from investment_tracker.quant.universe.models import (
    ArtifactIdentity,
    NormalizedDatasetMetadata,
    ProviderRequestRecord,
)

_SHA = "a" * 64


def make_metadata(symbol: str, *, start=CAMPAIGN_START, end=CAMPAIGN_END):
    request = ProviderRequestRecord(
        symbol=symbol,
        code=f"US.{symbol}",
        start=start,
        end=end,
        host="127.0.0.1",
        port=11111,
        ktype="K_DAY",
        autype="QFQ",
        fields=("open", "high", "low", "close", "volume"),
        max_count=1000,
        session="RTH",
    )
    return NormalizedDatasetMetadata(
        symbol=symbol,
        provider_request=request,
        raw_evidence=ArtifactIdentity(
            kind="raw_provider_evidence",
            sha256=_SHA,
            path=f"phase3/raw/moomoo/sha256/{_SHA}/evidence.json",
        ),
        sdk_version=None,
        opend_version=None,
        retrieved_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        row_count=1,
        first_timestamp=datetime(2014, 1, 2, tzinfo=timezone.utc),
        last_timestamp=datetime(2019, 6, 30, tzinfo=timezone.utc),
    )


def make_frame(start: str = "2014-01-02", end: str = "2019-06-30") -> pd.DataFrame:
    index = pd.date_range(start, end, freq="D", tz="UTC")
    close = 100.0 + np.arange(len(index)) * 0.1
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000.0,
        },
        index=index,
    )


def dataset(symbol: str, frame: pd.DataFrame, *, start=CAMPAIGN_START, end=CAMPAIGN_END):
    metadata = make_metadata(symbol, start=start, end=end)
    metadata = metadata.model_copy(
        update={
            "row_count": len(frame),
            "first_timestamp": frame.index[0].tz_convert("UTC").to_pydatetime(),
            "last_timestamp": frame.index[-1].tz_convert("UTC").to_pydatetime(),
        }
    )
    return SymbolDataset(
        symbol=symbol,
        frame=frame,
        metadata=metadata,
        content_sha256=content_hash(frame),
    )


def two_symbol_boundary():
    return build_research_boundary(
        {
            "SPY": dataset("SPY", make_frame()),
            "QQQ": dataset("QQQ", make_frame()),
        },
        expected_symbols=("SPY", "QQQ"),
    )


def test_build_boundary_happy_path_records_provenance() -> None:
    boundary = two_symbol_boundary()
    assert boundary.symbols == ("SPY", "QQQ")
    spy_frame = make_frame()
    assert boundary.content_sha256("SPY") == content_hash(spy_frame)
    record = next(r for r in boundary.provenance.symbols if r.symbol == "SPY")
    assert record.first_date == date(2014, 1, 2)
    assert record.last_date == date(2019, 6, 30)
    assert record.adjustment == "QFQ"


def test_train_bars_excludes_validation_period() -> None:
    boundary = two_symbol_boundary()
    train = boundary.train_bars()
    for frame in train.values():
        assert frame.index.max().normalize().date() <= date(2018, 12, 31)
    validation = boundary.validation_bars()
    for frame in validation.values():
        # Validation retains the full warm-up history (through 2019+).
        assert frame.index.max() > pd.Timestamp("2018-12-31", tz="UTC")


def test_missing_symbol_fails_closed() -> None:
    with pytest.raises(ValueError, match="RESEARCH_BOUNDARY_SYMBOL_MISMATCH"):
        build_research_boundary({"SPY": dataset("SPY", make_frame())}, expected_symbols=("SPY", "QQQ"))


def test_forbidden_expected_symbol_rejected() -> None:
    with pytest.raises(ValueError):
        build_research_boundary(
            {"SPY": dataset("SPY", make_frame())},
            expected_symbols=("SPY", "HACK"),
        )


def test_provided_forbidden_symbol_fails_closed() -> None:
    with pytest.raises(ValueError, match="RESEARCH_BOUNDARY_FORBIDDEN_SYMBOL"):
        build_research_boundary(
            {"HACK": dataset("SPY", make_frame())},
            expected_symbols=("SPY",),
        )


def test_cutoff_exceeded_fails_closed() -> None:
    frame = make_frame(start="2014-01-02", end="2023-01-02")
    with pytest.raises(ValueError, match="RESEARCH_BOUNDARY_CUTOFF_EXCEEDED"):
        build_research_boundary({"SPY": dataset("SPY", frame)}, expected_symbols=("SPY",))


def test_bar_before_fixed_window_fails_closed() -> None:
    frame = make_frame(start="2013-06-01", end="2019-06-30")
    with pytest.raises(ValueError, match="RESEARCH_BOUNDARY_BEFORE_WINDOW"):
        build_research_boundary({"SPY": dataset("SPY", frame)}, expected_symbols=("SPY",))


def test_frame_must_contain_open_and_close() -> None:
    frame = make_frame().drop(columns=["open"])
    metadata = make_metadata("SPY")
    direct = SymbolDataset(
        symbol="SPY",
        frame=frame,
        metadata=metadata,
        content_sha256=_SHA,
    )
    with pytest.raises(ValueError, match="RESEARCH_BOUNDARY_FRAME_COLUMNS_MISSING"):
        build_research_boundary({"SPY": direct}, expected_symbols=("SPY",))


def test_provenance_manifest_is_stable_and_self_hashed() -> None:
    boundary = two_symbol_boundary()
    manifest = boundary.provenance_manifest()
    payload = {k: v for k, v in manifest.items() if k != "provenance_sha256"}
    recomputed = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert recomputed == manifest["provenance_sha256"]
    assert boundary.provenance_manifest() == manifest


def test_default_expected_symbols_are_the_frozen_eight() -> None:
    # The module default is RESEARCH_SYMBOLS (eight allowed research symbols).
    import inspect

    signature = inspect.signature(build_research_boundary)
    default = signature.parameters["expected_symbols"].default
    assert default == RESEARCH_SYMBOLS and len(default) == 8


def test_metadata_window_mismatch_is_unrepresentable_via_model() -> None:
    # The provider request model itself enforces the fixed window, so a
    # mismatched start/end cannot be constructed: the boundary inherits this.
    with pytest.raises(ValidationError):
        make_metadata("SPY", start=date(2015, 1, 1), end=CAMPAIGN_END)


# ---------------------------------------------------------------------------
# Real-cache discovery (load_research_boundary)
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _real_cache() -> Path:
    return _repo_root() / "data" / "cache"


@pytest.mark.skipif(
    not (_real_cache() / "phase3" / "normalized" / "sha256").is_dir(),
    reason="local Phase-3 normalized cache not present",
)
def test_load_research_boundary_from_real_cache() -> None:
    cache = _real_cache()
    boundary = load_research_boundary(cache, cache)

    # Exactly the frozen eight research symbols, content-hash verified.
    assert boundary.symbols == RESEARCH_SYMBOLS and len(boundary.symbols) == 8
    for symbol in boundary.symbols:
        record = next(r for r in boundary.provenance.symbols if r.symbol == symbol)
        assert record.row_count > 0
        assert record.adjustment == "QFQ"
        # Fixed campaign window, first real session 2014-01-02 through 2022-12-30.
        assert record.first_date == date(2014, 1, 2)
        assert record.last_date == date(2022, 12, 30)

    # The TRAIN split really excludes the VALIDATION period.
    train = boundary.train_bars()
    for frame in train.values():
        assert frame.index.max().normalize().date() <= date(2018, 12, 31)
    # ...while VALIDATION retains the full warm-up history.
    for frame in boundary.validation_bars().values():
        assert frame.index.max() > pd.Timestamp("2018-12-31", tz="UTC")

    # Provenance is self-hashed and stable (content-addressed evidence).
    manifest = boundary.provenance_manifest()
    payload = {k: v for k, v in manifest.items() if k != "provenance_sha256"}
    recomputed = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert recomputed == manifest["provenance_sha256"]


@pytest.mark.skipif(
    not (_real_cache() / "phase3" / "normalized" / "sha256").is_dir(),
    reason="local Phase-3 normalized cache not present",
)
def test_load_research_boundary_content_hash_matches_frame() -> None:
    cache = _real_cache()
    boundary = load_research_boundary(cache, cache)
    for symbol, frame in boundary.validation_bars().items():
        assert boundary.content_sha256(symbol) == content_hash(frame)
