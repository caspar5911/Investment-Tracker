"""Synthetic identity checks for the governed Phase-7 source amendment."""

from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from investment_tracker.independent_audit.post_generation3 import phase7_source_amendment as amendment
from investment_tracker.independent_audit.post_generation3.phase7_data import (
    Generation4Phase7DataError,
    Generation4Phase7EvaluationAuthorization,
    acquire_prospective_phase7_data,
    build_generation4_phase7_data_request,
    load_and_verify_generation4_phase7_evaluation_authorization,
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
    amendment_path.write_bytes(amendment._canonical_json(payload))
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


def test_source_amendment_rejects_appended_whitespace_bytes(synthetic_amendment: Path) -> None:
    original = Generation4Phase7EvaluationAuthorization.model_validate(
        json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    )
    synthetic_amendment.write_bytes(synthetic_amendment.read_bytes() + b" ")
    with pytest.raises(amendment.SourceAmendmentError):
        amendment.verify_source_amendment(original)


@pytest.mark.parametrize("encoding", [
    "append_space", "append_newline", "prepend_space", "pretty_print",
    "reordered_keys", "utf8_bom", "spaced_separators", "crlf", "indent_two",
])
def test_source_amendment_rejects_alternate_json_bytes(
    synthetic_amendment: Path, encoding: str
) -> None:
    original = Generation4Phase7EvaluationAuthorization.model_validate(
        json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    )
    canonical = synthetic_amendment.read_bytes()
    payload = json.loads(canonical)
    alternatives = {
        "append_space": canonical + b" ",
        "append_newline": canonical + b"\n",
        "prepend_space": b" " + canonical,
        "pretty_print": json.dumps(payload, sort_keys=True, indent=4).encode("utf-8"),
        "reordered_keys": json.dumps(dict(reversed(list(payload.items()))),
                                     separators=(",", ":")).encode("utf-8"),
        "utf8_bom": b"\xef\xbb\xbf" + canonical,
        "spaced_separators": json.dumps(payload, sort_keys=True).encode("utf-8"),
        "crlf": json.dumps(payload, sort_keys=True, indent=2).replace("\n", "\r\n").encode("utf-8"),
        "indent_two": json.dumps(payload, indent=2).encode("utf-8"),
    }
    synthetic_amendment.write_bytes(alternatives[encoding])
    with pytest.raises(amendment.SourceAmendmentError):
        amendment.verify_source_amendment(original)


@pytest.mark.parametrize("field,value", [
    ("schema_version", "OTHER"),
    ("status", "DRAFT_TEMPLATE_NOT_AUTHORIZATION"),
    ("authority", "NONE"),
    ("audit_request_sha256", "0" * 64),
    ("original_evaluation_authorization_id", "INDEP-AUDIT-OTHER"),
    ("original_evaluation_authorization_sha256", "0" * 64),
    ("evaluation_contract_sha256", "0" * 64),
    ("implementation_commit", "0" * 40),
    ("source_sha256", {}),
    ("first_checkpoint_contract_sha256", "0" * 64),
    ("candidate_id", "G2-B"),
    ("research_universe", ["SPY"]),
    ("forbidden_holdout_symbols", []),
    ("benchmark_symbol", "QQQ"),
    ("friction_cases_bps", [3]),
    ("primary_friction_bps", 10),
    ("first_scored_session", "2026-09-29"),
    ("warmup_session_count", 209),
    ("dq030_status", "RESOLVED"),
    ("recon009_status", "CLOSED"),
    ("paper_only", False),
    ("live_trading_authorized", True),
    ("production_readiness_approved", True),
    ("candidate_search_authorized", True),
    ("parameter_mutation_authorized", True),
    ("symbol_substitution_authorized", True),
    ("holdout_reuse_authorized", True),
    ("result_dependent_methodology_change_allowed", True),
    ("checkpoint_evaluation_authorized", True),
])
def test_canonical_source_amendment_rejects_semantic_scope_tamper(
    synthetic_amendment: Path, field: str, value: object
) -> None:
    original = Generation4Phase7EvaluationAuthorization.model_validate(
        json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    )
    payload = json.loads(synthetic_amendment.read_bytes())
    payload[field] = value
    body = {key: item for key, item in payload.items() if key != "artifact_sha256"}
    payload["artifact_sha256"] = sha256(amendment._canonical_json(body)).hexdigest()
    synthetic_amendment.write_bytes(amendment._canonical_json(payload))
    with pytest.raises(amendment.SourceAmendmentError):
        amendment.verify_source_amendment(original)


def test_source_amendment_keeps_body_hash_check(synthetic_amendment: Path) -> None:
    original = Generation4Phase7EvaluationAuthorization.model_validate(
        json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    )
    payload = json.loads(synthetic_amendment.read_bytes())
    payload["approved_at_utc"] = "2026-10-01T00:00:00Z"
    synthetic_amendment.write_bytes(amendment._canonical_json(payload))
    with pytest.raises(amendment.SourceAmendmentError):
        amendment.verify_source_amendment(original)


@pytest.mark.parametrize("field,value", [
    ("approved_at_utc", "2026-10-01T00:00:00Z"),
    ("authorization_id", "INDEP-AUDIT-GEN4-PHASE7-SOURCE-SYNTHETIC-REISSUED"),
])
def test_auditor_selected_metadata_uses_canonical_bytes_and_fresh_body_hash(
    synthetic_amendment: Path, field: str, value: str
) -> None:
    original = Generation4Phase7EvaluationAuthorization.model_validate(
        json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())
    )
    payload = json.loads(synthetic_amendment.read_bytes())
    payload[field] = value
    body = {key: item for key, item in payload.items() if key != "artifact_sha256"}
    payload["artifact_sha256"] = sha256(amendment._canonical_json(body)).hexdigest()
    synthetic_amendment.write_bytes(amendment._canonical_json(payload))
    amendment.verify_source_amendment(original)


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


