from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .phase7_start import (
    Generation4Phase7StartError,
    load_generation4_phase7_start_contract,
    start_generation4_phase7,
    verify_generation4_phase7_start_readiness,
)


def _add_arguments(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument("--audit-request", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--start-contract", required=True)


def _paths(args: argparse.Namespace) -> dict[str, Path]:
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
        "audit_request_path": Path(args.audit_request),
        "authorization_path": Path(args.authorization),
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
        prog="generation4-phase7-start",
        description="Governed Generation-4 Phase-7 start boundary.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    readiness = commands.add_parser("verify-start-readiness")
    _add_arguments(readiness)
    start = commands.add_parser("start-phase7")
    _add_arguments(start)
    start.add_argument("--start-output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = _paths(args)
    start_source = Path(__file__).with_name("phase7_start.py")
    entry_source = Path(__file__).with_name("phase7_entry.py")
    entry_cli_source = Path(__file__).with_name("phase7_entry_cli.py")
    cli_source = Path(__file__)
    try:
        if args.command == "verify-start-readiness":
            report = verify_generation4_phase7_start_readiness(**common)
            load_generation4_phase7_start_contract(
                contract_path=Path(args.start_contract),
                readiness=report,
                authorization_path=common["authorization_path"],
                audit_request_path=common["audit_request_path"],
                phase7_entry_path=entry_source,
                phase7_entry_cli_path=entry_cli_source,
                phase7_start_path=start_source,
                phase7_start_cli_path=cli_source,
            )
        else:
            report = start_generation4_phase7(
                **common,
                start_contract_path=Path(args.start_contract),
                start_output_path=Path(args.start_output),
                phase7_entry_path=entry_source,
                phase7_entry_cli_path=entry_cli_source,
                phase7_start_path=start_source,
                phase7_start_cli_path=cli_source,
            )
    except Generation4Phase7StartError as exc:
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
