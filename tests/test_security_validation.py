import hashlib
import json

from investment_tracker.validation import validate_manifest_files


def test_manifest_cannot_hash_files_outside_staging(tmp_path):
    secret = tmp_path / "secret"
    secret.write_text("not staging")
    run = tmp_path / "run"
    run.mkdir()
    manifest = {
        "role": "worker-a", "run_id": "r1", "input_snapshot_id": "s1",
        "input_snapshot_digests": {"spec": "abc"}, "asset": "URA",
        "start_date": "2019-01-01", "end_date": "2019-12-31",
        "versions": {"tpc": "TPC-v1.2", "replay": "REPLAY-v1.0", "calc": "CALC-v1.2", "robust": "ROBUST-v1.0"},
        "source_provider": "Alpaca", "source_feed": "SIP", "input_refs": [],
        "output_digests": {"../secret": hashlib.sha256(secret.read_bytes()).hexdigest()},
        "locked_holdout_excluded": True, "completion_status": "READY_FOR_COORDINATOR_REVIEW",
    }
    path = run / "manifest.json"
    path.write_text(json.dumps(manifest))
    report = validate_manifest_files(path)
    assert not report.ok
    assert report.counts["verified_files"] == 0
    assert "unsafe artifact path" in report.errors[0]
