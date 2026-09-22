"""Materialize the frozen generation-2 grid manifest as immutable evidence.

Writes the canonical, self-contained manifest (including its own
self-excluding ``manifest_sha256``) to
``data/governance/generation2-grid-manifest.json`` and verifies that the
embedded hash equals the hash of the manifest with that field removed. This is
the content-addressed pattern used across the repo's governance artifacts.
Idempotent: re-running produces byte-identical output.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from investment_tracker.quant.generation2.grid import (  # noqa: E402
    canonical_grid_manifest,
    canonical_grid_manifest_bytes,
)

TARGET = REPO_ROOT / "data" / "governance" / "generation2-grid-manifest.json"


def main() -> int:
    manifest = canonical_grid_manifest()
    embedded = manifest["manifest_sha256"]
    # Self-excluding verification: hash of the manifest WITHOUT its own field.
    payload = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    recomputed = hashlib.sha256(canonical_grid_manifest_bytes(payload)).hexdigest()
    if recomputed != embedded:
        print(f"FAIL: self-hash mismatch {recomputed} != {embedded}")
        return 1

    # Materialize the full self-contained manifest (with the embedded hash).
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(canonical_grid_manifest_bytes(manifest))

    on_disk = json.loads(TARGET.read_bytes())
    assert on_disk["manifest_sha256"] == embedded
    assert on_disk["total_candidates"] == 162
    print(f"manifest_sha256={embedded}")
    print(f"total_candidates={on_disk['total_candidates']}")
    print(f"written={TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
