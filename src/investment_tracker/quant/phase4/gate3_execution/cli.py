"""Quote-free Gate 3 methodology CLI; intentionally no campaign command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from investment_tracker.quant.phase4.engine.models import Gate2SealError
from investment_tracker.quant.phase4.gate3.models import Gate3AuthorityError

from .methodology import preflight_execution_methodology, seal_execution_methodology


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase4-gate3-execution-methodology")
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("seal")
    seal.add_argument("--repository-root", required=True)
    seal.add_argument("--source-revision", required=True)
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--repository-root", required=True)
    preflight.add_argument("--manifest-content-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "seal":
            identity = seal_execution_methodology(Path(args.repository_root), args.source_revision)
            result = {"status": "GATE3_EXECUTION_METHODOLOGY_SEALED", "manifest": identity.model_dump(mode="json")}
        else:
            state = preflight_execution_methodology(Path(args.repository_root), args.manifest_content_sha256)
            result = state.model_dump(mode="json")
    except (ValueError, Gate2SealError, Gate3AuthorityError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
