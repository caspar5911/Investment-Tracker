import pytest

from investment_tracker.quant.phase5.artifacts import seal_evaluation
from investment_tracker.quant.phase5.conclusion import classify_phase5


def _metrics():
    return {
        "total_return": 0.5,
        "benchmark_excess_return": 0.1,
        "sharpe": 0.8,
        "sortino": 1.1,
        "annualized_one_way_turnover": 5.0,
        "average_gross_exposure": 0.7,
        "maximum_gross_exposure": 1.0,
        "all_session_exposures_valid": True,
        "bootstrap_lower_endpoint": 0.0,
        "max_drawdown": None,
        "calmar": None,
        "dsr": None,
        "pbo": None,
    }


def test_supported_requires_all_frozen_applicable_conditions():
    result = classify_phase5(
        identity_ok=True,
        reconciliation={"status": "MATCH"},
        equivalence={"status": "MATCH"},
        primary=_metrics(),
        friction_25={**_metrics(), "total_return": 0.3},
    )
    assert result["status"] == "PHASE5_DURABILITY_SUPPORTED"


def test_missing_independent_evidence_abstains():
    result = classify_phase5(
        identity_ok=True,
        reconciliation={"status": "UNKNOWN", "reason": "missing"},
        equivalence={"status": "MATCH"},
        primary=_metrics(),
        friction_25={**_metrics(), "total_return": 0.3},
    )
    assert result["status"] == "PHASE5_UNKNOWN_ABSTAIN"


def test_complete_negative_hard_condition_contradicts():
    primary = _metrics()
    primary["benchmark_excess_return"] = -0.01
    result = classify_phase5(
        identity_ok=True,
        reconciliation={"status": "MATCH"},
        equivalence={"status": "MATCH"},
        primary=primary,
        friction_25={**_metrics(), "total_return": 0.3},
    )
    assert result["status"] == "PHASE5_DURABILITY_CONTRADICTED"


def test_unknown_evaluation_cannot_be_sealed(tmp_path):
    with pytest.raises(ValueError, match="PHASE5_SEAL_REQUIRES_DECISION_GRADE_EVALUATION"):
        seal_evaluation(
            tmp_path,
            {
                "status": "PHASE5_UNKNOWN_ABSTAIN",
                "reasons": ["INDEPENDENT_SOURCE_EVIDENCE_INCOMPLETE"],
                "safety": {},
            },
            source_revision="a" * 40,
            spec_content_sha256="b" * 64,
        )

    assert not list(tmp_path.rglob("record.json"))
