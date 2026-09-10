from investment_tracker.readiness import WEIGHTS, ReadinessEvidence, score_readiness


def full(**changes):
    values = dict(phase_a=20, robustness=15, phase_b=15, prospective=15,
        portfolio_risk=10, reconciliation=10, operations=10, governance=5,
        phase_a_complete=True, robustness_passed=True, phase_b_passed=True,
        prospective_gate_met=True, critical_controls_clear=True,
        independent_audit_approved=False)
    values.update(changes)
    return ReadinessEvidence(**values)


def test_weights_are_frozen_to_100_and_score_is_non_official_without_audit():
    assert sum(WEIGHTS.values()) == 100
    result = score_readiness(full())
    assert result.capped_score == 100
    assert result.label == 'NON_OFFICIAL_ENGINEERING_EVIDENCE_SCORE'
    assert 'independent_audit_approved' in result.hard_gate_failures


def test_caps_are_applied_without_score_target_tuning():
    result = score_readiness(full(phase_a_complete=False, robustness_passed=False))
    assert result.raw_score == 100
    assert result.capped_score == 69
    assert result.applied_cap == 69
