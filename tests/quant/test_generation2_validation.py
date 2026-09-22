"""Tests for the generation-2 VALIDATION campaign (C4).

Pins the frozen VALIDATION procedure from
``2026-09-22-generation2-governance-preregistration.md``:

- only the preregistered TRAIN shortlist (<= 12) may be evaluated, and each
  candidate must still bind to the frozen grid;
- decision targets are restricted to the frozen VALIDATION due window
  [2019-01-01, 2022-12-31] while retaining full causal warm-up;
- the frozen pass criteria (all of which must hold) and their stable
  fail-closed reason codes;
- the frozen survivor ordering (Sharpe -> CAGR -> MDD magnitude -> turnover ->
  candidate_id), and ``NO_CREDIBLE_GENERATION2_CANDIDATE`` when none pass;
- the exclusive, self-verifying, content-addressed validation report
  (tamper detection, duplicate-seal rejection, survivor recompute);
- a real-cache end-to-end slice (skipped when the cache is absent).
"""

from __future__ import annotations

import json
import pathlib

import pandas as pd
import pytest

from investment_tracker.quant.generation2 import validation
from investment_tracker.quant.generation2.campaign import (
    CampaignError,
    REPORT_NAME as TRAIN_REPORT_NAME,
    verify_train_report,
)
from investment_tracker.quant.generation2.grid import (
    GridCandidate,
    build_generation2_grid,
    canonical_grid_manifest,
    grid_manifest_sha256,
)
from investment_tracker.quant.generation2.research_boundary import (
    RESEARCH_SYMBOLS,
    VALIDATION_END,
    VALIDATION_START,
    load_research_boundary,
)
from investment_tracker.quant.generation2.validation import (
    MAX_SHORTLIST,
    ROLLING_12M_POSITIVE_FRACTION_MIN,
    STATUS_NO_CREDIBLE,
    STATUS_SURVIVOR,
    REPORT_NAME,
    VALIDATION_SCHEMA,
    assess_pass,
    build_validation_targets,
    evaluate_validation_candidate,
    frozen_candidate_by_id,
    load_shortlist,
    run_validation_campaign,
    select_survivor,
    seal_validation_report,
    verify_validation_report,
)

REAL_CACHE = validation._repo_root() / "data" / "cache"
REAL_NORMALIZED_ROOT = REAL_CACHE / "phase3" / "normalized" / "sha256"
COMMITTED_TRAIN_REPORT = (
    validation._repo_root()
    / "data"
    / "governance"
    / "generation2-campaign"
    / TRAIN_REPORT_NAME
)
COMMITTED_VALIDATION_REPORT = (
    validation._repo_root()
    / "data"
    / "governance"
    / "generation2-campaign"
    / REPORT_NAME
)

FROZEN_ENTRIES = canonical_grid_manifest()["candidates"]

FROZEN_A = "G2-A|lookback=63|skip=0|top_k=1|rebalance=21"
FROZEN_B = "G2-B|lookback=63|trend_ma=126|top_k=1|rebalance=21"
FROZEN_C = "G2-C|lookback=63|vol_lookback=20|top_k=2|rebalance=21"
FROZEN_D = "G2-D|horizons=21+63+126|skip=0|top_k=2|rebalance=42"


def _candidate(candidate_id: str) -> GridCandidate:
    for entry in FROZEN_ENTRIES:
        if entry["candidate_id"] == candidate_id:
            data = dict(entry)
            data.pop("candidate_id")
            return GridCandidate(candidate_id=candidate_id, **data)
    raise LookupError(candidate_id)


