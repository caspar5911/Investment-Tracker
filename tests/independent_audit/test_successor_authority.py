from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from investment_tracker.independent_audit.successor.authority import (
    APPROVAL_SCHEMA,
    APPROVAL_STATUS,
    SuccessorAuthorityError,
    load_methodology_authorization,
)
from investment_tracker.independent_audit.successor.selection_contract import (
    build_holdout_selection_contract,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/governance/successor/corporate-action-normalization-v2.json"
REGISTRY = ROOT / "data/governance/holdout-exclusion-registry.json"
CLOSURE = ROOT / "data/generation2/phase6/phase6-final-holdout-closure.json"
TEMPLATE = ROOT / "data/governance/successor/successor-methodology-authorization.template.json"
NORMALIZER = ROOT / "src/investment_tracker/quant/successor/corporate_actions_v2.py"
EVALUATOR = ROOT / "src/investment_tracker/independent_audit/successor/evaluate.py"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _authorization() -> dict:
    return {
        "schema_version": APPROVAL_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": APPROVAL_STATUS,
        "approval_id": "AUDIT-SUCCESSOR-TEST-1",
        "signed_by": "Synthetic Independent Auditor Fixture",
        "approved_at_utc": "2026-09-23T00:00:00Z",
        "predecessor_closure_commit": "f875167f3e758ab3391ff2f961aa740f231568e5",
        "predecessor_phase6_status": "PHASE6_UNKNOWN_ABSTAIN",
        "successor_formal_name": "GENERATION_3_TEST_FIXTURE",
        "candidate_id": "G2-A|lookback=189|skip=21|top_k=1|rebalance=21",
        "binding_sha256": "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b",
        "implementation_sha256": "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b",
        "corporate_action_contract_sha256": _sha(CONTRACT),
        "successor_normalizer_sha256": _sha(NORMALIZER),
        "successor_evaluator_sha256": _sha(EVALUATOR),
        "holdout_exclusion_registry_sha256": _sha(REGISTRY),
        "evaluation_calendar_start": "2023-01-01",
        "evaluation_calendar_end": "2025-12-31",
        "required_pre_window_sessions": 210,
        "selection_count": 5,
        "listing_cutoff": "2022-03-03",
        "selection_seed_sha256": "1" * 64,
        "successor_methodology_authorized": True,
        "new_virgin_holdout_selection_authorized": True,
        "protected_history_access_authorized": False,
        "one_time_acquisition_required": True,
        "retry_after_historical_access_allowed": False,
        "symbol_substitution_after_access_allowed": False,
        "result_dependent_methodology_change_allowed": False,
        "phase7_authorized": False,
        "production_readiness_approved": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _load(path: Path):
    return load_methodology_authorization(
        authorization_path=path,
        corporate_action_contract_path=CONTRACT,
        holdout_exclusion_registry_path=REGISTRY,
        predecessor_closure_path=CLOSURE,
        successor_normalizer_path=NORMALIZER,
        successor_evaluator_path=EVALUATOR,
    )


def test_missing_real_audit_authorization_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(
        SuccessorAuthorityError,
        match="SUCCESSOR_INDEPENDENT_AUDIT_AUTHORIZATION_MISSING",
    ):
        _load(tmp_path / "missing.json")


def test_non_authorizing_template_cannot_be_used_as_approval() -> None:
    with pytest.raises(
        SuccessorAuthorityError,
        match="SUCCESSOR_INDEPENDENT_AUDIT_AUTHORIZATION_INVALID",
    ):
        _load(TEMPLATE)


def test_valid_synthetic_authority_fixture_binds_exact_governance(tmp_path: Path) -> None:
    auth_path = _write(tmp_path / "auth.json", _authorization())
    auth = _load(auth_path)
    assert auth.successor_methodology_authorized is True
    assert auth.new_virgin_holdout_selection_authorized is True
    assert auth.protected_history_access_authorized is False
    assert auth.phase7_authorized is False
    assert auth.recon009_status == "OPEN"


def test_tampered_contract_identity_fails_closed(tmp_path: Path) -> None:
    payload = _authorization()
    payload["corporate_action_contract_sha256"] = "0" * 64
    auth_path = _write(tmp_path / "auth.json", payload)
    with pytest.raises(
        SuccessorAuthorityError,
        match="SUCCESSOR_CORPORATE_ACTION_CONTRACT_IDENTITY_MISMATCH",
    ):
        _load(auth_path)


def test_tampered_normalizer_identity_fails_closed(tmp_path: Path) -> None:
    payload = _authorization()
    payload["successor_normalizer_sha256"] = "0" * 64
    auth_path = _write(tmp_path / "auth.json", payload)
    with pytest.raises(
        SuccessorAuthorityError,
        match="SUCCESSOR_NORMALIZER_IDENTITY_MISMATCH",
    ):
        _load(auth_path)


def test_selection_contract_requires_valid_audit_authority(tmp_path: Path) -> None:
    auth_path = _write(tmp_path / "auth.json", _authorization())
    contract = build_holdout_selection_contract(
        authorization_path=auth_path,
        corporate_action_contract_path=CONTRACT,
        holdout_exclusion_registry_path=REGISTRY,
        predecessor_closure_path=CLOSURE,
        successor_normalizer_path=NORMALIZER,
        successor_evaluator_path=EVALUATOR,
    )
    assert contract["status"] == "FROZEN_AFTER_INDEPENDENT_AUDIT_BEFORE_CANDIDATE_QUERY"
    assert contract["successor_formal_name"] == "GENERATION_3_TEST_FIXTURE"
    assert contract["candidate_id"] == _authorization()["candidate_id"]
    assert contract["successor_normalizer_sha256"] == _sha(NORMALIZER)
    assert contract["successor_evaluator_sha256"] == _sha(EVALUATOR)
    assert contract["governance"]["protected_history_access_authorized"] is False
    assert contract["governance"]["phase7_authorized"] is False
    assert contract["governance"]["recon009_status"] == "OPEN"
    assert contract["selection_rules"]["manual_substitution_allowed"] is False


def test_exclusion_registry_contains_all_consumed_generations() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    distinct = {
        symbol
        for group in registry["permanent_exclusions"]
        for symbol in group["symbols"]
    }
    assert len(distinct) == 23
    gen2_groups = [
        group
        for group in registry["permanent_exclusions"]
        if group["reason"] == "GENERATION2_FINAL_HOLDOUT_FROZEN_ACCESSED_AND_CONSUMED"
    ]
    assert len(gen2_groups) == 1
    assert len(gen2_groups[0]["symbols"]) == 5
