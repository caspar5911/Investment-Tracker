"""Synthetic checks for the first checkpoint's execution authority boundary."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
import exchange_calendars as xcals
import pandas as pd

from investment_tracker.independent_audit.post_generation3 import (
    phase7_checkpoint_gate as gate,
    phase7_evaluation_cli as cli,
    phase7_first_checkpoint as first,
    phase7_source_amendment as amendment,
)
from investment_tracker.independent_audit.post_generation3.phase7_data import (
    Generation4Phase7DataError,
    Generation4Phase7DataRequest,
    _build_snapshot,
    _snapshot_id,
    _write_snapshot,
    verify_generation4_phase7_evaluation_authorization,
)
from investment_tracker.quant.phase7 import generation4_durability as durability


def test_public_report_denies_direct_python_call_before_touching_bars() -> None:
    class Sensitive:
        @property
        def bars(self):
            pytest.fail("performance-sensitive bars were touched")

    with pytest.raises(gate.CheckpointGateError) as exc:
        durability.prospective_checkpoint_report(Sensitive())
    assert exc.value.code == gate.PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED


def test_original_general_authorization_pauses_without_auditor_source_amendment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(amendment, "_AMENDMENT_PATH", tmp_path / "absent-amendment.json")
    with pytest.raises(Generation4Phase7DataError) as exc:
        verify_generation4_phase7_evaluation_authorization(amendment._ORIGINAL_AUTH_PATH)
    assert exc.value.detail == "source_amendment"


def test_synthetic_auditor_source_amendment_binds_unchanged_methodology(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = first._contract()
    request = tmp_path / "source-request.json"
    path = tmp_path / "source-amendment.json"
    monkeypatch.setattr(amendment, "_REQUEST_PATH", request)
    monkeypatch.setattr(amendment, "_AMENDMENT_PATH", path)
    monkeypatch.setattr(amendment, "_verify_sources", lambda commit, hashes: None)
    body = {
        "schema_version": "GENERATION4-PHASE7-SOURCE-AMENDMENT-AUTHORIZATION-v1",
        "status": "GENERATION4_PHASE7_SOURCE_AMENDMENT_AUTHORIZED",
        "authority": "INDEPENDENT_AUDIT",
        "authorization_id": "INDEP-AUDIT-GEN4-PHASE7-SOURCE-SYNTHETIC-0001",
        "approved_at_utc": "2026-10-01T00:00:00Z",
        "audit_request_sha256": "",
        "original_evaluation_authorization_id": contract["evaluation_authorization_id"],
        "original_evaluation_authorization_sha256": contract["evaluation_authorization_sha256"],
        "evaluation_contract_sha256": contract["evaluation_contract_sha256"],
        "first_checkpoint_contract_sha256": first._CONTRACT_SHA256,
        "implementation_commit": "a" * 40,
        "source_sha256": {relative: sha256((gate._ROOT / relative).read_bytes()).hexdigest()
                          for relative in amendment._SOURCE_FILES},
        "candidate_id": contract["candidate_id"],
        "research_universe": contract["research_universe"],
        "forbidden_holdout_symbols": contract["forbidden_holdout_symbols"],
        "benchmark_symbol": contract["benchmark_symbol"],
        "friction_cases_bps": contract["friction_cases_bps"],
        "primary_friction_bps": contract["primary_friction_bps"],
        "first_scored_session": contract["first_scored_session"],
        "warmup_session_count": contract["warmup_session_count"],
        "dq030_status": "UNRESOLVED", "recon009_status": "OPEN",
        "paper_only": True,
        **{field: False for field in amendment._FALSE_FLAGS},
    }
    request.write_text(json.dumps({
        "schema_version": "GENERATION4-PHASE7-SOURCE-AMENDMENT-INDEPENDENT-AUDIT-REQUEST-v1",
        "status": "READY_FOR_INDEPENDENT_AUDIT", "authority": "NONE",
        **{field: body[field] for field in (
            "original_evaluation_authorization_sha256", "first_checkpoint_contract_sha256",
            "implementation_commit", "source_sha256", "candidate_id",
            "checkpoint_evaluation_authorized",
        )},
    }), encoding="utf-8")
    body["audit_request_sha256"] = sha256(request.read_bytes()).hexdigest()

    def write(value: dict) -> None:
        payload = {**value, "artifact_sha256": sha256(amendment._canonical_json(value)).hexdigest()}
        path.write_text(json.dumps(payload), encoding="utf-8")

    write(body)
    authorization = first._historical_snapshot_authorization()
    amendment.verify_source_amendment(authorization)
    write({**body, "candidate_id": "G2-B"})
    with pytest.raises(amendment.SourceAmendmentError):
        amendment.verify_source_amendment(authorization)


def test_general_authorization_loader_reaches_amendment_gate_for_source_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = []
    monkeypatch.setattr(
        amendment, "verify_source_amendment",
        lambda authorization, **identity: called.append((authorization.authorization_id, identity)),
    )
    authorization = verify_generation4_phase7_evaluation_authorization(
        amendment._ORIGINAL_AUTH_PATH
    )
    assert called == [(authorization.authorization_id, {
        "supplied_authorization_path": amendment._ORIGINAL_AUTH_PATH,
        "supplied_authorization_bytes": amendment._ORIGINAL_AUTH_PATH.read_bytes(),
    })]


def test_cli_denies_without_checkpoint_authorization_before_loading_bars(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli, "_load_bars", lambda *args, **kwargs: pytest.fail("bars were loaded")
    )
    monkeypatch.setattr(
        gate, "checkpoint_execution_permit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            gate.CheckpointGateError(gate.PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED)
        ),
    )
    rc = cli.main([
        "evaluate-phase7-checkpoint", "--evaluation-authorization",
        str(tmp_path / "general.json"), "--snapshot", str(tmp_path / "snapshot"),
    ])
    assert rc == 1
    assert gate.PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED in capsys.readouterr().out


def test_missing_checkpoint_authorization_fails_closed_after_structural_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir()
    snapshot = snapshot_root / ("gen4-phase7-snapshot-" + "a" * 32)
    snapshot.mkdir()
    monkeypatch.setattr(gate, "_SNAPSHOT_ROOT", snapshot_root)
    monkeypatch.setattr(gate, "_AUTHORIZATION_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(gate.first, "first_checkpoint_readiness", lambda: {
        "status": "PHASE7_CHECKPOINT_READY",
        "selected_snapshot_id": snapshot.name,
        "selected_manifest_sha256": "a" * 64,
        "selected_snapshot_scored_sessions": 63,
        "selected_snapshot_chain_sha256": "c" * 64,
    })
    with pytest.raises(gate.CheckpointGateError) as exc:
        gate.checkpoint_execution_permit(snapshot)
    assert exc.value.code == gate.PHASE7_CHECKPOINT_EVALUATION_NOT_AUTHORIZED


def _authorized_synthetic_boundary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    contract = first._contract()
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir()
    snapshot = snapshot_root / ("gen4-phase7-snapshot-" + "a" * 32)
    snapshot.mkdir()
    request = tmp_path / "audit-request.json"
    source = tmp_path / "source-amendment.json"
    source.write_text("{}", encoding="utf-8")
    authorization_path = tmp_path / "checkpoint-authorization.json"
    selected = {
        "status": "PHASE7_CHECKPOINT_READY",
        "selected_snapshot_id": snapshot.name,
        "selected_manifest_sha256": "a" * 64,
        "selected_snapshot_scored_sessions": 63,
        "selected_snapshot_chain_sha256": "c" * 64,
    }
    monkeypatch.setattr(gate, "_SNAPSHOT_ROOT", snapshot_root)
    monkeypatch.setattr(gate, "_AUTHORIZATION_PATH", authorization_path)
    monkeypatch.setattr(gate, "_AUDIT_REQUEST_PATH", request)
    monkeypatch.setattr(amendment, "_AMENDMENT_PATH", source)
    monkeypatch.setattr(amendment, "verify_source_amendment", lambda _: None)
    monkeypatch.setattr(first, "first_checkpoint_readiness", lambda: selected)
    monkeypatch.setattr(gate, "_verify_current_sources", lambda commit, hashes: None)
    authority = {
        "schema_version": "GENERATION4-PHASE7-FIRST-CHECKPOINT-AUTHORIZATION-v1",
        "status": gate.PHASE7_CHECKPOINT_AUTHORIZED,
        "authority": "INDEPENDENT_AUDIT",
        "authorization_id": "INDEP-AUDIT-GEN4-PHASE7-CP63-SYNTHETIC-0001",
        "approved_at_utc": "2026-12-25T00:00:00Z",
        "audit_request_sha256": "",
        "checkpoint_contract_sha256": first._CONTRACT_SHA256,
        "evaluation_contract_sha256": contract["evaluation_contract_sha256"],
        "evaluation_authorization_sha256": contract["evaluation_authorization_sha256"],
        "evaluation_authorization_id": contract["evaluation_authorization_id"],
        "source_amendment_authorization_sha256": sha256(source.read_bytes()).hexdigest(),
        "implementation_commit": "a" * 40,
        "source_sha256": {relative: sha256((gate._ROOT / relative).read_bytes()).hexdigest()
                          for relative in gate._SOURCE_FILES},
        "snapshot_id": snapshot.name,
        "snapshot_manifest_sha256": selected["selected_manifest_sha256"],
        "snapshot_chain_sha256": selected["selected_snapshot_chain_sha256"],
        "checkpoint_scored_sessions": 63,
        "candidate_id": contract["candidate_id"],
        "research_universe": contract["research_universe"],
        "forbidden_holdout_symbols": contract["forbidden_holdout_symbols"],
        "benchmark_symbol": contract["benchmark_symbol"],
        "friction_cases_bps": contract["friction_cases_bps"],
        "primary_friction_bps": contract["primary_friction_bps"],
        "first_scored_session": contract["first_scored_session"],
        "last_scored_session": contract["last_scored_session"],
        "warmup_start": contract["warmup_start"],
        "warmup_session_count": 210,
        "warmup_excluded_from_scored_pnl": True,
        "signal_price_convention": "QFQ",
        "execution_price_convention": "UNADJUSTED",
        "corporate_actions_required": True,
        "dq030_status": "UNRESOLVED",
        "recon009_status": "OPEN",
        "paper_only": True,
        **{field: False for field in gate._FALSE_FLAGS},
    }
    request.write_text(json.dumps({
        "schema_version": "GENERATION4-PHASE7-FIRST-CHECKPOINT-INDEPENDENT-AUDIT-REQUEST-v1",
        "status": "READY_FOR_INDEPENDENT_AUDIT", "authority": "NONE",
        **{field: authority[field] for field in (
            "checkpoint_contract_sha256", "evaluation_authorization_sha256",
            "source_amendment_authorization_sha256", "implementation_commit",
            "source_sha256", "snapshot_id", "snapshot_manifest_sha256",
            "snapshot_chain_sha256", "checkpoint_scored_sessions", "candidate_id",
        )},
    }), encoding="utf-8")
    authority["audit_request_sha256"] = sha256(request.read_bytes()).hexdigest()

    def write(payload: dict) -> None:
        body = dict(payload)
        body["artifact_sha256"] = sha256(gate._canonical_json(body)).hexdigest()
        authorization_path.write_text(json.dumps(body), encoding="utf-8")

    write(authority)
    return snapshot, selected, authority, write


def test_synthetic_checkpoint_authorization_is_distinct_from_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot, selected, _, _ = _authorized_synthetic_boundary(monkeypatch, tmp_path)
    permit = gate.checkpoint_execution_permit(snapshot)
    gate.require_checkpoint_permit(
        permit, SimpleNamespace(evidence_bindings={"snapshot_manifest_sha256": selected["selected_manifest_sha256"]})
    )
    with pytest.raises(gate.CheckpointGateError):
        gate.require_checkpoint_permit(object(), SimpleNamespace(evidence_bindings={}))


def test_checkpoint_placeholder_request_cannot_authorize_evaluation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot, _, authority, write = _authorized_synthetic_boundary(monkeypatch, tmp_path)
    request = json.loads(gate._AUDIT_REQUEST_PATH.read_bytes())
    request["status"] = "WAITING_EXACT_63_EVIDENCE"
    gate._AUDIT_REQUEST_PATH.write_text(json.dumps(request), encoding="utf-8")
    write({**authority, "audit_request_sha256": sha256(gate._AUDIT_REQUEST_PATH.read_bytes()).hexdigest()})
    with pytest.raises(gate.CheckpointGateError) as exc:
        gate.checkpoint_execution_permit(snapshot)
    assert exc.value.code == gate.PHASE7_UNKNOWN_ABSTAIN


@pytest.mark.parametrize(("field", "invalid"), [
    ("snapshot_manifest_sha256", "b" * 64),
    ("snapshot_chain_sha256", "d" * 64),
    ("checkpoint_scored_sessions", 62),
    ("candidate_id", "G2-B"),
    ("research_universe", ["IEF", "GLD", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP"]),
    ("benchmark_symbol", "QQQ"),
    ("friction_cases_bps", [0, 3, 10, 25]),
    ("primary_friction_bps", 10),
    ("first_scored_session", "2026-09-29"),
    ("warmup_session_count", 209),
    ("dq030_status", "RESOLVED"),
    ("recon009_status", "CLOSED"),
    ("live_trading_authorized", True),
])
def test_synthetic_authorization_binding_drift_denied(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, invalid: object
) -> None:
    snapshot, _, authority, write = _authorized_synthetic_boundary(monkeypatch, tmp_path)
    write({**authority, field: invalid})
    with pytest.raises(gate.CheckpointGateError) as exc:
        gate.checkpoint_execution_permit(snapshot)
    assert exc.value.code == gate.PHASE7_UNKNOWN_ABSTAIN


def test_authorization_byte_drift_denied_before_performance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot, selected, _, _ = _authorized_synthetic_boundary(monkeypatch, tmp_path)
    permit = gate.checkpoint_execution_permit(snapshot)
    gate._AUTHORIZATION_PATH.write_bytes(gate._AUTHORIZATION_PATH.read_bytes() + b" ")
    with pytest.raises(gate.CheckpointGateError):
        gate.require_checkpoint_permit(
            permit, SimpleNamespace(evidence_bindings={"snapshot_manifest_sha256": selected["selected_manifest_sha256"]})
        )


def test_result_is_content_bound_and_second_write_is_denied(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot, selected, authority, _ = _authorized_synthetic_boundary(monkeypatch, tmp_path)
    monkeypatch.setattr(gate, "_RESULT_PATH", tmp_path / "result" / "checkpoint-result.json")
    permit = gate.checkpoint_execution_permit(snapshot)
    unknown = {"status": "UNKNOWN", "value": None, "reason": "DQ-030_UNRESOLVED"}
    available = {"status": "AVAILABLE", "value": 0.0, "reason": "OK"}
    report = {
        "scored_session_count": 63, "checkpoint_cutoff": 63,
        "checkpoint_label": "EARLY_DIAGNOSTIC",
        "status": "PHASE7_PROSPECTIVE_EVIDENCE_PENDING",
        "candidate_id": authority["candidate_id"], "paper_only": True,
        "production_authority": False, "live_trading_authority": False,
        "production_pass": False,
        "signal_price_convention": "QFQ", "execution_price_convention": "UNADJUSTED",
        "no_tuning_performed": True, "no_final_holdout_reuse": True,
        "candidate_changed": False, "methodology_changed": False,
        "exposure_invariant_passes": True,
        "evidence_bindings": {"snapshot_manifest_sha256": selected["selected_manifest_sha256"]},
        "max_drawdown": unknown, "calmar": unknown, "recovery": unknown,
        "rolling_12m_return": {"status": "UNKNOWN", "value": None,
                               "reason": "INCOMPLETE_WINDOW"},
        "friction_cases": {str(bps): {"friction_bps": bps, "scored_session_count": 63,
                                      "total_return": available}
                           for bps in (0, 3, 10, 25, 50)},
        "benchmark_total_return": available,
        "excess_return_vs_spy": available, "excess_return_vs_cash": available,
    }
    output = gate.write_checkpoint_result(permit, report)
    result = json.loads(gate._RESULT_PATH.read_bytes())
    digest = result.pop("result_sha256")
    assert digest == output["result_sha256"] == sha256(gate._canonical_json(result)).hexdigest()
    assert result["snapshot_manifest_sha256"] == selected["selected_manifest_sha256"]
    assert result["checkpoint_authorization_sha256"] == permit.authorization_sha256
    with pytest.raises(gate.CheckpointGateError):
        gate.write_checkpoint_result(permit, report)


def test_synthetic_exact_63_cli_runs_only_after_checkpoint_authorization(
    bound_evidence, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _, selected, authority, write = _authorized_synthetic_boundary(monkeypatch, tmp_path)
    calendar = xcals.get_calendar("XNYS")
    sessions = calendar.sessions_in_range("2025-11-24", "2026-12-24")
    assert len(sessions) == 273
    symbols = tuple(authority["research_universe"])
    frames = {}
    for offset, symbol in enumerate(symbols):
        close = [100.0 + offset + i / 100.0 for i in range(len(sessions))]
        frames[symbol] = pd.DataFrame({
            "open": close, "high": [value + 1.0 for value in close],
            "low": [value - 1.0 for value in close], "close": close,
            "volume": [1000] * len(sessions),
        }, index=sessions)
    general_path = tmp_path / "general-authorization.json"
    general_path.write_text(json.dumps(bound_evidence.authorization), encoding="utf-8")
    monkeypatch.setattr(gate.collector, "_AUTHORIZATION_PATH", general_path)
    general = verify_generation4_phase7_evaluation_authorization(general_path)
    request = Generation4Phase7DataRequest.model_validate({
        "schema_version": "GENERATION4-PHASE7-DATA-REQUEST-v1",
        "symbols": list(symbols), "requested_start": "2025-11-24",
        "requested_end": "2026-12-24", "scored_start": "2026-09-28",
        "warmup_session_count": 210, "scored_session_count": 63,
    })
    retrieved = (calendar.session_close("2026-12-24") + pd.Timedelta(hours=1)).isoformat()
    snapshot_id = _snapshot_id(general, request, retrieved)
    manifest, payloads = _build_snapshot(
        general, request, frames, frames,
        {symbol: pd.DataFrame(columns=["ex_div_date"]) for symbol in symbols},
        {symbol: {"dividend_list": []} for symbol in symbols},
        {symbol: {"split_list": []} for symbol in symbols},
        retrieved, snapshot_id=snapshot_id,
        authorization_sha256=sha256(general_path.read_bytes()).hexdigest(),
    )
    snapshot = gate._SNAPSHOT_ROOT / snapshot_id
    _write_snapshot(snapshot, manifest, payloads)
    selected["selected_snapshot_id"] = snapshot_id
    selected["selected_manifest_sha256"] = manifest["manifest_sha256"]
    authority["snapshot_id"] = snapshot_id
    authority["snapshot_manifest_sha256"] = manifest["manifest_sha256"]
    audit_request = json.loads(gate._AUDIT_REQUEST_PATH.read_bytes())
    audit_request["snapshot_id"] = snapshot_id
    audit_request["snapshot_manifest_sha256"] = manifest["manifest_sha256"]
    gate._AUDIT_REQUEST_PATH.write_text(json.dumps(audit_request), encoding="utf-8")
    authority["audit_request_sha256"] = sha256(gate._AUDIT_REQUEST_PATH.read_bytes()).hexdigest()
    write(authority)
    monkeypatch.setattr(gate, "_RESULT_PATH", tmp_path / "result" / "checkpoint-result.json")

    rc = cli.main([
        "evaluate-phase7-checkpoint", "--evaluation-authorization", str(general_path),
        "--snapshot", str(snapshot),
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0, payload
    assert payload["status"] == "PHASE7_CHECKPOINT_EVALUATED"
    assert gate._RESULT_PATH.is_file()
