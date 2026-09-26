from __future__ import annotations

import argparse
import json
from pathlib import Path

from investment_tracker.independent_audit.successor.virginity import capture_virginity

from .authority import load_methodology_authorization
from .selection_contract import build_holdout_selection_contract, seal_holdout_selection_contract
from .holdout_selection import acquire_and_select
from .phase6_contract import build_phase6_contract, seal_phase6_contract

DEFAULT_AUTH = "data/governance/successor/post-generation3-methodology-authorization.json"
DEFAULT_CLOSURE = "data/generation3/phase6/phase6-final-holdout-closure.json"
DEFAULT_SPLIT_CONTRACT = "data/governance/successor/corporate-action-normalization-v2.json"
DEFAULT_DIVIDEND_CONTRACT = "data/governance/successor/dividend-reconciliation-v3.json"
DEFAULT_SPLIT_NORMALIZER = "src/investment_tracker/quant/successor/corporate_actions_v2.py"
DEFAULT_DIVIDEND_RECONCILIATION = "src/investment_tracker/quant/successor/dividend_reconciliation_v3.py"
DEFAULT_EVALUATOR = "src/investment_tracker/independent_audit/successor/evaluate_dividend_v3.py"
DEFAULT_REGISTRY = "data/governance/holdout-exclusion-registry.json"


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--methodology-authorization", default=DEFAULT_AUTH)
    parser.add_argument("--predecessor-closure", default=DEFAULT_CLOSURE)
    parser.add_argument("--split-contract", default=DEFAULT_SPLIT_CONTRACT)
    parser.add_argument("--dividend-contract", default=DEFAULT_DIVIDEND_CONTRACT)
    parser.add_argument("--split-normalizer", default=DEFAULT_SPLIT_NORMALIZER)
    parser.add_argument("--dividend-reconciliation", default=DEFAULT_DIVIDEND_RECONCILIATION)
    parser.add_argument("--evaluator", default=DEFAULT_EVALUATOR)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)


