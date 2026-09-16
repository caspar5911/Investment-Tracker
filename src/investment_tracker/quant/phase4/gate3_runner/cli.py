from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .dependencies import load_runner_dependencies
from .methodology import preflight_runner, seal_runner
from .orchestrator import CampaignExecutionError, run_campaign


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="phase4-gate3-runner")
    commands = parser.add_subparsers(dest="command", required=True)

    seal = commands.add_parser("seal")
    seal.add_argument("--repository-root", required=True)
    seal.add_argument("--source-revision", required=True)

    preflight = commands.add_parser("preflight")
    preflight.add_argument("--repository-root", required=True)
    preflight.add_argument("--manifest-content-sha256", required=True)

    run = commands.add_parser("run")
    run.add_argument("--repository-root", required=True)
    run.add_argument("--manifest-content-sha256", required=True)

    args = parser.parse_args(argv)
    root = Path(args.repository_root)
    try:
        if args.command == "seal":
            identity = seal_runner(root, args.source_revision)
            output = {
                "status": "GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE",
                "manifest": identity.model_dump(mode="json"),
                "candidate_executed": False,
            }
        elif args.command == "preflight":
            output = preflight_runner(root, args.manifest_content_sha256).model_dump(mode="json")
        else:
            ready = preflight_runner(root, args.manifest_content_sha256)
            context = load_runner_dependencies(root)
            summary = run_campaign(context, runner_manifest=ready.manifest)
            output = {
                "status": summary.status,
                "accounted_positions": summary.accounted_positions,
                "executed": summary.executed,
                "unknown": summary.unknown,
                "abstain": summary.abstain,
                "skipped_family_stop": summary.skipped_family_stop,
                "result_set": summary.result_set.model_dump(mode="json"),
            }
    except (CampaignExecutionError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
