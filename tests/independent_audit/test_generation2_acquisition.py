from __future__ import annotations

import json
from pathlib import Path

import pytest

from investment_tracker.independent_audit.generation2 import acquisition as a

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/generation2/phase6/evaluation-contract.json"
AUTH = ROOT / "data/generation2/phase6/acquisition-authorization.json"
PREACCESS = ROOT / "data/generation2/preaccess/preaccess-status.json"
ATTESTATION = ROOT / "data/generation2/preaccess/virginity-attestation.json"
EVIDENCE = ROOT / "data/generation2/preaccess/virginity-evidence.json"
PROVENANCE = ROOT / "data/generation2/preaccess/provenance"
CLASSIFICATION = ROOT / "data/generation2/phase6/ci-classification.json"
AUTH_COMMIT = "51f077cc5acddd02a231567088f70a3c7bdb7d36"


def _kwargs(tmp_path: Path) -> dict:
    return dict(
        repository_root=ROOT,
        contract_path=CONTRACT,
        authorization_path=AUTH,
        preaccess_status_path=PREACCESS,
        attestation_path=ATTESTATION,
        evidence_path=EVIDENCE,
        provenance_root=PROVENANCE,
        ci_classification_path=CLASSIFICATION,
        authorization_commit_sha=AUTH_COMMIT,
        private_output_dir=tmp_path / "private",
    )


def test_committed_ci_classification_is_explicitly_not_green():
    value = a._verify_ci_classification(CLASSIFICATION, AUTH_COMMIT)
    assert value["full_suite"]["full_suite_green"] is False
    assert value["assessment"]["generic_suite_failure_waived_as_green"] is False
    assert value["assessment"]["generation2_regression_detected"] is False


def test_private_output_inside_repository_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="GEN2_PRIVATE_OUTPUT_MUST_BE_OUTSIDE_REPOSITORY"):
        a.acquire_and_seal(
            **{**_kwargs(tmp_path), "private_output_dir": ROOT / ".runtime" / "forbidden"}
        )


def test_start_marker_exists_before_provider_sdk_load(monkeypatch, tmp_path: Path):
    def stop_after_marker():
        marker = next((tmp_path / "private").glob("*.acquisition-start.json"))
        payload = json.loads(marker.read_text(encoding="utf-8"))
        assert payload["historical_access_started"] is False
        raise RuntimeError("STOP_AFTER_MARKER")

    monkeypatch.setattr(a, "_load_sdk", stop_after_marker)
    with pytest.raises(RuntimeError, match="STOP_AFTER_MARKER"):
        a.acquire_and_seal(**_kwargs(tmp_path))
    marker = next((tmp_path / "private").glob("*.acquisition-start.json"))
    assert json.loads(marker.read_text())["retry_allowed_after_historical_access"] is False


def test_existing_start_marker_prevents_second_attempt_before_provider(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(a, "_load_sdk", lambda: (_ for _ in ()).throw(RuntimeError("FIRST")))
    with pytest.raises(RuntimeError, match="FIRST"):
        a.acquire_and_seal(**_kwargs(tmp_path))

    called = False
    def forbidden():
        nonlocal called
        called = True
        raise AssertionError("provider must not load on second attempt")
    monkeypatch.setattr(a, "_load_sdk", forbidden)
    with pytest.raises(RuntimeError, match="GEN2_ACQUISITION_AUTHORIZATION_ALREADY_CONSUMED"):
        a.acquire_and_seal(**_kwargs(tmp_path))
    assert called is False


def test_tampered_ci_classification_stops_before_provider(monkeypatch, tmp_path: Path):
    value = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    value["assessment"]["generation2_regression_detected"] = True
    bad = tmp_path / "bad-classification.json"
    bad.write_text(json.dumps(value), encoding="utf-8")
    called = False
    def forbidden():
        nonlocal called
        called = True
        raise AssertionError("provider must not load")
    monkeypatch.setattr(a, "_load_sdk", forbidden)
    with pytest.raises(ValueError, match="GEN2_ACQUISITION_CI_CLASSIFICATION_INVALID"):
        a.acquire_and_seal(**{**_kwargs(tmp_path), "ci_classification_path": bad})
    assert called is False


def test_expected_sessions_match_frozen_contract():
    contract = a.verify_contract(CONTRACT)
    warmup, scored = a.expected_sessions(contract)
    assert len(warmup) == 210
    assert scored[0].date().isoformat() >= "2023-01-01"
    assert scored[-1].date().isoformat() <= "2025-12-31"
    assert warmup[-1] < scored[0]
