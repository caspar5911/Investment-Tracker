from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .phase6_contract import verify_phase6_contract
from .virginity import verify_attestation

SCHEMA = "SUCCESSOR-PHASE6-ACQUISITION-AUTHORIZATION-v1"
STATUS = "SUCCESSOR_FINAL_HOLDOUT_ACQUISITION_AUTHORIZED"


class SuccessorAcquisitionAuthorityError(RuntimeError):
    pass


class SuccessorAcquisitionAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[SCHEMA]
    authority: Literal["INDEPENDENT_AUDIT"]
    status: Literal[STATUS]
    authorization_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    signed_by: str = Field(min_length=1, max_length=256)
    approved_at_utc: str = Field(min_length=1)

    successor_formal_name: str = Field(min_length=1, max_length=128)
    candidate_id: Literal["G2-A|lookback=189|skip=21|top_k=1|rebalance=21"]
    binding_sha256: Literal["fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"]
    implementation_sha256: Literal["35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"]
    successor_normalizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    phase6_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    virginity_attestation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    virginity_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locked_symbols: tuple[str, ...]

    one_time: Literal[True]
    acquisition_start_marker_required_before_provider_read: Literal[True]
    retry_after_historical_access_allowed: Literal[False]
    symbol_substitution_after_access_allowed: Literal[False]
    historical_data_included_in_authorization_artifact: Literal[False]
    holdout_performance_inspected: Literal[False]
    phase7_authorized: Literal[False]
    production_readiness_approved: Literal[False]
    recon009_status: Literal["OPEN"]
    paper_only: Literal[True]


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def load_acquisition_authorization(
    *,
    authorization_path: Path,
    phase6_contract_path: Path,
    selection_path: Path,
    virginity_attestation_path: Path,
    virginity_evidence_path: Path,
) -> SuccessorAcquisitionAuthorization:
    if not Path(authorization_path).is_file():
        raise SuccessorAcquisitionAuthorityError(
            "SUCCESSOR_ACQUISITION_AUTHORIZATION_MISSING"
        )
    try:
        auth = SuccessorAcquisitionAuthorization.model_validate_json(
            Path(authorization_path).read_bytes()
        )
    except Exception as exc:
        raise SuccessorAcquisitionAuthorityError(
            "SUCCESSOR_ACQUISITION_AUTHORIZATION_INVALID"
        ) from exc

    contract = verify_phase6_contract(phase6_contract_path)
    attestation = verify_attestation(
        selection_path=selection_path,
        evidence_path=virginity_evidence_path,
        attestation_path=virginity_attestation_path,
    )
    locked = tuple(contract.get("final_holdout", {}).get("locked_symbols", ()))
    if (
        auth.successor_formal_name != contract.get("successor_formal_name")
        or auth.candidate_id != contract.get("strategy", {}).get("candidate_id")
        or auth.binding_sha256 != contract.get("strategy", {}).get("binding_sha256")
        or auth.implementation_sha256 != contract.get("strategy", {}).get("implementation_sha256")
        or auth.successor_normalizer_sha256 != contract.get("methodology", {}).get("successor_normalizer_sha256")
        or auth.phase6_contract_sha256 != _sha(phase6_contract_path)
        or auth.selection_sha256 != _sha(selection_path)
        or auth.virginity_attestation_sha256 != _sha(virginity_attestation_path)
        or auth.virginity_evidence_sha256 != _sha(virginity_evidence_path)
        or auth.locked_symbols != locked
        or tuple(attestation.get("selected_symbols", ())) != locked
    ):
        raise SuccessorAcquisitionAuthorityError(
            "SUCCESSOR_ACQUISITION_AUTHORIZATION_IDENTITY_MISMATCH"
        )
    return auth
