"""Generation-2 TRAIN campaign runner (C3).

Evaluates the exact 162-candidate frozen grid on the TRAIN window only,
records per-candidate, per-friction decision-ledger evidence with stable
content hashes, applies the frozen TRAIN eligibility rules and the frozen
lexicographic shortlist (<= 3 per family, <= 12 total), and seals the result
into a self-verifying, content-addressed report that must be committed before
any VALIDATION data is read (C4).

Governance invariants enforced here (fail-closed):

- candidate identity must match the frozen grid entry byte-for-byte
  (``CAMPAIGN_CANDIDATE_BINDING_INVALID``); unknown or duplicate candidate ids
  are rejected (``CAMPAIGN_CANDIDATE_NOT_IN_FROZEN_GRID`` /
  ``CAMPAIGN_DUPLICATE_CANDIDATE``);
- VALIDATION data is never touched by the TRAIN ranking: the runner only ever
  consumes ``train_bars()`` of the verified research boundary;
- the sealed report is written exclusively (``CAMPAIGN_REPORT_EXISTS`` if one
  already exists) and every verification recomputes the content hash and the
  shortlist (``CAMPAIGN_REPORT_TAMPERED`` on any divergence).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from investment_tracker.quant.generation2.accounting import (
    DecisionError,
    DecisionReplayResult,
    replay_decision_targets,
)
from investment_tracker.quant.generation2.grid import (
    GridCandidate,
    INITIAL_CASH,
    PRIMARY_FRICTION_BPS,
    REQUIRED_FRICTION_CASES_BPS,
    build_generation2_grid,
    canonical_grid_manifest,
    grid_manifest_sha256,
)
from investment_tracker.quant.generation2.performance import summarize
from investment_tracker.quant.generation2.strategy import build_targets

FRICTION_25BP_BPS = 25

TRAIN_CAMPAIGN_SCHEMA = "GENERATION2-TRAIN-CAMPAIGN-v1"
TRAIN_CAMPAIGN_STATUS = "TRAIN_SEALED_BEFORE_VALIDATION"
REPORT_NAME = "train-campaign-report.json"

_METRIC_NAMES = (
    "total_return",
    "cagr",
    "sharpe",
    "sortino",
    "annualized_one_way_turnover",
    "rolling_12m_positive_fraction",
    "max_drawdown",
    "calmar",
)
_FAMILIES = ("G2-A", "G2-B", "G2-C", "G2-D")
_FAMILY_CAP = 3

__all__ = [
    "CampaignError",
    "FRICTION_25BP_BPS",
    "REPORT_NAME",
    "TRAIN_CAMPAIGN_SCHEMA",
    "TRAIN_CAMPAIGN_STATUS",
    "assert_frozen_candidate",
    "build_friction_cases",
    "canonical_bytes",
    "content_sha256",
    "evaluate_candidate",
    "run_train_campaign",
    "seal_train_campaign",
    "shortlist_candidates",
    "verify_train_report",
]


class CampaignError(ValueError):
    """Fail-closed campaign error carrying a stable ``code``."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def canonical_bytes(payload: dict) -> bytes:
    """Canonical byte encoding shared by hashing and materialization."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


def content_sha256(payload: dict) -> str:
    """Content identity of the canonical payload (self-excluding hash)."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _frozen_entries() -> dict[str, dict]:
    return {
        entry["candidate_id"]: entry
        for entry in canonical_grid_manifest()["candidates"]
    }


def _frozen_grid_order() -> tuple[str, ...]:
    return tuple(entry["candidate_id"] for entry in canonical_grid_manifest()["candidates"])


def assert_frozen_candidate(candidate: GridCandidate) -> dict:
    entries = _frozen_entries()
    entry = entries.get(candidate.candidate_id)
    if entry is None:
        raise CampaignError(
            "CAMPAIGN_CANDIDATE_NOT_IN_FROZEN_GRID",
            f"{candidate.candidate_id!r} is not part of the frozen generation-2 grid",
        )
    if candidate.to_manifest_dict() != entry:
        raise CampaignError(
            "CAMPAIGN_CANDIDATE_BINDING_INVALID",
            f"{candidate.candidate_id!r} coordinates do not match the frozen grid entry",
        )
    return entry


