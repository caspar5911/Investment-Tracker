from __future__ import annotations

from typing import Literal


def adverse_fill_price(reference_price: float, side: Literal["BUY", "SELL"], slippage_bps: float) -> float:
    rate = slippage_bps / 10_000.0
    return reference_price * (1.0 + rate if side == "BUY" else 1.0 - rate)


def commission(notional: float, commission_bps: float) -> float:
    return abs(notional) * commission_bps / 10_000.0
