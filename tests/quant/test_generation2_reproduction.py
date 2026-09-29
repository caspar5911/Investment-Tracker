"""Tests for the generation-2 deterministic reproduction check (C6).

C6 re-runs the sealed VALIDATION campaign from the legitimate
content-hash-verified research cache snapshot (a fresh process would do the
same via ``main``) and confirms the regenerated report is byte-identical to
the committed sealed report. Because no separate-provider snapshot exists in
this environment, the artifact must record
``independent_source_established: false`` -- the framework may never claim to
resolve the Generation-1 ``INDEPENDENT_SOURCE_SNAPSHOT_MISSING`` limitation.

Pinned behavior:

- ``validation.build_validation_payload`` is the single payload authority and
  byte-matches the file that ``seal_validation_report`` writes;
- ``build_reproduction_report`` confirms byte identity between the sealed
  VALIDATION payload and the freshly reproduced payload;
- a non-identical reproduced payload is NOT sealable
  (``REPRODUCTION_MISMATCH``, fail-closed);
- the sealed report is exclusive (``REPRODUCTION_EXISTS``) and self-verifying
  (``REPRODUCTION_TAMPERED``);
- the end-to-end orchestrator chains the TRAIN report, VALIDATION report, and
  survivor-freeze hashes into the sealed reproduction report.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from types import SimpleNamespace

import pandas as pd
import pytest

from investment_tracker.quant.generation2 import campaign, survivor_freeze, validation
from investment_tracker.quant.generation2.campaign import CampaignError, canonical_bytes
from investment_tracker.quant.generation2.grid import (
    GridCandidate,
    RESEARCH_SYMBOLS,
    canonical_grid_manifest,
)
from investment_tracker.quant.generation2.reproduction import (
    REPRODUCTION_CONFIRMED,
    REPRODUCTION_REPORT_NAME,
    REPRODUCTION_SCHEMA,
    build_reproduction_report,
    default_environment,
    run_reproduction,
    seal_reproduction_report,
    verify_reproduction_report,
)
from investment_tracker.quant.generation2.validation import build_validation_payload

FROZEN_ENTRIES = canonical_grid_manifest()["candidates"]
FROZEN_A = "G2-A|lookback=63|skip=0|top_k=1|rebalance=21"
FROZEN_B = "G2-B|lookback=63|trend_ma=126|top_k=1|rebalance=21"
FRICTION = (0, 3, 25)

COMMITTED_REPRODUCTION = (
    validation._repo_root()
    / "data"
    / "governance"
    / "generation2-campaign"
    / REPRODUCTION_REPORT_NAME
)


def _candidate(candidate_id: str) -> GridCandidate:
    for entry in FROZEN_ENTRIES:
        if entry["candidate_id"] == candidate_id:
            data = dict(entry)
            data.pop("candidate_id")
            return GridCandidate(candidate_id=candidate_id, **data)
    raise LookupError(candidate_id)


def _bars(n: int = 2300) -> dict[str, pd.DataFrame]:
    """Deterministic drift-dominant bars (same shape as the C4 tests)."""
    import math

    index = pd.bdate_range("2014-01-01", periods=n, tz="UTC")
    bars: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(RESEARCH_SYMBOLS):
        values = [
            100.0 + 0.15 * i + 0.1 * offset + 4.0 * math.sin(i / 20.0)
            for i in range(n)
        ]
        bars[symbol] = pd.DataFrame({"open": values, "close": values}, index=index)
    return bars


def _snapshot_symbols() -> dict[str, str]:
    return {
        symbol: hashlib.sha256(symbol.encode("utf-8")).hexdigest()
        for symbol in RESEARCH_SYMBOLS
    }


_PROVENANCE_SHA = "e" * 64
_ENVIRONMENT = {"python": "3.13", "pandas": "2.2", "numpy": "2.1"}


class _FakeBoundary:
    """Stands in for ResearchBoundary so the orchestrator is unit-testable."""

    symbols = RESEARCH_SYMBOLS
    provenance = SimpleNamespace(provenance_sha256=_PROVENANCE_SHA)

    def validation_bars(self) -> dict[str, pd.DataFrame]:
        return _bars()

    def content_sha256(self, symbol: str) -> str:
        return hashlib.sha256(symbol.encode("utf-8")).hexdigest()


def _sealed_campaign(evidence_root: pathlib.Path) -> dict:
    """Seal a small (2-candidate) TRAIN + VALIDATION chain under ``evidence_root``."""
    bars = _bars()
    evidence = campaign.run_train_campaign(
        bars,
        (_candidate(FROZEN_A), _candidate(FROZEN_B)),
        friction_cases=FRICTION,
    )
    campaign.seal_train_campaign(evidence, evidence_root, friction_cases=FRICTION)
    train_payload = campaign.verify_train_report(evidence_root / campaign.REPORT_NAME)
    result = validation.run_validation_campaign(train_payload, bars, FRICTION)
    validation.seal_validation_report(result, evidence_root, friction_cases=FRICTION)
    return result


# ---------------------------------------------------------------------------
# build_validation_payload (C6 refactor of the C4 payload authority)
# ---------------------------------------------------------------------------


def test_build_validation_payload_byte_matches_sealed_file(tmp_path: object) -> None:
    evidence_root = pathlib.Path(tmp_path) / "evidence"
    result = _sealed_campaign(evidence_root)
    payload = build_validation_payload(result, FRICTION)
    sealed_file = evidence_root / validation.REPORT_NAME
    assert canonical_bytes(payload) == sealed_file.read_bytes()
    assert json.loads(sealed_file.read_bytes().decode("utf-8")) == payload
    # The sealed report must still verify through the C4 authority.
    assert validation.verify_validation_report(sealed_file)["report_sha256"] == payload[
        "report_sha256"
    ]


# ---------------------------------------------------------------------------
# build_reproduction_report
# ---------------------------------------------------------------------------


def test_build_reproduction_report_confirms_match(tmp_path: object) -> None:
    evidence_root = pathlib.Path(tmp_path) / "evidence"
    result = _sealed_campaign(evidence_root)
    sealed = validation.verify_validation_report(evidence_root / validation.REPORT_NAME)
    reproduced = build_validation_payload(result, FRICTION)
    payload = build_reproduction_report(
        sealed,
        reproduced,
        snapshot_symbols=_snapshot_symbols(),
        research_boundary_provenance_sha256=_PROVENANCE_SHA,
        environment=_ENVIRONMENT,
        survivor_freeze_sha256="d" * 64,
    )
    assert payload["schema_version"] == REPRODUCTION_SCHEMA
    assert payload["status"] == REPRODUCTION_CONFIRMED
    assert payload["validation_report_sha256"] == sealed["report_sha256"]
    assert payload["train_report_sha256"] == sealed["train_report_sha256"]
    assert payload["survivor"] == sealed["survivor"]
    assert payload["survivor_freeze_sha256"] == "d" * 64
    assert payload["snapshot_symbols"] == _snapshot_symbols()
    assert payload["research_boundary_provenance_sha256"] == _PROVENANCE_SHA
    # No separate-provider snapshot exists: independence must stay unclaimed.
    assert payload["independent_source_established"] is False
    assert "INDEPENDENT_SOURCE_SNAPSHOT_MISSING" in payload["independent_source_note"]
    assert "report_sha256" not in payload


def test_reproduction_mismatch_is_not_sealable(tmp_path: object) -> None:
    evidence_root = pathlib.Path(tmp_path) / "evidence"
    result = _sealed_campaign(evidence_root)
    sealed = validation.verify_validation_report(evidence_root / validation.REPORT_NAME)
    reproduced = build_validation_payload(result, FRICTION)
    # Payload stores candidate records in shortlist order (a list).
    reproduced["candidates"][0]["friction_cases"]["3"]["sharpe"]["value"] = 99.0
    with pytest.raises(CampaignError) as excinfo:
        build_reproduction_report(
            sealed,
            reproduced,
            snapshot_symbols=_snapshot_symbols(),
            research_boundary_provenance_sha256=_PROVENANCE_SHA,
            environment=_ENVIRONMENT,
        )
    assert excinfo.value.code == "REPRODUCTION_MISMATCH"


def test_reproduction_survivor_freeze_hash_is_optional(tmp_path: object) -> None:
    evidence_root = pathlib.Path(tmp_path) / "evidence"
    result = _sealed_campaign(evidence_root)
    sealed = validation.verify_validation_report(evidence_root / validation.REPORT_NAME)
    payload = build_reproduction_report(
        sealed,
        build_validation_payload(result, FRICTION),
        snapshot_symbols=_snapshot_symbols(),
        research_boundary_provenance_sha256=_PROVENANCE_SHA,
        environment=_ENVIRONMENT,
    )
    assert payload["survivor_freeze_sha256"] is None


# ---------------------------------------------------------------------------
# seal / verify round-trip
# ---------------------------------------------------------------------------


def _reproduction_payload(tmp_path: object) -> dict:
    evidence_root = pathlib.Path(tmp_path) / "evidence"
    result = _sealed_campaign(evidence_root)
    sealed = validation.verify_validation_report(evidence_root / validation.REPORT_NAME)
    return build_reproduction_report(
        sealed,
        build_validation_payload(result, FRICTION),
        snapshot_symbols=_snapshot_symbols(),
        research_boundary_provenance_sha256=_PROVENANCE_SHA,
        environment=_ENVIRONMENT,
    )


def test_seal_then_verify_round_trip(tmp_path: object) -> None:
    payload = _reproduction_payload(tmp_path)
    root = pathlib.Path(tmp_path) / "reproduction"
    sealed = seal_reproduction_report(payload, root)
    assert "report_sha256" in sealed
    verified = verify_reproduction_report(root / REPRODUCTION_REPORT_NAME)
    assert verified == sealed
    assert verified["status"] == REPRODUCTION_CONFIRMED
    # Duplicate seal fails closed.
    with pytest.raises(CampaignError) as excinfo:
        seal_reproduction_report(payload, root)
    assert excinfo.value.code == "REPRODUCTION_EXISTS"


def test_verify_detects_tampered_snapshot_hash(tmp_path: object) -> None:
    payload = _reproduction_payload(tmp_path)
    root = pathlib.Path(tmp_path) / "reproduction"
    seal_reproduction_report(payload, root)
    report = root / REPRODUCTION_REPORT_NAME
    tampered = json.loads(report.read_text(encoding="utf-8"))
    tampered["snapshot_symbols"]["SPY"] = "f" * 64
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_reproduction_report(report)
    assert excinfo.value.code == "REPRODUCTION_TAMPERED"


def test_verify_detects_tampered_independence_claim(tmp_path: object) -> None:
    payload = _reproduction_payload(tmp_path)
    root = pathlib.Path(tmp_path) / "reproduction"
    seal_reproduction_report(payload, root)
    report = root / REPRODUCTION_REPORT_NAME
    tampered = json.loads(report.read_text(encoding="utf-8"))
    tampered["independent_source_established"] = True
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_reproduction_report(report)
    assert excinfo.value.code == "REPRODUCTION_TAMPERED"


# ---------------------------------------------------------------------------
# End-to-end orchestrator
# ---------------------------------------------------------------------------


def test_run_reproduction_end_to_end(tmp_path: object) -> None:
    evidence_root = pathlib.Path(tmp_path) / "evidence"
    _sealed_campaign(evidence_root)
    # Chain the survivor-freeze artifact into the evidence root.
    train_payload = campaign.verify_train_report(evidence_root / campaign.REPORT_NAME)
    validation_payload = validation.verify_validation_report(
        evidence_root / validation.REPORT_NAME
    )
    survivor_freeze.seal_survivor_freeze(
        survivor_freeze.build_survivor_freeze(validation_payload, train_payload),
        evidence_root,
    )

    sealed = run_reproduction(evidence_root, boundary=_FakeBoundary())
    assert sealed["status"] == REPRODUCTION_CONFIRMED
    assert sealed["survivor_freeze_sha256"] == survivor_freeze.verify_survivor_freeze(
        evidence_root / survivor_freeze.FREEZE_REPORT_NAME
    )["report_sha256"]
    assert sealed["validation_report_sha256"] == validation_payload["report_sha256"]
    assert sealed["snapshot_symbols"] == _snapshot_symbols()
    verify_reproduction_report(evidence_root / REPRODUCTION_REPORT_NAME)

    # Re-running in a different directory must seal an independent copy whose
    # content hashes match: reproduction is deterministic.
    alt_root = pathlib.Path(tmp_path) / "alt"
    alt_root.mkdir()
    for name in (
        campaign.REPORT_NAME,
        validation.REPORT_NAME,
        survivor_freeze.FREEZE_REPORT_NAME,
    ):
        (alt_root / name).write_bytes((evidence_root / name).read_bytes())
    alt_sealed = run_reproduction(alt_root, boundary=_FakeBoundary())
    assert alt_sealed["report_sha256"] == sealed["report_sha256"]


def test_default_environment_records_runtime_versions() -> None:
    environment = default_environment()
    assert set(environment) == {"python", "pandas", "numpy"}
    assert all(isinstance(value, str) and value for value in environment.values())


@pytest.mark.skipif(
    not COMMITTED_REPRODUCTION.exists(),
    reason="committed reproduction artifact not present yet",
)
def test_verify_committed_reproduction() -> None:
    payload = verify_reproduction_report(COMMITTED_REPRODUCTION)
    assert payload["schema_version"] == REPRODUCTION_SCHEMA
    assert payload["status"] == REPRODUCTION_CONFIRMED
    assert payload["independent_source_established"] is False
    campaign_root = COMMITTED_REPRODUCTION.parent
    assert payload["validation_report_sha256"] == validation.verify_validation_report(
        campaign_root / validation.REPORT_NAME
    )["report_sha256"]
    assert payload["train_report_sha256"] == campaign.verify_train_report(
        campaign_root / campaign.REPORT_NAME
    )["report_sha256"]
