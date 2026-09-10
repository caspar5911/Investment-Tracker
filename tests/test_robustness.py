from decimal import Decimal

import pytest

from investment_tracker.robustness import (
    REQUIRED_PHASE_A,
    RobustObservation,
    RobustnessBlockedError,
    analyze_phase_a,
)


def rows():
    result = []
    for i, asset in enumerate(sorted(REQUIRED_PHASE_A)):
        for friction in (0, 10, 25):
            result.append(RobustObservation(f"{asset}-E1", asset, 20, friction, Decimal(i - friction) / 100, Decimal("0.01"), "PRECLASSIFIED"))
    return result


def states():
    return {asset: "BASELINES_COMPLETE" for asset in REQUIRED_PHASE_A}


def test_fails_closed_before_complete_phase_a():
    incomplete = states()
    incomplete["URA"] = "OUTCOMES_COMPLETE"
    with pytest.raises(RobustnessBlockedError, match="coordinator snapshots.*URA"):
        analyze_phase_a(rows(), incomplete)


def test_report_is_deterministic_and_episode_level():
    first = analyze_phase_a(rows(), states(), bootstrap_draws=40)
    second = analyze_phase_a(reversed(rows()), states(), bootstrap_draws=40)
    assert first == second
    assert first.version == "ROBUST-v1.0"
    assert first.unique_episode_count == 8
    assert set(first.means_by_friction) == {0, 10, 25}
    assert set(first.leave_one_asset_out) == REQUIRED_PHASE_A


def test_quarantine_is_excluded_and_counted():
    supplied = rows() + [RobustObservation("ETN-Q", "ETN", 20, 0, Decimal("99"), Decimal(0), "PRECLASSIFIED", "QUARANTINED")]
    report = analyze_phase_a(supplied, states(), bootstrap_draws=20)
    assert report.quarantined_count == 1
    assert report.observation_count == len(rows())


def test_requires_all_frozen_friction_scenarios():
    with pytest.raises(RobustnessBlockedError, match="0/10/25"):
        analyze_phase_a([row for row in rows() if row.friction_bps != 25], states())


def test_locked_holdout_denied_before_analysis():
    bad = rows() + [RobustObservation("forbidden", "HACK", 20, 0, Decimal(0), Decimal(0), "X")]
    with pytest.raises(ValueError, match="locked replacement holdout"):
        analyze_phase_a(bad, states())
