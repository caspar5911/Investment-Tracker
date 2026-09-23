from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from .authority import authorization_summary, load_methodology_authorization
from .selection_contract import build_holdout_selection_contract, seal_holdout_selection_contract
from .holdout_selection import acquire_and_select
from .virginity import capture_virginity
from .phase6_contract import build_phase6_contract, seal_phase6_contract
from .acquisition_authority import load_acquisition_authorization
from .acquisition import preflight_acquisition, acquire_and_seal
from .release import issue_release
from .evaluate import evaluate_released_holdout
from .closure import close_phase6

DEFAULT_CA_CONTRACT = "data/governance/successor/corporate-action-normalization-v2.json"
DEFAULT_REGISTRY = "data/governance/holdout-exclusion-registry.json"
DEFAULT_CLOSURE = "data/generation2/phase6/phase6-final-holdout-closure.json"
DEFAULT_NORMALIZER = "src/investment_tracker/quant/successor/corporate_actions_v2.py"
DEFAULT_EVALUATOR = "src/investment_tracker/independent_audit/successor/evaluate.py"


def _common_methodology_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--methodology-authorization", required=True)
    parser.add_argument("--corporate-action-contract", default=DEFAULT_CA_CONTRACT)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--predecessor-closure", default=DEFAULT_CLOSURE)
    parser.add_argument("--normalizer", default=DEFAULT_NORMALIZER)
    parser.add_argument("--evaluator", default=DEFAULT_EVALUATOR)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investment-tracker-successor-audit")
    sub = parser.add_subparsers(dest="command", required=True)

    bindings = sub.add_parser("print-audit-code-bindings")
    bindings.add_argument("--corporate-action-contract", default=DEFAULT_CA_CONTRACT)
    bindings.add_argument("--registry", default=DEFAULT_REGISTRY)
    bindings.add_argument("--normalizer", default=DEFAULT_NORMALIZER)
    bindings.add_argument("--evaluator", default=DEFAULT_EVALUATOR)
    bindings.add_argument("--acquisition", default="src/investment_tracker/independent_audit/successor/acquisition.py")
    bindings.add_argument("--release", default="src/investment_tracker/independent_audit/successor/release.py")

    verify_method = sub.add_parser("verify-methodology-authorization")
    _common_methodology_args(verify_method)

    seal_selection = sub.add_parser("seal-selection-contract")
    _common_methodology_args(seal_selection)
    seal_selection.add_argument("--output", required=True)

    select = sub.add_parser("select-final-holdout")
    _common_methodology_args(select)
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
    _common_methodology_args(phase6)
    phase6.add_argument("--selection", required=True)
    phase6.add_argument("--virginity-evidence", required=True)
    phase6.add_argument("--virginity-attestation", required=True)
    phase6.add_argument("--output", required=True)

    verify_acq = sub.add_parser("verify-acquisition-authorization")
    verify_acq.add_argument("--acquisition-authorization", required=True)
    verify_acq.add_argument("--phase6-contract", required=True)
    verify_acq.add_argument("--selection", required=True)
    verify_acq.add_argument("--virginity-evidence", required=True)
    verify_acq.add_argument("--virginity-attestation", required=True)

    preflight = sub.add_parser("preflight-final-holdout")
    preflight.add_argument("--acquisition-authorization", required=True)
    preflight.add_argument("--phase6-contract", required=True)
    preflight.add_argument("--selection", required=True)
    preflight.add_argument("--virginity-evidence", required=True)
    preflight.add_argument("--virginity-attestation", required=True)
    preflight.add_argument("--host", default="127.0.0.1")
    preflight.add_argument("--port", type=int, default=11111)

    acquire = sub.add_parser("acquire-final-holdout")
    acquire.add_argument("--repository-root", default=".")
    acquire.add_argument("--acquisition-authorization", required=True)
    acquire.add_argument("--phase6-contract", required=True)
    acquire.add_argument("--selection", required=True)
    acquire.add_argument("--virginity-evidence", required=True)
    acquire.add_argument("--virginity-attestation", required=True)
    acquire.add_argument("--private-output-dir", required=True)
    acquire.add_argument("--host", default="127.0.0.1")
    acquire.add_argument("--port", type=int, default=11111)

    release = sub.add_parser("issue-final-holdout-release")
    release.add_argument("--phase6-contract", required=True)
    release.add_argument("--acquisition-authorization", required=True)
    release.add_argument("--selection", required=True)
    release.add_argument("--virginity-evidence", required=True)
    release.add_argument("--virginity-attestation", required=True)
    release.add_argument("--receipt", required=True)
    release.add_argument("--bundle", required=True)
    release.add_argument("--key", required=True)
    release.add_argument("--output", required=True)
    release.add_argument("--receipt-evidence-output", required=True)

    evaluate = sub.add_parser("evaluate-final-holdout")
    evaluate.add_argument("--repository-root", default=".")
    evaluate.add_argument("--release", required=True)
    evaluate.add_argument("--phase6-contract", required=True)
    evaluate.add_argument("--acquisition-authorization", required=True)
    evaluate.add_argument("--selection", required=True)
    evaluate.add_argument("--virginity-evidence", required=True)
    evaluate.add_argument("--virginity-attestation", required=True)
    evaluate.add_argument("--receipt", required=True)
    evaluate.add_argument("--bundle", required=True)
    evaluate.add_argument("--key", required=True)
    evaluate.add_argument("--marker-directory", required=True)
    evaluate.add_argument("--output", required=True)

    close = sub.add_parser("close-phase6")
    close.add_argument("--phase6-contract", required=True)
    close.add_argument("--release", required=True)
    close.add_argument("--result", required=True)
    close.add_argument("--consumption-marker", required=True)
    close.add_argument("--acquisition-receipt", required=True)
    close.add_argument("--output", required=True)

    args = parser.parse_args(argv)

    if args.command == "print-audit-code-bindings":
        def digest(value: str) -> str:
            return sha256(Path(value).read_bytes()).hexdigest()
        print(json.dumps({
            "predecessor_closure_commit": "f875167f3e758ab3391ff2f961aa740f231568e5",
            "candidate_id": "G2-A|lookback=189|skip=21|top_k=1|rebalance=21",
            "binding_sha256": "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b",
            "implementation_sha256": "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b",
            "corporate_action_contract_sha256": digest(args.corporate_action_contract),
            "holdout_exclusion_registry_sha256": digest(args.registry),
            "successor_normalizer_sha256": digest(args.normalizer),
            "successor_evaluator_sha256": digest(args.evaluator),
            "acquisition_implementation_sha256": digest(args.acquisition),
            "release_implementation_sha256": digest(args.release),
            "authority_granted": False,
            "protected_history_access_authorized": False,
            "phase7_authorized": False,
        }, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "verify-methodology-authorization":
        auth = load_methodology_authorization(
            authorization_path=Path(args.methodology_authorization),
            corporate_action_contract_path=Path(args.corporate_action_contract),
            holdout_exclusion_registry_path=Path(args.registry),
            predecessor_closure_path=Path(args.predecessor_closure),
            successor_normalizer_path=Path(args.normalizer),
            successor_evaluator_path=Path(args.evaluator),
        )
        print(json.dumps(authorization_summary(auth), sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "seal-selection-contract":
        payload = build_holdout_selection_contract(
            authorization_path=Path(args.methodology_authorization),
            corporate_action_contract_path=Path(args.corporate_action_contract),
            holdout_exclusion_registry_path=Path(args.registry),
            predecessor_closure_path=Path(args.predecessor_closure),
            successor_normalizer_path=Path(args.normalizer),
            successor_evaluator_path=Path(args.evaluator),
        )
        path = seal_holdout_selection_contract(payload, Path(args.output))
        print(json.dumps({"status": payload["status"], "output": str(path)}, sort_keys=True))
        return 0

    if args.command == "select-final-holdout":
        path = acquire_and_select(
            repository_root=Path("."),
            methodology_authorization_path=Path(args.methodology_authorization),
            selection_contract_path=Path(args.selection_contract),
            corporate_action_contract_path=Path(args.corporate_action_contract),
            successor_normalizer_path=Path(args.normalizer),
            successor_evaluator_path=Path(args.evaluator),
            holdout_exclusion_registry_path=Path(args.registry),
            predecessor_closure_path=Path(args.predecessor_closure),
            log_paths=tuple(Path(item) for item in args.log_path),
            output_path=Path(args.output),
            static_snapshot_path=Path(args.static_snapshot_output),
            provider_ledger_output_path=Path(args.provider_ledger_output),
            host=args.host,
            port=args.port,
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps({
            "status": payload["status"],
            "selected_symbols": [item["symbol"] for item in payload.get("selected", [])],
            "historical_market_data_api_called": payload["historical_market_data_api_called"],
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
        print(json.dumps({"status": value["status"], "historical_market_data_api_called": False, "evidence": str(evidence), "attestation": str(attestation)}, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "seal-phase6-contract":
        payload = build_phase6_contract(
            methodology_authorization_path=Path(args.methodology_authorization),
            selection_path=Path(args.selection),
            virginity_evidence_path=Path(args.virginity_evidence),
            virginity_attestation_path=Path(args.virginity_attestation),
            corporate_action_contract_path=Path(args.corporate_action_contract),
            successor_normalizer_path=Path(args.normalizer),
            successor_evaluator_path=Path(args.evaluator),
            holdout_exclusion_registry_path=Path(args.registry),
            predecessor_closure_path=Path(args.predecessor_closure),
        )
        path = seal_phase6_contract(payload, Path(args.output))
        print(json.dumps({"status": payload["status"], "protected_history_access_authorized": False, "output": str(path)}, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "verify-acquisition-authorization":
        auth = load_acquisition_authorization(
            authorization_path=Path(args.acquisition_authorization),
            phase6_contract_path=Path(args.phase6_contract),
            selection_path=Path(args.selection),
            virginity_attestation_path=Path(args.virginity_attestation),
            virginity_evidence_path=Path(args.virginity_evidence),
        )
        print(json.dumps({"status": auth.status, "authorization_id": auth.authorization_id, "one_time": auth.one_time, "phase7_authorized": auth.phase7_authorized}, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "preflight-final-holdout":
        result = preflight_acquisition(
            authorization_path=Path(args.acquisition_authorization),
            phase6_contract_path=Path(args.phase6_contract),
            selection_path=Path(args.selection),
            virginity_attestation_path=Path(args.virginity_attestation),
            virginity_evidence_path=Path(args.virginity_evidence),
            host=args.host,
            port=args.port,
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "acquire-final-holdout":
        receipt = acquire_and_seal(
            repository_root=Path(args.repository_root),
            authorization_path=Path(args.acquisition_authorization),
            phase6_contract_path=Path(args.phase6_contract),
            selection_path=Path(args.selection),
            virginity_attestation_path=Path(args.virginity_attestation),
            virginity_evidence_path=Path(args.virginity_evidence),
            private_output_dir=Path(args.private_output_dir),
            host=args.host,
            port=args.port,
        )
        value = json.loads(receipt.read_text(encoding="utf-8"))
        print(json.dumps({"status": value["status"], "holdout_id": value["holdout_id"], "performance_inspected": value["performance_inspected"], "receipt": str(receipt)}, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "issue-final-holdout-release":
        path = issue_release(
            contract_path=Path(args.phase6_contract),
            authorization_path=Path(args.acquisition_authorization),
            selection_path=Path(args.selection),
            virginity_attestation_path=Path(args.virginity_attestation),
            virginity_evidence_path=Path(args.virginity_evidence),
            receipt_path=Path(args.receipt),
            encrypted_bundle_path=Path(args.bundle),
            key_path=Path(args.key),
            output_path=Path(args.output),
            receipt_evidence_path=Path(args.receipt_evidence_output),
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps({"status": value["status"], "release_id": value["release_id"], "phase7_authorized": value["phase7_authorized"], "output": str(path)}, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "evaluate-final-holdout":
        result = evaluate_released_holdout(
            repository_root=Path(args.repository_root),
            release_path=Path(args.release),
            contract_path=Path(args.phase6_contract),
            authorization_path=Path(args.acquisition_authorization),
            selection_path=Path(args.selection),
            virginity_attestation_path=Path(args.virginity_attestation),
            virginity_evidence_path=Path(args.virginity_evidence),
            receipt_path=Path(args.receipt),
            encrypted_bundle_path=Path(args.bundle),
            key_path=Path(args.key),
            marker_directory=Path(args.marker_directory),
            output_path=Path(args.output),
        )
        print(json.dumps({"status": result["status"], "one_time_consumed": result.get("one_time_consumed"), "phase7_authorized": result.get("phase7_authorized"), "output": args.output}, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "close-phase6":
        result = close_phase6(
            contract_path=Path(args.phase6_contract),
            release_path=Path(args.release),
            result_path=Path(args.result),
            consumption_marker_path=Path(args.consumption_marker),
            acquisition_receipt_path=Path(args.acquisition_receipt),
            output_path=Path(args.output),
        )
        print(json.dumps({"status": result["status"], "phase7_eligible": result["phase7"]["eligible_for_independent_entry_review"], "phase7_authorized": result["phase7"]["authorized"], "output": args.output}, sort_keys=True, separators=(",", ":")))
        return 0

    raise ValueError("SUCCESSOR_AUDIT_COMMAND_UNSUPPORTED")


if __name__ == "__main__":
    raise SystemExit(main())