def _validation_bars(n: int = 2300) -> dict[str, pd.DataFrame]:
    """Deterministic bars spanning 2014..2022 (warm-up + VALIDATION window).

    The drift (0.15/session) dominates the oscillation (amplitude 4.0,
    ~126-session period, at most 4.0/20 = 0.20 per session), so 63-session
    momentum, the 126-session trend filter, and every 12-month window stay
    positive, while individual down days still exist and Sortino's downside
    denominator is strictly positive for an uptrending candidate.
    """
    import math

    index = pd.bdate_range("2014-01-01", periods=n, tz="UTC")
    bars: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(RESEARCH_SYMBOLS):
        values = [
            100.0 + 0.15 * i + 0.1 * offset + 4.0 * math.sin(i / 20.0)
            for i in range(n)
        ]
        bars[symbol] = pd.DataFrame({"open": values, "close": values}, index=index)
    return bars


# ---------------------------------------------------------------------------
# Due-window target construction
# ---------------------------------------------------------------------------


def test_build_validation_targets_restricts_due_window() -> None:
    candidate = _candidate(FROZEN_A)
    bars = _validation_bars()
    targets = build_validation_targets(candidate, bars)
    assert len(targets) > 0
    window_start = pd.Timestamp(VALIDATION_START, tz="UTC")
    window_end = pd.Timestamp(VALIDATION_END, tz="UTC")
    for target in targets:
        assert window_start <= target.due_session <= window_end
        assert target.signal_session < target.due_session
    # The ledger starts at the first in-window due session, never before.
    assert targets[0].due_session >= window_start


def test_build_validation_targets_full_frame_retained_for_warmup() -> None:
    # Signals for early-2019 due dates must be able to read pre-2019 history.
    candidate = _candidate(FROZEN_A)
    bars = _validation_bars()
    first_due = build_validation_targets(candidate, bars)[0].due_session
    # The first in-window due is a real session present in the bars.
    assert first_due in bars["SPY"].index


# ---------------------------------------------------------------------------
# Shortlist loading
# ---------------------------------------------------------------------------


def test_load_shortlist_flattens_in_family_order() -> None:
    train_report = {
        "report_sha256": "0" * 64,
        "shortlist": {
            "G2-A": ["a1", "a2"],
            "G2-B": ["b1"],
            "G2-C": [],
            "G2-D": ["d1"],
        },
    }
    assert load_shortlist(train_report) == ("a1", "a2", "b1", "d1")


def test_load_shortlist_rejects_missing() -> None:
    with pytest.raises(CampaignError) as excinfo:
        load_shortlist({"report_sha256": "0" * 64})
    assert excinfo.value.code == "VALIDATION_SHORTLIST_MISSING"


def test_load_shortlist_enforces_maximum_size() -> None:
    train_report = {
        "report_sha256": "0" * 64,
        "shortlist": {
            "G2-A": ["a1", "a2", "a3"],
            "G2-B": ["b1", "b2", "b3"],
            "G2-C": ["c1", "c2", "c3"],
            "G2-D": ["d1", "d2", "d3"],
        },
    }
    # 12 is allowed.
    assert len(load_shortlist(train_report)) == MAX_SHORTLIST
    # 13 must fail closed.
    train_report["shortlist"]["G2-D"].append("d4")
    with pytest.raises(CampaignError) as excinfo:
        load_shortlist(train_report)
    assert excinfo.value.code == "VALIDATION_SHORTLIST_TOO_LARGE"


# ---------------------------------------------------------------------------
# Pass criteria
# ---------------------------------------------------------------------------


def _metric(status: str = "AVAILABLE", value: float | None = 1.0) -> dict:
    return {
        "status": status,
        "value": value,
        "reason": "OK" if status == "AVAILABLE" else "X",
    }


def _case(primary: dict, bps: int = 3) -> dict:
    case = {
        "friction_bps": bps,
        "replay_error": None,
        "replay_sha256": "0" * 64,
        "session_count": 2000,
        "exposure_invariant_passes": True,
    }
    case.update(primary)
    return case


