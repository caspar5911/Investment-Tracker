from datetime import datetime, timezone

from investment_tracker.candidate_v3 import (
    V3_VALIDATION_PANEL,
    V3_VERSIONS,
    preregister_candidate_v3,
    verify_preregistration,
)


def test_v3_is_one_fixed_hypothesis_with_no_grid_search():
    record=preregister_candidate_v3(created_at=datetime(2026,9,11,11,0,tzinfo=timezone.utc))
    assert record.versions==V3_VERSIONS
    assert record.grid_search_allowed is False
    assert len(record.replay_changes)==2
    assert record.validation_panel==("XLV","XLP","XLY","XLF","XLRE","XBI","XRT","ITB")
    assert record.panel_substitution_after_history_access_allowed is False
    assert record.candidate_v1_v2_data_eligible_as_unseen is False
    assert not set(V3_VALIDATION_PANEL)&{"GEV","HACK","NLR","SOXX","URNM"}
    assert verify_preregistration(record)
