"""Provider-free CLI for sealing the Phase 4 Gate 2 research engine.

The only accepted option is --repository-root.  On success a single line of
canonical JSON reports the SEALED status and the manifest identity; on
failure the frozen Gate 2 failure code is written to stderr and the process
exits nonzero.  There is no data, candidate, parameter, provider, export,
order, or trading surface here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import Gate2SealError
from .seal import seal_gate2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="phase4-gate2-seal",
        description=(
            "Seal the deterministic Phase 4 Gate 2 paper-only research "
            "engine and publish its content-addressed manifest."
        ),
    )
    parser.add_argument(
        "--repository-root",
        required=True,
        help="repository root containing the sealed Gate 1 authority",
    )
    args = parser.parse_args(argv)

    try:
        result = seal_gate2(Path(args.repository_root))
    except Gate2SealError as exc:
        print(f"GATE2_SEAL_FAILED {exc.code}", file=sys.stderr)
        return 1

    payload = {
        "status": result.status,
        "manifest": result.manifest.model_dump(mode="json"),
    }
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
