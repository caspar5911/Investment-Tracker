from datetime import datetime,timezone
from investment_tracker.candidate_v5 import V5_VALIDATION_PANEL,preregister_candidate_v5,verify_preregistration

def test_v5_is_single_research_derived_hypothesis():
    r=preregister_candidate_v5(created_at=datetime(2026,9,11,11,50,tzinfo=timezone.utc))
    assert r.grid_search_allowed is False
    assert r.repeated_v5_variants_allowed is False
    assert r.validation_panel==("DIA","IJR","VTI","IWF","IWD","QUAL","MTUM","USMV")
    assert not set(V5_VALIDATION_PANEL)&{"HACK","SOXX","NLR","URNM","GEV"}
    assert verify_preregistration(r)
