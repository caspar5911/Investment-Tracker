"""Generation-2 deterministic reproduction check (C6).

Re-runs the sealed VALIDATION campaign from the legitimate
content-hash-verified research cache snapshot and confirms that the
regenerated report is byte-identical to the committed sealed VALIDATION
report. The result is sealed as a new self-verifying, content-addressed
artifact that chains the TRAIN report hash, the sealed VALIDATION report
hash, and (when present) the survivor-freeze hash, plus the per-symbol
content hashes of the snapshot the reproduction consumed.

Governance invariants enforced here (fail-closed):

- the reproduced payload must be byte-identical to the sealed report; any
  divergence is ``REPRODUCTION_MISMATCH`` and is never sealed;
- no separate-provider snapshot exists in this environment, so the artifact
  always records ``independent_source_established: false`` and notes that the
  Generation-1 ``INDEPENDENT_SOURCE_SNAPSHOT_MISSING`` limitation remains
  unresolved -- this framework never claims to resolve it;
- the report is written exclusively (``REPRODUCTION_EXISTS``) and
  verification recomputes the content hash and every recorded hash field
  (``REPRODUCTION_TAMPERED`` on any divergence).
"""

from __future__ import annotations

import argparse
import json
import platform
import re
from pathlib import Path

import numpy as np
import pandas as pd

from investment_tracker.quant.generation2.campaign import (
    REPORT_NAME as TRAIN_REPORT_NAME,
    CampaignError,
    canonical_bytes,
    content_sha256,
    verify_train_report,
)
from investment_tracker.quant.generation2.grid import RESEARCH_SYMBOLS
from investment_tracker.quant.generation2.survivor_freeze import (
    FREEZE_REPORT_NAME,
    verify_survivor_freeze,
)
from investment_tracker.quant.generation2.validation import (
    REPORT_NAME as VALIDATION_REPORT_NAME,
    build_validation_payload,
    run_validation_campaign,
    verify_validation_report,
)

REPRODUCTION_SCHEMA = "GENERATION2-REPRODUCTION-v1"
REPRODUCTION_CONFIRMED = "REPRODUCTION_CONFIRMED"
REPRODUCTION_REPORT_NAME = "reproduction-report.json"

_INDEPENDENCE_NOTE = (
    "No separate-provider snapshot exists in this environment; the campaign "
    "was reproduced from the content-hash-verified primary research cache "
    "snapshot only. The Generation-1 INDEPENDENT_SOURCE_SNAPSHOT_MISSING "
    "limitation remains unresolved."
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

__all__ = [
    "INDEPENDENCE_NOTE",
    "REPRODUCTION_CONFIRMED",
    "REPRODUCTION_REPORT_NAME",
    "REPRODUCTION_SCHEMA",
    "build_reproduction_report",
    "default_environment",
    "main",
    "run_reproduction",
    "seal_reproduction_report",
    "verify_reproduction_report",
]

INDEPENDENCE_NOTE = _INDEPENDENCE_NOTE


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_environment() -> dict:
    """Runtime versions recorded with the reproduction so it is auditable."""
    return {
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }


def build_reproduction_report(
    sealed_validation_payload: dict,
    reproduced_payload: dict,
    *,
    snapshot_symbols: dict[str, str],
    research_boundary_provenance_sha256: str,
    environment: dict,
    survivor_freeze_sha256: str | None = None,
) -> dict:
    """Confirm byte identity between the sealed and reproduced VALIDATION payloads.

    Both payloads must carry their self-excluding ``report_sha256`` (the
    verified sealed payload and the freshly built reproduced payload).
    Raises ``REPRODUCTION_MISMATCH`` -- fail-closed, never sealable -- when
    the canonical bytes differ.
    """
    if canonical_bytes(sealed_validation_payload) != canonical_bytes(reproduced_payload):
        raise CampaignError(
            "REPRODUCTION_MISMATCH",
            "the reproduced VALIDATION payload is not byte-identical to the sealed report",
        )
    return {
        "schema_version": REPRODUCTION_SCHEMA,
        "status": REPRODUCTION_CONFIRMED,
        "train_report_sha256": sealed_validation_payload.get("train_report_sha256"),
        "validation_report_sha256": sealed_validation_payload.get("report_sha256"),
        "survivor": sealed_validation_payload.get("survivor"),
        "survivor_freeze_sha256": survivor_freeze_sha256,
        "snapshot_symbols": {
            symbol: str(snapshot_symbols[symbol]) for symbol in RESEARCH_SYMBOLS
        },
        "research_boundary_provenance_sha256": research_boundary_provenance_sha256,
        "independent_source_established": False,
        "independent_source_note": _INDEPENDENCE_NOTE,
        "environment": environment,
    }


def seal_reproduction_report(payload: dict, root: Path | str) -> dict:
    """Seal the reproduction report exclusively under ``root``."""
    root = Path(root)
    report_path = root / REPRODUCTION_REPORT_NAME
    if report_path.exists():
        raise CampaignError(
            "REPRODUCTION_EXISTS",
            f"a reproduction report already exists at {report_path}",
        )
    sealed = dict(payload)
    sealed["report_sha256"] = content_sha256(sealed)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with report_path.open("xb") as handle:
            handle.write(canonical_bytes(sealed))
    except FileExistsError as exc:
        raise CampaignError(
            "REPRODUCTION_EXISTS",
            f"a reproduction report already exists at {report_path}",
        ) from exc
    return sealed


def verify_reproduction_report(path: Path | str) -> dict:
    """Verify a sealed reproduction report; fail closed on any divergence."""
    payload = json.loads(Path(path).read_bytes().decode("utf-8"))
    claimed = payload.pop("report_sha256", None)
    if claimed is None or content_sha256(payload) != claimed:
        raise CampaignError(
            "REPRODUCTION_TAMPERED",
            f"report content hash does not match {Path(path)}",
        )
    if payload.get("schema_version") != REPRODUCTION_SCHEMA:
        raise CampaignError(
            "REPRODUCTION_TAMPERED",
            f"schema_version is {payload.get('schema_version')!r}, expected {REPRODUCTION_SCHEMA!r}",
        )
    if payload.get("status") != REPRODUCTION_CONFIRMED:
        raise CampaignError(
            "REPRODUCTION_TAMPERED",
            f"status is {payload.get('status')!r}, expected {REPRODUCTION_CONFIRMED!r}",
        )
    for key in ("train_report_sha256", "validation_report_sha256"):
        value = payload.get(key)
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise CampaignError(
                "REPRODUCTION_TAMPERED", f"{key} is not a 64-char sha256"
            )
    freeze_sha = payload.get("survivor_freeze_sha256")
    if freeze_sha is not None and not (
        isinstance(freeze_sha, str) and _SHA256.fullmatch(freeze_sha)
    ):
        raise CampaignError(
            "REPRODUCTION_TAMPERED", "survivor_freeze_sha256 is not a 64-char sha256"
        )
    snapshot_symbols = payload.get("snapshot_symbols")
    if not isinstance(snapshot_symbols, dict) or set(snapshot_symbols) != set(
        RESEARCH_SYMBOLS
    ):
        raise CampaignError(
            "REPRODUCTION_TAMPERED",
            "snapshot_symbols must cover exactly the frozen research symbols",
        )
    for symbol, digest in snapshot_symbols.items():
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise CampaignError(
                "REPRODUCTION_TAMPERED", f"snapshot hash for {symbol} is not a 64-char sha256"
            )
    provenance_sha = payload.get("research_boundary_provenance_sha256")
    if not isinstance(provenance_sha, str) or not _SHA256.fullmatch(provenance_sha):
        raise CampaignError(
            "REPRODUCTION_TAMPERED",
            "research_boundary_provenance_sha256 is not a 64-char sha256",
        )
    if payload.get("independent_source_established") is not False:
        raise CampaignError(
            "REPRODUCTION_TAMPERED",
            "independent_source_established must be false until a separate-provider snapshot exists",
        )
    environment = payload.get("environment")
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(value, str) and value
        for key, value in environment.items()
    ):
        raise CampaignError(
            "REPRODUCTION_TAMPERED", "environment must map names to version strings"
        )
    payload["report_sha256"] = claimed
    return payload