def _passing_case() -> dict:
    return {
        "total_return": _metric("AVAILABLE", 0.5),
        "cagr": _metric("AVAILABLE", 0.1),
        "sharpe": _metric("AVAILABLE", 2.0),
        "sortino": _metric("AVAILABLE", 2.0),
        "annualized_one_way_turnover": _metric("AVAILABLE", 1.0),
        "rolling_12m_positive_fraction": _metric("AVAILABLE", 0.8),
        "max_drawdown": _metric("AVAILABLE", 0.1),
        "calmar": _metric("AVAILABLE", 1.0),
    }


def _record(case_primary: dict, case_25: dict) -> dict:
    return {
        "candidate_id": "X",
        "family": "G2-A",
        "candidate": {"candidate_id": "X", "family": "G2-A"},
        "target_count": 50,
        "friction_cases": {"3": case_primary, "25": case_25},
    }


def test_assess_pass_all_pass() -> None:
    primary = _case(_passing_case())
    case_25 = _case(_passing_case(), bps=25)
    passed, reasons = assess_pass(_record(primary, case_25))
    assert passed is True
    assert reasons == []


def test_assess_pass_total_return_not_positive() -> None:
    primary = _case(_passing_case())
    primary["total_return"] = _metric("AVAILABLE", -0.1)
    case_25 = _case(_passing_case(), bps=25)
    passed, reasons = assess_pass(_record(primary, case_25))
    assert passed is False
    assert "VALIDATION_TOTAL_RETURN_UNAVAILABLE_OR_NOT_POSITIVE" in reasons


def test_assess_pass_sharpe_unknown() -> None:
    primary = _case(_passing_case())
    primary["sharpe"] = _metric("UNKNOWN", None)
    case_25 = _case(_passing_case(), bps=25)
    passed, reasons = assess_pass(_record(primary, case_25))
    assert passed is False
    assert "VALIDATION_SHARPE_UNAVAILABLE_OR_NOT_POSITIVE" in reasons
    assert "VALIDATION_SHARPE_UNKNOWN" in reasons


def test_assess_pass_exposure_invariant_fails() -> None:
    primary = _case(_passing_case())
    primary["exposure_invariant_passes"] = False
    case_25 = _case(_passing_case(), bps=25)
    passed, reasons = assess_pass(_record(primary, case_25))
    assert passed is False
    assert "VALIDATION_EXPOSURE_INVARIANT_FAILED" in reasons


def test_assess_pass_friction_25bp_not_positive() -> None:
    primary = _case(_passing_case())
    case_25 = _case(_passing_case(), bps=25)
    case_25["total_return"] = _metric("AVAILABLE", -0.05)
    passed, reasons = assess_pass(_record(primary, case_25))
    assert passed is False
    assert "VALIDATION_FRICTION_25BP_TOTAL_RETURN_UNAVAILABLE_OR_NOT_POSITIVE" in reasons


def test_assess_pass_rolling_12m_below_threshold() -> None:
    primary = _case(_passing_case())
    primary["rolling_12m_positive_fraction"] = _metric("AVAILABLE", 0.4)
    case_25 = _case(_passing_case(), bps=25)
    passed, reasons = assess_pass(_record(primary, case_25))
    assert passed is False
    assert "VALIDATION_ROLLING_12M_POSITIVE_FRACTION_BELOW_050" in reasons


def test_assess_pass_max_drawdown_unavailable() -> None:
    primary = _case(_passing_case())
    primary["max_drawdown"] = _metric("UNKNOWN", None)
    case_25 = _case(_passing_case(), bps=25)
    passed, reasons = assess_pass(_record(primary, case_25))
    assert passed is False
    assert "VALIDATION_MAX_DRAWDOWN_UNAVAILABLE" in reasons


def test_assess_pass_primary_replay_failed() -> None:
    primary = _case(_passing_case())
    primary["replay_error"] = "DECISION_LONG_ONLY_ACCOUNTING_BREACH"
    case_25 = _case(_passing_case(), bps=25)
    passed, reasons = assess_pass(_record(primary, case_25))
    assert passed is False
    assert "VALIDATION_PRIMARY_REPLAY_FAILED" in reasons


