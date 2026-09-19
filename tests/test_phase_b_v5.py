from decimal import Decimal
from investment_tracker.phase_b_v5 import Replay20,Replay60,SimpleDip20,Status,evaluate_phase_b_v5

def test_v5_phase_b_pass_contract():
    assets=("DIA","IJR","VTI","IWF")
    a=[];b=[];d=[]
    for asset in assets:
        for i in range(5):
            eid=f"{asset}-{i}"
            a.append(Replay20(eid,asset,Decimal("0.02"),Decimal("0.02"),Decimal("0.03"),Decimal("0.002")))
            b.append(Replay60(eid,asset,Decimal("0.01")))
            d.append(SimpleDip20(eid+"-d",asset,Decimal("0.01")))
    assert evaluate_phase_b_v5(a,b,d).status==Status.PASS

def test_v5_phase_b_fails_bad_primary_oos():
    assets=("DIA","IJR","VTI","IWF")
    a=[];b=[];d=[]
    for asset in assets:
        for i in range(5):
            eid=f"{asset}-{i}"
            a.append(Replay20(eid,asset,Decimal("-0.01"),Decimal("0.01"),Decimal("0.03"),Decimal("0.002")))
            b.append(Replay60(eid,asset,Decimal("0.01")))
            d.append(SimpleDip20(eid+"-d",asset,Decimal("-0.02")))
    assert evaluate_phase_b_v5(a,b,d).status==Status.FAIL
