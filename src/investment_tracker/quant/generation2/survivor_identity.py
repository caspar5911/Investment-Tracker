"""Generation-2 survivor implementation + binding identity (additive freeze).

The sealed ``survivor-freeze`` artifact records *which* candidate survived, but
it does not explicitly freeze the two identity values the governance model
requires before the real final-holdout boundary may be crossed:

- ``implementation_sha256`` -- the content identity of the exact five
  execution-semantic source modules (``grid``, ``strategy``, ``accounting``,
  ``metrics``, ``performance``) that the survivor's signals are computed by;
- ``binding_sha256`` -- the content identity of the survivor binding: the
  frozen candidate, its exact frozen-grid coordinates, the implementation
  hash, and the chained self-hashes of all six prior sealed Generation-2
  campaign artifacts.

This module freezes both additively into a new self-verifying, content-addressed
artifact (``survivor-identity.json``). It reuses the repository's canonical
JSON / hashing utilities, verifies the existing self-hashes of the six sealed
artifacts before trusting any field, and fails closed with stable error codes.
No market data is read, no holdout symbol is selected, and no re-run of the
TRAIN or VALIDATION campaign is performed or required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from investment_tracker.quant.generation2.campaign import (
    REPORT_NAME as TRAIN_REPORT_NAME,
    CampaignError,
    canonical_bytes,
    content_sha256,
    verify_train_report,
)
from investment_tracker.quant.generation2.grid import GRID_MANIFEST_SCHEMA
from investment_tracker.quant.generation2.reproduction import (
    REPRODUCTION_REPORT_NAME,
    verify_reproduction_report,
)
from investment_tracker.quant.generation2.survivor_freeze import (
    FREEZE_REPORT_NAME,
    verify_survivor_freeze,
)
from investment_tracker.quant.generation2.survivor_rehearsal import (
    SURVIVOR_REHEARSAL_REPORT_NAME,
    verify_survivor_rehearsal_report,
)
from investment_tracker.quant.generation2.validation import (
    REPORT_NAME as VALIDATION_REPORT_NAME,
    frozen_candidate_by_id,
    verify_validation_report,
)

SURVIVOR_IDENTITY_SCHEMA = "GENERATION2-SURVIVOR-IDENTITY-v1"
SURVIVOR_IDENTITY_STATUS = "SURVIVOR_IMPLEMENTATION_AND_BINDING_FROZEN"
GENERATION = "GENERATION_2"
IDENTITY_REPORT_NAME = "survivor-identity.json"

IMPLEMENTATION_SURFACE_SCHEMA = "GENERATION2-IMPLEMENTATION-SURFACE-v1"
EXECUTION_INTERFACE = "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1"
BINDING_SCHEMA = "GENERATION2-SURVIVOR-BINDING-v1"

EXPECTED_CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
EXPECTED_FAMILY = "G2-A"

# The exact five execution-semantic modules that define the survivor's signal
# computation. Deliberately EXCLUDES validation.py, campaign.py, reproduction.py,
# survivor_rehearsal.py, and phase7_entry.py: those govern campaign orchestration,
# evidence sealing, rehearsal, and live entry -- not the execution semantics of the
# signals themselves.
IMPLEMENTATION_SOURCE_FILES = (
    "src/investment_tracker/quant/generation2/grid.py",
    "src/investment_tracker/quant/generation2/strategy.py",
    "src/investment_tracker/quant/generation2/accounting.py",
    "src/investment_tracker/quant/generation2/metrics.py",
    "src/investment_tracker/quant/generation2/performance.py",
)

# Chained self-hashes of the six prior sealed artifacts, in campaign order.
CHAINED_KEYS = (
    "grid_manifest_sha256",
    "train_report_sha256",
    "validation_report_sha256",
    "survivor_freeze_sha256",
    "reproduction_report_sha256",
    "survivor_rehearsal_sha256",
)

GRID_MANIFEST_NAME = "generation2-grid-manifest.json"

__all__ = [
    "BINDING_SCHEMA",
    "CHAINED_KEYS",
    "EXECUTION_INTERFACE",
    "EXPECTED_CANDIDATE_ID",
    "EXPECTED_FAMILY",
    "GENERATION",
    "IMPLEMENTATION_SOURCE_FILES",
    "IMPLEMENTATION_SURFACE_SCHEMA",
    "IDENTITY_REPORT_NAME",
    "SURVIVOR_IDENTITY_SCHEMA",
    "SURVIVOR_IDENTITY_STATUS",
    "build_survivor_identity",
    "seal_survivor_identity",
    "seal_survivor_identity_from_evidence",
    "verify_survivor_identity",
    "main",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_evidence_root() -> Path:
    return _repo_root() / "data" / "governance" / "generation2-campaign"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _implementation_payload(repo_root: Path) -> dict:
    """Hash the exact bytes of the five execution-semantic source modules."""
    source_sha256 = {}
    for rel in IMPLEMENTATION_SOURCE_FILES:
        path = repo_root / rel
        if not path.is_file():
            raise CampaignError(
                "SURVIVOR_IDENTITY_SOURCE_MISSING",
                f"implementation source {rel} is missing from {repo_root}",
            )
        source_sha256[rel] = _sha256_file(path)
    return {
        "schema_version": IMPLEMENTATION_SURFACE_SCHEMA,
        "interface": EXECUTION_INTERFACE,
        "source_sha256": source_sha256,
    }


def _verify_grid_manifest(path: Path) -> dict:
    """Verify the sealed grid manifest's self-hash and schema (no dedicated
    ``verify_grid_manifest`` exists in grid.py, so this is inline)."""
    if not path.is_file():
        raise CampaignError(
            "SURVIVOR_IDENTITY_EVIDENCE_TAMPERED", f"grid manifest missing at {path}"
        )
    payload = json.loads(path.read_bytes().decode("utf-8"))
    claimed = payload.pop("manifest_sha256", None)
    if claimed is None or content_sha256(payload) != claimed:
        raise CampaignError(
            "SURVIVOR_IDENTITY_EVIDENCE_TAMPERED",
            "grid manifest content hash does not match",
        )
    if payload.get("schema_version") != GRID_MANIFEST_SCHEMA:
        raise CampaignError(
            "SURVIVOR_IDENTITY_EVIDENCE_TAMPERED",
            f"grid manifest schema_version is {payload.get('schema_version')!r}, "
            f"expected {GRID_MANIFEST_SCHEMA!r}",
        )
    payload["manifest_sha256"] = claimed
    return payload


def _verify_artifact(kind: str, verifier, path: Path) -> dict:
    if not path.is_file():
        raise CampaignError(
            "SURVIVOR_IDENTITY_EVIDENCE_TAMPERED",
            f"{kind} artifact missing at {path}",
        )
    try:
        return verifier(path)
    except CampaignError as exc:
        raise CampaignError(
            "SURVIVOR_IDENTITY_EVIDENCE_TAMPERED",
            f"{kind} artifact failed verification ({exc.code})",
        ) from exc


def _verify_all_artifacts(evidence_root: Path) -> dict:
    """Verify the six sealed artifacts' self-hashes and return their self-hashes.

    The survivor survivor id is taken from the sealed VALIDATION report and
    cross-checked against the survivor-freeze, reproduction, and rehearsal
    reports; any disagreement is a candidate-mismatch failure.
    """
    grid = _verify_grid_manifest(evidence_root.parent / GRID_MANIFEST_NAME)
    train = _verify_artifact(
        "train", verify_train_report, evidence_root / TRAIN_REPORT_NAME
    )
    validation = _verify_artifact(
        "validation", verify_validation_report, evidence_root / VALIDATION_REPORT_NAME
    )
    freeze = _verify_artifact(
        "survivor-freeze", verify_survivor_freeze, evidence_root / FREEZE_REPORT_NAME
    )
    repro = _verify_artifact(
        "reproduction", verify_reproduction_report, evidence_root / REPRODUCTION_REPORT_NAME
    )
    rehearsal = _verify_artifact(
        "rehearsal",
        verify_survivor_rehearsal_report,
        evidence_root / SURVIVOR_REHEARSAL_REPORT_NAME,
    )

    survivor = validation.get("survivor")
    if not isinstance(survivor, str) or not survivor:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_MISMATCH",
            "the sealed VALIDATION report carries no survivor",
        )
    if freeze.get("survivor", {}).get("candidate_id") != survivor:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_MISMATCH",
            "survivor-freeze survivor differs from the VALIDATION survivor",
        )
    if repro.get("survivor") != survivor:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_MISMATCH",
            "reproduction survivor differs from the VALIDATION survivor",
        )
    if rehearsal.get("survivor") != survivor:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_MISMATCH",
            "rehearsal survivor differs from the VALIDATION survivor",
        )

    return {
        "survivor": survivor,
        "survivor_binding": freeze["survivor"]["binding"],
        "grid_manifest_sha256": grid["manifest_sha256"],
        "train_report_sha256": train["report_sha256"],
        "validation_report_sha256": validation["report_sha256"],
        "survivor_freeze_sha256": freeze["report_sha256"],
        "reproduction_report_sha256": repro["report_sha256"],
        "survivor_rehearsal_sha256": rehearsal["report_sha256"],
    }


def build_survivor_identity(evidence_root: Path | str, repo_root: Path | str) -> dict:
    """Derive the survivor-identity payload from the sealed campaign evidence.

    Verifies all six sealed artifacts (self-hash first), pins the candidate to
    the expected frozen survivor and its exact grid binding, hashes the five
    execution-semantic source modules, and computes ``implementation_sha256``
    and ``binding_sha256``. The returned payload has NO ``report_sha256``.
    """
    evidence_root = Path(evidence_root)
    repo_root = Path(repo_root)
    artifacts = _verify_all_artifacts(evidence_root)

    candidate_id = artifacts["survivor"]
    if candidate_id != EXPECTED_CANDIDATE_ID:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_MISMATCH",
            f"sealed survivor {candidate_id!r} is not the frozen candidate "
            f"{EXPECTED_CANDIDATE_ID!r}",
        )
    try:
        frozen = frozen_candidate_by_id(candidate_id)
    except CampaignError as exc:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_NOT_IN_FROZEN_GRID",
            f"candidate {candidate_id!r} does not bind to the frozen grid",
        ) from exc
    candidate_binding = frozen.to_manifest_dict()
    if candidate_binding != artifacts["survivor_binding"]:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_BINDING_MISMATCH",
            "the survivor-freeze binding differs from the frozen grid binding",
        )
    if frozen.family != EXPECTED_FAMILY:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_MISMATCH",
            f"frozen candidate family is {frozen.family!r}, expected {EXPECTED_FAMILY!r}",
        )

    implementation = _implementation_payload(repo_root)
    implementation_sha256 = content_sha256(implementation)

    binding_payload = {
        "schema_version": BINDING_SCHEMA,
        "candidate_id": candidate_id,
        "family": frozen.family,
        "candidate_binding": candidate_binding,
        "implementation_sha256": implementation_sha256,
        "grid_manifest_sha256": artifacts["grid_manifest_sha256"],
        "train_report_sha256": artifacts["train_report_sha256"],
        "validation_report_sha256": artifacts["validation_report_sha256"],
        "survivor_freeze_sha256": artifacts["survivor_freeze_sha256"],
        "reproduction_report_sha256": artifacts["reproduction_report_sha256"],
        "survivor_rehearsal_sha256": artifacts["survivor_rehearsal_sha256"],
    }
    binding_sha256 = content_sha256(binding_payload)

    return {
        "schema_version": SURVIVOR_IDENTITY_SCHEMA,
        "status": SURVIVOR_IDENTITY_STATUS,
        "generation": GENERATION,
        "candidate_id": candidate_id,
        "family": frozen.family,
        "candidate_binding": candidate_binding,
        "implementation_surface": implementation,
        "implementation_sha256": implementation_sha256,
        "binding_sha256": binding_sha256,
        "grid_manifest_sha256": artifacts["grid_manifest_sha256"],
        "train_report_sha256": artifacts["train_report_sha256"],
        "validation_report_sha256": artifacts["validation_report_sha256"],
        "survivor_freeze_sha256": artifacts["survivor_freeze_sha256"],
        "reproduction_report_sha256": artifacts["reproduction_report_sha256"],
        "survivor_rehearsal_sha256": artifacts["survivor_rehearsal_sha256"],
    }


def seal_survivor_identity(payload: dict, evidence_root: Path | str) -> dict:
    """Seal the identity exclusively under ``evidence_root``; fail closed if it
    already exists."""
    evidence_root = Path(evidence_root)
    report_path = evidence_root / IDENTITY_REPORT_NAME
    if report_path.exists():
        raise CampaignError(
            "SURVIVOR_IDENTITY_EXISTS",
            f"a survivor identity already exists at {report_path}",
        )
    sealed = dict(payload)
    sealed["report_sha256"] = content_sha256(sealed)
    evidence_root.mkdir(parents=True, exist_ok=True)
    try:
        with report_path.open("xb") as handle:
            handle.write(canonical_bytes(sealed))
    except FileExistsError as exc:
        raise CampaignError(
            "SURVIVOR_IDENTITY_EXISTS",
            f"a survivor identity already exists at {report_path}",
        ) from exc
    return sealed


def verify_survivor_identity(evidence_root: Path | str, repo_root: Path | str) -> dict:
    """Verify the sealed survivor identity; fail closed on any drift.

    Checks, in order: the identity's own self-hash; schema/status; the pinned
    candidate id, family, and exact grid binding; the exact five-file
    implementation surface and each source file's bytes; the recomputed
    ``implementation_sha256``; the six sealed artifacts (self-hash first) and
    every chained ``*_sha256``; and the recomputed ``binding_sha256``.
    """
    evidence_root = Path(evidence_root)
    repo_root = Path(repo_root)
    path = evidence_root / IDENTITY_REPORT_NAME
    if not path.is_file():
        raise CampaignError(
            "SURVIVOR_IDENTITY_MISSING", f"survivor identity missing at {path}"
        )
    payload = json.loads(path.read_bytes().decode("utf-8"))
    claimed = payload.pop("report_sha256", None)
    if claimed is None or content_sha256(payload) != claimed:
        raise CampaignError(
            "SURVIVOR_IDENTITY_TAMPERED",
            f"identity content hash does not match {path}",
        )
    if payload.get("schema_version") != SURVIVOR_IDENTITY_SCHEMA:
        raise CampaignError(
            "SURVIVOR_IDENTITY_TAMPERED",
            f"schema_version is {payload.get('schema_version')!r}, expected "
            f"{SURVIVOR_IDENTITY_SCHEMA!r}",
        )
    if payload.get("status") != SURVIVOR_IDENTITY_STATUS:
        raise CampaignError(
            "SURVIVOR_IDENTITY_TAMPERED",
            f"status is {payload.get('status')!r}, expected {SURVIVOR_IDENTITY_STATUS!r}",
        )

    candidate_id = payload.get("candidate_id")
    if candidate_id != EXPECTED_CANDIDATE_ID:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_MISMATCH",
            f"candidate_id {candidate_id!r} is not the frozen candidate "
            f"{EXPECTED_CANDIDATE_ID!r}",
        )
    try:
        frozen = frozen_candidate_by_id(candidate_id)
    except CampaignError as exc:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_NOT_IN_FROZEN_GRID",
            f"candidate {candidate_id!r} does not bind to the frozen grid",
        ) from exc
    if payload.get("family") != frozen.family:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_MISMATCH",
            f"family {payload.get('family')!r} does not match the frozen grid",
        )
    if payload.get("candidate_binding") != frozen.to_manifest_dict():
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_BINDING_MISMATCH",
            "candidate_binding does not match the frozen grid binding",
        )

    surface = payload.get("implementation_surface")
    if (
        not isinstance(surface, dict)
        or surface.get("schema_version") != IMPLEMENTATION_SURFACE_SCHEMA
        or surface.get("interface") != EXECUTION_INTERFACE
    ):
        raise CampaignError(
            "SURVIVOR_IDENTITY_TAMPERED", "implementation surface is malformed"
        )
    recorded = surface.get("source_sha256")
    if not isinstance(recorded, dict) or set(recorded) != set(IMPLEMENTATION_SOURCE_FILES):
        raise CampaignError(
            "SURVIVOR_IDENTITY_TAMPERED",
            "implementation source set does not match the frozen five-file surface",
        )
    for rel in IMPLEMENTATION_SOURCE_FILES:
        source_path = repo_root / rel
        if not source_path.is_file():
            raise CampaignError(
                "SURVIVOR_IDENTITY_SOURCE_MISSING",
                f"implementation source {rel} is missing from {repo_root}",
            )
        actual = _sha256_file(source_path)
        if actual != recorded.get(rel):
            raise CampaignError(
                "SURVIVOR_IDENTITY_IMPLEMENTATION_DRIFT",
                f"{rel} bytes changed since the identity was sealed",
            )
    impl_payload = {
        "schema_version": IMPLEMENTATION_SURFACE_SCHEMA,
        "interface": EXECUTION_INTERFACE,
        "source_sha256": recorded,
    }
    if content_sha256(impl_payload) != payload.get("implementation_sha256"):
        raise CampaignError(
            "SURVIVOR_IDENTITY_IMPLEMENTATION_SHA_MISMATCH",
            "implementation_sha256 does not match the recorded surface",
        )

    artifacts = _verify_all_artifacts(evidence_root)
    if artifacts["survivor"] != candidate_id:
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_MISMATCH",
            "the sealed survivor differs from the identity candidate",
        )
    if artifacts["survivor_binding"] != payload.get("candidate_binding"):
        raise CampaignError(
            "SURVIVOR_IDENTITY_CANDIDATE_BINDING_MISMATCH",
            "the sealed survivor binding differs from the identity binding",
        )
    for key in CHAINED_KEYS:
        if payload.get(key) != artifacts[key]:
            raise CampaignError(
                "SURVIVOR_IDENTITY_CHAINED_HASH_MISMATCH",
                f"{key} does not match the re-verified sealed artifact",
            )

    binding_payload = {
        "schema_version": BINDING_SCHEMA,
        "candidate_id": candidate_id,
        "family": payload["family"],
        "candidate_binding": payload["candidate_binding"],
        "implementation_sha256": payload["implementation_sha256"],
        **{key: payload[key] for key in CHAINED_KEYS},
    }
    if content_sha256(binding_payload) != payload.get("binding_sha256"):
        raise CampaignError(
            "SURVIVOR_IDENTITY_BINDING_SHA_MISMATCH",
            "binding_sha256 does not match the recorded binding payload",
        )

    payload["report_sha256"] = claimed
    return payload


def seal_survivor_identity_from_evidence(
    evidence_root: Path | str, repo_root: Path | str
) -> dict:
    """Build and seal the identity from the sealed campaign evidence in one step."""
    return seal_survivor_identity(
        build_survivor_identity(evidence_root, repo_root), evidence_root
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze the generation-2 survivor implementation and binding identity."
    )
    parser.add_argument(
        "--evidence-root",
        default=str(_default_evidence_root()),
        help="directory containing the six sealed Generation-2 artifacts and receiving survivor-identity.json",
    )
    parser.add_argument(
        "--repo-root",
        default=str(_repo_root()),
        help="repository root used to locate the five execution-semantic source modules",
    )
    args = parser.parse_args(argv)
    payload = seal_survivor_identity_from_evidence(
        Path(args.evidence_root), Path(args.repo_root)
    )
    print(f"schema_version={payload['schema_version']}")
    print(f"status={payload['status']}")
    print(f"candidate_id={payload['candidate_id']}")
    print(f"family={payload['family']}")
    print(f"implementation_sha256={payload['implementation_sha256']}")
    print(f"binding_sha256={payload['binding_sha256']}")
    print(f"report_sha256={payload['report_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
