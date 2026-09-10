import hashlib
import json
from datetime import date

from investment_tracker.governance import FROZEN_VERSIONS
from investment_tracker.validation import validate_manifest_files


def _manifest(output_digests):
    return {
        "role": "URA",
        "run_id": "WORKER-SEC-1",
        "input_snapshot_id": "SNAP-SEC-1",
        "input_snapshot_digests": {"spy": "spy-digest", "governance": "gov-digest"},
        "asset": "URA",
        "start_date": date(2018, 1, 1).isoformat(),
        "end_date": date(2018, 12, 31).isoformat(),
        "versions": FROZEN_VERSIONS.as_dict(),
        "source_provider": "Alpaca",
        "source_feed": "SIP",
        "input_refs": ["canonical snapshot"],
        "output_digests": output_digests,
        "locked_holdout_excluded": True,
        "completion_status": "READY_FOR_COORDINATOR_REVIEW",
    }


def test_manifest_rejects_absolute_artifact_path(tmp_path):
    outside = tmp_path.parent / "outside.csv"
    outside.write_text("sensitive")
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest({str(outside): digest})))

    report = validate_manifest_files(manifest_path)
    assert report.ok is False
    assert any("unsafe artifact path" in error for error in report.errors)


def test_manifest_rejects_parent_traversal(tmp_path):
    outside = tmp_path.parent / "outside.csv"
    outside.write_text("sensitive")
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest({"../outside.csv": digest})))

    report = validate_manifest_files(manifest_path)
    assert report.ok is False
    assert any("unsafe artifact path" in error for error in report.errors)


def test_manifest_rejects_symlink_artifact(tmp_path):
    outside = tmp_path.parent / "outside.csv"
    outside.write_text("sensitive")
    link = tmp_path / "market-data.csv"
    link.symlink_to(outside)
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest({"market-data.csv": digest})))

    report = validate_manifest_files(manifest_path)
    assert report.ok is False
    assert any("symlink" in error for error in report.errors)


def test_manifest_rejects_undeclared_artifact_name(tmp_path):
    artifact = tmp_path / "arbitrary.txt"
    artifact.write_text("unexpected")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest({"arbitrary.txt": digest})))

    report = validate_manifest_files(manifest_path)
    assert report.ok is False
    assert any("artifact name not allowed" in error for error in report.errors)