def test_acquisition_uses_only_the_bytes_read_during_authorization(
    synthetic_amendment: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = amendment._ORIGINAL_AUTH_PATH
    original_bytes = canonical.read_bytes()
    original = json.loads(original_bytes)
    request = build_generation4_phase7_data_request(
        authorization=Generation4Phase7EvaluationAuthorization.model_validate(original),
        requested_start="2025-11-24",
        requested_end="2026-09-28",
        retrieved_at_utc="2026-09-29T00:00:00Z",
    )
    changed = json.dumps({**original, "approved_at_utc": "2026-10-01T00:00:00Z"}).encode()
    actual_read = Path.read_bytes
    reads = 0
    provider_calls = 0

    def raced_read(path: Path) -> bytes:
        nonlocal reads
        if path == canonical:
            reads += 1
            if reads > 2:
                return changed
        return actual_read(path)

    def provider_spy(**kwargs: object) -> None:
        nonlocal provider_calls
        provider_calls += 1
        raise RuntimeError("mock provider reached")

    monkeypatch.setattr(Path, "read_bytes", raced_read)
    with pytest.raises(RuntimeError, match="mock provider reached"):
        acquire_prospective_phase7_data(
            evaluation_authorization=canonical,
            request=request,
            output_dir=tmp_path,
            retrieved_at_utc="2026-09-29T00:00:00Z",
            client_factory=provider_spy,
        )
    assert provider_calls == 1
    assert reads == 1, f"authorization reads={reads}; mock provider calls={provider_calls}"


def test_changed_first_authorization_read_stops_before_provider(
    synthetic_amendment: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = amendment._ORIGINAL_AUTH_PATH
    original = json.loads(canonical.read_bytes())
    request = build_generation4_phase7_data_request(
        authorization=Generation4Phase7EvaluationAuthorization.model_validate(original),
        requested_start="2025-11-24",
        requested_end="2026-09-28",
        retrieved_at_utc="2026-09-29T00:00:00Z",
    )
    changed = json.dumps({**original, "approved_at_utc": "2026-10-01T00:00:00Z"}).encode()
    actual_read = Path.read_bytes
    provider_calls = 0

    def changed_first(path: Path) -> bytes:
        return changed if path == canonical else actual_read(path)

    def provider_spy(**kwargs: object) -> None:
        nonlocal provider_calls
        provider_calls += 1
        pytest.fail("provider reached with changed authorization")

    monkeypatch.setattr(Path, "read_bytes", changed_first)
    with pytest.raises(Generation4Phase7DataError):
        acquire_prospective_phase7_data(
            evaluation_authorization=canonical,
            request=request,
            output_dir=tmp_path,
            retrieved_at_utc="2026-09-29T00:00:00Z",
            client_factory=provider_spy,
        )
    assert provider_calls == 0


def test_acquisition_rejects_mapping_without_file_bytes(
    synthetic_amendment: Path, tmp_path: Path
) -> None:
    original = json.loads(amendment._ORIGINAL_AUTH_PATH.read_bytes())

    def provider_spy(**kwargs: object) -> None:
        pytest.fail("provider reached with mapping authorization")

    with pytest.raises(Generation4Phase7DataError) as exc:
        acquire_prospective_phase7_data(
            evaluation_authorization=original,
            request={},
            output_dir=tmp_path,
            retrieved_at_utc="2026-09-29T00:00:00Z",
            client_factory=provider_spy,
        )
    assert exc.value.detail == "authorization_path_required"


def test_copied_verified_result_cannot_bypass_the_loader(
    synthetic_amendment: Path, tmp_path: Path
) -> None:
    verified = load_and_verify_generation4_phase7_evaluation_authorization(
        amendment._ORIGINAL_AUTH_PATH
    )
    copied = replace(verified)

    def provider_spy(**kwargs: object) -> None:
        pytest.fail("provider reached with unissued verified result")

    with pytest.raises(Generation4Phase7DataError) as exc:
        acquire_prospective_phase7_data(
            evaluation_authorization=copied,
            request={},
            output_dir=tmp_path,
            retrieved_at_utc="2026-09-29T00:00:00Z",
            client_factory=provider_spy,
        )
    assert exc.value.detail == "verified_authorization"
