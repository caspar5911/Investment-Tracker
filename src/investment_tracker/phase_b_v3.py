"""Strict Candidate-v3 Phase-B evaluator, frozen before panel history access."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from .candidate_v3 import V3_VALIDATION_PANEL
from .governance import assert_symbol_allowed

PHASE_B_V3_VERSION = "PHASEB-v2.0"
MIN_MATURED_20D = 20
MIN_ADEQUATELY_SAMPLED_PROXIES = 4
MIN_EPISODES_PER_PROXY = 3


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class Replay20:
    episode_id: str
    asset: str
    excess_spy: Decimal
    excess_cash: Decimal
    return_net_25bps: Decimal
    cash_return: Decimal
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class Replay60:
    episode_id: str
    asset: str
    excess_spy: Decimal
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class SimpleDip20:
    episode_id: str
    asset: str
    excess_spy: Decimal
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class Report:
    version: str
    status: Status
    failures: tuple[str, ...]
    matured20_count: int
    matured60_count: int
    adequately_sampled_proxy_count: int
    nonnegative_proxy_count: int
    median20_excess_spy: Decimal | None
    median20_excess_cash: Decimal | None
    median60_excess_spy: Decimal | None
    median20_net25: Decimal | None
    median20_cash_hurdle: Decimal | None
    simple_dip20_median_excess_spy: Decimal | None


def _median(values):
    rows=sorted(values)
    if not rows:
        raise ValueError("median requires values")
    m=len(rows)//2
    return rows[m] if len(rows)%2 else (rows[m-1]+rows[m])/Decimal(2)


def _asset(value: str) -> str:
    normalized=assert_symbol_allowed(value)
    if normalized not in V3_VALIDATION_PANEL:
        raise ValueError(f"asset is outside frozen Candidate-v3 validation panel: {normalized}")
    return normalized


def evaluate_phase_b_v3(
    replay20: Iterable[Replay20],
    replay60: Iterable[Replay60],
    simple_dip20: Iterable[SimpleDip20],
) -> Report:
    r20=[Replay20(r.episode_id,_asset(r.asset),r.excess_spy,r.excess_cash,r.return_net_25bps,r.cash_return,r.dq_status) for r in replay20 if r.dq_status=="CLEAN"]
    r60=[Replay60(r.episode_id,_asset(r.asset),r.excess_spy,r.dq_status) for r in replay60 if r.dq_status=="CLEAN"]
    dips=[SimpleDip20(r.episode_id,_asset(r.asset),r.excess_spy,r.dq_status) for r in simple_dip20 if r.dq_status=="CLEAN"]
    by=defaultdict(list)
    for r in r20: by[r.asset].append(r.excess_spy)
    adequate={a:v for a,v in by.items() if len(v)>=MIN_EPISODES_PER_PROXY}
    sample=[]
    if len(r20)<MIN_MATURED_20D: sample.append("matured20_count")
    if len(adequate)<MIN_ADEQUATELY_SAMPLED_PROXIES: sample.append("adequately_sampled_proxy_count")
    if not r60: sample.append("matured60_count")
    if not dips: sample.append("simple_dip20_count")
    m20s=_median(r.excess_spy for r in r20) if r20 else None
    m20c=_median(r.excess_cash for r in r20) if r20 else None
    m60=_median(r.excess_spy for r in r60) if r60 else None
    mnet=_median(r.return_net_25bps for r in r20) if r20 else None
    mcash=_median(r.cash_return for r in r20) if r20 else None
    mdip=_median(r.excess_spy for r in dips) if dips else None
    nonneg=sum(1 for v in adequate.values() if _median(v)>=0)
    if sample:
        return Report(PHASE_B_V3_VERSION,Status.INCONCLUSIVE,tuple(sample),len(r20),len(r60),len(adequate),nonneg,m20s,m20c,m60,mnet,mcash,mdip)
    failures=[]
    if m20s is None or m20s<=0: failures.append("median20_excess_spy")
    if m20c is None or m20c<=0: failures.append("median20_excess_cash")
    if m60 is None or m60<0: failures.append("median60_excess_spy")
    if nonneg*2<=len(adequate): failures.append("cross_proxy_breadth")
    if mnet is None or mcash is None or mnet<=mcash: failures.append("friction_survival")
    if mdip is None or m20s is None or m20s<mdip: failures.append("simple_dip_complexity_value")
    return Report(PHASE_B_V3_VERSION,Status.FAIL if failures else Status.PASS,tuple(failures),len(r20),len(r60),len(adequate),nonneg,m20s,m20c,m60,mnet,mcash,mdip)
