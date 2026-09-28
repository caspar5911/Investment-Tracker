"""The authorization binds frozen evidence before either data gate opens."""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from investment_tracker.independent_audit.post_generation3 import phase7_evaluation_cli
from investment_tracker.independent_audit.post_generation3.phase7_data import (
    GEN4_PHASE7_DATA_AUTHORIZATION_INVALID,
    Generation4Phase7DataError,
    acquire_prospective_phase7_data,
    verify_generation4_phase7_evaluation_authorization,
)


def test_complete_synthetic_evidence_is_accepted(bound_evidence):
    authorization = verify_generation4_phase7_evaluation_authorization(
        bound_evidence.authorization
    )
    assert authorization.audit_request_sha256 == bound_evidence.authorization["audit_request_sha256"]


def _request():
    return {
        "schema_version": "GENERATION4-PHASE7-DATA-REQUEST-v1",
        "symbols": ["GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP"],
        "requested_start": "2026-03-02",
        "requested_end": "2026-09-30",
        "scored_start": "2026-09-28",
        "warmup_session_count": 120,
        "scored_session_count": 25,
    }


def _reject_before_provider(bound_evidence, tmp_path, auth):
    created = []

    def factory(**kwargs):
        created.append(kwargs)
        raise AssertionError("provider created before authorization")

    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=auth,
            request=_request(),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-09-28T00:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == GEN4_PHASE7_DATA_AUTHORIZATION_INVALID
    assert created == []


