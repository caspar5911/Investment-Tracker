from __future__ import annotations

import argparse
import json
from pathlib import Path

from investment_tracker.independent_audit.successor.acquisition_authority import (
    load_acquisition_authorization,
)
from investment_tracker.independent_audit.successor.acquisition import (
    acquire_and_seal,
    preflight_acquisition,
)
from investment_tracker.independent_audit.successor.release import issue_release
from investment_tracker.independent_audit.successor.evaluate_dividend_v3 import (
    evaluate_released_holdout,
)
from investment_tracker.independent_audit.successor.closure import close_phase6


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investment-tracker-generation4-stage-b")
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify-acquisition-authorization")
    verify.add_argument("--acquisition-authorization", required=True)
    verify.add_argument("--phase6-contract", required=True)
    verify.add_argument("--selection", required=True)
    verify.add_argument("--virginity-evidence", required=True)
    verify.add_argument("--virginity-attestation", required=True)

    preflight = sub.add_parser("preflight-final-holdout")
    preflight.add_argument("--acquisition-authorization", required=True)
    preflight.add_argument("--phase6-contract", required=True)
    preflight.add_argument("--selection", required=True)
    preflight.add_argument("--virginity-evidence", required=True)
    preflight.add_argument("--virginity-attestation", required=True)
    preflight.add_argument("--host", default="127.0.0.1")
    preflight.add_argument("--port", type=int, default=11111)

    acquire = sub.add_parser("acquire-final-holdout")
    acquire.add_argument("--repository-root", default=".")
    acquire.add_argument("--acquisition-authorization", required=True)
    acquire.add_argument("--phase6-contract", required=True)
    acquire.add_argument("--selection", required=True)
    acquire.add_argument("--virginity-evidence", required=True)
    acquire.add_argument("--virginity-attestation", required=True)
    acquire.add_argument("--private-output-dir", required=True)
    acquire.add_argument("--host", default="127.0.0.1")
    acquire.add_argument("--port", type=int, default=11111)

    release = sub.add_parser("issue-final-holdout-release")
    release.add_argument("--phase6-contract", required=True)
    release.add_argument("--acquisition-authorization", required=True)
    release.add_argument("--selection", required=True)
    release.add_argument("--virginity-evidence", required=True)
    release.add_argument("--virginity-attestation", required=True)
    release.add_argument("--receipt", required=True)
    release.add_argument("--bundle", required=True)
    release.add_argument("--key", required=True)
    release.add_argument("--output", required=True)
    release.add_argument("--receipt-evidence-output", required=True)

    evaluate = sub.add_parser("evaluate-final-holdout")
    evaluate.add_argument("--repository-root", default=".")
    evaluate.add_argument("--release", required=True)
    evaluate.add_argument("--phase6-contract", required=True)
    evaluate.add_argument("--acquisition-authorization", required=True)
    evaluate.add_argument("--selection", required=True)
    evaluate.add_argument("--virginity-evidence", required=True)
    evaluate.add_argument("--virginity-attestation", required=True)
    evaluate.add_argument("--receipt", required=True)
    evaluate.add_argument("--bundle", required=True)
    evaluate.add_argument("--key", required=True)
    evaluate.add_argument("--marker-directory", required=True)
    evaluate.add_argument("--output", required=True)

    close = sub.add_parser("close-phase6")
    close.add_argument("--phase6-contract", required=True)
    close.add_argument("--release", required=True)
    close.add_argument("--result", required=True)
    close.add_argument("--consumption-marker", required=True)
    close.add_argument("--acquisition-receipt", required=True)
    close.add_argument("--output", required=True)

    args = parser.parse_args(argv)

    def common() -> dict[str, Path]:
        return {
            "authorization_path": Path(args.acquisition_authorization),
            "phase6_contract_path": Path(args.phase6_contract),
            "selection_path": Path(args.selection),
            "virginity_attestation_path": Path(args.virginity_attestation),
            "virginity_evidence_path": Path(args.virginity_evidence),
        }

    if args.command == "verify-acquisition-authorization":
        auth = load_acquisition_authorization(**common())
        print(json.dumps({
            "status": auth.status,
            "authorization_id": auth.authorization_id,
            "successor_formal_name": auth.successor_formal_name,
            "one_time": auth.one_time,
            "phase7_authorized": auth.phase7_authorized,
        }, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "preflight-final-holdout":
        result = preflight_acquisition(host=args.host, port=args.port, **common())
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "acquire-final-holdout":
        receipt = acquire_and_seal(
            repository_root=Path(args.repository_root),
            private_output_dir=Path(args.private_output_dir),
            host=args.host,
            port=args.port,
            **common(),
        )
        value = json.loads(receipt.read_text(encoding="utf-8"))
        print(json.dumps({
            "status": value["status"],
            "holdout_id": value["holdout_id"],
            "performance_inspected": value["performance_inspected"],
            "receipt": str(receipt),
        }, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "issue-final-holdout-release":
        path = issue_release(
            contract_path=Path(args.phase6_contract),
            authorization_path=Path(args.acquisition_authorization),
            selection_path=Path(args.selection),
            virginity_attestation_path=Path(args.virginity_attestation),
            virginity_evidence_path=Path(args.virginity_evidence),
            receipt_path=Path(args.receipt),
            encrypted_bundle_path=Path(args.bundle),
            key_path=Path(args.key),
            output_path=Path(args.output),
            receipt_evidence_path=Path(args.receipt_evidence_output),
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps({
            "status": value["status"],
            "release_id": value["release_id"],
            "phase7_authorized": value["phase7_authorized"],
            "output": str(path),
        }, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "evaluate-final-holdout":
        result = evaluate_released_holdout(
            repository_root=Path(args.repository_root),
            release_path=Path(args.release),
            contract_path=Path(args.phase6_contract),
            authorization_path=Path(args.acquisition_authorization),
            selection_path=Path(args.selection),
            virginity_attestation_path=Path(args.virginity_attestation),
            virginity_evidence_path=Path(args.virginity_evidence),
            receipt_path=Path(args.receipt),
            encrypted_bundle_path=Path(args.bundle),
            key_path=Path(args.key),
            marker_directory=Path(args.marker_directory),
            output_path=Path(args.output),
        )
        print(json.dumps({
            "status": result["status"],
            "one_time_consumed": result.get("one_time_consumed"),
            "phase7_authorized": result.get("phase7_authorized"),
            "output": args.output,
        }, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "close-phase6":
        result = close_phase6(
            contract_path=Path(args.phase6_contract),
            release_path=Path(args.release),
            result_path=Path(args.result),
            consumption_marker_path=Path(args.consumption_marker),
            acquisition_receipt_path=Path(args.acquisition_receipt),
            output_path=Path(args.output),
        )
        print(json.dumps({
            "status": result["status"],
            "phase7_eligible": result["phase7"]["eligible_for_independent_entry_review"],
            "phase7_authorized": result["phase7"]["authorized"],
            "output": args.output,
        }, sort_keys=True, separators=(",", ":")))
        return 0

    raise ValueError("GENERATION4_STAGE_B_COMMAND_UNSUPPORTED")


if __name__ == "__main__":
    raise SystemExit(main())
