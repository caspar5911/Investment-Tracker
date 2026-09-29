"""Structural, paper-only Generation-4 Phase-7 prospective collection."""

from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import pandas as pd

from .phase7_data import (
    PROVIDER,
    SNAPSHOT_SCHEMA,
    Generation4Phase7DataError,
    Generation4Phase7EvaluationAuthorization,
    VerifiedPhase7Authorization,
    _CHECKPOINT_SESSIONS,
    _canonical_json,
    _normalize_provider_frame,
    _snapshot_id,
    _validate_request,
    acquire_prospective_phase7_data,
    build_generation4_phase7_data_request,
    load_and_verify_generation4_phase7_evaluation_authorization,
)

PHASE7_COLLECTION_PENDING = "PHASE7_COLLECTION_PENDING"
PHASE7_CHECKPOINT_READY = "PHASE7_CHECKPOINT_READY"
PHASE7_UNKNOWN_ABSTAIN = "PHASE7_UNKNOWN_ABSTAIN"
NO_NEW_COMPLETED_SESSION = "NO_NEW_COMPLETED_SESSION"
PHASE7_COLLECTION_UPDATED = "PHASE7_COLLECTION_UPDATED"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_AUTHORIZATION_PATH = (
    _REPO_ROOT / "data/governance/successor/generation4-phase7-evaluation-authorization.json"
)
_OUTPUT_DIR = _REPO_ROOT / "data/phase7/generation4/prospective"
_SNAPSHOT_NAME = re.compile(r"gen4-phase7-snapshot-[0-9a-f]{32}")
_MANIFEST_FIELDS = frozenset({
    "schema_version", "snapshot_id", "provider", "retrieved_at_utc",
    "requested_start", "requested_end", "scored_start",
    "warmup_session_count", "scored_session_count", "candidate_id",
    "evaluation_authorization_id", "evaluation_authorization_sha256",
    "audit_request_sha256", "evaluation_contract_sha256",
    "start_artifact_sha256", "frozen_evaluation_implementation_commit",
    "benchmark_symbol", "friction_cases_bps", "primary_friction_bps",
    "signal_price_convention", "execution_price_convention",
    "corporate_actions_included", "symbols", "files",
    "trading_context_created", "protected_holdout_symbols_accessed",
    "performance_computed", "performance_inspected", "manifest_sha256",
})


class Generation4Phase7CollectorError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise Generation4Phase7CollectorError(PHASE7_UNKNOWN_ABSTAIN, detail)


def _verified_authorization() -> VerifiedPhase7Authorization:
    repository = _REPO_ROOT.resolve()
    _require(
        _AUTHORIZATION_PATH.resolve().is_relative_to(repository)
        and _OUTPUT_DIR.resolve().is_relative_to(repository)
        and not _AUTHORIZATION_PATH.is_symlink()
        and not _OUTPUT_DIR.is_symlink(),
        "governed_paths",
    )
    try:
        return load_and_verify_generation4_phase7_evaluation_authorization(_AUTHORIZATION_PATH)
    except Generation4Phase7DataError as exc:
        raise Generation4Phase7CollectorError(
            PHASE7_UNKNOWN_ABSTAIN, f"authorization:{exc.code}"
        ) from exc


def _authorization() -> Generation4Phase7EvaluationAuthorization:
    return _verified_authorization().authorization


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def latest_completed_session() -> str:
    """Return the last XNYS session whose scheduled close has passed in UTC."""
    now = _utc_now()
    if now.tzinfo is None or now.utcoffset() is None:
        raise Generation4Phase7CollectorError(PHASE7_UNKNOWN_ABSTAIN, "untrusted_clock")
    instant = pd.Timestamp(now.astimezone(timezone.utc))
    calendar = xcals.get_calendar("XNYS")
    try:
        session = calendar.date_to_session(pd.Timestamp(instant.date()), direction="previous")
        while calendar.session_close(session) > instant:
            session = calendar.previous_session(session)
    except (TypeError, ValueError, KeyError) as exc:
        raise Generation4Phase7CollectorError(
            PHASE7_UNKNOWN_ABSTAIN, "xnys_calendar"
        ) from exc
    return str(session.date())


