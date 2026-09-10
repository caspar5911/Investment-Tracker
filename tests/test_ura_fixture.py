import json
from datetime import date
from pathlib import Path

from investment_tracker.validation import validate_market_bars


FIXTURE = Path(__file__).parent / "fixtures" / "ura-2018-sample.json"


def test_live_derived_ura_fixture_matches_canonical_identity_and_spy_dates():
    payload = json.loads(FIXTURE.read_text())
    rows = payload["market_bars"]
    benchmark_dates = {date.fromisoformat(value) for value in payload["spy_dates"]}
    report = validate_market_bars(rows, benchmark_dates)
    assert report.ok is True
    assert report.counts["rows"] == 2
    assert report.counts["benchmark_mismatches"] == 0
    assert report.counts["unique_keys"] == 2
