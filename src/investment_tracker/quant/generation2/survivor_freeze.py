"""Generation-2 survivor freeze artifact (C5).

Freezes the single VALIDATION survivor's identity -- candidate id, family,
and exact frozen-grid binding -- into a new self-verifying,
content-addressed artifact that chains the content hashes of the sealed
TRAIN and VALIDATION reports. This is the explicit Gen-2 governance record
that a survivor has been selected; no final-holdout step may proceed
without it (and Phase 7 requires, in addition, the real Phase-6 status and
an explicit Gen-2 Phase-7 entry artifact).

Fail-closed error codes:

- ``SURVIVOR_FREEZE_NO_SURVIVOR`` -- the sealed VALIDATION report has no
  survivor (i.e. ``NO_CREDIBLE_GENERATION2_CANDIDATE``);
- ``SURVIVOR_FREEZE_SURVIVOR_NOT_IN_FROZEN_GRID`` -- the named survivor does
  not bind to the frozen generation-2 grid;
- ``SURVIVOR_FREEZE_TRAIN_HASH_MISMATCH`` /
  ``SURVIVOR_FREEZE_VALIDATION_HASH_INVALID`` -- report hash chain broken;
- ``SURVIVOR_FREEZE_EXISTS`` -- a freeze artifact already exists;
- ``SURVIVOR_FREEZE_TAMPERED`` -- any verification divergence.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from investment_tracker.quant.generation2.campaign import (
    CampaignError,
    canonical_bytes,
    content_sha256,
    verify_train_report,
)
from investment_tracker.quant.generation2.validation import (
    STATUS_SURVIVOR,
    REPORT_NAME as VALIDATION_REPORT_NAME,
    frozen_candidate_by_id,
    verify_validation_report,
)

SURVIVOR_FREEZE_SCHEMA = "GENERATION2-SURVIVOR-FREEZE-v1"
SURVIVOR_FREEZE_STATUS = "SURVIVOR_FROZEN_BEFORE_HOLDOUT"
FREEZE_REPORT_NAME = "survivor-freeze.json"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

__all__ = [
    "FREEZE_REPORT_NAME",
    "SURVIVOR_FREEZE_SCHEMA",
    "SURVIVOR_FREEZE_STATUS",
    "build_survivor_freeze",
    "main",
    "seal_survivor_freeze",
    "verify_survivor_freeze",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def build_survivor_freeze(validation_report: dict, train_report: dict) -> dict:
    """Assemble the survivor freeze payload from the two sealed reports.

    Both payloads are expected to be the verified outputs of
    ``verify_validation_report`` / ``verify_train_report``. The payload is
    the freeze content *without* its self hash.
    """
    survivor_id = validation_report.get("survivor")
    if not isinstance(survivor_id, str) or not survivor_id:
        raise CampaignError(
            "SURVIVOR_FREEZE_NO_SURVIVOR",
            "the sealed VALIDATION report has no survivor to freeze",
        )
    try:
        frozen = frozen_candidate_by_id(survivor_id)
    except CampaignError as exc:
        raise CampaignError(
            "SURVIVOR_FREEZE_SURVIVOR_NOT_IN_FROZEN_GRID",
            f"{survivor_id!r} does not bind to the frozen generation-2 grid",
        ) from exc

    validation_sha = validation_report.get("report_sha256")
    if not isinstance(validation_sha, str) or not _SHA256.fullmatch(validation_sha):
        raise CampaignError(
            "SURVIVOR_FREEZE_VALIDATION_HASH_INVALID",
            "the sealed VALIDATION report hash is not a 64-char sha256",
        )
    train_sha = train_report.get("report_sha256")
    if train_sha != validation_report.get("train_report_sha256"):
        raise CampaignError(
            "SURVIVOR_FREEZE_TRAIN_HASH_MISMATCH",
            "TRAIN report hash differs from the hash recorded by the VALIDATION report",
        )

    return {
        "schema_version": SURVIVOR_FREEZE_SCHEMA,
        "status": SURVIVOR_FREEZE_STATUS,
        "survivor": {
            "candidate_id": survivor_id,
            "family": frozen.family,
            "binding": frozen.to_manifest_dict(),
        },
        "train_report_sha256": train_sha,
        "validation_report_sha256": validation_sha,
        "grid_manifest_sha256": validation_report.get("grid_manifest_sha256"),
    }


def seal_survivor_freeze(payload: dict, root: Path | str) -> dict:
    """Seal the freeze artifact exclusively under ``root``.

    Adds the self-excluding ``report_sha256`` and writes the canonical
    payload; refuses to overwrite an existing artifact.
    """
    root = Path(root)
    report_path = root / FREEZE_REPORT_NAME
    if report_path.exists():
        raise CampaignError(
            "SURVIVOR_FREEZE_EXISTS",
            f"a survivor freeze artifact already exists at {report_path}",
        )
    sealed = dict(payload)
    sealed["report_sha256"] = content_sha256(sealed)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with report_path.open("xb") as handle:
            handle.write(canonical_bytes(sealed))
    except FileExistsError as exc:
        raise CampaignError(
            "SURVIVOR_FREEZE_EXISTS",
            f"a survivor freeze artifact already exists at {report_path}",
        ) from exc
    return sealed


def verify_survivor_freeze(path: Path | str) -> dict:
    """Verify a sealed survivor freeze artifact; fail closed on divergence."""
    payload = json.loads(Path(path).read_bytes().decode("utf-8"))
    claimed = payload.pop("report_sha256", None)
    if claimed is None or content_sha256(payload) != claimed:
        raise CampaignError(
            "SURVIVOR_FREEZE_TAMPERED",
            f"freeze artifact content hash does not match {Path(path)}",
        )
    if payload.get("schema_version") != SURVIVOR_FREEZE_SCHEMA:
        raise CampaignError(
            "SURVIVOR_FREEZE_TAMPERED",
            f"schema_version is {payload.get('schema_version')!r}, expected {SURVIVOR_FREEZE_SCHEMA!r}",
        )
    survivor = payload.get("survivor")
    if not isinstance(survivor, dict):
        raise CampaignError(
            "SURVIVOR_FREEZE_TAMPERED", "survivor must be an object"
        )
    survivor_id = survivor.get("candidate_id")
    try:
        frozen = frozen_candidate_by_id(survivor_id)
    except CampaignError as exc:
        raise CampaignError(
            "SURVIVOR_FREEZE_SURVIVOR_NOT_IN_FROZEN_GRID",
            f"{survivor_id!r} does not bind to the frozen generation-2 grid",
        ) from exc
    if survivor.get("family") != frozen.family:
        raise CampaignError(
            "SURVIVOR_FREEZE_TAMPERED",
            f"survivor family for {survivor_id!r} does not match the frozen grid",
        )
    if survivor.get("binding") != frozen.to_manifest_dict():
        raise CampaignError(
            "SURVIVOR_FREEZE_TAMPERED",
            f"survivor binding for {survivor_id!r} does not match the frozen grid",
        )
    for key in ("train_report_sha256", "validation_report_sha256"):
        value = payload.get(key)
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise CampaignError(
                "SURVIVOR_FREEZE_TAMPERED", f"{key} is not a 64-char sha256"
            )
    payload["report_sha256"] = claimed
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze the generation-2 VALIDATION survivor."
    )
    parser.add_argument(
        "--evidence-root",
        default=str(_repo_root() / "data" / "governance" / "generation2-campaign"),
        help="directory containing the sealed TRAIN and VALIDATION reports",
    )
    args = parser.parse_args(argv)

    from investment_tracker.quant.generation2.campaign import REPORT_NAME as TRAIN_REPORT_NAME

    evidence_root = Path(args.evidence_root)
    validation_payload = verify_validation_report(evidence_root / VALIDATION_REPORT_NAME)
    if validation_payload.get("status") != STATUS_SURVIVOR:
        print(f"status={validation_payload.get('status')}")
        print("no survivor to freeze; generation 2 terminated per frozen rules")
        return 0
    train_payload = verify_train_report(evidence_root / TRAIN_REPORT_NAME)
    payload = build_survivor_freeze(validation_payload, train_payload)
    sealed = seal_survivor_freeze(payload, evidence_root)
    print(f"schema_version={sealed['schema_version']}")
    print(f"status={sealed['status']}")
    print(f"survivor={sealed['survivor']['candidate_id']}")
    print(f"family={sealed['survivor']['family']}")
    print(f"train_report_sha256={sealed['train_report_sha256']}")
    print(f"validation_report_sha256={sealed['validation_report_sha256']}")
    print(f"grid_manifest_sha256={sealed['grid_manifest_sha256']}")
    print(f"report_sha256={sealed['report_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
