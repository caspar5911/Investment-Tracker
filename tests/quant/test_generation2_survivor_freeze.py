"""Tests for the generation-2 survivor freeze artifact (C5).

The survivor freeze is the explicit Gen-2 governance record that names the
single VALIDATION survivor and its frozen grid binding, and chains the
content hashes of the sealed TRAIN and VALIDATION reports into a new
self-verifying, content-addressed artifact. It fails closed on:

- no VALIDATION survivor (``NO_CREDIBLE_GENERATION2_CANDIDATE``);
- a survivor id that does not bind to the frozen grid;
- any hash/binding tampering (``SURVIVOR_FREEZE_TAMPERED``);
- a hash mismatch between the TRAIN report and the VALIDATION report;
- an already-existing freeze artifact (``SURVIVOR_FREEZE_EXISTS``).
"""

from __future__ import annotations

import json
import pathlib

import pytest

from investment_tracker.quant.generation2 import survivor_freeze
from investment_tracker.quant.generation2.campaign import CampaignError
from investment_tracker.quant.generation2.grid import canonical_grid_manifest
from investment_tracker.quant.generation2.validation import (
    STATUS_NO_CREDIBLE,
    STATUS_SURVIVOR,
)
from investment_tracker.quant.generation2.survivor_freeze import (
    FREEZE_REPORT_NAME,
    SURVIVOR_FREEZE_SCHEMA,
    SURVIVOR_FREEZE_STATUS,
    build_survivor_freeze,
    seal_survivor_freeze,
    verify_survivor_freeze,
)

FROZEN_ENTRIES = canonical_grid_manifest()["candidates"]
SURVIVOR_ID = FROZEN_ENTRIES[0]["candidate_id"]
SURVIVOR_FAMILY = FROZEN_ENTRIES[0]["family"]
OTHER_ID = FROZEN_ENTRIES[1]["candidate_id"]

TRAIN_SHA = "a" * 64
VALIDATION_SHA = "b" * 64
GRID_SHA = "c" * 64

COMMITTED_FREEZE = (
    survivor_freeze._repo_root()
    / "data"
    / "governance"
    / "generation2-campaign"
    / FREEZE_REPORT_NAME
)


def _validation_payload(status: str = STATUS_SURVIVOR, survivor: str = SURVIVOR_ID) -> dict:
    return {
        "schema_version": "GENERATION2-VALIDATION-v1",
        "status": status,
        "grid_manifest_sha256": GRID_SHA,
        "train_report_sha256": TRAIN_SHA,
        "friction_cases_bps": [0, 3, 10, 25, 50],
        "shortlist": [SURVIVOR_ID, OTHER_ID],
        "survivor": survivor,
        "survivor_selection_order": [
            "higher VALIDATION Sharpe",
            "higher VALIDATION CAGR",
            "smaller max-drawdown magnitude",
            "lower annualized one-way turnover",
            "ascending candidate_id",
        ],
        "candidates": [],
        "report_sha256": VALIDATION_SHA,
    }


def _train_payload() -> dict:
    return {"report_sha256": TRAIN_SHA, "shortlist": {"G2-A": [SURVIVOR_ID]}}


# ---------------------------------------------------------------------------
# build_survivor_freeze
# ---------------------------------------------------------------------------


def test_build_freeze_names_survivor_and_chains_hashes() -> None:
    payload = build_survivor_freeze(_validation_payload(), _train_payload())
    assert payload["schema_version"] == SURVIVOR_FREEZE_SCHEMA
    assert payload["status"] == SURVIVOR_FREEZE_STATUS
    assert payload["survivor"]["candidate_id"] == SURVIVOR_ID
    assert payload["survivor"]["family"] == SURVIVOR_FAMILY
    entry = next(e for e in FROZEN_ENTRIES if e["candidate_id"] == SURVIVOR_ID)
    assert payload["survivor"]["binding"] == entry
    assert payload["train_report_sha256"] == TRAIN_SHA
    assert payload["validation_report_sha256"] == VALIDATION_SHA
    assert payload["grid_manifest_sha256"] == GRID_SHA
    assert "report_sha256" not in payload


def test_build_freeze_requires_a_survivor() -> None:
    with pytest.raises(CampaignError) as excinfo:
        build_survivor_freeze(
            _validation_payload(status=STATUS_NO_CREDIBLE, survivor=None),
            _train_payload(),
        )
    assert excinfo.value.code == "SURVIVOR_FREEZE_NO_SURVIVOR"