def run_reproduction(
    evidence_root: Path | str,
    cache_root: Path | str | None = None,
    *,
    boundary=None,
) -> dict:
    """Re-run the sealed VALIDATION campaign and seal the reproduction report.

    Verifies the committed TRAIN/VALIDATION reports (and the survivor-freeze
    artifact when present), loads the research boundary (or accepts a supplied
    boundary for testing), re-runs the campaign with the sealed friction
    cases, rebuilds the payload through the shared C4 authority, and seals the
    byte-identity confirmation under ``evidence_root``.
    """
    evidence_root = Path(evidence_root)
    train_payload = verify_train_report(evidence_root / TRAIN_REPORT_NAME)
    sealed_validation = verify_validation_report(evidence_root / VALIDATION_REPORT_NAME)
    freeze_path = evidence_root / FREEZE_REPORT_NAME
    survivor_freeze_sha = (
        verify_survivor_freeze(freeze_path)["report_sha256"]
        if freeze_path.exists()
        else None
    )
    if boundary is None:
        from investment_tracker.quant.generation2.research_boundary import (
            load_research_boundary,
        )

        boundary = load_research_boundary(Path(cache_root), Path(cache_root))
    bars = boundary.validation_bars()
    friction_cases = tuple(int(bps) for bps in sealed_validation["friction_cases_bps"])
    result = run_validation_campaign(train_payload, bars, friction_cases)
    reproduced = build_validation_payload(result, friction_cases)
    payload = build_reproduction_report(
        sealed_validation,
        reproduced,
        snapshot_symbols={symbol: boundary.content_sha256(symbol) for symbol in RESEARCH_SYMBOLS},
        research_boundary_provenance_sha256=boundary.provenance.provenance_sha256,
        environment=default_environment(),
        survivor_freeze_sha256=survivor_freeze_sha,
    )
    return seal_reproduction_report(payload, evidence_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-run the generation-2 VALIDATION campaign and seal the reproduction report."
    )
    parser.add_argument(
        "--evidence-root",
        default=str(_repo_root() / "data" / "governance" / "generation2-campaign"),
        help="directory containing the sealed TRAIN/VALIDATION reports and receiving the reproduction report",
    )
    parser.add_argument(
        "--cache-root",
        default=str(_repo_root() / "data" / "cache"),
        help="local Phase-3 cache root used to load the research boundary",
    )
    args = parser.parse_args(argv)
    payload = run_reproduction(Path(args.evidence_root), Path(args.cache_root))
    print(f"schema_version={payload['schema_version']}")
    print(f"status={payload['status']}")
    print(f"train_report_sha256={payload['train_report_sha256']}")
    print(f"validation_report_sha256={payload['validation_report_sha256']}")
    print(f"survivor={payload['survivor']}")
    print(f"survivor_freeze_sha256={payload['survivor_freeze_sha256']}")
    print(f"independent_source_established={payload['independent_source_established']}")
    print(f"report_sha256={payload['report_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
