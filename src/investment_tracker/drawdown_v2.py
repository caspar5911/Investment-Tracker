"""Prospective CALC-v2.0 max-drawdown convention.

This module must not be used to rewrite CALC-v1.2 historical evidence. It
defines the convention for Candidate v2 evidence recorded after preregistration.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

CALC_V2_VERSION = "CALC-v2.0"
MAX_DRAWDOWN_CONVENTION = "C25_CLOSE_MARKED_ENTRY_OPEN_HIGH_WATER"


def max_drawdown_close_path(
    entry_open: Decimal,
    closes: Iterable[Decimal | None],
    *,
    censored: bool = False,
) -> Decimal | None:
    """Return close-marked peak-to-trough drawdown for one evaluation horizon.

    Frozen Candidate-v2 definition:
    - path starts at executable t+1 entry open with equity/high-water = 1.0;
    - each later mark is split-normalized usable close / entry_open;
    - high-water mark includes the entry open and every prior usable close;
    - drawdown at each mark is mark/high_water - 1;
    - the reported value is the minimum drawdown, in [-1, 0];
    - friction is excluded from this path metric and remains in return_net;
    - MAE/MFE remain separate intraday range metrics;
    - a censored horizon or any unusable/missing close returns UNKNOWN (None).

    This convention resolves DQ-030 only for CALC-v2.0 and later. CALC-v1.2
    historical max_drawdown remains UNKNOWN and must not be backfilled.
    """

    if entry_open <= 0:
        raise ValueError("entry_open must be positive")
    if censored:
        return None

    path = list(closes)
    if not path or any(value is None for value in path):
        return None

    high_water = entry_open
    worst = Decimal(0)
    for close in path:
        assert close is not None
        if close <= 0:
            raise ValueError("close values must be positive")
        if close > high_water:
            high_water = close
        drawdown = close / high_water - Decimal(1)
        if drawdown < worst:
            worst = drawdown
    return worst
