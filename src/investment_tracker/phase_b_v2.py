"""Pre-registered Candidate-v2 strict OOS acceptance criteria.

This module evaluates only evidence from the fixed Candidate-v2 validation
panel. It must not be used to reinterpret Candidate-v1 Phase B.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from .candidate_v2 import V2_VALIDATION_PANEL
from .governance import assert_symbol_allowed

PHASE_B_V2_VERSION = "PHASEB-v2.0"
MIN_MATURED_20D = 20
MIN_ADEQUATELY_SAMPLED_PROXIES = 4
MIN_EPISODES_PER_PROXY = 3


class PhaseBV2Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class Replay20Observation:
    episode_id: str
    asset: str
    excess_spy: Decimal
    excess_cash: Decimal
    return_net_25bps: Decimal
    cash_return: Decimal
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class Replay60Observation:
    episode_id: str
    asset: str
    excess_spy: Decimal
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class SimpleDip20Observation:
    episode_id: str
    asset: str
    excess_spy: Decimal
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class PhaseBV2Report:
    version: str
    status: PhaseBV2Status
    matured20_count: int
    matured60_count: int
    adequately_sampled_proxy_count: int
    nonnegative_proxy_count: int
    median20_excess_spy: Decimal | None
    median20_excess_cash: Decimal | None
    median60_excess_spy: Decimal | None
    median20_net25: Decimal | None
    median20_cash_hurdle: Decimal | None
    simple_dip20_count: int
    simple_dip20_median_excess_spy: Decimal | None
    failures: tuple[str, ...]


def _median(values: Iterable[Decimal]) -> Decimal:
    rows = sorted(values)
    if not rows:
        raise ValueError("median requires at least one value")
    mid = len(rows) // 2
    if len(rows) % 2:
        return rows[mid]
    return (rows[mid - 1] + rows[mid]) / Decimal(2)


def _validate_asset(asset: str) -> str:
    normalized = assert_symbol_allowed(asset)
    if normalized not in V2_VALIDATION_PANEL:
        raise ValueError(f"asset is outside frozen Candidate-v2 validation panel: {normalized}")
    return normalized


def evaluate_phase_b_v2(
    replay20: Iterable[Replay20Observation],
    replay60: Iterable[Replay60Observation],
    simple_dip20: Iterable[SimpleDip20Observation],
) -> PhaseBV2Report:
    """Evaluate strict Candidate-v2 OOS evidence against frozen criteria.

    PASS requires all of:
    - >=20 clean matured 20d REPLAY episodes overall;
    - median 20d excess vs SPY > 0;
    - median 20d excess vs cash > 0;
    - median 60d excess vs SPY >= 0;
    - at least 4 proxies with >=3 matured 20d episodes;
    - >50% of adequately sampled proxies have non-negative median 20d SPY excess;
    - median 25bps net 20d return > median matched cash hurdle;
    - REPLAY median 20d SPY excess >= Simple-Dip median 20d SPY excess.

    Insufficient sample produces INCONCLUSIVE. Once minimum sample exists,
    failure of any performance criterion produces FAIL.
    """

    r20 = []
    for row in replay20:
        asset = _validate_asset(row.asset)
        if not row.episode_id:
            raise ValueError("episode_id is required")
        if row.dq_status == "CLEAN":
            r20.append(
                Replay20Observation(
                    row.episode_id,
                    asset,
                    row.excess_spy,
                    row.excess_cash,
                    row.return_net_25bps,
                    row.cash_return,
                    row.dq_status,
                )
            )

    r60 = []
    for row in replay60:
        asset = _validate_asset(row.asset)
        if not row.episode_id:
            raise ValueError("episode_id is required")
        if row.dq_status == "CLEAN":
            r60.append(
                Replay60Observation(row.episode_id, asset, row.excess_spy, row.dq_status)
            )

    dips = []
    for row in simple_dip20:
        asset = _validate_asset(row.asset)
        if not row.episode_id:
            raise ValueError("episode_id is required")
        if row.dq_status == "CLEAN":
            dips.append(SimpleDip20Observation(row.episode_id, asset, row.excess_spy, row.dq_status))

    by_asset: dict[str, list[Decimal]] = defaultdict(list)
    for row in r20:
        by_asset[row.asset].append(row.excess_spy)
    adequately_sampled = {
        asset: values
        for asset, values in by_asset.items()
        if len(values) >= MIN_EPISODES_PER_PROXY
    }

    sample_failures = []
    if len(r20) < MIN_MATURED_20D:
        sample_failures.append("matured20_count")
    if len(adequately_sampled) < MIN_ADEQUATELY_SAMPLED_PROXIES:
        sample_failures.append("adequately_sampled_proxy_count")
    if not r60:
        sample_failures.append("matured60_count")
    if not dips:
        sample_failures.append("simple_dip20_count")

    med20_spy = _median(row.excess_spy for row in r20) if r20 else None
    med20_cash = _median(row.excess_cash for row in r20) if r20 else None
    med60_spy = _median(row.excess_spy for row in r60) if r60 else None
    med20_net25 = _median(row.return_net_25bps for row in r20) if r20 else None
    med20_cash_hurdle = _median(row.cash_return for row in r20) if r20 else None
    dip_med = _median(row.excess_spy for row in dips) if dips else None

    nonnegative_proxy_count = sum(
        1 for values in adequately_sampled.values() if _median(values) >= 0
    )

    if sample_failures:
        return PhaseBV2Report(
            version=PHASE_B_V2_VERSION,
            status=PhaseBV2Status.INCONCLUSIVE,
            matured20_count=len(r20),
            matured60_count=len(r60),
            adequately_sampled_proxy_count=len(adequately_sampled),
            nonnegative_proxy_count=nonnegative_proxy_count,
            median20_excess_spy=med20_spy,
            median20_excess_cash=med20_cash,
            median60_excess_spy=med60_spy,
            median20_net25=med20_net25,
            median20_cash_hurdle=med20_cash_hurdle,
            simple_dip20_count=len(dips),
            simple_dip20_median_excess_spy=dip_med,
            failures=tuple(sample_failures),
        )

    failures = []
    assert med20_spy is not None
    assert med20_cash is not None
    assert med60_spy is not None
    assert med20_net25 is not None
    assert med20_cash_hurdle is not None
    assert dip_med is not None

    if med20_spy <= 0:
        failures.append("median20_excess_spy")
    if med20_cash <= 0:
        failures.append("median20_excess_cash")
    if med60_spy < 0:
        failures.append("median60_excess_spy")
    if nonnegative_proxy_count * 2 <= len(adequately_sampled):
        failures.append("cross_proxy_breadth")
    if med20_net25 <= med20_cash_hurdle:
        failures.append("friction_survival")
    if med20_spy < dip_med:
        failures.append("simple_dip_complexity_value")

    return PhaseBV2Report(
        version=PHASE_B_V2_VERSION,
        status=PhaseBV2Status.FAIL if failures else PhaseBV2Status.PASS,
        matured20_count=len(r20),
        matured60_count=len(r60),
        adequately_sampled_proxy_count=len(adequately_sampled),
        nonnegative_proxy_count=nonnegative_proxy_count,
        median20_excess_spy=med20_spy,
        median20_excess_cash=med20_cash,
        median60_excess_spy=med60_spy,
        median20_net25=med20_net25,
        median20_cash_hurdle=med20_cash_hurdle,
        simple_dip20_count=len(dips),
        simple_dip20_median_excess_spy=dip_med,
        failures=tuple(failures),
    )
