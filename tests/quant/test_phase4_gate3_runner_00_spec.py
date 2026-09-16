from pathlib import Path

from investment_tracker.quant.phase4.gate3_runner.methodology import SPEC_CONTENT_SHA256, spec_identity


ROOT = Path(__file__).resolve().parents[2]


def test_runner_spec_exact_bytes_match_pinned_digest():
    identity = spec_identity(ROOT)
    assert identity.content_sha256 == SPEC_CONTENT_SHA256
    assert identity.kind == "phase4_gate3_runner_spec"
