from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from investment_tracker.independent_audit.successor.acquisition_authority import (
    SCHEMA_V2 as ACQUISITION_AUTHORIZATION_SCHEMA,
    SuccessorAcquisitionAuthorityError,
    SuccessorAcquisitionAuthorizationV2,
    load_acquisition_authorization,
)
from investment_tracker.independent_audit.successor.phase6_contract import (
    verify_phase6_contract,
)
from investment_tracker.independent_audit.successor.release import (
    load_receipt,
    load_release,
)


READINESS_SCHEMA = "GENERATION4-PHASE7-ENTRY-READINESS-v1"
READINESS_STATUS = "GENERATION4_PHASE7_READY_FOR_INDEPENDENT_AUDIT"
PHASE6_STATUS = "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"

GEN4_PHASE7_EVIDENCE_INVALID = "GEN4_PHASE7_EVIDENCE_INVALID"
GEN4_PHASE7_GOVERNANCE_MISMATCH = "GEN4_PHASE7_GOVERNANCE_MISMATCH"
GEN4_PHASE7_IDENTITY_MISMATCH = "GEN4_PHASE7_IDENTITY_MISMATCH"
GEN4_PHASE7_CHAIN_MISMATCH = "GEN4_PHASE7_CHAIN_MISMATCH"
GEN4_PHASE7_AUTHORIZATION_MISSING = "GEN4_PHASE7_AUTHORIZATION_MISSING"
GEN4_PHASE7_AUTHORIZATION_INVALID = "GEN4_PHASE7_AUTHORIZATION_INVALID"
GEN4_PHASE7_AUTHORIZATION_MISMATCH = "GEN4_PHASE7_AUTHORIZATION_MISMATCH"

_CONTRACT_SCHEMA = "SUCCESSOR-PHASE6-EVALUATION-CONTRACT-v2"
_CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
_BINDING_SHA256 = "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"
_IMPLEMENTATION_SHA256 = (
    "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"
)
_SPLIT_NORMALIZER_SHA256 = (
    "bfbf0de5bdeb39af3535641570f3f9224f5301abb7db9fffc34c580481cace04"
)
_DIVIDEND_RECONCILIATION_SHA256 = (
    "6baa251d51f6f16be602aa82b08fc46665a4ccdd62f68705821c48c8a28ac9bc"
)
_SUCCESSOR_EVALUATOR_SHA256 = (
    "fb20b368d6d7ac0f698c5ab45e5824aaad73341cccfacc25bc6903b98c9a2b21"
)
_STRATEGY = {
    "candidate_id": _CANDIDATE_ID,
    "binding_sha256": _BINDING_SHA256,
    "implementation_sha256": _IMPLEMENTATION_SHA256,
    "family": "G2-A",
    "lookback": 189,
    "skip": 21,
    "top_k": 1,
    "rebalance": 21,
    "long_only": True,
    "portfolio_leverage_allowed": False,
    "short_selling_allowed": False,
    "candidate_search_allowed": False,
    "parameter_mutation_allowed": False,
    "signal_on_completed_session": True,
    "earliest_fill": "NEXT_ELIGIBLE_SESSION_OPEN",
}


class Generation4Phase7EntryError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


def _sha(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _load_object(path: Path, *, detail: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, detail
        ) from exc
    if not isinstance(value, dict):
        raise Generation4Phase7EntryError(GEN4_PHASE7_EVIDENCE_INVALID, detail)
    return value


def _require_equal(
    actual: object, expected: object, *, code: str, field: str
) -> None:
    if actual != expected:
        raise Generation4Phase7EntryError(code, field)


def _verify_contract(contract: dict[str, Any]) -> None:
    _require_equal(
        contract.get("schema_version"),
        _CONTRACT_SCHEMA,
        code=GEN4_PHASE7_IDENTITY_MISMATCH,
        field="contract.schema_version",
    )
    _require_equal(
        contract.get("successor_formal_name"),
        "GENERATION_4",
        code=GEN4_PHASE7_IDENTITY_MISMATCH,
        field="contract.successor_formal_name",
    )
    strategy = contract.get("strategy")
    if not isinstance(strategy, dict):
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "contract.strategy"
        )
    for field, expected in _STRATEGY.items():
        _require_equal(
            strategy.get(field),
            expected,
            code=GEN4_PHASE7_IDENTITY_MISMATCH,
            field=f"contract.strategy.{field}",
        )
    methodology = contract.get("methodology")
    if not isinstance(methodology, dict):
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "contract.methodology"
        )
    for field, expected in (
        ("split_normalizer_sha256", _SPLIT_NORMALIZER_SHA256),
        ("dividend_reconciliation_sha256", _DIVIDEND_RECONCILIATION_SHA256),
        ("successor_evaluator_sha256", _SUCCESSOR_EVALUATOR_SHA256),
    ):
        _require_equal(
            methodology.get(field),
            expected,
            code=GEN4_PHASE7_IDENTITY_MISMATCH,
            field=f"contract.methodology.{field}",
        )
    governance = contract.get("governance")
    if not isinstance(governance, dict):
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "contract.governance"
        )
    for field, expected in (
        ("retry_after_historical_access_allowed", False),
        ("symbol_substitution_after_access_allowed", False),
        ("phase7_authorized", False),
        ("production_readiness_approved", False),
        ("recon009_status", "OPEN"),
        ("paper_only", True),
    ):
        _require_equal(
            governance.get(field),
            expected,
            code=GEN4_PHASE7_GOVERNANCE_MISMATCH,
            field=f"contract.governance.{field}",
        )


