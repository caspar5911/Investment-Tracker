from datetime import date,timedelta
from decimal import Decimal

from investment_tracker.replay_v3 import (
    EligibleOpportunity,
    select_cluster_aware_opportunities,
)


def cal(n=100):
    start=date(2027,1,1)
    return [start+timedelta(days=i) for i in range(n)]


def test_same_day_selects_highest_relative_strength():
    c=cal()
    rows=[
        EligibleOpportunity("QQQ",c[5],Decimal("0.03")),
        EligibleOpportunity("IWM",c[5],Decimal("0.01")),
    ]
    selected=select_cluster_aware_opportunities(rows,c)
    assert [(x.asset,x.signal_date) for x in selected]==[("QQQ",c[5])]


def test_exact_tie_is_lexical_and_order_independent():
    c=cal()
    rows=[
        EligibleOpportunity("QQQ",c[5],Decimal("0.02")),
        EligibleOpportunity("IWM",c[5],Decimal("0.02")),
    ]
    first=select_cluster_aware_opportunities(rows,c)
    second=select_cluster_aware_opportunities(reversed(rows),c)
    assert first==second
    assert first[0].asset=="IWM"


def test_global_cooldown_is_twenty_benchmark_sessions():
    c=cal()
    rows=[
        EligibleOpportunity("QQQ",c[5],Decimal("0.03")),
        EligibleOpportunity("IWM",c[24],Decimal("0.10")),
        EligibleOpportunity("MDY",c[25],Decimal("0.01")),
    ]
    selected=select_cluster_aware_opportunities(rows,c)
    assert [x.signal_date for x in selected]==[c[5],c[25]]


def test_quarantined_candidate_cannot_win():
    c=cal()
    rows=[
        EligibleOpportunity("QQQ",c[5],Decimal("0.99"),"QUARANTINED"),
        EligibleOpportunity("IWM",c[5],Decimal("0.01")),
    ]
    assert select_cluster_aware_opportunities(rows,c)[0].asset=="IWM"
