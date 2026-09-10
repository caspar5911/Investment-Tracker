from investment_tracker.leakage_audit import LeakageEvidence, audit_leakage


def clean(**changes):
    values = dict(
        candidate_frozen_before_phase_b=True, phase_b_excluded_from_tuning=True,
        signals_use_completed_day_t_only=True, execution_is_t_plus_one_open=True,
        c22_warmup_only=True, original_contaminated_holdout_excluded=True,
        queried_symbols=frozenset({"URA", "SPY"}),
    )
    values.update(changes)
    return LeakageEvidence(**values)


def test_leakage_audit_requires_every_boundary():
    for field in (
        "candidate_frozen_before_phase_b", "phase_b_excluded_from_tuning",
        "signals_use_completed_day_t_only", "execution_is_t_plus_one_open",
        "c22_warmup_only", "original_contaminated_holdout_excluded",
    ):
        report = audit_leakage(clean(**{field: False}))
        assert not report.passed
        assert field in report.failures


def test_locked_holdout_exposure_is_a_contamination_failure():
    report = audit_leakage(clean(queried_symbols=frozenset({"URA", "HACK"})))
    assert not report.passed
    assert report.failures == ("locked_holdout_access:HACK",)
