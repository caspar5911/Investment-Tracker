from decimal import Decimal

from investment_tracker.candidate_v3 import V3_VALIDATION_PANEL
from investment_tracker.phase_b_v3 import (
    Replay20, Replay60, SimpleDip20, Status, evaluate_phase_b_v3,
)


def evidence():
    r20=[];r60=[];dips=[]
    for a in V3_VALIDATION_PANEL:
        for i in range(3):
            eid=f"{a}-{i}"
            r20.append(Replay20(eid,a,Decimal("0.02"),Decimal("0.02"),Decimal("0.03"),Decimal("0.002")))
            r60.append(Replay60(eid,a,Decimal("0.01")))
            dips.append(SimpleDip20("D-"+eid,a,Decimal("0.01")))
    return r20,r60,dips


def test_all_frozen_criteria_are_required():
    assert evaluate_phase_b_v3(*evidence()).status==Status.PASS


def test_adverse_primary_result_fails():
    r20,r60,dips=evidence()
    r20=[Replay20(r.episode_id,r.asset,Decimal("-0.001"),r.excess_cash,r.return_net_25bps,r.cash_return) for r in r20]
    report=evaluate_phase_b_v3(r20,r60,dips)
    assert report.status==Status.FAIL
    assert "median20_excess_spy" in report.failures
