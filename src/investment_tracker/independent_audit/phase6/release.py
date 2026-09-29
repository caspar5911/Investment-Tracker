from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from .authority import (
    AcquisitionAuthorization,
    CONTRACT_SHA256,
    LOCKED_SYMBOLS,
    SELECTED_BINDING_SHA256,
    SELECTED_CANDIDATE_ID,
    SELECTED_IMPLEMENTATION_SHA256,
    VirginHoldoutAttestation,
    canonical_json_bytes,
    load_acquisition_authorization,
    load_frozen_contract,
    sha256_bytes,
)


def issue_acquisition_authorization(
    *,
    contract_path: Path,
    attestation_path: Path,
    ci_head_sha: str,
    ci_run_id: int,
    output_path: Path,
) -> Path:
    load_frozen_contract(contract_path)
    attestation_bytes = Path(attestation_path).read_bytes()
    attestation = VirginHoldoutAttestation.model_validate_json(attestation_bytes)
    if attestation.locked_symbols != LOCKED_SYMBOLS:
        raise ValueError("PHASE6_ATTESTATION_SYMBOL_SET_MISMATCH")
    seed = canonical_json_bytes(
        {
            "contract": CONTRACT_SHA256,
            "attestation": sha256_bytes(attestation_bytes),
            "ci_head_sha": ci_head_sha,
            "ci_run_id": ci_run_id,
        }
    )
    authorization = AcquisitionAuthorization(
        schema_version="PHASE6-ACQUISITION-AUTHORIZATION-v1",
        authority="INDEPENDENT_AUDIT",
        status="FINAL_HOLDOUT_ACQUISITION_AUTHORIZED",
        authorization_id=f"phase6-acquire-{sha256(seed).hexdigest()[:32]}",
        evaluation_contract_sha256=CONTRACT_SHA256,
        candidate_id=SELECTED_CANDIDATE_ID,
        binding_sha256=SELECTED_BINDING_SHA256,
        implementation_sha256=SELECTED_IMPLEMENTATION_SHA256,
        virgin_holdout_attestation_sha256=sha256_bytes(attestation_bytes),
        ci_head_sha=ci_head_sha,
        ci_run_id=ci_run_id,
        one_time=True,
        holdout_performance_inspected=False,
    )
    output = Path(output_path)
    if output.exists():
        raise FileExistsError("PHASE6_ACQUISITION_AUTHORIZATION_ALREADY_EXISTS")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json_bytes(authorization.model_dump(mode="json")))
    return output


def _load_receipt(path: Path) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("PHASE6_ACQUISITION_RECEIPT_INVALID") from exc
    if not isinstance(value, dict):
        raise ValueError("PHASE6_ACQUISITION_RECEIPT_INVALID")
    if (
        value.get("schema_version") != "PHASE6-HOLDOUT-ACQUISITION-RECEIPT-v1"
        or value.get("authority") != "INDEPENDENT_AUDIT"
        or value.get("status") != "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED"
        or value.get("evaluation_contract_sha256") != CONTRACT_SHA256
        or value.get("candidate_id") != SELECTED_CANDIDATE_ID
        or value.get("binding_sha256") != SELECTED_BINDING_SHA256
        or value.get("implementation_sha256") != SELECTED_IMPLEMENTATION_SHA256
        or value.get("protected_symbols_accessed") != list(LOCKED_SYMBOLS)
        or value.get("final_holdout_accessed") is not True
        or value.get("performance_computed") is not False
        or value.get("performance_inspected") is not False
    ):
        raise ValueError("PHASE6_ACQUISITION_RECEIPT_GOVERNANCE_MISMATCH")
    for field in ("holdout_id", "bundle_sha256", "acquisition_authorization_sha256"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise ValueError("PHASE6_ACQUISITION_RECEIPT_INVALID")
    bundle_sha = value["bundle_sha256"]
    if len(bundle_sha) != 64 or any(ch not in "0123456789abcdef" for ch in bundle_sha):
        raise ValueError("PHASE6_ACQUISITION_RECEIPT_INVALID")
    return value


def issue_holdout_release(
    *,
    contract_path: Path,
    attestation_path: Path,
    authorization_path: Path,
    receipt_path: Path,
    output_path: Path,
) -> Path:
    load_frozen_contract(contract_path)
    authorization = load_acquisition_authorization(
        authorization_path,
        contract_path=contract_path,
        attestation_path=attestation_path,
    )
    authorization_sha = sha256_bytes(Path(authorization_path).read_bytes())
    receipt = _load_receipt(receipt_path)
    if receipt["acquisition_authorization_sha256"] != authorization_sha:
        raise ValueError("PHASE6_RECEIPT_AUTHORIZATION_IDENTITY_MISMATCH")

    holdout_id = str(receipt["holdout_id"])
    bundle_sha = str(receipt["bundle_sha256"])
    seed = canonical_json_bytes(
        {
            "holdout_id": holdout_id,
            "candidate_id": SELECTED_CANDIDATE_ID,
            "contract_sha256": CONTRACT_SHA256,
            "bundle_sha256": bundle_sha,
            "authorization_id": authorization.authorization_id,
        }
    )
    release = {
        "schema_version": "PHASE6-HOLDOUT-RELEASE-v1",
        "authority": "INDEPENDENT_AUDIT",
        "status": "FINAL_HOLDOUT_RELEASE_AUTHORIZED",
        "release_id": f"phase6-release-{sha256(seed).hexdigest()[:32]}",
        "holdout_id": holdout_id,
        "candidate_id": SELECTED_CANDIDATE_ID,
        "binding_sha256": SELECTED_BINDING_SHA256,
        "implementation_sha256": SELECTED_IMPLEMENTATION_SHA256,
        "evaluation_contract_sha256": CONTRACT_SHA256,
        "holdout_bundle_sha256": bundle_sha,
        "one_time": True,
    }
    output = Path(output_path)
    if output.exists():
        raise FileExistsError("PHASE6_HOLDOUT_RELEASE_ALREADY_EXISTS")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json_bytes(release))
    return output
