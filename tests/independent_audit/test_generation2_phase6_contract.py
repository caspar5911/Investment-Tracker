from __future__ import annotations

import json
from pathlib import Path

import pytest

from investment_tracker.independent_audit.generation2 import phase6_contract as pc


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return path


def test_contract_build_requires_ready_preaccess(monkeypatch, tmp_path: Path):
    pre = _write(tmp_path / "pre.json", {
        "status": "GENERATION2_PHASE6_PREACCESS_BLOCKED",
        "locked_symbols": list(pc.LOCKED_SYMBOLS),
        "independent_source_established": False,
    })
    with pytest.raises(ValueError, match="GEN2_PHASE6_CONTRACT_PREACCESS_NOT_READY"):
        pc.build_contract(
            repository_root=tmp_path,
            preaccess_status_path=pre,
            selection_path=tmp_path / "selection.json",
            selection_contract_path=tmp_path / "selection-contract.json",
            virginity_attestation_path=tmp_path / "attestation.json",
            virginity_evidence_path=tmp_path / "evidence.json",
            provenance_root=tmp_path / "provenance",
        )


def test_contract_builds_only_from_verified_ready_inputs(monkeypatch, tmp_path: Path):
    pre = _write(tmp_path / "pre.json", {
        "status": "GENERATION2_PHASE6_PREACCESS_READY",
        "locked_symbols": list(pc.LOCKED_SYMBOLS),
        "independent_source_established": True,
        "primary_snapshot_sha256": "a" * 64,
        "provider_origin_snapshot_sha256": "b" * 64,
        "reconciliation_sha256": "c" * 64,
    })
    selection = _write(tmp_path / "selection.json", {"x": 1})
    selection_contract = _write(tmp_path / "selection-contract.json", {"x": 2})
    attestation = _write(tmp_path / "attestation.json", {"x": 3})
    evidence = _write(tmp_path / "evidence.json", {"x": 4})
    provenance_root = tmp_path / "provenance"
    provenance_root.mkdir()
    monkeypatch.setattr(pc, "verify_cache_provenance", lambda root: {
        "status": "MATCHED",
        "independent_source_established": True,
        "decision_critical": False,
        "primary_snapshot_sha256": "a" * 64,
        "provider_origin_snapshot_sha256": "b" * 64,
        "reconciliation_sha256": "c" * 64,
    })

    monkeypatch.setattr(pc, "verify_attestation", lambda **kwargs: {"status": "ok"})
    monkeypatch.setattr(
        pc,
        "verify_survivor_identity",
        lambda evidence_root, repository_root: {
            "candidate_id": pc.FROZEN_CANDIDATE_ID,
            "binding_sha256": pc.FROZEN_BINDING_SHA256,
            "implementation_sha256": pc.FROZEN_IMPLEMENTATION_SHA256,
            "report_sha256": pc.FROZEN_IDENTITY_SHA256,
            "candidate_binding": {
                "candidate_id": pc.FROZEN_CANDIDATE_ID,
                "family": "G2-A",
                "horizon_set": None,
                "lookback": 189,
                "rebalance": 21,
                "skip": 21,
                "top_k": 1,
                "trend_ma": None,
                "vol_lookback": None,
            },
        },
    )

    payload = pc.build_contract(
        repository_root=tmp_path,
        preaccess_status_path=pre,
        selection_path=selection,
        selection_contract_path=selection_contract,
        virginity_attestation_path=attestation,
        virginity_evidence_path=evidence,
        provenance_root=provenance_root,
    )
    assert payload["status"] == pc.CONTRACT_STATUS
    assert payload["final_holdout"]["locked_symbols"] == list(pc.LOCKED_SYMBOLS)
    assert payload["final_holdout"]["required_pre_window_sessions"] == 210
    assert payload["strategy"]["candidate_binding"]["lookback"] == 189
    assert payload["methodology"]["accounting"] == "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1"
    assert payload["methodology"]["signal_price_convention"] == "MOOMOO_QFQ_DAILY_RTH"
    assert payload["methodology"]["execution_price_convention"] == "MOOMOO_UNADJUSTED_DAILY_RTH"
    assert payload["friction"]["fixed_friction_cases_bps"] == [0, 3, 10, 25, 50]
    assert payload["governance"]["historical_access_authorized"] is False
    assert payload["result_contract"]["complete_status"] == "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"
    assert len(payload["contract_sha256"]) == 64


def test_seal_and_verify_contract(monkeypatch, tmp_path: Path):
    payload = {
        "schema_version": pc.CONTRACT_SCHEMA,
        "status": pc.CONTRACT_STATUS,
        "final_holdout": {"locked_symbols": list(pc.LOCKED_SYMBOLS)},
        "governance": {"historical_access_authorized": False},
    }
    payload["contract_sha256"] = pc.content_sha256(payload)
    path = tmp_path / "contract.json"
    pc.seal_contract(payload, path)
    verified = pc.verify_contract(path)
    assert verified["contract_sha256"] == payload["contract_sha256"]
    with pytest.raises(FileExistsError, match="GEN2_PHASE6_CONTRACT_EXISTS"):
        pc.seal_contract(payload, path)
