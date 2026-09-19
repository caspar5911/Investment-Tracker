from __future__ import annotations

import argparse
import json
from pathlib import Path

from .opend import export_opend_bundle
from .reconstruction import evaluate_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investment-tracker-phase5")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export-opend")
    export.add_argument("--output-dir", required=True)
    export.add_argument("--host", default="127.0.0.1")
    export.add_argument("--port", type=int, default=11111)

    run = sub.add_parser("evaluate")
    run.add_argument("--bundle-dir", required=True)
    run.add_argument("--output")

    args = parser.parse_args(argv)
    if args.command == "export-opend":
        path = export_opend_bundle(Path(args.output_dir), host=args.host, port=args.port)
        print(path)
        return 0

    result = evaluate_bundle(Path(args.bundle_dir))
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "READY_FOR_PASS_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