def test_assess_pass_sortino_negative_rejected() -> None:
    primary = _case(_passing_case())
    primary["sortino"] = _metric("AVAILABLE", -0.3)
    case_25 = _case(_passing_case(), bps=25)
    passed, reasons = assess_pass(_record(primary, case_25))
    assert passed is False
    assert "VALIDATION_SORTINO_UNAVAILABLE_OR_NOT_POSITIVE" in reasons


# ---------------------------------------------------------------------------
# Survivor selection (frozen ordering)
# ---------------------------------------------------------------------------


def _survivor_record(candidate_id: str, *, sharpe, cagr, mdd, turnover) -> dict:
    primary = _passing_case()
    primary["sharpe"] = _metric("AVAILABLE", sharpe)
    primary["cagr"] = _metric("AVAILABLE", cagr)
    primary["max_drawdown"] = _metric("AVAILABLE", mdd)
    primary["annualized_one_way_turnover"] = _metric("AVAILABLE", turnover)
    case_25 = _case(_passing_case(), bps=25)
    record = _record(_case(primary), case_25)
    record["candidate_id"] = candidate_id
    record["pass"] = True
    return record


def test_select_survivor_none_pass() -> None:
    failing = _passing_case()
    failing["sharpe"] = _metric("UNKNOWN", None)
    records = {
        "A": _record(_case(failing), _case(_passing_case(), bps=25)),
    }
    assert select_survivor(records) is None


def test_select_survivor_prefers_higher_sharpe() -> None:
    records = {
        "low": _survivor_record("low", sharpe=1.0, cagr=0.2, mdd=0.05, turnover=0.5),
        "high": _survivor_record("high", sharpe=3.0, cagr=0.0, mdd=0.5, turnover=9.0),
    }
    assert select_survivor(records) == "high"


def test_select_survivor_cagr_tiebreak() -> None:
    records = {
        "low_cagr": _survivor_record("low_cagr", sharpe=2.0, cagr=0.05, mdd=0.05, turnover=0.5),
        "high_cagr": _survivor_record("high_cagr", sharpe=2.0, cagr=0.20, mdd=0.5, turnover=9.0),
    }
    assert select_survivor(records) == "high_cagr"


def test_select_survivor_mdd_magnitude_tiebreak() -> None:
    records = {
        "big_mdd": _survivor_record("big_mdd", sharpe=2.0, cagr=0.1, mdd=0.4, turnover=0.5),
        "small_mdd": _survivor_record("small_mdd", sharpe=2.0, cagr=0.1, mdd=0.05, turnover=9.0),
    }
    assert select_survivor(records) == "small_mdd"


def test_select_survivor_turnover_tiebreak() -> None:
    records = {
        "high_turnover": _survivor_record("high_turnover", sharpe=2.0, cagr=0.1, mdd=0.1, turnover=9.0),
        "low_turnover": _survivor_record("low_turnover", sharpe=2.0, cagr=0.1, mdd=0.1, turnover=0.5),
    }
    assert select_survivor(records) == "low_turnover"


def test_select_survivor_candidate_id_tiebreak() -> None:
    records = {
        "zeta": _survivor_record("zeta", sharpe=2.0, cagr=0.1, mdd=0.1, turnover=1.0),
        "alpha": _survivor_record("alpha", sharpe=2.0, cagr=0.1, mdd=0.1, turnover=1.0),
    }
    assert select_survivor(records) == "alpha"


# ---------------------------------------------------------------------------
# Candidate evaluation + campaign runner
# ---------------------------------------------------------------------------


