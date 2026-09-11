from datetime import datetime, timezone

import pytest

from investment_tracker.candidate_v2 import (
    LEGACY_SEEN_PARTITIONS,
    V2_BENCHMARK,
    V2_PHASE_A_WINDOW,
    V2_PHASE_B_WINDOW,
    V2_VALIDATION_PANEL,
    V2_VERSIONS,
    V2_WARMUP_WINDOW,
    preregister_candidate_v2,
    verify_preregistration,
)


NOW = datetime(2026, 9, 11, 10, 45, tzinfo=timezone.utc)


def test_candidate_v2_is_preregistered_without_replay_threshold_tuning():
    record = preregister_candidate_v2(
        created_at=NOW,
        prospective_evidence_not_before=NOW,
    )

    assert record.versions == V2_VERSIONS
    assert record.replay_thresholds_changed is False
    assert record.replay_threshold_source == "INHERIT_REPLAY-v1.0_UNCHANGED"
    assert record.validation_panel == V2_VALIDATION_PANEL
    assert record.benchmark == V2_BENCHMARK
    assert record.warmup_window == V2_WARMUP_WINDOW
    assert record.phase_a_window == V2_PHASE_A_WINDOW
    assert record.phase_b_window == V2_PHASE_B_WINDOW
    assert record.panel_substitution_after_history_access_allowed is False
    assert record.legacy_seen_partitions == LEGACY_SEEN_PARTITIONS
    assert record.legacy_seen_partitions_eligible_as_unseen_oos is False
    assert record.replacement_holdout_locked is True
    assert set(record.replacement_holdout_symbols) == {
        "GEV", "HACK", "NLR", "SOXX", "URNM"
    }
    assert verify_preregistration(record)


def test_validation_panel_is_fixed_and_distinct_from_locked_holdout():
    assert V2_VALIDATION_PANEL == (
        "XLI", "XLU", "XLB", "XME", "XOP", "IGV", "XSD", "IYT"
    )
    assert not set(V2_VALIDATION_PANEL) & {"GEV", "HACK", "NLR", "SOXX", "URNM"}


def test_candidate_v2_cannot_backdate_prospective_evidence_boundary():
    with pytest.raises(ValueError, match="cannot predate"):
        preregister_candidate_v2(
            created_at=NOW,
            prospective_evidence_not_before=datetime(
                2026, 9, 11, 10, 44, tzinfo=timezone.utc
            ),
        )


def test_preregistration_requires_aware_timestamps():
    with pytest.raises(ValueError, match="timezone-aware"):
        preregister_candidate_v2(
            created_at=datetime(2026, 9, 11, 10, 45),
            prospective_evidence_not_before=NOW,
        )
