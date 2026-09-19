"""Large, temporally separated Candidate-v5 qualification program.

This freezes a single broad panel and three validation folds before any price
history for this program is requested. Candidate-v5 strategy rules are not
changed. BACKTEST-v1.0 remains the evaluator.
"""

from __future__ import annotations

from datetime import date, datetime

from .backtest_v1 import FrozenBacktestProtocol, ValidationFold, freeze_backtest_protocol
from .candidate_v5 import CANDIDATE_V5, V5_VERSIONS
from .governance import LOCKED_HOLDOUT

V5_LARGE_QUALIFICATION_ID = "V5-LARGE-Q1"
V5_LARGE_PANEL = (
    "IVV","IWB","IWS","IWP","IWN","IWO",
    "EPP","EWJ","EWU","EWG","EWC","EWA","EWZ","EWW","EWH","EWS",
)
V5_LARGE_BENCHMARK = "SPY"
V5_LARGE_RESEARCH_END = date(2007, 12, 31)
V5_LARGE_FOLDS = (
    ValidationFold("F1-2008-2011", date(2008, 2, 1), date(2011, 12, 30)),
    ValidationFold("F2-2012-2014", date(2012, 1, 3), date(2014, 12, 31)),
    ValidationFold("F3-2015-2017", date(2015, 1, 2), date(2017, 12, 29)),
)


def build_v5_large_protocol(
    *, preregistered_at: datetime, history_accessed_at: datetime
) -> FrozenBacktestProtocol:
    """Build the exact frozen BACKTEST-v1.0 protocol for Candidate v5."""
    return freeze_backtest_protocol(
        candidate_id=CANDIDATE_V5,
        qualification_dataset_id=V5_LARGE_QUALIFICATION_ID,
        panel=V5_LARGE_PANEL,
        benchmark=V5_LARGE_BENCHMARK,
        research_end_date=V5_LARGE_RESEARCH_END,
        folds=V5_LARGE_FOLDS,
        preregistered_at=preregistered_at,
        history_accessed_at=history_accessed_at,
        strategy_version=V5_VERSIONS["replay"],
        calculation_version=V5_VERSIONS["calc"],
        robustness_version="BACKTEST-v1.0",
    )


def governance_assertions() -> bool:
    prior_v5_panel={"DIA","IJR","VTI","IWF","IWD","QUAL","MTUM","USMV"}
    prior_v4_panel={"QQQ","IWM","MDY","EFA","EEM","VNQ","RSP","IJH"}
    prior_v3_panel={"XLV","XLP","XLY","XLF","XLRE","XBI","XRT","ITB"}
    prior_v2_panel={"XLI","XLU","XLB","XME","XOP","IGV","XSD","IYT"}
    prior_v1_panel={"ETN","PWR","VRT","URA","CIBR","SMH","COPX","XLE"}
    frozen=set(V5_LARGE_PANEL)
    return (
        len(frozen)==len(V5_LARGE_PANEL)
        and not frozen & LOCKED_HOLDOUT
        and not frozen & prior_v5_panel
        and not frozen & prior_v4_panel
        and not frozen & prior_v3_panel
        and not frozen & prior_v2_panel
        and not frozen & prior_v1_panel
    )
