from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from .phase6_contract import verify_phase6_contract
from .release import load_release

SCHEMA = "SUCCESSOR-PHASE6-FINAL-HOLDOUT-CLOSURE-v1"
SUCCESS = "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"
UNKNOWN = "PHASE6_UNKNOWN_ABSTAIN"


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _write_exclusive_verified(path: Path, payload: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise FileExistsError(f"SUCCESSOR_PHASE6_CLOSURE_ALREADY_EXISTS:{path}") from exc
    if path.read_bytes() != payload:
        raise OSError("SUCCESSOR_PHASE6_CLOSURE_READBACK_FAILED")


def close_phase6(
    *,
    contract_path: Path,
    release_path: Path,
    result_path: Path,
    consumption_marker_path: Path,
    acquisition_receipt_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    contract = verify_phase6_contract(contract_path)
    release = load_release(release_path, contract_path=contract_path)
    try:
        result = json.loads(Path(result_path).read_text(encoding="utf-8"))
        marker = json.loads(Path(consumption_marker_path).read_text(encoding="utf-8"))
        receipt = json.loads(Path(acquisition_receipt_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("SUCCESSOR_PHASE6_CLOSURE_EVIDENCE_INVALID") from exc

    status = result.get("status")
    if status not in {SUCCESS, UNKNOWN}:
        raise ValueError("SUCCESSOR_PHASE6_CLOSURE_RESULT_STATUS_INVALID")
    if (
        result.get("one_time_consumed") is not True
        or result.get("candidate_id") != contract["strategy"]["candidate_id"]
        or result.get("locked_symbols") != contract["final_holdout"]["locked_symbols"]
        or result.get("phase7_authorized") is not False
        or result.get("production_readiness_approved") is not False
        or result.get("recon009_status") != "OPEN"
    ):
        raise ValueError("SUCCESSOR_PHASE6_CLOSURE_RESULT_GOVERNANCE_MISMATCH")
    if (
        marker.get("status") != "FINAL_HOLDOUT_RELEASE_CONSUMED"
        or marker.get("release_id") != release["release_id"]
        or marker.get("holdout_id") != release["holdout_id"]
        or marker.get("evaluation_status") != status
        or marker.get("result_readback_verified") is not True
        or marker.get("retry_allowed") is not False
    ):
        raise ValueError("SUCCESSOR_PHASE6_CLOSURE_CONSUMPTION_MISMATCH")
    if (
        receipt.get("status") != "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED"
        or receipt.get("holdout_id") != release["holdout_id"]
        or receipt.get("final_holdout_accessed") is not True
        or receipt.get("performance_inspected") is not False
        or receipt.get("retry_allowed") is not False
    ):
        raise ValueError("SUCCESSOR_PHASE6_CLOSURE_ACQUISITION_MISMATCH")

    closure = {
        "schema_version": SCHEMA,
        "authority": "COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE",
        "status": status,
        "successor_formal_name": contract["successor_formal_name"],
        "candidate_id": contract["strategy"]["candidate_id"],
        "binding_sha256": contract["strategy"]["binding_sha256"],
        "implementation_sha256": contract["strategy"]["implementation_sha256"],
        "successor_normalizer_sha256": contract["methodology"]["successor_normalizer_sha256"],
        "successor_evaluator_sha256": contract["methodology"]["successor_evaluator_sha256"],
        "locked_symbols": list(contract["final_holdout"]["locked_symbols"]),
        "holdout_id": release["holdout_id"],
        "release_id": release["release_id"],
        "phase6_contract_sha256": _sha(contract_path),
        "acquisition_receipt_sha256": _sha(acquisition_receipt_path),
        "release_sha256": _sha(release_path),
        "evaluation_result_sha256": _sha(result_path),
        "evaluation_consumption_marker_sha256": _sha(consumption_marker_path),
        "one_time_semantics": {
            "holdout_consumed": True,
            "retry_authorized": False,
            "symbol_substitution_authorized": False,
            "methodology_change_from_holdout_forbidden": True,
            "parameter_change_from_holdout_forbidden": True,
        },
        "phase7": {
            "eligible_for_independent_entry_review": status == SUCCESS,
            "authorized": False,
            "entry_artifact_created": False,
            "started": False,
        },
        "production_readiness_approved": False,
        "recon009_status": "OPEN",
    }
    if status == UNKNOWN:
        closure["failure_reason"] = result.get("reason", "UNKNOWN_UNSPECIFIED")

    payload = json.dumps(
        closure,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    _write_exclusive_verified(Path(output_path), payload)
    return closure
