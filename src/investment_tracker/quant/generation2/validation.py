"""Generation-2 VALIDATION campaign runner (C4).

Evaluates ONLY the preregistered TRAIN shortlist (<= 12 candidates) on the
frozen VALIDATION window (due sessions 2019-01-01..2022-12-31) with full
causal warm-up retained, applies the frozen VALIDATION pass criteria, selects
at most one survivor by the frozen ordering, and seals the result into a
self-verifying, content-addressed report.

Governance invariants enforced here (fail-closed):

- only candidates that bind to the frozen grid and appear in the verified
  TRAIN report's shortlist may be evaluated; no parameters, ranking criteria,
  or family definitions may change after VALIDATION begins;
- the full frozen pass criteria are applied; if none pass the campaign
  terminates with ``NO_CREDIBLE_GENERATION2_CANDIDATE``;
- the sealed report is written exclusively (``VALIDATION_REPORT_EXISTS``) and
  every verification recomputes the content hash, the candidate bindings, and
  the survivor selection (``VALIDATION_REPORT_TAMPERED`` on any divergence).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from investment_tracker.quant.generation2.campaign import (
    CampaignError,
    assert_frozen_candidate,
    build_friction_cases,
    content_sha256,
    canonical_bytes,
)
from investment_tracker.quant.generation2.grid import (
    GridCandidate,
    INITIAL_CASH,
    REQUIRED_FRICTION_CASES_BPS,
    build_generation2_grid,
    grid_manifest_sha256,
)
from investment_tracker.quant.generation2.research_boundary import (
    VALIDATION_END,
    VALIDATION_START,
)
from investment_tracker.quant.generation2.strategy import build_targets

MAX_SHORTLIST = 12
ROLLING_12M_POSITIVE_FRACTION_MIN = 0.50
PRIMARY_CASE_KEY = "3"
FRICTION_25BP_CASE_KEY = "25"

VALIDATION_SCHEMA = "GENERATION2-VALIDATION-v1"
STATUS_SURVIVOR = "VALIDATION_SURVIVOR_SELECTED"
STATUS_NO_CREDIBLE = "NO_CREDIBLE_GENERATION2_CANDIDATE"
REPORT_NAME = "validation-report.json"

_FAMILIES = ("G2-A", "G2-B", "G2-C", "G2-D")

# Decision-critical metrics: none may be UNKNOWN for a candidate to pass.
_DECISION_CRITICAL_METRICS = (
    "total_return",
    "cagr",
    "sharpe",
    "sortino",
    "rolling_12m_positive_fraction",
    "max_drawdown",
)

# Frozen survivor ordering (preregistration "VALIDATION procedure").
SURVIVOR_SELECTION_ORDER = (
    "higher VALIDATION Sharpe",
    "higher VALIDATION CAGR",
    "smaller max-drawdown magnitude",
    "lower annualized one-way turnover",
    "ascending candidate_id",
)

__all__ = [
    "MAX_SHORTLIST",
    "REPORT_NAME",
    "ROLLING_12M_POSITIVE_FRACTION_MIN",
    "STATUS_NO_CREDIBLE",
    "STATUS_SURVIVOR",
    "SURVIVOR_SELECTION_ORDER",
    "VALIDATION_SCHEMA",
    "assess_pass",
    "build_validation_payload",
    "build_validation_targets",
    "evaluate_validation_candidate",
    "frozen_candidate_by_id",
    "load_shortlist",
    "run_validation_campaign",
    "select_survivor",
    "seal_validation_report",
    "verify_validation_report",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def frozen_candidate_by_id(candidate_id: str) -> GridCandidate:
    """Reconstruct the frozen grid candidate for ``candidate_id``.

    Unknown ids fail closed with ``VALIDATION_CANDIDATE_NOT_IN_FROZEN_GRID``.
    """
    for candidate in build_generation2_grid():
        if candidate.candidate_id == candidate_id:
            return candidate
    raise CampaignError(
        "VALIDATION_CANDIDATE_NOT_IN_FROZEN_GRID",
        f"{candidate_id!r} is not part of the frozen generation-2 grid",
    )


def build_validation_targets(
    candidate: GridCandidate,
    bars: dict[str, pd.DataFrame],
) -> tuple:
    """Decision targets restricted to the frozen VALIDATION due window.

    The full 2014+ frames provide causal warm-up; only due sessions inside
    [2019-01-01, 2022-12-31] are scheduled, so the ledger starts at the first
    in-window due session.
    """
    return build_targets(
        candidate,
        bars,
        due_from=pd.Timestamp(VALIDATION_START, tz="UTC"),
        due_until=pd.Timestamp(VALIDATION_END, tz="UTC"),
    )


def load_shortlist(train_report: dict) -> tuple[str, ...]:
    """Flatten the TRAIN report's shortlist in frozen family order.

    ``train_report`` is the verified TRAIN campaign payload. The shortlist is
    a dict keyed by family (G2-A..G2-D); empty families are omitted and the
    total is capped at ``MAX_SHORTLIST`` (fail-closed).
    """
    shortlist = train_report.get("shortlist")
    if not isinstance(shortlist, dict):
        raise CampaignError(
            "VALIDATION_SHORTLIST_MISSING",
            "the verified TRAIN report carries no usable shortlist",
        )
    ids: list[str] = []
    for family in _FAMILIES:
        for candidate_id in shortlist.get(family, []):
            ids.append(str(candidate_id))
    if len(ids) > MAX_SHORTLIST:
        raise CampaignError(
            "VALIDATION_SHORTLIST_TOO_LARGE",
            f"shortlist has {len(ids)} candidates, maximum {MAX_SHORTLIST}",
        )
    return tuple(ids)


def _metric_positive(metric: dict) -> bool:
    return (
        metric.get("status") == "AVAILABLE"
        and metric.get("value") is not None
        and metric["value"] > 0.0
    )


def _metric_available(metric: dict) -> bool:
    return (
        metric.get("status") == "AVAILABLE"
        and metric.get("value") is not None
    )


def assess_pass(record: dict) -> tuple[bool, list[str]]:
    """Apply the frozen VALIDATION pass criteria to one candidate record.

    Returns ``(passed, reasons)`` where ``reasons`` lists every stable
    fail-closed code violated. The decision-critical metrics are read from the
    primary-friction (3 bps) case; the 25 bps case supplies its total return.
    """
    reasons: list[str] = []
    cases = record.get("friction_cases", {})
    primary = cases.get(PRIMARY_CASE_KEY, {})
    case_25 = cases.get(FRICTION_25BP_CASE_KEY, {})

    if primary.get("replay_error") is not None:
        reasons.append("VALIDATION_PRIMARY_REPLAY_FAILED")

    for name in ("total_return", "cagr", "sharpe", "sortino"):
        if not _metric_positive(primary.get(name, {})):
            reasons.append(f"VALIDATION_{name.upper()}_UNAVAILABLE_OR_NOT_POSITIVE")

    if primary.get("exposure_invariant_passes") is not True:
        reasons.append("VALIDATION_EXPOSURE_INVARIANT_FAILED")

    if not _metric_positive(case_25.get("total_return", {})):
        reasons.append(
            "VALIDATION_FRICTION_25BP_TOTAL_RETURN_UNAVAILABLE_OR_NOT_POSITIVE"
        )

    rolling = primary.get("rolling_12m_positive_fraction", {})
    if not _metric_available(rolling):
        reasons.append("VALIDATION_ROLLING_12M_POSITIVE_FRACTION_UNAVAILABLE")
    elif rolling["value"] < ROLLING_12M_POSITIVE_FRACTION_MIN:
        reasons.append("VALIDATION_ROLLING_12M_POSITIVE_FRACTION_BELOW_050")

    if not _metric_available(primary.get("max_drawdown", {})):
        reasons.append("VALIDATION_MAX_DRAWDOWN_UNAVAILABLE")

    for name in _DECISION_CRITICAL_METRICS:
        if primary.get(name, {}).get("status") == "UNKNOWN":
            reasons.append(f"VALIDATION_{name.upper()}_UNKNOWN")

    return (not reasons, reasons)


def evaluate_validation_candidate(
    candidate: GridCandidate,
    bars: dict[str, pd.DataFrame],
    friction_cases: tuple[int, ...] = REQUIRED_FRICTION_CASES_BPS,
    initial_cash: float = INITIAL_CASH,
) -> dict:
    """Evaluate one frozen candidate on the VALIDATION window.

    The candidate must still bind to the frozen grid entry; the shared
    ``build_friction_cases`` primitive guarantees byte-identical case payloads
    with the TRAIN campaign for the same replay.
    """
    assert_frozen_candidate(candidate)
    targets = build_validation_targets(candidate, bars)
    cases = build_friction_cases(bars, targets, friction_cases, initial_cash)
    record = {
        "candidate_id": candidate.candidate_id,
        "family": candidate.family,
        "candidate": candidate.to_manifest_dict(),
        "target_count": len(targets),
        "friction_cases": cases,
    }
    passed, reasons = assess_pass(record)
    record["pass"] = passed
    record["pass_reasons"] = reasons
    return record


def _sort_metric(record: dict, name: str, *, prefer_high: bool) -> float:
    """Metric value for frozen-ordering comparisons.

    Callers negate the result themselves for "higher is better" axes, so an
    unavailable metric returns ``-inf`` on a prefer-high axis (worst after
    negation) and ``inf`` on a lower-is-better axis (worst as-is).
    """
    metric = record["friction_cases"][PRIMARY_CASE_KEY][name]
    if not (metric["status"] == "AVAILABLE" and metric["value"] is not None):
        return float("-inf") if prefer_high else float("inf")
    return float(metric["value"])


def select_survivor(records: dict[str, dict]) -> str | None:
    """Choose exactly one survivor among passing candidates by the frozen ordering.

    (1) higher VALIDATION Sharpe; (2) higher VALIDATION CAGR;
    (3) smaller max-drawdown magnitude; (4) lower annualized one-way turnover;
    (5) ascending candidate_id. Returns ``None`` when no candidate passes.

    Pass status comes from the ``pass`` flag recorded by
    :func:`evaluate_validation_candidate`; the sealed report's content hash
    protects that flag from tampering, and :func:`verify_validation_report`
    recomputes the survivor from the sealed records.
    """
    ranked: list[tuple[float, float, float, float, str]] = []
    for candidate_id, record in records.items():
        if not record.get("pass"):
            continue
        mdd = _sort_metric(record, "max_drawdown", prefer_high=False)
        turnover = _sort_metric(record, "annualized_one_way_turnover", prefer_high=False)
        ranked.append(
            (
                -_sort_metric(record, "sharpe", prefer_high=True),
                -_sort_metric(record, "cagr", prefer_high=True),
                mdd,
                turnover,
                candidate_id,
            )
        )
    if not ranked:
        return None
    ranked.sort()
    return ranked[0][4]


def run_validation_campaign(
    train_report: dict,
    bars: dict[str, pd.DataFrame],
    friction_cases: tuple[int, ...] = REQUIRED_FRICTION_CASES_BPS,
    initial_cash: float = INITIAL_CASH,
) -> dict:
    """Evaluate the frozen shortlist on the VALIDATION window and pick a survivor."""
    shortlist = load_shortlist(train_report)
    records: dict[str, dict] = {}
    for candidate_id in shortlist:
        candidate = frozen_candidate_by_id(candidate_id)
        records[candidate_id] = evaluate_validation_candidate(
            candidate, bars, friction_cases, initial_cash
        )
    survivor = select_survivor(records)
    status = STATUS_SURVIVOR if survivor is not None else STATUS_NO_CREDIBLE
    return {
        "train_report_sha256": train_report.get("report_sha256"),
        "shortlist": list(shortlist),
        "candidates": records,
        "survivor": survivor,
        "status": status,
    }


def build_validation_payload(
    result: dict,
    friction_cases: tuple[int, ...] = REQUIRED_FRICTION_CASES_BPS,
) -> dict:
    """Assemble the self-hashing VALIDATION report payload (no file writes).

    This is the single authority for the VALIDATION report content: sealing
    and independent reproduction (C6) both consume it so they can never
    diverge. Candidate records are stored in shortlist order.
    """
    shortlist = result["shortlist"]
    for candidate_id in shortlist:
        assert_frozen_candidate(frozen_candidate_by_id(candidate_id))
    payload: dict = {
        "schema_version": VALIDATION_SCHEMA,
        "status": result["status"],
        "grid_manifest_sha256": grid_manifest_sha256(),
        "train_report_sha256": result["train_report_sha256"],
        "friction_cases_bps": [int(bps) for bps in friction_cases],
        "shortlist": list(shortlist),
        "survivor": result["survivor"],
        "survivor_selection_order": list(SURVIVOR_SELECTION_ORDER),
        "candidates": [result["candidates"][cid] for cid in shortlist],
    }
    payload["report_sha256"] = content_sha256(payload)
    return payload


def seal_validation_report(
    result: dict,
    root: Path | str,
    friction_cases: tuple[int, ...] = REQUIRED_FRICTION_CASES_BPS,
) -> dict:
    """Seal the VALIDATION report exclusively under ``root``.

    The report is canonical-JSON, self-hashing (``report_sha256`` is computed
    over the payload without that key) and refuses to overwrite an existing
    report. Candidate records are stored in shortlist order.
    """
    root = Path(root)
    report_path = root / REPORT_NAME
    if report_path.exists():
        raise CampaignError(
            "VALIDATION_REPORT_EXISTS",
            f"a VALIDATION report already exists at {report_path}",
        )
    payload = build_validation_payload(result, friction_cases)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with report_path.open("xb") as handle:
            handle.write(canonical_bytes(payload))
    except FileExistsError as exc:
        raise CampaignError(
            "VALIDATION_REPORT_EXISTS",
            f"a VALIDATION report already exists at {report_path}",
        ) from exc
    return payload


def verify_validation_report(path: Path | str) -> dict:
    """Verify a sealed VALIDATION report; fail closed on any divergence."""
    payload = json.loads(Path(path).read_bytes().decode("utf-8"))
    claimed = payload.pop("report_sha256", None)
    if claimed is None or content_sha256(payload) != claimed:
        raise CampaignError(
            "VALIDATION_REPORT_TAMPERED",
            f"report content hash does not match {Path(path)}",
        )
    if payload.get("schema_version") != VALIDATION_SCHEMA:
        raise CampaignError(
            "VALIDATION_REPORT_TAMPERED",
            f"schema_version is {payload.get('schema_version')!r}, expected {VALIDATION_SCHEMA!r}",
        )
    shortlist = payload.get("shortlist")
    records = payload.get("candidates")
    if not isinstance(shortlist, list) or not isinstance(records, list):
        raise CampaignError(
            "VALIDATION_REPORT_TAMPERED",
            "shortlist/candidates must be lists",
        )
    if len(records) != len(shortlist):
        raise CampaignError(
            "VALIDATION_REPORT_TAMPERED",
            "candidate count does not match the shortlist",
        )
    evidence: dict[str, dict] = {}
    for record in records:
        candidate_id = record.get("candidate_id")
        try:
            frozen = frozen_candidate_by_id(candidate_id)
        except CampaignError as exc:
            raise CampaignError(
                "VALIDATION_REPORT_TAMPERED",
                f"candidate {candidate_id!r} is not part of the frozen generation-2 grid",
            ) from exc
        if record.get("candidate") != frozen.to_manifest_dict():
            raise CampaignError(
                "VALIDATION_REPORT_TAMPERED",
                f"candidate binding for {candidate_id!r} does not match the frozen grid",
            )
        evidence[candidate_id] = record
    if [record.get("candidate_id") for record in records] != list(shortlist):
        raise CampaignError(
            "VALIDATION_REPORT_TAMPERED",
            "candidate order does not match the shortlist",
        )
    recomputed_survivor = select_survivor(evidence)
    if payload.get("survivor") != recomputed_survivor:
        raise CampaignError(
            "VALIDATION_REPORT_TAMPERED",
            "stored survivor does not match the frozen selection rule",
        )
    expected_status = (
        STATUS_SURVIVOR if recomputed_survivor is not None else STATUS_NO_CREDIBLE
    )
    if payload.get("status") != expected_status:
        raise CampaignError(
            "VALIDATION_REPORT_TAMPERED",
            "stored status does not match the survivor outcome",
        )
    payload["report_sha256"] = claimed
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run and seal the generation-2 VALIDATION campaign.")
    parser.add_argument(
        "--evidence-root",
        default=str(_repo_root() / "data" / "governance" / "generation2-campaign"),
        help="directory containing the sealed TRAIN report and receiving the VALIDATION report",
    )
    parser.add_argument(
        "--cache-root",
        default=str(_repo_root() / "data" / "cache"),
        help="local Phase-3 cache root used to load the research boundary",
    )
    args = parser.parse_args(argv)

    from investment_tracker.quant.generation2.campaign import (
        REPORT_NAME as TRAIN_REPORT_NAME,
        verify_train_report,
    )
    from investment_tracker.quant.generation2.research_boundary import load_research_boundary

    evidence_root = Path(args.evidence_root)
    train_report = verify_train_report(evidence_root / TRAIN_REPORT_NAME)
    boundary = load_research_boundary(Path(args.cache_root), Path(args.cache_root))
    bars = boundary.validation_bars()
    result = run_validation_campaign(train_report, bars)
    payload = seal_validation_report(result, evidence_root)
    print(f"schema_version={payload['schema_version']}")
    print(f"status={payload['status']}")
    print(f"train_report_sha256={payload['train_report_sha256']}")
    print(f"grid_manifest_sha256={payload['grid_manifest_sha256']}")
    print(f"shortlist_size={len(payload['shortlist'])}")
    print(f"survivor={payload['survivor']}")
    print(f"report_sha256={payload['report_sha256']}")
    for candidate_id in payload["shortlist"]:
        record = result["candidates"][candidate_id]
        marker = "PASS" if record["pass"] else "FAIL"
        print(f"  {marker} {candidate_id} reasons={','.join(record['pass_reasons']) or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
