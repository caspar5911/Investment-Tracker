from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from investment_tracker.independent_audit.post_generation3.authority import (
    BINDING,
    CANDIDATE_ID,
    IMPLEMENTATION,
    PREDECESSOR_COMMIT,
    PREDECESSOR_STATUS,
    SCHEMA,
    STATUS,
    PostGeneration3AuthorityError,
    load_methodology_authorization,
)

ROOT = Path(__file__).resolve().parents[2]
CLOSURE = ROOT / "data/generation3/phase6/phase6-final-holdout-closure.json"
SPLIT_CONTRACT = ROOT / "data/governance/successor/corporate-action-normalization-v2.json"
DIVIDEND_CONTRACT = ROOT / "data/governance/successor/dividend-reconciliation-v3.json"
SPLIT_NORMALIZER = ROOT / "src/investment_tracker/quant/successor/corporate_actions_v2.py"
DIVIDEND_RECONCILIATION = ROOT / "src/investment_tracker/quant/successor/dividend_reconciliation_v3.py"
EVALUATOR = ROOT / "src/investment_tracker/independent_audit/successor/evaluate_dividend_v3.py"
REGISTRY = ROOT / "data/governance/holdout-exclusion-registry.json"
TEMPLATE = ROOT / "data/governance/successor/post-generation3-methodology-authorization.template.json"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _payload() -> dict:
    return {
        "schema_version": SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": STATUS,
        "approval_id": "AUDIT-POST-GEN3-SYNTHETIC-1",
        "signed_by": "Synthetic Independent Auditor Fixture",
        "approved_at_utc": "2026-09-23T05:00:00Z",
        "predecessor_closure_commit": PREDECESSOR_COMMIT,
        "predecessor_phase6_status": PREDECESSOR_STATUS,
        "successor_formal_name": "GENERATION_4_TEST_FIXTURE",
        "candidate_id": CANDIDATE_ID,
        "binding_sha256": BINDING,
        "implementation_sha256": IMPLEMENTATION,
        "split_contract_sha256": _sha(SPLIT_CONTRACT),
        "dividend_contract_sha256": _sha(DIVIDEND_CONTRACT),
        "split_normalizer_sha256": _sha(SPLIT_NORMALIZER),
        "dividend_reconciliation_sha256": _sha(DIVIDEND_RECONCILIATION),
        "successor_evaluator_sha256": _sha(EVALUATOR),
        "holdout_exclusion_registry_sha256": _sha(REGISTRY),
        "evaluation_calendar_start": "2023-01-01",
        "evaluation_calendar_end": "2025-12-31",
        "required_pre_window_sessions": 210,
        "selection_count": 5,
        "listing_cutoff": "2022-03-03",
        "selection_seed_sha256": "4" * 64,
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


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _load(path: Path, *, closure_path: Path = CLOSURE):
    return load_methodology_authorization(
        authorization_path=path,
        predecessor_closure_path=closure_path,
        split_contract_path=SPLIT_CONTRACT,
        dividend_contract_path=DIVIDEND_CONTRACT,
        split_normalizer_path=SPLIT_NORMALIZER,
        dividend_reconciliation_path=DIVIDEND_RECONCILIATION,
        successor_evaluator_path=EVALUATOR,
        holdout_exclusion_registry_path=REGISTRY,
    )


def test_missing_authorization_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(
        PostGeneration3AuthorityError,
        match="POST_GEN3_INDEPENDENT_AUDIT_AUTHORIZATION_MISSING",
    ):
        _load(tmp_path / "missing.json")


def test_template_is_not_authorization() -> None:
    with pytest.raises(
        PostGeneration3AuthorityError,
        match="POST_GEN3_INDEPENDENT_AUDIT_AUTHORIZATION_INVALID",
    ):
        _load(TEMPLATE)


def test_valid_synthetic_authorization_binds_all_successor_inputs(tmp_path: Path) -> None:
    auth = _load(_write(tmp_path / "auth.json", _payload()))
    assert auth.successor_methodology_authorized is True
    assert auth.new_virgin_holdout_selection_authorized is True
    assert auth.protected_history_access_authorized is False
    assert auth.phase7_authorized is False
    assert auth.recon009_status == "OPEN"


def test_dividend_contract_tamper_fails_closed(tmp_path: Path) -> None:
    value = _payload()
    value["dividend_contract_sha256"] = "0" * 64
    with pytest.raises(
        PostGeneration3AuthorityError,
        match="POST_GEN3_IDENTITY_MISMATCH:dividend_contract_sha256",
    ):
        _load(_write(tmp_path / "auth.json", value))


def test_successor_evaluator_tamper_fails_closed(tmp_path: Path) -> None:
    value = _payload()
    value["successor_evaluator_sha256"] = "0" * 64
    with pytest.raises(
        PostGeneration3AuthorityError,
        match="POST_GEN3_IDENTITY_MISMATCH:successor_evaluator_sha256",
    ):
        _load(_write(tmp_path / "auth.json", value))


def test_predecessor_closure_is_consumed_unknown_and_phase7_false() -> None:
    closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
    assert closure["status"] == PREDECESSOR_STATUS
    assert closure["one_time_semantics"]["holdout_consumed"] is True
    assert closure["one_time_semantics"]["retry_authorized"] is False
    assert closure["phase7"]["authorized"] is False
    assert closure["recon009_status"] == "OPEN"


def test_registry_contains_28_permanently_excluded_symbols() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    symbols = {
        symbol
        for group in registry["permanent_exclusions"]
        for symbol in group["symbols"]
    }
    assert len(symbols) == 28


def test_predecessor_symbol_substitution_authority_fails_closed(
    tmp_path: Path,
) -> None:
    closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
    closure["one_time_semantics"]["symbol_substitution_authorized"] = True
    closure_path = tmp_path / "tampered-closure.json"
    closure_path.write_text(json.dumps(closure), encoding="utf-8")
    auth_path = _write(tmp_path / "auth.json", _payload())

    with pytest.raises(
        PostGeneration3AuthorityError,
        match="POST_GEN3_PREDECESSOR_CLOSURE_MISMATCH",
    ):
        _load(auth_path, closure_path=closure_path)
