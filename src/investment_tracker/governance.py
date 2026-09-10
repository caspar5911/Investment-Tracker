from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True)
class FrozenVersions:
    tpc: str
    replay: str
    calc: str
    robust: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


FROZEN_VERSIONS = FrozenVersions(
    tpc="TPC-v1.2",
    replay="REPLAY-v1.0",
    calc="CALC-v1.2",
    robust="ROBUST-v1.0",
)

LOCKED_HOLDOUT = frozenset({"HACK", "SOXX", "NLR", "URNM", "GEV"})
PHASE_A_END = date(2023, 12, 31)
PHASE_B_END = date(2025, 9, 7)


class LockedHoldoutError(ValueError):
    pass


def assert_symbol_allowed(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol must not be empty")
    if normalized in LOCKED_HOLDOUT:
        raise LockedHoldoutError(f"locked replacement holdout symbol denied: {normalized}")
    return normalized
