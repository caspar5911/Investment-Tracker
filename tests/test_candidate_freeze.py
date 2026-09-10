from datetime import datetime, timezone

import pytest

from investment_tracker.candidate_freeze import (
    CandidateFreezeInputs, FreezeBlockedError, freeze_candidate,
)
from investment_tracker.governance import FROZEN_VERSIONS


def inputs(**updates):
    values = dict(
        candidate_id="candidate-1", implementation_sha="a" * 40,
        canonical_input_digests={"phase-a": "b" * 64},
        calculation_versions=FROZEN_VERSIONS.as_dict(), test_suite_ref="ci/run/1",
        tests_passed=True, phase_a_complete=True, robustness_passed=True,
        independent_recompute_passed=True, robustness_result_digest="c" * 64,
        unresolved_limitations=["Independent Audit pending"],
        frozen_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
    )
    values.update(updates)
    return CandidateFreezeInputs(**values)


@pytest.mark.parametrize("gate", [
    "tests_passed", "phase_a_complete", "robustness_passed",
    "independent_recompute_passed",
])
def test_candidate_freeze_fails_closed_until_evidence_gate_passes(gate):
    with pytest.raises(FreezeBlockedError, match=gate):
        freeze_candidate(inputs(**{gate: False}))


def test_candidate_digest_is_deterministic_and_never_claims_production():
    first = freeze_candidate(inputs())
    second = freeze_candidate(inputs())
    assert first.candidate_output_digest == second.candidate_output_digest
    assert first.status == "FROZEN_CANDIDATE_NOT_PRODUCTION_APPROVED"
