from __future__ import annotations

from datetime import date
from typing import Any

import exchange_calendars as xcals
import pandas as pd

from investment_tracker.quant.data.moomoo_client import (
    MoomooCalendarEvidence,
    MoomooFetchEvidence,
    MoomooRawRowLink,
)
from investment_tracker.quant.data.validation import BarDataValidator

from .models import (
    ArtifactIdentity,
    CalendarDiagnostic,
    CandidateDQAssessment,
    DataQualityIssueRecord,
    ProviderRequestRecord,
    RawRowReference,
    SessionDiagnostic,
)


def _enum_value(parameters: dict[str, object], key: str) -> str:
    value = parameters.get(key)
    if not isinstance(value, dict) or "value" not in value:
        raise ValueError(f"provider request parameter {key} is malformed")
    return str(value["value"])


def provider_request_from_evidence(evidence: MoomooFetchEvidence) -> ProviderRequestRecord:
    parameters = evidence.request_parameters
    field_records = parameters.get("fields")
    if not isinstance(field_records, list):
        raise ValueError("provider request parameter fields is malformed")
    fields: list[str] = []
    for record in field_records:
        if not isinstance(record, dict) or "value" not in record:
            raise ValueError("provider request field identity is malformed")
        fields.append(str(record["value"]))
    return ProviderRequestRecord(
        symbol=evidence.request.symbol,
        code=str(parameters["code"]),
        start=evidence.request.start,
        end=evidence.request.end,
        host=str(parameters["host"]),
        port=int(parameters["port"]),
        ktype=_enum_value(parameters, "ktype"),
        autype=_enum_value(parameters, "autype"),
        fields=tuple(fields),
        max_count=int(parameters["max_count"]),
        extended_time=bool(parameters["extended_time"]),
        session=_enum_value(parameters, "session"),
    )


def _raw_reference(
    link: MoomooRawRowLink, raw_identity: ArtifactIdentity
) -> RawRowReference:
    return RawRowReference(
        raw_evidence_sha256=raw_identity.sha256,
        page_number=link.page_number,
        row_number=link.row_number,
        code=link.code,
        raw_time_key=link.raw_time_key,
        normalized_date=link.normalized_date,
    )


def _calendar_open_dates(evidence: MoomooCalendarEvidence | None) -> set[date] | None:
    if evidence is None or evidence.status != "SUCCESS" or not isinstance(evidence.data, list):
        return None
    result: set[date] = set()
    try:
        for item in evidence.data:
            if not isinstance(item, dict):
                return None
            raw_date = item.get("time", item.get("trade_date"))
            if raw_date is None:
                return None
            result.add(pd.Timestamp(raw_date).date())
    except (TypeError, ValueError, pd.errors.OutOfBoundsDatetime):
        return None
    return result


def _calendar_diagnostic(
    *,
    session_date: date,
    xnys_expected_open: bool,
    evidence: MoomooCalendarEvidence | None,
    identity: ArtifactIdentity | None,
) -> CalendarDiagnostic:
    open_dates = _calendar_open_dates(evidence)
    if open_dates is None or identity is None:
        return CalendarDiagnostic(
            state="UNAVAILABLE",
            evidence=identity,
            provider_reported_open=None,
            error=evidence.error if evidence is not None else None,
        )
    provider_open = session_date in open_dates
    if provider_open == xnys_expected_open:
        state = "AGREE_OPEN" if provider_open else "AGREE_CLOSED"
    else:
        state = "DISAGREE"
    return CalendarDiagnostic(
        state=state,
        evidence=identity,
        provider_reported_open=provider_open,
        error=evidence.error,
    )


