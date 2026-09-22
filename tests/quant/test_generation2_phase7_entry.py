from __future__ import annotations

import json
from pathlib import Path

import pytest

from investment_tracker.quant.generation2 import ci_gate, phase7_entry
from investment_tracker.quant.generation2.phase7_entry import (
    PHASE7_ENTRY_AUTHORITY,
    REQUIRED_PHASE6_STATUS,
    Phase7EntryGateError,
    evaluate_generation2_phase7_entry,
    seal_generation2_phase7_entry,
    verify_generation2_phase7_entry,
)


ROOT = Path(__file__).resolve().parents[2]
SURVIVOR = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _sha(text: str) -> str:
    return "1" * 63 + "a"


def _auth_dict(flags: dict[str, bool] | None = None) -> dict:
    base = {
        "schema_version": "GENERATION2-GOVERNANCE-AUTHORITY-v1",
        "status": "FROZEN_FOR_IMPLEMENTATION",
        "generation": "GENERATION_2",
        "real_final_holdout_access_authorized": False,
        "phase7_authorized": False,
        "production_readiness_approved": False,
    }
    if flags is not None:
        base.update(flags)
    return base


def _registry_dict() -> dict:
    # The CI gate requires the real research universe to be permanently
    # excluded; drive the synthetic registry from that constant so it always
    # stays in lockstep with ``ci_gate``.
    symbols = list(ci_gate.RESEARCH_SYMBOLS)
    return {
        "schema_version": "HOLDOUT-EXCLUSION-REGISTRY-v1",
        "status": "FROZEN",
        "permanent_exclusions": [
            {"symbols": symbols, "reason": "SYNTHETIC_TEST_EXCLUSION"}
        ],
    }


def _make_repo_root(tmp_path: Path, flags: dict[str, bool] | None = None) -> Path:
    (tmp_path / ci_gate.AUTHORITY_REL).parent.mkdir(parents=True, exist_ok=True)
    _write(tmp_path / ci_gate.AUTHORITY_REL, _auth_dict(flags))
    _write(tmp_path / ci_gate.REGISTRY_REL, _registry_dict())
    return tmp_path


def _make_phase6(tmp_path: Path, candidate: str, status: str = REQUIRED_PHASE6_STATUS) -> Path:
    return _write(
        tmp_path / "phase6.json",
        {
            "status": status,
            "candidate_id": candidate,
            "one_time_consumed": True,
            "phase7_started": False,
            "production_readiness_approved": False,
        },
    )


def _make_artifact(tmp_path: Path, candidate: str, *, phase6_status: str = REQUIRED_PHASE6_STATUS, authority: str = PHASE7_ENTRY_AUTHORITY, name: str = "entry.json") -> Path:
    """Write a sealed, self-hashing entry artifact and return its path."""
    payload = {
        "schema_version": phase7_entry.GENERATION2_PHASE7_ENTRY_SCHEMA,
        "authority": authority,
        "generation": "GENERATION_2",
        "candidate_id": candidate,
        "survivor": SURVIVOR,
        "phase6_status": phase6_status,
        "phase6_result_sha256": _sha("phase6"),
        "validation_report_sha256": _sha("validation"),
        "survivor_freeze_sha256": _sha("freeze"),
        "survivor_rehearsal_sha256": _sha("rehearsal"),
    }
    from investment_tracker.quant.generation2.campaign import content_sha256
    payload["artifact_sha256"] = content_sha256(payload)
    return _write(tmp_path / name, payload)


def test_gate_passes_when_all_three_prerequisites_hold(tmp_path: Path):
    root = _make_repo_root(tmp_path)
    candidate = "gen2-candidate-" + "a" * 40
    phase6 = _make_phase6(tmp_path, candidate)
    artifact = _make_artifact(tmp_path, candidate)

    report = evaluate_generation2_phase7_entry(
        phase6_result_path=phase6,
        entry_artifact_path=artifact,
        repository_root=root,
    )

    assert report["status"] == "GENERATION2_PHASE7_ENTRY_ALLOWED"
    assert report["candidate_id"] == candidate
    assert report["survivor"] == SURVIVOR
    assert report["phase6_status"] == REQUIRED_PHASE6_STATUS
    # CI gate must be embedded verbatim, proving authority flags stayed false.
    assert report["ci_gate"]["status"] == "PASS"
    assert report["ci_gate"]["real_final_holdout_access_authorized"] is False
    assert report["ci_gate"]["phase7_authorized"] is False
    assert report["ci_gate"]["production_readiness_approved"] is False
    # The bound artifact hash must match the sealed file.
    assert report["entry_artifact_sha256"] == verify_generation2_phase7_entry(artifact)["artifact_sha256"]


