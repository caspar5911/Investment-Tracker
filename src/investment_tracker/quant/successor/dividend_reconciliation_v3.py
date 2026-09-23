from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

DIVIDEND_RECONCILIATION_SCHEMA = "DIVIDEND-RECONCILIATION-v3"


class DividendReconciliationError(ValueError):
    pass


@dataclass(frozen=True)
class DividendAmountAuthority:
    schema_version: str
    ordinary_amount: float
    special_amount: float
    endpoint_statement_count: int


def reconcile_structured_dividend_amounts(
    endpoint_rows: Sequence[Mapping[str, object]],
    *,
    rehab_ordinary_amount: float,
    rehab_special_amount: float,
) -> DividendAmountAuthority:
    """Use structured rehab fields as amount authority.

    The corporate-action dividend endpoint is free-text distribution-plan
    evidence. It corroborates the event but is not parsed as a numeric amount
    source.
    """
    ordinary = float(rehab_ordinary_amount)
    special = float(rehab_special_amount)
    if (
        not math.isfinite(ordinary)
        or not math.isfinite(special)
        or ordinary < 0.0
        or special < 0.0
        or ordinary + special <= 0.0
    ):
        raise DividendReconciliationError(
            "SUCCESSOR_DIVIDEND_STRUCTURED_AMOUNT_INVALID"
        )
    if not endpoint_rows:
        raise DividendReconciliationError(
            "SUCCESSOR_DIVIDEND_ENDPOINT_MISSING"
        )
    for row in endpoint_rows:
        if not isinstance(row, Mapping):
            raise DividendReconciliationError(
                "SUCCESSOR_DIVIDEND_ENDPOINT_RECORD_INVALID"
            )
        if not str(row.get("statement") or "").strip():
            raise DividendReconciliationError(
                "SUCCESSOR_DIVIDEND_ENDPOINT_STATEMENT_MISSING"
            )
    return DividendAmountAuthority(
        schema_version=DIVIDEND_RECONCILIATION_SCHEMA,
        ordinary_amount=ordinary,
        special_amount=special,
        endpoint_statement_count=len(endpoint_rows),
    )