def structural_progress(scored_session_count: int) -> dict[str, object]:
    """Describe frozen checkpoint distance without evaluating performance."""
    if (
        isinstance(scored_session_count, bool)
        or not isinstance(scored_session_count, int)
        or not 0 <= scored_session_count <= _CHECKPOINT_SESSIONS[-1]
    ):
        raise Generation4Phase7CollectorError(
            PHASE7_UNKNOWN_ABSTAIN, "scored_session_count"
        )
    next_checkpoint = next(
        (value for value in _CHECKPOINT_SESSIONS if scored_session_count <= value),
        _CHECKPOINT_SESSIONS[-1],
    )
    return {
        "status": (
            PHASE7_CHECKPOINT_READY
            if scored_session_count in _CHECKPOINT_SESSIONS
            else PHASE7_COLLECTION_PENDING
        ),
        "scored_session_count": scored_session_count,
        "next_checkpoint_sessions": next_checkpoint,
        "sessions_remaining": next_checkpoint - scored_session_count,
    }


def _expected_file_paths(symbols: tuple[str, ...]) -> set[str]:
    return {
        f"{prefix}/{symbol}.{extension}"
        for symbol in symbols
        for prefix, extension in (
            ("bars/qfq", "csv"),
            ("bars/unadjusted", "csv"),
            ("corporate_actions/rehab", "csv"),
            ("corporate_actions/dividends", "json"),
            ("corporate_actions/splits", "json"),
        )
    }


