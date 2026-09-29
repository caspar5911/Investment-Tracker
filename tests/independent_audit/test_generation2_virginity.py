from __future__ import annotations

import json
from pathlib import Path

import pytest

from investment_tracker.independent_audit.generation2 import virginity


class FakeContext:
    def __init__(self, details):
        self.details = details
        self.closed = False

    def get_history_kl_quota(self, get_detail=False):
        assert get_detail is True
        return 0, (len(self.details), 300 - len(self.details), self.details)

    def close(self):
        self.closed = True


class FakeSdk:
    RET_OK = 0

    def __init__(self, context):
        self.context = context

    def OpenQuoteContext(self, host, port):
        assert host == "127.0.0.1"
        assert port == 11111
        return self.context


def _stub_selection(monkeypatch):
    monkeypatch.setattr(
        virginity,
        "_verify_selection",
        lambda path, contract: (
            {
                "selected": [{"symbol": s} for s in virginity.LOCKED_SYMBOLS],
            },
            "a" * 64,
            "b" * 64,
        ),
    )


def test_locked_symbols_are_exact_frozen_selection():
    assert virginity.LOCKED_SYMBOLS == ("BNO", "GBIL", "CWS", "ESG", "VICI")


def test_capture_uses_quota_and_retained_logs_only(monkeypatch, tmp_path: Path):
    _stub_selection(monkeypatch)
    context = FakeContext(
        [
            {"code": "US.SPY", "name": "SPY", "request_time": "2026-09-22 01:00:00"},
            {"code": "US.FQAL", "name": "FQAL", "request_time": "2026-09-22 02:00:00"},
        ]
    )
    monkeypatch.setattr(virginity, "_load_sdk", lambda: (FakeSdk(context), "fake"))

    log = tmp_path / "OpenD.log"
    log.write_text(
        "Qot_RequestHistoryKL protoID=3103\nsecurity=US.SPY\n",
        encoding="utf-8",
    )
    evidence = tmp_path / "evidence.json"
    attestation = tmp_path / "attestation.json"

    virginity.capture_composite_virginity(
        log_paths=(log,),
        evidence_output_path=evidence,
        attestation_output_path=attestation,
    )

    payload = json.loads(attestation.read_text(encoding="utf-8"))
    assert payload["status"] == virginity.ATTESTATION_STATUS
    assert payload["locked_symbols"] == list(virginity.LOCKED_SYMBOLS)
    assert payload["provider_locked_symbol_matches"] == []
    assert payload["retained_log_locked_symbol_history_matches"] == []
    assert payload["independent_source_provenance_gate"] == "OPEN"
    assert payload["historical_acquisition_authorized"] is False
    assert context.closed is True


def test_provider_match_fails_closed(monkeypatch, tmp_path: Path):
    _stub_selection(monkeypatch)
    context = FakeContext(
        [{"code": "US.BNO", "name": "BNO", "request_time": "2026-09-22 03:00:00"}]
    )
    monkeypatch.setattr(virginity, "_load_sdk", lambda: (FakeSdk(context), "fake"))
    log = tmp_path / "OpenD.log"
    log.write_text("ordinary metadata\n", encoding="utf-8")

    evidence = tmp_path / "evidence.json"
    attestation = tmp_path / "attestation.json"
    with pytest.raises(ValueError, match="GEN2_COMPOSITE_VIRGINITY_FAILED"):
        virginity.capture_composite_virginity(
            log_paths=(log,),
            evidence_output_path=evidence,
            attestation_output_path=attestation,
        )
    assert evidence.exists()
    assert not attestation.exists()


def test_retained_log_match_fails_closed(monkeypatch, tmp_path: Path):
    _stub_selection(monkeypatch)
    context = FakeContext([])
    monkeypatch.setattr(virginity, "_load_sdk", lambda: (FakeSdk(context), "fake"))
    log = tmp_path / "OpenD.log"
    log.write_text(
        "Qot_RequestHistoryKL protoID=3103\nsecurity=VICI\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="GEN2_COMPOSITE_VIRGINITY_FAILED"):
        virginity.capture_composite_virginity(
            log_paths=(log,),
            evidence_output_path=tmp_path / "evidence.json",
            attestation_output_path=tmp_path / "attestation.json",
        )


def test_output_collision_fails_before_provider_access(monkeypatch, tmp_path: Path):
    _stub_selection(monkeypatch)
    evidence = tmp_path / "evidence.json"
    evidence.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(
        virginity,
        "_load_sdk",
        lambda: (_ for _ in ()).throw(AssertionError("provider must not open")),
    )
    with pytest.raises(FileExistsError, match="GEN2_COMPOSITE_VIRGINITY_OUTPUT_EXISTS"):
        virginity.capture_composite_virginity(
            log_paths=(tmp_path,),
            evidence_output_path=evidence,
            attestation_output_path=tmp_path / "attestation.json",
        )


def test_current_committed_selection_verifies():
    payload, selection_sha, contract_sha = virginity._verify_selection(
        Path("data/generation2/holdout-selection/selection.json"),
        Path("data/governance/generation2-holdout-selection-contract.json"),
    )
    assert [x["symbol"] for x in payload["selected"]] == list(virginity.LOCKED_SYMBOLS)
    assert len(selection_sha) == 64
    assert len(contract_sha) == 64


def test_verify_attestation_binds_evidence_and_selection(monkeypatch, tmp_path: Path):
    _stub_selection(monkeypatch)
    context = FakeContext([])
    monkeypatch.setattr(virginity, "_load_sdk", lambda: (FakeSdk(context), "fake"))
    log = tmp_path / "OpenD.log"
    log.write_text("ordinary metadata\n", encoding="utf-8")
    evidence = tmp_path / "evidence.json"
    attestation = tmp_path / "attestation.json"
    virginity.capture_composite_virginity(
        log_paths=(log,),
        evidence_output_path=evidence,
        attestation_output_path=attestation,
    )
    payload = virginity.verify_attestation(
        attestation_path=attestation,
        evidence_path=evidence,
        selection_path=tmp_path / "unused-selection.json",
        selection_contract_path=tmp_path / "unused-contract.json",
    )
    assert payload["historical_acquisition_authorized"] is False


def test_tampered_evidence_rejected(monkeypatch, tmp_path: Path):
    _stub_selection(monkeypatch)
    context = FakeContext([])
    monkeypatch.setattr(virginity, "_load_sdk", lambda: (FakeSdk(context), "fake"))
    log = tmp_path / "OpenD.log"
    log.write_text("ordinary metadata\n", encoding="utf-8")
    evidence = tmp_path / "evidence.json"
    attestation = tmp_path / "attestation.json"
    virginity.capture_composite_virginity(
        log_paths=(log,),
        evidence_output_path=evidence,
        attestation_output_path=attestation,
    )
    evidence.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="GEN2_VIRGINITY_ATTESTATION_EVIDENCE_MISMATCH"):
        virginity.verify_attestation(
            attestation_path=attestation,
            evidence_path=evidence,
            selection_path=tmp_path / "unused-selection.json",
            selection_contract_path=tmp_path / "unused-contract.json",
        )
