from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class QFQMethodology:
    version: Literal["QFQ-NORMALIZED-RESEARCH-v1"]
    signal_prices: Literal["MOOMOO_QFQ"]
    execution_prices: Literal["MOOMOO_QFQ_NORMALIZED"]
    decision_grade: Literal[False]
    required_successor: Literal["UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS"]


CURRENT_QFQ_METHODOLOGY = QFQMethodology(
    version="QFQ-NORMALIZED-RESEARCH-v1",
    signal_prices="MOOMOO_QFQ",
    execution_prices="MOOMOO_QFQ_NORMALIZED",
    decision_grade=False,
    required_successor="UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS",
)