def verify_generation4_phase7_readiness(
    *,
    phase6_contract_path: Path,
    acquisition_authorization_path: Path,
    selection_path: Path,
    virginity_attestation_path: Path,
    virginity_evidence_path: Path,
    acquisition_receipt_path: Path,
    release_path: Path,
    phase6_result_path: Path,
    consumption_marker_path: Path,
    phase6_closure_path: Path,
) -> dict[str, Any]:
    try:
        contract = verify_phase6_contract(phase6_contract_path)
    except (OSError, ValueError) as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "phase6_contract"
        ) from exc
    _verify_contract(contract)

    try:
        authorization = load_acquisition_authorization(
            authorization_path=acquisition_authorization_path,
            phase6_contract_path=phase6_contract_path,
            selection_path=selection_path,
            virginity_attestation_path=virginity_attestation_path,
            virginity_evidence_path=virginity_evidence_path,
        )
    except SuccessorAcquisitionAuthorityError as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_IDENTITY_MISMATCH, "acquisition_authorization"
        ) from exc
    except (OSError, ValueError) as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "acquisition_authorization"
        ) from exc
    if not isinstance(authorization, SuccessorAcquisitionAuthorizationV2):
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_IDENTITY_MISMATCH, "acquisition_authorization.schema_version"
        )
    _require_equal(
        authorization.schema_version,
        ACQUISITION_AUTHORIZATION_SCHEMA,
        code=GEN4_PHASE7_IDENTITY_MISMATCH,
        field="acquisition_authorization.schema_version",
    )
    for field, actual, expected in (
        ("split_normalizer_sha256", authorization.split_normalizer_sha256, _SPLIT_NORMALIZER_SHA256),
        (
            "dividend_reconciliation_sha256",
            authorization.dividend_reconciliation_sha256,
            _DIVIDEND_RECONCILIATION_SHA256,
        ),
        (
            "successor_evaluator_sha256",
            authorization.successor_evaluator_sha256,
            _SUCCESSOR_EVALUATOR_SHA256,
        ),
        ("paper_only", authorization.paper_only, True),
    ):
        _require_equal(
            actual,
            expected,
            code=GEN4_PHASE7_IDENTITY_MISMATCH,
            field=f"acquisition_authorization.{field}",
        )
    try:
        acquisition_authorization_sha256 = _sha(acquisition_authorization_path)
        receipt = load_receipt(
            acquisition_receipt_path,
            contract_path=phase6_contract_path,
            authorization_path=acquisition_authorization_path,
            selection_path=selection_path,
            virginity_attestation_path=virginity_attestation_path,
            virginity_evidence_path=virginity_evidence_path,
        )
        release = load_release(release_path, contract_path=phase6_contract_path)
    except (OSError, ValueError, SuccessorAcquisitionAuthorityError) as exc:
        raise Generation4Phase7EntryError(
            GEN4_PHASE7_EVIDENCE_INVALID, "receipt_or_release"
        ) from exc

    result = _load_object(phase6_result_path, detail="phase6_result")
    marker = _load_object(consumption_marker_path, detail="consumption_marker")
    closure = _load_object(phase6_closure_path, detail="phase6_closure")
    methodology = contract["methodology"]
    locked_symbols = list(contract["final_holdout"]["locked_symbols"])

    for name, value in (
        ("receipt", receipt),
        ("release", release),
        ("result", result),
        ("closure", closure),
    ):
        for field, expected in (
            ("successor_normalizer_sha256", methodology["split_normalizer_sha256"]),
            ("successor_evaluator_sha256", methodology["successor_evaluator_sha256"]),
        ):
            _require_equal(
                value.get(field),
                expected,
                code=GEN4_PHASE7_IDENTITY_MISMATCH,
                field=f"{name}.{field}",
            )

    return {
        "schema_version": READINESS_SCHEMA,
        "status": READINESS_STATUS,
        "generation": "GENERATION_4",
        "candidate_id": _CANDIDATE_ID,
        "binding_sha256": _BINDING_SHA256,
        "implementation_sha256": _IMPLEMENTATION_SHA256,
        "split_normalizer_sha256": _SPLIT_NORMALIZER_SHA256,
        "dividend_reconciliation_sha256": _DIVIDEND_RECONCILIATION_SHA256,
        "successor_evaluator_sha256": _SUCCESSOR_EVALUATOR_SHA256,
        "locked_symbols": locked_symbols,
        "holdout_id": release.get("holdout_id"),
        "release_id": release.get("release_id"),
        "phase6_status": result.get("status"),
        "one_time_consumed": result.get("one_time_consumed"),
        "phase6_contract_sha256": _sha(phase6_contract_path),
        "acquisition_authorization_sha256": acquisition_authorization_sha256,
        "acquisition_receipt_sha256": _sha(acquisition_receipt_path),
        "release_sha256": _sha(release_path),
        "evaluation_result_sha256": _sha(phase6_result_path),
        "evaluation_consumption_marker_sha256": _sha(consumption_marker_path),
        "phase6_closure_sha256": _sha(phase6_closure_path),
        "authority_granted": False,
        "phase7_authorized": False,
        "phase7_started": False,
        "production_readiness_approved": False,
        "live_trading_authorized": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }
