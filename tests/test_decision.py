from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from investment_tracker.decision import (
    DecisionRequest, EvidenceHealth, PortfolioRiskPolicy, PortfolioSnapshot,
    RecommendationState, ConfidenceLevel, generate_decision,
)
from investment_tracker.governance import LockedHoldoutError


def healthy(**changes):
    values = dict(market_data_fresh=True, benchmark_aligned=True, no_critical_dq=True,
        canonical_digests_valid=True, snapshot_current=True, versions_match=True,
        calculation_tests_pass=True, breadth_met=True, independent_recalculation_agrees=True,
        phase_b_passed=True, prospective_gate_met=True, operational_healthy=True)
    values.update(changes)
    return EvidenceHealth(**values)


def request(**changes):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = dict(decision_id='d1', asset='URA', as_of_timestamp=now, market_data_cutoff=now,
        signal_state='ACCUMULATE', source_snapshot_id='s1', evidence=healthy(),
        policy=PortfolioRiskPolicy(policy_version='RISK-v1', max_single_position=Decimal('.1'),
            max_theme_exposure=Decimal('.3'), max_correlated_exposure=Decimal('.3'),
            max_aggregate_exposure=Decimal('.8'), minimum_cash_buffer=Decimal('.1')),
        portfolio=PortfolioSnapshot(snapshot_id='p1', as_of_timestamp=now,
            asset_allocation=Decimal('.04'), theme_allocation=Decimal('.1'),
            correlated_allocation=Decimal('.1'), aggregate_exposure=Decimal('.5'),
            cash_allocation=Decimal('.5')))
    values.update(changes)
    return DecisionRequest(**values)


def test_healthy_decision_is_structured_paper_only_and_requires_human():
    result = generate_decision(request())
    assert result.recommendation_state is RecommendationState.CONSIDER_ACCUMULATING
    assert result.confidence_level is ConfidenceLevel.HIGH
    assert result.incremental_policy_room == Decimal('.06')
    assert result.human_approval_required is True
    assert result.decision_status == 'PAPER_ONLY_NOT_PRODUCTION_APPROVED'


@pytest.mark.parametrize('failed', list(healthy().model_dump()))
def test_every_critical_evidence_failure_abstains(failed):
    result = generate_decision(request(evidence=healthy(**{failed: False})))
    assert result.recommendation_state is RecommendationState.ABSTAIN
    assert result.confidence_level is ConfidenceLevel.UNAVAILABLE
    assert failed in result.confidence_basis


def test_missing_policy_and_limit_violation_fail_closed():
    assert generate_decision(request(policy=None)).recommendation_state is RecommendationState.ABSTAIN
    over = request().portfolio.model_copy(update={'asset_allocation': Decimal('.11')})
    result = generate_decision(request(portfolio=over))
    assert result.portfolio_risk_status == 'VIOLATION'
    assert result.recommendation_state is RecommendationState.ABSTAIN


def test_locked_holdout_is_rejected_at_input_boundary():
    with pytest.raises(ValidationError, match="locked replacement holdout"):
        request(asset='HACK')
