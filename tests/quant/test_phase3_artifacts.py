from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from investment_tracker.governance import LockedHoldoutError
from investment_tracker.quant.data.models import DataRequest
from investment_tracker.quant.data.moomoo_client import (
    MoomooFetchEvidence,
    MoomooRawPage,
    MoomooRawRowLink,
)
from investment_tracker.quant.universe.artifacts import (
    ArtifactIntegrityError,
    Phase3ArtifactStore,
)
from investment_tracker.quant.universe.constants import (
    CAMPAIGN_END,
    CAMPAIGN_START,
    CANDIDATE_POOL,
    NORMALIZATION_VERSION,
    VALIDATOR_VERSION,
)
from investment_tracker.quant.universe.models import (
    CandidateDQResult,
    DQSnapshot,
    NormalizedDatasetMetadata,
    ProviderRequestRecord,
)


NOW = datetime(2026, 9, 12, 1, 2, 3, tzinfo=timezone.utc)


def request(symbol: str = "SPY", end: date = CAMPAIGN_END) -> DataRequest:
    return DataRequest(symbol=symbol, start=CAMPAIGN_START, end=end)


def provider_request(symbol: str = "SPY") -> ProviderRequestRecord:
    return ProviderRequestRecord(
        symbol=symbol,
        code=f"US.{symbol}",
        start=CAMPAIGN_START,
        end=CAMPAIGN_END,
        host="127.0.0.1",
        port=11111,
        ktype="K_DAY",
        autype="qfq",
        fields=("",),
        max_count=1000,
        extended_time=False,
        session="RTH",
    )


def raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "code": "US.SPY",
                "time_key": "2014-01-02 00:00:00",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 1_000,
                "turnover": 100_000.0,
                "pe_ratio": float("nan"),
            },
            {
                "code": "US.SPY",
                "time_key": "2014-01-03 00:00:00",
                "open": 101.0,
                "high": 103.0,
                "low": 100.0,
                "close": 102.0,
                "volume": 1_100,
                "turnover": 110_000.0,
                "pe_ratio": 20.5,
            },
        ]
    )


def normalized_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1_000, 1_100],
        },
        index=pd.DatetimeIndex(["2014-01-02", "2014-01-03"], tz="UTC", name="timestamp"),
    )


def fetch_evidence() -> MoomooFetchEvidence:
    frame = raw_frame()
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
        pages=(
            MoomooRawPage(1, None, b"next", frame.iloc[[0]].copy()),
            MoomooRawPage(2, b"next", None, frame.iloc[[1]].copy()),
        ),
        normalized=normalized_frame(),
        row_links=(
            MoomooRawRowLink(1, 0, "US.SPY", "2014-01-02 00:00:00", date(2014, 1, 2)),
            MoomooRawRowLink(2, 0, "US.SPY", "2014-01-03 00:00:00", date(2014, 1, 3)),
        ),
    )


def store(tmp_path: Path) -> Phase3ArtifactStore:
    return Phase3ArtifactStore(tmp_path / "cache", tmp_path / "results")


def test_raw_artifact_preserves_typed_fields_and_page_provenance(tmp_path: Path) -> None:
    artifacts = store(tmp_path)

    identity = artifacts.write_raw_evidence(fetch_evidence(), opend_version="10.10.7008")
    payload = artifacts.read_json(identity)

    assert identity.kind == "raw_provider_evidence"
    assert identity.sha256 in identity.path
    assert len(payload["pages"]) == 2
    assert payload["pages"][0]["input_page_req_key"] == {"type": "null", "value": None}
    assert payload["pages"][0]["output_page_req_key"] == {
        "type": "bytes",
        "value": "6e657874",
    }
    columns = payload["pages"][0]["columns"]
    first_row = dict(zip(columns, payload["pages"][0]["rows"][0], strict=True))
    assert first_row["code"] == {"type": "str", "value": "US.SPY"}
    assert first_row["time_key"] == {
        "type": "str",
        "value": "2014-01-02 00:00:00",
    }
    assert first_row["volume"] == {"type": "int", "value": "1000"}
    assert first_row["pe_ratio"] == {"type": "float", "value": "nan"}
    assert payload["sdk_version"] == "10.10.7008"
    assert payload["opend_version"] == "10.10.7008"


def test_identical_raw_content_reuses_identity_and_tampering_fails(tmp_path: Path) -> None:
    artifacts = store(tmp_path)
    first = artifacts.write_raw_evidence(fetch_evidence(), opend_version="10.10.7008")
    second = artifacts.write_raw_evidence(fetch_evidence(), opend_version="10.10.7008")
    assert first == second

    path = artifacts.resolve(first)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ArtifactIntegrityError, match="hash mismatch"):
        artifacts.read_json(first)
    with pytest.raises(ArtifactIntegrityError, match="immutable artifact collision"):
        artifacts.write_raw_evidence(fetch_evidence(), opend_version="10.10.7008")