_DRIFT_FIELDS = {
    "audit_request_sha256": "0" * 64,
    "frozen_evaluation_implementation_commit": "0" * 40,
    "evaluation_module_sha256": "0" * 64,
    "evaluation_cli_sha256": "0" * 64,
    "durability_module_sha256": "0" * 64,
    "data_boundary_module_sha256": "0" * 64,
    "evaluation_contract_sha256": "0" * 64,
    "start_artifact_sha256": "0" * 64,
    "start_artifact_self_hash": "0" * 64,
    "start_contract_sha256": "0" * 64,
    "entry_authorization_id": "WRONG-ENTRY-ID",
    "entry_authorization_sha256": "0" * 64,
    "candidate_id": "WRONG-CANDIDATE",
    "binding_sha256": "0" * 64,
    "implementation_sha256": "0" * 64,
    "split_normalizer_sha256": "0" * 64,
    "dividend_reconciliation_sha256": "0" * 64,
    "successor_evaluator_sha256": "0" * 64,
    "research_universe": ["IEF", "GLD", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP"],
    "forbidden_holdout_symbols": ["FALN", "QQQM", "IIPR", "PSTL", "EFAS"],
    "benchmark_symbol": "QQQ",
    "initial_cash": 200000.0,
    "friction_cases_bps": [0, 3, 10, 25],
    "primary_friction_bps": 10,
    "prospective_first_scored_session": "2026-09-29",
    "warmup_session_limit": 209,
    "checkpoint_sessions": [63, 125, 252],
    "historical_lane_classification": "NEW_OOS",
    "dq030_status": "RESOLVED",
    "phase7_started": False,
    "phase7_performance_evaluation_authorized": False,
    "production_readiness_approved": True,
    "live_trading_authorized": True,
    "holdout_reuse_authorized": True,
    "candidate_search_authorized": True,
    "parameter_mutation_authorized": True,
    "symbol_substitution_authorized": True,
    "adaptive_walk_forward_authorized": True,
    "annual_reoptimization_authorized": True,
    "result_dependent_methodology_change_allowed": True,
    "result_dependent_parameter_change_allowed": True,
    "recon009_status": "CLOSED",
    "paper_only": False,
}


@pytest.mark.parametrize("field", list(_DRIFT_FIELDS))
def test_authorization_identity_drift_fails_before_provider(bound_evidence, tmp_path, field):
    _reject_before_provider(
        bound_evidence, tmp_path, bound_evidence.auth(**{field: _DRIFT_FIELDS[field]})
    )


@pytest.mark.parametrize(
    "field",
    [
        "audit_request", "evaluation_contract", "start_artifact",
        "start_contract", "entry_authorization",
        "evaluation_module_sha256", "evaluation_cli_sha256",
        "durability_module_sha256", "data_boundary_module_sha256",
    ],
)
def test_evidence_byte_drift_fails_before_provider(bound_evidence, tmp_path, field):
    with bound_evidence.paths[field].open("ab") as handle:
        handle.write(b"\n")
    _reject_before_provider(bound_evidence, tmp_path, bound_evidence.authorization)


def _rebind_after_start_change(bound_evidence):
    """Rehash outer files, leaving only the embedded self-hash invalid."""
    paths = bound_evidence.paths
    contract = json.loads(paths["evaluation_contract"].read_text(encoding="utf-8"))
    contract["start_artifact_sha256"] = sha256(paths["start_artifact"].read_bytes()).hexdigest()
    paths["evaluation_contract"].write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    request = json.loads(paths["audit_request"].read_text(encoding="utf-8"))
    request["start_artifact_sha256"] = contract["start_artifact_sha256"]
    request["evaluation_contract_sha256"] = sha256(paths["evaluation_contract"].read_bytes()).hexdigest()
    paths["audit_request"].write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    return bound_evidence.auth(
        start_artifact_sha256=request["start_artifact_sha256"],
        evaluation_contract_sha256=request["evaluation_contract_sha256"],
        audit_request_sha256=sha256(paths["audit_request"].read_bytes()).hexdigest(),
    )


def _rebind_contract_and_request(bound_evidence, contract, request, **auth_overrides):
    paths = bound_evidence.paths
    paths["evaluation_contract"].write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    request["evaluation_contract_sha256"] = sha256(paths["evaluation_contract"].read_bytes()).hexdigest()
    paths["audit_request"].write_text(
        json.dumps(request, indent=2) + "\n", encoding="utf-8"
    )
    return bound_evidence.auth(
        evaluation_contract_sha256=request["evaluation_contract_sha256"],
        audit_request_sha256=sha256(paths["audit_request"].read_bytes()).hexdigest(),
        **auth_overrides,
    )


def test_rebound_wrong_prospective_session_is_rejected(bound_evidence, tmp_path):
    paths = bound_evidence.paths
    contract = json.loads(paths["evaluation_contract"].read_text(encoding="utf-8"))
    request = json.loads(paths["audit_request"].read_text(encoding="utf-8"))
    contract["prospective_first_scored_session"] = "2026-09-29"
    request["prospective_first_scored_session"] = "2026-09-29"
    auth = _rebind_contract_and_request(
        bound_evidence, contract, request,
        prospective_first_scored_session="2026-09-29",
    )
    _reject_before_provider(bound_evidence, tmp_path, auth)


def test_rehashed_request_cannot_omit_required_source_identity(bound_evidence, tmp_path):
    paths = bound_evidence.paths
    request = json.loads(paths["audit_request"].read_text(encoding="utf-8"))
    del request["durability_module_sha256"]
    paths["audit_request"].write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    auth = bound_evidence.auth(
        audit_request_sha256=sha256(paths["audit_request"].read_bytes()).hexdigest()
    )
    _reject_before_provider(bound_evidence, tmp_path, auth)


@pytest.mark.parametrize(
    "field,contract_field",
    [
        ("evaluation_module_sha256", "phase7_evaluation_source_sha256"),
        ("evaluation_cli_sha256", "phase7_evaluation_cli_source_sha256"),
        ("durability_module_sha256", None),
        ("data_boundary_module_sha256", None),
    ],
)
def test_rebound_source_still_must_match_frozen_git_tree(
    bound_evidence, tmp_path, field, contract_field
):
    paths = bound_evidence.paths
    with paths[field].open("ab") as handle:
        handle.write(b"changed after freeze\n")
    digest = sha256(paths[field].read_bytes()).hexdigest()
    contract = json.loads(paths["evaluation_contract"].read_text(encoding="utf-8"))
    request = json.loads(paths["audit_request"].read_text(encoding="utf-8"))
    if contract_field is not None:
        contract[contract_field] = digest
    request[field] = digest
    auth = _rebind_contract_and_request(
        bound_evidence, contract, request, **{field: digest}
    )
    _reject_before_provider(bound_evidence, tmp_path, auth)


def test_start_artifact_self_hash_mismatch_rejected_even_with_updated_outer_hashes(bound_evidence, tmp_path):
    path = bound_evidence.paths["start_artifact"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["artifact_sha256"] = "0" * 64
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    auth = _rebind_after_start_change(bound_evidence)
    _reject_before_provider(bound_evidence, tmp_path, auth)


def test_invalid_authorization_prevents_snapshot_manifest_read(bound_evidence, tmp_path, monkeypatch, capsys):
    authorization_path = tmp_path / "authorization.json"
    authorization_path.write_text(
        json.dumps(bound_evidence.auth(audit_request_sha256="0" * 64)), encoding="utf-8"
    )
    read_paths = []

    def fail_on_snapshot_read(path, **kwargs):
        read_paths.append(Path(path))
        raise AssertionError("snapshot read before authorization")

    monkeypatch.setattr(phase7_evaluation_cli, "_load_json", fail_on_snapshot_read)
    rc = phase7_evaluation_cli.main([
        "evaluate-phase7-checkpoint", "--evaluation-authorization",
        str(authorization_path), "--snapshot", str(tmp_path / "snapshot"),
    ])
    assert rc == 1
    assert read_paths == []
    assert json.loads(capsys.readouterr().out)["status"] == "FORBIDDEN"


@pytest.mark.parametrize("field", list(_DRIFT_FIELDS))
def test_each_authorization_drift_prevents_checkpoint_snapshot_read(
    bound_evidence, tmp_path, monkeypatch, capsys, field
):
    authorization_path = tmp_path / "authorization.json"
    authorization_path.write_text(
        json.dumps(bound_evidence.auth(**{field: _DRIFT_FIELDS[field]})),
        encoding="utf-8",
    )
    reads = []

    def fail_on_snapshot_read(path, **kwargs):
        reads.append(Path(path))
        raise AssertionError("snapshot read before authorization")

    monkeypatch.setattr(phase7_evaluation_cli, "_load_json", fail_on_snapshot_read)
    rc = phase7_evaluation_cli.main([
        "evaluate-phase7-checkpoint", "--evaluation-authorization",
        str(authorization_path), "--snapshot", str(tmp_path / "snapshot"),
    ])
    assert rc == 1
    assert reads == []
    assert json.loads(capsys.readouterr().out)["status"] == "FORBIDDEN"


@pytest.mark.parametrize(
    "field",
    [
        "audit_request", "evaluation_contract", "start_artifact",
        "start_contract", "entry_authorization",
        "evaluation_module_sha256", "evaluation_cli_sha256",
        "durability_module_sha256", "data_boundary_module_sha256",
    ],
)
def test_each_evidence_byte_drift_prevents_checkpoint_snapshot_read(
    bound_evidence, tmp_path, monkeypatch, capsys, field
):
    with bound_evidence.paths[field].open("ab") as handle:
        handle.write(b"\n")
    authorization_path = tmp_path / "authorization.json"
    authorization_path.write_text(json.dumps(bound_evidence.authorization), encoding="utf-8")
    reads = []

    def fail_on_snapshot_read(path, **kwargs):
        reads.append(Path(path))
        raise AssertionError("snapshot read before authorization")

    monkeypatch.setattr(phase7_evaluation_cli, "_load_json", fail_on_snapshot_read)
    rc = phase7_evaluation_cli.main([
        "evaluate-phase7-checkpoint", "--evaluation-authorization",
        str(authorization_path), "--snapshot", str(tmp_path / "snapshot"),
    ])
    assert rc == 1
    assert reads == []
    assert json.loads(capsys.readouterr().out)["status"] == "FORBIDDEN"
