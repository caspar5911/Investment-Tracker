from __future__ import annotations


def classify_phase5(
    *,
    identity_ok: bool,
    reconciliation: dict[str, object],
    equivalence: dict[str, object],
    primary: dict[str, object] | None,
    friction_25: dict[str, object] | None,
) -> dict[str, object]:
    if not identity_ok:
        return {"status": "PHASE5_UNKNOWN_ABSTAIN", "reasons": ["IDENTITY_PROOF_MISSING"]}
    if reconciliation.get("status") == "UNKNOWN":
        return {"status": "PHASE5_UNKNOWN_ABSTAIN", "reasons": [str(reconciliation.get("reason"))]}
    if reconciliation.get("status") == "MISMATCH":
        return {"status": "PHASE5_UNKNOWN_ABSTAIN", "reasons": ["INDEPENDENT_SOURCE_DISCREPANCY_UNRESOLVED"]}
    if primary is None or friction_25 is None:
        return {"status": "PHASE5_UNKNOWN_ABSTAIN", "reasons": ["REQUIRED_METRICS_MISSING"]}
    if equivalence.get("status") != "MATCH":
        return {"status": "PHASE5_DURABILITY_CONTRADICTED", "reasons": ["SIGNAL_EQUIVALENCE_MISMATCH"]}
    required_numeric = ("total_return", "benchmark_excess_return", "sharpe", "sortino", "annualized_one_way_turnover", "average_gross_exposure", "bootstrap_lower_endpoint")
    if any(primary.get(field) is None for field in required_numeric):
        return {"status": "PHASE5_UNKNOWN_ABSTAIN", "reasons": ["REQUIRED_APPLICABLE_METRIC_UNKNOWN"]}
    failures: list[str] = []
    if float(primary["total_return"]) <= 0.0:
        failures.append("TOTAL_RETURN_NONPOSITIVE")
    if float(primary["benchmark_excess_return"]) <= 0.0:
        failures.append("BENCHMARK_EXCESS_NONPOSITIVE")
    if float(primary["sharpe"]) <= 0.0:
        failures.append("SHARPE_NONPOSITIVE")
    if float(primary["sortino"]) <= 0.0:
        failures.append("SORTINO_NONPOSITIVE")
    if float(friction_25.get("total_return", -1.0)) <= 0.0:
        failures.append("FRICTION_25BPS_RETURN_NONPOSITIVE")
    turnover = float(primary["annualized_one_way_turnover"])
    if not 0.0 <= turnover <= 12.0:
        failures.append("TURNOVER_OUTSIDE_FROZEN_RANGE")
    average = float(primary["average_gross_exposure"])
    maximum = float(primary.get("maximum_gross_exposure", float("inf")))
    if not 0.0 <= average <= 1.0 or maximum > 1.0 + 1e-12 or primary.get("all_session_exposures_valid") is not True:
        failures.append("LONG_ONLY_EXPOSURE_INVALID")
    if float(primary["bootstrap_lower_endpoint"]) < 0.0:
        failures.append("BOOTSTRAP_LOWER_ENDPOINT_NEGATIVE")
    if primary.get("max_drawdown") is not None or primary.get("calmar") is not None:
        failures.append("DQ030_UNAVAILABLE_METRIC_POPULATED")
    if primary.get("dsr") is not None or primary.get("pbo") is not None:
        failures.append("UNIMPLEMENTED_METRIC_POPULATED")
    if failures:
        return {"status": "PHASE5_DURABILITY_CONTRADICTED", "reasons": failures}
    return {"status": "PHASE5_DURABILITY_SUPPORTED", "reasons": []}
