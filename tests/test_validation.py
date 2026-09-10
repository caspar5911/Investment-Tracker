import hashlib
import json
from datetime import date

from investment_tracker.governance import FROZEN_VERSIONS
from investment_tracker.identity import canonical_bar_key, raw_digest_token
from investment_tracker.validation import validate_manifest_files, validate_market_bars


def market_row(asset="URA", day=date(2018, 1, 2)):
    row = {
        "asset": asset,
        "bar_date": day.isoformat(),
        "open_raw": 15.14,
        "high_raw": 15.74,
        "low_raw": 15.12,
        "close_raw": 15.68,
        "volume_raw": 609218,
        "trade_count_raw": 2530,
        "vwap_raw": 15.495505,
        "bar_key": canonical_bar_key(asset, day),
        "source_digest": raw_digest_token(asset, day, 15.14, 15.74, 15.12, 15.68, 609218, 2530, 15.495505),
        "range_usable": True,
        "close_usable": True,
    }
    return row


def test_market_bar_validation_reports_clean_invariants():
    row1 = market_row(day=date(2018, 1, 2))
    row2 = market_row(day=date(2018, 1, 3))
    report = validate_market_bars([row1, row2], {date(2018, 1, 2), date(2018, 1, 3)})
    assert report.ok is True
    assert report.counts == {
        "rows": 2,
        "unique_dates": 2,
        "unique_keys": 2,
        "close_usable": 2,
        "range_usable": 2,
        "benchmark_mismatches": 0,
    }


def test_market_bar_validation_rejects_duplicate_and_bad_digest():
    row = market_row()
    duplicate_report = validate_market_bars([row, dict(row)], {date(2018, 1, 2)})
    assert duplicate_report.ok is False
    assert any("duplicate bar_key" in error for error in duplicate_report.errors)

    bad = dict(row)
    bad["source_digest"] = "wrong"
    bad_report = validate_market_bars([bad], {date(2018, 1, 2)})
    assert bad_report.ok is False
    assert any("source_digest mismatch" in error for error in bad_report.errors)


def manifest_payload(output_digests):
    return {
        "role": "URA",
        "run_id": "WORKER-1",
        "input_snapshot_id": "SNAP-1",
        "input_snapshot_digests": {"spy": "spy-digest"},
        "asset": "URA",
        "start_date": "2018-01-02",
        "end_date": "2018-12-31",
        "versions": FROZEN_VERSIONS.as_dict(),
        "source_provider": "Alpaca",
        "source_feed": "SIP",
        "input_refs": ["Phase Matrix URA 2018"],
        "output_digests": output_digests,
        "locked_holdout_excluded": True,
        "completion_status": "READY_FOR_COORDINATOR_REVIEW",
    }


def test_manifest_file_digests_are_verified(tmp_path):
    artifact = tmp_path / "market-data.csv"
    artifact.write_text("asset,bar_date\nURA,2018-01-02\n")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload({"market-data.csv": digest})))

    report = validate_manifest_files(manifest_path)
    assert report.ok is True
    assert report.counts["verified_files"] == 1

    artifact.write_text("corrupted")
    report = validate_manifest_files(manifest_path)
    assert report.ok is False
    assert any("digest mismatch" in error for error in report.errors)


def test_manifest_with_zero_output_evidence_fails_closed(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload({})))
    report = validate_manifest_files(manifest_path)
    assert report.ok is False
    assert any("no output evidence" in error for error in report.errors)
