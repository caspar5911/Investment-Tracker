"""Synthetic, provider-free first-checkpoint preregistration tests."""

from __future__ import annotations

import json
import subprocess
from hashlib import sha256
from pathlib import Path

import exchange_calendars as xcals
import pytest

from investment_tracker.independent_audit.post_generation3 import (
    phase7_first_checkpoint as first,
)
from investment_tracker.independent_audit.post_generation3 import phase7_collector


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/governance/successor/generation4-phase7-first-checkpoint-contract.json"
AUTHORIZATION = ROOT / "data/governance/successor/generation4-phase7-evaluation-authorization.json"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _record(count: int, end: str, *, first_snapshot: bool = False) -> dict:
    contract = _contract()
    return {
        "snapshot_id": (
            contract["first_verified_snapshot_id"]
            if first_snapshot else f"gen4-phase7-snapshot-{count:032x}"
        ),
        "manifest_sha256": (
            contract["first_verified_snapshot_manifest_sha256"]
            if first_snapshot else f"{count:064x}"
        ),
        "requested_start": contract["warmup_start"],
        "requested_end": end,
        "scored_start": contract["first_scored_session"],
        "warmup_session_count": contract["warmup_session_count"],
        "scored_session_count": count,
        "candidate_id": contract["candidate_id"],
        "evaluation_authorization_id": contract["evaluation_authorization_id"],
        "evaluation_authorization_sha256": contract["evaluation_authorization_sha256"],
    }


def test_contract_binds_current_frozen_sources_and_governance() -> None:
    contract = _contract()
    bound = {
        "evaluation_authorization_sha256": AUTHORIZATION,
        "evaluation_request_sha256": ROOT / "data/governance/successor/generation4-phase7-evaluation-independent-audit-request.json",
        "evaluation_contract_sha256": ROOT / "data/governance/successor/generation4-phase7-evaluation-contract.json",
        "start_artifact_sha256": ROOT / "data/governance/successor/generation4-phase7-start.json",
        "start_contract_sha256": ROOT / "data/governance/successor/generation4-phase7-start-contract.json",
        "entry_authorization_sha256": ROOT / "data/governance/successor/generation4-phase7-entry-authorization.json",
        "evaluation_source_sha256": ROOT / "src/investment_tracker/independent_audit/post_generation3/phase7_evaluation.py",
        "evaluation_cli_source_sha256": ROOT / "src/investment_tracker/independent_audit/post_generation3/phase7_evaluation_cli.py",
        "durability_source_sha256": ROOT / "src/investment_tracker/quant/phase7/generation4_durability.py",
        "data_boundary_source_sha256": ROOT / "src/investment_tracker/independent_audit/post_generation3/phase7_data.py",
        "collector_source_sha256": ROOT / "src/investment_tracker/independent_audit/post_generation3/phase7_collector.py",
    }
    assert contract["schema_version"] == "GENERATION4-PHASE7-FIRST-CHECKPOINT-CONTRACT-v1"
    assert contract["status"] == "PREREGISTERED_EXECUTION_BLOCKED"
    assert contract["authority"] == "NONE"
    for field, path in bound.items():
        if field in first._FROZEN_SOURCE_COMMITS:
            relative = path.relative_to(ROOT).as_posix()
            frozen = subprocess.run(
                ["git", "-C", str(ROOT), "show", f"{first._FROZEN_SOURCE_COMMITS[field]}:{relative}"],
                capture_output=True, check=True,
            ).stdout
            assert contract[field] == sha256(frozen).hexdigest()
        else:
            assert contract[field] == sha256(path.read_bytes()).hexdigest()
    assert contract["candidate_id"] == "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
    assert contract["research_universe"] == ["GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP"]
    assert contract["forbidden_holdout_symbols"] == ["QQQM", "FALN", "IIPR", "PSTL", "EFAS"]
    assert contract["friction_cases_bps"] == [0, 3, 10, 25, 50]
    assert contract["primary_friction_bps"] == 3
    assert contract["benchmark_symbol"] == "SPY"
    assert contract["dq030_status"] == "UNRESOLVED"
    assert contract["recon009_status"] == "OPEN"
    assert contract["dq030_unknown_fields"] == ["max_drawdown", "calmar", "recovery"]
    assert contract["checkpoint_evaluation_authorized"] is False
    assert contract["checkpoint_specific_independent_audit_authorization_required"] is True
    assert contract["paper_only"] is True
    assert all(
        contract[key] is False for key in (
            "production_readiness_approved", "live_trading_authorized",
            "candidate_search_authorized", "parameter_mutation_authorized",
            "symbol_substitution_authorized", "holdout_reuse_authorized",
            "result_dependent_methodology_change_allowed",
        )
    )


