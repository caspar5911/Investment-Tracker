from __future__ import annotations

import json
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

from investment_tracker.independent_audit.post_generation3 import (
    phase7_data as phase7_data_module,
    phase7_evaluation as phase7_evaluation_module,
    phase7_evaluation_cli as phase7_evaluation_cli_module,
)
from investment_tracker.quant.phase7 import generation4_durability as durability_module
from investment_tracker.independent_audit.post_generation3.phase7_evaluation import (
    resolve_generation4_phase7_prospective_boundary,
    verify_generation4_phase7_evaluation_preflight,
)

ROOT = Path(__file__).resolve().parents[2]
COMMITTED_START_CONTRACT = (
    ROOT / "data/governance/successor/generation4-phase7-start-contract.json"
)
COMMITTED_START_ARTIFACT = (
    ROOT / "data/governance/successor/generation4-phase7-start.json"
)
COMMITTED_EVALUATION_CONTRACT = (
    ROOT / "data/governance/successor/generation4-phase7-evaluation-contract.json"
)


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _committed_paths_exist() -> bool:
    return all(
        path.is_file()
        for path in (
            COMMITTED_START_CONTRACT,
            COMMITTED_START_ARTIFACT,
            COMMITTED_EVALUATION_CONTRACT,
        )
    )


def _load_contract() -> dict[str, object]:
    return json.loads(COMMITTED_EVALUATION_CONTRACT.read_text(encoding="utf-8"))


def _xny_business_days(start: date, end: date) -> list[str]:
    """Minimal XNYS calendar proxy: Mon-Fri business days.

    The committed Phase-7 start timestamp (2026-09-26, a Saturday) has no US
    market holiday on the following Monday (2026-09-28), so the first
    strictly-after-start business day is a deterministic, market-data-free
    resolution of the prospective scored boundary.
    """
    days: list[str] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def test_committed_evaluation_contract_is_frozen_pre_evaluation() -> None:
    if not _committed_paths_exist():
        return
    contract = _load_contract()
    assert contract["schema_version"] == "GENERATION4-PHASE7-EVALUATION-CONTRACT-v1"
    assert contract["status"] == "FROZEN_PRE_EVALUATION"
    assert contract["generation"] == "GENERATION_4"
    assert contract["phase7_started"] is True
    assert contract["phase7_performance_evaluation_authorized"] is False
    assert contract["production_readiness_approved"] is False
    assert contract["live_trading_authorized"] is False
    assert contract["holdout_reuse_authorized"] is False
    assert contract["candidate_search_authorized"] is False
    assert contract["parameter_mutation_authorized"] is False
    assert contract["symbol_substitution_authorized"] is False
    assert contract["adaptive_walk_forward_authorized"] is False
    assert contract["annual_reoptimization_authorized"] is False
    assert contract["result_dependent_methodology_change_allowed"] is False
    assert contract["result_dependent_parameter_change_allowed"] is False
    assert contract["recon009_status"] == "OPEN"
    assert contract["paper_only"] is True
    assert contract["dq030_status"] == "UNRESOLVED"
    assert contract["historical_lane_classification"] == "REUSED_HISTORY_DIAGNOSTIC_ONLY"
    assert "metrics" not in contract


def test_committed_evaluation_contract_passes_preflight() -> None:
    if not _committed_paths_exist():
        return
    report = verify_generation4_phase7_evaluation_preflight(
        start_artifact_path=COMMITTED_START_ARTIFACT,
        start_contract_path=COMMITTED_START_CONTRACT,
        evaluation_contract_path=COMMITTED_EVALUATION_CONTRACT,
    )
    assert report["status"] == "GENERATION4_PHASE7_EVALUATION_PREFLIGHT_READY"
    assert report["generation"] == "GENERATION_4"
    assert report["research_universe"] == [
        "GLD",
        "IEF",
        "IWM",
        "QQQ",
        "SPY",
        "TLT",
        "VNQ",
        "XLP",
    ]
    assert report["benchmark_symbol"] == "SPY"
    assert report["friction_cases_bps"] == [0, 3, 10, 25, 50]
    assert report["primary_friction_bps"] == 3
    assert report["warmup_session_limit"] == 210
    assert report["checkpoint_sessions"] == [63, 126, 252]
    assert report["prospective_first_scored_session"] == "2026-09-28"
    assert report["phase7_performance_evaluation_authorized"] is False
    assert report["recon009_status"] == "OPEN"
    assert report["paper_only"] is True


def test_committed_evaluation_contract_binds_frozen_source_hashes() -> None:
    if not _committed_paths_exist():
        return
    contract = _load_contract()
    assert contract["start_artifact_sha256"] == _file_sha(COMMITTED_START_ARTIFACT)
    assert contract["start_contract_sha256"] == _file_sha(COMMITTED_START_CONTRACT)
    assert contract["start_artifact_self_hash"] == json.loads(
        COMMITTED_START_ARTIFACT.read_text(encoding="utf-8")
    )["artifact_sha256"]
    assert contract["phase7_evaluation_source_sha256"] == _file_sha(
        Path(phase7_evaluation_module.__file__)
    )
    assert contract["phase7_evaluation_cli_source_sha256"] == _file_sha(
        Path(phase7_evaluation_cli_module.__file__)
    )
    assert contract["phase7_durability_source_sha256"] == _file_sha(
        Path(durability_module.__file__)
    )
    assert contract["phase7_data_boundary_source_sha256"] == _file_sha(
        Path(phase7_data_module.__file__)
    )


def test_committed_evaluation_contract_holdout_matches_start_artifact() -> None:
    if not _committed_paths_exist():
        return
    contract = _load_contract()
    artifact = json.loads(COMMITTED_START_ARTIFACT.read_text(encoding="utf-8"))
    assert contract["forbidden_holdout_symbols"] == artifact["locked_symbols"]
    assert "metrics" not in artifact


def test_committed_evaluation_contract_prospective_boundary_is_deterministic() -> None:
    if not _committed_paths_exist():
        return
    contract = _load_contract()
    artifact = json.loads(COMMITTED_START_ARTIFACT.read_text(encoding="utf-8"))
    sessions = _xny_business_days(date(2026, 9, 1), date(2027, 6, 30))
    boundary = resolve_generation4_phase7_prospective_boundary(
        sessions=sessions,
        started_at_utc=artifact["started_at_utc"],
        warmup_session_limit=int(contract["warmup_session_limit"]),
    )
    assert boundary["first_scored_session"] == contract["prospective_first_scored_session"]
    assert boundary["warmup_excluded_from_scored_pnl"] is True
