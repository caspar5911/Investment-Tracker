from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from investment_tracker.quant.phase4.engine.models import PortfolioReplay
from investment_tracker.quant.phase4.gate3.authorities import (
    LaggedReturnRegimeAuthority,
    REGIME_IDS,
    canonical_authority_sha256,
)


FROZEN_REGIME_DEFINITION_SHA256 = "f8f78a3eff8c5785b6da3a8079b4e3d44c6a186459ae180074d9c40b65e4499b"


@dataclass(frozen=True)
class ConditionalRegime:
    regime_id: str
    ending_sessions: tuple[pd.Timestamp, ...]
    return_vector: tuple[float, ...]
    return_observation_count: int
    positive_return_count: int
    positive_return_percentage: float | None
    arithmetic_mean_session_return: float | None
    conditional_compounded_return: float | None
    status: str
    reason: str


@dataclass(frozen=True)
class RegimeAttribution:
    first_session_label: str
    first_session_return: None
    regimes: tuple[ConditionalRegime, ...]


def _conditional_metrics(values: tuple[float, ...]) -> tuple[int, int, float | None, float | None, float | None, str, str]:
    count = len(values)
    positive = sum(value > 0.0 for value in values)
    if count == 0:
        return 0, 0, None, None, None, "UNKNOWN", "NO_RETURN_OBSERVATIONS"
    fraction = positive / count
    mean = math.fsum(values) / count
    compounded = math.prod(1.0 + value for value in values) - 1.0
    if not all(math.isfinite(value) for value in (fraction, mean, compounded)):
        raise ValueError("REGIME_REPLAY_INVALID: conditional summary is nonfinite")
    return count, positive, fraction, mean, compounded, "AVAILABLE", "OK"


def attribute_regime_returns(
    replay: PortfolioReplay,
    authority: LaggedReturnRegimeAuthority,
) -> RegimeAttribution:
    """Partition actual returns from one continuous replay by ending-session label."""

    if not isinstance(replay, PortfolioReplay) or not isinstance(authority, LaggedReturnRegimeAuthority):
        raise ValueError("REGIME_INPUT_INVALID: replay and frozen authority are required")
    if (
        authority.regime_ids != REGIME_IDS
        or canonical_authority_sha256(authority) != FROZEN_REGIME_DEFINITION_SHA256
    ):
        raise ValueError("REGIME_AUTHORITY_INVALID: exact frozen definition or mapping changed")
    sessions = replay.sessions
    returns = replay.daily_returns
    if len(sessions) < 2 or len(returns) != len(sessions) - 1:
        raise ValueError("REGIME_REPLAY_INVALID: no actual scored return vector")
    expected_sessions = tuple(session.strftime("%Y-%m-%d") for session in sessions)
    provided = authority.session_to_regime
    if (
        len(provided) != len(expected_sessions)
        or tuple(session for session, _ in provided) != expected_sessions
        or len(set(session for session, _ in provided)) != len(provided)
        or any(label not in REGIME_IDS for _, label in provided)
    ):
        raise ValueError("REGIME_AUTHORITY_INVALID: frozen mapping is incomplete or altered")
    mapping = dict(provided)
    ending: dict[str, list[pd.Timestamp]] = {regime: [] for regime in REGIME_IDS}
    vectors: dict[str, list[float]] = {regime: [] for regime in REGIME_IDS}
    for session, value in zip(sessions[1:], returns, strict=True):
        numeric = float(value)
        if not math.isfinite(numeric) or numeric <= -1.0:
            raise ValueError("REGIME_REPLAY_INVALID: one-session return is invalid")
        label = mapping[session.strftime("%Y-%m-%d")]
        ending[label].append(session)
        vectors[label].append(numeric)
    if sum(len(vector) for vector in vectors.values()) != len(returns):
        raise ValueError("REGIME_ATTRIBUTION_INVALID: actual return was omitted")

    regimes = []
    for regime_id in REGIME_IDS:
        values = tuple(vectors[regime_id])
        count, positive, fraction, mean, compounded, status, reason = _conditional_metrics(values)
        regimes.append(
            ConditionalRegime(
                regime_id=regime_id,
                ending_sessions=tuple(ending[regime_id]),
                return_vector=values,
                return_observation_count=count,
                positive_return_count=positive,
                positive_return_percentage=fraction,
                arithmetic_mean_session_return=mean,
                conditional_compounded_return=compounded,
                status=status,
                reason=reason,
            )
        )
    return RegimeAttribution(
        first_session_label=mapping[expected_sessions[0]],
        first_session_return=None,
        regimes=tuple(regimes),
    )