def test_normalized_parquet_round_trips_and_detects_tampering(tmp_path: Path) -> None:
    artifacts = store(tmp_path)
    raw_identity = artifacts.write_raw_evidence(fetch_evidence(), "10.10.7008")
    metadata = NormalizedDatasetMetadata(
        symbol="SPY",
        provider_request=provider_request(),
        raw_evidence=raw_identity,
        sdk_version="10.10.7008",
        opend_version="10.10.7008",
        retrieved_at=NOW,
        row_count=2,
        first_timestamp=datetime(2014, 1, 2, tzinfo=timezone.utc),
        last_timestamp=datetime(2014, 1, 3, tzinfo=timezone.utc),
    )

    identity = artifacts.write_normalized_dataset(normalized_frame(), metadata)
    loaded, loaded_metadata = artifacts.load_normalized_dataset(identity)

    pd.testing.assert_frame_equal(loaded, normalized_frame(), check_dtype=False)
    assert loaded_metadata == metadata
    assert identity.kind == "normalized_dataset"

    artifacts.resolve(identity).joinpath("bars.parquet").write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError, match="normalized dataset unreadable"):
        artifacts.load_normalized_dataset(identity)


def test_quarantine_and_snapshot_are_content_addressed_and_write_once(tmp_path: Path) -> None:
    artifacts = store(tmp_path)
    raw_identity = artifacts.write_raw_evidence(fetch_evidence(), "10.10.7008")
    quarantine_payload = {
        "schema_version": "PHASE3-QUARANTINE-v1",
        "symbol": "SPY",
        "raw_evidence": raw_identity.model_dump(mode="json"),
        "issues": [{"code": "MISSING_SESSION", "detail": "2014-01-03"}],
    }
    first = artifacts.write_quarantine(quarantine_payload)
    second = artifacts.write_quarantine(quarantine_payload)
    assert first == second

    candidates = []
    for symbol in CANDIDATE_POOL:
        candidates.append(
            CandidateDQResult(
                symbol=symbol,
                status="FAIL",
                row_count=0,
                provider_request=provider_request(symbol),
                raw_evidence=raw_identity,
                normalized_dataset=None,
                quarantine=first,
                issues=({"code": "PROVIDER_ERROR", "detail": "fixture"},),
                missing_sessions=(),
                unexpected_sessions=(),
                sdk_version="10.10.7008",
                opend_version="10.10.7008",
                retrieved_at=NOW,
            )
        )
    snapshot = DQSnapshot(
        campaign_id="phase3-test",
        window_start=CAMPAIGN_START,
        window_end=CAMPAIGN_END,
        candidate_pool=CANDIDATE_POOL,
        candidates=tuple(candidates),
        created_at=NOW,
    )
    frozen = artifacts.freeze_dq_snapshot(snapshot)
    assert artifacts.load_frozen_snapshot(frozen) == snapshot

    artifacts.resolve(frozen).write_text("{}", encoding="utf-8")
    with pytest.raises(ArtifactIntegrityError, match="hash mismatch"):
        artifacts.load_frozen_snapshot(frozen)


def test_candidate_cache_requires_exact_request_and_versions(tmp_path: Path) -> None:
    artifacts = store(tmp_path)
    raw_identity = artifacts.write_raw_evidence(fetch_evidence(), "10.10.7008")
    normalized_identity = artifacts.write_normalized_dataset(
        normalized_frame(),
        NormalizedDatasetMetadata(
            symbol="SPY",
            provider_request=provider_request(),
            raw_evidence=raw_identity,
            sdk_version="10.10.7008",
            opend_version="10.10.7008",
            retrieved_at=NOW,
            row_count=2,
            first_timestamp=datetime(2014, 1, 2, tzinfo=timezone.utc),
            last_timestamp=datetime(2014, 1, 3, tzinfo=timezone.utc),
        ),
    )
    result = CandidateDQResult(
        symbol="SPY",
        status="PASS",
        row_count=2,
        provider_request=provider_request(),
        raw_evidence=raw_identity,
        normalized_dataset=normalized_identity,
        issues=(),
        missing_sessions=(),
        unexpected_sessions=(),
        sdk_version="10.10.7008",
        opend_version="10.10.7008",
        retrieved_at=NOW,
    )
    artifacts.write_candidate_record(result)

    assert artifacts.find_candidate_record(
        "SPY", provider_request(), sdk_version="10.10.7008", opend_version="10.10.7008"
    ) == result
    assert artifacts.find_candidate_record(
        "SPY", provider_request(), sdk_version="10.9", opend_version="10.10.7008"
    ) is None
    assert artifacts.find_candidate_record(
        "SPY", provider_request(), sdk_version="10.10.7008", opend_version="10.9"
    ) is None


def test_locked_symbol_is_denied_before_candidate_cache_filesystem_access(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied"
    occupied.write_text("not a directory", encoding="utf-8")
    artifacts = Phase3ArtifactStore(occupied, occupied)

    with pytest.raises(LockedHoldoutError):
        artifacts.find_candidate_record(
            "HACK",
            provider_request(),
            sdk_version="10.10.7008",
            opend_version="10.10.7008",
        )
