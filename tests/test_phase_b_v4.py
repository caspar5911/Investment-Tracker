from decimal import Decimal

from investment_tracker.phase_b_v4 import (
    Replay20,Replay60,SimpleDip20,Status,evaluate_phase_b_v4,
)


def test_phase_b_v4_pass_requires_positive_oos_and_breadth():
    assets=("QQQ","IWM","MDY","EFA")
    r20=[]
    r60=[]
    dips=[]
    for a in assets:
        for i in range(5):
            eid=f"{a}-{i}"
            r20.append(Replay20(eid,a,Decimal("0.02"),Decimal("0.02"),Decimal("0.03"),Decimal("0.002")))
            r60.append(Replay60(eid,a,Decimal("0.01")))
            dips.append(SimpleDip20(eid+"-d",a,Decimal("0.01")))
    report=evaluate_phase_b_v4(r20,r60,dips)
    assert report.status==Status.PASS


def test_phase_b_v4_fails_negative_primary_median():
    assets=("QQQ","IWM","MDY","EFA")
    r20=[]
    r60=[]
    dips=[]
    for a in assets:
        for i in range(5):
            eid=f"{a}-{i}"
            r20.append(Replay20(eid,a,Decimal("-0.01"),Decimal("0.01"),Decimal("0.03"),Decimal("0.002")))
            r60.append(Replay60(eid,a,Decimal("0.01")))
            dips.append(SimpleDip20(eid+"-d",a,Decimal("-0.02")))
    assert evaluate_phase_b_v4(r20,r60,dips).status==Status.FAIL
