from __future__ import annotations

from pathlib import Path

from investment_tracker.quant.phase4.finalization.audit import (
    CAMPAIGN_RESULT_SET_IDENTITY,
    audit_campaign,
)


def test_real_committed_campaign_audits_all_180_positions() -> None:
    root = Path(__file__).resolve().parents[2]
    audit = audit_campaign(root, CAMPAIGN_RESULT_SET_IDENTITY)
    assert audit.expected_positions == 180
    assert audit.accounted_positions == 180
    assert tuple(row.population_position for row in audit.rows) == tuple(range(1, 181))
    assert len({row.candidate_id for row in audit.rows}) == 180
    assert sum(audit.status_counts.values()) == 180
    assert audit.status_counts.get("CAMPAIGN_EXECUTION_FAILED", 0) == 0
    assert tuple(
        row.candidate_id for row in audit.rows if row.eligibility_status == "ELIGIBLE"
    ) == audit.eligible_candidate_ids
