"""Read-only CLI for the governed Generation-4 Phase-7 evaluation boundary.

This module exposes exactly four subcommands, all of which are thin, fail-closed
wrappers over the trusted, frozen evaluation functions:

- ``verify-evaluation-preflight``: verify the Phase-7 start artifact + start
  contract + evaluation contract agree and are governance-clean (no market data,
  no provider, no performance).
- ``resolve-prospective-boundary``: resolve the exact first prospective scored
  session strictly after the frozen start timestamp, with its warmup boundary.
- ``acquire-phase7-data``: acquire the prospective snapshot; the provider is
  created only after a valid Independent-Audit evaluation authorization.
- ``evaluate-phase7-checkpoint``: render the prospective checkpoint report from
  a frozen snapshot; no provider is accessed and no result grants authority.

No command accepts arbitrary symbols or strategy-parameter overrides: the
universe, candidate, benchmark, scored start, warmup limit, checkpoint cutoff,
and friction cases all come from the validated artifacts/authorization or the
frozen durable module.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pandas as pd

from investment_tracker.independent_audit.successor.evaluate_dividend_v3 import (
    _corporate_actions,
)

from ...quant.phase7.generation4_durability import (
    BENCHMARK_SYMBOL,
    CHECKPOINT_SESSIONS_EARLY,
    Generation4DurabilityError,
    ProspectiveCheckpoint,
    _governed_prospective_checkpoint_report,
)
from . import phase7_checkpoint_gate as checkpoint_gate
from . import phase7_first_checkpoint as first_checkpoint
from . import phase7_collector as collector
from .phase7_data import (
    DATA_REQUEST_SCHEMA,
    SNAPSHOT_SCHEMA,
    Generation4Phase7DataError,
    acquire_prospective_phase7_data,
    build_generation4_phase7_data_request,
    verify_generation4_phase7_evaluation_authorization,
    load_and_verify_generation4_phase7_evaluation_authorization,
)
from .phase7_evaluation import (
    GEN4_PHASE7_EVAL_BOUNDARY_INVALID,
    GEN4_PHASE7_EVAL_BINDING_MISMATCH,
    GEN4_PHASE7_EVAL_EVIDENCE_INVALID,
    Generation4Phase7EvaluationError,
    resolve_generation4_phase7_prospective_boundary,
    verify_generation4_phase7_evaluation_preflight,
)

_ERROR_TYPES = (
    Generation4Phase7EvaluationError,
    Generation4Phase7DataError,
    Generation4DurabilityError,
    checkpoint_gate.CheckpointGateError,
)


def _print_json(value: dict[str, Any]) -> None:
    print(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )


def _load_json(path: Path, *, expect: type, code: str, detail: str) -> Any:
    """Read a JSON file, failing closed unless it parses to the expected type."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise Generation4Phase7EvaluationError(code, detail) from None
    if not isinstance(payload, expect):
        raise Generation4Phase7EvaluationError(code, detail)
    return payload


def _preflight_command(args: argparse.Namespace) -> dict[str, Any]:
    return verify_generation4_phase7_evaluation_preflight(
        start_artifact_path=Path(args.start_artifact),
        start_contract_path=Path(args.start_contract),
        evaluation_contract_path=Path(args.evaluation_contract),
    )


def _resolve_boundary_command(args: argparse.Namespace) -> dict[str, Any]:
    start_artifact = _load_json(
        Path(args.start_artifact),
        expect=dict,
        code=GEN4_PHASE7_EVAL_EVIDENCE_INVALID,
        detail="start_artifact",
    )
    sessions = _load_json(
        Path(args.sessions),
        expect=list,
        code=GEN4_PHASE7_EVAL_BOUNDARY_INVALID,
        detail="sessions",
    )
    return resolve_generation4_phase7_prospective_boundary(
        sessions=sessions,
        started_at_utc=start_artifact["started_at_utc"],
    )


def _acquire_command(args: argparse.Namespace) -> dict[str, Any]:
    # Fail closed on the authorization BEFORE the provider exists.
    verified_authorization = load_and_verify_generation4_phase7_evaluation_authorization(
        Path(args.evaluation_authorization)
    )
    request = build_generation4_phase7_data_request(
        authorization=verified_authorization.authorization,
        requested_start=args.requested_start,
        requested_end=args.requested_end,
        retrieved_at_utc=args.retrieved_at_utc,
    )
    return acquire_prospective_phase7_data(
        evaluation_authorization=verified_authorization,
        request=request,
        output_dir=Path(args.output_dir),
        retrieved_at_utc=args.retrieved_at_utc,
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _snapshot_file_table(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if manifest.get("manifest_sha256") != sha256(_canonical_json(body)).hexdigest():
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "manifest_sha256"
        )
    files = manifest.get("files")
    if not isinstance(files, list):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_EVIDENCE_INVALID, "manifest_files"
        )
    table: dict[str, dict[str, Any]] = {}
    for item in files:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not isinstance(item.get("sha256"), str)
            or not isinstance(item.get("bytes"), int)
            or item["path"] in table
        ):
            raise Generation4Phase7EvaluationError(
                GEN4_PHASE7_EVAL_EVIDENCE_INVALID, "manifest_files"
            )
        table[item["path"]] = item
    return table


