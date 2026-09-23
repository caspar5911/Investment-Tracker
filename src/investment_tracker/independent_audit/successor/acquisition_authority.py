from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .phase6_contract import verify_phase6_contract
from .virginity import verify_attestation

SCHEMA = "SUCCESSOR-PHASE6-ACQUISITION-AUTHORIZATION-v1"
SCHEMA_V2 = "SUCCESSOR-PHASE6-ACQUISITION-AUTHORIZATION-v2"
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
    successor_evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

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
    one_time_evaluation_after_verified_release_authorized: Literal[True]
    phase7_authorized: Literal[False]
    production_readiness_approved: Literal[False]
    recon009_status: Literal["OPEN"]
    paper_only: Literal[True]


class SuccessorAcquisitionAuthorizationV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[SCHEMA_V2]
    authority: Literal["INDEPENDENT_AUDIT"]
    status: Literal[STATUS]
    authorization_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    signed_by: str = Field(min_length=1, max_length=256)
    approved_at_utc: str = Field(min_length=1)

    successor_formal_name: Literal["GENERATION_4"]
    candidate_id: Literal["G2-A|lookback=189|skip=21|top_k=1|rebalance=21"]
    binding_sha256: Literal["fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"]
    implementation_sha256: Literal["35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"]

    split_normalizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dividend_reconciliation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    phase6_verifier_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_authority_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    closure_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    virginity_verifier_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stage_b_cli_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

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
    one_time_evaluation_after_verified_release_authorized: Literal[True]
    phase7_authorized: Literal[False]
    production_readiness_approved: Literal[False]
    recon009_status: Literal["OPEN"]
    paper_only: Literal[True]

    @property
    def successor_normalizer_sha256(self) -> str:
        """Legacy runtime alias for the Stage-A audited split normalizer."""
        return self.split_normalizer_sha256


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def load_acquisition_authorization(
    *,
    authorization_path: Path,
    phase6_contract_path: Path,
    selection_path: Path,
    virginity_attestation_path: Path,
    virginity_evidence_path: Path,
) -> SuccessorAcquisitionAuthorization | SuccessorAcquisitionAuthorizationV2:
    if not Path(authorization_path).is_file():
        raise SuccessorAcquisitionAuthorityError(
            "SUCCESSOR_ACQUISITION_AUTHORIZATION_MISSING"
        )
    try:
        raw = json.loads(Path(authorization_path).read_text(encoding="utf-8"))
        schema = raw.get("schema_version") if isinstance(raw, dict) else None
        if schema == SCHEMA_V2:
            auth = SuccessorAcquisitionAuthorizationV2.model_validate(raw)
        else:
            auth = SuccessorAcquisitionAuthorization.model_validate(raw)
    except Exception as exc:
        raise SuccessorAcquisitionAuthorityError(
            "SUCCESSOR_ACQUISITION_AUTHORIZATION_INVALID"
        ) from exc

    contract = verify_phase6_contract(phase6_contract_path)
    acquisition_impl = Path(__file__).with_name("acquisition.py")
    release_impl = Path(__file__).with_name("release.py")

    if auth.acquisition_implementation_sha256 != _sha(acquisition_impl):
        raise SuccessorAcquisitionAuthorityError(
            "SUCCESSOR_ACQUISITION_IMPLEMENTATION_IDENTITY_MISMATCH"
        )
    if auth.release_implementation_sha256 != _sha(release_impl):
        raise SuccessorAcquisitionAuthorityError(
            "SUCCESSOR_RELEASE_IMPLEMENTATION_IDENTITY_MISMATCH"
        )

    if isinstance(auth, SuccessorAcquisitionAuthorizationV2):
        verifier_impl = Path(__file__).with_name("phase6_contract.py")
        authority_impl = Path(__file__)
        closure_impl = Path(__file__).with_name("closure.py")
        virginity_impl = Path(__file__).with_name("virginity.py")
        stage_b_cli_impl = (
            Path(__file__).resolve().parents[1] / "post_generation3" / "stage_b_cli.py"
        )
        if auth.phase6_verifier_implementation_sha256 != _sha(verifier_impl):
            raise SuccessorAcquisitionAuthorityError(
                "SUCCESSOR_PHASE6_VERIFIER_IMPLEMENTATION_IDENTITY_MISMATCH"
            )
        if auth.acquisition_authority_implementation_sha256 != _sha(authority_impl):
            raise SuccessorAcquisitionAuthorityError(
                "SUCCESSOR_ACQUISITION_AUTHORITY_IMPLEMENTATION_IDENTITY_MISMATCH"
            )
        if auth.closure_implementation_sha256 != _sha(closure_impl):
            raise SuccessorAcquisitionAuthorityError(
                "SUCCESSOR_CLOSURE_IMPLEMENTATION_IDENTITY_MISMATCH"
            )
        if auth.virginity_verifier_implementation_sha256 != _sha(virginity_impl):
            raise SuccessorAcquisitionAuthorityError(
                "SUCCESSOR_VIRGINITY_VERIFIER_IMPLEMENTATION_IDENTITY_MISMATCH"
            )
        if auth.stage_b_cli_implementation_sha256 != _sha(stage_b_cli_impl):
            raise SuccessorAcquisitionAuthorityError(
                "SUCCESSOR_STAGE_B_CLI_IMPLEMENTATION_IDENTITY_MISMATCH"
            )

    attestation = verify_attestation(
        selection_path=selection_path,
        evidence_path=virginity_evidence_path,
        attestation_path=virginity_attestation_path,
    )
    locked = tuple(contract.get("final_holdout", {}).get("locked_symbols", ()))
    methodology = contract.get("methodology", {})
    normalizer_hash = methodology.get(
        "split_normalizer_sha256",
        methodology.get("successor_normalizer_sha256"),
    )

    mismatch = (
        auth.successor_formal_name != contract.get("successor_formal_name")
        or auth.candidate_id != contract.get("strategy", {}).get("candidate_id")
        or auth.binding_sha256 != contract.get("strategy", {}).get("binding_sha256")
        or auth.implementation_sha256 != contract.get("strategy", {}).get("implementation_sha256")
        or auth.successor_evaluator_sha256 != methodology.get("successor_evaluator_sha256")
        or auth.phase6_contract_sha256 != _sha(phase6_contract_path)
        or auth.selection_sha256 != _sha(selection_path)
        or auth.virginity_attestation_sha256 != _sha(virginity_attestation_path)
        or auth.virginity_evidence_sha256 != _sha(virginity_evidence_path)
        or auth.locked_symbols != locked
        or tuple(attestation.get("selected_symbols", ())) != locked
    )
    if isinstance(auth, SuccessorAcquisitionAuthorizationV2):
        mismatch = mismatch or (
            auth.split_normalizer_sha256 != normalizer_hash
            or auth.dividend_reconciliation_sha256
            != methodology.get("dividend_reconciliation_sha256")
            or contract.get("schema_version") != "SUCCESSOR-PHASE6-EVALUATION-CONTRACT-v2"
            or contract.get("governance", {}).get("symbol_substitution_after_access_allowed")
            is not False
        )
    else:
        mismatch = mismatch or (
            auth.successor_normalizer_sha256 != methodology.get("successor_normalizer_sha256")
        )
    if mismatch:
        raise SuccessorAcquisitionAuthorityError(
            "SUCCESSOR_ACQUISITION_AUTHORIZATION_IDENTITY_MISMATCH"
        )
    return auth

