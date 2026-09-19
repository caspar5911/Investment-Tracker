from datetime import datetime, timezone

from investment_tracker.qualification_v5_large import (
    V5_LARGE_FOLDS,
    V5_LARGE_PANEL,
    V5_LARGE_QUALIFICATION_ID,
    build_v5_large_protocol,
    governance_assertions,
)


def test_large_v5_program_is_fixed_and_disjoint_from_prior_panels():
    assert V5_LARGE_QUALIFICATION_ID=="V5-LARGE-Q1"
    assert len(V5_LARGE_PANEL)==16
    assert V5_LARGE_PANEL==(
        "IVV","IWB","IWS","IWP","IWN","IWO",
        "EPP","EWJ","EWU","EWG","EWC","EWA","EWZ","EWW","EWH","EWS",
    )
    assert governance_assertions()


def test_large_v5_program_has_three_frozen_temporal_folds():
    assert [(f.fold_id,f.start_date.isoformat(),f.end_date.isoformat()) for f in V5_LARGE_FOLDS]==[
        ("F1-2008-2011","2008-02-01","2011-12-30"),
        ("F2-2012-2014","2012-01-03","2014-12-31"),
        ("F3-2015-2017","2015-01-02","2017-12-29"),
    ]


def test_protocol_uses_existing_candidate_v5_rules_without_change():
    p=build_v5_large_protocol(
        preregistered_at=datetime(2026,9,11,12,10,tzinfo=timezone.utc),
        history_accessed_at=datetime(2026,9,11,12,11,tzinfo=timezone.utc),
    )
    assert p.candidate_id=="CANDIDATE-v5.0"
    assert p.strategy_version=="REPLAY-v2.1"
    assert p.calculation_version=="CALC-v2.0"
    assert p.robustness_version=="BACKTEST-v1.0"
    assert p.qualification_dataset_id=="V5-LARGE-Q1"
    assert p.research_end_date.isoformat()=="2007-12-31"
