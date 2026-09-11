"""Strict Candidate-v5 Phase-B gate, frozen before v5 panel history."""

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Iterable
from .candidate_v5 import V5_VALIDATION_PANEL
from .governance import assert_symbol_allowed

PHASE_B_V5_VERSION="PHASEB-v4.0"
MIN_MATURED_20D=20
MIN_ADEQUATELY_SAMPLED_PROXIES=4
MIN_EPISODES_PER_PROXY=3

class Status(StrEnum):
    PASS="PASS"; FAIL="FAIL"; INCONCLUSIVE="INCONCLUSIVE"

@dataclass(frozen=True)
class Replay20:
    episode_id:str; asset:str; excess_spy:Decimal; excess_cash:Decimal
    return_net_25bps:Decimal; cash_return:Decimal; dq_status:str="CLEAN"

@dataclass(frozen=True)
class Replay60:
    episode_id:str; asset:str; excess_spy:Decimal; dq_status:str="CLEAN"

@dataclass(frozen=True)
class SimpleDip20:
    episode_id:str; asset:str; excess_spy:Decimal; dq_status:str="CLEAN"

@dataclass(frozen=True)
class Report:
    version:str; status:Status; failures:tuple[str,...]
    matured20_count:int; matured60_count:int
    adequately_sampled_proxy_count:int; nonnegative_proxy_count:int
    median20_excess_spy:Decimal|None; median20_excess_cash:Decimal|None
    median60_excess_spy:Decimal|None; median20_net25:Decimal|None
    median20_cash_hurdle:Decimal|None
    simple_dip20_median_excess_spy:Decimal|None

def _median(values):
    x=sorted(values)
    if not x: raise ValueError("median requires values")
    m=len(x)//2
    return x[m] if len(x)%2 else (x[m-1]+x[m])/Decimal(2)

def _asset(value:str)->str:
    s=assert_symbol_allowed(value)
    if s not in V5_VALIDATION_PANEL:
        raise ValueError(f"asset outside Candidate-v5 panel: {s}")
    return s

def evaluate_phase_b_v5(r20:Iterable[Replay20],r60:Iterable[Replay60],dips20:Iterable[SimpleDip20])->Report:
    a=[Replay20(r.episode_id,_asset(r.asset),r.excess_spy,r.excess_cash,r.return_net_25bps,r.cash_return,r.dq_status) for r in r20 if r.dq_status=="CLEAN"]
    b=[Replay60(r.episode_id,_asset(r.asset),r.excess_spy,r.dq_status) for r in r60 if r.dq_status=="CLEAN"]
    d=[SimpleDip20(r.episode_id,_asset(r.asset),r.excess_spy,r.dq_status) for r in dips20 if r.dq_status=="CLEAN"]
    by=defaultdict(list)
    for r in a: by[r.asset].append(r.excess_spy)
    adequate={k:v for k,v in by.items() if len(v)>=MIN_EPISODES_PER_PROXY}
    missing=[]
    if len(a)<MIN_MATURED_20D: missing.append("matured20_count")
    if len(adequate)<MIN_ADEQUATELY_SAMPLED_PROXIES: missing.append("adequately_sampled_proxy_count")
    if not b: missing.append("matured60_count")
    if not d: missing.append("simple_dip20_count")
    m20s=_median(r.excess_spy for r in a) if a else None
    m20c=_median(r.excess_cash for r in a) if a else None
    m60=_median(r.excess_spy for r in b) if b else None
    mnet=_median(r.return_net_25bps for r in a) if a else None
    mcash=_median(r.cash_return for r in a) if a else None
    mdip=_median(r.excess_spy for r in d) if d else None
    nonneg=sum(1 for vals in adequate.values() if _median(vals)>=0)
    if missing:
        return Report(PHASE_B_V5_VERSION,Status.INCONCLUSIVE,tuple(missing),len(a),len(b),len(adequate),nonneg,m20s,m20c,m60,mnet,mcash,mdip)
    failures=[]
    if m20s is None or m20s<=0: failures.append("median20_excess_spy")
    if m20c is None or m20c<=0: failures.append("median20_excess_cash")
    if m60 is None or m60<0: failures.append("median60_excess_spy")
    if nonneg*2<=len(adequate): failures.append("cross_proxy_breadth")
    if mnet is None or mcash is None or mnet<=mcash: failures.append("friction_survival")
    if mdip is None or m20s is None or m20s<mdip: failures.append("simple_dip_complexity_value")
    return Report(PHASE_B_V5_VERSION,Status.FAIL if failures else Status.PASS,tuple(failures),len(a),len(b),len(adequate),nonneg,m20s,m20c,m60,mnet,mcash,mdip)
