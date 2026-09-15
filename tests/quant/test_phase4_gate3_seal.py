from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
import subprocess

import pyarrow.parquet as pq
import pytest

from investment_tracker.quant.phase4.gate3.artifacts import Gate3ArtifactStore
from investment_tracker.quant.phase4.gate3.inputs import load_frozen_authority_inputs
from investment_tracker.quant.phase4.gate3.models import Gate3AuthorityError
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
)
import investment_tracker.quant.phase4.gate3.seal as seal_module
from investment_tracker.quant.phase4.gate3.seal import (
    GATE1_MANIFEST_IDENTITY,
    GATE2_MANIFEST_IDENTITY,
    load_and_verify_gate3_authority,
    preflight_gate3,
    seal_gate3_authorities,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_seal_requires_committed_source_revision() -> None:
    with pytest.raises(Gate3AuthorityError, match="SOURCE_REVISION_INVALID"):
        seal_gate3_authorities(REPOSITORY_ROOT, source_revision="not-a-commit")


def test_missing_authority_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(Gate3AuthorityError, match="AUTHORITY_MANIFEST_MISSING"):
        load_and_verify_gate3_authority(tmp_path, "0" * 64)


def test_gate2_identity_is_exact_and_not_discovered_as_latest() -> None:
    assert GATE2_MANIFEST_IDENTITY.content_sha256 == (
        "c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6"
    )
    source = inspect.getsource(load_and_verify_gate3_authority).lower()
    assert "mtime" not in source
    assert "glob(" not in source
    assert "rglob(" not in source


def test_preflight_requires_explicit_manifest_digest() -> None:
    signature = inspect.signature(preflight_gate3)
    assert signature.parameters["manifest_content_sha256"].default is inspect.Parameter.empty


def test_gate3_namespace_has_no_campaign_or_trading_surface() -> None:
    import investment_tracker.quant.phase4.gate3 as gate3

    forbidden = {
        "run_campaign", "execute_candidate", "rank_candidates", "select_survivor",
        "place_order", "unlock_trade", "open_trade_context",
    }
    assert forbidden.isdisjoint(set(dir(gate3)))


def test_frozen_loader_handles_timestamp_index_and_requests_no_open_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_columns: list[tuple[str, ...]] = []
    real_read_table = pq.read_table

    def observed_read_table(path: Path, *, columns: list[str]):
        requested_columns.append(tuple(columns))
        return real_read_table(path, columns=columns)

    monkeypatch.setattr(pq, "read_table", observed_read_table)
    frozen = load_frozen_authority_inputs(
        REPOSITORY_ROOT,
        gate1_identity=GATE1_MANIFEST_IDENTITY,
        gate2_identity=GATE2_MANIFEST_IDENTITY,
    )

    assert len(frozen.all_sessions) == 2266
    assert len(frozen.validation_sessions) == 1008
    assert tuple(frozen.close_by_symbol) == (
        "SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP"
    )
    assert requested_columns == [("timestamp", "close")] * 8


def test_unapproved_manifest_references_fail_before_any_dereference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = json.loads(
        (
            REPOSITORY_ROOT
            / "results/phase4/gate3/gate3_authority_manifest/sha256/"
            / "83f4bec6bade156fc3e54534403e901319dc3fb97a26c27b22df2195fef70cfc"
            / "manifest.json"
        ).read_bytes()
    )
    original["gate1_manifest"] = {
        "kind": "phase4_preregistration_manifest",
        "content_sha256": "0" * 64,
        "path": "results/private.json",
        "sha256": artifact_envelope_identity(
            content_sha256="0" * 64,
            kind="phase4_preregistration_manifest",
            path="results/private.json",
        ),
    }
    encoded = canonical_json_bytes(original)
    calls: list[str] = []

    def observed_verify(self: Gate3ArtifactStore, identity):
        calls.append(identity.path)
        if identity.kind == "gate3_authority_manifest":
            return encoded
        raise AssertionError("unapproved artifact dereferenced")

    monkeypatch.setattr(Gate3ArtifactStore, "verify", observed_verify)
    with pytest.raises(Gate3AuthorityError, match="AUTHORITY_DEPENDENCY_MISMATCH"):
        load_and_verify_gate3_authority(tmp_path, "a" * 64)
    assert len(calls) == 1


def test_fold_and_regime_references_require_canonical_content_paths() -> None:
    manifest = seal_module.Gate3AuthorityManifest.model_validate_json(
        (
            REPOSITORY_ROOT
            / "results/phase4/gate3/gate3_authority_manifest/sha256/"
            / "83f4bec6bade156fc3e54534403e901319dc3fb97a26c27b22df2195fef70cfc"
            / "manifest.json"
        ).read_bytes()
    )
    manifest = manifest.model_copy(
        update={
            "supersedes_manifest_content_sha256": (
                seal_module.SUPERSEDED_MANIFEST_CONTENT_SHA256
            )
        }
    )
    copied_path = "results/phase4/gate3/copied/authority.json"
    copied = manifest.fold_authority.model_copy(
        update={
            "path": copied_path,
            "sha256": artifact_envelope_identity(
                content_sha256=manifest.fold_authority.content_sha256,
                kind="fold_authority",
                path=copied_path,
            ),
        }
    )
    mutated = manifest.model_copy(update={"fold_authority": copied})
    with pytest.raises(Gate3AuthorityError, match="AUTHORITY_REFERENCE_INVALID"):
        seal_module.validate_gate3_manifest_references(mutated)


def _create_junction(link: Path, target: Path) -> None:
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.skip(f"junction creation unavailable: {completed.stderr}")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction coverage")
def test_gate3_artifact_root_rejects_windows_junction(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    external = tmp_path / "external-results"
    external.mkdir()
    junction = repository / "results"
    _create_junction(junction, external)
    try:
        with pytest.raises(Gate3AuthorityError, match="ARTIFACT_PATH_INVALID"):
            Gate3ArtifactStore(repository)
    finally:
        junction.rmdir()
