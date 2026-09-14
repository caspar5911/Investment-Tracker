from __future__ import annotations

from hashlib import sha256
from importlib import import_module
import inspect
from pathlib import Path

import pytest

from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
)

try:
    from investment_tracker.quant.phase4.engine.artifacts import (
        Gate2ArtifactError,
        Gate2ArtifactStore,
    )
    from investment_tracker.quant.phase4.engine.models import (
        Gate2ArtifactIdentity,
    )

    _ARTIFACT_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as exc:
    Gate2ArtifactError = None
    Gate2ArtifactStore = None
    Gate2ArtifactIdentity = None
    _ARTIFACT_IMPORT_ERROR = exc


MARKDOWN = "# Gate 2 Engine Report\n\nSYNTHETIC_CONFORMANCE_ONLY\n"
MARKDOWN_CONTENT_SHA = "087f3f560957cfdfdc7ab968fd390c961218e82a24cebc08ac83c06d6e5a56db"
MARKDOWN_ENVELOPE_SHA = "4aa184c9cd572f72b4704271c849b7f679ff5b4ed49a268993dc1af4332f098c"
MANIFEST_CONTENT_SHA = "0963650054c0389a960c9e4b45c56815d539facb88ea04afaffb60c4f16ce406"
MANIFEST_ENVELOPE_SHA = "47458ce43f38fbbce77727b2630c4594e3791ef18d1933e5546b2a1419206514"

EXACT_FILENAMES = {
    "engine_contract": "contract.json",
    "family_implementation_bindings": "bindings.json",
    "candidate_implementation_bindings": "bindings.json",
    "synthetic_conformance": "conformance.json",
    "phase4_engine_report": "report.md",
    "phase4_engine_manifest": "manifest.json",
}


def _store(tmp_path: Path, results_name: str = "results") -> object:
    repository = tmp_path / "repository"
    repository.mkdir()
    return Gate2ArtifactStore(repository, repository / results_name)


@pytest.fixture(autouse=True)
def require_artifact_types(request: pytest.FixtureRequest) -> None:
    if (
        request.node.name != "test_artifact_types_are_available"
        and _ARTIFACT_IMPORT_ERROR is not None
    ):
        pytest.skip("Gate 2 artifact types are not implemented yet")


def test_artifact_types_are_available() -> None:
    assert _ARTIFACT_IMPORT_ERROR is None
    assert inspect.isclass(Gate2ArtifactStore)
    assert inspect.isclass(Gate2ArtifactError)
    assert inspect.isclass(Gate2ArtifactIdentity)


