from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from investment_tracker.quant.phase4.preregistration.artifacts import (
    Gate1ArtifactError,
    Gate1ArtifactStore,
)
from investment_tracker.quant.phase4.preregistration.canonical import (
    canonical_json_bytes,
)


def test_json_artifact_is_canonical_content_addressed_and_verified(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate1ArtifactStore(repository, repository / "results")
    payload = {"z": 2, "a": [True, None]}

    identity = store.write_json("durability_policy", "policy.json", payload)
    expected = canonical_json_bytes(payload)
    expected_content = sha256(expected).hexdigest()

    assert identity.path == (
        "results/phase4/gate1/durability_policy/sha256/"
        f"{expected_content}/policy.json"
    )
    assert repository.joinpath(*identity.path.split("/")).read_bytes() == expected
    assert store.verify(identity) == expected
    assert store.write_json("durability_policy", "policy.json", payload) == identity


def test_artifact_collision_fails_without_overwrite(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate1ArtifactStore(repository, repository / "results")
    payload = {"schema_version": "TEST-v1"}
    encoded = canonical_json_bytes(payload)
    content_sha256 = sha256(encoded).hexdigest()
    destination = (
        repository
        / "results"
        / "phase4"
        / "gate1"
        / "survivor_policy"
        / "sha256"
        / content_sha256
        / "policy.json"
    )
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"collision")

    with pytest.raises(Gate1ArtifactError, match="collision"):
        store.write_json("survivor_policy", "policy.json", payload)
    assert destination.read_bytes() == b"collision"


@pytest.mark.parametrize(
    "filename",
    ("", "../escape.json", "nested/evidence.json", "C:\\escape.json"),
)
def test_artifact_filename_must_be_one_portable_component(
    tmp_path: Path, filename: str
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate1ArtifactStore(repository, repository / "results")

    with pytest.raises(Gate1ArtifactError, match="filename"):
        store.write_json("survivor_policy", filename, {"value": 1})


def test_artifact_kind_and_results_root_are_bounded(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    with pytest.raises(Gate1ArtifactError, match="results root"):
        Gate1ArtifactStore(repository, tmp_path / "outside")

    store = Gate1ArtifactStore(repository, repository / "results")
    with pytest.raises(Gate1ArtifactError, match="kind"):
        store.write_json("phase2_experiment", "evidence.json", {"value": 1})  # type: ignore[arg-type]


def test_results_root_rejects_symlink_component_before_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    configured = repository / "linked-results"

    def pretend_symlink(path: Path) -> bool:
        return path.name == "linked-results"

    monkeypatch.setattr(Path, "is_symlink", pretend_symlink)
    with pytest.raises(Gate1ArtifactError, match="symlink"):
        Gate1ArtifactStore(repository, configured)


def test_verify_rejects_symlink_component_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate1ArtifactStore(repository, repository / "results")
    identity = store.write_json("survivor_policy", "policy.json", {"value": 1})
    reads = 0

    def pretend_symlink(path: Path) -> bool:
        return path.name == "sha256"

    def counted_read(_path: Path) -> bytes:
        nonlocal reads
        reads += 1
        return b""

    monkeypatch.setattr(Path, "is_symlink", pretend_symlink)
    monkeypatch.setattr(Path, "read_bytes", counted_read)

    with pytest.raises(Gate1ArtifactError, match="symlink"):
        store.verify(identity)
    assert reads == 0


def test_final_commit_has_no_fallible_post_publication_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate1ArtifactStore(repository, repository / "results")

    def forbidden_verify(_identity: object) -> bytes:
        raise AssertionError("commit must not verify after publication")

    monkeypatch.setattr(store, "verify", forbidden_verify)
    identity = store.commit_json(
        "phase4_preregistration_manifest",
        "manifest.json",
        {"status": "PHASE4_PREREGISTRATION_SEALED"},
    )

    destination = repository.joinpath(*identity.path.split("/"))
    assert destination.is_file()
    assert sha256(destination.read_bytes()).hexdigest() == identity.content_sha256
