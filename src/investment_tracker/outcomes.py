from __future__ import annotations

from datetime import date
from collections.abc import Iterable

from .governance import PHASE_A_END, PHASE_B_END

MAE_MFE_USABLE = "USABLE"
MAE_MFE_UNKNOWN = "UNKNOWN"
_ALLOWED_FRICTION_BPS = {0, 10, 25}


def horizon_return(entry_open: float, horizon_close: float) -> float:
    if entry_open <= 0:
        raise ValueError("entry_open must be positive")
    return horizon_close / entry_open - 1


def apply_friction(gross_return: float, round_trip_bps: int) -> float:
    if round_trip_bps not in _ALLOWED_FRICTION_BPS:
        raise ValueError("round-trip friction must be one of 0, 10, 25 bps")
    return gross_return - round_trip_bps / 10_000


def cash_hurdle(entry_date: date, horizon_date: date, annual_rate: float = 0.0325) -> float:
    elapsed_days = (horizon_date - entry_date).days
    if elapsed_days < 0:
        raise ValueError("horizon_date must be on or after entry_date")
    return (1 + annual_rate) ** (elapsed_days / 365) - 1


def is_censored(horizon_close_date: date, phase: str) -> bool:
    normalized = phase.strip().upper()
    if normalized == "PHASE_A":
        return horizon_close_date > PHASE_A_END
    if normalized == "PHASE_B":
        return horizon_close_date > PHASE_B_END
    raise ValueError("phase must be PHASE_A or PHASE_B")


def range_metrics_status(range_usable_flags: Iterable[bool]) -> str:
    return MAE_MFE_USABLE if all(range_usable_flags) else MAE_MFE_UNKNOWN
