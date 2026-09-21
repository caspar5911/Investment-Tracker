"""Tests for the Generation-2 TRAIN campaign runner (C3, campaign.py).

Pins:
- content-addressed canonical JSON encoding (sorted keys, compact separators);
- frozen-grid binding enforcement (identity + coordinates must match C1);
- per-candidate multi-friction evidence records with stable replay hashes;
- the frozen TRAIN eligibility rules and lexicographic shortlisting (<= 3 per
  family, <= 12 total);
- exclusive seal + self-verifying report (tamper detection, duplicate seal
  rejection, shortlist consistency);
- a real-cache smoke slice (skipped when the cache is absent).
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from investment_tracker.quant.generation2 import campaign
from investment_tracker.quant.generation2.campaign import (
    CampaignError,
    REPORT_NAME,
    TRAIN_CAMPAIGN_SCHEMA,
    canonical_bytes,
    content_sha256,
    evaluate_candidate,
    run_train_campaign,
    seal_train_campaign,
    shortlist_candidates,
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
    load_research_boundary,
)

REAL_CACHE = campaign._repo_root() / "data" / "cache"
REAL_NORMALIZED_ROOT = REAL_CACHE / "phase3" / "normalized" / "sha256"
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


def _synthetic_bars(n: int = 1000) -> dict[str, pd.DataFrame]:
    index = pd.bdate_range("2015-01-01", periods=n, tz="UTC")
    bars: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(RESEARCH_SYMBOLS):
        values = [100.0 + 0.01 * i + 0.05 * offset for i in range(n)]
        bars[symbol] = pd.DataFrame({"open": values, "close": values}, index=index)
    return bars


def _short_frictions() -> tuple[int, ...]:
    return (0, 3, 25)


# ---------------------------------------------------------------------------
# Canonical encoding
# ---------------------------------------------------------------------------


def test_canonical_bytes_are_sorted_compact_and_deterministic() -> None:
    payload = {"b": 1, "a": [1, 2], "c": None}
    assert canonical_bytes(payload) == b'{"a":[1,2],"b":1,"c":null}'
    assert content_sha256(payload) == hashlib.sha256(
        b'{"a":[1,2],"b":1,"c":null}'
    ).hexdigest()
    assert content_sha256(payload) == content_sha256(dict(payload))


# ---------------------------------------------------------------------------
# Binding enforcement
# ---------------------------------------------------------------------------


def test_evaluate_candidate_rejects_binding_mismatch() -> None:
    bars = _synthetic_bars()
    mismatched = GridCandidate(
        candidate_id=FROZEN_A,
        family="G2-A",
        lookback=63,
        skip=0,
        top_k=2,  # grid entry says top_k=1
        rebalance=21,
    )
    with pytest.raises(CampaignError) as excinfo:
        evaluate_candidate(mismatched, bars, friction_cases=_short_frictions())
    assert excinfo.value.code == "CAMPAIGN_CANDIDATE_BINDING_INVALID"


def test_run_train_campaign_rejects_unknown_candidate_id() -> None:
    bars = _synthetic_bars()
    stranger = GridCandidate(
        candidate_id="G2-Z|lookback=63|skip=0|top_k=1|rebalance=21",
        family="G2-Z",
        lookback=63,
        skip=0,
        top_k=1,
        rebalance=21,
    )
    with pytest.raises(CampaignError) as excinfo:
        run_train_campaign(bars, [stranger])
    assert excinfo.value.code == "CAMPAIGN_CANDIDATE_NOT_IN_FROZEN_GRID"


def test_run_train_campaign_rejects_duplicate_candidates() -> None:
    bars = _synthetic_bars()
    entry = _candidate(FROZEN_A)
    with pytest.raises(CampaignError) as excinfo:
        run_train_campaign(bars, [entry, entry])
    assert excinfo.value.code == "CAMPAIGN_DUPLICATE_CANDIDATE"


# ---------------------------------------------------------------------------
# Synthetic campaign + seal round-trip
# ---------------------------------------------------------------------------


def test_synthetic_full_campaign_seal_and_verify(tmp_path: object) -> None:
    import pathlib

    bars = _synthetic_bars()
    candidates = [_candidate(c) for c in (FROZEN_A, FROZEN_B, FROZEN_C, FROZEN_D)]
    evidence = run_train_campaign(
        bars, candidates, friction_cases=_short_frictions(), initial_cash=100_000.0
    )
    assert set(evidence) == {FROZEN_A, FROZEN_B, FROZEN_C, FROZEN_D}

    record = evidence[FROZEN_A]
    assert record["candidate"] == _candidate(FROZEN_A).to_manifest_dict()
    assert record["target_count"] > 0
    assert set(record["friction_cases"]) == {"0", "3", "25"}
    for case in record["friction_cases"].values():
        assert case["replay_error"] is None
        assert case["replay_sha256"] is not None
        assert len(case["replay_sha256"]) == 64
        assert case["session_count"] > 0
        for metric in (
            "total_return",
            "cagr",
            "sharpe",
            "sortino",
            "annualized_one_way_turnover",
            "rolling_12m_positive_fraction",
            "max_drawdown",
            "calmar",
        ):
            assert set(case[metric]) == {"status", "value", "reason"}

    # Determinism: re-running yields byte-identical evidence.
    rerun = run_train_campaign(
        bars, candidates, friction_cases=_short_frictions(), initial_cash=100_000.0
    )
    assert json.dumps(evidence, sort_keys=True) == json.dumps(rerun, sort_keys=True)

    root = pathlib.Path(tmp_path) / "campaign"
    payload = seal_train_campaign(evidence, root, friction_cases=_short_frictions())
    assert payload["schema_version"] == TRAIN_CAMPAIGN_SCHEMA
    assert payload["status"] == "TRAIN_SEALED_BEFORE_VALIDATION"
    assert payload["grid_manifest_sha256"] == grid_manifest_sha256()
    assert payload["candidate_count"] == 4

    verified = verify_train_report(root / REPORT_NAME)
    assert verified["candidate_count"] == 4
    assert verified["shortlist"] == shortlist_candidates(evidence)

    # Duplicate seal fails closed.
    with pytest.raises(CampaignError) as excinfo:
        seal_train_campaign(evidence, root, friction_cases=_short_frictions())
    assert excinfo.value.code == "CAMPAIGN_REPORT_EXISTS"

    # Tampering fails verification.
    report = root / REPORT_NAME
    tampered = json.loads(report.read_text(encoding="utf-8"))
    tampered["candidates"][0]["friction_cases"]["3"]["sharpe"]["value"] = 99.0
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_train_report(report)
    assert excinfo.value.code == "CAMPAIGN_REPORT_TAMPERED"


def test_seal_requires_report_root_writable_and_creates_dir(tmp_path: object) -> None:
    import pathlib

    bars = _synthetic_bars()
    evidence = run_train_campaign(
        bars, [_candidate(FROZEN_A)], friction_cases=_short_frictions()
    )
    root = pathlib.Path(tmp_path) / "nested" / "campaign"
    payload = seal_train_campaign(evidence, root, friction_cases=_short_frictions())
    assert (root / REPORT_NAME).is_file()
    assert payload["report_sha256"] == verify_train_report(root / REPORT_NAME)["report_sha256"]


# ---------------------------------------------------------------------------
# Shortlisting (frozen lexicographic order)
# ---------------------------------------------------------------------------


def _fake_evidence(candidate_id: str, family: str, **metrics) -> dict:
    def metric(status: str, value):
        return {"status": status, "value": value, "reason": "OK" if status == "AVAILABLE" else "X"}

    sharpe = metric("AVAILABLE", metrics.get("sharpe")) if "sharpe" in metrics else metric("UNKNOWN", None)
    cagr = metric("AVAILABLE", metrics.get("cagr")) if "cagr" in metrics else metric("UNKNOWN", None)
    turnover = (
        metric("AVAILABLE", metrics.get("turnover"))
        if "turnover" in metrics
        else metric("UNKNOWN", None)
    )
    return {
        "candidate_id": candidate_id,
        "family": family,
        "target_count": 3,
        "friction_cases": {
            "3": {
                "friction_bps": 3,
                "replay_error": None,
                "replay_sha256": "0" * 64,
                "session_count": 100,
                "total_return": metric("AVAILABLE", 0.2),
                "cagr": cagr,
                "sharpe": sharpe,
                "sortino": metric("AVAILABLE", 1.0),
                "annualized_one_way_turnover": turnover,
                "rolling_12m_positive_fraction": metric("UNKNOWN", None),
                "max_drawdown": metric("AVAILABLE", 0.1),
                "calmar": metric("UNKNOWN", None),
                "exposure_invariant_passes": True,
            },
            "25": {
                "friction_bps": 25,
                "replay_error": None,
                "replay_sha256": "1" * 64,
                "session_count": 100,
                "total_return": metric("AVAILABLE", 0.1),
                "cagr": cagr,
                "sharpe": sharpe,
                "sortino": metric("AVAILABLE", 1.0),
                "annualized_one_way_turnover": turnover,
                "rolling_12m_positive_fraction": metric("UNKNOWN", None),
                "max_drawdown": metric("AVAILABLE", 0.1),
                "calmar": metric("UNKNOWN", None),
                "exposure_invariant_passes": True,
            },
        },
        "eligible": metrics.get("eligible", True),
        "disqualification_reasons": list(metrics.get("reasons", ())),
    }


def test_shortlist_applies_frozen_lexicographic_order_and_family_cap() -> None:
    evidence = {
        # sharpe 4.0 -> first regardless of the rest.
        "A3": _fake_evidence("A3", "G2-A", sharpe=4.0, cagr=0.05, turnover=9.0),
        # sharpe tie 3.0: cagr 0.15 beats 0.10.
        "A2": _fake_evidence("A2", "G2-A", sharpe=3.0, cagr=0.15, turnover=5.0),
        # sharpe/cagr tie with A1: lower turnover wins.
        "A4": _fake_evidence("A4", "G2-A", sharpe=3.0, cagr=0.10, turnover=0.5),
        "A1": _fake_evidence("A1", "G2-A", sharpe=3.0, cagr=0.10, turnover=1.0),
        # out of top 3.
        "A5": _fake_evidence("A5", "G2-A", sharpe=2.0, cagr=0.30, turnover=0.1),
        # ineligible: never shortlisted.
        "A6": _fake_evidence("A6", "G2-A", eligible=False, reasons=["PRIMARY_SHARPE_UNAVAILABLE_OR_NOT_POSITIVE"]),
        "B1": _fake_evidence("B1", "G2-B", sharpe=1.0, cagr=0.05, turnover=1.0),
        "C1": _fake_evidence("C1", "G2-C", sharpe=1.0, cagr=0.05, turnover=1.0),
        "D1": _fake_evidence("D1", "G2-D", sharpe=1.0, cagr=0.05, turnover=1.0),
    }
    shortlist = shortlist_candidates(evidence)
    assert shortlist["G2-A"] == ["A3", "A2", "A4"]
    assert shortlist["G2-B"] == ["B1"]
    assert shortlist["G2-C"] == ["C1"]
    assert shortlist["G2-D"] == ["D1"]
    assert sum(len(v) for v in shortlist.values()) <= 12
    assert all(len(v) <= 3 for v in shortlist.values())
    assert "A6" not in shortlist["G2-A"]


# ---------------------------------------------------------------------------
# Real-cache smoke slice (skipped when the cache is absent)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not REAL_NORMALIZED_ROOT.is_dir(), reason="real Phase-3 normalized cache not available")
def test_real_cache_slice_is_deterministic_and_well_formed() -> None:
    boundary = load_research_boundary(REAL_CACHE, REAL_CACHE)
    bars = boundary.train_bars()
    assert set(bars) == set(RESEARCH_SYMBOLS)
    candidates = [_candidate(FROZEN_A), _candidate(FROZEN_D)]
    evidence = run_train_campaign(bars, candidates, friction_cases=_short_frictions())
    for record in evidence.values():
        for case in record["friction_cases"].values():
            assert case["replay_error"] is None
            assert case["replay_sha256"] is not None
            assert case["session_count"] > 0
    rerun = run_train_campaign(bars, candidates, friction_cases=_short_frictions())
    assert json.dumps(evidence, sort_keys=True) == json.dumps(rerun, sort_keys=True)


def test_committed_report_verifies_and_matches_grid_manifest() -> None:
    repo_root = campaign._repo_root()
    report_path = repo_root / "data" / "governance" / "generation2-campaign" / REPORT_NAME
    if not report_path.is_file():
        pytest.skip("committed TRAIN campaign report not sealed yet")
    payload = verify_train_report(report_path)
    assert payload["candidate_count"] == len(build_generation2_grid())
    assert payload["grid_manifest_sha256"] == grid_manifest_sha256()
    expected_ids = {entry["candidate_id"] for entry in FROZEN_ENTRIES}
    assert {record["candidate_id"] for record in payload["candidates"]} == expected_ids
    assert payload["shortlist"] == shortlist_candidates(
        {record["candidate_id"]: record for record in payload["candidates"]}
    )
