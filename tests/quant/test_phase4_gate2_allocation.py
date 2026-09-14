from __future__ import annotations

import math
import sys

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.phase4.engine.allocation import (
    _canonical_weights,
    capped_inverse_volatility,
    equal_weights,
    portfolio_volatility_scale,
)


def test_equal_weights_are_literal_and_symbol_sorted() -> None:
    assert equal_weights(("CCC", "AAA", "BBB")) == (
        ("AAA", 1.0 / 3.0),
        ("BBB", 1.0 / 3.0),
        ("CCC", 1.0 / 3.0),
    )
    assert equal_weights(()) == ()


def test_equal_weights_reject_duplicate_or_invalid_symbols() -> None:
    with pytest.raises(ValueError):
        equal_weights(("AAA", "AAA"))
    with pytest.raises(ValueError):
        equal_weights(("AAA", ""))


def test_inverse_volatility_uses_literal_reciprocal_proportions() -> None:
    assert capped_inverse_volatility(
        {"BBB": 0.2, "AAA": 0.1}, maximum_asset_weight=1.0
    ) == (("AAA", 2.0 / 3.0), ("BBB", 1.0 / 3.0))


def test_inverse_volatility_iteratively_redistributes_each_capped_mass() -> None:
    weights = capped_inverse_volatility(
        {"DDD": 1.0, "BBB": 1.0 / 25.0, "AAA": 1.0 / 70.0, "CCC": 0.25},
        maximum_asset_weight=0.4,
    )

    assert tuple(symbol for symbol, _ in weights) == ("AAA", "BBB", "CCC", "DDD")
    assert tuple(weight for _, weight in weights) == pytest.approx(
        (0.4, 0.4, 0.16, 0.04)
    )


def test_inverse_volatility_leaves_nonallocable_mass_as_cash() -> None:
    weights = capped_inverse_volatility(
        {"BBB": 0.2, "AAA": 0.1}, maximum_asset_weight=0.3
    )

    assert weights == (("AAA", 0.3), ("BBB", 0.3))
    assert sum(weight for _, weight in weights) == pytest.approx(0.6)


def test_inverse_volatility_is_mapping_order_independent() -> None:
    forward = capped_inverse_volatility(
        {"AAA": 0.1, "BBB": 0.2, "CCC": 0.4}, maximum_asset_weight=0.5
    )
    reverse = capped_inverse_volatility(
        {"CCC": 0.4, "BBB": 0.2, "AAA": 0.1}, maximum_asset_weight=0.5
    )

    assert reverse == forward
    assert tuple(symbol for symbol, _ in forward) == ("AAA", "BBB", "CCC")


@pytest.mark.parametrize("bad_volatility", [0.0, -0.1, np.nan, np.inf, -np.inf])
def test_inverse_volatility_excludes_nonpositive_or_nonfinite_estimates(
    bad_volatility: float,
) -> None:
    assert (
        capped_inverse_volatility({"AAA": bad_volatility}, maximum_asset_weight=0.5)
        == ()
    )


def test_portfolio_volatility_scale_uses_covariance_and_252_sessions() -> None:
    covariance = pd.DataFrame(
        [[0.0004, 0.0], [0.0, 0.0004]],
        index=["AAA", "BBB"],
        columns=["AAA", "BBB"],
    )
    unscaled_annual_volatility = math.sqrt(252.0 * 0.0002)

    weights = portfolio_volatility_scale(
        (("BBB", 0.5), ("AAA", 0.5)),
        covariance,
        target_portfolio_volatility=unscaled_annual_volatility / 2.0,
    )

    assert tuple(symbol for symbol, _ in weights) == ("AAA", "BBB")
    assert tuple(weight for _, weight in weights) == pytest.approx((0.25, 0.25))


def test_portfolio_volatility_scale_caps_scale_at_one() -> None:
    covariance = pd.DataFrame([[0.0001]], index=["AAA"], columns=["AAA"])

    assert portfolio_volatility_scale(
        (("AAA", 0.75),), covariance, target_portfolio_volatility=1.0
    ) == (("AAA", 0.75),)


@pytest.mark.parametrize(
    "covariance_value",
    [0.0, np.nan, np.inf, -np.inf],
    ids=["zero", "nan", "inf", "neg-inf"],
)
def test_portfolio_volatility_scale_targets_cash_when_volatility_is_unavailable(
    covariance_value: float,
) -> None:
    covariance = pd.DataFrame([[covariance_value]], index=["AAA"], columns=["AAA"])

    assert (
        portfolio_volatility_scale(
            (("AAA", 1.0),), covariance, target_portfolio_volatility=0.12
        )
        == ()
    )


def test_weight_roundoff_within_tolerance_is_canonically_clamped() -> None:
    covariance = pd.DataFrame(
        [[0.0001, 0.0], [0.0, 0.0001]],
        index=["AAA", "BBB"],
        columns=["AAA", "BBB"],
    )

    weights = portfolio_volatility_scale(
        (("AAA", 0.5), ("BBB", 0.5000000000005)),
        covariance,
        target_portfolio_volatility=1.0,
    )

    assert sum(weight for _, weight in weights) == 1.0
    assert weights[0][1] == pytest.approx(0.49999999999975)
    assert weights[1][1] == pytest.approx(0.50000000000025)


