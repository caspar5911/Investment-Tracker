from __future__ import annotations

import numpy as np
import pandas as pd

from investment_tracker.quant.backtest.engine import run_backtest
from investment_tracker.quant.backtest.models import ExecutionAssumptions
from investment_tracker.quant.methodology import CURRENT_QFQ_METHODOLOGY


def bars(scale: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": np.array([100.0, 102.0, 104.0, 103.0]) * scale,
            "high": np.array([102.0, 105.0, 105.0, 104.0]) * scale,
            "low": np.array([99.0, 101.0, 102.0, 101.0]) * scale,
            "close": np.array([101.0, 104.0, 103.0, 102.0]) * scale,
            "volume": [1000.0, 1100.0, 1200.0, 1300.0],
        },
        index=pd.bdate_range("2024-01-02", periods=4, tz="UTC"),
    )


def test_qfq_methodology_is_explicitly_not_decision_grade() -> None:
    assert CURRENT_QFQ_METHODOLOGY.version == "QFQ-NORMALIZED-RESEARCH-v1"
    assert CURRENT_QFQ_METHODOLOGY.signal_prices == "MOOMOO_QFQ"
    assert CURRENT_QFQ_METHODOLOGY.execution_prices == "MOOMOO_QFQ_NORMALIZED"
    assert CURRENT_QFQ_METHODOLOGY.decision_grade is False
    assert CURRENT_QFQ_METHODOLOGY.required_successor == "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS"


def test_fractional_percentage_simulation_is_invariant_to_uniform_price_scale() -> None:
    targets = pd.Series([1.0, 1.0, 0.0, 0.0], index=bars().index)
    assumptions = ExecutionAssumptions(100_000.0, 1.0, 2.0, True)

    original = run_backtest(bars(), targets, assumptions)
    scaled = run_backtest(bars(0.25), targets, assumptions)

    np.testing.assert_allclose(original.equity_curve, scaled.equity_curve)
    assert original.fills[0].reference_price != scaled.fills[0].reference_price
