import hashlib
import json

from investment_tracker.cli import main
from investment_tracker.governance import FROZEN_VERSIONS


def manifest(asset: str, output_digests: dict[str, str]):
    return {
        "role": asset,
        "run_id": "WORKER-CLI",
        "input_snapshot_id": "SNAP-CLI",
        "input_snapshot_digests": {"spy": "spy-digest"},
        "asset": asset,
        "start_date": "2019-01-01",
        "end_date": "2019-12-31",
        "versions": FROZEN_VERSIONS.as_dict(),
        "source_provider": "Alpaca",
        "source_feed": "SIP",
        "input_refs": [],
        "output_digests": output_digests,
        "locked_holdout_excluded": True,
        "completion_status": "READY_FOR_COORDINATOR_REVIEW",
    }


def test_validate_manifest_cli_returns_zero_for_clean_manifest(tmp_path):
    artifact = tmp_path / "market-data.csv"
    artifact.write_text("ok\n")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest("URA", {"market-data.csv": digest})))
    assert main(["validate-manifest", str(path)]) == 0


def test_validate_manifest_cli_rejects_locked_holdout(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest("HACK", {})))
    assert main(["validate-manifest", str(path)]) == 2