def _metric_payload(status: str, value, reason: str) -> dict:
    return {"status": status, "value": value, "reason": reason}


def _failed_case(bps: int) -> dict:
    case: dict = {
        "friction_bps": int(bps),
        "replay_error": None,
        "replay_sha256": None,
        "session_count": 0,
    }
    for name in _METRIC_NAMES:
        case[name] = _metric_payload("UNKNOWN", None, "REPLAY_FAILED")
    case["exposure_invariant_passes"] = False
    return case


def _replay_payload(replay: DecisionReplayResult) -> dict:
    return {
        "schema": replay.schema_version,
        "friction_bps": replay.friction_bps,
        "initial_cash": replay.initial_cash,
        "sessions": [session.isoformat() for session in replay.sessions],
        "states": [
            [
                state.session.isoformat(),
                state.cash,
                state.receivable,
                state.close_equity,
                state.realized_gross_exposure,
                [list(unit) for unit in state.units],
                list(state.pending_orders),
            ]
            for state in replay.states
        ],
        "fills": [
            [
                fill.symbol,
                fill.source_target_id,
                fill.fill_session.isoformat(),
                fill.unadjusted_open,
                fill.units_delta,
                fill.notional,
                fill.friction,
            ]
            for fill in replay.fills
        ],
        "total_turnover": replay.total_turnover,
    }


def _case_payload(bps: int, replay: DecisionReplayResult) -> dict:
    summary = summarize(replay)
    case: dict = {
        "friction_bps": int(bps),
        "replay_error": None,
        "replay_sha256": content_sha256(_replay_payload(replay)),
        "session_count": len(replay.sessions),
    }
    for name in _METRIC_NAMES:
        metric = getattr(summary, name)
        case[name] = _metric_payload(metric.status, metric.value, metric.reason)
    case["exposure_invariant_passes"] = summary.exposure_invariant_passes
    return case


def _positive_available(metric: dict) -> bool:
    return (
        metric["status"] == "AVAILABLE"
        and metric["value"] is not None
        and metric["value"] > 0.0
    )


def _disqualification_reasons(friction_cases: dict[str, dict]) -> list[str]:
    reasons: list[str] = []
    primary = friction_cases.get(str(PRIMARY_FRICTION_BPS))
    if primary is None or primary["replay_error"] is not None:
        reasons.append(f"REPLAY_FAILED_{PRIMARY_FRICTION_BPS}")
    else:
        if not _positive_available(primary["total_return"]):
            reasons.append("PRIMARY_TOTAL_RETURN_UNAVAILABLE_OR_NOT_POSITIVE")
        if not _positive_available(primary["cagr"]):
            reasons.append("PRIMARY_CAGR_UNAVAILABLE_OR_NOT_POSITIVE")
        if not _positive_available(primary["sharpe"]):
            reasons.append("PRIMARY_SHARPE_UNAVAILABLE_OR_NOT_POSITIVE")
        if not primary["exposure_invariant_passes"]:
            reasons.append("EXPOSURE_INVARIANT_FAILED")
    case_25bp = friction_cases.get(str(FRICTION_25BP_BPS))
    if case_25bp is None or case_25bp["replay_error"] is not None:
        reasons.append("FRICTION_25BP_TOTAL_RETURN_UNAVAILABLE_OR_NOT_POSITIVE")
    elif not _positive_available(case_25bp["total_return"]):
        reasons.append("FRICTION_25BP_TOTAL_RETURN_UNAVAILABLE_OR_NOT_POSITIVE")
    return reasons


def build_friction_cases(
    bars: dict[str, pd.DataFrame],
    targets: tuple,
    friction_cases: tuple[int, ...],
    initial_cash: float = INITIAL_CASH,
) -> dict[str, dict]:
    """Run the decision-ledger replay for ``targets`` at every friction case.

    This is the shared case-construction primitive used by both the TRAIN
    campaign and the VALIDATION campaign, so both record byte-identical,
    content-addressed case payloads for a given replay.
    """
    cases: dict[str, dict] = {}
    for bps in friction_cases:
        case = _failed_case(int(bps))
        try:
            replay = replay_decision_targets(
                bars,
                targets,
                friction_bps=int(bps),
                initial_cash=initial_cash,
            )
        except DecisionError as exc:
            case["replay_error"] = str(exc)
        else:
            case = _case_payload(int(bps), replay)
        cases[str(bps)] = case
    return cases


