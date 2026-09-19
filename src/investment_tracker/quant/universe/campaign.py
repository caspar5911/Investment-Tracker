from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
import platform
import subprocess
from typing import Protocol

from investment_tracker.governance import assert_symbol_allowed
from investment_tracker.quant.data.models import DataRequest
from investment_tracker.quant.data.moomoo_client import (
    MoomooCalendarEvidence,
    MoomooFetchEvidence,
    MoomooPreflightResult,
)

from .artifacts import Phase3ArtifactStore
from .constants import (
    CALENDAR_SOURCE_VERSION,
    CAMPAIGN_END,
    CAMPAIGN_SPEC_VERSION,
    CAMPAIGN_START,
    CANDIDATE_POOL,
    NORMALIZATION_VERSION,
    SELECTION_POLICY_VERSION,
    VALIDATOR_VERSION,
)
from .hashing import canonical_sha256
from .models import (
    CampaignOutcome,
    CandidateDQAssessment,
    CandidateDQResult,
    DQSnapshot,
    NormalizedDatasetMetadata,
    ProviderRequestRecord,
    UniverseManifest,
)
from .report import render_dq_report
from .selection import select_universe
from .validation import Phase3DQValidator, provider_request_from_parameters


class Phase3QuoteSource(Protocol):
    def preflight(self, symbol: str) -> MoomooPreflightResult: ...

    def history_request_parameters(self, request: DataRequest) -> dict[str, object]: ...

    def fetch_with_evidence(self, request: DataRequest) -> MoomooFetchEvidence: ...

    def fetch_calendar_evidence(self, request: DataRequest) -> MoomooCalendarEvidence: ...


def _source_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"
    return result.stdout.strip() or "UNKNOWN"


def _dependency_identity() -> str:
    packages = sorted(
        (
            distribution.metadata.get("Name", "UNKNOWN"),
            distribution.version,
        )
        for distribution in importlib_metadata.distributions()
    )
    return canonical_sha256(
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": packages,
        }
    )


def _quarantine_payload(assessment: CandidateDQAssessment) -> dict[str, object]:
    return {
        "schema_version": "PHASE3-QUARANTINE-v1",
        "symbol": assessment.symbol,
        "status": "QUARANTINED",
        "provider_request": assessment.provider_request.model_dump(mode="json"),
        "raw_evidence": assessment.raw_evidence.model_dump(mode="json"),
        "normalized_dataset": (
            assessment.normalized_dataset.model_dump(mode="json")
            if assessment.normalized_dataset is not None
            else None
        ),
        "issues": [issue.model_dump(mode="json") for issue in assessment.issues],
        "missing_sessions": [
            item.model_dump(mode="json") for item in assessment.missing_sessions
        ],
        "unexpected_sessions": [
            item.model_dump(mode="json") for item in assessment.unexpected_sessions
        ],
        "cause_policy": "UNKNOWN_UNLESS_AFFIRMATIVELY_ESTABLISHED",
    }


def _provider_request(
    request: DataRequest, parameters: dict[str, object]
) -> ProviderRequestRecord:
    return provider_request_from_parameters(request, parameters)


def _assess_new_candidate(
    *,
    source: Phase3QuoteSource,
    store: Phase3ArtifactStore,
    validator: Phase3DQValidator,
    request: DataRequest,
    preflight: MoomooPreflightResult,
    expected_request: ProviderRequestRecord,
) -> CandidateDQResult:
    fetch = source.fetch_with_evidence(request)
    actual_request = _provider_request(fetch.request, fetch.request_parameters)
    if actual_request != expected_request:
        raise ValueError("provider request parameters changed between cache lookup and fetch")
    raw_identity = store.write_raw_evidence(fetch, preflight.opend_version)
    normalized_identity = None
    if fetch.status == "SUCCESS" and fetch.normalized is not None and not fetch.normalized.empty:
        frame = fetch.normalized
        if not hasattr(frame.index, "min"):
            raise ValueError("normalized provider frame lacks a timestamp index")
        normalized_identity = store.write_normalized_dataset(
            frame,
            NormalizedDatasetMetadata(
                symbol=request.symbol,
                provider_request=expected_request,
                raw_evidence=raw_identity,
                sdk_version=fetch.sdk_version,
                opend_version=preflight.opend_version,
                retrieved_at=fetch.retrieved_at,
                row_count=len(frame),
                first_timestamp=frame.index.min().to_pydatetime(),
                last_timestamp=frame.index.max().to_pydatetime(),
            ),
        )

    assessment = validator.assess(
        fetch,
        raw_identity=raw_identity,
        normalized_identity=normalized_identity,
        opend_version=preflight.opend_version,
    )
    if assessment.missing_sessions or assessment.unexpected_sessions:
        calendar = source.fetch_calendar_evidence(request)
        calendar_identity = store.write_calendar_evidence(
            calendar, preflight.opend_version
        )
        assessment = validator.assess(
            fetch,
            raw_identity=raw_identity,
            normalized_identity=normalized_identity,
            opend_version=preflight.opend_version,
            calendar_evidence=calendar,
            calendar_identity=calendar_identity,
        )

    quarantine = None
    if assessment.status == "FAIL":
        quarantine = store.write_quarantine(_quarantine_payload(assessment))
    result = assessment.finalize(quarantine)
    store.write_candidate_record(result)
    return result