def test_evaluate_validation_candidate_structure() -> None:
    bars = _validation_bars()
    record = evaluate_validation_candidate(_candidate(FROZEN_A), bars, (0, 3, 25))
    assert record["candidate_id"] == FROZEN_A
    assert record["family"] == "G2-A"
    assert record["candidate"] == _candidate(FROZEN_A).to_manifest_dict()
    assert set(record["friction_cases"]) == {"0", "3", "25"}
    for case in record["friction_cases"].values():
        assert case["replay_error"] is None
        assert len(case["replay_sha256"]) == 64
        assert case["session_count"] > 0
    assert isinstance(record["pass"], bool)
    assert isinstance(record["pass_reasons"], list)


def test_evaluate_validation_candidate_rejects_unknown_id() -> None:
    stranger = GridCandidate(
        candidate_id="G2-A|lookback=5|skip=5|top_k=1|rebalance=21",
        family="G2-A",
        lookback=5,
        skip=5,
        top_k=1,
        rebalance=21,
    )
    with pytest.raises(CampaignError) as excinfo:
        evaluate_validation_candidate(stranger, _validation_bars(), (0, 3, 25))
    assert excinfo.value.code == "CAMPAIGN_CANDIDATE_NOT_IN_FROZEN_GRID"


def test_run_validation_campaign_evaluates_only_shortlist() -> None:
    bars = _validation_bars()
    train_report = {
        "report_sha256": "0" * 64,
        "shortlist": {"G2-A": [FROZEN_A], "G2-B": [], "G2-C": [], "G2-D": []},
    }
    result = run_validation_campaign(train_report, bars, (0, 3, 25))
    assert set(result["candidates"]) == {FROZEN_A}
    assert result["shortlist"] == [FROZEN_A]
    assert result["train_report_sha256"] == "0" * 64
    assert result["survivor"] in (None, FROZEN_A)
    expected_status = STATUS_SURVIVOR if result["survivor"] else STATUS_NO_CREDIBLE
    assert result["status"] == expected_status


def test_run_validation_campaign_rejects_non_frozen_shortlisted_id() -> None:
    bars = _validation_bars()
    train_report = {
        "report_sha256": "0" * 64,
        "shortlist": {"G2-A": ["G2-A|lookback=5|skip=5|top_k=1|rebalance=21"]},
    }
    with pytest.raises(CampaignError) as excinfo:
        run_validation_campaign(train_report, bars, (0, 3, 25))
    assert excinfo.value.code == "VALIDATION_CANDIDATE_NOT_IN_FROZEN_GRID"


def test_frozen_candidate_by_id_round_trips_binding() -> None:
    for candidate_id in (FROZEN_A, FROZEN_B, FROZEN_C, FROZEN_D):
        candidate = frozen_candidate_by_id(candidate_id)
        # The reconstruction must bind to the frozen grid entry.
        from investment_tracker.quant.generation2.campaign import assert_frozen_candidate

        assert assert_frozen_candidate(candidate)["candidate_id"] == candidate_id


# ---------------------------------------------------------------------------
# Seal + verify round-trip
# ---------------------------------------------------------------------------


def test_seal_and_verify_round_trip(tmp_path: object) -> None:
    bars = _validation_bars()
    train_report = {
        "report_sha256": "1" * 64,
        "shortlist": {"G2-A": [FROZEN_A], "G2-B": [FROZEN_B]},
    }
    result = run_validation_campaign(train_report, bars, (0, 3, 25))
    root = pathlib.Path(tmp_path) / "validation"
    payload = seal_validation_report(result, root, friction_cases=(0, 3, 25))
    assert payload["schema_version"] == VALIDATION_SCHEMA
    assert payload["grid_manifest_sha256"] == grid_manifest_sha256()
    assert payload["train_report_sha256"] == "1" * 64
    assert payload["shortlist"] == [FROZEN_A, FROZEN_B]
    assert payload["survivor"] == result["survivor"]

    verified = verify_validation_report(root / REPORT_NAME)
    assert verified["report_sha256"] == payload["report_sha256"]
    assert verified["survivor"] == payload["survivor"]
    assert verified["status"] == payload["status"]

    # Duplicate seal fails closed.
    with pytest.raises(CampaignError) as excinfo:
        seal_validation_report(result, root, friction_cases=(0, 3, 25))
    assert excinfo.value.code == "VALIDATION_REPORT_EXISTS"


