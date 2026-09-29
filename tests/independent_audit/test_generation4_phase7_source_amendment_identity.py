"""Synthetic identity checks for the governed Phase-7 source amendment."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from investment_tracker.independent_audit.post_generation3 import phase7_source_amendment as amendment
from investment_tracker.independent_audit.post_generation3.phase7_data import (
    Generation4Phase7DataError,
    Generation4Phase7EvaluationAuthorization,
    acquire_prospective_phase7_data,
    build_generation4_phase7_data_request,
    verify_generation4_phase7_evaluation_authorization,
)


@pytest.fixture
def synthetic_amendment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    request = json.loads(amendment._REQUEST_PATH.read_bytes())
    contract = json.loads(amendment._FIRST_CONTRACT_PATH.read_bytes())
    request_path = tmp_path / "source-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    amendment_path = tmp_path / "source-amendment.json"
    monkeypatch.setattr(amendment, "_REQUEST_PATH", request_path)
    monkeypatch.setattr(amendment, "_AMENDMENT_PATH", amendment_path)
    monkeypatch.setattr(amendment, "_verify_sources", lambda commit, hashes: None)
    body = {
        "schema_version": "GENERATION4-PHASE7-SOURCE-AMENDMENT-AUTHORIZATION-v1",
        "status": "GENERATION4_PHASE7_SOURCE_AMENDMENT_AUTHORIZED",
        "authority": "INDEPENDENT_AUDIT",
        "authorization_id": "INDEP-AUDIT-GEN4-PHASE7-SOURCE-SYNTHETIC-IDENTITY",
        "approved_at_utc": "2026-09-30T00:00:00Z",
        "audit_request_sha256": sha256(request_path.read_bytes()).hexdigest(),
        "original_evaluation_authorization_id": contract["evaluation_authorization_id"],
        "original_evaluation_authorization_sha256": contract["evaluation_authorization_sha256"],
        "evaluation_contract_sha256": contract["evaluation_contract_sha256"],
        "first_checkpoint_contract_sha256": amendment._FIRST_CONTRACT_SHA256,
        "implementation_commit": request["implementation_commit"],
        "source_sha256": request["source_sha256"],
        "candidate_id": contract["candidate_id"],
        "research_universe": contract["research_universe"],
        "forbidden_holdout_symbols": contract["forbidden_holdout_symbols"],
        "benchmark_symbol": contract["benchmark_symbol"],
        "friction_cases_bps": contract["friction_cases_bps"],
        "primary_friction_bps": contract["primary_friction_bps"],
        "first_scored_session": contract["first_scored_session"],
        "warmup_session_count": contract["warmup_session_count"],
        "dq030_status": "UNRESOLVED",
        "recon009_status": "OPEN",
        "paper_only": True,
        **{field: False for field in amendment._FALSE_FLAGS},
    }
    payload = {
        **body,
        "artifact_sha256": sha256(amendment._canonical_json(body)).hexdigest(),
    }
    amendment_path.write_text(json.dumps(payload), encoding="utf-8")
    return amendment_path


@pytest.mark.parametrize("field,value", [
    ("approved_at_utc", "2026-09-30T00:00:00Z"),
    ("implementation_sha256", "0" * 64),
])
def test_alternate_authorization_with_same_id_and_changed_field_is_rejected(
    synthetic_amendment: Path, tmp_path: Path, field: str, value: str
) -> None:
    original = json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    original[field] = value
    alternate = tmp_path / "alternate-authorization.json"
    alternate.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(Generation4Phase7DataError):
        verify_generation4_phase7_evaluation_authorization(alternate)


def test_canonical_authorization_passes_synthetic_amendment(synthetic_amendment: Path) -> None:
    verified = verify_generation4_phase7_evaluation_authorization(amendment._ORIGINAL_AUTH_PATH)
    assert verified.authorization_id == json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())["authorization_id"]


@pytest.mark.parametrize("field,value", [
    ("approved_at_utc", "2026-10-01T00:00:00Z"),
    ("authorization_id", "INDEP-AUDIT-GEN4-PHASE7-EVAL-SUBSTITUTE"),
])
def test_mutated_mapping_is_rejected(synthetic_amendment: Path, field: str, value: str) -> None:
    payload = json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    payload[field] = value
    with pytest.raises(Generation4Phase7DataError):
        verify_generation4_phase7_evaluation_authorization(payload)


def test_exact_mapping_is_rejected_without_file_identity(synthetic_amendment: Path) -> None:
    payload = json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    with pytest.raises(Generation4Phase7DataError):
        verify_generation4_phase7_evaluation_authorization(payload)


def test_copied_authorization_file_is_rejected(synthetic_amendment: Path, tmp_path: Path) -> None:
    copied = tmp_path / "copied.json"
    copied.write_bytes(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    with pytest.raises(Generation4Phase7DataError):
        verify_generation4_phase7_evaluation_authorization(copied)


def test_canonical_content_with_changed_bytes_is_rejected(
    synthetic_amendment: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = tmp_path / "original.json"
    canonical.write_bytes(amendment._ORIGINAL_AUTH_PATH.read_bytes() + b"\n")
    monkeypatch.setattr(amendment, "_ORIGINAL_AUTH_PATH", canonical)
    with pytest.raises(Generation4Phase7DataError):
        verify_generation4_phase7_evaluation_authorization(canonical)


@pytest.mark.parametrize("contents", [b"{", None])
def test_bad_or_missing_file_is_rejected(
    synthetic_amendment: Path, tmp_path: Path, contents: bytes | None
) -> None:
    bad = tmp_path / "bad.json"
    if contents is not None:
        bad.write_bytes(contents)
    with pytest.raises(Generation4Phase7DataError):
        verify_generation4_phase7_evaluation_authorization(bad)


def test_symlink_is_rejected(synthetic_amendment: Path, tmp_path: Path) -> None:
    link = tmp_path / "authorization-link.json"
    try:
        link.symlink_to(amendment._ORIGINAL_AUTH_PATH)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this runner")
    with pytest.raises(Generation4Phase7DataError):
        verify_generation4_phase7_evaluation_authorization(link)


def test_source_verifier_rejects_forged_parsed_object(synthetic_amendment: Path) -> None:
    payload = json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    payload["approved_at_utc"] = "2026-10-01T00:00:00Z"
    forged = Generation4Phase7EvaluationAuthorization.model_validate(payload)
    with pytest.raises(amendment.SourceAmendmentError):
        amendment.verify_source_amendment(forged)


def test_invalid_authorization_denied_before_provider_factory(
    synthetic_amendment: Path, tmp_path: Path
) -> None:
    original = json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    request = build_generation4_phase7_data_request(
        authorization=Generation4Phase7EvaluationAuthorization.model_validate(original),
        requested_start="2025-11-24",
        requested_end="2026-09-28",
        retrieved_at_utc="2026-09-29T00:00:00Z",
    )
    payload = {**original, "approved_at_utc": "2026-10-01T00:00:00Z"}
    alternate = tmp_path / "alternate.json"
    alternate.write_text(json.dumps(payload), encoding="utf-8")

    def provider_factory(**kwargs: object) -> None:
        pytest.fail("provider factory was called")

    with pytest.raises(Generation4Phase7DataError) as exc:
        acquire_prospective_phase7_data(
            evaluation_authorization=alternate,
            request=request,
            output_dir=tmp_path,
            retrieved_at_utc="2026-09-29T00:00:00Z",
            client_factory=provider_factory,
        )
    assert exc.value.detail == "source_amendment"