def verify_snapshot(
    snapshot_dir: Path,
    authorization: Generation4Phase7EvaluationAuthorization,
    authorization_source: Path | VerifiedPhase7Authorization,
) -> dict[str, Any]:
    """Verify snapshot bytes and structure without calculating performance."""
    if isinstance(authorization_source, VerifiedPhase7Authorization):
        _require(authorization_source.authorization is authorization, "authorization_identity")
    _require(
        snapshot_dir.is_dir()
        and not snapshot_dir.is_symlink()
        and _SNAPSHOT_NAME.fullmatch(snapshot_dir.name) is not None,
        "snapshot_directory",
    )
    manifest_path = snapshot_dir / "manifest.json"
    _require(manifest_path.is_file() and not manifest_path.is_symlink(), "manifest_file")
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
        auth_hash = (
            authorization_source.sha256
            if isinstance(authorization_source, VerifiedPhase7Authorization)
            else sha256(authorization_source.read_bytes()).hexdigest()
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Generation4Phase7CollectorError(
            PHASE7_UNKNOWN_ABSTAIN, "manifest_or_authorization_bytes"
        ) from exc
    _require(isinstance(manifest, dict) and set(manifest) == _MANIFEST_FIELDS, "manifest_schema")
    _require(manifest["schema_version"] == SNAPSHOT_SCHEMA, "manifest_schema_version")
    _require(manifest["snapshot_id"] == snapshot_dir.name, "snapshot_id")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    _require(
        manifest["manifest_sha256"] == sha256(_canonical_json(body)).hexdigest(),
        "manifest_hash",
    )
    for field in (
        "corporate_actions_included", "performance_computed",
        "performance_inspected", "trading_context_created",
    ):
        _require(type(manifest[field]) is bool, f"manifest_boolean:{field}")
    expected_bindings: dict[str, Any] = {
        "provider": PROVIDER,
        "candidate_id": authorization.candidate_id,
        "evaluation_authorization_id": authorization.authorization_id,
        "evaluation_authorization_sha256": auth_hash,
        "audit_request_sha256": authorization.audit_request_sha256,
        "evaluation_contract_sha256": authorization.evaluation_contract_sha256,
        "start_artifact_sha256": authorization.start_artifact_sha256,
        "frozen_evaluation_implementation_commit": authorization.frozen_evaluation_implementation_commit,
        "benchmark_symbol": authorization.benchmark_symbol,
        "friction_cases_bps": list(authorization.friction_cases_bps),
        "primary_friction_bps": authorization.primary_friction_bps,
        "scored_start": authorization.prospective_first_scored_session,
        "signal_price_convention": "QFQ",
        "execution_price_convention": "UNADJUSTED",
        "corporate_actions_included": True,
        "protected_holdout_symbols_accessed": [],
        "performance_computed": False,
        "performance_inspected": False,
        "trading_context_created": False,
    }
    for field, expected in expected_bindings.items():
        _require(manifest[field] == expected, f"binding:{field}")
    _require(authorization.recon009_status == "OPEN", "recon009")
    _require(authorization.dq030_status == "UNRESOLVED", "dq030")
    symbols = tuple(authorization.research_universe)
    _require(
        isinstance(manifest["symbols"], dict)
        and tuple(manifest["symbols"]) == symbols,
        "research_universe",
    )
    request = {
        "schema_version": "GENERATION4-PHASE7-DATA-REQUEST-v1",
        "symbols": list(symbols),
        "requested_start": manifest["requested_start"],
        "requested_end": manifest["requested_end"],
        "scored_start": manifest["scored_start"],
        "warmup_session_count": manifest["warmup_session_count"],
        "scored_session_count": manifest["scored_session_count"],
    }
    try:
        validated, sessions = _validate_request(
            request, retrieved_at_utc=manifest["retrieved_at_utc"]
        )
    except Generation4Phase7DataError as exc:
        raise Generation4Phase7CollectorError(
            PHASE7_UNKNOWN_ABSTAIN, f"request:{exc.code}"
        ) from exc
    _require(
        manifest["snapshot_id"] == _snapshot_id(
            authorization, validated, manifest["retrieved_at_utc"]
        ),
        "snapshot_seed",
    )
    expected_paths = _expected_file_paths(symbols)
    file_entries = manifest["files"]
    _require(
        isinstance(file_entries, list)
        and len(file_entries) == len(expected_paths)
        and all(
            isinstance(item, dict)
            and set(item) == {"path", "sha256", "bytes"}
            and isinstance(item["path"], str)
            and isinstance(item["sha256"], str)
            and isinstance(item["bytes"], int)
            and not isinstance(item["bytes"], bool)
            and item["bytes"] >= 0
            for item in file_entries
        ),
        "file_table",
    )
    listed = [item["path"] for item in file_entries]
    _require(listed == sorted(expected_paths), "file_paths")
    _require(
        all(not item.is_symlink() for item in snapshot_dir.rglob("*")),
        "snapshot_symlink",
    )
    actual = {
        item.relative_to(snapshot_dir).as_posix()
        for item in snapshot_dir.rglob("*") if item.is_file()
    } - {"manifest.json"}
    _require(actual == expected_paths, "snapshot_file_set")
    hashes: dict[str, str] = {}
    for entry in file_entries:
        relative = entry["path"]
        try:
            payload = (snapshot_dir / relative).read_bytes()
        except OSError as exc:
            raise Generation4Phase7CollectorError(
                PHASE7_UNKNOWN_ABSTAIN, f"missing_file:{relative}"
            ) from exc
        digest = sha256(payload).hexdigest()
        _require(
            len(payload) == entry["bytes"] and digest == entry["sha256"],
            f"file_hash:{relative}",
        )
        hashes[relative] = digest
        if relative.startswith("bars/"):
            try:
                frame = pd.read_csv(BytesIO(payload), index_col=0)
                _require(
                    frame.index.name == "session"
                    and set(frame.columns) == {"open", "high", "low", "close", "volume"},
                    f"bar_columns:{relative}",
                )
                _normalize_provider_frame(
                    frame, expected_sessions=sessions, symbol=relative
                )
            except (ValueError, pd.errors.ParserError, Generation4Phase7DataError) as exc:
                raise Generation4Phase7CollectorError(
                    PHASE7_UNKNOWN_ABSTAIN, f"bars:{relative}"
                ) from exc
        elif relative.endswith(".json"):
            try:
                _require(isinstance(json.loads(payload), dict), f"json:{relative}")
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise Generation4Phase7CollectorError(
                    PHASE7_UNKNOWN_ABSTAIN, f"json:{relative}"
                ) from exc
        else:
            try:
                pd.read_csv(BytesIO(payload))
            except (ValueError, pd.errors.ParserError) as exc:
                raise Generation4Phase7CollectorError(
                    PHASE7_UNKNOWN_ABSTAIN, f"rehab:{relative}"
                ) from exc
    for symbol in symbols:
        _require(
            manifest["symbols"][symbol] == {
                "qfq_sha256": hashes[f"bars/qfq/{symbol}.csv"],
                "unadjusted_sha256": hashes[f"bars/unadjusted/{symbol}.csv"],
                "rehab_sha256": hashes[f"corporate_actions/rehab/{symbol}.csv"],
                "dividends_sha256": hashes[f"corporate_actions/dividends/{symbol}.json"],
                "splits_sha256": hashes[f"corporate_actions/splits/{symbol}.json"],
            },
            f"symbol_hashes:{symbol}",
        )
    return manifest


def _verified_snapshots(
    authorization: Generation4Phase7EvaluationAuthorization,
    authorization_source: Path | VerifiedPhase7Authorization | None = None,
) -> list[dict[str, Any]]:
    if authorization_source is None:
        authorization_source = _AUTHORIZATION_PATH
    root = _OUTPUT_DIR / "snapshots"
    _require(not root.is_symlink(), "snapshots_directory_symlink")
    if not root.exists():
        return []
    _require(root.is_dir() and not root.is_symlink(), "snapshots_directory")
    manifests: list[dict[str, Any]] = []
    for snapshot_dir in sorted(root.iterdir()):
        manifests.append(verify_snapshot(snapshot_dir, authorization, authorization_source))
    ends = [manifest["requested_end"] for manifest in manifests]
    _require(len(ends) == len(set(ends)), "duplicate_acquired_session")
    return sorted(manifests, key=lambda item: item["requested_end"])


def _status_from_verified(
    completed: str, snapshots: list[dict[str, Any]]
) -> dict[str, Any]:
    latest = snapshots[-1] if snapshots else None
    if latest is not None:
        _require(latest["requested_end"] <= completed, "acquired_after_completed")
    scored_count = latest["scored_session_count"] if latest else 0
    progress = structural_progress(scored_count)
    return {
        **progress,
        "latest_completed_session": completed,
        "latest_acquired_session": latest["requested_end"] if latest else None,
        "snapshot_id": latest["snapshot_id"] if latest else None,
        "manifest_sha256": latest["manifest_sha256"] if latest else None,
        "manifest_verification": "VERIFIED" if latest else "NO_SNAPSHOT",
    }


def prospective_status() -> dict[str, Any]:
    """Report structural progress from verified local snapshots only."""
    verified = _verified_authorization()
    authorization = verified.authorization
    completed = latest_completed_session()
    snapshots = _verified_snapshots(authorization, verified)
    return _status_from_verified(completed, snapshots)


def _warmup_start(authorization: Generation4Phase7EvaluationAuthorization) -> str:
    calendar = xcals.get_calendar("XNYS")
    first = pd.Timestamp(authorization.prospective_first_scored_session)
    prior = calendar.sessions_in_range(
        first - pd.Timedelta(days=500), first - pd.Timedelta(days=1)
    )
    _require(len(prior) >= authorization.warmup_session_limit, "warmup_calendar")
    return str(prior[-authorization.warmup_session_limit].date())


def _collection_target_end(
    completed: str,
    snapshots: list[dict[str, Any]],
    authorization: Generation4Phase7EvaluationAuthorization,
) -> str:
    """Preserve an exact first-checkpoint snapshot before collecting later data."""
    first = pd.Timestamp(authorization.prospective_first_scored_session)
    calendar = xcals.get_calendar("XNYS")
    sessions = calendar.sessions_in_range(first, first + pd.Timedelta(days=120))
    _require(len(sessions) >= _CHECKPOINT_SESSIONS[0], "first_checkpoint_calendar")
    boundary = str(sessions[_CHECKPOINT_SESSIONS[0] - 1].date())
    exact = any(item["requested_end"] == boundary for item in snapshots)
    if not exact:
        _require(
            not any(item["requested_end"] > boundary for item in snapshots),
            "missing_exact_first_checkpoint_snapshot",
        )
        if completed >= boundary:
            return boundary
    return completed


def collect_prospective_data() -> dict[str, Any]:
    """Collect only new completed sessions through the frozen acquisition path."""
    verified_authorization = _verified_authorization()
    authorization = verified_authorization.authorization
    completed = latest_completed_session()
    snapshots = _verified_snapshots(authorization, verified_authorization)
    status = _status_from_verified(completed, snapshots)
    acquired = status["latest_acquired_session"]
    target_end = _collection_target_end(completed, snapshots, authorization)
    if acquired == completed or completed < authorization.prospective_first_scored_session:
        return {**status, "status": NO_NEW_COMPLETED_SESSION}

    now = _utc_now()
    _require(
        now.tzinfo is not None and now.utcoffset() is not None,
        "untrusted_clock",
    )
    retrieved_at_utc = now.astimezone(timezone.utc).isoformat()
    try:
        request = build_generation4_phase7_data_request(
            authorization=authorization,
            requested_start=_warmup_start(authorization),
            requested_end=target_end,
            retrieved_at_utc=retrieved_at_utc,
        )
    except Generation4Phase7DataError as exc:
        raise Generation4Phase7CollectorError(
            PHASE7_UNKNOWN_ABSTAIN, f"request:{exc.code}"
        ) from exc

    _require(
        not _OUTPUT_DIR.is_symlink(),
        "output_directory_symlink",
    )
    try:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".phase7-collector-", dir=_OUTPUT_DIR
        ) as staging_name:
            staging = Path(staging_name)
            try:
                produced = acquire_prospective_phase7_data(
                    evaluation_authorization=verified_authorization,
                    request=request,
                    output_dir=staging,
                    retrieved_at_utc=retrieved_at_utc,
                )
            except Exception as exc:
                raise Generation4Phase7CollectorError(
                    PHASE7_UNKNOWN_ABSTAIN, "acquisition_failed"
                ) from exc
            _require(
                isinstance(produced, dict)
                and isinstance(produced.get("snapshot_id"), str)
                and _SNAPSHOT_NAME.fullmatch(produced["snapshot_id"]) is not None,
                "acquisition_manifest",
            )
            staged_snapshot = staging / "snapshots" / produced["snapshot_id"]
            verified = verify_snapshot(
                staged_snapshot, authorization, verified_authorization
            )
            _require(produced == verified, "acquisition_readback")
            destination_root = _OUTPUT_DIR / "snapshots"
            _require(
                not _OUTPUT_DIR.is_symlink()
                and not destination_root.is_symlink(),
                "publication_path_symlink",
            )
            destination_root.mkdir(exist_ok=True)
            destination = destination_root / produced["snapshot_id"]
            _require(
                not destination.exists() and not destination.is_symlink(),
                "snapshot_exists",
            )
            staged_snapshot.rename(destination)
    except OSError as exc:
        raise Generation4Phase7CollectorError(
            PHASE7_UNKNOWN_ABSTAIN, "staging_or_publication"
        ) from exc
    updated = _status_from_verified(completed, snapshots + [verified])
    if updated["status"] != PHASE7_CHECKPOINT_READY:
        updated["status"] = PHASE7_COLLECTION_UPDATED
    return updated