def test_write_json_publishes_canonical_utf8_bytes_at_content_addressed_path(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate2ArtifactStore(repository, repository / "results")
    payload = {"z": 2, "a": [True, None]}

    identity = store.write_json("engine_contract", payload)

    encoded = canonical_json_bytes(payload)
    content_sha = sha256(encoded).hexdigest()
    expected_path = (
        "results/phase4/gate2/engine_contract/sha256/"
        f"{content_sha}/contract.json"
    )
    assert isinstance(identity, Gate2ArtifactIdentity)
    assert identity.kind == "engine_contract"
    assert identity.content_sha256 == content_sha
    assert identity.path == expected_path
    assert identity.sha256 == artifact_envelope_identity(
        content_sha256=content_sha,
        kind="engine_contract",
        path=expected_path,
    )
    assert repository.joinpath(*identity.path.split("/")).read_bytes() == encoded
    assert store.verify(identity) == encoded
    # idempotent for identical bytes
    assert store.write_json("engine_contract", payload) == identity


def test_write_bytes_publishes_exact_markdown_bytes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    identity = store.write_bytes("phase4_engine_report", MARKDOWN.encode("utf-8"))

    expected_path = (
        "results/phase4/gate2/phase4_engine_report/sha256/"
        f"{MARKDOWN_CONTENT_SHA}/report.md"
    )
    assert identity.content_sha256 == MARKDOWN_CONTENT_SHA
    assert identity.path == expected_path
    assert identity.sha256 == MARKDOWN_ENVELOPE_SHA
    assert store.verify(identity) == MARKDOWN.encode("utf-8")


def test_every_kind_publishes_its_exact_filename(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for kind, filename in EXACT_FILENAMES.items():
        if kind == "phase4_engine_manifest":
            continue
        if kind == "phase4_engine_report":
            identity = store.write_bytes(kind, b"gate2 report bytes")
        else:
            identity = store.write_json(kind, {"kind": kind})
        assert identity.path.endswith(f"/{identity.content_sha256}/{filename}")


def test_only_exact_gate2_kinds_are_permitted(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for kind in (
        "phase2_experiment",
        "durability_policy",
        "research_report",
        "phase4_preregistration_manifest",
    ):
        with pytest.raises(Gate2ArtifactError, match="kind"):
            store.write_json(kind, {"value": 1})  # type: ignore[arg-type]


def test_manifest_kind_is_rejected_by_regular_writes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(Gate2ArtifactError, match="manifest"):
        store.write_json("phase4_engine_manifest", {"status": "x"})
    with pytest.raises(Gate2ArtifactError, match="manifest"):
        store.write_bytes("phase4_engine_manifest", b"x")


def test_collision_with_different_bytes_fails_closed_and_preserves_existing(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate2ArtifactStore(repository, repository / "results")
    payload = {"schema_version": "PHASE4-ENGINE-CONTRACT-v1"}
    encoded = canonical_json_bytes(payload)
    content_sha = sha256(encoded).hexdigest()
    destination = (
        repository
        / "results"
        / "phase4"
        / "gate2"
        / "engine_contract"
        / "sha256"
        / content_sha
        / "contract.json"
    )
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"collision")

    with pytest.raises(Gate2ArtifactError, match="collision"):
        store.write_json("engine_contract", payload)
    assert destination.read_bytes() == b"collision"


def test_nonregular_destination_fails_closed(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate2ArtifactStore(repository, repository / "results")
    payload = {"value": 1}
    content_sha = sha256(canonical_json_bytes(payload)).hexdigest()
    destination = (
        repository
        / "results"
        / "phase4"
        / "gate2"
        / "engine_contract"
        / "sha256"
        / content_sha
        / "contract.json"
    )
    destination.mkdir(parents=True)

    with pytest.raises(Gate2ArtifactError, match="invalid|collision"):
        store.write_json("engine_contract", payload)


def test_results_root_must_stay_inside_repository(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    with pytest.raises(Gate2ArtifactError, match="results root"):
        Gate2ArtifactStore(repository, tmp_path / "outside")


def test_results_root_rejects_symlink_component_before_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    configured = repository / "linked-results"

    def pretend_symlink(path: Path) -> bool:
        return path.name == "linked-results"

    monkeypatch.setattr(Path, "is_symlink", pretend_symlink)
    with pytest.raises(Gate2ArtifactError, match="symlink"):
        Gate2ArtifactStore(repository, configured)


def test_write_rejects_symlink_component(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate2ArtifactStore(repository, repository / "results")

    def pretend_symlink(path: Path) -> bool:
        return path.name == "sha256"

    monkeypatch.setattr(Path, "is_symlink", pretend_symlink)
    with pytest.raises(Gate2ArtifactError, match="symlink"):
        store.write_json("engine_contract", {"value": 1})


def test_verify_rejects_symlink_component_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate2ArtifactStore(repository, repository / "results")
    identity = store.write_json("synthetic_conformance", {"value": 1})
    reads = 0

    def pretend_symlink(path: Path) -> bool:
        return path.name == "sha256"

    def counted_read(_path: Path) -> bytes:
        nonlocal reads
        reads += 1
        return b""

    monkeypatch.setattr(Path, "is_symlink", pretend_symlink)
    monkeypatch.setattr(Path, "read_bytes", counted_read)

    with pytest.raises(Gate2ArtifactError, match="symlink"):
        store.verify(identity)
    assert reads == 0


def test_verify_detects_tampered_content(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate2ArtifactStore(repository, repository / "results")
    identity = store.write_json("family_implementation_bindings", {"value": 1})
    destination = repository.joinpath(*identity.path.split("/"))
    destination.write_bytes(destination.read_bytes() + b"x")

    with pytest.raises(Gate2ArtifactError, match="digest|content"):
        store.verify(identity)


def test_verify_rejects_envelope_mismatch(tmp_path: Path) -> None:
    store = _store(tmp_path)
    identity = store.write_json("candidate_implementation_bindings", {"value": 1})
    tampered = identity.model_copy(update={"sha256": "0" * 64})

    with pytest.raises(Gate2ArtifactError, match="envelope"):
        store.verify(tampered)


def test_temporary_files_are_cleaned_up(tmp_path: Path) -> None:
    store = _store(tmp_path)
    identity = store.write_json("engine_contract", {"value": 1})
    destination = Path(tmp_path / "repository").joinpath(*identity.path.split("/"))
    leftovers = [
        entry for entry in destination.parent.iterdir() if entry.name.startswith(".tmp")
    ]
    assert leftovers == []


def test_write_json_rejects_noncanonical_payload(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(Gate2ArtifactError, match="canonical"):
        store.write_json("engine_contract", {"value": float("nan")})
    with pytest.raises(Gate2ArtifactError, match="bytes"):
        store.write_bytes("phase4_engine_report", "not-bytes")  # type: ignore[arg-type]


def test_commit_manifest_is_final_without_post_publication_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = Gate2ArtifactStore(repository, repository / "results")

    def forbidden_verify(_identity: object) -> bytes:
        raise AssertionError("manifest commit must not verify after publication")

    monkeypatch.setattr(store, "verify", forbidden_verify)
    identity = store.commit_manifest({"PHASE4-ENGINE-SEALED": True})

    assert identity.kind == "phase4_engine_manifest"
    assert identity.content_sha256 == MANIFEST_CONTENT_SHA
    expected_path = (
        "results/phase4/gate2/phase4_engine_manifest/sha256/"
        f"{MANIFEST_CONTENT_SHA}/manifest.json"
    )
    assert identity.path == expected_path
    assert identity.sha256 == MANIFEST_ENVELOPE_SHA
    destination = repository.joinpath(*identity.path.split("/"))
    assert destination.is_file()
    assert sha256(destination.read_bytes()).hexdigest() == identity.content_sha256


def test_commit_manifest_is_idempotent_for_identical_payload(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.commit_manifest({"PHASE4-ENGINE-SEALED": True})
    assert store.commit_manifest({"PHASE4-ENGINE-SEALED": True}) == first
    different = store.commit_manifest({"PHASE4-ENGINE-SEALED": True, "extra": 1})
    assert different.content_sha256 != first.content_sha256
    assert store.verify(first) == canonical_json_bytes({"PHASE4-ENGINE-SEALED": True})
