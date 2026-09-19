from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from investment_tracker.quant.universe.constants import (
    CAMPAIGN_END,
    CAMPAIGN_START,
    CANDIDATE_POOL,
    EXPOSURE_SLOTS,
    MAX_UNIVERSE_SIZE,
    MIN_UNIVERSE_SIZE,
    NORMALIZATION_VERSION,
    VALIDATOR_VERSION,
)
from investment_tracker.quant.universe.hashing import canonical_sha256, tag_scalar
from investment_tracker.quant.universe.models import (
    ArtifactIdentity,
    CandidateDQResult,
    DQSnapshot,
    ProviderRequestRecord,
)


def artifact(kind: str) -> ArtifactIdentity:
    return ArtifactIdentity(kind=kind, sha256="a" * 64, path=f"{kind}/{'a' * 64}")


def provider_request(symbol: str) -> ProviderRequestRecord:
    return ProviderRequestRecord(
        symbol=symbol,
        code=f"US.{symbol}",
        start=CAMPAIGN_START,
        end=CAMPAIGN_END,
        host="127.0.0.1",
        port=11111,
        ktype="K_DAY",
        autype="QFQ",
        fields=("ALL",),
        max_count=1000,
        extended_time=False,
        session="RTH",
    )


def candidate(symbol: str, status: str = "PASS") -> CandidateDQResult:
    issues = () if status == "PASS" else ({"code": "PROVIDER_ERROR", "detail": "failed"},)
    return CandidateDQResult(
        symbol=symbol,
        status=status,
        row_count=2264 if status == "PASS" else 0,
        provider_request=provider_request(symbol),
        raw_evidence=artifact("raw"),
        normalized_dataset=artifact("normalized") if status == "PASS" else None,
        quarantine=artifact("quarantine") if status == "FAIL" else None,
        issues=issues,
        missing_sessions=(),
        unexpected_sessions=(),
        sdk_version="10.10.7008",
        opend_version="10.10.7008",
        normalization_version=NORMALIZATION_VERSION,
        validator_version=VALIDATOR_VERSION,
        retrieved_at=datetime(2026, 9, 12, tzinfo=timezone.utc),
    )


def test_phase3_contracts_freeze_window_pool_limits_and_slot_order() -> None:
    assert (CAMPAIGN_START, CAMPAIGN_END) == (date(2014, 1, 1), date(2022, 12, 31))
    assert CANDIDATE_POOL == (
        "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV",
        "XLI", "XLP", "XLY", "XLU", "VNQ", "TLT", "IEF", "GLD",
    )
    assert MIN_UNIVERSE_SIZE == 6
    assert MAX_UNIVERSE_SIZE == 8
    assert [(slot.name, slot.candidates) for slot in EXPOSURE_SLOTS] == [
        ("BROAD_US_EQUITY", ("SPY", "DIA")),
        ("GROWTH_TECHNOLOGY", ("QQQ", "XLK")),
        ("SMALL_CAP", ("IWM",)),
        ("LONG_TREASURY", ("TLT",)),
        ("INTERMEDIATE_TREASURY", ("IEF",)),
        ("GOLD", ("GLD",)),
        ("REAL_ESTATE", ("VNQ",)),
        ("DEFENSIVE_EQUITY", ("XLP", "XLV", "XLU")),
        ("CYCLICAL_EQUITY", ("XLI", "XLF", "XLE", "XLY")),
    ]


def test_canonical_hash_is_order_independent_and_matches_literal_fixture() -> None:
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})
    assert canonical_sha256({"a": 1, "b": 2}) == (
        "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )


def test_tag_scalar_preserves_values_that_plain_json_would_conflate() -> None:
    assert tag_scalar(None) == {"type": "null", "value": None}
    assert tag_scalar(True) == {"type": "bool", "value": True}
    assert tag_scalar(7) == {"type": "int", "value": "7"}
    assert tag_scalar(1.25) == {"type": "float", "value": "1.25"}
    assert tag_scalar(float("nan")) == {"type": "float", "value": "nan"}
    assert tag_scalar(float("inf")) == {"type": "float", "value": "inf"}
    assert tag_scalar(b"next") == {"type": "bytes", "value": "6e657874"}
    assert tag_scalar("US.SPY") == {"type": "str", "value": "US.SPY"}


def test_dq_snapshot_requires_exact_complete_candidate_pool() -> None:
    payload = {
        "campaign_id": "phase3-test",
        "window_start": CAMPAIGN_START,
        "window_end": CAMPAIGN_END,
        "candidate_pool": CANDIDATE_POOL,
        "candidates": tuple(candidate(symbol) for symbol in CANDIDATE_POOL[:-1]),
        "created_at": datetime(2026, 9, 12, tzinfo=timezone.utc),
    }
    with pytest.raises(ValidationError, match="exactly one DQ result"):
        DQSnapshot(**payload)

    complete = DQSnapshot(
        **{**payload, "candidates": tuple(candidate(symbol) for symbol in CANDIDATE_POOL)}
    )
    assert len(complete.candidates) == 16


def test_phase3_models_reject_strategy_performance_fields() -> None:
    payload = candidate("SPY").model_dump(mode="json")
    payload["sharpe"] = 1.0
    with pytest.raises(ValidationError, match="sharpe"):
        CandidateDQResult.model_validate(payload)


@pytest.mark.parametrize(
    ("symbol", "code"),
    [("HACK", "US.HACK"), ("SPY", "US.QQQ"), ("SPY", "SPY")],
)
def test_provider_request_rejects_locked_or_mismatched_codes(symbol: str, code: str) -> None:
    payload = provider_request("SPY").model_dump()
    payload.update(symbol=symbol, code=code)
    with pytest.raises((ValidationError, ValueError)):
        ProviderRequestRecord.model_validate(payload)
