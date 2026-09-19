from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import math
from typing import Mapping, Sequence

from investment_tracker.quant.phase4.preregistration.canonical import canonical_sha256


SYMBOLS = ("SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP")
FOLD_IDS = ("FOLD_2019", "FOLD_2020", "FOLD_2021", "FOLD_2022")
REGIME_IDS = (
    "broad_negative_trend",
    "broad_positive_trend",
    "mixed_cross_asset",
)
REGIME_LOOKBACK_SESSIONS = 126


class AuthorityDefinitionError(ValueError):
    """A predeclared fold or regime authority cannot be constructed exactly."""


@dataclass(frozen=True)
class FoldSummary:
    fold_id: str
    first_session: str
    final_session: str
    session_count: int


@dataclass(frozen=True)
class CalendarYearFoldAuthority:
    schema_version: str
    definition: str
    fold_ids: tuple[str, ...]
    folds: tuple[FoldSummary, ...]
    session_to_fold: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class LaggedReturnRegimeAuthority:
    schema_version: str
    algorithm: str
    symbols: tuple[str, ...]
    regime_ids: tuple[str, ...]
    lookback_sessions: int
    numerator_offset: int
    denominator_offset: int
    positive_threshold: int
    negative_threshold: int
    zero_semantics: str
    session_to_regime: tuple[tuple[str, str], ...]


def _validated_sessions(
    sessions: Sequence[str], *, code: str, permitted_years: frozenset[int] | None = None
) -> tuple[str, ...]:
    values = tuple(sessions)
    try:
        parsed = tuple(date.fromisoformat(item) for item in values)
    except (TypeError, ValueError) as exc:
        raise AuthorityDefinitionError(f"{code}: sessions must be ISO dates") from exc
    if not values or len(set(values)) != len(values) or parsed != tuple(sorted(parsed)):
        raise AuthorityDefinitionError(f"{code}: sessions must be nonempty, unique, ordered")
    if permitted_years is not None and {item.year for item in parsed} != permitted_years:
        raise AuthorityDefinitionError(f"{code}: sessions must cover exactly 2019-2022")
    return values


def build_fold_authority(validation_sessions: Sequence[str]) -> CalendarYearFoldAuthority:
    sessions = _validated_sessions(
        validation_sessions,
        code="FOLD_AUTHORITY_INVALID",
        permitted_years=frozenset({2019, 2020, 2021, 2022}),
    )
    grouped: dict[int, list[str]] = {year: [] for year in range(2019, 2023)}
    for session in sessions:
        grouped[date.fromisoformat(session).year].append(session)
    if any(not grouped[year] for year in grouped):
        raise AuthorityDefinitionError("FOLD_AUTHORITY_INVALID: every fold must be nonempty")
    folds = tuple(
        FoldSummary(
            fold_id=f"FOLD_{year}",
            first_session=grouped[year][0],
            final_session=grouped[year][-1],
            session_count=len(grouped[year]),
        )
        for year in range(2019, 2023)
    )
    mapping = tuple((session, f"FOLD_{date.fromisoformat(session).year}") for session in sessions)
    if tuple(item.fold_id for item in folds) != FOLD_IDS or len(mapping) != len(sessions):
        raise AuthorityDefinitionError("FOLD_AUTHORITY_INVALID: fold mapping is incomplete")
    return CalendarYearFoldAuthority(
        schema_version="PHASE4-GATE3-FOLD-AUTHORITY-v1",
        definition="UTC_CALENDAR_YEAR",
        fold_ids=FOLD_IDS,
        folds=folds,
        session_to_fold=mapping,
    )


def _required_close(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuthorityDefinitionError("REGIME_INPUT_INVALID: required close is not numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise AuthorityDefinitionError("REGIME_INPUT_INVALID: required close must be finite and positive")
    return result


def build_regime_authority(
    all_sessions: Sequence[str],
    close_by_symbol: Mapping[str, Sequence[float]],
    validation_sessions: Sequence[str],
) -> LaggedReturnRegimeAuthority:
    sessions = _validated_sessions(all_sessions, code="REGIME_INPUT_INVALID")
    validation = _validated_sessions(validation_sessions, code="REGIME_INPUT_INVALID")
    if tuple(close_by_symbol) != SYMBOLS or set(close_by_symbol) != set(SYMBOLS):
        raise AuthorityDefinitionError("REGIME_INPUT_INVALID: symbol population or order mismatch")
    if any(len(tuple(close_by_symbol[symbol])) != len(sessions) for symbol in SYMBOLS):
        raise AuthorityDefinitionError("REGIME_INPUT_INVALID: close vectors must align with sessions")
    positions = {session: index for index, session in enumerate(sessions)}
    if any(session not in positions for session in validation):
        raise AuthorityDefinitionError("REGIME_INPUT_INVALID: validation session is absent")

    mapping: list[tuple[str, str]] = []
    for session in validation:
        position = positions[session]
        if position < 127:
            raise AuthorityDefinitionError(
                "REGIME_HISTORY_INSUFFICIENT: 126-session lagged history is unavailable"
            )
        positive_count = 0
        negative_count = 0
        for symbol in SYMBOLS:
            values = close_by_symbol[symbol]
            numerator = _required_close(values[position - 1])
            denominator = _required_close(values[position - 127])
            lagged_return = numerator / denominator - 1.0
            if lagged_return > 0.0:
                positive_count += 1
            elif lagged_return < 0.0:
                negative_count += 1
        if positive_count >= 6:
            regime = "broad_positive_trend"
        elif negative_count >= 6:
            regime = "broad_negative_trend"
        else:
            regime = "mixed_cross_asset"
        mapping.append((session, regime))

    if len(mapping) != len(validation) or len({item[0] for item in mapping}) != len(validation):
        raise AuthorityDefinitionError("REGIME_INPUT_INVALID: regime mapping is incomplete")
    return LaggedReturnRegimeAuthority(
        schema_version="PHASE4-GATE3-REGIME-AUTHORITY-v1",
        algorithm="LAGGED_126_SESSION_EIGHT_ASSET_SIGN_BREADTH",
        symbols=SYMBOLS,
        regime_ids=REGIME_IDS,
        lookback_sessions=REGIME_LOOKBACK_SESSIONS,
        numerator_offset=-1,
        denominator_offset=-127,
        positive_threshold=6,
        negative_threshold=6,
        zero_semantics="NEITHER_POSITIVE_NOR_NEGATIVE",
        session_to_regime=tuple(mapping),
    )


def authority_payload(authority: object) -> dict[str, object]:
    if not isinstance(authority, (CalendarYearFoldAuthority, LaggedReturnRegimeAuthority)):
        raise TypeError("unsupported authority type")
    return asdict(authority)


def canonical_authority_sha256(authority: object) -> str:
    return canonical_sha256(authority_payload(authority))


__all__ = (
    "FOLD_IDS",
    "REGIME_IDS",
    "SYMBOLS",
    "AuthorityDefinitionError",
    "CalendarYearFoldAuthority",
    "LaggedReturnRegimeAuthority",
    "authority_payload",
    "build_fold_authority",
    "build_regime_authority",
    "canonical_authority_sha256",
)
