import hashlib
import json
from pathlib import Path

from investment_tracker.governance import FROZEN_VERSIONS
from investment_tracker.models import BlockedWorkerManifest
from investment_tracker.validation import validate_manifest_files


def test_blocked_manifest_is_not_a_ready_manifest_and_validates_diagnostics(tmp_path):
    notes = tmp_path / "notes.md"
    validation = tmp_path / "validation.json"
    notes.write_text("blocked\n")
    validation.write_text('{"status":"BLOCKED_REQUIRED_INPUT"}\n')
    payload = {
        "role": "URA", "run_id": "URA-PREFLIGHT", "asset": "URA",
        "start_date": "2020-01-01", "end_date": "2023-12-31",
        "versions": FROZEN_VERSIONS.as_dict(), "source_provider": "Alpaca",
        "source_feed": "SIP", "requested_outputs": ["market-data.csv"],
        "required_inputs": ["coordinator-issued immutable snapshot"],
        "unavailable_inputs": ["canonical snapshot"],
        "diagnostic_digests": {
            name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
            for name in ("notes.md", "validation.json")
        },
        "locked_holdout_excluded": True, "canonical_write_attempted": False,
        "completion_status": "BLOCKED_REQUIRED_INPUT",
    }
    manifest = BlockedWorkerManifest.model_validate(payload)
    assert manifest.completion_status == "BLOCKED_REQUIRED_INPUT"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload))
    report = validate_manifest_files(path)
    assert report.ok
    assert report.counts["verified_files"] == 2


def test_all_committed_proxy_preflights_name_one_snapshot_and_validate():
    root = Path(__file__).parents[1] / "staging"
    for asset in ("URA", "CIBR", "SMH", "COPX", "XLE"):
        paths = list((root / asset.lower()).glob("*/manifest.json"))
        assert len(paths) == 1
        payload = json.loads(paths[0].read_text())
        manifest = BlockedWorkerManifest.model_validate(payload)
        assert manifest.asset == asset
        assert manifest.completion_status == "BLOCKED_REQUIRED_INPUT"
        assert len(manifest.unavailable_inputs) == 1
        assert "coordinator-issued immutable" in manifest.unavailable_inputs[0]
        assert validate_manifest_files(paths[0]).ok
