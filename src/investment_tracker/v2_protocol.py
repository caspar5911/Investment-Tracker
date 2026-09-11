from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .governance import assert_symbol_allowed


V2_PROTOCOL_VERSION = "V2-PROTOCOL-v0.1"
MAX_DRAWDOWN_CONVENTION = (
    "close-based gross equity path from t+1 entry open; include entry equity 1.0; "
    "for each in-partition session use close/entry_open; max drawdown is the "
    "minimum equity/previous_peak-1; no intraday low and no friction adjustment"
)
RB09_TIE_CONVENTION = (
    "group all eligible entries sharing the same benchmark session; use their "
    "equal-weight mean outcome as one session observation; then greedily select "
    "session observations in ascending benchmark-session order with the next "
    "entry index at least horizon_sessions after the prior selected index"
)


@dataclass(frozen=True)
class SessionOutcome:
    asset: str
    entry_session_index: int
    excess_spy: Decimal


@dataclass(frozen=True)
class SessionBasket:
    entry_session_index: int
    assets: tuple[str, ...]
    excess_spy: Decimal


def max_drawdown_close_gross(
    entry_open: Decimal,
    horizon_closes: Iterable[Decimal],
) -> Decimal:
    """Deterministic v2 max-drawdown convention.

    Equity starts at 1.0 at the t+1 entry open. Each subsequent point is the
    in-partition session close divided by entry_open. The result is <= 0.
    This intentionally does not use intraday lows or transaction friction.
    """

    if entry_open <= 0:
        raise ValueError("entry_open must be positive")

    peak = Decimal(1)
    worst = Decimal(0)
    for close in horizon_closes:
        if close <= 0:
            raise ValueError("horizon closes must be positive")
        equity = close / entry_open
        if equity > peak:
            peak = equity
        drawdown = equity / peak - Decimal(1)
        if drawdown < worst:
            worst = drawdown
    return worst


def rb09_equal_weight_nonoverlap(
    observations: Iterable[SessionOutcome],
    *,
    horizon_sessions: int = 20,
) -> tuple[SessionBasket, ...]:
    """Resolve cross-proxy same-session ties without choosing a winning asset."""

    if horizon_sessions < 1:
        raise ValueError("horizon_sessions must be positive")

    grouped: dict[int, list[SessionOutcome]] = {}
    for row in observations:
        asset = assert_symbol_allowed(row.asset)
        if row.entry_session_index < 0:
            raise ValueError("entry_session_index must be non-negative")
        if not row.excess_spy.is_finite():
            raise ValueError("excess_spy must be finite")
        grouped.setdefault(row.entry_session_index, []).append(
            SessionOutcome(asset, row.entry_session_index, row.excess_spy)
        )

    baskets: list[SessionBasket] = []
    for index in sorted(grouped):
        rows = grouped[index]
        value = sum((row.excess_spy for row in rows), Decimal(0)) / Decimal(len(rows))
        baskets.append(
            SessionBasket(
                entry_session_index=index,
                assets=tuple(sorted(row.asset for row in rows)),
                excess_spy=value,
            )
        )

    selected: list[SessionBasket] = []
    next_allowed = 0
    for basket in baskets:
        if basket.entry_session_index < next_allowed:
            continue
        selected.append(basket)
        next_allowed = basket.entry_session_index + horizon_sessions
    return tuple(selected)
