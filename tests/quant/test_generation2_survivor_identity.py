"""Tests for the generation-2 survivor implementation + binding identity.

``survivor_identity`` freezes two additive identity values that the sealed
survivor-freeze artifact does not itself pin: ``implementation_sha256`` (the
content identity of the exact five execution-semantic source modules) and
``binding_sha256`` (the content identity of the frozen survivor's binding plus
the chained self-hashes of all six prior sealed campaign artifacts).

These tests mirror the survivor-freeze conventions: tampering a stored field
without re-signing trips the self-hash gate (``SURVIVOR_IDENTITY_TAMPERED``);
source-file byte drift is detected independently of the identity's own
self-hash (``SURVIVOR_IDENTITY_IMPLEMENTATION_DRIFT``); sealing an existing
identity is refused (``SURVIVOR_IDENTITY_EXISTS``); and the sealed identity is
self-verifying against the exact current frozen survivor.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from investment_tracker.quant.generation2 import survivor_identity
from investment_tracker.quant.generation2.campaign import CampaignError, content_sha256
from investment_tracker.quant.generation2.survivor_identity import (
    IMPLEMENTATION_SOURCE_FILES,
    IDENTITY_REPORT_NAME,
    SURVIVOR_IDENTITY_SCHEMA,
    SURVIVOR_IDENTITY_STATUS,
    _implementation_payload,
    build_survivor_identity,
    seal_survivor_identity,
    seal_survivor_identity_from_evidence,
    verify_survivor_identity,
)
from investment_tracker.quant.generation2.validation import frozen_candidate_by_id

REAL_REPO = survivor_identity._repo_root()
REAL_EVIDENCE = REAL_REPO / "data" / "governance" / "generation2-campaign"
REAL_GRID = REAL_REPO / "data" / "governance" / "generation2-grid-manifest.json"

SRC_REL = "src/investment_tracker/quant/generation2"
ARTIFACT_NAMES = (
    "train-campaign-report.json",
    "validation-report.json",
    "survivor-freeze.json",
    "reproduction-report.json",
    "survivor-rehearsal-report.json",
)
SOURCE_FILE_NAMES = ("grid.py", "strategy.py", "accounting.py", "metrics.py", "performance.py")

EXPECTED_CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
EXPECTED_FAMILY = "G2-A"
EXPECTED_BINDING = frozen_candidate_by_id(EXPECTED_CANDIDATE_ID).to_manifest_dict()

EXCLUDED_SOURCE_NAMES = (
    "validation.py",
    "campaign.py",
    "reproduction.py",
    "survivor_rehearsal.py",
    "phase7_entry.py",
)

COMMITTED_IDENTITY = (
    survivor_identity._repo_root()
    / "data"
    / "governance"
    / "generation2-campaign"
    / IDENTITY_REPORT_NAME
)


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Byte-identical copy of the five source modules and six sealed artifacts."""
    src_dir = tmp_path / SRC_REL
    src_dir.mkdir(parents=True)
    for name in SOURCE_FILE_NAMES:
        shutil.copyfile(REAL_REPO / SRC_REL / name, src_dir / name)
    evidence = tmp_path / "data" / "governance" / "generation2-campaign"
    evidence.mkdir(parents=True)
    for name in ARTIFACT_NAMES:
        shutil.copyfile(REAL_EVIDENCE / name, evidence / name)
    shutil.copyfile(REAL_GRID, tmp_path / "data" / "governance" / "generation2-grid-manifest.json")
    return tmp_path


def _evidence(repo: Path) -> Path:
    return repo / "data" / "governance" / "generation2-campaign"


def _source(repo: Path, name: str) -> Path:
    return repo / SRC_REL / name


def _seal(repo: Path) -> Path:
    seal_survivor_identity_from_evidence(_evidence(repo), repo)
    return _evidence(repo) / IDENTITY_REPORT_NAME


def _code(raiser) -> str:
    try:
        raiser()
    except CampaignError as exc:
        return exc.code
    raise AssertionError("expected CampaignError was not raised")


def _all_real_present() -> bool:
    return all((REAL_EVIDENCE / name).exists() for name in ARTIFACT_NAMES) and REAL_GRID.exists()


# ---------------------------------------------------------------------------
# build / seal: exact current survivor
# ---------------------------------------------------------------------------