def evaluate_candidate(
    candidate: GridCandidate,
    bars: dict[str, pd.DataFrame],
    friction_cases: tuple[int, ...] = REQUIRED_FRICTION_CASES_BPS,
    initial_cash: float = INITIAL_CASH,
) -> dict:
    """Evaluate one frozen candidate on the TRAIN bars at every friction case."""
    assert_frozen_candidate(candidate)
    targets = build_targets(candidate, bars)
    cases = build_friction_cases(bars, targets, friction_cases, initial_cash)
    reasons = _disqualification_reasons(cases)
    return {
        "candidate_id": candidate.candidate_id,
        "family": candidate.family,
        "candidate": candidate.to_manifest_dict(),
        "target_count": len(targets),
        "friction_cases": cases,
        "eligible": not reasons,
        "disqualification_reasons": reasons,
    }


def run_train_campaign(
    bars: dict[str, pd.DataFrame],
    candidates: tuple[GridCandidate, ...] | list[GridCandidate] | None = None,
    *,
    friction_cases: tuple[int, ...] = REQUIRED_FRICTION_CASES_BPS,
    initial_cash: float = INITIAL_CASH,
) -> dict[str, dict]:
    """Evaluate the full frozen grid (or an explicit subset) on TRAIN bars."""
    grid = tuple(candidates if candidates is not None else build_generation2_grid())
    seen: set[str] = set()
    evidence: dict[str, dict] = {}
    for candidate in grid:
        if candidate.candidate_id in seen:
            raise CampaignError(
                "CAMPAIGN_DUPLICATE_CANDIDATE",
                f"{candidate.candidate_id!r} appears more than once in the campaign",
            )
        seen.add(candidate.candidate_id)
        evidence[candidate.candidate_id] = evaluate_candidate(
            candidate, bars, friction_cases, initial_cash
        )
    return evidence


def _sort_value(metric: dict, *, prefer_high: bool) -> float:
    value = metric["value"]
    if not (metric["status"] == "AVAILABLE" and value is not None):
        return float("-inf") if prefer_high else float("inf")
    return float(value)


def shortlist_candidates(evidence: dict[str, dict]) -> dict[str, list[str]]:
    """Frozen lexicographic TRAIN shortlist: <= 3 per family, <= 12 total.

    Order: (1) higher primary-friction Sharpe; (2) higher primary-friction
    CAGR; (3) lower annualized one-way turnover; (4) ascending candidate_id.
    Only eligible candidates are considered.
    """
    shortlist: dict[str, list[str]] = {family: [] for family in _FAMILIES}
    by_family: dict[str, list[tuple[float, float, float, str]]] = {
        family: [] for family in _FAMILIES
    }
    for record in evidence.values():
        if not record.get("eligible"):
            continue
        family = record["family"]
        case = record["friction_cases"].get(str(PRIMARY_FRICTION_BPS))
        if case is None:
            continue
        key = (
            -_sort_value(case["sharpe"], prefer_high=True),
            -_sort_value(case["cagr"], prefer_high=True),
            _sort_value(case["annualized_one_way_turnover"], prefer_high=False),
            record["candidate_id"],
        )
        by_family[family].append(key)
    for family in _FAMILIES:
        ranked = sorted(by_family[family])
        shortlist[family] = [item[3] for item in ranked[:_FAMILY_CAP]]
    return shortlist


