from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from investment_tracker.governance import assert_symbol_allowed

from .constants import (
    CALENDAR_SOURCE_VERSION,
    CAMPAIGN_END,
    CAMPAIGN_SPEC_VERSION,
    CAMPAIGN_START,
    CANDIDATE_POOL,
    DQ_SNAPSHOT_SCHEMA_VERSION,
    NORMALIZATION_VERSION,
    PROVIDER_REQUEST_SCHEMA_VERSION,
    VALIDATOR_VERSION,
    NORMALIZED_DATASET_SCHEMA_VERSION,
)


class FrozenPhase3Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactIdentity(FrozenPhase3Model):
    kind: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str = Field(min_length=1)


class ProviderRequestRecord(FrozenPhase3Model):
    schema_version: Literal["MOOMOO-HISTORY-REQUEST-v1"] = PROVIDER_REQUEST_SCHEMA_VERSION
    provider: Literal["MOOMOO"] = "MOOMOO"
    symbol: str
    code: str
    start: date
    end: date
    interval: Literal["1d"] = "1d"
    adjustment: Literal["QFQ"] = "QFQ"
    host: str = Field(min_length=1)
    port: int = Field(gt=0, le=65535)
    ktype: str
    autype: str
    fields: tuple[str, ...] = Field(min_length=1)
    max_count: int = Field(gt=0, le=1000)
    extended_time: Literal[False] = False
    session: str

    @model_validator(mode="after")
    def validate_fixed_request(self) -> "ProviderRequestRecord":
        symbol = assert_symbol_allowed(self.symbol)
        if symbol != self.symbol:
            raise ValueError("symbol must already be normalized")
        if self.code != f"US.{symbol}":
            raise ValueError("provider code must exactly match US.<symbol>")
        if (self.start, self.end) != (CAMPAIGN_START, CAMPAIGN_END):
            raise ValueError("Phase 3 provider request must use the fixed 2014-2022 window")
        if self.ktype.upper() != "K_DAY":
            raise ValueError("Phase 3 provider request must use KLType.K_DAY")
        if self.autype.upper() != "QFQ":
            raise ValueError("Phase 3 provider request must use AuType.QFQ")
        if self.session.upper() != "RTH":
            raise ValueError("Phase 3 provider request must use the regular US session")
        return self


class DataQualityIssueRecord(FrozenPhase3Model):
    code: str = Field(min_length=1)
    detail: str


class RawRowReference(FrozenPhase3Model):
    raw_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_number: int = Field(ge=1)
    row_number: int = Field(ge=0)
    code: str
    raw_time_key: str
    normalized_date: date


class CalendarDiagnostic(FrozenPhase3Model):
    state: Literal["AGREE_OPEN", "AGREE_CLOSED", "DISAGREE", "UNAVAILABLE"]
    evidence: ArtifactIdentity | None = None
    provider_open_dates: tuple[date, ...] = ()
    error: str | None = None


class SessionDiagnostic(FrozenPhase3Model):
    classification: Literal["MISSING_SESSION", "UNEXPECTED_SESSION"]
    session_date: date
    xnys_expected_open: bool
    raw_time_key: str | None
    normalized_date: date | None
    preceding: RawRowReference | None = None
    following: RawRowReference | None = None
    calendar: CalendarDiagnostic
    cause: Literal["UNKNOWN"] = "UNKNOWN"

    @model_validator(mode="after")
    def validate_timestamp_evidence(self) -> "SessionDiagnostic":
        if self.classification == "MISSING_SESSION" and self.raw_time_key is not None:
            raise ValueError("MISSING_SESSION raw_time_key must be null")
        if self.classification == "UNEXPECTED_SESSION" and self.raw_time_key is None:
            raise ValueError("UNEXPECTED_SESSION raw_time_key must be exact")
        return self