def test_exact_current_survivor_seals(tmp_repo: Path) -> None:
    payload = build_survivor_identity(_evidence(tmp_repo), tmp_repo)
    assert payload["schema_version"] == SURVIVOR_IDENTITY_SCHEMA
    assert payload["status"] == SURVIVOR_IDENTITY_STATUS
    assert payload["generation"] == "GENERATION_2"
    assert payload["candidate_id"] == EXPECTED_CANDIDATE_ID
    assert payload["family"] == EXPECTED_FAMILY
    assert payload["candidate_binding"] == EXPECTED_BINDING
    assert payload["implementation_surface"]["schema_version"] == (
        "GENERATION2-IMPLEMENTATION-SURFACE-v1"
    )
    assert payload["implementation_surface"]["interface"] == (
        "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1"
    )
    # Self-excluding hash is only added by seal.
    assert "report_sha256" not in payload


def test_identity_artifact_verifies_round_trip(tmp_repo: Path) -> None:
    sealed = seal_survivor_identity_from_evidence(_evidence(tmp_repo), tmp_repo)
    assert "report_sha256" in sealed
    report = _evidence(tmp_repo) / IDENTITY_REPORT_NAME
    assert report.exists()
    verified = verify_survivor_identity(_evidence(tmp_repo), tmp_repo)
    assert verified == sealed
    assert verified["candidate_id"] == EXPECTED_CANDIDATE_ID
    assert verified["binding_sha256"] == sealed["binding_sha256"]


def test_implementation_surface_is_exactly_five_execution_files(tmp_repo: Path) -> None:
    payload = build_survivor_identity(_evidence(tmp_repo), tmp_repo)
    keys = set(payload["implementation_surface"]["source_sha256"])
    assert keys == set(IMPLEMENTATION_SOURCE_FILES)
    for name in EXCLUDED_SOURCE_NAMES:
        assert not any(key.endswith(name) for key in keys)
    # Each recorded digest is a 64-char lowercase sha256 of the real source bytes.
    for key, digest in payload["implementation_surface"]["source_sha256"].items():
        assert len(digest) == 64 and digest == digest.lower()
        assert digest == _sha256(tmp_repo / key)


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# implementation-surface sensitivity
# ---------------------------------------------------------------------------


def test_implementation_hash_changes_when_a_source_byte_changes(tmp_repo: Path) -> None:
    before = content_sha256(_implementation_payload(tmp_repo))
    target = _source(tmp_repo, "strategy.py")
    target.write_bytes(target.read_bytes() + b"# byte\n")
    after = content_sha256(_implementation_payload(tmp_repo))
    assert before != after


# ---------------------------------------------------------------------------
# source drift is detected independently of the identity's own self-hash
# ---------------------------------------------------------------------------


def test_changed_strategy_source_fails(tmp_repo: Path) -> None:
    _seal(tmp_repo)
    target = _source(tmp_repo, "strategy.py")
    target.write_bytes(target.read_bytes() + b"# drifted\n")
    assert _code(lambda: verify_survivor_identity(_evidence(tmp_repo), tmp_repo)) == (
        "SURVIVOR_IDENTITY_IMPLEMENTATION_DRIFT"
    )


def test_changed_accounting_source_fails(tmp_repo: Path) -> None:
    _seal(tmp_repo)
    target = _source(tmp_repo, "accounting.py")
    target.write_bytes(target.read_bytes() + b"# drifted\n")
    assert _code(lambda: verify_survivor_identity(_evidence(tmp_repo), tmp_repo)) == (
        "SURVIVOR_IDENTITY_IMPLEMENTATION_DRIFT"
    )


# ---------------------------------------------------------------------------
# tamper a stored field -> self-hash gate trips (SURVIVOR_IDENTITY_TAMPERED)
# ---------------------------------------------------------------------------


def _tamper_report(repo: Path, mutate) -> None:
    report = _evidence(repo) / IDENTITY_REPORT_NAME
    data = json.loads(report.read_text(encoding="utf-8"))
    mutate(data)
    report.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize(
    "key, replacement",
    [
        ("candidate_id", "G2-B|lookback=42|skip=1|top_k=1|rebalance=21"),
        ("candidate_binding", {**EXPECTED_BINDING, "lookback": 42}),
        ("implementation_sha256", "0" * 64),
        ("binding_sha256", "f" * 64),
        ("train_report_sha256", "a" * 64),
        ("validation_report_sha256", "b" * 64),
        ("survivor_freeze_sha256", "c" * 64),
        ("reproduction_report_sha256", "d" * 64),
        ("survivor_rehearsal_sha256", "e" * 64),
    ],
)
def test_tampered_field_fails_self_hash(tmp_repo: Path, key: str, replacement: object) -> None:
    _seal(tmp_repo)
    _tamper_report(tmp_repo, lambda data: data.__setitem__(key, replacement))
    assert _code(lambda: verify_survivor_identity(_evidence(tmp_repo), tmp_repo)) == (
        "SURVIVOR_IDENTITY_TAMPERED"
    )


