from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from typing import Iterable, Mapping


@dataclass(frozen=True)
class CandidateConfiguration:
    candidate_id: str
    family: str
    parameters: dict[str, int | float]


class CandidateGenerator:
    def __init__(self, candidates: Iterable[CandidateConfiguration]) -> None:
        self._candidates = tuple(candidates)

    def __iter__(self):
        return iter(self._candidates)

    def __len__(self) -> int:
        return len(self._candidates)

    @classmethod
    def from_parameter_grid(
        cls,
        family: str,
        grid: Mapping[str, Iterable[int | float]],
    ) -> "CandidateGenerator":
        if not family:
            raise ValueError("family is required")
        keys = tuple(sorted(grid))
        dimensions = [tuple(sorted(set(grid[key]))) for key in keys]
        if not keys or any(not values for values in dimensions):
            raise ValueError("parameter grid dimensions must not be empty")
        candidates: list[CandidateConfiguration] = []
        for values in product(*dimensions):
            parameters = dict(zip(keys, values))
            payload = json.dumps(
                {"family": family, "parameters": parameters},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            candidates.append(
                CandidateConfiguration(
                    candidate_id=f"{family}-{sha256(payload).hexdigest()[:16]}",
                    family=family,
                    parameters=parameters,
                )
            )
        return cls(candidates)


def default_generators() -> dict[str, CandidateGenerator]:
    allocations = [0.25, 0.5, 1.0]
    return {
        "trend": CandidateGenerator.from_parameter_grid(
            "trend",
            {"fast_window": [15, 20, 25], "slow_window": [40, 50, 60], "allocation": allocations},
        ),
        "momentum": CandidateGenerator.from_parameter_grid(
            "momentum", {"lookback": [63, 126, 252], "allocation": allocations}
        ),
        "trend_momentum": CandidateGenerator.from_parameter_grid(
            "trend_momentum",
            {
                "fast_window": [15, 20, 25],
                "slow_window": [40, 50, 60],
                "momentum_lookback": [63, 126, 252],
                "allocation": allocations,
            },
        ),
        "risk_managed_trend": CandidateGenerator.from_parameter_grid(
            "risk_managed_trend",
            {
                "trend_window": [100, 150, 200],
                "volatility_window": [20, 40, 60],
                "target_volatility": [0.08, 0.10, 0.12],
                "maximum_exposure": allocations,
            },
        ),
    }