def _read_snapshot_bytes(
    snapshot_dir: Path | collector.VerifiedCheckpointSnapshot,
    relative: str,
    file_table: dict[str, dict[str, Any]],
) -> bytes:
    entry = file_table.get(relative)
    if entry is None:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_EVIDENCE_INVALID, f"manifest_missing:{relative}"
        )
    try:
        payload = (
            snapshot_dir.payload(relative)
            if isinstance(snapshot_dir, collector.VerifiedCheckpointSnapshot)
            else (snapshot_dir / relative).read_bytes()
        )
    except (OSError, collector.Generation4Phase7CollectorError):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_EVIDENCE_INVALID, relative
        ) from None
    if len(payload) != entry["bytes"] or sha256(payload).hexdigest() != entry["sha256"]:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, f"file_hash:{relative}"
        )
    return payload


def _load_bars(
    snapshot_dir: Path | collector.VerifiedCheckpointSnapshot,
    symbols: list[str],
    *,
    kind: str,
    file_table: dict[str, dict[str, Any]],
) -> dict[str, pd.DataFrame]:
    bars: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        relative = f"bars/{kind}/{symbol}.csv"
        payload = _read_snapshot_bytes(snapshot_dir, relative, file_table)
        try:
            from io import BytesIO

            frame = pd.read_csv(BytesIO(payload), index_col=0)
        except (ValueError, pd.errors.ParserError):
            raise Generation4Phase7EvaluationError(
                GEN4_PHASE7_EVAL_EVIDENCE_INVALID, f"bars:{kind}:{symbol}"
            ) from None
        frame.index = pd.to_datetime(frame.index, utc=True)
        bars[symbol] = frame
    return bars


def _load_corporate_actions(
    snapshot_dir: Path | collector.VerifiedCheckpointSnapshot,
    symbols: list[str],
    scored_sessions: pd.DatetimeIndex,
    file_table: dict[str, dict[str, Any]],
) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[dict[str, Any], ...]]:
    entries: dict[str, bytes] = {}
    for symbol in symbols:
        for relative in (
            f"corporate_actions/rehab/{symbol}.csv",
            f"corporate_actions/dividends/{symbol}.json",
            f"corporate_actions/splits/{symbol}.json",
        ):
            entries[relative] = _read_snapshot_bytes(
                snapshot_dir, relative, file_table
            )
    splits: list[Any] = []
    dividends: list[Any] = []
    evidence: list[dict[str, Any]] = []
    try:
        for symbol in symbols:
            symbol_splits, symbol_dividends, symbol_evidence = _corporate_actions(
                entries, symbol, scored_sessions
            )
            splits.extend(symbol_splits)
            dividends.extend(symbol_dividends)
            evidence.append(symbol_evidence)
    except Exception as exc:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_EVIDENCE_INVALID, f"corporate_actions:{exc}"
        ) from None
    return tuple(splits), tuple(dividends), tuple(evidence)


