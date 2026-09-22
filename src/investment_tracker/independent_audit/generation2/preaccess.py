from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from investment_tracker.independent_audit.generation2.virginity import (
    FROZEN_CANDIDATE_ID,
    LOCKED_SYMBOLS,
    verify_attestation,
)
from investment_tracker.quant.generation2.reproduction import verify_reproduction_report

STATUS_READY = "GENERATION2_PHASE6_PREACCESS_READY"
STATUS_BLOCKED = "GENERATION2_PHASE6_PREACCESS_BLOCKED"
REASON_INDEPENDENT_SOURCE = "INDEPENDENT_SOURCE_PROVENANCE_NOT_ESTABLISHED"


def evaluate_preaccess(
    *,
    attestation_path: Path,
    evidence_path: Path,
    selection_path: Path,
    selection_contract_path: Path,
    reproduction_report_path: Path,
) -> dict[str, Any]:
    attestation = verify_attestation(
        attestation_path=attestation_path,
        evidence_path=evidence_path,
        selection_path=selection_path,
        selection_contract_path=selection_contract_path,
    )
    reproduction = verify_reproduction_report(reproduction_report_path)

    if reproduction.get("survivor") != FROZEN_CANDIDATE_ID:
        raise ValueError("GEN2_PREACCESS_SURVIVOR_MISMATCH")

    independent = reproduction.get("independent_source_established")
    if independent is not True:
        return {
            "schema_version": "GENERATION2-PHASE6-PREACCESS-v1",
            "status": STATUS_BLOCKED,
            "reason": REASON_INDEPENDENT_SOURCE,
            "candidate_id": FROZEN_CANDIDATE_ID,
            "locked_symbols": list(LOCKED_SYMBOLS),
            "virginity_attestation_id": attestation["attestation_id"],
            "virginity_status": attestation["status"],
            "independent_source_established": False,
            "historical_acquisition_authorized": False,
            "phase7_authorized": False,
            "production_readiness_approved": False,
        }

    return {
        "schema_version": "GENERATION2-PHASE6-PREACCESS-v1",
        "status": STATUS_READY,
        "reason": None,
        "candidate_id": FROZEN_CANDIDATE_ID,
        "locked_symbols": list(LOCKED_SYMBOLS),
        "virginity_attestation_id": attestation["attestation_id"],
        "virginity_status": attestation["status"],
        "independent_source_established": True,
        "historical_acquisition_authorized": False,
        "phase7_authorized": False,
        "production_readiness_approved": False,
    }


def write_preaccess_status(payload: dict[str, Any], output_path: Path) -> Path:
    output = Path(output_path)
    if output.exists():
        raise FileExistsError("GEN2_PREACCESS_OUTPUT_EXISTS")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return output
