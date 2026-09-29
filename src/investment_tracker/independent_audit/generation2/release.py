from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from .acquisition import RECEIPT_SCHEMA, _canonical_bytes
from .authorization import load_authorization
from .phase6_contract import verify_contract
from .virginity import LOCKED_SYMBOLS

RELEASE_SCHEMA = "GENERATION2-PHASE6-HOLDOUT-RELEASE-v1"


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _write_exclusive_verified(path: Path, payload: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise FileExistsError(f"GEN2_PHASE6_IMMUTABLE_OUTPUT_EXISTS:{path.name}") from exc
    if path.read_bytes() != payload:
        raise OSError(f"GEN2_PHASE6_OUTPUT_READBACK_FAILED:{path.name}")


def load_receipt(
    receipt_path: Path,
    *,
    contract_path: Path,
    authorization_path: Path,
) -> dict[str, Any]:
    contract = verify_contract(contract_path)
    try:
        payload = Path(receipt_path).read_bytes()
        value = json.loads(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("GEN2_PHASE6_ACQUISITION_RECEIPT_INVALID") from exc
    if not isinstance(value, dict):
        raise ValueError("GEN2_PHASE6_ACQUISITION_RECEIPT_INVALID")
    strategy = contract["strategy"]
    expected = {
        "schema_version": RECEIPT_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED",
        "evaluation_contract_sha256": contract["contract_sha256"],
        "acquisition_authorization_sha256": sha256(Path(authorization_path).read_bytes()).hexdigest(),
        "candidate_id": strategy["candidate_id"],
        "binding_sha256": strategy["binding_sha256"],
        "implementation_sha256": strategy["implementation_sha256"],
        "protected_symbols_accessed": list(LOCKED_SYMBOLS),
        "final_holdout_accessed": True,
        "performance_computed": False,
        "performance_inspected": False,
        "retry_allowed": False,
        "artifact_readback_verified": True,
    }
    if any(value.get(field) != expected_value for field, expected_value in expected.items()):
        raise ValueError("GEN2_PHASE6_ACQUISITION_RECEIPT_GOVERNANCE_MISMATCH")
    for field in (
        "bundle_sha256",
        "plaintext_bundle_sha256",
        "bundle_manifest_sha256",
        "key_sha256",
        "receipt_sha256",
    ):
        if not _is_sha256(value.get(field)):
            raise ValueError("GEN2_PHASE6_ACQUISITION_RECEIPT_INVALID")
    if value["receipt_sha256"] != sha256(
        _canonical_bytes({key: item for key, item in value.items() if key != "receipt_sha256"})
    ).hexdigest():
        raise ValueError("GEN2_PHASE6_ACQUISITION_RECEIPT_SELF_HASH_MISMATCH")
    if not isinstance(value.get("holdout_id"), str) or not value["holdout_id"]:
        raise ValueError("GEN2_PHASE6_ACQUISITION_RECEIPT_INVALID")
    return value


def load_release(path: Path, *, contract_path: Path) -> dict[str, Any]:
    contract = verify_contract(contract_path)
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("GEN2_PHASE6_RELEASE_INVALID") from exc
    strategy = contract["strategy"]
    expected = {
        "schema_version": RELEASE_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": "FINAL_HOLDOUT_RELEASE_AUTHORIZED",
        "candidate_id": strategy["candidate_id"],
        "binding_sha256": strategy["binding_sha256"],
        "implementation_sha256": strategy["implementation_sha256"],
        "evaluation_contract_sha256": contract["contract_sha256"],
        "locked_symbols": list(LOCKED_SYMBOLS),
        "one_time": True,
        "performance_inspected_before_release": False,
    }
    if not isinstance(value, dict) or any(
        value.get(field) != expected_value for field, expected_value in expected.items()
    ):
        raise ValueError("GEN2_PHASE6_RELEASE_GOVERNANCE_MISMATCH")
    if not isinstance(value.get("release_id"), str) or not value["release_id"].startswith("gen2-phase6-release-"):
        raise ValueError("GEN2_PHASE6_RELEASE_INVALID")
    for field in ("holdout_bundle_sha256", "holdout_key_sha256", "acquisition_receipt_file_sha256"):
        if not _is_sha256(value.get(field)):
            raise ValueError("GEN2_PHASE6_RELEASE_INVALID")
    seed = _canonical_bytes(
        {
            "holdout_id": value.get("holdout_id"),
            "candidate_id": value.get("candidate_id"),
            "contract_sha256": value.get("evaluation_contract_sha256"),
            "bundle_sha256": value.get("holdout_bundle_sha256"),
            "receipt_sha256": value.get("acquisition_receipt_file_sha256"),
        }
    )
    expected_release_id = f"gen2-phase6-release-{sha256(seed).hexdigest()[:32]}"
    if value.get("release_id") != expected_release_id:
        raise ValueError("GEN2_PHASE6_RELEASE_ID_MISMATCH")
    return value


def issue_release(
    *,
    contract_path: Path,
    authorization_path: Path,
    receipt_path: Path,
    encrypted_bundle_path: Path,
    key_path: Path,
    output_path: Path,
    receipt_evidence_path: Path,
) -> Path:
    contract = verify_contract(contract_path)
    load_authorization(
        authorization_path=authorization_path,
        repository_root=Path(contract_path).resolve().parents[3],
        contract_path=contract_path,
        preaccess_status_path=Path(contract_path).resolve().parents[1] / "preaccess" / "preaccess-status.json",
        attestation_path=Path(contract_path).resolve().parents[1] / "preaccess" / "virginity-attestation.json",
        evidence_path=Path(contract_path).resolve().parents[1] / "preaccess" / "virginity-evidence.json",
        provenance_root=Path(contract_path).resolve().parents[1] / "preaccess" / "provenance",
    )
    receipt_bytes = Path(receipt_path).read_bytes()
    receipt = load_receipt(
        receipt_path,
        contract_path=contract_path,
        authorization_path=authorization_path,
    )
    encrypted = Path(encrypted_bundle_path).read_bytes()
    if sha256(encrypted).hexdigest() != receipt["bundle_sha256"]:
        raise ValueError("GEN2_PHASE6_BUNDLE_HASH_MISMATCH")
    try:
        key = bytes.fromhex(Path(key_path).read_text(encoding="ascii"))
    except (OSError, ValueError) as exc:
        raise ValueError("GEN2_PHASE6_KEY_INVALID") from exc
    if sha256(key).hexdigest() != receipt["key_sha256"]:
        raise ValueError("GEN2_PHASE6_KEY_HASH_MISMATCH")
    strategy = contract["strategy"]
    seed = _canonical_bytes(
        {
            "holdout_id": receipt["holdout_id"],
            "candidate_id": strategy["candidate_id"],
            "contract_sha256": contract["contract_sha256"],
            "bundle_sha256": receipt["bundle_sha256"],
            "receipt_sha256": sha256(receipt_bytes).hexdigest(),
        }
    )
    release = {
        "schema_version": RELEASE_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": "FINAL_HOLDOUT_RELEASE_AUTHORIZED",
        "release_id": f"gen2-phase6-release-{sha256(seed).hexdigest()[:32]}",
        "holdout_id": receipt["holdout_id"],
        "candidate_id": strategy["candidate_id"],
        "binding_sha256": strategy["binding_sha256"],
        "implementation_sha256": strategy["implementation_sha256"],
        "evaluation_contract_sha256": contract["contract_sha256"],
        "holdout_bundle_sha256": receipt["bundle_sha256"],
        "holdout_key_sha256": receipt["key_sha256"],
        "acquisition_receipt_file_sha256": sha256(receipt_bytes).hexdigest(),
        "locked_symbols": list(LOCKED_SYMBOLS),
        "one_time": True,
        "performance_inspected_before_release": False,
        "phase7_authorized": False,
        "production_readiness_approved": False,
    }
    _write_exclusive_verified(Path(receipt_evidence_path), receipt_bytes)
    _write_exclusive_verified(Path(output_path), _canonical_bytes(release))
    return Path(output_path)