@pytest.mark.parametrize(
    "weights",
    [
        (("AAA", -1e-15),),
        (("AAA", 0.5), ("BBB", 0.500000000002)),
        (("AAA", np.nan),),
        (("AAA", np.inf),),
    ],
    ids=["negative", "gross-over-one", "nan", "infinite"],
)
def test_portfolio_volatility_scale_rejects_invalid_base_weights(
    weights: tuple[tuple[str, float], ...],
) -> None:
    covariance = pd.DataFrame(
        np.eye(len(weights), dtype=np.float64),
        index=[symbol for symbol, _ in weights],
        columns=[symbol for symbol, _ in weights],
    )

    with pytest.raises(ValueError):
        portfolio_volatility_scale(
            weights, covariance, target_portfolio_volatility=0.12
        )


def test_portfolio_volatility_scale_rejects_covariance_label_substitution() -> None:
    covariance = pd.DataFrame([[0.01]], index=["BBB"], columns=["BBB"])

    with pytest.raises(ValueError):
        portfolio_volatility_scale(
            (("AAA", 1.0),), covariance, target_portfolio_volatility=0.12
        )


# ============================================================
# Canonical weight non-negativity regression tests
# ============================================================


def _search_for_negative_weight() -> list[tuple[str, float]] | None:
    """Systematically search for inputs that produce a negative canonical weight."""
    for n in range(2, 31):
        for excess_exp in range(-16, -8):
            excess = 10**excess_exp
            base = (1.0 + excess) / n
            tiny_last = 10**(-16)
            remaining = (1.0 + excess) - tiny_last
            per_weight = remaining / (n - 1)

            symbols = tuple(chr(ord("A") + i) for i in range(n))
            weights = tuple(
                (symbols[i], per_weight) for i in range(n - 1)
            ) + ((symbols[-1], tiny_last),)

            total = math.fsum(w for _, w in weights)
            if total > 1.0 + 1e-12 or total <= 0:
                continue

            result = _canonical_weights(weights)
            for symbol, weight in result:
                if weight < 0.0:
                    return list(weights)
    return None


class TestCanonicalWeightsNonNegativity:
    """Regression tests for the floating-point residual correction in _canonical_weights."""

    def test_brute_force_search_for_negative(self) -> None:
        """Search systematically over 30 symbol counts and 8 excess exponents."""
        result = _search_for_negative_weight()
        if result is not None:
            pytest.fail(
                f"_canonical_weights produced a negative weight for input: "
                f"{result}\n"
                f"total={math.fsum(w for _, w in result)}\n"
                f"result={_canonical_weights(result)}"
            )

    def test_direct_adversarial_construction(self) -> None:
        """Construct edge cases where fsum residual could exceed the last weight."""
        a = 0.5 + 1e-14
        b = 0.5 + 1e-14
        c = 1e-18
        total = math.fsum([a, b, c])
        if total > 1.0:
            result = _canonical_weights((("AAA", a), ("BBB", b), ("CCC", c)))
            for symbol, weight in result:
                assert weight >= 0.0, (
                    f"NEGATIVE WEIGHT: {symbol}={weight!r}"
                )

    def test_comprehensive_edge_cases(self) -> None:
        """Battery of adversarial inputs."""
        test_cases = [
            [(f"S{i:02d}", 0.02 + 1e-15) for i in range(50)],
            [("AAA", 0.99)] + [(f"S{i:02d}", 0.001) for i in range(10)],
            [(f"S{i:02d}", 1.0 / 10 + 1e-16) for i in range(10)],
            [("AAA", 0.7), ("BBB", 0.3), ("CCC", 5e-324)],
            [("AAA", 0.6), ("BBB", 0.4), ("CCC", sys.float_info.min)],
        ]
        for i, weights in enumerate(test_cases):
            filtered = [(s, w) for s, w in weights if w > 0.0]
            total = math.fsum(w for _, w in filtered)
            if total > 1.0 + 1e-12:
                continue
            try:
                result = _canonical_weights(filtered)
                for symbol, weight in result:
                    assert weight >= 0.0, (
                        f"Case {i}: negative weight {weight!r} for {symbol!r} "
                        f"(input total={total!r})"
                    )
            except ValueError as e:
                assert "exceeds one" in str(e).lower() or "nonnegative" in str(e).lower()

    def test_idempotence_and_determinism(self) -> None:
        """Repeated canonicalization must be idempotent and deterministic."""
        weights = (
            ("AAA", 0.3333333333333333),
            ("BBB", 0.3333333333333333),
            ("CCC", 0.3333333333333333),
        )
        first = _canonical_weights(weights)
        second = _canonical_weights(first)
        third = _canonical_weights(second)
        assert first == second == third
        for symbol, weight in third:
            assert weight >= 0.0

    def test_gross_exposure_never_exceeds_one(self) -> None:
        """The canonical output total must never exceed 1.0 + tolerance."""
        weights = (("AAA", 0.4), ("BBB", 0.35), ("CCC", 0.25))
        result = _canonical_weights(weights)
        total = math.fsum(w for _, w in result)
        assert total <= 1.0 + 1e-12, f"canonical total {total!r} exceeds 1.0"
