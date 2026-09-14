from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from investment_tracker.quant.phase4.engine.allocation import (
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
