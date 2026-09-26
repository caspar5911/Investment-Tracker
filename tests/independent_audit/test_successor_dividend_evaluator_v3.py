from __future__ import annotations

import json

import pandas as pd
import pytest

from investment_tracker.quant.successor.dividend_reconciliation_v3 import (
    DividendReconciliationError,
)

from investment_tracker.independent_audit.successor.evaluate_dividend_v3 import (
    _corporate_actions,
)


def _entries(
    statement: str,
    *,
    ordinary: float = 0.25,
    special: float = 0.10,
    include_endpoint: bool = True,
) -> dict[str, bytes]:
    rehab = pd.DataFrame(
        [
            {
                "ex_div_date": "2024-06-03",
                "per_cash_div": ordinary,
                "special_dividend": special,
                "split_ratio": 1.0,
                "per_share_div_ratio": 0.0,
                "per_share_trans_ratio": 0.0,
                "allotment_ratio": 0.0,
                "stk_spo_ratio": 0.0,
                "spin_off_ratio": 0.0,
            }
        ]
    )
    return {
        "corporate_actions/rehab/SYN.csv": rehab.to_csv(
            index=False, lineterminator="\n"
        ).encode("utf-8"),
        "corporate_actions/dividends/SYN.json": json.dumps(
            {
                "dividend_list": (
                    [
                        {
                            "ex_date": "2024-06-03",
                            "dividend_payable_date": "2024-06-10",
                            "statement": statement,
                        }
                    ]
                    if include_endpoint
                    else []
                )
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
        "corporate_actions/splits/SYN.json": b'{"split_list":[]}',
    }


def test_multi_component_statement_uses_structured_rehab_amounts() -> None:
    scored = pd.DatetimeIndex([pd.Timestamp("2024-06-03", tz="UTC")])
    splits, dividends, evidence = _corporate_actions(
        _entries(
            "Cash Dividend: 0.25 USD Per Share; "
            "Special Dividend: 0.10 USD Per Share"
        ),
        "SYN",
        scored,
    )
    assert splits == []
    assert [event.amount_per_unit for event in dividends] == [0.25, 0.10]
    assert evidence["dividend_component_count"] == 2


def test_free_text_numbers_are_not_treated_as_amount_authority() -> None:
    scored = pd.DatetimeIndex([pd.Timestamp("2024-06-03", tz="UTC")])
    _, dividends, _ = _corporate_actions(
        _entries(
            "Distribution plan reference 2024; "
            "Cash Dividend: 99.99 USD Per Share; "
            "Special Dividend: 88.88 USD Per Share"
        ),
        "SYN",
        scored,
    )
    assert [event.amount_per_unit for event in dividends] == [0.25, 0.10]


@pytest.mark.parametrize(
    ("ordinary", "special", "include_endpoint"),
    [
        (-1.0, 2.0, True),
        (-1.0, 0.0, False),
    ],
)
def test_negative_rehab_cash_fails_before_positive_component_filtering(
    ordinary: float,
    special: float,
    include_endpoint: bool,
) -> None:
    scored = pd.DatetimeIndex([pd.Timestamp("2024-06-03", tz="UTC")])
    with pytest.raises(
        DividendReconciliationError,
        match="SUCCESSOR_DIVIDEND_STRUCTURED_AMOUNT_INVALID",
    ):
        _corporate_actions(
            _entries(
                "Synthetic distribution plan",
                ordinary=ordinary,
                special=special,
                include_endpoint=include_endpoint,
            ),
            "SYN",
            scored,
        )
