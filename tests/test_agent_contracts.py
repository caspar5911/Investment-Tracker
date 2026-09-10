from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKERS = [
    "agents/ura.md",
    "agents/cibr.md",
    "agents/smh.md",
    "agents/copx-xle.md",
    "agents/audit-robustness.md",
]


def test_root_agents_file_pins_governance_and_single_writer():
    text = (ROOT / "AGENTS.md").read_text()
    for token in ["TPC-v1.2", "REPLAY-v1.0", "CALC-v1.2", "ROBUST-v1.0"]:
        assert token in text
    for symbol in ["HACK", "SOXX", "NLR", "URNM", "GEV"]:
        assert symbol in text
    assert "Only the coordinator" in text
    assert "No trade execution" in text


def test_worker_contracts_explicitly_deny_canonical_sheet_writes():
    for relative in WORKERS:
        text = (ROOT / relative).read_text()
        assert "MUST NOT write to the canonical Google Sheet" in text
        assert "READY_FOR_COORDINATOR_REVIEW" in text
        assert "HACK, SOXX, NLR, URNM, GEV" in text


def test_coordinator_contract_requires_snapshot_freshness_and_readback():
    text = (ROOT / "agents/coordinator.md").read_text()
    assert "STALE_SNAPSHOT" in text
    assert "read back" in text.lower()
    assert "Phase Matrix last" in text