def _load_auth(args: argparse.Namespace):
    return load_methodology_authorization(
        authorization_path=Path(args.methodology_authorization),
        predecessor_closure_path=Path(args.predecessor_closure),
        split_contract_path=Path(args.split_contract),
        dividend_contract_path=Path(args.dividend_contract),
        split_normalizer_path=Path(args.split_normalizer),
        dividend_reconciliation_path=Path(args.dividend_reconciliation),
        successor_evaluator_path=Path(args.evaluator),
        holdout_exclusion_registry_path=Path(args.registry),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investment-tracker-generation4-stage-a")
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify-methodology-authorization")
    _common(verify)

    seal = sub.add_parser("seal-selection-contract")
    _common(seal)
    seal.add_argument("--output", required=True)

    select = sub.add_parser("select-final-holdout")
    _common(select)
    select.add_argument("--selection-contract", required=True)
    select.add_argument("--log-path", action="append", required=True)
    select.add_argument("--output", required=True)
    select.add_argument("--static-snapshot-output", required=True)
    select.add_argument("--provider-ledger-output", required=True)
    select.add_argument("--host", default="127.0.0.1")
    select.add_argument("--port", type=int, default=11111)

    virgin = sub.add_parser("capture-virginity")
    virgin.add_argument("--selection", required=True)
    virgin.add_argument("--log-path", action="append", required=True)
    virgin.add_argument("--evidence-output", required=True)
    virgin.add_argument("--attestation-output", required=True)
    virgin.add_argument("--host", default="127.0.0.1")
    virgin.add_argument("--port", type=int, default=11111)

    phase6 = sub.add_parser("seal-phase6-contract")
    _common(phase6)
    phase6.add_argument("--selection", required=True)
    phase6.add_argument("--virginity-evidence", required=True)
    phase6.add_argument("--virginity-attestation", required=True)
    phase6.add_argument("--output", required=True)

    args = parser.parse_args(argv)

    if args.command == "verify-methodology-authorization":
        auth = _load_auth(args)
        print(json.dumps({
            "status": auth.status,
            "approval_id": auth.approval_id,
            "successor_formal_name": auth.successor_formal_name,
            "protected_history_access_authorized": auth.protected_history_access_authorized,
            "phase7_authorized": auth.phase7_authorized,
        }, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "seal-selection-contract":
        payload = build_holdout_selection_contract(
            authorization_path=Path(args.methodology_authorization),
            predecessor_closure_path=Path(args.predecessor_closure),
            split_contract_path=Path(args.split_contract),
            dividend_contract_path=Path(args.dividend_contract),
            split_normalizer_path=Path(args.split_normalizer),
            dividend_reconciliation_path=Path(args.dividend_reconciliation),
            successor_evaluator_path=Path(args.evaluator),
            holdout_exclusion_registry_path=Path(args.registry),
        )
        path = seal_holdout_selection_contract(payload, Path(args.output))
        print(json.dumps({"status": payload["status"], "output": str(path)}, sort_keys=True))
        return 0

    if args.command == "select-final-holdout":
        path = acquire_and_select(
            methodology_authorization_path=Path(args.methodology_authorization),
            selection_contract_path=Path(args.selection_contract),
            predecessor_closure_path=Path(args.predecessor_closure),
            split_contract_path=Path(args.split_contract),
            dividend_contract_path=Path(args.dividend_contract),
            split_normalizer_path=Path(args.split_normalizer),
            dividend_reconciliation_path=Path(args.dividend_reconciliation),
            successor_evaluator_path=Path(args.evaluator),
            holdout_exclusion_registry_path=Path(args.registry),
            log_paths=tuple(Path(item) for item in args.log_path),
            output_path=Path(args.output),
            static_snapshot_path=Path(args.static_snapshot_output),
            provider_ledger_output_path=Path(args.provider_ledger_output),
            host=args.host,
            port=args.port,
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps({
            "status": value["status"],
            "selected_symbols": [item["symbol"] for item in value.get("selected", [])],
            "historical_market_data_api_called": value["historical_market_data_api_called"],
            "output": str(path),
        }, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "capture-virginity":
        evidence, attestation = capture_virginity(
            selection_path=Path(args.selection),
            log_paths=tuple(Path(item) for item in args.log_path),
            evidence_output_path=Path(args.evidence_output),
            attestation_output_path=Path(args.attestation_output),
            host=args.host,
            port=args.port,
        )
        value = json.loads(attestation.read_text(encoding="utf-8"))
        print(json.dumps({
            "status": value["status"],
            "historical_market_data_api_called": False,
            "evidence": str(evidence),
            "attestation": str(attestation),
        }, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "seal-phase6-contract":
        payload = build_phase6_contract(
            methodology_authorization_path=Path(args.methodology_authorization),
            selection_path=Path(args.selection),
            virginity_evidence_path=Path(args.virginity_evidence),
            virginity_attestation_path=Path(args.virginity_attestation),
            predecessor_closure_path=Path(args.predecessor_closure),
            split_contract_path=Path(args.split_contract),
            dividend_contract_path=Path(args.dividend_contract),
            split_normalizer_path=Path(args.split_normalizer),
            dividend_reconciliation_path=Path(args.dividend_reconciliation),
            successor_evaluator_path=Path(args.evaluator),
            holdout_exclusion_registry_path=Path(args.registry),
        )
        path = seal_phase6_contract(payload, Path(args.output))
        print(json.dumps({
            "status": payload["status"],
            "protected_history_access_authorized": False,
            "phase7_authorized": False,
            "output": str(path),
        }, sort_keys=True, separators=(",", ":")))
        return 0

    raise ValueError("POST_GEN3_STAGE_A_COMMAND_UNSUPPORTED")


if __name__ == "__main__":
    raise SystemExit(main())