def run_phase3_campaign(
    source: Phase3QuoteSource,
    store: Phase3ArtifactStore,
    *,
    campaign_id: str,
    created_at: datetime | None = None,
    source_revision: str | None = None,
    dependency_identity: str | None = None,
) -> CampaignOutcome:
    moment = created_at or datetime.now(timezone.utc)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")

    for symbol in CANDIDATE_POOL:
        assert_symbol_allowed(symbol)
    preflight = source.preflight("SPY")
    validator = Phase3DQValidator("XNYS")
    candidates: list[CandidateDQResult] = []

    for symbol in CANDIDATE_POOL:
        request = DataRequest(symbol=symbol, start=CAMPAIGN_START, end=CAMPAIGN_END)
        parameters = source.history_request_parameters(request)
        provider_request = _provider_request(request, parameters)
        cached = store.find_candidate_record(
            symbol,
            provider_request,
            sdk_version=preflight.sdk_version,
            opend_version=preflight.opend_version,
        )
        if cached is not None:
            candidates.append(cached)
            continue
        candidates.append(
            _assess_new_candidate(
                source=source,
                store=store,
                validator=validator,
                request=request,
                preflight=preflight,
                expected_request=provider_request,
            )
        )

    snapshot = DQSnapshot(
        campaign_id=campaign_id,
        window_start=CAMPAIGN_START,
        window_end=CAMPAIGN_END,
        candidate_pool=CANDIDATE_POOL,
        candidates=tuple(candidates),
        created_at=moment,
    )
    snapshot_identity = store.freeze_dq_snapshot(snapshot)
    frozen_snapshot = store.load_frozen_snapshot(snapshot_identity)

    selection = select_universe(snapshot_identity, store)
    report_text = render_dq_report(frozen_snapshot, snapshot_identity, selection)
    report_identity = store.write_report(campaign_id, report_text)
    if store.read_text(report_identity) != report_text:
        raise ValueError("DQ report readback differs from frozen content")

    manifest_identity = None
    if selection.admitted:
        manifest = UniverseManifest(
            campaign_id=campaign_id,
            window_start=CAMPAIGN_START,
            window_end=CAMPAIGN_END,
            candidate_pool=CANDIDATE_POOL,
            candidate_pool_digest=canonical_sha256(CANDIDATE_POOL),
            selection_policy_version=SELECTION_POLICY_VERSION,
            sdk_versions=tuple(
                sorted({item.sdk_version for item in candidates if item.sdk_version})
            ),
            opend_versions=tuple(
                sorted({item.opend_version for item in candidates if item.opend_version})
            ),
            normalization_version=NORMALIZATION_VERSION,
            validator_version=VALIDATOR_VERSION,
            calendar_source_version=CALENDAR_SOURCE_VERSION,
            dq_snapshot=snapshot_identity,
            dq_report=report_identity,
            candidates=tuple(candidates),
            raw_evidence=tuple(item.raw_evidence for item in candidates),
            normalized_datasets=tuple(
                item.normalized_dataset
                for item in candidates
                if item.normalized_dataset is not None
            ),
            selected_exposures=selection.selected_exposures,
            selected_symbols=selection.selected_symbols,
            source_revision=source_revision or _source_revision(),
            dependency_identity=dependency_identity or _dependency_identity(),
            created_at=moment,
        )
        manifest_identity = store.write_universe_manifest(manifest)
        UniverseManifest.model_validate(store.read_json(manifest_identity))

    return CampaignOutcome(
        campaign_id=campaign_id,
        window_start=CAMPAIGN_START,
        window_end=CAMPAIGN_END,
        candidate_pool=CANDIDATE_POOL,
        preflight_sdk_version=preflight.sdk_version,
        preflight_opend_version=preflight.opend_version,
        dq_snapshot=snapshot_identity,
        dq_report=report_identity,
        selection=selection,
        universe_manifest=manifest_identity,
        stop_reason=selection.stop_reason,
    )
