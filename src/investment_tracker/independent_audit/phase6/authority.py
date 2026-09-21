from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.quant.phase5.methodology import (
    SELECTED_BINDING_SHA256,
    SELECTED_CANDIDATE_ID,
    SELECTED_IMPLEMENTATION_SHA256,
)

CONTRACT_SHA256 = "f64f31c20172491f6175a176592d463fed36f73ecf2b99542022afa55f50b77e"
LOCKED_SYMBOLS = ("HACK", "SOXX", "NLR", "URNM", "GEV")
BENCHMARK_SYMBOL = "SPY"
HOLDOUT_START = "2023-01-01"
HOLDOUT_END = "2025-12-31"
WARMUP_SESSIONS = 147
FRICTION_CASE_BPS = (0, 3, 10, 25, 50)
PRIMARY_FRICTION_BPS = 3
INITIAL_CASH = 100000.0


def sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


def load_frozen_contract(path: Path) -> dict[str, object]:
    payload = Path(path).read_bytes()
    if sha256_bytes(payload) != CONTRACT_SHA256:
        raise ValueError("PHASE6_AUDIT_CONTRACT_IDENTITY_MISMATCH")
    try:
        contract = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("PHASE6_AUDIT_CONTRACT_INVALID") from exc
    if not isinstance(contract, dict):
        raise ValueError("PHASE6_AUDIT_CONTRACT_INVALID")

    holdout = contract.get("final_holdout")
    methodology = contract.get("methodology")
    strategy = contract.get("strategy")
    friction = contract.get("friction")
    if (
        contract.get("schema_version") != "PHASE6-EVALUATION-CONTRACT-v1"
        or contract.get("authority") != "INDEPENDENT_AUDIT"
        or contract.get("status") != "FROZEN_PRE_ACCESS"
        or not isinstance(holdout, dict)
        or holdout.get("calendar_start") != HOLDOUT_START
        or holdout.get("calendar_end") != HOLDOUT_END
        or tuple(holdout.get("locked_symbols", ())) != LOCKED_SYMBOLS
        or holdout.get("benchmark_reference_symbol") != BENCHMARK_SYMBOL
        or not isinstance(methodology, dict)
        or methodology.get("option") != "A_STRICT_FROZEN_RESEARCH_COMPARABILITY"
        or methodology.get("provider_price_convention") != "MOOMOO_QFQ"
        or methodology.get("signal_price_convention") != "MOOMOO_QFQ"
        or methodology.get("execution_price_convention") != "MOOMOO_QFQ_NORMALIZED"
        or methodology.get("decision_grade") is not False
        or not isinstance(strategy, dict)
        or strategy.get("candidate_id") != SELECTED_CANDIDATE_ID
        or strategy.get("binding_sha256") != SELECTED_BINDING_SHA256
        or strategy.get("implementation_sha256") != SELECTED_IMPLEMENTATION_SHA256
        or strategy.get("candidate_search_allowed") is not False
        or strategy.get("parameter_mutation_allowed") is not False
        or not isinstance(friction, dict)
        or tuple(friction.get("fixed_friction_cases_bps", ())) != FRICTION_CASE_BPS
        or friction.get("primary_friction_bps") != PRIMARY_FRICTION_BPS
        or float(friction.get("initial_cash", 0.0)) != INITIAL_CASH
    ):
        raise ValueError("PHASE6_AUDIT_CONTRACT_GOVERNANCE_MISMATCH")
    params = strategy.get("parameters")
    if params != {
        "lookback_sessions": 126,
        "rebalance_sessions": 21,
        "skip_sessions": 21,
        "top_k": 3,
    }:
        raise ValueError("PHASE6_AUDIT_CONTRACT_PARAMETER_MISMATCH")
    warmup = holdout.get("warmup_policy")
    if not isinstance(warmup, dict) or warmup.get("required_pre_window_sessions") != WARMUP_SESSIONS:
        raise ValueError("PHASE6_AUDIT_CONTRACT_WARMUP_MISMATCH")
    return contract


class EvidenceFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=0)


class AccessLogMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    symbol: Literal["HACK", "SOXX", "NLR", "URNM", "GEV"]
    line_number: int = Field(ge=1)


class AccessLogEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["PHASE6-ACCESS-LOG-EVIDENCE-v1"]
    status: Literal[
        "NO_LOCKED_SYMBOL_REFERENCE_FOUND_IN_SUPPLIED_LOGS",
        "LOCKED_SYMBOL_REFERENCE_FOUND",
    ]
    source_description: str = Field(min_length=1)
    coverage_start_utc: datetime
    coverage_end_utc: datetime
    files: tuple[EvidenceFile, ...] = Field(min_length=1)
    matches: tuple[AccessLogMatch, ...] = ()

    @model_validator(mode="after")
    def validate_evidence(self) -> "AccessLogEvidence":
        _require_aware(self.coverage_start_utc, "coverage_start_utc")
        _require_aware(self.coverage_end_utc, "coverage_end_utc")
        if self.coverage_end_utc < self.coverage_start_utc:
            raise ValueError("access-log coverage must be chronological")
        found = bool(self.matches)
        if found != (self.status == "LOCKED_SYMBOL_REFERENCE_FOUND"):
            raise ValueError("access-log status and matches disagree")
        if len({item.path for item in self.files}) != len(self.files):
            raise ValueError("access-log evidence files must be unique")
        return self


class VirginHoldoutAttestation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["PHASE6-VIRGIN-HOLDOUT-ATTESTATION-v1"]
    authority: Literal["INDEPENDENT_AUDIT"]
    status: Literal["INDEPENDENTLY_VERIFIED_NO_PRIOR_LOCKED_SYMBOL_ACCESS"]
    attestation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    locked_symbols: tuple[str, ...]
    evidence_kind: Literal["PROVIDER_SIDE_QUERY_HISTORY"]
    evidence_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    coverage_start_utc: datetime
    coverage_end_utc: datetime
    complete_query_history: Literal[True]
    independent_source: Literal[True]
    coordinator_self_report_only: Literal[False]
    limitations: tuple[()] = ()

    @model_validator(mode="after")
    def validate_attestation(self) -> "VirginHoldoutAttestation":
        _require_aware(self.coverage_start_utc, "coverage_start_utc")
        _require_aware(self.coverage_end_utc, "coverage_end_utc")
        if self.coverage_end_utc < self.coverage_start_utc:
            raise ValueError("attestation coverage must be chronological")
        if self.locked_symbols != LOCKED_SYMBOLS:
            raise ValueError("attestation must cover the exact locked symbol set")
        return self


class AcquisitionAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["PHASE6-ACQUISITION-AUTHORIZATION-v1"]
    authority: Literal["INDEPENDENT_AUDIT"]
    status: Literal["FINAL_HOLDOUT_ACQUISITION_AUTHORIZED"]
    authorization_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    evaluation_contract_sha256: Literal[
        "f64f31c20172491f6175a176592d463fed36f73ecf2b99542022afa55f50b77e"
    ]
    candidate_id: Literal[
        "phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075"
    ]
    binding_sha256: Literal[
        "9ff5b11e1b7f381ce574f4b0fc37a16d824e64afa5afeba16be54980c3ed5d3a"
    ]
    implementation_sha256: Literal[
        "bebb913887573a293e6a8cf23ad3d28e5fa3bbd2f613995e37741ec4d80f7c6f"
    ]
    virgin_holdout_attestation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ci_head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    ci_run_id: int = Field(gt=0)
    one_time: Literal[True]
    holdout_performance_inspected: Literal[False]


def load_attestation(path: Path) -> VirginHoldoutAttestation:
    payload = Path(path).read_bytes()
    value = json.loads(payload)
    attestation = VirginHoldoutAttestation.model_validate(value)
    return attestation


def load_acquisition_authorization(
    path: Path,
    *,
    contract_path: Path,
    attestation_path: Path,
) -> AcquisitionAuthorization:
    load_frozen_contract(contract_path)
    attestation_bytes = Path(attestation_path).read_bytes()
    VirginHoldoutAttestation.model_validate_json(attestation_bytes)
    authorization = AcquisitionAuthorization.model_validate_json(Path(path).read_bytes())
    if authorization.virgin_holdout_attestation_sha256 != sha256_bytes(attestation_bytes):
        raise ValueError("PHASE6_ACQUISITION_ATTESTATION_IDENTITY_MISMATCH")
    return authorization
