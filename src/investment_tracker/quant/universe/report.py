from __future__ import annotations

from .constants import DQ_REPORT_SCHEMA_VERSION, EXPOSURE_SLOTS
from .models import ArtifactIdentity, DQSnapshot, SelectionResult


_CATEGORY_BY_SYMBOL = {
    symbol: slot.name for slot in EXPOSURE_SLOTS for symbol in slot.candidates
}


def _selection_reason(symbol: str, status: str, selection: SelectionResult) -> str:
    for decision in selection.decisions:
        if symbol not in decision.ordered_candidates:
            continue
        if decision.selected_symbol == symbol:
            return "SELECTED_FIRST_CLEAN"
        if status == "FAIL":
            return "NOT_SELECTED_DQ_FAIL"
        if decision.selected_symbol is not None:
            return "NOT_SELECTED_EARLIER_CLEAN_IN_SLOT"
        return "NOT_SELECTED_NO_SLOT_ADMISSION"
    return "NOT_SELECTED_TARGET_ALREADY_REACHED"


def render_dq_report(
    snapshot: DQSnapshot,
    snapshot_identity: ArtifactIdentity,
    selection: SelectionResult,
) -> str:
    lines = [
        "# Phase 3 ETF Universe Data-Quality Report",
        "",
        f"- Report schema: `{DQ_REPORT_SCHEMA_VERSION}`",
        f"- Campaign: `{snapshot.campaign_id}`",
        f"- Window: `{snapshot.window_start.isoformat()}` through `{snapshot.window_end.isoformat()}`",
        f"- DQ snapshot SHA-256: `{snapshot_identity.sha256}`",
        "- Admission calendar: `XNYS`",
        "- Moomoo calendar role: diagnostic only",
        "- Selection basis: frozen DQ dispositions and predefined exposure order only",
        "- Bars repaired: `0`",
        "- Decision grade: `false`",
        "",
        "## Candidate assessment",
        "",
        "| Symbol | Exposure category | DQ | Rows | Raw evidence | Normalized dataset | Missing sessions | Unexpected sessions | Calendar diagnostics | Quarantine reason | Selection reason |",
        "|---|---|---:|---:|---|---|---|---|---|---|---|",
    ]
    for candidate in snapshot.candidates:
        missing = ", ".join(
            item.session_date.isoformat() for item in candidate.missing_sessions
        ) or "NONE"
        unexpected = ", ".join(
            f"{item.session_date.isoformat()} ({item.raw_time_key})"
            for item in candidate.unexpected_sessions
        ) or "NONE"
        calendar = ", ".join(
            (
                f"{item.session_date.isoformat()}:{item.calendar.state}:"
                f"{item.calendar.evidence.sha256 if item.calendar.evidence else 'NO_EVIDENCE'}"
            )
            for item in (*candidate.missing_sessions, *candidate.unexpected_sessions)
        ) or "NONE"
        quarantine = (
            ",".join(issue.code for issue in candidate.issues)
            if candidate.quarantine is not None
            else "NONE"
        )
        normalized = (
            candidate.normalized_dataset.sha256
            if candidate.normalized_dataset is not None
            else "NONE"
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    candidate.symbol,
                    _CATEGORY_BY_SYMBOL[candidate.symbol],
                    candidate.status,
                    str(candidate.row_count),
                    candidate.raw_evidence.sha256,
                    normalized,
                    missing,
                    unexpected,
                    calendar,
                    quarantine,
                    _selection_reason(candidate.symbol, candidate.status, selection),
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Deterministic selection",
            "",
            "| Exposure category | Ordered candidates and frozen DQ | Selected | Reason |",
            "|---|---|---|---|",
        ]
    )
    for decision in selection.decisions:
        statuses = ", ".join(
            f"{item.symbol}:{item.status}" for item in decision.dq_statuses
        )
        lines.append(
            f"| {decision.category} | {statuses} | "
            f"{decision.selected_symbol or 'NONE'} | {decision.reason} |"
        )
    lines.extend(
        [
            "",
            f"Selected symbols: `{', '.join(selection.selected_symbols) or 'NONE'}`",
            "",
            f"Stop reason: `{selection.stop_reason}`",
            "",
        ]
    )
    return "\n".join(lines)

