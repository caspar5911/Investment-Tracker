from __future__ import annotations

import argparse
import json
from pathlib import Path

from .holdout_selection import acquire_and_select
from .virginity import capture_composite_virginity
from .research_provenance_export import export_and_reconcile


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
