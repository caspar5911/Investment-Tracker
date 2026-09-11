from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def bootstrap_interval(
    values: Sequence[float],
    *,
    draws: int = 2000,
    seed: int = 0,
    lower_percentile: float = 5.0,
    upper_percentile: float = 95.0,
) -> tuple[float, float]:
    observations = np.asarray(values, dtype=float)
    if observations.size < 2 or not np.isfinite(observations).all():
        raise ValueError("bootstrap requires at least two finite observations")
    if draws < 100:
        raise ValueError("bootstrap draws must be at least 100")
    if not 0 <= lower_percentile < upper_percentile <= 100:
        raise ValueError("bootstrap percentiles are invalid")
    rng = np.random.default_rng(seed)
    samples = rng.choice(observations, size=(draws, observations.size), replace=True)
    medians = np.median(samples, axis=1)
    return (
        float(np.percentile(medians, lower_percentile)),
        float(np.percentile(medians, upper_percentile)),
    )
