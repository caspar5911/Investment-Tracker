from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from investment_tracker.independent_audit.post_generation3.authority import (
    load_methodology_authorization,
)
from investment_tracker.independent_audit.post_generation3.selection_contract import (
    build_holdout_selection_contract,
)
from investment_tracker.independent_audit.post_generation3.phase6_contract import (
    build_phase6_contract,
)
from investment_tracker.independent_audit.post_generation3 import cli as stage_a_cli
from investment_tracker.independent_audit.successor.virginity import (
    ATTESTATION_SCHEMA,
    ATTESTATION_STATUS,
)

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "data/governance/successor/post-generation3-methodology-authorization.json"
CLOSURE = ROOT / "data/generation3/phase6/phase6-final-holdout-closure.json"
SPLIT_CONTRACT = ROOT / "data/governance/successor/corporate-action-normalization-v2.json"
DIVIDEND_CONTRACT = ROOT / "data/governance/successor/dividend-reconciliation-v3.json"
SPLIT_NORMALIZER = ROOT / "src/investment_tracker/quant/successor/corporate_actions_v2.py"
DIVIDEND_RECONCILIATION = ROOT / "src/investment_tracker/quant/successor/dividend_reconciliation_v3.py"
EVALUATOR = ROOT / "src/investment_tracker/independent_audit/successor/evaluate_dividend_v3.py"
REGISTRY = ROOT / "data/governance/holdout-exclusion-registry.json"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _auth():
    return load_methodology_authorization(
        authorization_path=AUTH,
        predecessor_closure_path=CLOSURE,
        split_contract_path=SPLIT_CONTRACT,
        dividend_contract_path=DIVIDEND_CONTRACT,
        split_normalizer_path=SPLIT_NORMALIZER,
        dividend_reconciliation_path=DIVIDEND_RECONCILIATION,
        successor_evaluator_path=EVALUATOR,
        holdout_exclusion_registry_path=REGISTRY,
    )


def _write(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def test_real_generation4_stage_a_authorization_loads() -> None:
    auth = _auth()
    assert auth.successor_formal_name == "GENERATION_4"
    assert auth.approval_id == "INDEP-AUDIT-GEN4-METHODOLOGY-0001"
    assert auth.protected_history_access_authorized is False
    assert auth.phase7_authorized is False


def test_generation4_selection_contract_binds_dividend_v3() -> None:
    auth = _auth()
    contract = build_holdout_selection_contract(
        authorization_path=AUTH,
        predecessor_closure_path=CLOSURE,
        split_contract_path=SPLIT_CONTRACT,
        dividend_contract_path=DIVIDEND_CONTRACT,
        split_normalizer_path=SPLIT_NORMALIZER,
        dividend_reconciliation_path=DIVIDEND_RECONCILIATION,
        successor_evaluator_path=EVALUATOR,
        holdout_exclusion_registry_path=REGISTRY,
    )
    assert contract["schema_version"] == "SUCCESSOR-HOLDOUT-SELECTION-CONTRACT-v2"
    assert contract["successor_formal_name"] == "GENERATION_4"
    assert contract["dividend_contract_sha256"] == auth.dividend_contract_sha256
    assert contract["dividend_reconciliation_sha256"] == auth.dividend_reconciliation_sha256
    assert contract["successor_evaluator_sha256"] == auth.successor_evaluator_sha256
    assert contract["governance"]["protected_history_access_authorized"] is False
    assert contract["selection_rules"]["manual_substitution_allowed"] is False


def test_generation4_stage_a_cli_exposes_no_acquisition_commands() -> None:
    source = Path(stage_a_cli.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "preflight-final-holdout",
        "acquire-final-holdout",
        "issue-final-holdout-release",
        "evaluate-final-holdout",
        "close-phase6",
    ):
        assert forbidden not in source


def test_generation4_phase6_contract_binds_new_evaluator_and_dividend_authority(
    tmp_path: Path,
) -> None:
    auth = _auth()
    symbols = ["SYN1", "SYN2", "SYN3", "SYN4", "SYN5"]
    selection = _write(
        tmp_path / "selection.json",
        {
            "schema_version": "SUCCESSOR-BLIND-FINAL-HOLDOUT-SELECTION-v1",
            "authority": "INDEPENDENT_AUDIT",
            "status": "SUCCESSOR_HOLDOUT_SELECTION_FROZEN",
            "successor_formal_name": auth.successor_formal_name,
            "methodology_authorization_id": auth.approval_id,
            "methodology_authorization_sha256": _sha(AUTH),
            "candidate_id": auth.candidate_id,
            "binding_sha256": auth.binding_sha256,
            "implementation_sha256": auth.implementation_sha256,
            "split_contract_sha256": auth.split_contract_sha256,
            "dividend_contract_sha256": auth.dividend_contract_sha256,
            "split_normalizer_sha256": auth.split_normalizer_sha256,
            "dividend_reconciliation_sha256": auth.dividend_reconciliation_sha256,
            "successor_evaluator_sha256": auth.successor_evaluator_sha256,
            "holdout_exclusion_registry_sha256": _sha(REGISTRY),
            "historical_market_data_api_called": False,
            "protected_history_access_authorized": False,
            "selected": [
                {"position": index + 1, "symbol": symbol}
                for index, symbol in enumerate(symbols)
            ],
        },
    )
    evidence = _write(
        tmp_path / "evidence.json",
        {
            "status": ATTESTATION_STATUS,
            "historical_market_data_api_called": False,
            "protected_history_access_authorized": False,
        },
    )
    attestation = _write(
        tmp_path / "attestation.json",
        {
            "schema_version": ATTESTATION_SCHEMA,
            "status": ATTESTATION_STATUS,
            "selected_symbols": symbols,
            "selection_sha256": _sha(selection),
            "evidence_bundle_sha256": _sha(evidence),
            "historical_market_data_api_called": False,
            "protected_history_access_authorized": False,
        },
    )

    contract = build_phase6_contract(
        methodology_authorization_path=AUTH,
        selection_path=selection,
        virginity_evidence_path=evidence,
        virginity_attestation_path=attestation,
        predecessor_closure_path=CLOSURE,
        split_contract_path=SPLIT_CONTRACT,
        dividend_contract_path=DIVIDEND_CONTRACT,
        split_normalizer_path=SPLIT_NORMALIZER,
        dividend_reconciliation_path=DIVIDEND_RECONCILIATION,
        successor_evaluator_path=EVALUATOR,
        holdout_exclusion_registry_path=REGISTRY,
    )
    assert contract["schema_version"] == "SUCCESSOR-PHASE6-EVALUATION-CONTRACT-v2"
    assert contract["status"] == "FROZEN_PRE_ACCESS"
    assert contract["methodology"]["accounting"] == "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v3"
    assert contract["methodology"]["dividend_amount_authority"] == "MOOMOO_REHAB_STRUCTURED_FIELDS"
    assert contract["methodology"]["endpoint_statement_numeric_authority"] is False
    assert contract["methodology"]["successor_evaluator_sha256"] == _sha(EVALUATOR)
    assert contract["governance"]["protected_history_access_authorized"] is False
    assert contract["governance"]["acquisition_authorization_required"] is True
    assert contract["governance"]["phase7_authorized"] is False
