"""Generation-4 Phase-7 real snapshot-integrity boundary tests.

These tests cover the provider-facing semantics that must hold before the first
real prospective snapshot is allowed:
- session counts are derived from the exact XNYS request window, never a frozen
  252-session placeholder;
- an in-progress XNYS daily session is rejected before provider creation;
- raw Moomoo-style time_key frames are normalized to canonical UTC session
  indexes before persistence;
- every research-universe frame must contain the exact same expected XNYS
  sessions or the snapshot is rejected without writing evidence.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import exchange_calendars as xcals
import pandas as pd
import pytest

from investment_tracker.independent_audit.post_generation3 import phase7_evaluation_cli
from investment_tracker.independent_audit.post_generation3.phase7_data import (
    Generation4Phase7DataError,
    acquire_prospective_phase7_data,
)

UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
START = "2026-09-23"
SCORED = "2026-09-28"
END = "2026-09-30"
AFTER_CLOSE = "2026-10-01T00:00:00Z"


def _sessions() -> pd.DatetimeIndex:
    cal = xcals.get_calendar("XNYS")
    sessions = cal.sessions_in_range(START, END)
    assert [str(value.date()) for value in sessions] == [
        "2026-09-23",
        "2026-09-24",
        "2026-09-25",
        "2026-09-28",
        "2026-09-29",
        "2026-09-30",
    ]
    return sessions


def _request(*, warmup: int = 3, scored: int = 3) -> dict[str, object]:
    return {
        "schema_version": "GENERATION4-PHASE7-DATA-REQUEST-v1",
        "symbols": list(UNIVERSE),
        "requested_start": START,
        "requested_end": END,
        "scored_start": SCORED,
        "warmup_session_count": warmup,
        "scored_session_count": scored,
    }


def _raw_frames(*, missing_last_for: str | None = None) -> dict[str, pd.DataFrame]:
    sessions = _sessions()
    frames: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(UNIVERSE):
        used = sessions[:-1] if symbol == missing_last_for else sessions
        prices = [100.0 + offset + i for i in range(len(used))]
        frames[symbol] = pd.DataFrame(
            {
                "code": [f"US.{symbol}"] * len(used),
                "time_key": [f"{value.date()} 00:00:00" for value in used],
                "open": prices,
                "high": [value + 1.0 for value in prices],
                "low": [value - 1.0 for value in prices],
                "close": [value + 0.5 for value in prices],
                "volume": [1000 + i for i in range(len(used))],
            }
        )
    return frames


def _factory(frames: dict[str, pd.DataFrame]):
    created = {"count": 0}

    class Client:
        def fetch_daily_bars(self, symbol, start, end):
            return frames[symbol]

        def close(self):
            pass

    def make(*, host, port):
        created["count"] += 1
        return Client()

    return make, created


def test_calendar_count_mismatch_rejected_before_provider(bound_evidence, tmp_path):
    factory, created = _factory(_raw_frames())
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=bound_evidence.authorization,
            request=_request(scored=252),
            output_dir=tmp_path / "out",
            retrieved_at_utc=AFTER_CLOSE,
            client_factory=factory,
        )
    assert excinfo.value.code == "GEN4_PHASE7_DATA_SESSION_COUNT_MISMATCH"
    assert created["count"] == 0


def test_in_progress_requested_end_rejected_before_provider(bound_evidence, tmp_path):
    factory, created = _factory(_raw_frames())
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=bound_evidence.authorization,
            request=_request(),
            output_dir=tmp_path / "out",
            retrieved_at_utc="2026-09-30T15:00:00Z",
            client_factory=factory,
        )
    assert excinfo.value.code == "GEN4_PHASE7_DATA_SESSION_INCOMPLETE"
    assert created["count"] == 0


def test_raw_time_key_is_canonicalized_before_snapshot_write(bound_evidence, tmp_path):
    factory, _ = _factory(_raw_frames())
    manifest = acquire_prospective_phase7_data(
        evaluation_authorization=bound_evidence.authorization,
        request=_request(),
        output_dir=tmp_path / "out",
        retrieved_at_utc=AFTER_CLOSE,
        client_factory=factory,
    )
    assert manifest["warmup_session_count"] == 3
    assert manifest["scored_session_count"] == 3
    snapshot = tmp_path / "out" / "snapshots" / manifest["snapshot_id"]
    saved = pd.read_csv(snapshot / "bars" / "SPY.csv", index_col=0)
    assert list(saved.index) == [str(value.date()) for value in _sessions()]
    assert "time_key" not in saved.columns
    assert "code" not in saved.columns


def test_missing_provider_session_rejects_snapshot(bound_evidence, tmp_path):
    factory, created = _factory(_raw_frames(missing_last_for="GLD"))
    with pytest.raises(Generation4Phase7DataError) as excinfo:
        acquire_prospective_phase7_data(
            evaluation_authorization=bound_evidence.authorization,
            request=_request(),
            output_dir=tmp_path / "out",
            retrieved_at_utc=AFTER_CLOSE,
            client_factory=factory,
        )
    assert excinfo.value.code == "GEN4_PHASE7_DATA_SESSION_ALIGNMENT_INVALID"
    assert created["count"] == 1
    assert not (tmp_path / "out" / "snapshots").exists()


def test_cli_derives_actual_session_counts_instead_of_checkpoint_max(monkeypatch, tmp_path, capsys):
    authorization = SimpleNamespace(
        research_universe=UNIVERSE,
        prospective_first_scored_session=SCORED,
        warmup_session_limit=210,
        checkpoint_sessions=(63, 126, 252),
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        phase7_evaluation_cli,
        "verify_generation4_phase7_evaluation_authorization",
        lambda path: authorization,
    )

    def fake_acquire(**kwargs):
        captured.update(kwargs)
        return {"status": "SYNTHETIC_OK"}

    monkeypatch.setattr(
        phase7_evaluation_cli, "acquire_prospective_phase7_data", fake_acquire
    )

    rc = phase7_evaluation_cli.main(
        [
            "acquire-phase7-data",
            "--evaluation-authorization",
            str(tmp_path / "authorization.json"),
            "--output-dir",
            str(tmp_path / "out"),
            "--requested-start",
            START,
            "--requested-end",
            END,
            "--retrieved-at-utc",
            AFTER_CLOSE,
        ]
    )
    assert rc == 0
    request = captured["request"]
    assert request["warmup_session_count"] == 3
    assert request["scored_session_count"] == 3
    assert json.loads(capsys.readouterr().out)["status"] == "SYNTHETIC_OK"