def _evaluate_checkpoint_command(args: argparse.Namespace) -> dict[str, Any]:
    # The separate first-checkpoint gate verifies all structural evidence and
    # Independent-Audit authority before bars, actions, or replay are loaded.
    snapshot_dir = Path(args.snapshot)
    permit = checkpoint_gate.checkpoint_execution_permit(snapshot_dir)
    authorization_path = Path(args.evaluation_authorization)
    if authorization_path.resolve() != collector._AUTHORIZATION_PATH.resolve():
        raise checkpoint_gate.CheckpointGateError(checkpoint_gate.PHASE7_UNKNOWN_ABSTAIN)
    authorization = first_checkpoint._historical_snapshot_authorization()
    try:
        authorization_sha256 = sha256(authorization_path.read_bytes()).hexdigest()
    except OSError:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_EVIDENCE_INVALID, "evaluation_authorization"
        ) from None
    manifest = _load_json(
        snapshot_dir / "manifest.json",
        expect=dict,
        code=GEN4_PHASE7_EVAL_BOUNDARY_INVALID,
        detail="manifest",
    )
    if manifest.get("schema_version") != SNAPSHOT_SCHEMA:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "manifest_schema"
        )
    if manifest.get("candidate_id") != authorization.candidate_id:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "candidate_id"
        )
    bound_manifest = {
        "evaluation_authorization_id": authorization.authorization_id,
        "evaluation_authorization_sha256": authorization_sha256,
        "audit_request_sha256": authorization.audit_request_sha256,
        "evaluation_contract_sha256": authorization.evaluation_contract_sha256,
        "start_artifact_sha256": authorization.start_artifact_sha256,
        "frozen_evaluation_implementation_commit": authorization.frozen_evaluation_implementation_commit,
    }
    for field, expected in bound_manifest.items():
        if manifest.get(field) != expected:
            raise Generation4Phase7EvaluationError(
                GEN4_PHASE7_EVAL_BINDING_MISMATCH, field
            )
    if manifest.get("scored_start") != authorization.prospective_first_scored_session:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "scored_start"
        )
    if manifest.get("benchmark_symbol") != BENCHMARK_SYMBOL:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "benchmark_symbol"
        )
    if tuple(manifest.get("symbols", {}).keys()) != tuple(authorization.research_universe):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "research_universe"
        )
    if (
        manifest.get("signal_price_convention") != "QFQ"
        or manifest.get("execution_price_convention") != "UNADJUSTED"
        or manifest.get("corporate_actions_included") is not True
    ):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "accounting_convention"
        )

    file_table = _snapshot_file_table(manifest)
    # Structural readiness reads manifests only. Consume the last mutable-file
    # authority before reading any performance-bearing snapshot payload.
    capability = checkpoint_gate.consume_checkpoint_permit(
        permit, snapshot_dir, manifest["manifest_sha256"]
    )
    try:
        # Deep verification reads payloads once after consumption. All later
        # loaders use these immutable verified bytes, never reopen snapshot files.
        verified_snapshot = collector.verify_snapshot_payloads(
            snapshot_dir, authorization, authorization_sha256,
            expected_manifest_sha256=capability.manifest_sha256,
        )
    except collector.Generation4Phase7CollectorError as exc:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_EVIDENCE_INVALID, f"snapshot:{exc.detail}"
        ) from None
    symbols = list(authorization.research_universe)
    signal_bars = _load_bars(
        verified_snapshot, symbols, kind="qfq", file_table=file_table
    )
    execution_bars = _load_bars(
        verified_snapshot, symbols, kind="unadjusted", file_table=file_table
    )
    scored_start = pd.Timestamp(manifest["scored_start"], tz="UTC")
    scored_sessions = pd.DatetimeIndex(
        [
            value
            for value in execution_bars[BENCHMARK_SYMBOL].index
            if value >= scored_start
        ]
    )
    if len(scored_sessions) != int(manifest.get("scored_session_count", -1)):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "scored_session_count"
        )
    splits, dividends, action_evidence = _load_corporate_actions(
        verified_snapshot, symbols, scored_sessions, file_table
    )
    snapshot = ProspectiveCheckpoint(
        bars=signal_bars,
        execution_bars=execution_bars,
        splits=splits,
        dividends=dividends,
        corporate_action_reconciliation=action_evidence,
        evidence_bindings={
            **bound_manifest,
            "snapshot_id": manifest["snapshot_id"],
            "snapshot_manifest_sha256": manifest["manifest_sha256"],
            "snapshot_chain_sha256": capability.snapshot_chain_sha256,
        },
        scored_start=scored_start,
        checkpoint_cutoff=CHECKPOINT_SESSIONS_EARLY,
    )
    report = _governed_prospective_checkpoint_report(snapshot, permit=capability)
    return checkpoint_gate.write_checkpoint_result(capability, report)


def evaluate_phase7_checkpoint(
    snapshot_dir: Path, evaluation_authorization_path: Path
) -> dict[str, Any]:
    """Governed Python entrypoint; consume authority before loading snapshot data."""
    return _evaluate_checkpoint_command(argparse.Namespace(
        snapshot=str(snapshot_dir),
        evaluation_authorization=str(evaluation_authorization_path),
    ))


def _evaluate_checkpoint_cli_command(args: argparse.Namespace) -> dict[str, Any]:
    return evaluate_phase7_checkpoint(
        Path(args.snapshot), Path(args.evaluation_authorization)
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generation4-phase7-evaluation",
        description="Governed Generation-4 Phase-7 evaluation boundary.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    preflight = commands.add_parser("verify-evaluation-preflight")
    preflight.add_argument("--start-artifact", required=True)
    preflight.add_argument("--start-contract", required=True)
    preflight.add_argument("--evaluation-contract", required=True)

    boundary = commands.add_parser("resolve-prospective-boundary")
    boundary.add_argument("--start-artifact", required=True)
    boundary.add_argument("--sessions", required=True)

    acquire = commands.add_parser("acquire-phase7-data")
    acquire.add_argument("--evaluation-authorization", required=True)
    acquire.add_argument("--output-dir", required=True)
    acquire.add_argument("--requested-start", required=True)
    acquire.add_argument("--requested-end", required=True)
    acquire.add_argument("--retrieved-at-utc", required=True)

    evaluate = commands.add_parser("evaluate-phase7-checkpoint")
    evaluate.add_argument("--evaluation-authorization", required=True)
    evaluate.add_argument("--snapshot", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "verify-evaluation-preflight": _preflight_command,
        "resolve-prospective-boundary": _resolve_boundary_command,
        "acquire-phase7-data": _acquire_command,
        "evaluate-phase7-checkpoint": _evaluate_checkpoint_cli_command,
    }
    try:
        report = handlers[args.command](args)
    except _ERROR_TYPES as exc:
        _print_json(
            {
                "status": "FORBIDDEN",
                "code": exc.code,
                "detail": exc.detail,
            }
        )
        return 1
    _print_json(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