class Phase3DQValidator:
    def __init__(self, calendar_name: str = "XNYS") -> None:
        self._calendar = xcals.get_calendar(calendar_name)
        self._base = BarDataValidator(calendar_name)

    def assess(
        self,
        evidence: MoomooFetchEvidence,
        *,
        raw_identity: ArtifactIdentity,
        normalized_identity: ArtifactIdentity | None,
        opend_version: str | None,
        calendar_evidence: MoomooCalendarEvidence | None = None,
        calendar_identity: ArtifactIdentity | None = None,
    ) -> CandidateDQAssessment:
        provider_request = provider_request_from_evidence(evidence)
        if evidence.status != "SUCCESS" or evidence.normalized is None:
            detail = evidence.error or "provider evidence is incomplete"
            return CandidateDQAssessment(
                symbol=evidence.request.symbol,
                status="FAIL",
                row_count=0,
                provider_request=provider_request,
                raw_evidence=raw_identity,
                normalized_dataset=None,
                issues=(DataQualityIssueRecord(code="PROVIDER_ERROR", detail=detail),),
                missing_sessions=(),
                unexpected_sessions=(),
                sdk_version=evidence.sdk_version,
                opend_version=opend_version,
                retrieved_at=evidence.retrieved_at,
            )

        frame = evidence.normalized
        report = self._base.validate(frame, evidence.request)
        issues = tuple(
            DataQualityIssueRecord(code=issue.code, detail=issue.detail)
            for issue in report.issues
        )
        if normalized_identity is None:
            issues = (
                *issues,
                DataQualityIssueRecord(
                    code="MISSING_NORMALIZED_ARTIFACT",
                    detail="normalized provider bars were not stored",
                ),
            )

        expected = pd.DatetimeIndex(
            self._calendar.sessions_in_range(evidence.request.start, evidence.request.end)
        )
        if expected.tz is None:
            expected = expected.tz_localize("UTC")
        else:
            expected = expected.tz_convert("UTC")
        observed = frame.index.normalize() if isinstance(frame.index, pd.DatetimeIndex) else pd.DatetimeIndex([])
        missing_dates = [timestamp.date() for timestamp in expected.difference(observed)]
        unexpected_dates = [timestamp.date() for timestamp in observed.difference(expected)]

        ordered_links = sorted(
            evidence.row_links,
            key=lambda link: (link.normalized_date, link.page_number, link.row_number),
        )
        missing_diagnostics: list[SessionDiagnostic] = []
        for missing_date in missing_dates:
            preceding = next(
                (link for link in reversed(ordered_links) if link.normalized_date < missing_date),
                None,
            )
            following = next(
                (link for link in ordered_links if link.normalized_date > missing_date),
                None,
            )
            missing_diagnostics.append(
                SessionDiagnostic(
                    classification="MISSING_SESSION",
                    session_date=missing_date,
                    xnys_expected_open=True,
                    raw_time_key=None,
                    normalized_date=None,
                    preceding=(
                        _raw_reference(preceding, raw_identity) if preceding is not None else None
                    ),
                    following=(
                        _raw_reference(following, raw_identity) if following is not None else None
                    ),
                    calendar=_calendar_diagnostic(
                        session_date=missing_date,
                        xnys_expected_open=True,
                        evidence=calendar_evidence,
                        identity=calendar_identity,
                    ),
                )
            )

        unexpected_diagnostics: list[SessionDiagnostic] = []
        for unexpected_date in unexpected_dates:
            matching_indexes = [
                index
                for index, link in enumerate(ordered_links)
                if link.normalized_date == unexpected_date
            ]
            for index in matching_indexes:
                link = ordered_links[index]
                unexpected_diagnostics.append(
                    SessionDiagnostic(
                        classification="UNEXPECTED_SESSION",
                        session_date=unexpected_date,
                        xnys_expected_open=False,
                        raw_time_key=link.raw_time_key,
                        normalized_date=link.normalized_date,
                        preceding=(
                            _raw_reference(ordered_links[index - 1], raw_identity)
                            if index > 0
                            else None
                        ),
                        following=(
                            _raw_reference(ordered_links[index + 1], raw_identity)
                            if index + 1 < len(ordered_links)
                            else None
                        ),
                        calendar=_calendar_diagnostic(
                            session_date=unexpected_date,
                            xnys_expected_open=False,
                            evidence=calendar_evidence,
                            identity=calendar_identity,
                        ),
                    )
                )

        return CandidateDQAssessment(
            symbol=evidence.request.symbol,
            status="PASS" if not issues else "FAIL",
            row_count=len(frame),
            provider_request=provider_request,
            raw_evidence=raw_identity,
            normalized_dataset=normalized_identity,
            issues=issues,
            missing_sessions=tuple(missing_diagnostics),
            unexpected_sessions=tuple(unexpected_diagnostics),
            sdk_version=evidence.sdk_version,
            opend_version=opend_version,
            retrieved_at=evidence.retrieved_at,
        )
