from decimal import Decimal

import pytest

from investment_tracker.phase_b_v2 import (
    PhaseBV2Status,
    Replay20Observation,
    Replay60Observation,
    SimpleDip20Observation,
    evaluate_phase_b_v2,
)


ASSETS = ("XLI", "XLU", "XLB", "XME", "XOP", "IGV", "XSD", "IYT")


def good_evidence():
    r20 = []
    r60 = []
    dips = []
    for i, asset in enumerate(ASSETS):
        for j in range(3):
            episode = f"{asset}-{j}"
            r20.append(
                Replay20Observation(
                    episode,
                    asset,
                    Decimal("0.02"),
                    Decimal("0.025"),
                    Decimal("0.03"),
                    Decimal("0.002"),
                )
            )
            r60.append(
                Replay60Observation(episode, asset, Decimal("0.01"))
            )
            dips.append(
                SimpleDip20Observation(f"DIP-{episode}", asset, Decimal("0.01"))
            )
    return r20, r60, dips


def test_phase_b_v2_passes_only_when_all_preregistered_criteria_pass():
    report = evaluate_phase_b_v2(*good_evidence())
    assert report.status == PhaseBV2Status.PASS
    assert report.matured20_count == 24
    assert report.adequately_sampled_proxy_count == 8
    assert report.nonnegative_proxy_count == 8
    assert report.failures == ()


def test_phase_b_v2_is_inconclusive_below_minimum_episode_sample():
    r20, r60, dips = good_evidence()
    report = evaluate_phase_b_v2(r20[:19], r60[:19], dips[:19])
    assert report.status == PhaseBV2Status.INCONCLUSIVE
    assert "matured20_count" in report.failures


def test_negative_primary_median_is_a_fail_not_an_invitation_to_tune():
    r20, r60, dips = good_evidence()
    r20 = [
        Replay20Observation(
            row.episode_id,
            row.asset,
            Decimal("-0.001"),
            row.excess_cash,
            row.return_net_25bps,
            row.cash_return,
        )
        for row in r20
    ]
    report = evaluate_phase_b_v2(r20, r60, dips)
    assert report.status == PhaseBV2Status.FAIL
    assert "median20_excess_spy" in report.failures


def test_simple_dip_superiority_fails_complexity_value_test():
    r20, r60, dips = good_evidence()
    dips = [
        SimpleDip20Observation(row.episode_id, row.asset, Decimal("0.05"))
        for row in dips
    ]
    report = evaluate_phase_b_v2(r20, r60, dips)
    assert report.status == PhaseBV2Status.FAIL
    assert "simple_dip_complexity_value" in report.failures


def test_panel_substitution_is_rejected():
    r20, r60, dips = good_evidence()
    r20[0] = Replay20Observation(
        "QQQ-1", "QQQ", Decimal("0.1"), Decimal("0.1"), Decimal("0.1"), Decimal("0.002")
    )
    with pytest.raises(ValueError, match="outside frozen Candidate-v2 validation panel"):
        evaluate_phase_b_v2(r20, r60, dips)


def test_locked_holdout_is_rejected_before_evaluation():
    r20, r60, dips = good_evidence()
    r20[0] = Replay20Observation(
        "HACK-1", "HACK", Decimal("0.1"), Decimal("0.1"), Decimal("0.1"), Decimal("0.002")
    )
    with pytest.raises(ValueError, match="locked replacement holdout"):
        evaluate_phase_b_v2(r20, r60, dips)
