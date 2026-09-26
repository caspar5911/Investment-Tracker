from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .phase7_entry import (
    Generation4Phase7EntryError,
    evaluate_generation4_phase7_entry,
    verify_generation4_phase7_readiness,
)


def _add_evidence_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--phase6-contract", required=True)
    parser.add_argument("--acquisition-authorization", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--virginity-attestation", required=True)
    parser.add_argument("--virginity-evidence", required=True)
    parser.add_argument("--acquisition-receipt", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--phase6-result", required=True)
    parser.add_argument("--consumption-marker", required=True)
    parser.add_argument("--phase6-closure", required=True)


def _evidence_paths(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "phase6_contract_path": Path(args.phase6_contract),
        "acquisition_authorization_path": Path(args.acquisition_authorization),
        "selection_path": Path(args.selection),
        "virginity_attestation_path": Path(args.virginity_attestation),
        "virginity_evidence_path": Path(args.virginity_evidence),
        "acquisition_receipt_path": Path(args.acquisition_receipt),
        "release_path": Path(args.release),
        "phase6_result_path": Path(args.phase6_result),
        "consumption_marker_path": Path(args.consumption_marker),
        "phase6_closure_path": Path(args.phase6_closure),
    }


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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generation4-phase7-entry",
        description="Read-only Generation-4 Phase-7 entry governance gate.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    readiness = commands.add_parser("verify-readiness")
    _add_evidence_arguments(readiness)
    entry = commands.add_parser("evaluate-entry")
    _add_evidence_arguments(entry)
    entry.add_argument("--audit-request", required=True)
    entry.add_argument("--authorization", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "verify-readiness":
            report = verify_generation4_phase7_readiness(**_evidence_paths(args))
        else:
            report = evaluate_generation4_phase7_entry(
                audit_request_path=Path(args.audit_request),
                authorization_path=Path(args.authorization),
                **_evidence_paths(args),
            )
    except Generation4Phase7EntryError as exc:
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
