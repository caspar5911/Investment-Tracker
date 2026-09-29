"""Provider-free status and governed prospective collection CLI."""

from __future__ import annotations

import argparse
import json
from typing import Any

from . import phase7_collector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generation4-phase7-collector",
        description="Structural, paper-only Generation-4 Phase-7 collection.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prospective-status")
    commands.add_parser("collect-prospective-data")
    return parser


def _print_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prospective-status":
            report = phase7_collector.prospective_status()
        else:
            report = phase7_collector.collect_prospective_data()
    except phase7_collector.Generation4Phase7CollectorError as exc:
        _print_json({
            "status": phase7_collector.PHASE7_UNKNOWN_ABSTAIN,
            "code": exc.code,
            "detail": exc.detail,
        })
        return 1
    except Exception:
        _print_json({
            "status": phase7_collector.PHASE7_UNKNOWN_ABSTAIN,
            "code": "UNEXPECTED_COLLECTOR_ERROR",
        })
        return 1
    _print_json(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
