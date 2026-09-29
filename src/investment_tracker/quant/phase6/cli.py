from __future__ import annotations

import argparse
import json
from pathlib import Path

from .preseal import phase6_preflight


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investment-tracker-phase6")
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--repository-root", default=".")
    preflight.add_argument("--output")

    args = parser.parse_args(argv)
    if args.command != "preflight":
        raise ValueError("PHASE6_COMMAND_UNSUPPORTED")

    result = phase6_preflight(Path(args.repository_root))
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