class CandidateDQResult(FrozenPhase3Model):
    schema_version: Literal["PHASE3-CANDIDATE-DQ-v1"] = "PHASE3-CANDIDATE-DQ-v1"
    symbol: str
    status: Literal["PASS", "FAIL"]
    row_count: int = Field(ge=0)
    provider_request: ProviderRequestRecord
    raw_evidence: ArtifactIdentity
    normalized_dataset: ArtifactIdentity | None
    quarantine: ArtifactIdentity | None = None
    issues: tuple[DataQualityIssueRecord, ...]
    missing_sessions: tuple[SessionDiagnostic, ...]
    unexpected_sessions: tuple[SessionDiagnostic, ...]
    sdk_version: str | None
    opend_version: str | None
    normalization_version: Literal["MOOMOO-US-DAILY-EASTERN-DATE-UTC-v1"] = NORMALIZATION_VERSION
    validator_version: Literal["XNYS-OHLCV-DQ-v1"] = VALIDATOR_VERSION
    calendar_source_version: Literal["exchange_calendars-XNYS-v1"] = CALENDAR_SOURCE_VERSION
    retrieved_at: datetime

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        symbol = assert_symbol_allowed(value)
        if symbol not in CANDIDATE_POOL:
            raise ValueError("symbol is not in the Phase 3 candidate pool")
        return symbol

    @model_validator(mode="after")
    def validate_disposition(self) -> "CandidateDQResult":
        if self.provider_request.symbol != self.symbol:
            raise ValueError("candidate and provider request symbols differ")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        if self.status == "PASS":
            if self.issues:
                raise ValueError("PASS candidate cannot contain DQ issues")
            if self.normalized_dataset is None:
                raise ValueError("PASS candidate requires a normalized dataset")
            if self.quarantine is not None:
                raise ValueError("PASS candidate cannot be quarantined")
        else:
            if not self.issues:
                raise ValueError("FAIL candidate requires at least one DQ issue")
            if self.quarantine is None:
                raise ValueError("FAIL candidate requires a quarantine artifact")
        return self


class NormalizedDatasetMetadata(FrozenPhase3Model):
    schema_version: Literal["PHASE3-NORMALIZED-DATASET-v1"] = (
        NORMALIZED_DATASET_SCHEMA_VERSION
    )
    symbol: str
    provider_request: ProviderRequestRecord
    raw_evidence: ArtifactIdentity
    sdk_version: str | None
    opend_version: str | None
    normalization_version: Literal["MOOMOO-US-DAILY-EASTERN-DATE-UTC-v1"] = (
        NORMALIZATION_VERSION
    )
    retrieved_at: datetime
    row_count: int = Field(gt=0)
    first_timestamp: datetime
    last_timestamp: datetime

    @model_validator(mode="after")
    def validate_metadata(self) -> "NormalizedDatasetMetadata":
        symbol = assert_symbol_allowed(self.symbol)
        if symbol not in CANDIDATE_POOL or symbol != self.provider_request.symbol:
            raise ValueError("normalized dataset symbol identity mismatch")
        if self.raw_evidence.kind != "raw_provider_evidence":
            raise ValueError("normalized dataset must reference raw provider evidence")
        for field_name in ("retrieved_at", "first_timestamp", "last_timestamp"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if self.last_timestamp < self.first_timestamp:
            raise ValueError("normalized dataset timestamps must be ordered")
        return self


class DQSnapshot(FrozenPhase3Model):
    schema_version: Literal["PHASE3-DQ-SNAPSHOT-v1"] = DQ_SNAPSHOT_SCHEMA_VERSION
    campaign_spec_version: Literal["PHASE3-ETF-DQ-SPEC-v1"] = CAMPAIGN_SPEC_VERSION
    campaign_id: str = Field(min_length=1)
    window_start: date
    window_end: date
    candidate_pool: tuple[str, ...]
    candidates: tuple[CandidateDQResult, ...]
    created_at: datetime

    @model_validator(mode="after")
    def validate_complete_snapshot(self) -> "DQSnapshot":
        if (self.window_start, self.window_end) != (CAMPAIGN_START, CAMPAIGN_END):
            raise ValueError("DQ snapshot must use the fixed 2014-2022 window")
        if self.candidate_pool != CANDIDATE_POOL:
            raise ValueError("DQ snapshot candidate pool must match the frozen candidate pool")
        symbols = tuple(candidate.symbol for candidate in self.candidates)
        if len(symbols) != len(CANDIDATE_POOL) or set(symbols) != set(CANDIDATE_POOL):
            raise ValueError("DQ snapshot requires exactly one DQ result for every candidate")
        if len(symbols) != len(set(symbols)):
            raise ValueError("DQ snapshot candidate results must be unique")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return self
