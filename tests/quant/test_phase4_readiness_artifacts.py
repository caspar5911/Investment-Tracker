from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from investment_tracker.quant.readiness.artifacts import (
    ReadinessArtifactIntegrityError,
    ReadinessArtifactStore,
)
from investment_tracker.quant.readiness.hashing import (
    canonical_json_bytes,
    canonical_sha256,
)
from investment_tracker.quant.readiness.models import ReadinessArtifactIdentity


def readiness_store(tmp_path: Path) -> ReadinessArtifactStore:
    repository = tmp_path / "repo"
    repository.mkdir()
    return ReadinessArtifactStore(repository, repository / "results")


def test_store_uses_exact_content_hash_path_and_envelope_identity(
    tmp_path: Path,
) -> None:
    store = readiness_store(tmp_path)
    identity = store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
    assert identity.content_sha256 == sha256(b'{"a":1}').hexdigest()
    assert identity.path == (
        f"results/phase4/readiness/phase4_split_manifest/sha256/"
        f"{identity.content_sha256}/manifest.json"
    )
    assert identity.sha256 == canonical_sha256(
        {
            "content_sha256": identity.content_sha256,
            "kind": identity.kind,
            "path": identity.path,
        }
    )
    assert Path(tmp_path / "repo", identity.path).read_bytes() == b'{"a":1}'
    assert store.read_json(identity) == {"a": 1}


def test_text_store_hashes_and_reads_exact_utf8_bytes(tmp_path: Path) -> None:
    store = readiness_store(tmp_path)
    text = "Readiness caf\N{LATIN SMALL LETTER E WITH ACUTE}\n"
    identity = store.write_text("phase4_readiness_report", "report.md", text)

    assert identity.content_sha256 == sha256(text.encode("utf-8")).hexdigest()
    assert Path(tmp_path / "repo", identity.path).read_bytes() == text.encode("utf-8")
    assert store.read_text(identity) == text


def test_final_json_commit_does_not_reopen_after_atomic_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = readiness_store(tmp_path)
    original_read_bytes = Path.read_bytes

    def reject_published_file(self: Path) -> bytes:
        if self.name == "manifest.json" and ".tmp-" not in self.parent.name:
            raise OSError("published file must not be reopened")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", reject_published_file)
    identity = store.commit_json(
        "phase4_readiness_manifest",
        "manifest.json",
        {"status": "PHASE_4_READY"},
    )

    assert identity.kind == "phase4_readiness_manifest"
    assert original_read_bytes(tmp_path / "repo" / identity.path) == (
        b'{"status":"PHASE_4_READY"}'
    )


def test_store_reuses_only_exactly_identical_bytes(tmp_path: Path) -> None:
    store = readiness_store(tmp_path)
    first = store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
    second = store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
    assert first == second

    Path(tmp_path / "repo", first.path).write_bytes(b"tampered")
    with pytest.raises(ReadinessArtifactIntegrityError, match="collision"):
        store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})


@pytest.mark.parametrize(
    "filename",
    ["../manifest.json", "/manifest.json", "nested/manifest.json", "", "."],
)
def test_store_rejects_unsafe_filenames(tmp_path: Path, filename: str) -> None:
    store = readiness_store(tmp_path)
    with pytest.raises(ReadinessArtifactIntegrityError, match="filename"):
        store.write_json("phase4_split_manifest", filename, {"a": 1})


def test_store_rejects_results_root_outside_repository(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    with pytest.raises(ReadinessArtifactIntegrityError, match="results root"):
        ReadinessArtifactStore(repository, tmp_path / "outside")


def test_store_rejects_kind_and_path_mismatch_on_verify(tmp_path: Path) -> None:
    store = readiness_store(tmp_path)
    identity = store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
    envelope = {
        "content_sha256": identity.content_sha256,
        "kind": "bootstrap_audit",
        "path": identity.path,
    }
    mismatched = ReadinessArtifactIdentity(
        **envelope,
        sha256=canonical_sha256(envelope),
    )

    with pytest.raises(ReadinessArtifactIntegrityError, match="kind or content path"):
        store.verify(mismatched)


def test_store_rejects_non_regular_destination(tmp_path: Path) -> None:
    store = readiness_store(tmp_path)
    content_sha256 = sha256(canonical_json_bytes({"a": 1})).hexdigest()
    destination = (
        tmp_path
        / "repo"
        / "results"
        / "phase4"
        / "readiness"
        / "phase4_split_manifest"
        / "sha256"
        / content_sha256
        / "manifest.json"
    )
    destination.mkdir(parents=True)

    with pytest.raises(ReadinessArtifactIntegrityError, match="non-regular"):
        store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})


def test_atomic_publication_does_not_clobber_race_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = readiness_store(tmp_path)
    payload = canonical_json_bytes({"a": 1})
    content_sha256 = sha256(payload).hexdigest()
    destination = (
        tmp_path
        / "repo"
        / "results"
        / "phase4"
        / "readiness"
        / "phase4_split_manifest"
        / "sha256"
        / content_sha256
        / "manifest.json"
    )
    real_exists = Path.exists
    destination_checks = 0

    def insert_competitor_after_final_check(path: Path) -> bool:
        nonlocal destination_checks
        if path == destination:
            destination_checks += 1
            if destination_checks == 2:
                destination.write_bytes(b"competing writer")
                return False
        return real_exists(path)

    monkeypatch.setattr(Path, "exists", insert_competitor_after_final_check)

    with pytest.raises(ReadinessArtifactIntegrityError, match="collision"):
        store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
    assert destination.read_bytes() == b"competing writer"


def test_verify_rejects_changed_exact_bytes(tmp_path: Path) -> None:
    store = readiness_store(tmp_path)
    identity = store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
    Path(tmp_path / "repo", identity.path).write_bytes(b'{"a":1}\n')

    with pytest.raises(ReadinessArtifactIntegrityError, match="content hash mismatch"):
        store.verify(identity)


def test_read_json_parses_the_same_buffer_whose_digest_was_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = readiness_store(tmp_path)
    identity = store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
    artifact = Path(tmp_path / "repo", identity.path)
    real_read_bytes = Path.read_bytes

    def mutate_before_read(path: Path) -> bytes:
        if path == artifact:
            path.write_bytes(b'{"a":2}')
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", mutate_before_read)

    with pytest.raises(ReadinessArtifactIntegrityError, match="content hash"):
        store.read_json(identity)


def test_read_text_decodes_the_same_buffer_whose_digest_was_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = readiness_store(tmp_path)
    identity = store.write_text("phase4_readiness_report", "report.md", "original")
    artifact = Path(tmp_path / "repo", identity.path)
    real_read_bytes = Path.read_bytes

    def mutate_before_read(path: Path) -> bytes:
        if path == artifact:
            path.write_bytes(b"changed")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", mutate_before_read)

    with pytest.raises(ReadinessArtifactIntegrityError, match="content hash"):
        store.read_text(identity)


def test_store_rejects_symlinked_repository_root(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    linked_repository = tmp_path / "linked-repository"
    try:
        linked_repository.symlink_to(repository, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(ReadinessArtifactIntegrityError, match="symlink"):
        ReadinessArtifactStore(linked_repository, Path("results"))


def test_store_rejects_symlinked_output_parent_when_supported(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    results = repository / "results"
    repository.mkdir()
    store = ReadinessArtifactStore(repository, results)
    (results / "phase4").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    readiness = results / "phase4" / "readiness"
    try:
        readiness.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(ReadinessArtifactIntegrityError, match="symlink"):
        store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
