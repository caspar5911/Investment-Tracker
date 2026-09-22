from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .phase6_contract import verify_contract
from .preaccess import STATUS_READY
from .research_provenance_cache import verify_cache_provenance
from .virginity import (
    FROZEN_BINDING_SHA256,
    FROZEN_CANDIDATE_ID,
    FROZEN_IMPLEMENTATION_SHA256,
    FROZEN_IDENTITY_SHA256,
    LOCKED_SYMBOLS,
    verify_attestation,
)

AUTH_SCHEMA = "GENERATION2-PHASE6-ACQUISITION-AUTHORIZATION-v1"
AUTH_STATUS = "GENERATION2_FINAL_HOLDOUT_ACQUISITION_AUTHORIZED"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


class AcquisitionAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[AUTH_SCHEMA]
    authority: Literal["INDEPENDENT_AUDIT"]
    status: Literal[AUTH_STATUS]
    authorization_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    candidate_id: Literal["G2-A|lookback=189|skip=21|top_k=1|rebalance=21"]
    binding_sha256: Literal[
        "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"
    ]
    implementation_sha256: Literal[
        "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"
    ]
    survivor_identity_report_sha256: Literal[
        "96580b61ddb617f54157cc2ce12f5dc5316dc143321f1aaf214e7a563b5aff87"
    ]
    locked_symbols: tuple[str, ...]
    evaluation_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_contract_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preaccess_status_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    virginity_attestation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    virginity_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance_reconciliation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    ci_workflow: Literal["generation2-holdout-selection-audit"]
    ci_run_id: int = Field(gt=0)
    ci_conclusion: Literal["success"]
    one_time: Literal[True]
    acquisition_start_marker_required_before_provider_read: Literal[True]
    retry_after_historical_access_allowed: Literal[False]
    holdout_performance_inspected: Literal[False]
    historical_data_included_in_authorization_artifact: Literal[False]
    phase7_authorized: Literal[False]
    production_readiness_approved: Literal[False]


def issue_authorization(
    *,
    repository_root: Path,
    contract_path: Path,
    preaccess_status_path: Path,
    attestation_path: Path,
    evidence_path: Path,
    provenance_root: Path,
    evidence_commit_sha: str,
    ci_run_id: int,
    ci_conclusion: str,
    output_path: Path,
) -> Path:
    repository_root = Path(repository_root)
    if ci_conclusion != "success":
        raise ValueError("GEN2_AUTH_CI_NOT_GREEN")
    if len(evidence_commit_sha) != 40 or any(ch not in "0123456789abcdef" for ch in evidence_commit_sha):
        raise ValueError("GEN2_AUTH_EVIDENCE_COMMIT_INVALID")

    contract = verify_contract(contract_path)
    preaccess = json.loads(Path(preaccess_status_path).read_text(encoding="utf-8"))
    if preaccess.get("status") != STATUS_READY:
        raise ValueError("GEN2_AUTH_PREACCESS_NOT_READY")
    if preaccess.get("historical_acquisition_authorized") is not False:
        raise ValueError("GEN2_AUTH_PREACCESS_ALREADY_AUTHORIZED")
    if preaccess.get("locked_symbols") != list(LOCKED_SYMBOLS):
        raise ValueError("GEN2_AUTH_SYMBOL_SET_MISMATCH")

    attestation = verify_attestation(
        attestation_path=attestation_path,
        evidence_path=evidence_path,
        selection_path=repository_root / "data" / "generation2" / "holdout-selection" / "selection.json",
        selection_contract_path=repository_root / "data" / "governance" / "generation2-holdout-selection-contract.json",
    )
    provenance = verify_cache_provenance(provenance_root)
    if (
        provenance.get("status") != "MATCHED"
        or provenance.get("independent_source_established") is not True
        or provenance.get("decision_critical") is not False
    ):
        raise ValueError("GEN2_AUTH_PROVENANCE_NOT_MATCHED")

    if contract["strategy"]["candidate_id"] != FROZEN_CANDIDATE_ID:
        raise ValueError("GEN2_AUTH_CANDIDATE_MISMATCH")
    if contract["strategy"]["binding_sha256"] != FROZEN_BINDING_SHA256:
        raise ValueError("GEN2_AUTH_BINDING_MISMATCH")
    if contract["strategy"]["implementation_sha256"] != FROZEN_IMPLEMENTATION_SHA256:
        raise ValueError("GEN2_AUTH_IMPLEMENTATION_MISMATCH")
    if contract["strategy"]["survivor_identity_report_sha256"] != FROZEN_IDENTITY_SHA256:
        raise ValueError("GEN2_AUTH_IDENTITY_MISMATCH")
    if contract["final_holdout"]["locked_symbols"] != list(LOCKED_SYMBOLS):
        raise ValueError("GEN2_AUTH_CONTRACT_SYMBOL_SET_MISMATCH")
    if contract["governance"]["historical_access_authorized"] is not False:
        raise ValueError("GEN2_AUTH_CONTRACT_ALREADY_AUTHORIZED")
    if attestation["locked_symbols"] != list(LOCKED_SYMBOLS):
        raise ValueError("GEN2_AUTH_ATTESTATION_SYMBOL_SET_MISMATCH")

    contract_file_sha = _sha(contract_path)
    preaccess_sha = _sha(preaccess_status_path)
    attestation_sha = _sha(attestation_path)
    evidence_sha = _sha(evidence_path)
    reconciliation_sha = provenance["reconciliation_sha256"]

    if contract["final_holdout"]["preaccess_status_sha256"] != preaccess_sha:
        raise ValueError("GEN2_AUTH_PREACCESS_HASH_MISMATCH")
    if contract["final_holdout"]["virginity_attestation_sha256"] != attestation_sha:
        raise ValueError("GEN2_AUTH_ATTESTATION_HASH_MISMATCH")
    if contract["final_holdout"]["virginity_evidence_sha256"] != evidence_sha:
        raise ValueError("GEN2_AUTH_EVIDENCE_HASH_MISMATCH")
    if contract["final_holdout"]["independent_reconciliation_sha256"] != reconciliation_sha:
        raise ValueError("GEN2_AUTH_RECONCILIATION_HASH_MISMATCH")

    seed = {
        "schema_version": AUTH_SCHEMA,
        "candidate_id": FROZEN_CANDIDATE_ID,
        "locked_symbols": list(LOCKED_SYMBOLS),
        "evaluation_contract_sha256": contract["contract_sha256"],
        "evaluation_contract_file_sha256": contract_file_sha,
        "preaccess_status_sha256": preaccess_sha,
        "virginity_attestation_sha256": attestation_sha,
        "virginity_evidence_sha256": evidence_sha,
        "provenance_reconciliation_sha256": reconciliation_sha,
        "evidence_commit_sha": evidence_commit_sha,
        "ci_workflow": "generation2-holdout-selection-audit",
        "ci_run_id": ci_run_id,
        "ci_conclusion": ci_conclusion,
    }
    auth_id = f"gen2-phase6-acquire-{sha256(_canonical_bytes(seed)).hexdigest()[:32]}"

    authorization = AcquisitionAuthorization(
        schema_version=AUTH_SCHEMA,
        authority="INDEPENDENT_AUDIT",
        status=AUTH_STATUS,
        authorization_id=auth_id,
        candidate_id=FROZEN_CANDIDATE_ID,
        binding_sha256=FROZEN_BINDING_SHA256,
        implementation_sha256=FROZEN_IMPLEMENTATION_SHA256,
        survivor_identity_report_sha256=FROZEN_IDENTITY_SHA256,
        locked_symbols=LOCKED_SYMBOLS,
        evaluation_contract_sha256=contract["contract_sha256"],
        evaluation_contract_file_sha256=contract_file_sha,
        preaccess_status_sha256=preaccess_sha,
        virginity_attestation_sha256=attestation_sha,
        virginity_evidence_sha256=evidence_sha,
        provenance_reconciliation_sha256=reconciliation_sha,
        evidence_commit_sha=evidence_commit_sha,
        ci_workflow="generation2-holdout-selection-audit",
        ci_run_id=ci_run_id,
        ci_conclusion="success",
        one_time=True,
        acquisition_start_marker_required_before_provider_read=True,
        retry_after_historical_access_allowed=False,
        holdout_performance_inspected=False,
        historical_data_included_in_authorization_artifact=False,
        phase7_authorized=False,
        production_readiness_approved=False,
    )

    output = Path(output_path)
    if output.exists():
        raise FileExistsError("GEN2_AUTHORIZATION_ALREADY_EXISTS")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical_bytes(authorization.model_dump(mode="json")))
    return output


