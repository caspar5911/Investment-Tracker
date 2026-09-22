from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

APPROVAL_SCHEMA = "SUCCESSOR-PHASE6-METHODOLOGY-AUTHORIZATION-v1"
APPROVAL_STATUS = "SUCCESSOR_PHASE6_METHODOLOGY_AUTHORIZED"
PREDECESSOR_CLOSURE_COMMIT = "f875167f3e758ab3391ff2f961aa740f231568e5"
PREDECESSOR_STATUS = "PHASE6_UNKNOWN_ABSTAIN"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class SuccessorAuthorityError(RuntimeError):
    pass


class SuccessorMethodologyAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[APPROVAL_SCHEMA]
    authority: Literal["INDEPENDENT_AUDIT"]
    status: Literal[APPROVAL_STATUS]
    approval_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    signed_by: str = Field(min_length=1, max_length=256)
    approved_at_utc: str = Field(min_length=1)

    predecessor_closure_commit: Literal[PREDECESSOR_CLOSURE_COMMIT]
    predecessor_phase6_status: Literal[PREDECESSOR_STATUS]

    successor_formal_name: str = Field(min_length=1, max_length=128)
    candidate_id: Literal["G2-A|lookback=189|skip=21|top_k=1|rebalance=21"]
    binding_sha256: Literal["fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"]
    implementation_sha256: Literal["35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"]
    corporate_action_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_normalizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_exclusion_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    evaluation_calendar_start: str = Field(min_length=10, max_length=10)
    evaluation_calendar_end: str = Field(min_length=10, max_length=10)
    required_pre_window_sessions: int = Field(ge=1, le=1000)
    selection_count: int = Field(ge=1, le=20)
    listing_cutoff: str = Field(min_length=10, max_length=10)
    selection_seed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    successor_methodology_authorized: Literal[True]
    new_virgin_holdout_selection_authorized: Literal[True]
    protected_history_access_authorized: Literal[False]
    one_time_acquisition_required: Literal[True]
    retry_after_historical_access_allowed: Literal[False]
    symbol_substitution_after_access_allowed: Literal[False]
    result_dependent_methodology_change_allowed: Literal[False]

    phase7_authorized: Literal[False]
    production_readiness_approved: Literal[False]
    recon009_status: Literal["OPEN"]
    paper_only: Literal[True]

    @model_validator(mode="after")
    def validate_window(self) -> "SuccessorMethodologyAuthorization":
        from datetime import date

        try:
            start = date.fromisoformat(self.evaluation_calendar_start)
            end = date.fromisoformat(self.evaluation_calendar_end)
            cutoff = date.fromisoformat(self.listing_cutoff)
        except ValueError as exc:
            raise ValueError("SUCCESSOR_AUTH_DATE_INVALID") from exc
        if end < start:
            raise ValueError("SUCCESSOR_AUTH_WINDOW_INVALID")
        if cutoff >= start:
            raise ValueError("SUCCESSOR_AUTH_LISTING_CUTOFF_NOT_PRE_WINDOW")
        return self


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def load_methodology_authorization(
    *,
    authorization_path: Path,
    corporate_action_contract_path: Path,
    holdout_exclusion_registry_path: Path,
    predecessor_closure_path: Path,
    successor_normalizer_path: Path,
    successor_evaluator_path: Path,
) -> SuccessorMethodologyAuthorization:
    path = Path(authorization_path)
    if not path.is_file():
        raise SuccessorAuthorityError("SUCCESSOR_INDEPENDENT_AUDIT_AUTHORIZATION_MISSING")
    try:
        authorization = SuccessorMethodologyAuthorization.model_validate_json(
            path.read_bytes()
        )
    except Exception as exc:
        raise SuccessorAuthorityError(
            "SUCCESSOR_INDEPENDENT_AUDIT_AUTHORIZATION_INVALID"
        ) from exc

    if authorization.corporate_action_contract_sha256 != _sha(
        corporate_action_contract_path
    ):
        raise SuccessorAuthorityError(
            "SUCCESSOR_CORPORATE_ACTION_CONTRACT_IDENTITY_MISMATCH"
        )
    if authorization.successor_normalizer_sha256 != _sha(successor_normalizer_path):
        raise SuccessorAuthorityError("SUCCESSOR_NORMALIZER_IDENTITY_MISMATCH")
    if authorization.successor_evaluator_sha256 != _sha(successor_evaluator_path):
        raise SuccessorAuthorityError("SUCCESSOR_EVALUATOR_IDENTITY_MISMATCH")
    if authorization.holdout_exclusion_registry_sha256 != _sha(
        holdout_exclusion_registry_path
    ):
        raise SuccessorAuthorityError(
            "SUCCESSOR_HOLDOUT_EXCLUSION_REGISTRY_IDENTITY_MISMATCH"
        )

    try:
        closure = json.loads(Path(predecessor_closure_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuccessorAuthorityError("SUCCESSOR_PREDECESSOR_CLOSURE_INVALID") from exc
    if (
        closure.get("status") != PREDECESSOR_STATUS
        or closure.get("evaluation", {}).get("one_time_consumed") is not True
        or closure.get("phase7", {}).get("authorized") is not False
        or closure.get("recon009_status") != "OPEN"
    ):
        raise SuccessorAuthorityError("SUCCESSOR_PREDECESSOR_CLOSURE_MISMATCH")

    return authorization


def authorization_summary(
    authorization: SuccessorMethodologyAuthorization,
) -> dict[str, Any]:
    return {
        "schema_version": APPROVAL_SCHEMA,
        "status": APPROVAL_STATUS,
        "approval_id": authorization.approval_id,
        "successor_formal_name": authorization.successor_formal_name,
        "candidate_id": authorization.candidate_id,
        "binding_sha256": authorization.binding_sha256,
        "implementation_sha256": authorization.implementation_sha256,
        "successor_normalizer_sha256": authorization.successor_normalizer_sha256,
        "successor_evaluator_sha256": authorization.successor_evaluator_sha256,
        "new_virgin_holdout_selection_authorized": True,
        "protected_history_access_authorized": False,
        "one_time_acquisition_required": True,
        "retry_after_historical_access_allowed": False,
        "phase7_authorized": False,
        "production_readiness_approved": False,
        "recon009_status": "OPEN",
    }
