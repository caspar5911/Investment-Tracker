from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .models import Gate3AuthorityError
from .seal import preflight_gate3, seal_gate3_authorities


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase4-gate3-authorities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seal = subparsers.add_parser("seal")
    seal.add_argument("--repository-root", required=True)
    seal.add_argument("--source-revision", required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--repository-root", required=True)
    preflight.add_argument("--manifest-content-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "seal":
            identity = seal_gate3_authorities(
                Path(args.repository_root), source_revision=args.source_revision
            )
            output = {"status": "GATE3_AUTHORITIES_SEALED", "manifest": identity.model_dump(mode="json")}
        else:
            result = preflight_gate3(Path(args.repository_root), args.manifest_content_sha256)
            output = result.model_dump(mode="json")
    except Gate3AuthorityError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