def load_authorization(
    *,
    authorization_path: Path,
    repository_root: Path,
    contract_path: Path,
    preaccess_status_path: Path,
    attestation_path: Path,
    evidence_path: Path,
    provenance_root: Path,
) -> AcquisitionAuthorization:
    raw = Path(authorization_path).read_bytes()
    authorization = AcquisitionAuthorization.model_validate_json(raw)
    contract = verify_contract(contract_path)
    if authorization.locked_symbols != LOCKED_SYMBOLS:
        raise ValueError("GEN2_AUTHORIZATION_SYMBOL_SET_MISMATCH")
    if authorization.evaluation_contract_sha256 != contract["contract_sha256"]:
        raise ValueError("GEN2_AUTHORIZATION_CONTRACT_MISMATCH")
    if authorization.evaluation_contract_file_sha256 != _sha(contract_path):
        raise ValueError("GEN2_AUTHORIZATION_CONTRACT_FILE_MISMATCH")
    if authorization.preaccess_status_sha256 != _sha(preaccess_status_path):
        raise ValueError("GEN2_AUTHORIZATION_PREACCESS_MISMATCH")
    if authorization.virginity_attestation_sha256 != _sha(attestation_path):
        raise ValueError("GEN2_AUTHORIZATION_ATTESTATION_MISMATCH")
    if authorization.virginity_evidence_sha256 != _sha(evidence_path):
        raise ValueError("GEN2_AUTHORIZATION_EVIDENCE_MISMATCH")
    provenance = verify_cache_provenance(provenance_root)
    if authorization.provenance_reconciliation_sha256 != provenance["reconciliation_sha256"]:
        raise ValueError("GEN2_AUTHORIZATION_PROVENANCE_MISMATCH")
    verify_attestation(
        attestation_path=attestation_path,
        evidence_path=evidence_path,
        selection_path=Path(repository_root) / "data" / "generation2" / "holdout-selection" / "selection.json",
        selection_contract_path=Path(repository_root) / "data" / "governance" / "generation2-holdout-selection-contract.json",
    )
    return authorization