def test_gate_rejects_wrong_phase6_status(tmp_path: Path):
    root = _make_repo_root(tmp_path)
    phase6 = _make_phase6(tmp_path, "c1", status="PHASE6_UNKNOWN_ABSTAIN")
    artifact = _make_artifact(tmp_path, "c1")

    with pytest.raises(Phase7EntryGateError) as excinfo:
        evaluate_generation2_phase7_entry(
            phase6_result_path=phase6,
            entry_artifact_path=artifact,
            repository_root=root,
        )
    assert excinfo.value.code == phase7_entry.PHASE7_ENTRY_PHASE6_INVALID


def test_gate_rejects_missing_phase6_result(tmp_path: Path):
    root = _make_repo_root(tmp_path)
    artifact = _make_artifact(tmp_path, "c1")

    with pytest.raises(Phase7EntryGateError) as excinfo:
        evaluate_generation2_phase7_entry(
            phase6_result_path=tmp_path / "does-not-exist.json",
            entry_artifact_path=artifact,
            repository_root=root,
        )
    assert excinfo.value.code == phase7_entry.PHASE7_ENTRY_PHASE6_INVALID
    assert "PHASE7_EVIDENCE_INVALID" in str(excinfo.value)


def test_gate_rejects_missing_entry_artifact(tmp_path: Path):
    root = _make_repo_root(tmp_path)
    phase6 = _make_phase6(tmp_path, "c1")

    with pytest.raises(Phase7EntryGateError) as excinfo:
        evaluate_generation2_phase7_entry(
            phase6_result_path=phase6,
            entry_artifact_path=tmp_path / "absent-entry.json",
            repository_root=root,
        )
    assert excinfo.value.code == phase7_entry.PHASE7_ENTRY_ARTIFACT_MISSING


def test_gate_rejects_tampered_entry_artifact(tmp_path: Path):
    root = _make_repo_root(tmp_path)
    phase6 = _make_phase6(tmp_path, "c-original")
    artifact = _make_artifact(tmp_path, "c-original")
    # Tamper: flip the candidate after sealing; self-hash no longer verifies.
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["candidate_id"] = "c-attacker"
    _write(artifact, payload)

    with pytest.raises(Phase7EntryGateError) as excinfo:
        evaluate_generation2_phase7_entry(
            phase6_result_path=phase6,
            entry_artifact_path=artifact,
            repository_root=root,
        )
    assert excinfo.value.code == phase7_entry.PHASE7_ENTRY_ARTIFACT_TAMPERED


def test_gate_rejects_entry_artifact_with_wrong_authority(tmp_path: Path):
    root = _make_repo_root(tmp_path)
    phase6 = _make_phase6(tmp_path, "c1")
    # Author an artifact under a different authority (not INDEPENDENT_AUDIT).
    artifact = _make_artifact(tmp_path, "c1", authority="AGENT")

    with pytest.raises(Phase7EntryGateError) as excinfo:
        evaluate_generation2_phase7_entry(
            phase6_result_path=phase6,
            entry_artifact_path=artifact,
            repository_root=root,
        )
    assert excinfo.value.code == phase7_entry.PHASE7_ENTRY_ARTIFACT_TAMPERED


def test_gate_rejects_candidate_mismatch(tmp_path: Path):
    root = _make_repo_root(tmp_path)
    # Phase-6 result names a candidate; the artifact names a different one.
    phase6 = _make_phase6(tmp_path, "c-phase6")
    artifact = _make_artifact(tmp_path, "c-artifact")

    with pytest.raises(Phase7EntryGateError) as excinfo:
        evaluate_generation2_phase7_entry(
            phase6_result_path=phase6,
            entry_artifact_path=artifact,
            repository_root=root,
        )
    assert excinfo.value.code == phase7_entry.PHASE7_ENTRY_CANDIDATE_MISMATCH