def test_verify_detects_tamper(tmp_path: object) -> None:
    bars = _validation_bars()
    train_report = {
        "report_sha256": "1" * 64,
        "shortlist": {"G2-A": [FROZEN_A], "G2-B": []},
    }
    result = run_validation_campaign(train_report, bars, (0, 3, 25))
    root = pathlib.Path(tmp_path) / "validation"
    seal_validation_report(result, root, friction_cases=(0, 3, 25))
    report = root / REPORT_NAME
    tampered = json.loads(report.read_text(encoding="utf-8"))
    tampered["candidates"][0]["friction_cases"]["3"]["sharpe"]["value"] = 99.0
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_validation_report(report)
    assert excinfo.value.code == "VALIDATION_REPORT_TAMPERED"


def test_verify_detects_forced_survivor(tmp_path: object) -> None:
    # A report whose survivor does not match the frozen ordering is tampered.
    bars = _validation_bars()
    train_report = {
        "report_sha256": "1" * 64,
        "shortlist": {"G2-A": [FROZEN_A], "G2-B": [FROZEN_B]},
    }
    result = run_validation_campaign(train_report, bars, (0, 3, 25))
    root = pathlib.Path(tmp_path) / "validation"
    payload = seal_validation_report(result, root, friction_cases=(0, 3, 25))
    report = root / REPORT_NAME
    tampered = json.loads(report.read_text(encoding="utf-8"))
    # Swap the survivor to the *other* shortlisted candidate (if two exist).
    other = [cid for cid in tampered["shortlist"] if cid != payload["survivor"]]
    if other and payload["survivor"] is not None:
        tampered["survivor"] = other[0]
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_validation_report(report)
    assert excinfo.value.code == "VALIDATION_REPORT_TAMPERED"


# ---------------------------------------------------------------------------
# Real-cache end-to-end (skipped when the cache is absent)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not REAL_NORMALIZED_ROOT.is_dir(), reason="real Phase-3 normalized cache not available")
def test_real_cache_validation_end_to_end_is_deterministic() -> None:
    boundary = load_research_boundary(REAL_CACHE, REAL_CACHE)
    bars = boundary.validation_bars()
    assert set(bars) == set(RESEARCH_SYMBOLS)
    train_report = verify_train_report(COMMITTED_TRAIN_REPORT)
    result = run_validation_campaign(train_report, bars, friction_cases=(0, 3, 25))
    # Determinism: an identical re-run yields byte-identical evidence.
    rerun = run_validation_campaign(train_report, bars, friction_cases=(0, 3, 25))
    assert json.dumps(result["candidates"], sort_keys=True) == json.dumps(
        rerun["candidates"], sort_keys=True
    )
    for record in result["candidates"].values():
        for case in record["friction_cases"].values():
            assert case["replay_error"] is None
            assert case["replay_sha256"] is not None
            assert case["session_count"] > 0


def test_committed_validation_report_verifies() -> None:
    if not COMMITTED_VALIDATION_REPORT.is_file():
        pytest.skip("committed VALIDATION campaign report not sealed yet")
    payload = verify_validation_report(COMMITTED_VALIDATION_REPORT)
    assert payload["schema_version"] == VALIDATION_SCHEMA
    assert payload["grid_manifest_sha256"] == grid_manifest_sha256()
    expected_ids = {entry["candidate_id"] for entry in FROZEN_ENTRIES}
    assert {record["candidate_id"] for record in payload["candidates"]} <= expected_ids
    # Survivor, if present, must be a shortlisted candidate.
    if payload["survivor"] is not None:
        assert payload["survivor"] in payload["shortlist"]
