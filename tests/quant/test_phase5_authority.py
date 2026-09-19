from pathlib import Path

from investment_tracker.quant.phase5.authority import load_phase4_authority
from investment_tracker.quant.phase5.methodology import (
    SELECTED_BINDING_SHA256,
    SELECTED_CANDIDATE_ID,
)
from investment_tracker.quant.phase5.targets import extract_sealed_validation_targets


ROOT = Path(__file__).resolve().parents[2]


def test_phase5_binds_exact_sealed_survivor_and_zero_bps_targets():
    decision, _result, binding = load_phase4_authority(ROOT)
    assert decision["selected_candidate_id"] == SELECTED_CANDIDATE_ID
    assert binding.binding_sha256 == SELECTED_BINDING_SHA256
    targets = extract_sealed_validation_targets(ROOT)
    assert targets[0].signal_session.isoformat().startswith("2019-01-02")
    assert targets[0].due_session.isoformat().startswith("2019-01-03")
    assert set(targets[0].selected_symbols) == {"SPY", "VNQ", "XLP"}
