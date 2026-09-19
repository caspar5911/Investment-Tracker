from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from investment_tracker.governance import assert_symbol_allowed

from .constants import (
    CALENDAR_SOURCE_VERSION,
    CAMPAIGN_END,
    CAMPAIGN_SPEC_VERSION,
    CAMPAIGN_START,
    CANDIDATE_POOL,
    DQ_SNAPSHOT_SCHEMA_VERSION,
    NORMALIZED_DATASET_SCHEMA_VERSION,
    NORMALIZATION_VERSION,
    PROVIDER_REQUEST_SCHEMA_VERSION,
    SELECTION_POLICY_VERSION,
    UNIVERSE_MANIFEST_SCHEMA_VERSION,
    VALIDATOR_VERSION,
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
    provider_reported_open: bool | None = None
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


class CandidateDQAssessment(FrozenPhase3Model):
    schema_version: Literal["PHASE3-CANDIDATE-ASSESSMENT-v1"] = (
        "PHASE3-CANDIDATE-ASSESSMENT-v1"
    )
    symbol: str
    status: Literal["PASS", "FAIL"]
    row_count: int = Field(ge=0)
    provider_request: ProviderRequestRecord
    raw_evidence: ArtifactIdentity
    normalized_dataset: ArtifactIdentity | None
    issues: tuple[DataQualityIssueRecord, ...]
    missing_sessions: tuple[SessionDiagnostic, ...]
    unexpected_sessions: tuple[SessionDiagnostic, ...]
    sdk_version: str | None
    opend_version: str | None
    normalization_version: Literal["MOOMOO-US-DAILY-EASTERN-DATE-UTC-v1"] = (
        NORMALIZATION_VERSION
    )
    validator_version: Literal["XNYS-OHLCV-DQ-v1"] = VALIDATOR_VERSION
    calendar_source_version: Literal["exchange_calendars-XNYS-v1"] = (
        CALENDAR_SOURCE_VERSION
    )
    retrieved_at: datetime

    def finalize(self, quarantine: ArtifactIdentity | None) -> CandidateDQResult:
        if self.status == "FAIL" and quarantine is None:
            raise ValueError("failed DQ assessment requires a quarantine artifact")
        return CandidateDQResult(
            symbol=self.symbol,
            status=self.status,
            row_count=self.row_count,
            provider_request=self.provider_request,
            raw_evidence=self.raw_evidence,
            normalized_dataset=self.normalized_dataset,
            quarantine=quarantine,
            issues=self.issues,
            missing_sessions=self.missing_sessions,
            unexpected_sessions=self.unexpected_sessions,
            sdk_version=self.sdk_version,
            opend_version=self.opend_version,
            normalization_version=self.normalization_version,
            validator_version=self.validator_version,
            calendar_source_version=self.calendar_source_version,
            retrieved_at=self.retrieved_at,
        )


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


class SelectionCandidateStatus(FrozenPhase3Model):
    symbol: str
    status: Literal["PASS", "FAIL"]


class SelectionDecision(FrozenPhase3Model):
    category: str = Field(min_length=1)
    ordered_candidates: tuple[str, ...] = Field(min_length=1)
    dq_statuses: tuple[SelectionCandidateStatus, ...] = Field(min_length=1)
    selected_symbol: str | None
    reason: Literal["SELECTED_FIRST_CLEAN", "NO_CLEAN_CANDIDATE"]

    @model_validator(mode="after")
    def validate_decision(self) -> "SelectionDecision":
        status_symbols = tuple(item.symbol for item in self.dq_statuses)
        if status_symbols != self.ordered_candidates:
            raise ValueError("selection status order must match declared candidate order")
        passing = [item.symbol for item in self.dq_statuses if item.status == "PASS"]
        expected = passing[0] if passing else None
        if self.selected_symbol != expected:
            raise ValueError("selection must choose the first clean candidate")
        expected_reason = "SELECTED_FIRST_CLEAN" if expected else "NO_CLEAN_CANDIDATE"
        if self.reason != expected_reason:
            raise ValueError("selection reason does not match DQ outcomes")
        return self


class SelectedExposure(FrozenPhase3Model):
    category: str = Field(min_length=1)
    symbol: str


class SelectionResult(FrozenPhase3Model):
    schema_version: Literal["PHASE3-SELECTION-RESULT-v1"] = "PHASE3-SELECTION-RESULT-v1"
    selection_policy_version: Literal["PHASE3-EXPOSURE-SELECTION-v1"] = (
        SELECTION_POLICY_VERSION
    )
    snapshot: ArtifactIdentity
    decisions: tuple[SelectionDecision, ...]
    selected_exposures: tuple[SelectedExposure, ...]
    selected_symbols: tuple[str, ...]
    admitted: bool
    stop_reason: Literal[
        "PHASE_3_UNIVERSE_FROZEN", "INSUFFICIENT_CLEAN_DIVERSIFIED_UNIVERSE"
    ]
    strategy_performance_used: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(self) -> "SelectionResult":
        if self.snapshot.kind != "dq_snapshot":
            raise ValueError("selection requires a frozen DQ snapshot")
        exposure_symbols = tuple(item.symbol for item in self.selected_exposures)
        if exposure_symbols != self.selected_symbols:
            raise ValueError("selected symbol and exposure order differ")
        if len(self.selected_symbols) != len(set(self.selected_symbols)):
            raise ValueError("selected symbols must be unique")
        categories = tuple(item.category for item in self.selected_exposures)
        if len(categories) != len(set(categories)):
            raise ValueError("selected exposure categories must be unique")
        if len(self.selected_symbols) > 8:
            raise ValueError("Phase 3 selection cannot exceed eight exposures")
        expected_admitted = len(self.selected_symbols) >= 6
        if self.admitted != expected_admitted:
            raise ValueError("admission must fail closed below six exposures")
        expected_reason = (
            "PHASE_3_UNIVERSE_FROZEN"
            if expected_admitted
            else "INSUFFICIENT_CLEAN_DIVERSIFIED_UNIVERSE"
        )
        if self.stop_reason != expected_reason:
            raise ValueError("stop reason does not match selected exposure count")
        return self


class UniverseManifest(FrozenPhase3Model):
    schema_version: Literal["PHASE3-UNIVERSE-MANIFEST-v1"] = (
        UNIVERSE_MANIFEST_SCHEMA_VERSION
    )
    campaign_spec_version: Literal["PHASE3-ETF-DQ-SPEC-v1"] = CAMPAIGN_SPEC_VERSION
    campaign_id: str = Field(min_length=1)
    window_start: date
    window_end: date
    candidate_pool: tuple[str, ...]
    candidate_pool_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_policy_version: Literal["PHASE3-EXPOSURE-SELECTION-v1"] = (
        SELECTION_POLICY_VERSION
    )
    provider: Literal["MOOMOO"] = "MOOMOO"
    sdk_versions: tuple[str, ...]
    opend_versions: tuple[str, ...]
    normalization_version: Literal["MOOMOO-US-DAILY-EASTERN-DATE-UTC-v1"] = (
        NORMALIZATION_VERSION
    )
    validator_version: Literal["XNYS-OHLCV-DQ-v1"] = VALIDATOR_VERSION
    calendar_source_version: Literal["exchange_calendars-XNYS-v1"] = (
        CALENDAR_SOURCE_VERSION
    )
    dq_snapshot: ArtifactIdentity
    dq_report: ArtifactIdentity
    candidates: tuple[CandidateDQResult, ...]
    raw_evidence: tuple[ArtifactIdentity, ...]
    normalized_datasets: tuple[ArtifactIdentity, ...]
    selected_exposures: tuple[SelectedExposure, ...]
    selected_symbols: tuple[str, ...]
    source_revision: str = Field(min_length=1)
    dependency_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    qfq_execution_methodology: Literal[
        "NORMALIZED_RESEARCH_SIMULATION_NOT_HISTORICAL_EXECUTABLE_FILLS"
    ] = "NORMALIZED_RESEARCH_SIMULATION_NOT_HISTORICAL_EXECUTABLE_FILLS"
    decision_grade: Literal[False] = False
    strategy_performance_used: Literal[False] = False
    strategy_backtests_executed: Literal[0] = 0
    bars_repaired: Literal[0] = 0
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()
    live_trading_capability: Literal[False] = False
    created_at: datetime

    @model_validator(mode="after")
    def validate_manifest(self) -> "UniverseManifest":
        if (self.window_start, self.window_end) != (CAMPAIGN_START, CAMPAIGN_END):
            raise ValueError("universe manifest must use the fixed 2014-2022 window")
        if self.candidate_pool != CANDIDATE_POOL:
            raise ValueError("universe manifest candidate pool differs from the frozen pool")
        candidate_symbols = tuple(candidate.symbol for candidate in self.candidates)
        if len(candidate_symbols) != 16 or set(candidate_symbols) != set(CANDIDATE_POOL):
            raise ValueError("universe manifest requires all 16 DQ candidates")
        if self.dq_snapshot.kind != "dq_snapshot" or self.dq_report.kind != "dq_report":
            raise ValueError("universe manifest evidence identity kind mismatch")
        if self.raw_evidence != tuple(candidate.raw_evidence for candidate in self.candidates):
            raise ValueError("raw evidence chain does not match candidate DQ records")
        expected_normalized = tuple(
            candidate.normalized_dataset
            for candidate in self.candidates
            if candidate.normalized_dataset is not None
        )
        if self.normalized_datasets != expected_normalized:
            raise ValueError("normalized evidence chain does not match candidate DQ records")
        if self.selected_symbols != tuple(item.symbol for item in self.selected_exposures):
            raise ValueError("selected exposure and symbol order differ")
        if not 6 <= len(self.selected_symbols) <= 8:
            raise ValueError("admitted Phase 3 universe must contain six to eight exposures")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return self


class CampaignOutcome(FrozenPhase3Model):
    schema_version: Literal["PHASE3-CAMPAIGN-OUTCOME-v1"] = "PHASE3-CAMPAIGN-OUTCOME-v1"
    campaign_id: str
    window_start: date
    window_end: date
    candidate_pool: tuple[str, ...]
    preflight_sdk_version: str | None
    preflight_opend_version: str | None
    dq_snapshot: ArtifactIdentity
    dq_report: ArtifactIdentity
    selection: SelectionResult
    universe_manifest: ArtifactIdentity | None
    stop_reason: Literal[
        "PHASE_3_UNIVERSE_FROZEN", "INSUFFICIENT_CLEAN_DIVERSIFIED_UNIVERSE"
    ]

    @model_validator(mode="after")
    def validate_outcome(self) -> "CampaignOutcome":
        if (self.window_start, self.window_end) != (CAMPAIGN_START, CAMPAIGN_END):
            raise ValueError("campaign outcome window mismatch")
        if self.candidate_pool != CANDIDATE_POOL:
            raise ValueError("campaign outcome candidate pool mismatch")
        if self.selection.snapshot != self.dq_snapshot:
            raise ValueError("selection does not reference the frozen campaign snapshot")
        if self.stop_reason != self.selection.stop_reason:
            raise ValueError("campaign and selection stop reasons differ")
        if self.selection.admitted != (self.universe_manifest is not None):
            raise ValueError("manifest presence must match selection admission")
        return self
