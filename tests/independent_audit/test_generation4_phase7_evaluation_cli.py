"""Generation-4 Phase-7 read-only evaluation CLI tests (Task 7, RED first).

These tests prove:

- the read-only CLI exposes the two pre-authorization commands
  (``verify-evaluation-preflight``, ``resolve-prospective-boundary``) as thin,
  fail-closed wrappers over the trusted evaluation functions;
- the two post-authorization commands (``acquire-phase7-data``,
  ``evaluate-phase7-checkpoint``) fail BEFORE any provider/data access when the
  evaluation authorization is absent or invalid;
- no command accepts arbitrary symbols or strategy-parameter overrides;
- the CLI source carries no trade/order/trade-context API identifiers and no
  final-holdout tickers (mirrors the focused CI "Governance boundary" grep).
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd
import pytest

from investment_tracker.independent_audit.post_generation3 import (
    phase7_data,
    phase7_evaluation_cli,
)
from investment_tracker.independent_audit.post_generation3.phase7_data import (
    SNAPSHOT_SCHEMA,
    acquire_prospective_phase7_data,
)

RESEARCH_UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
FORBIDDEN = ("QQQM", "FALN", "IIPR", "PSTL", "EFAS")
CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
BINDING_SHA256 = "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"
IMPLEMENTATION_SHA256 = (
    "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"
)
SPLIT_NORMALIZER_SHA256 = (
    "bfbf0de5bdeb39af3535641570f3f9224f5301abb7db9fffc34c580481cace04"
)
DIVIDEND_RECONCILIATION_SHA256 = (
    "6baa251d51f6f16be602aa82b08fc46665a4ccdd62f68705821c48c8a28ac9bc"
)
SUCCESSOR_EVALUATOR_SHA256 = (
    "fb20b368d6d7ac0f698c5ab45e5824aaad73341cccfacc25bc6903b98c9a2b21"
)
PHASE6_STATUS = "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"
AUTHORITY = "COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION"
_BOUND_EVIDENCE = None


@pytest.fixture(autouse=True)
def _synthetic_authorization_evidence(bound_evidence):
    global _BOUND_EVIDENCE
    _BOUND_EVIDENCE = bound_evidence
    yield
    _BOUND_EVIDENCE = None


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> Path:
    path.write_bytes(_canonical(value))
    return path


def _self_hash(payload: dict[str, object]) -> str:
    body = dict(payload)
    body.pop("artifact_sha256", None)
    return sha256(_canonical(body)).hexdigest()


def _start_contract_payload() -> dict[str, object]:
    return {
        "schema_version": "GENERATION4-PHASE7-START-CONTRACT-v1",
        "status": "FROZEN_PRE_START",
        "authority": AUTHORITY,
        "generation": "GENERATION_4",
        "candidate_id": CANDIDATE_ID,
        "binding_sha256": BINDING_SHA256,
        "implementation_sha256": IMPLEMENTATION_SHA256,
        "split_normalizer_sha256": SPLIT_NORMALIZER_SHA256,
        "dividend_reconciliation_sha256": DIVIDEND_RECONCILIATION_SHA256,
        "successor_evaluator_sha256": SUCCESSOR_EVALUATOR_SHA256,
        "locked_symbols": list(FORBIDDEN),
        "holdout_id": "successor-phase6-holdout-synthetic",
        "release_id": "successor-phase6-release-synthetic",
        "authorization_id": "SYNTHETIC-GEN4-PHASE7-AUTHORIZATION",
        "entry_authorization_sha256": "a" * 64,
        "audit_request_sha256": "b" * 64,
        "phase6_contract_sha256": "1" * 64,
        "acquisition_authorization_sha256": "2" * 64,
        "acquisition_receipt_sha256": "3" * 64,
        "release_sha256": "4" * 64,
        "evaluation_result_sha256": "5" * 64,
        "evaluation_consumption_marker_sha256": "6" * 64,
        "phase6_closure_sha256": "7" * 64,
        "phase6_status": PHASE6_STATUS,
        "one_time_consumed": True,
        "phase7_entry_implementation_commit": "7" * 40,
        "phase7_entry_source_sha256": "c" * 64,
        "phase7_entry_cli_source_sha256": "d" * 64,
        "phase7_start_implementation_commit": "3" * 40,
        "phase7_start_source_sha256": "f" * 64,
        "phase7_start_cli_source_sha256": "9" * 64,
        "phase7_entry_authorized": True,
        "phase7_started": False,
        "phase7_performance_evaluation_authorized": False,
        "production_readiness_approved": False,
        "live_trading_authorized": False,
        "retry_authorized": False,
        "holdout_reuse_authorized": False,
        "candidate_search_authorized": False,
        "parameter_mutation_authorized": False,
        "symbol_substitution_authorized": False,
        "result_dependent_methodology_change_allowed": False,
        "result_dependent_parameter_change_allowed": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }


def _start_artifact_payload(start_contract_sha256: str) -> dict[str, object]:
    payload = dict(_start_contract_payload())
    payload.update(
        {
            "schema_version": "GENERATION4-PHASE7-START-v1",
            "status": "GENERATION4_PHASE7_STARTED",
            "started_at_utc": "2026-09-26T00:00:00Z",
            "start_contract_sha256": start_contract_sha256,
            "phase7_started": True,
        }
    )
    payload["artifact_sha256"] = _self_hash(payload)
    return payload


def _evaluation_contract_payload(
    start_artifact_sha256: str,
    start_artifact_self_hash: str,
    start_contract_sha256: str,
) -> dict[str, object]:
    return {
        "schema_version": "GENERATION4-PHASE7-EVALUATION-CONTRACT-v1",
        "status": "FROZEN_PRE_EVALUATION",
        "authority": AUTHORITY,
        "generation": "GENERATION_4",
        "candidate_id": CANDIDATE_ID,
        "binding_sha256": BINDING_SHA256,
        "implementation_sha256": IMPLEMENTATION_SHA256,
        "split_normalizer_sha256": SPLIT_NORMALIZER_SHA256,
        "dividend_reconciliation_sha256": DIVIDEND_RECONCILIATION_SHA256,
        "successor_evaluator_sha256": SUCCESSOR_EVALUATOR_SHA256,
        "start_artifact_sha256": start_artifact_sha256,
        "start_artifact_self_hash": start_artifact_self_hash,
        "start_contract_sha256": start_contract_sha256,
        "entry_authorization_id": "SYNTHETIC-GEN4-PHASE7-AUTHORIZATION",
        "entry_authorization_sha256": "a" * 64,
        "phase7_entry_implementation_commit": "7" * 40,
        "phase7_entry_source_sha256": "c" * 64,
        "phase7_entry_cli_source_sha256": "d" * 64,
        "phase7_start_implementation_commit": "3" * 40,
        "phase7_start_source_sha256": "f" * 64,
        "phase7_start_cli_source_sha256": "9" * 64,
        "phase7_evaluation_implementation_commit": "e" * 40,
        "phase7_evaluation_source_sha256": "0" * 64,
        "phase7_evaluation_cli_source_sha256": "8" * 64,
        "phase7_durability_source_sha256": "7" * 64,
        "phase7_data_boundary_source_sha256": "6" * 64,
        "research_universe": list(RESEARCH_UNIVERSE),
        "forbidden_holdout_symbols": list(FORBIDDEN),
        "benchmark_symbol": "SPY",
        "initial_cash": 100000.0,
        "friction_cases_bps": [0, 3, 10, 25, 50],
        "primary_friction_bps": 3,
        "prospective_first_scored_session": "2026-09-28",
        "warmup_session_limit": 210,
        "checkpoint_sessions": [63, 126, 252],
        "historical_lane_classification": "REUSED_HISTORY_DIAGNOSTIC_ONLY",
        "dq030_status": "UNRESOLVED",
        "phase7_started": True,
        "phase7_performance_evaluation_authorized": False,
        "production_readiness_approved": False,
        "live_trading_authorized": False,
        "holdout_reuse_authorized": False,
        "candidate_search_authorized": False,
        "parameter_mutation_authorized": False,
        "symbol_substitution_authorized": False,
        "adaptive_walk_forward_authorized": False,
        "annual_reoptimization_authorized": False,
        "result_dependent_methodology_change_allowed": False,
        "result_dependent_parameter_change_allowed": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }


def _valid_paths(tmp_path: Path) -> dict[str, Path]:
    start_contract = _write(tmp_path / "start-contract.json", _start_contract_payload())
    artifact_payload = _start_artifact_payload(_sha(start_contract))
    start_artifact = _write(tmp_path / "start.json", artifact_payload)
    evaluation_contract = _write(
        tmp_path / "evaluation-contract.json",
        _evaluation_contract_payload(
            _sha(start_artifact),
            str(artifact_payload["artifact_sha256"]),
            _sha(start_contract),
        ),
    )
    return {
        "start_artifact": start_artifact,
        "start_contract": start_contract,
        "evaluation_contract": evaluation_contract,
    }


def _frames():
    calendar = xcals.get_calendar("XNYS")
    all_sessions = calendar.sessions_in_range("2025-01-01", "2026-09-30")
    scored_pos = all_sessions.get_loc(pd.Timestamp("2026-09-28"))
    index = all_sessions[scored_pos - 210 : scored_pos + 3]
    if index.tz is None:
        index = index.tz_localize("UTC")
    out = {}
    for i, symbol in enumerate(RESEARCH_UNIVERSE):
        close = [100.0 + 0.5 * (i + 1) * step for step in range(1, len(index) + 1)]
        out[symbol] = pd.DataFrame({"open": close, "close": close}, index=index)
    return out


class _FakeQuoteClient:
    def __init__(self, frames):
        self._frames = frames
        self.fetched = []
        self.closed = False

    def fetch_daily_bars(self, symbol, start, end):
        self.fetched.append(symbol)
        return self._frames[symbol]

    def close(self):
        self.closed = True


def _spy_client_factory(frames):
    created = {"count": 0, "clients": []}

    def factory(*, host, port):
        created["count"] += 1
        client = _FakeQuoteClient(frames)
        created["clients"].append(client)
        return client

    return factory, created


def _authorization(**overrides):
    return _BOUND_EVIDENCE.auth(**overrides)


def _request(**overrides):
    payload = {
        "schema_version": "GENERATION4-PHASE7-DATA-REQUEST-v1",
        "symbols": list(RESEARCH_UNIVERSE),
        "requested_start": str(_frames()[RESEARCH_UNIVERSE[0]].index[0].date()),
        "requested_end": "2026-09-30",
        "scored_start": "2026-09-28",
        "warmup_session_count": 210,
        "scored_session_count": 3,
    }
    payload.update(overrides)
    return payload


def _stdout_json(capsys):
    return json.loads(capsys.readouterr().out)


# ---------------------------------------------------------------------------
# Pre-authorization command: verify-evaluation-preflight
# ---------------------------------------------------------------------------


def test_verify_evaluation_preflight_command_succeeds(tmp_path, capsys):
    paths = _valid_paths(tmp_path)
    rc = phase7_evaluation_cli.main(
        [
            "verify-evaluation-preflight",
            "--start-artifact",
            str(paths["start_artifact"]),
            "--start-contract",
            str(paths["start_contract"]),
            "--evaluation-contract",
            str(paths["evaluation_contract"]),
        ]
    )
    assert rc == 0
    report = _stdout_json(capsys)
    assert report["status"] == "GENERATION4_PHASE7_EVALUATION_PREFLIGHT_READY"
    assert report["candidate_id"] == CANDIDATE_ID
    assert "metrics" not in report


def test_verify_evaluation_preflight_command_fails_closed_missing_artifact(
    tmp_path, capsys
):
    paths = _valid_paths(tmp_path)
    paths["start_artifact"].unlink()
    rc = phase7_evaluation_cli.main(
        [
            "verify-evaluation-preflight",
            "--start-artifact",
            str(paths["start_artifact"]),
            "--start-contract",
            str(paths["start_contract"]),
            "--evaluation-contract",
            str(paths["evaluation_contract"]),
        ]
    )
    assert rc == 1
    out = _stdout_json(capsys)
    assert out["status"] == "FORBIDDEN"
    assert out["code"] == "GEN4_PHASE7_EVAL_EVIDENCE_INVALID"


# ---------------------------------------------------------------------------
# Pre-authorization command: resolve-prospective-boundary
# ---------------------------------------------------------------------------


def test_resolve_prospective_boundary_command_succeeds(tmp_path, capsys):
    start_artifact = _write(
        tmp_path / "start.json", {"started_at_utc": "2026-09-26T00:00:00Z"}
    )
    sessions = _write(
        tmp_path / "sessions.json", ["2026-09-25", "2026-09-28", "2026-09-29"]
    )
    rc = phase7_evaluation_cli.main(
        [
            "resolve-prospective-boundary",
            "--start-artifact",
            str(start_artifact),
            "--sessions",
            str(sessions),
        ]
    )
    assert rc == 0
    report = _stdout_json(capsys)
    assert report["schema_version"] == "GENERATION4-PHASE7-PROSPECTIVE-BOUNDARY-v1"
    # The first scored session is strictly later than the start timestamp.
    assert report["first_scored_session"] == "2026-09-28"
    assert report["warmup_excluded_from_scored_pnl"] is True


def test_resolve_prospective_boundary_command_unresolved_fails_closed(
    tmp_path, capsys
):
    start_artifact = _write(
        tmp_path / "start.json", {"started_at_utc": "2026-09-26T00:00:00Z"}
    )
    sessions = _write(tmp_path / "sessions.json", ["2026-09-20", "2026-09-21"])
    rc = phase7_evaluation_cli.main(
        [
            "resolve-prospective-boundary",
            "--start-artifact",
            str(start_artifact),
            "--sessions",
            str(sessions),
        ]
    )
    assert rc == 1
    out = _stdout_json(capsys)
    assert out["status"] == "FORBIDDEN"
    assert out["code"] == "GEN4_PHASE7_EVAL_BOUNDARY_UNRESOLVED"


# ---------------------------------------------------------------------------
# Post-authorization command: acquire-phase7-data (fail closed pre-provider)
# ---------------------------------------------------------------------------


def test_acquire_phase7_data_missing_auth_fails_before_provider(
    tmp_path, capsys, monkeypatch
):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    monkeypatch.setattr(phase7_data, "_default_client_factory", factory)
    rc = phase7_evaluation_cli.main(
        [
            "acquire-phase7-data",
            "--evaluation-authorization",
            str(tmp_path / "does-not-exist.json"),
            "--output-dir",
            str(tmp_path / "out"),
            "--requested-start",
            str(_frames()[RESEARCH_UNIVERSE[0]].index[0].date()),
            "--requested-end",
            "2026-09-30",
            "--retrieved-at-utc",
            "2026-10-01T00:00:00Z",
        ]
    )
    assert rc == 1
    out = _stdout_json(capsys)
    assert out["status"] == "FORBIDDEN"
    assert created["count"] == 0


def test_acquire_phase7_data_invalid_auth_fails_before_provider(
    tmp_path, capsys, monkeypatch
):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    monkeypatch.setattr(phase7_data, "_default_client_factory", factory)
    auth_file = _write(tmp_path / "auth.json", _authorization(status="DRAFT_TEMPLATE_NOT_AUTHORIZATION"))
    rc = phase7_evaluation_cli.main(
        [
            "acquire-phase7-data",
            "--evaluation-authorization",
            str(auth_file),
            "--output-dir",
            str(tmp_path / "out"),
            "--requested-start",
            str(_frames()[RESEARCH_UNIVERSE[0]].index[0].date()),
            "--requested-end",
            "2026-09-30",
            "--retrieved-at-utc",
            "2026-10-01T00:00:00Z",
        ]
    )
    assert rc == 1
    out = _stdout_json(capsys)
    assert out["status"] == "FORBIDDEN"
    assert created["count"] == 0


def test_acquire_phase7_data_valid_auth_uses_provider_once(
    tmp_path, capsys, monkeypatch
):
    frames = _frames()
    factory, created = _spy_client_factory(frames)
    monkeypatch.setattr(phase7_data, "_default_client_factory", factory)
    auth_file = _write(tmp_path / "auth.json", _authorization())
    rc = phase7_evaluation_cli.main(
        [
            "acquire-phase7-data",
            "--evaluation-authorization",
            str(auth_file),
            "--output-dir",
            str(tmp_path / "out"),
            "--requested-start",
            str(_frames()[RESEARCH_UNIVERSE[0]].index[0].date()),
            "--requested-end",
            "2026-09-30",
            "--retrieved-at-utc",
            "2026-10-01T00:00:00Z",
        ]
    )
    assert rc == 0
    out = _stdout_json(capsys)
    assert out["schema_version"] == SNAPSHOT_SCHEMA
    assert out["trading_context_created"] is False
    # The provider was created exactly once, only after a valid authorization.
    assert created["count"] == 1
    assert created["clients"][0].fetched == list(RESEARCH_UNIVERSE)
    assert created["clients"][0].closed is True


# ---------------------------------------------------------------------------
# Post-authorization command: evaluate-phase7-checkpoint
# ---------------------------------------------------------------------------


def test_evaluate_phase7_checkpoint_missing_auth_fails_before_data(
    tmp_path, capsys
):
    rc = phase7_evaluation_cli.main(
        [
            "evaluate-phase7-checkpoint",
            "--evaluation-authorization",
            str(tmp_path / "does-not-exist.json"),
            "--snapshot",
            str(tmp_path / "no-snapshot"),
        ]
    )
    assert rc == 1
    out = _stdout_json(capsys)
    assert out["status"] == "FORBIDDEN"


def test_evaluate_phase7_checkpoint_valid_auth_renders_pending_report(
    tmp_path, capsys, monkeypatch
):
    frames = _frames()
    factory, _ = _spy_client_factory(frames)
    monkeypatch.setattr(phase7_data, "_default_client_factory", factory)
    manifest = acquire_prospective_phase7_data(
        evaluation_authorization=_authorization(),
        request=_request(),
        output_dir=tmp_path / "snap",
        retrieved_at_utc="2026-10-01T00:00:00Z",
        client_factory=factory,
    )
    snapshot_dir = tmp_path / "snap" / "snapshots" / manifest["snapshot_id"]
    auth_file = _write(tmp_path / "auth.json", _authorization())
    rc = phase7_evaluation_cli.main(
        [
            "evaluate-phase7-checkpoint",
            "--evaluation-authorization",
            str(auth_file),
            "--snapshot",
            str(snapshot_dir),
        ]
    )
    assert rc == 0
    report = _stdout_json(capsys)
    assert report["schema"] == "GENERATION4-PHASE7-PROSPECTIVE-CHECKPOINT-v1"
    # All bars precede the frozen scored start, so no session is scored yet.
    assert report["scored_session_count"] == 0
    assert report["status"] == "PHASE7_PROSPECTIVE_EVIDENCE_PENDING"
    # A pending/complete result never grants production or live authority.
    assert report["production_authority"] is False
    assert report["live_trading_authority"] is False
    assert report["paper_only"] is True


# ---------------------------------------------------------------------------
# No command may accept arbitrary symbols or parameter overrides.
# ---------------------------------------------------------------------------


def test_no_command_accepts_arbitrary_symbols_or_parameters():
    parser = phase7_evaluation_cli.build_parser()
    # Each known command parses with exactly its intended (read-only) options.
    parser.parse_args(
        [
            "verify-evaluation-preflight",
            "--start-artifact",
            "a",
            "--start-contract",
            "b",
            "--evaluation-contract",
            "c",
        ]
    )
    parser.parse_args(
        ["resolve-prospective-boundary", "--start-artifact", "a", "--sessions", "b"]
    )
    parser.parse_args(
        [
            "acquire-phase7-data",
            "--evaluation-authorization",
            "a",
            "--output-dir",
            "b",
            "--requested-start",
            str(_frames()[RESEARCH_UNIVERSE[0]].index[0].date()),
            "--requested-end",
            "2026-09-30",
            "--retrieved-at-utc",
            "2026-10-01T00:00:00Z",
        ]
    )
    parser.parse_args(
        [
            "evaluate-phase7-checkpoint",
            "--evaluation-authorization",
            "a",
            "--snapshot",
            "b",
        ]
    )


def test_acquire_command_rejects_arbitrary_symbol_flag():
    parser = phase7_evaluation_cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "acquire-phase7-data",
                "--evaluation-authorization",
                "a",
                "--output-dir",
                "b",
                "--requested-start",
                str(_frames()[RESEARCH_UNIVERSE[0]].index[0].date()),
                "--requested-end",
                "2026-09-30",
                "--retrieved-at-utc",
                "2026-10-01T00:00:00Z",
                "--symbols",
                "GLD",
            ]
        )


def test_evaluate_command_rejects_parameter_override_flags():
    parser = phase7_evaluation_cli.build_parser()
    for flag in ("--checkpoint-cutoff", "--lookback", "--friction"):
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "evaluate-phase7-checkpoint",
                    "--evaluation-authorization",
                    "a",
                    "--snapshot",
                    "b",
                    flag,
                    "0",
                ]
            )


# ---------------------------------------------------------------------------
# Static governance scans on the CLI source (mirrors focused CI grep).
# ---------------------------------------------------------------------------


def test_cli_source_contains_no_trade_or_order_api():
    source = Path(phase7_evaluation_cli.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "OpenTradeContext",
        "place_order",
        "modify_order",
        "cancel_order",
        "unlock_trade",
        "TrdEnv",
        "buy_stock",
        "sell_stock",
    ):
        assert forbidden not in source, f"forbidden identifier {forbidden!r} in CLI source"


def test_cli_source_contains_no_holdout_symbols():
    source = Path(phase7_evaluation_cli.__file__).read_text(encoding="utf-8")
    for symbol in FORBIDDEN:
        assert symbol not in source, f"holdout literal {symbol!r} in CLI source"
