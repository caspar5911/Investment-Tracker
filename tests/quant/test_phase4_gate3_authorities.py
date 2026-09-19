from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from investment_tracker.quant.phase4.gate3.authorities import (
    FOLD_IDS,
    REGIME_IDS,
    AuthorityDefinitionError,
    build_fold_authority,
    build_regime_authority,
    canonical_authority_sha256,
)


def _sessions(year: int, count: int = 3) -> tuple[str, ...]:
    return tuple(f"{year}-01-{day:02d}" for day in range(2, 2 + count))


def _regime_fixture(
    signs: tuple[int, ...],
    *,
    prior: float = 100.0,
) -> tuple[tuple[str, ...], dict[str, tuple[float, ...]], tuple[str, ...]]:
    symbols = ("SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP")
    start = date(2018, 6, 1)
    all_sessions = tuple((start + timedelta(days=offset)).isoformat() for offset in range(127))
    assert len(all_sessions) == 127
    validation = ("2019-01-02",)
    sequence = all_sessions + validation
    closes: dict[str, tuple[float, ...]] = {}
    for symbol, sign in zip(symbols, signs, strict=True):
        values = [prior] * len(sequence)
        values[-2] = prior + sign
        values[-1] = 999_999.0
        closes[symbol] = tuple(values)
    return sequence, closes, validation


def test_calendar_year_folds_are_exact_complete_and_deterministic() -> None:
    validation = tuple(
        session
        for year in range(2019, 2023)
        for session in _sessions(year)
    )
    authority = build_fold_authority(validation)

    assert authority.fold_ids == FOLD_IDS
    assert tuple(item.fold_id for item in authority.folds) == FOLD_IDS
    assert tuple(item.session_count for item in authority.folds) == (3, 3, 3, 3)
    assert tuple(item.first_session for item in authority.folds) == (
        "2019-01-02", "2020-01-02", "2021-01-02", "2022-01-02"
    )
    assert tuple(item.final_session for item in authority.folds) == (
        "2019-01-04", "2020-01-04", "2021-01-04", "2022-01-04"
    )
    assert tuple(session for session, _ in authority.session_to_fold) == validation
    assert len(set(session for session, _ in authority.session_to_fold)) == len(validation)
    assert authority == build_fold_authority(validation)


@pytest.mark.parametrize(
    ("signs", "expected"),
    [
        ((1, 1, 1, 1, 1, 1, 0, 0), "broad_positive_trend"),
        ((1, 1, 1, 1, 1, 1, 1, 0), "broad_positive_trend"),
        ((1, 1, 1, 1, 1, 1, 1, 1), "broad_positive_trend"),
        ((-1, -1, -1, -1, -1, -1, 0, 0), "broad_negative_trend"),
        ((-1, -1, -1, -1, -1, -1, -1, 0), "broad_negative_trend"),
        ((-1, -1, -1, -1, -1, -1, -1, -1), "broad_negative_trend"),
        ((1, 1, 1, 1, 1, 0, 0, -1), "mixed_cross_asset"),
        ((-1, -1, -1, -1, -1, 0, 0, 1), "mixed_cross_asset"),
        ((0, 0, 0, 0, 0, 0, 0, 0), "mixed_cross_asset"),
    ],
)
def test_regime_sign_thresholds_and_zero_semantics(
    signs: tuple[int, ...], expected: str
) -> None:
    sessions, closes, validation = _regime_fixture(signs)
    authority = build_regime_authority(sessions, closes, validation)
    assert authority.regime_ids == REGIME_IDS
    assert authority.session_to_regime == ((validation[0], expected),)


def test_regime_uses_t_minus_1_and_t_minus_127_not_current_close() -> None:
    sessions, closes, validation = _regime_fixture((1,) * 8)
    first = build_regime_authority(sessions, closes, validation)
    current_mutation = {
        symbol: values[:-1] + (-999_999.0,)
        for symbol, values in closes.items()
    }
    assert build_regime_authority(sessions, current_mutation, validation) == first

    endpoint_mutation = {
        symbol: values[:0] + (200.0,) + values[1:]
        for symbol, values in closes.items()
    }
    changed = build_regime_authority(sessions, endpoint_mutation, validation)
    assert changed.session_to_regime[0][1] == "broad_negative_trend"


def test_regime_fails_closed_on_insufficient_exact_history() -> None:
    sessions, closes, validation = _regime_fixture((1,) * 8)
    with pytest.raises(AuthorityDefinitionError, match="REGIME_HISTORY_INSUFFICIENT"):
        build_regime_authority(sessions[1:], {k: v[1:] for k, v in closes.items()}, validation)


def test_regime_maps_every_validation_session_once_and_rejects_bad_population() -> None:
    sessions, closes, validation = _regime_fixture((1,) * 8)
    second = "2019-01-03"
    sessions = sessions + (second,)
    closes = {symbol: values + (101.0,) for symbol, values in closes.items()}
    authority = build_regime_authority(sessions, closes, validation + (second,))
    assert tuple(session for session, _ in authority.session_to_regime) == validation + (second,)
    assert len(set(authority.session_to_regime)) == 2

    with pytest.raises(AuthorityDefinitionError, match="REGIME_INPUT_INVALID"):
        build_regime_authority(sessions, {**closes, "EXTRA": closes["SPY"]}, validation + (second,))


def test_authority_identity_is_deterministic_and_mutation_sensitive() -> None:
    validation = tuple(
        session
        for year in range(2019, 2023)
        for session in _sessions(year)
    )
    authority = build_fold_authority(validation)
    digest = canonical_authority_sha256(authority)
    assert digest == canonical_authority_sha256(build_fold_authority(validation))
    mutated = replace(
        authority,
        session_to_fold=authority.session_to_fold[:-1]
        + ((authority.session_to_fold[-1][0], "FOLD_2021"),),
    )
    assert canonical_authority_sha256(mutated) != digest


def test_fold_authority_fails_closed_on_gap_duplicate_or_wrong_year() -> None:
    validation = tuple(
        session
        for year in range(2019, 2023)
        for session in _sessions(year)
    )
    with pytest.raises(AuthorityDefinitionError, match="FOLD_AUTHORITY_INVALID"):
        build_fold_authority(validation + (validation[-1],))
    with pytest.raises(AuthorityDefinitionError, match="FOLD_AUTHORITY_INVALID"):
        build_fold_authority(validation[:-3])
    with pytest.raises(AuthorityDefinitionError, match="FOLD_AUTHORITY_INVALID"):
        build_fold_authority(("2018-12-31",) + validation)


def test_classifier_api_has_no_candidate_performance_channel() -> None:
    sessions, closes, validation = _regime_fixture((1,) * 8)
    with pytest.raises(TypeError):
        build_regime_authority(
            sessions,
            closes,
            validation,
            candidate_returns=(0.99,),  # type: ignore[call-arg]
        )