def seal_train_campaign(
    evidence: dict[str, dict],
    root: Path | str,
    friction_cases: tuple[int, ...] = REQUIRED_FRICTION_CASES_BPS,
) -> dict:
    """Seal the TRAIN campaign report exclusively under ``root``.

    The report is canonical-JSON, self-hashing (``report_sha256`` is computed
    over the payload without that key) and refuses to overwrite an existing
    report.
    """
    root = Path(root)
    report_path = root / REPORT_NAME
    if report_path.exists():
        raise CampaignError(
            "CAMPAIGN_REPORT_EXISTS",
            f"a TRAIN campaign report already exists at {report_path}",
        )
    ordered_ids = [cid for cid in _frozen_grid_order() if cid in evidence]
    for candidate_id in evidence:
        if candidate_id not in ordered_ids:
            raise CampaignError(
                "CAMPAIGN_CANDIDATE_NOT_IN_FROZEN_GRID",
                f"{candidate_id!r} is not part of the frozen generation-2 grid",
            )
    payload: dict = {
        "schema_version": TRAIN_CAMPAIGN_SCHEMA,
        "status": TRAIN_CAMPAIGN_STATUS,
        "grid_manifest_sha256": grid_manifest_sha256(),
        "candidate_count": len(evidence),
        "friction_cases_bps": [int(bps) for bps in friction_cases],
        "shortlist": shortlist_candidates(evidence),
        "candidates": [evidence[cid] for cid in ordered_ids],
    }
    payload["report_sha256"] = content_sha256(payload)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with report_path.open("xb") as handle:
            handle.write(canonical_bytes(payload))
    except FileExistsError as exc:
        raise CampaignError(
            "CAMPAIGN_REPORT_EXISTS",
            f"a TRAIN campaign report already exists at {report_path}",
        ) from exc
    return payload


def verify_train_report(path: Path | str) -> dict:
    """Verify a sealed TRAIN campaign report; fail closed on any divergence."""
    payload = json.loads(Path(path).read_bytes().decode("utf-8"))
    claimed = payload.pop("report_sha256", None)
    if claimed is None or content_sha256(payload) != claimed:
        raise CampaignError(
            "CAMPAIGN_REPORT_TAMPERED",
            f"report content hash does not match {Path(path)}",
        )
    records = payload.get("candidates")
    if not isinstance(records, list) or len(records) != payload.get("candidate_count"):
        raise CampaignError(
            "CAMPAIGN_REPORT_TAMPERED",
            "candidate_count does not match the candidate records",
        )
    entries = _frozen_entries()
    evidence: dict[str, dict] = {}
    for record in records:
        candidate_id = record.get("candidate_id")
        entry = entries.get(candidate_id)
        if entry is None or record.get("candidate") != entry:
            raise CampaignError(
                "CAMPAIGN_REPORT_TAMPERED",
                f"candidate binding for {candidate_id!r} does not match the frozen grid",
            )
        evidence[candidate_id] = record
    if payload.get("shortlist") != shortlist_candidates(evidence):
        raise CampaignError(
            "CAMPAIGN_REPORT_TAMPERED",
            "stored shortlist does not match the frozen lexicographic rule",
        )
    payload["report_sha256"] = claimed
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run and seal the generation-2 TRAIN campaign.")
    parser.add_argument(
        "--evidence-root",
        default=str(_repo_root() / "data" / "governance" / "generation2-campaign"),
        help="directory receiving the sealed TRAIN campaign report",
    )
    parser.add_argument(
        "--cache-root",
        default=str(_repo_root() / "data" / "cache"),
        help="local Phase-3 cache root used to load the research boundary",
    )
    args = parser.parse_args(argv)

    from investment_tracker.quant.generation2.research_boundary import load_research_boundary

    boundary = load_research_boundary(Path(args.cache_root), Path(args.cache_root))
    # TRAIN-only: the VALIDATION frames are never materialized during ranking.
    bars = boundary.train_bars()
    evidence = run_train_campaign(bars)
    payload = seal_train_campaign(evidence, Path(args.evidence_root))
    print(f"schema_version={payload['schema_version']}")
    print(f"status={payload['status']}")
    print(f"candidate_count={payload['candidate_count']}")
    print(f"grid_manifest_sha256={payload['grid_manifest_sha256']}")
    print(f"report_sha256={payload['report_sha256']}")
    for family in _FAMILIES:
        print(f"shortlist[{family}]={','.join(payload['shortlist'][family]) or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
