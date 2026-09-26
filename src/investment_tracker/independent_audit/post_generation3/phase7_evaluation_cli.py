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
import json
from pathlib import Path
from typing import Any

import pandas as pd

from ...quant.phase7.generation4_durability import (
    BENCHMARK_SYMBOL,
    CHECKPOINT_SESSIONS_PRIMARY,
    Generation4DurabilityError,
    ProspectiveCheckpoint,
    prospective_checkpoint_report,
)
from .phase7_data import (
    DATA_REQUEST_SCHEMA,
    SNAPSHOT_SCHEMA,
    Generation4Phase7DataError,
    acquire_prospective_phase7_data,
    verify_generation4_phase7_evaluation_authorization,
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
    authorization = verify_generation4_phase7_evaluation_authorization(
        Path(args.evaluation_authorization)
    )
    request: dict[str, Any] = {
        "schema_version": DATA_REQUEST_SCHEMA,
        "symbols": list(authorization.research_universe),
        "requested_start": args.requested_start,
        "requested_end": args.requested_end,
        "scored_start": authorization.prospective_first_scored_session,
        "warmup_session_count": authorization.warmup_session_limit,
        "scored_session_count": authorization.checkpoint_sessions[-1],
    }
    return acquire_prospective_phase7_data(
        evaluation_authorization=Path(args.evaluation_authorization),
        request=request,
        output_dir=Path(args.output_dir),
        retrieved_at_utc=args.retrieved_at_utc,
    )


def _load_bars(snapshot_dir: Path, symbols: list[str]) -> dict[str, pd.DataFrame]:
    bars: dict[str, pd.DataFrame] = {}
    bars_dir = snapshot_dir / "bars"
    for symbol in symbols:
        try:
            frame = pd.read_csv(bars_dir / f"{symbol}.csv", index_col=0)
        except (OSError, ValueError, pd.errors.ParserError):
            raise Generation4Phase7EvaluationError(
                GEN4_PHASE7_EVAL_EVIDENCE_INVALID, f"bars:{symbol}"
            ) from None
        frame.index = pd.to_datetime(frame.index, utc=True)
        bars[symbol] = frame
    return bars


def _evaluate_checkpoint_command(args: argparse.Namespace) -> dict[str, Any]:
    # Fail closed on the authorization BEFORE any data is read.
    authorization = verify_generation4_phase7_evaluation_authorization(
        Path(args.evaluation_authorization)
    )
    snapshot_dir = Path(args.snapshot)
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
    if (
        manifest.get("scored_start")
        != authorization.prospective_first_scored_session
    ):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "scored_start"
        )
    if manifest.get("benchmark_symbol") != BENCHMARK_SYMBOL:
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "benchmark_symbol"
        )
    if set(manifest.get("symbols", {}).keys()) != set(authorization.research_universe):
        raise Generation4Phase7EvaluationError(
            GEN4_PHASE7_EVAL_BINDING_MISMATCH, "research_universe"
        )
    bars = _load_bars(snapshot_dir, list(authorization.research_universe))
    snapshot = ProspectiveCheckpoint(
        bars=bars,
        scored_start=pd.Timestamp(manifest["scored_start"], tz="UTC"),
        checkpoint_cutoff=CHECKPOINT_SESSIONS_PRIMARY,
    )
    return prospective_checkpoint_report(snapshot)


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
        "evaluate-phase7-checkpoint": _evaluate_checkpoint_command,
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
