from __future__ import annotations

import math

import pytest

from investment_tracker.quant.successor.dividend_reconciliation_v3 import (
    DIVIDEND_RECONCILIATION_SCHEMA,
    DividendReconciliationError,
    reconcile_structured_dividend_amounts,
    validate_structured_dividend_components,
)


def test_structured_amounts_are_authority_even_when_statement_has_multiple_numbers() -> None:
    result = reconcile_structured_dividend_amounts(
        [
            {
                "statement": (
                    "Cash Dividend: 0.25 USD Per Share; "
                    "Special Dividend: 0.10 USD Per Share"
                )
            }
        ],
        rehab_ordinary_amount=0.25,
        rehab_special_amount=0.10,
    )
    assert result.schema_version == DIVIDEND_RECONCILIATION_SCHEMA
    assert result.ordinary_amount == 0.25
    assert result.special_amount == 0.10
    assert result.endpoint_statement_count == 1


def test_multiple_endpoint_records_do_not_get_summed_from_free_text() -> None:
    result = reconcile_structured_dividend_amounts(
        [
            {"statement": "Cash Dividend: 0.25 USD Per Share"},
            {"statement": "Special Dividend: 0.10 USD Per Share"},
        ],
        rehab_ordinary_amount=0.25,
        rehab_special_amount=0.10,
    )
    assert result.ordinary_amount == 0.25
    assert result.special_amount == 0.10
    assert result.endpoint_statement_count == 2


def test_statement_wording_is_not_numeric_authority() -> None:
    result = reconcile_structured_dividend_amounts(
        [{"statement": "Final distribution plan - implemented"}],
        rehab_ordinary_amount=0.42,
        rehab_special_amount=0.0,
    )
    assert result.ordinary_amount == 0.42
    assert result.special_amount == 0.0


@pytest.mark.parametrize(
    ("ordinary", "special"),
    [
        (-0.1, 0.0),
        (0.0, -0.1),
        (math.nan, 0.1),
        (0.1, math.inf),
        (0.0, 0.0),
    ],
)
def test_invalid_structured_amounts_fail_closed(ordinary: float, special: float) -> None:
    with pytest.raises(
        DividendReconciliationError,
        match="SUCCESSOR_DIVIDEND_STRUCTURED_AMOUNT_INVALID",
    ):
        reconcile_structured_dividend_amounts(
            [{"statement": "Cash Dividend"}],
            rehab_ordinary_amount=ordinary,
            rehab_special_amount=special,
        )


def test_missing_endpoint_fails_closed() -> None:
    with pytest.raises(
        DividendReconciliationError,
        match="SUCCESSOR_DIVIDEND_ENDPOINT_MISSING",
    ):
        reconcile_structured_dividend_amounts(
            [],
            rehab_ordinary_amount=0.2,
            rehab_special_amount=0.0,
        )


def test_blank_statement_fails_closed() -> None:
    with pytest.raises(
        DividendReconciliationError,
        match="SUCCESSOR_DIVIDEND_ENDPOINT_STATEMENT_MISSING",
    ):
        reconcile_structured_dividend_amounts(
            [{"statement": "   "}],
            rehab_ordinary_amount=0.2,
            rehab_special_amount=0.0,
        )


def test_raw_component_validation_allows_zero_zero_but_rejects_negative() -> None:
    assert validate_structured_dividend_components(
        rehab_ordinary_amount=0.0,
        rehab_special_amount=0.0,
    ) == (0.0, 0.0)

    with pytest.raises(
        DividendReconciliationError,
        match="SUCCESSOR_DIVIDEND_STRUCTURED_AMOUNT_INVALID",
    ):
        validate_structured_dividend_components(
            rehab_ordinary_amount=-1.0,
            rehab_special_amount=2.0,
        )
