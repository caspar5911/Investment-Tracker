"""REPLAY-v3.0 portfolio opportunity selector.

REPLAY-v3.0 inherits the preregistered REPLAY-v2.0 per-asset signal unchanged,
then adds exactly one allocation hypothesis: overlapping cross-asset ACCUMULATE
signals are treated as one portfolio opportunity. The selector chooses only the
strongest contemporaneous relative-strength candidate and then enforces a
20-benchmark-session global cooldown.

The selector uses only information available on completed signal day t.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Sequence

from .governance import assert_symbol_allowed

REPLAY_V3_VERSION = "REPLAY-v3.0"
GLOBAL_COOLDOWN_SESSIONS = 20


@dataclass(frozen=True)
class EligibleOpportunity:
    asset: str
    signal_date: date
    relative_strength_spread: Decimal
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class SelectedOpportunity:
    asset: str
    signal_date: date
    relative_strength_spread: Decimal
    benchmark_session_index: int


def select_cluster_aware_opportunities(
    opportunities: Iterable[EligibleOpportunity],
    benchmark_sessions: Sequence[date],
) -> list[SelectedOpportunity]:
    """Select one opportunity per global 20-session independence window.

    Frozen rule:
    1. Inputs contain only assets whose REPLAY-v2.0 state is ACCUMULATE.
    2. Group eligible candidates by completed signal date.
    3. If several candidates occur on the same date, select the asset with the
       highest (asset_ret20 - SPY_ret20). Exact ties use lexical asset order.
    4. After a selection at benchmark index i, no later opportunity may be
       selected until index i + 20.
    5. No future candidate strength is inspected when making a selection.
    """

    sessions=list(benchmark_sessions)
    if sessions != sorted(set(sessions)):
        raise ValueError("benchmark_sessions must be unique and increasing")
    index={day:i for i,day in enumerate(sessions)}

    grouped: dict[date,list[EligibleOpportunity]]={}
    for row in opportunities:
        asset=assert_symbol_allowed(row.asset)
        if row.dq_status != "CLEAN":
            continue
        if row.signal_date not in index:
            raise ValueError(f"signal date absent from benchmark calendar: {row.signal_date}")
        grouped.setdefault(row.signal_date,[]).append(
            EligibleOpportunity(
                asset=asset,
                signal_date=row.signal_date,
                relative_strength_spread=row.relative_strength_spread,
                dq_status=row.dq_status,
            )
        )

    selected=[]
    next_allowed=0
    for signal_date in sorted(grouped):
        position=index[signal_date]
        if position < next_allowed:
            continue
        winner=sorted(
            grouped[signal_date],
            key=lambda row: (-row.relative_strength_spread, row.asset),
        )[0]
        selected.append(
            SelectedOpportunity(
                asset=winner.asset,
                signal_date=winner.signal_date,
                relative_strength_spread=winner.relative_strength_spread,
                benchmark_session_index=position,
            )
        )
        next_allowed=position + GLOBAL_COOLDOWN_SESSIONS
    return selected
