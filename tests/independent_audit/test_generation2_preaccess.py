from __future__ import annotations

from pathlib import Path

import pytest

from investment_tracker.independent_audit.generation2 import preaccess


def test_preaccess_blocks_when_independent_source_not_established(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        preaccess,
        "verify_attestation",
        lambda **kwargs: {
            "attestation_id": "gen2-composite-test",
            "status": "COMPOSITE_EVIDENCE_NO_PRIOR_LOCKED_SYMBOL_ACCESS_FOUND",
        },
    )
    monkeypatch.setattr(
        preaccess,
        "verify_reproduction_report",
        lambda path: {
            "survivor": preaccess.FROZEN_CANDIDATE_ID,
            "independent_source_established": False,
        },
    )
    monkeypatch.setattr(preaccess, "verify_cache_provenance", lambda root: {
        "status": "UNKNOWN_ABSTAIN",
        "independent_source_established": False,
        "decision_critical": False,
    })
    result = preaccess.evaluate_preaccess(
        attestation_path=Path("a"),
        evidence_path=Path("b"),
        selection_path=Path("c"),
        selection_contract_path=Path("d"),
        reproduction_report_path=Path("e"),
        provenance_root=tmp_path,
    )
    assert result["status"] == preaccess.STATUS_BLOCKED
    assert result["reason"] == preaccess.REASON_INDEPENDENT_SOURCE
    assert result["historical_acquisition_authorized"] is False
    assert result["phase7_authorized"] is False


def test_preaccess_ready_only_when_both_gates_verify(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        preaccess,
        "verify_attestation",
        lambda **kwargs: {
            "attestation_id": "gen2-composite-test",
            "status": "COMPOSITE_EVIDENCE_NO_PRIOR_LOCKED_SYMBOL_ACCESS_FOUND",
        },
    )
    monkeypatch.setattr(
        preaccess,
        "verify_reproduction_report",
        lambda path: {
            "survivor": preaccess.FROZEN_CANDIDATE_ID,
            "independent_source_established": True,
        },
    )
    monkeypatch.setattr(preaccess, "verify_cache_provenance", lambda root: {
        "status": "MATCHED",
        "independent_source_established": True,
        "decision_critical": False,
        "primary_snapshot_sha256": "a" * 64,
        "provider_origin_snapshot_sha256": "b" * 64,
        "reconciliation_sha256": "c" * 64,
    })
    result = preaccess.evaluate_preaccess(
        attestation_path=Path("a"),
        evidence_path=Path("b"),
        selection_path=Path("c"),
        selection_contract_path=Path("d"),
        reproduction_report_path=Path("e"),
        provenance_root=tmp_path,
    )
    assert result["status"] == preaccess.STATUS_READY
    assert result["independent_source_established"] is True
    assert result["historical_acquisition_authorized"] is False


def test_preaccess_rejects_survivor_mismatch(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        preaccess,
        "verify_attestation",
        lambda **kwargs: {
            "attestation_id": "gen2-composite-test",
            "status": "COMPOSITE_EVIDENCE_NO_PRIOR_LOCKED_SYMBOL_ACCESS_FOUND",
        },
    )
    monkeypatch.setattr(
        preaccess,
        "verify_reproduction_report",
        lambda path: {
            "survivor": "OTHER",
            "independent_source_established": True,
        },
    )
    monkeypatch.setattr(preaccess, "verify_cache_provenance", lambda root: {
        "status": "MATCHED",
        "independent_source_established": True,
        "decision_critical": False,
        "primary_snapshot_sha256": "a" * 64,
        "provider_origin_snapshot_sha256": "b" * 64,
        "reconciliation_sha256": "c" * 64,
    })
    with pytest.raises(ValueError, match="GEN2_PREACCESS_SURVIVOR_MISMATCH"):
        preaccess.evaluate_preaccess(
            attestation_path=Path("a"),
            evidence_path=Path("b"),
            selection_path=Path("c"),
            selection_contract_path=Path("d"),
            reproduction_report_path=Path("e"),
        provenance_root=tmp_path,
        )


def test_write_preaccess_status_is_exclusive(tmp_path: Path):
    out = tmp_path / "status.json"
    preaccess.write_preaccess_status({"status": "x"}, out)
    with pytest.raises(FileExistsError, match="GEN2_PREACCESS_OUTPUT_EXISTS"):
        preaccess.write_preaccess_status({"status": "y"}, out)