def test_gate_rejects_when_ci_gate_is_red(tmp_path: Path):
    # Authority flags flipped true -> CI gate cannot stay green.
    root = _make_repo_root(
        tmp_path,
        flags={"phase7_authorized": True},
    )
    phase6 = _make_phase6(tmp_path, "c1")
    artifact = _make_artifact(tmp_path, "c1")

    with pytest.raises(Phase7EntryGateError) as excinfo:
        evaluate_generation2_phase7_entry(
            phase6_result_path=phase6,
            entry_artifact_path=artifact,
            repository_root=root,
        )
    assert excinfo.value.code == phase7_entry.PHASE7_ENTRY_CI_GATE_RED


def test_seal_refuses_to_overwrite_existing_artifact(tmp_path: Path):
    payload = seal_generation2_phase7_entry(
        candidate_id="c1",
        survivor=SURVIVOR,
        phase6_status=REQUIRED_PHASE6_STATUS,
        phase6_result_sha256=_sha("p"),
        validation_report_sha256=_sha("v"),
        survivor_freeze_sha256=_sha("f"),
        survivor_rehearsal_sha256=_sha("r"),
        root=tmp_path,
    )
    assert payload["artifact_sha256"]

    with pytest.raises(Phase7EntryGateError) as excinfo:
        seal_generation2_phase7_entry(
            candidate_id="c1",
            survivor=SURVIVOR,
            phase6_status=REQUIRED_PHASE6_STATUS,
            phase6_result_sha256=_sha("p"),
            validation_report_sha256=_sha("v"),
            survivor_freeze_sha256=_sha("f"),
            survivor_rehearsal_sha256=_sha("r"),
            root=tmp_path,
        )
    assert excinfo.value.code == phase7_entry.PHASE7_ENTRY_FORBIDDEN


def test_seal_refuses_non_success_phase6_status(tmp_path: Path):
    with pytest.raises(Phase7EntryGateError) as excinfo:
        seal_generation2_phase7_entry(
            candidate_id="c1",
            survivor=SURVIVOR,
            phase6_status="PHASE6_UNKNOWN_ABSTAIN",
            phase6_result_sha256=_sha("p"),
            validation_report_sha256=_sha("v"),
            survivor_freeze_sha256=_sha("f"),
            survivor_rehearsal_sha256=_sha("r"),
            root=tmp_path,
        )
    assert excinfo.value.code == phase7_entry.PHASE7_ENTRY_FORBIDDEN


def test_phase7_entry_is_impossible_in_the_current_repository():
    """Against the real repo (no real Phase-6 result, no Gen-2 entry artifact),
    the gate must fail closed: Phase-7 entry is impossible today."""
    # A genuine Phase-6 result does not exist yet.
    phase6 = ROOT / "data" / "governance" / "generation2-phase6-result.json"
    artifact = ROOT / "data" / "governance" / "generation2-phase7-entry.json"

    with pytest.raises(Phase7EntryGateError):
        evaluate_generation2_phase7_entry(
            phase6_result_path=phase6,
            entry_artifact_path=artifact,
            repository_root=ROOT,
        )


def test_phase7_entry_stays_impossible_without_explicit_artifact(tmp_path: Path):
    """Even a valid real-Phase-6 success result is not enough by itself: the
    explicit Gen-2 entry artifact is also required."""
    root = _make_repo_root(tmp_path)
    phase6 = _make_phase6(tmp_path, "c1")
    # Deliberately do NOT create the entry artifact.
    with pytest.raises(Phase7EntryGateError) as excinfo:
        evaluate_generation2_phase7_entry(
            phase6_result_path=phase6,
            entry_artifact_path=tmp_path / "generation2-phase7-entry.json",
            repository_root=root,
        )
    assert excinfo.value.code == phase7_entry.PHASE7_ENTRY_ARTIFACT_MISSING
