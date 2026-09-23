from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA = "SUCCESSOR-PHASE6-METHODOLOGY-AUTHORIZATION-v2"
STATUS = "SUCCESSOR_PHASE6_METHODOLOGY_AUTHORIZED"
PREDECESSOR_COMMIT = "df9a0c974a392f414dc9b44551b544aa64e8e7f6"
PREDECESSOR_STATUS = "PHASE6_UNKNOWN_ABSTAIN"
CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
BINDING = "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"
IMPLEMENTATION = "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"


class PostGeneration3AuthorityError(RuntimeError):
    pass


class MethodologyAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[SCHEMA]
    authority: Literal["INDEPENDENT_AUDIT"]
    status: Literal[STATUS]
    approval_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    signed_by: str = Field(min_length=1, max_length=256)
    approved_at_utc: str = Field(min_length=1)

    predecessor_closure_commit: Literal[PREDECESSOR_COMMIT]
    predecessor_phase6_status: Literal[PREDECESSOR_STATUS]

    successor_formal_name: str = Field(min_length=1, max_length=128)
    candidate_id: Literal[CANDIDATE_ID]
    binding_sha256: Literal[BINDING]
    implementation_sha256: Literal[IMPLEMENTATION]

    split_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dividend_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    split_normalizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dividend_reconciliation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_exclusion_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    evaluation_calendar_start: str
    evaluation_calendar_end: str
    required_pre_window_sessions: int = Field(ge=1, le=1000)
    selection_count: int = Field(ge=1, le=20)
    listing_cutoff: str
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
    def validate_dates(self) -> "MethodologyAuthorization":
        try:
            start = date.fromisoformat(self.evaluation_calendar_start)
            end = date.fromisoformat(self.evaluation_calendar_end)
            cutoff = date.fromisoformat(self.listing_cutoff)
        except ValueError as exc:
            raise ValueError("POST_GEN3_AUTH_DATE_INVALID") from exc
        if end < start:
            raise ValueError("POST_GEN3_AUTH_WINDOW_INVALID")
        if cutoff >= start:
            raise ValueError("POST_GEN3_AUTH_LISTING_CUTOFF_INVALID")
        return self


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def load_methodology_authorization(
    *,
    authorization_path: Path,
    predecessor_closure_path: Path,
    split_contract_path: Path,
    dividend_contract_path: Path,
    split_normalizer_path: Path,
    dividend_reconciliation_path: Path,
    successor_evaluator_path: Path,
    holdout_exclusion_registry_path: Path,
) -> MethodologyAuthorization:
    if not Path(authorization_path).is_file():
        raise PostGeneration3AuthorityError(
            "POST_GEN3_INDEPENDENT_AUDIT_AUTHORIZATION_MISSING"
        )
    try:
        auth = MethodologyAuthorization.model_validate_json(
            Path(authorization_path).read_bytes()
        )
    except Exception as exc:
        raise PostGeneration3AuthorityError(
            "POST_GEN3_INDEPENDENT_AUDIT_AUTHORIZATION_INVALID"
        ) from exc

    bindings = (
        ("split_contract_sha256", split_contract_path),
        ("dividend_contract_sha256", dividend_contract_path),
        ("split_normalizer_sha256", split_normalizer_path),
        ("dividend_reconciliation_sha256", dividend_reconciliation_path),
        ("successor_evaluator_sha256", successor_evaluator_path),
        ("holdout_exclusion_registry_sha256", holdout_exclusion_registry_path),
    )
    for field, path in bindings:
        if getattr(auth, field) != _sha(path):
            raise PostGeneration3AuthorityError(
                f"POST_GEN3_IDENTITY_MISMATCH:{field}"
            )

    try:
        closure = json.loads(Path(predecessor_closure_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PostGeneration3AuthorityError(
            "POST_GEN3_PREDECESSOR_CLOSURE_INVALID"
        ) from exc
    if (
        closure.get("status") != PREDECESSOR_STATUS
        or closure.get("one_time_semantics", {}).get("holdout_consumed") is not True
        or closure.get("one_time_semantics", {}).get("retry_authorized") is not False
        or closure.get("one_time_semantics", {}).get("symbol_substitution_authorized") is not False
        or closure.get("phase7", {}).get("authorized") is not False
        or closure.get("recon009_status") != "OPEN"
    ):
        raise PostGeneration3AuthorityError(
            "POST_GEN3_PREDECESSOR_CLOSURE_MISMATCH"
        )
    return auth