def test_exact_62_63_64_xnys_boundary_and_210_warmup() -> None:
    contract = _contract()
    calendar = xcals.get_calendar("XNYS")
    scored = calendar.sessions_in_range("2026-09-28", "2026-12-28")
    warmup = calendar.sessions_in_range("2025-11-24", "2026-09-25")
    assert len(warmup) == contract["warmup_session_count"] == 210
    assert [str(scored[i].date()) for i in (61, 62, 63)] == [
        contract["prior_scored_session_62"],
        contract["last_scored_session"],
        contract["next_scored_session_64"],
    ]
    assert contract["exact_snapshot_session_count"] == len(warmup) + 63
    assert contract["snapshot_selection"] == "EXACT_63_COMPLETE_SNAPSHOT_ONLY"


@pytest.mark.parametrize(
    ("records", "expected_status", "selected_count"),
    [
        ([], "PHASE7_CHECKPOINT_PENDING", None),
        ([(1, "2026-09-28", True), (62, "2026-12-23", False)], "PHASE7_CHECKPOINT_PENDING", None),
        ([(1, "2026-09-28", True), (63, "2026-12-24", False)], "PHASE7_CHECKPOINT_READY", 63),
        ([(1, "2026-09-28", True), (64, "2026-12-28", False)], "PHASE7_UNKNOWN_ABSTAIN", None),
        ([(1, "2026-09-28", True), (63, "2026-12-24", False), (64, "2026-12-28", False)], "PHASE7_CHECKPOINT_READY", 63),
    ],
)
def test_readiness_uses_only_exact_63_verified_snapshot(
    records, expected_status, selected_count, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifests = [_record(*item[:2], first_snapshot=item[2]) for item in records]
    monkeypatch.setattr(first.collector, "_verified_snapshots", lambda authorization: manifests)
    monkeypatch.setattr(
        first.collector, "acquire_prospective_phase7_data",
        lambda **kwargs: pytest.fail("provider path was reached"),
    )

    report = first.first_checkpoint_readiness()

    assert report["status"] == expected_status, report
    assert report["checkpoint_scored_sessions"] == 63
    assert report["evaluation_authorized"] is False
    assert report["performance_computed"] is False
    assert not any(key in report for key in ("returns", "positions", "signals", "sharpe", "drawdown"))
    assert report.get("selected_snapshot_scored_sessions") == selected_count
    if selected_count:
        assert report["selected_snapshot_id"] == _record(63, "2026-12-24")["snapshot_id"]


def test_corrupt_snapshot_abstains_without_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    def corrupt(_authorization):
        raise phase7_collector.Generation4Phase7CollectorError(
            phase7_collector.PHASE7_UNKNOWN_ABSTAIN, "synthetic_corruption"
        )

    monkeypatch.setattr(first.collector, "_verified_snapshots", corrupt)
    report = first.first_checkpoint_readiness()
    assert report["status"] == "PHASE7_UNKNOWN_ABSTAIN"
    assert report["performance_computed"] is False


def test_contract_drift_abstains_before_snapshot_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _contract()
    contract["evaluation_authorization_sha256"] = "0" * 64
    bad = tmp_path / "checkpoint-contract.json"
    bad.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(first, "_CONTRACT_PATH", bad)
    monkeypatch.setattr(
        first.collector, "_verified_snapshots",
        lambda authorization: pytest.fail("snapshot read before contract validation"),
    )
    report = first.first_checkpoint_readiness()
    assert report["status"] == "PHASE7_UNKNOWN_ABSTAIN"


def test_missing_authorization_abstains_before_snapshot_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        first, "_historical_snapshot_authorization",
        lambda: (_ for _ in ()).throw(
            phase7_collector.Generation4Phase7CollectorError(
                phase7_collector.PHASE7_UNKNOWN_ABSTAIN, "synthetic_missing_authorization"
            )
        ),
    )
    monkeypatch.setattr(
        first.collector, "_verified_snapshots",
        lambda authorization: pytest.fail("snapshot read before authorization"),
    )
    report = first.first_checkpoint_readiness()
    assert report["status"] == "PHASE7_UNKNOWN_ABSTAIN"
    assert report["evaluation_authorized"] is False


def test_first_snapshot_identity_mismatch_abstains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_record = _record(1, "2026-09-28", first_snapshot=True)
    first_record["manifest_sha256"] = "0" * 64
    exact = _record(63, "2026-12-24")
    monkeypatch.setattr(
        first.collector, "_verified_snapshots", lambda authorization: [first_record, exact]
    )
    report = first.first_checkpoint_readiness()
    assert report["status"] == "PHASE7_UNKNOWN_ABSTAIN"
    assert "selected_snapshot_id" not in report


def test_later_snapshot_does_not_change_first_checkpoint_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_record = _record(1, "2026-09-28", first_snapshot=True)
    exact = _record(63, "2026-12-24")
    later = _record(64, "2026-12-28")
    records = [first_record, exact]
    monkeypatch.setattr(first.collector, "_verified_snapshots", lambda _: records)
    before = first.first_checkpoint_readiness()
    records.append(later)
    after = first.first_checkpoint_readiness()
    assert before["selected_snapshot_chain_sha256"] == after["selected_snapshot_chain_sha256"]
