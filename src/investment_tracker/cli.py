from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from .validation import validate_manifest_files


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="investment-tracker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-manifest")
    validate.add_argument("path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate-manifest":
        report = validate_manifest_files(args.path)
        print(json.dumps({
            "ok": report.ok,
            "counts": report.counts,
            "errors": list(report.errors),
        }, sort_keys=True))
        return 0 if report.ok else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