def test_second_seal_refused(tmp_repo: Path) -> None:
    evidence = _evidence(tmp_repo)
    payload = build_survivor_identity(evidence, tmp_repo)
    seal_survivor_identity(payload, evidence)
    assert _code(lambda: seal_survivor_identity(payload, evidence)) == (
        "SURVIVOR_IDENTITY_EXISTS"
    )


def test_self_hash_is_canonical_and_corruption_detected(tmp_repo: Path) -> None:
    sealed = seal_survivor_identity_from_evidence(_evidence(tmp_repo), tmp_repo)
    report = _evidence(tmp_repo) / IDENTITY_REPORT_NAME
    payload = json.loads(report.read_bytes().decode("utf-8"))
    check = {key: value for key, value in payload.items() if key != "report_sha256"}
    assert content_sha256(check) == sealed["report_sha256"]
    # A single-byte corruption of the stored self-hash trips the gate.
    claimed = sealed["report_sha256"]
    flipped = ("1" if claimed[0] != "1" else "0") + claimed[1:]
    report.write_text(
        report.read_text(encoding="utf-8").replace(f'"report_sha256":"{claimed}"', f'"report_sha256":"{flipped}"'),
        encoding="utf-8",
    )
    assert _code(lambda: verify_survivor_identity(_evidence(tmp_repo), tmp_repo)) == (
        "SURVIVOR_IDENTITY_TAMPERED"
    )


# ---------------------------------------------------------------------------
# specific-code reachability (re-sign so the self-hash gate passes)
# ---------------------------------------------------------------------------


def _resign(data: dict) -> None:
    """Re-sign a self-excluding payload so the self-hash gate passes."""
    data.pop("report_sha256", None)
    data["report_sha256"] = content_sha256(data)


def test_resealed_implementation_sha_mismatch_is_detectable(tmp_repo: Path) -> None:
    _seal(tmp_repo)
    report = _evidence(tmp_repo) / IDENTITY_REPORT_NAME
    data = json.loads(report.read_text(encoding="utf-8"))
    data["implementation_sha256"] = "1" * 64
    _resign(data)
    report.write_text(json.dumps(data), encoding="utf-8")
    assert _code(lambda: verify_survivor_identity(_evidence(tmp_repo), tmp_repo)) == (
        "SURVIVOR_IDENTITY_IMPLEMENTATION_SHA_MISMATCH"
    )


def test_resealed_binding_sha_mismatch_is_detectable(tmp_repo: Path) -> None:
    _seal(tmp_repo)
    report = _evidence(tmp_repo) / IDENTITY_REPORT_NAME
    data = json.loads(report.read_text(encoding="utf-8"))
    data["binding_sha256"] = "2" * 64
    _resign(data)
    report.write_text(json.dumps(data), encoding="utf-8")
    assert _code(lambda: verify_survivor_identity(_evidence(tmp_repo), tmp_repo)) == (
        "SURVIVOR_IDENTITY_BINDING_SHA_MISMATCH"
    )


def test_resealed_candidate_mismatch_is_detectable(tmp_repo: Path) -> None:
    _seal(tmp_repo)
    report = _evidence(tmp_repo) / IDENTITY_REPORT_NAME
    data = json.loads(report.read_text(encoding="utf-8"))
    data["candidate_id"] = "G2-X|nonsense=1"
    _resign(data)
    report.write_text(json.dumps(data), encoding="utf-8")
    assert _code(lambda: verify_survivor_identity(_evidence(tmp_repo), tmp_repo)) == (
        "SURVIVOR_IDENTITY_CANDIDATE_MISMATCH"
    )


@pytest.mark.skipif(not (COMMITTED_IDENTITY.exists() and _all_real_present()), reason="committed artifacts not present yet")
def test_verify_committed_identity() -> None:
    payload = verify_survivor_identity(
        survivor_identity._repo_root() / "data" / "governance" / "generation2-campaign",
        survivor_identity._repo_root(),
    )
    assert payload["status"] == SURVIVOR_IDENTITY_STATUS
    assert payload["candidate_id"] == EXPECTED_CANDIDATE_ID
