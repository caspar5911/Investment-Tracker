from __future__ import annotations

import json
from pathlib import Path

import pytest

from investment_tracker.independent_audit.phase6 import virginity


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


def test_composite_capture_uses_quota_api_and_retained_logs_only(monkeypatch, tmp_path: Path):
    context = FakeContext(
        [
            {"code": "US.SPY", "name": "SPY", "request_time": "2026-09-21 13:59:25"},
            {"code": "US.HACK", "name": "HACK", "request_time": "2026-09-21 15:31:28"},
        ]
    )
    monkeypatch.setattr(virginity, "_load_sdk", lambda: (FakeSdk(context), "fake-moomoo"))

    log = tmp_path / "OpenD.log"
    log.write_text(
        "ordinary quote metadata\n"
        "Qot_RequestHistoryKL protoID=3103\n"
        "security=US.SPY\n",
        encoding="utf-8",
    )
    evidence = tmp_path / "evidence.json"
    attestation = tmp_path / "attestation.json"

    virginity.capture_composite_virginity(
        log_paths=(log,),
        evidence_output_path=evidence,
        attestation_output_path=attestation,
    )

    value = json.loads(attestation.read_text(encoding="utf-8"))
    assert value["status"] == "COMPOSITE_EVIDENCE_NO_PRIOR_LOCKED_SYMBOL_ACCESS_FOUND"
    assert value["locked_symbols"] == ["FQAL", "FDMO", "CSB", "FTXO", "VNLA"]
    assert value["provider_quota_protocol_id"] == 3104
    assert value["provider_quota_window_days"] == 7
    assert value["complete_query_history"] is False
    assert value["provider_locked_symbol_matches"] == []
    assert value["retained_log_locked_symbol_history_matches"] == []
    assert context.closed is True
    assert evidence.is_file()


def test_provider_match_fails_closed_and_does_not_issue_attestation(monkeypatch, tmp_path: Path):
    context = FakeContext(
        [{"code": "US.FQAL", "name": "FQAL", "request_time": "2026-09-22 01:00:00"}]
    )
    monkeypatch.setattr(virginity, "_load_sdk", lambda: (FakeSdk(context), "fake-moomoo"))
    log = tmp_path / "OpenD.log"
    log.write_text("ordinary metadata\n", encoding="utf-8")
    evidence = tmp_path / "evidence.json"
    attestation = tmp_path / "attestation.json"

    with pytest.raises(ValueError, match="PHASE6_COMPOSITE_VIRGINITY_FAILED"):
        virginity.capture_composite_virginity(
            log_paths=(log,),
            evidence_output_path=evidence,
            attestation_output_path=attestation,
        )
    assert evidence.is_file()
    assert not attestation.exists()


def test_retained_history_log_match_fails_closed(monkeypatch, tmp_path: Path):
    context = FakeContext([])
    monkeypatch.setattr(virginity, "_load_sdk", lambda: (FakeSdk(context), "fake-moomoo"))
    log = tmp_path / "OpenD.log"
    log.write_text(
        "Qot_RequestHistoryKL protoID=3103\n"
        "security=US.VNLA\n",
        encoding="utf-8",
    )
    evidence = tmp_path / "evidence.json"
    attestation = tmp_path / "attestation.json"

    with pytest.raises(ValueError, match="PHASE6_COMPOSITE_VIRGINITY_FAILED"):
        virginity.capture_composite_virginity(
            log_paths=(log,),
            evidence_output_path=evidence,
            attestation_output_path=attestation,
        )
    assert evidence.is_file()
    assert not attestation.exists()
