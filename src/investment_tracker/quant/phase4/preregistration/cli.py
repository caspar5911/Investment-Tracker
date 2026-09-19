from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .seal import Gate1SealError, seal_gate1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seal the provider-free Phase 4 Gate 1 preregistration")
    parser.add_argument("--repository-root", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = seal_gate1(args.repository_root)
    except (Gate1SealError, OSError, ValueError) as exc:
        code = exc.code if isinstance(exc, Gate1SealError) else "READINESS_MANIFEST_MISMATCH"
        print(json.dumps({
            "status": "GATE1_FAILED",
            "error_code": code,
            "message": str(exc),
        }, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps({
        "status": result.manifest.status,
        "manifest": result.manifest_identity.model_dump(mode="json"),
    }, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
