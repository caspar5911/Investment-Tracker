from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from investment_tracker.quant.phase4.preregistration.canonical import canonical_json_bytes

from .methodology import (
    PHASE4_AUDIT_CONTENT_SHA256,
    PHASE4_DECISION_CONTENT_SHA256,
    PHASE4_FINALIZATION_COMMIT,
    PHASE4_MANIFEST_CONTENT_SHA256,
    SELECTED_BINDING_SHA256,
    SELECTED_CANDIDATE_ID,
)


def _write(root: Path, kind: str, payload: dict[str, object]) -> dict[str, str]:
    raw = canonical_json_bytes(payload)
    digest = sha256(raw).hexdigest()
    path = root / kind / "sha256" / digest / "record.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("PHASE5_ARTIFACT_COLLISION")
    path.write_bytes(raw)
    return {"kind": kind, "content_sha256": digest, "path": path.as_posix()}


def seal_evaluation(
    results_root: Path,
    evaluation: dict[str, object],
    *,
    source_revision: str,
    spec_content_sha256: str,
) -> dict[str, object]:
    if evaluation.get("status") not in {
        "PHASE5_DURABILITY_SUPPORTED",
        "PHASE5_DURABILITY_CONTRADICTED",
    }:
        raise ValueError("PHASE5_SEAL_REQUIRES_DECISION_GRADE_EVALUATION")

    root = Path(results_root).resolve()
    evaluation_ref = _write(root, "evaluation", evaluation)
    decision_payload = {
        "schema_version": "PHASE5-FINAL-DECISION-v1",
        "status": evaluation["status"],
        "reasons": evaluation.get("reasons", []),
        "evaluation": evaluation_ref,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "selected_binding_sha256": SELECTED_BINDING_SHA256,
        "safety": evaluation.get("safety", {}),
    }
    decision_ref = _write(root, "decision", decision_payload)
    manifest_payload = {
        "schema_version": "PHASE5-FINALIZATION-MANIFEST-v1",
        "status": "PHASE5_SEALED",
        "source_revision": source_revision,
        "spec_content_sha256": spec_content_sha256,
        "phase4_finalization_commit": PHASE4_FINALIZATION_COMMIT,
        "phase4_decision_content_sha256": PHASE4_DECISION_CONTENT_SHA256,
        "phase4_audit_content_sha256": PHASE4_AUDIT_CONTENT_SHA256,
        "phase4_manifest_content_sha256": PHASE4_MANIFEST_CONTENT_SHA256,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "selected_binding_sha256": SELECTED_BINDING_SHA256,
        "evaluation": evaluation_ref,
        "decision": decision_ref,
        "safety": evaluation.get("safety", {}),
    }
    manifest_ref = _write(root, "manifest", manifest_payload)
    return {**manifest_payload, "manifest": manifest_ref}
