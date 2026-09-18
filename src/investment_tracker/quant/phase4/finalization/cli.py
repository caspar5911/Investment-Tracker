from __future__ import annotations

import argparse
import json
from pathlib import Path

from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity
from investment_tracker.quant.phase4.preregistration.canonical import artifact_envelope_identity

from .artifacts import FinalizationArtifactStore
from .audit import (
    CAMPAIGN_RESULT_SET_CONTENT,
    CAMPAIGN_RESULT_SET_IDENTITY,
    audit_campaign,
)
from .methodology import preflight_finalization, seal_finalization
from .selection import select_phase4_decision


def _artifact(kind: str, content: str, directory: str, filename: str) -> ArtifactIdentity:
    path = f"results/phase4/finalization/{directory}/sha256/{content}/{filename}"
    return ArtifactIdentity(
        kind=kind,
        content_sha256=content,
        path=path,
        sha256=artifact_envelope_identity(
            content_sha256=content,
            kind=kind,
            path=path,
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit")
    audit.add_argument("--repository-root", type=Path, required=True)
    audit.add_argument("--campaign-result-set-content-sha256", required=True)

    select = sub.add_parser("select")
    select.add_argument("--repository-root", type=Path, required=True)
    select.add_argument("--audit-content-sha256", required=True)

    seal = sub.add_parser("seal")
    seal.add_argument("--repository-root", type=Path, required=True)
    seal.add_argument("--source-revision", required=True)
    seal.add_argument("--audit-content-sha256", required=True)
    seal.add_argument("--decision-content-sha256", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--repository-root", type=Path, required=True)
    preflight.add_argument("--manifest-content-sha256", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = args.repository_root
    store = FinalizationArtifactStore(root)

    if args.command == "audit":
        if args.campaign_result_set_content_sha256 != CAMPAIGN_RESULT_SET_CONTENT:
            raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
        audit = audit_campaign(root, CAMPAIGN_RESULT_SET_IDENTITY)
        identity = store.write_audit(audit)
        print(json.dumps({
            "status": "PHASE4_FINALIZATION_AUDIT_COMPLETE",
            "content_sha256": identity.content_sha256,
            "envelope_sha256": identity.sha256,
            "eligible_candidate_count": len(audit.eligible_candidate_ids),
            "eligible_candidate_ids": list(audit.eligible_candidate_ids),
            "status_counts": audit.status_counts,
        }, sort_keys=True))
        return 0

    if args.command == "select":
        audit_identity = _artifact(
            "phase4_finalization_audit",
            args.audit_content_sha256,
            "audit",
            "audit.json",
        )
        audit = store.read_audit(audit_identity)
        decision = select_phase4_decision(audit, audit_artifact=audit_identity)
        identity = store.write_decision(decision)
        print(json.dumps({
            "status": decision.status,
            "selected_candidate_id": decision.selected_candidate_id,
            "content_sha256": identity.content_sha256,
            "envelope_sha256": identity.sha256,
        }, sort_keys=True))
        return 0

    if args.command == "seal":
        audit_identity = _artifact(
            "phase4_finalization_audit",
            args.audit_content_sha256,
            "audit",
            "audit.json",
        )
        decision_identity = _artifact(
            "phase4_finalization_decision",
            args.decision_content_sha256,
            "decision",
            "decision.json",
        )
        identity = seal_finalization(
            root,
            source_revision=args.source_revision,
            audit_identity=audit_identity,
            decision_identity=decision_identity,
        )
        print(json.dumps({
            "status": "PHASE4_FINALIZATION_SEALED",
            "content_sha256": identity.content_sha256,
            "envelope_sha256": identity.sha256,
        }, sort_keys=True))
        return 0

    result = preflight_finalization(root, args.manifest_content_sha256)
    print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
