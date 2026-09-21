from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from .access_logs import scan_access_logs
from .evaluate import evaluate_released_holdout
from .opend_qfq import acquire_and_seal
from .release import (
    issue_acquisition_authorization,
    issue_holdout_release,
)


def _dt(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected ISO-8601 datetime") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise argparse.ArgumentTypeError("datetime must include timezone")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investment-tracker-phase6-audit")
    sub = parser.add_subparsers(dest="command", required=True)

    logs = sub.add_parser("scan-access-logs")
    logs.add_argument("--path", action="append", required=True)
    logs.add_argument("--source-description", required=True)
    logs.add_argument("--coverage-start-utc", type=_dt, required=True)
    logs.add_argument("--coverage-end-utc", type=_dt, required=True)
    logs.add_argument("--output", required=True)

    authorize = sub.add_parser("issue-acquisition-authorization")
    authorize.add_argument("--contract", required=True)
    authorize.add_argument("--attestation", required=True)
    authorize.add_argument("--ci-head-sha", required=True)
    authorize.add_argument("--ci-run-id", type=int, required=True)
    authorize.add_argument("--output", required=True)

    acquire = sub.add_parser("acquire-seal")
    acquire.add_argument("--repository-root", default=".")
    acquire.add_argument("--contract", required=True)
    acquire.add_argument("--attestation", required=True)
    acquire.add_argument("--authorization", required=True)
    acquire.add_argument("--private-output-dir", required=True)
    acquire.add_argument("--host", default="127.0.0.1")
    acquire.add_argument("--port", type=int, default=11111)

    release = sub.add_parser("issue-release")
    release.add_argument("--contract", required=True)
    release.add_argument("--attestation", required=True)
    release.add_argument("--authorization", required=True)
    release.add_argument("--receipt", required=True)
    release.add_argument("--output", required=True)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--release", required=True)
    evaluate.add_argument("--contract", required=True)
    evaluate.add_argument("--receipt", required=True)
    evaluate.add_argument("--bundle", required=True)
    evaluate.add_argument("--key", required=True)
    evaluate.add_argument("--marker-directory", required=True)
    evaluate.add_argument("--output", required=True)

    args = parser.parse_args(argv)

    if args.command == "scan-access-logs":
        path = scan_access_logs(
            tuple(Path(item) for item in args.path),
            source_description=args.source_description,
            coverage_start_utc=args.coverage_start_utc,
            coverage_end_utc=args.coverage_end_utc,
            output_path=Path(args.output),
        )
        print(path)
        return 0

    if args.command == "issue-acquisition-authorization":
        path = issue_acquisition_authorization(
            contract_path=Path(args.contract),
            attestation_path=Path(args.attestation),
            ci_head_sha=args.ci_head_sha,
            ci_run_id=args.ci_run_id,
            output_path=Path(args.output),
        )
        print(path)
        return 0

    if args.command == "acquire-seal":
        receipt = acquire_and_seal(
            repository_root=Path(args.repository_root),
            contract_path=Path(args.contract),
            attestation_path=Path(args.attestation),
            authorization_path=Path(args.authorization),
            private_output_dir=Path(args.private_output_dir),
            host=args.host,
            port=args.port,
        )
        print(receipt)
        return 0

    if args.command == "issue-release":
        path = issue_holdout_release(
            contract_path=Path(args.contract),
            attestation_path=Path(args.attestation),
            authorization_path=Path(args.authorization),
            receipt_path=Path(args.receipt),
            output_path=Path(args.output),
        )
        print(path)
        return 0

    if args.command == "evaluate":
        result = evaluate_released_holdout(
            release_path=Path(args.release),
            contract_path=Path(args.contract),
            receipt_path=Path(args.receipt),
            encrypted_bundle_path=Path(args.bundle),
            key_path=Path(args.key),
            marker_directory=Path(args.marker_directory),
            output_path=Path(args.output),
        )
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "release_id": result.get("release_id"),
                    "holdout_id": result.get("holdout_id"),
                    "one_time_consumed": result.get("one_time_consumed"),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0

    raise ValueError("PHASE6_AUDIT_COMMAND_UNSUPPORTED")


if __name__ == "__main__":
    raise SystemExit(main())