def test_build_freeze_rejects_non_grid_survivor() -> None:
    with pytest.raises(CampaignError) as excinfo:
        build_survivor_freeze(
            _validation_payload(survivor="G2-X|nonsense=1"), _train_payload()
        )
    assert excinfo.value.code == "SURVIVOR_FREEZE_SURVIVOR_NOT_IN_FROZEN_GRID"


def test_build_freeze_rejects_train_hash_mismatch() -> None:
    train = {"report_sha256": "d" * 64, "shortlist": {}}
    with pytest.raises(CampaignError) as excinfo:
        build_survivor_freeze(_validation_payload(), train)
    assert excinfo.value.code == "SURVIVOR_FREEZE_TRAIN_HASH_MISMATCH"


def test_build_freeze_rejects_non_hex_validation_hash() -> None:
    payload = _validation_payload()
    payload["report_sha256"] = "nothash"
    with pytest.raises(CampaignError) as excinfo:
        build_survivor_freeze(payload, _train_payload())
    assert excinfo.value.code == "SURVIVOR_FREEZE_VALIDATION_HASH_INVALID"


# ---------------------------------------------------------------------------
# seal / verify round-trip
# ---------------------------------------------------------------------------


def test_seal_then_verify_round_trip(tmp_path: object) -> None:
    payload = build_survivor_freeze(_validation_payload(), _train_payload())
    sealed = seal_survivor_freeze(payload, pathlib.Path(tmp_path))
    assert "report_sha256" in sealed
    report = pathlib.Path(tmp_path) / FREEZE_REPORT_NAME
    assert report.exists()
    verified = verify_survivor_freeze(report)
    assert verified == sealed
    assert verified["survivor"]["candidate_id"] == SURVIVOR_ID


def test_seal_refuses_to_overwrite(tmp_path: object) -> None:
    payload = build_survivor_freeze(_validation_payload(), _train_payload())
    seal_survivor_freeze(payload, pathlib.Path(tmp_path))
    with pytest.raises(CampaignError) as excinfo:
        seal_survivor_freeze(payload, pathlib.Path(tmp_path))
    assert excinfo.value.code == "SURVIVOR_FREEZE_EXISTS"


def test_verify_detects_tampered_survivor(tmp_path: object) -> None:
    payload = build_survivor_freeze(_validation_payload(), _train_payload())
    seal_survivor_freeze(payload, pathlib.Path(tmp_path))
    report = pathlib.Path(tmp_path) / FREEZE_REPORT_NAME
    tampered = json.loads(report.read_text(encoding="utf-8"))
    tampered["survivor"]["candidate_id"] = OTHER_ID
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_survivor_freeze(report)
    assert excinfo.value.code == "SURVIVOR_FREEZE_TAMPERED"


def test_verify_detects_content_hash_mutation(tmp_path: object) -> None:
    payload = build_survivor_freeze(_validation_payload(), _train_payload())
    seal_survivor_freeze(payload, pathlib.Path(tmp_path))
    report = pathlib.Path(tmp_path) / FREEZE_REPORT_NAME
    tampered = json.loads(report.read_text(encoding="utf-8"))
    tampered["validation_report_sha256"] = "e" * 64
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_survivor_freeze(report)
    assert excinfo.value.code == "SURVIVOR_FREEZE_TAMPERED"


def test_verify_detects_unknown_survivor_id(tmp_path: object) -> None:
    payload = build_survivor_freeze(_validation_payload(), _train_payload())
    sealed = seal_survivor_freeze(payload, pathlib.Path(tmp_path))
    report = pathlib.Path(tmp_path) / FREEZE_REPORT_NAME
    tampered = json.loads(report.read_text(encoding="utf-8"))
    tampered["survivor"] = {"candidate_id": "G2-X|nonsense=1", "family": "G2-X"}
    # Recompute the hash so the content check passes and the binding check fires.
    claimed = tampered.pop("report_sha256", None)
    del sealed
    from investment_tracker.quant.generation2.campaign import content_sha256

    tampered["report_sha256"] = content_sha256(tampered)
    assert claimed is not None
    report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignError) as excinfo:
        verify_survivor_freeze(report)
    assert excinfo.value.code == "SURVIVOR_FREEZE_SURVIVOR_NOT_IN_FROZEN_GRID"


@pytest.mark.skipif(
    not COMMITTED_FREEZE.exists(),
    reason="committed survivor-freeze artifact not present yet",
)
def test_verify_committed_freeze() -> None:
    payload = verify_survivor_freeze(COMMITTED_FREEZE)
    assert payload["status"] == SURVIVOR_FREEZE_STATUS
    assert payload["survivor"]["candidate_id"] in {
        e["candidate_id"] for e in FROZEN_ENTRIES
    }
