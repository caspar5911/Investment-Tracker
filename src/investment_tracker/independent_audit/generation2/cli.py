from __future__ import annotations

import argparse
import json
from pathlib import Path

from .holdout_selection import acquire_and_select
from .virginity import capture_composite_virginity
from .research_provenance_export import export_and_reconcile
from .research_provenance_cache import build_from_phase3_cache
from .preaccess import evaluate_preaccess, write_preaccess_status
from .phase6_contract import build_contract, seal_contract
from .authorization import issue_authorization
from .acquisition import acquire_and_seal, preflight_acquisition


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investment-tracker-generation2-audit")
    sub = parser.add_subparsers(dest="command", required=True)

    select = sub.add_parser("select-final-holdout")
    select.add_argument("--log-path", action="append", required=True)
    select.add_argument("--output", required=True)
    select.add_argument("--static-snapshot-output", required=True)
    select.add_argument("--provider-ledger-output", required=True)
    select.add_argument("--contract", default="data/governance/generation2-holdout-selection-contract.json")
    select.add_argument("--identity-root", default="data/governance/generation2-campaign")
    select.add_argument("--registry", default="data/governance/holdout-exclusion-registry.json")
    select.add_argument("--host", default="127.0.0.1")
    select.add_argument("--port", type=int, default=11111)

    virgin = sub.add_parser("capture-composite-virginity")
    virgin.add_argument("--log-path", action="append", required=True)
    virgin.add_argument("--evidence-output", required=True)
    virgin.add_argument("--attestation-output", required=True)
    virgin.add_argument("--selection", default="data/generation2/holdout-selection/selection.json")
    virgin.add_argument("--selection-contract", default="data/governance/generation2-holdout-selection-contract.json")
    virgin.add_argument("--host", default="127.0.0.1")
    virgin.add_argument("--port", type=int, default=11111)

    provenance = sub.add_parser("export-research-provenance")
    provenance.add_argument("--output-root", required=True)
    provenance.add_argument("--reproduction-report", default="data/governance/generation2-campaign/reproduction-report.json")
    provenance.add_argument("--host", default="127.0.0.1")
    provenance.add_argument("--port", type=int, default=11111)

    cache_provenance = sub.add_parser("build-cache-provenance")
    cache_provenance.add_argument("--cache-root", default="data/cache")
    cache_provenance.add_argument("--output-root", required=True)
    cache_provenance.add_argument("--reproduction-report", default="data/governance/generation2-campaign/reproduction-report.json")

    preaccess = sub.add_parser("evaluate-preaccess")
    preaccess.add_argument("--attestation", required=True)
    preaccess.add_argument("--evidence", required=True)
    preaccess.add_argument("--selection", default="data/generation2/holdout-selection/selection.json")
    preaccess.add_argument("--selection-contract", default="data/governance/generation2-holdout-selection-contract.json")
    preaccess.add_argument("--reproduction-report", default="data/governance/generation2-campaign/reproduction-report.json")
    preaccess.add_argument("--provenance-root", required=True)
    preaccess.add_argument("--output", required=True)

    contract = sub.add_parser("seal-phase6-contract")
    contract.add_argument("--repository-root", default=".")
    contract.add_argument("--preaccess-status", required=True)
    contract.add_argument("--selection", default="data/generation2/holdout-selection/selection.json")
    contract.add_argument("--selection-contract", default="data/governance/generation2-holdout-selection-contract.json")
    contract.add_argument("--attestation", required=True)
    contract.add_argument("--evidence", required=True)
    contract.add_argument("--provenance-root", required=True)
    contract.add_argument("--output", required=True)

    auth = sub.add_parser("issue-acquisition-authorization")
    auth.add_argument("--repository-root", default=".")
    auth.add_argument("--contract", required=True)
    auth.add_argument("--preaccess-status", required=True)
    auth.add_argument("--attestation", required=True)
    auth.add_argument("--evidence", required=True)
    auth.add_argument("--provenance-root", required=True)
    auth.add_argument("--evidence-commit-sha", required=True)
    auth.add_argument("--ci-run-id", required=True, type=int)
    auth.add_argument("--ci-conclusion", required=True)
    auth.add_argument("--output", required=True)

    preflight_acquire = sub.add_parser("preflight-final-holdout")
    preflight_acquire.add_argument("--repository-root", default=".")
    preflight_acquire.add_argument("--contract", default="data/generation2/phase6/evaluation-contract.json")
    preflight_acquire.add_argument("--authorization", default="data/generation2/phase6/acquisition-authorization.json")
    preflight_acquire.add_argument("--preaccess-status", default="data/generation2/preaccess/preaccess-status.json")
    preflight_acquire.add_argument("--attestation", default="data/generation2/preaccess/virginity-attestation.json")
    preflight_acquire.add_argument("--evidence", default="data/generation2/preaccess/virginity-evidence.json")
    preflight_acquire.add_argument("--provenance-root", default="data/generation2/preaccess/provenance")
    preflight_acquire.add_argument("--ci-classification", default="data/generation2/phase6/ci-classification.json")
    preflight_acquire.add_argument("--authorization-commit-sha", required=True)
    preflight_acquire.add_argument("--host", default="127.0.0.1")
    preflight_acquire.add_argument("--port", type=int, default=11111)

    acquire = sub.add_parser("acquire-final-holdout")
    acquire.add_argument("--repository-root", default=".")
    acquire.add_argument("--contract", default="data/generation2/phase6/evaluation-contract.json")
    acquire.add_argument("--authorization", default="data/generation2/phase6/acquisition-authorization.json")
    acquire.add_argument("--preaccess-status", default="data/generation2/preaccess/preaccess-status.json")
    acquire.add_argument("--attestation", default="data/generation2/preaccess/virginity-attestation.json")
    acquire.add_argument("--evidence", default="data/generation2/preaccess/virginity-evidence.json")
    acquire.add_argument("--provenance-root", default="data/generation2/preaccess/provenance")
    acquire.add_argument("--ci-classification", default="data/generation2/phase6/ci-classification.json")
    acquire.add_argument("--authorization-commit-sha", required=True)
    acquire.add_argument("--private-output-dir", required=True)
    acquire.add_argument("--host", default="127.0.0.1")
    acquire.add_argument("--port", type=int, default=11111)

    args = parser.parse_args(argv)

    if args.command == "select-final-holdout":
        path = acquire_and_select(
            log_paths=tuple(Path(item) for item in args.log_path),
            output_path=Path(args.output),
            static_snapshot_path=Path(args.static_snapshot_output),
            provider_ledger_output_path=Path(args.provider_ledger_output),
            contract_path=Path(args.contract),
            identity_root=Path(args.identity_root),
            registry_path=Path(args.registry),
            host=args.host,
            port=args.port,
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "selected_symbols": [item["symbol"] for item in payload.get("selected", [])],
                    "selection_seed_sha256": payload["selection_seed_sha256"],
                    "selection_contract_sha256": payload["selection_contract_sha256"],
                    "static_snapshot_sha256": payload["static_snapshot_sha256"],
                    "provider_ledger_sha256": payload["provider_ledger_sha256"],
                    "log_manifest_sha256": payload["log_manifest_sha256"],
                    "history_context_manifest_sha256": payload["history_context_manifest_sha256"],
                    "output": str(path),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0

    if args.command == "capture-composite-virginity":
        evidence, attestation = capture_composite_virginity(
            log_paths=tuple(Path(item) for item in args.log_path),
            evidence_output_path=Path(args.evidence_output),
            attestation_output_path=Path(args.attestation_output),
            selection_path=Path(args.selection),
            selection_contract_path=Path(args.selection_contract),
            host=args.host,
            port=args.port,
        )
        payload = json.loads(attestation.read_text(encoding="utf-8"))
        print(json.dumps({
            "status": payload["status"],
            "locked_symbols": payload["locked_symbols"],
            "provider_used_quota": payload["provider_used_quota"],
            "provider_remaining_quota": payload["provider_remaining_quota"],
            "evidence_bundle_sha256": payload["evidence_bundle_sha256"],
            "selection_sha256": payload["selection_sha256"],
            "independent_source_provenance_gate": payload["independent_source_provenance_gate"],
            "historical_acquisition_authorized": payload["historical_acquisition_authorized"],
            "evidence_output": str(evidence),
            "attestation_output": str(attestation),
        }, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "preflight-final-holdout":
        result = preflight_acquisition(
            repository_root=Path(args.repository_root), contract_path=Path(args.contract),
            authorization_path=Path(args.authorization), preaccess_status_path=Path(args.preaccess_status),
            attestation_path=Path(args.attestation), evidence_path=Path(args.evidence),
            provenance_root=Path(args.provenance_root), ci_classification_path=Path(args.ci_classification),
            authorization_commit_sha=args.authorization_commit_sha, host=args.host, port=args.port,
        )
        print(json.dumps(result, sort_keys=True,separators=(",",":")))
        return 0

    if args.command == "acquire-final-holdout":
        receipt = acquire_and_seal(
            repository_root=Path(args.repository_root), contract_path=Path(args.contract),
            authorization_path=Path(args.authorization), preaccess_status_path=Path(args.preaccess_status),
            attestation_path=Path(args.attestation), evidence_path=Path(args.evidence),
            provenance_root=Path(args.provenance_root), ci_classification_path=Path(args.ci_classification),
            authorization_commit_sha=args.authorization_commit_sha,
            private_output_dir=Path(args.private_output_dir), host=args.host, port=args.port,
        )
        payload=json.loads(receipt.read_text(encoding="utf-8"))
        print(json.dumps({"status":payload["status"],"holdout_id":payload["holdout_id"],"bundle_sha256":payload["bundle_sha256"],"performance_computed":payload["performance_computed"],"performance_inspected":payload["performance_inspected"],"receipt":str(receipt)}, sort_keys=True,separators=(",",":")))
        return 0

    if args.command == "issue-acquisition-authorization":
        path = issue_authorization(
            repository_root=Path(args.repository_root), contract_path=Path(args.contract),
            preaccess_status_path=Path(args.preaccess_status), attestation_path=Path(args.attestation),
            evidence_path=Path(args.evidence), provenance_root=Path(args.provenance_root),
            evidence_commit_sha=args.evidence_commit_sha, ci_run_id=args.ci_run_id,
            ci_conclusion=args.ci_conclusion, output_path=Path(args.output),
        )
        payload=json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps({"status":payload["status"],"authorization_id":payload["authorization_id"],"one_time":payload["one_time"],"output":str(path)}, sort_keys=True,separators=(",",":")))
        return 0

    if args.command == "seal-phase6-contract":
        payload = build_contract(
            repository_root=Path(args.repository_root),
            preaccess_status_path=Path(args.preaccess_status),
            selection_path=Path(args.selection),
            selection_contract_path=Path(args.selection_contract),
            virginity_attestation_path=Path(args.attestation),
            virginity_evidence_path=Path(args.evidence),
            provenance_root=Path(args.provenance_root),
        )
        seal_contract(payload, Path(args.output))
        print(json.dumps({
            "status": payload["status"],
            "contract_sha256": payload["contract_sha256"],
            "candidate_id": payload["strategy"]["candidate_id"],
            "locked_symbols": payload["final_holdout"]["locked_symbols"],
            "historical_access_authorized": payload["governance"]["historical_access_authorized"],
            "output": args.output,
        }, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "evaluate-preaccess":
        result = evaluate_preaccess(
            attestation_path=Path(args.attestation),
            evidence_path=Path(args.evidence),
            selection_path=Path(args.selection),
            selection_contract_path=Path(args.selection_contract),
            reproduction_report_path=Path(args.reproduction_report),
            provenance_root=Path(args.provenance_root),
        )
        write_preaccess_status(result, Path(args.output))
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result["status"] == "GENERATION2_PHASE6_PREACCESS_READY" else 2

    if args.command == "build-cache-provenance":
        result = build_from_phase3_cache(
            cache_root=Path(args.cache_root),
            output_root=Path(args.output_root),
            reproduction_report_path=Path(args.reproduction_report),
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "export-research-provenance":
        result = export_and_reconcile(
            output_root=Path(args.output_root),
            reproduction_report_path=Path(args.reproduction_report),
            host=args.host,
            port=args.port,
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0

    raise ValueError("GENERATION2_AUDIT_COMMAND_UNSUPPORTED")


if __name__ == "__main__":
    raise SystemExit(main())
