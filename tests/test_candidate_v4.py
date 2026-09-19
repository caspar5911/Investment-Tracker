from datetime import datetime,timezone

from investment_tracker.candidate_v4 import (
    V4_VALIDATION_PANEL,
    preregister_candidate_v4,
    verify_preregistration,
)


def test_v4_is_one_cluster_aware_hypothesis_without_threshold_search():
    r=preregister_candidate_v4(created_at=datetime(2026,9,11,11,15,tzinfo=timezone.utc))
    assert r.grid_search_allowed is False
    assert r.replay_v2_thresholds_changed is False
    assert r.cooldown_sessions==20
    assert r.validation_panel==("QQQ","IWM","MDY","EFA","EEM","VNQ","RSP","IJH")
    assert r.panel_substitution_after_history_access_allowed is False
    assert r.prior_candidate_data_eligible_as_unseen is False
    assert not set(V4_VALIDATION_PANEL)&{"HACK","SOXX","NLR","URNM","GEV"}
    assert verify_preregistration(r)
