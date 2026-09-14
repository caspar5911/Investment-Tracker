from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

from investment_tracker.quant.phase4.engine.models import Gate2SealError

try:
    import investment_tracker.quant.phase4.engine.source_identity as _source_module

    GATE2_SOURCE_BUNDLES = _source_module.GATE2_SOURCE_BUNDLES
    SourceBundleEntry = _source_module.SourceBundleEntry
    SourceBundleIdentity = _source_module.SourceBundleIdentity
    source_bundle_identity = _source_module.source_bundle_identity
    _SOURCE_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as _exc:  # pragma: no cover - RED marker
    GATE2_SOURCE_BUNDLES = None
    SourceBundleEntry = None
    SourceBundleIdentity = None
    source_bundle_identity = None
    _SOURCE_IMPORT_ERROR = _exc


@pytest.fixture(autouse=True)
def require_source_types(request: pytest.FixtureRequest) -> None:
    if _SOURCE_IMPORT_ERROR is not None and (
        "test_source_types_are_available" not in request.node.name
    ):
        pytest.skip(f"Gate 2 source identity unavailable: {_SOURCE_IMPORT_ERROR}")


def test_source_types_are_available() -> None:
    assert _SOURCE_IMPORT_ERROR is None, str(_SOURCE_IMPORT_ERROR)
    assert callable(source_bundle_identity)
    assert GATE2_SOURCE_BUNDLES is not None


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            "GIT_CONFIG_GLOBAL": "NUL",
            "GIT_CONFIG_SYSTEM": "NUL",
            "HOME": str(cwd),
        },
    )


@pytest.fixture()
def temp_repository(tmp_path: Path) -> dict[str, Any]:
    _git("init", "-q", tmp_path.as_posix(), cwd=tmp_path)
    _git("config", "core.autocrlf", "false", cwd=tmp_path)
    _git("config", "user.email", "gate2@example.test", cwd=tmp_path)
    _git("config", "user.name", "Gate 2 Conformance", cwd=tmp_path)
    engine_dir = tmp_path / "src" / "investment_tracker" / "quant" / "phase4" / "engine"
    engine_dir.mkdir(parents=True)
    files = {
        "market.py": "MARKET\n",
        "allocation.py": "ALLOCATION\n",
        "strategies.py": "STRATEGIES\n",
        "models.py": "MODELS\n",
    }
    for relative, content in files.items():
        (engine_dir / relative).write_bytes(content.encode("utf-8"))
    _git("add", "src", cwd=tmp_path)
    _git(
        "commit",
        "-q",
        "-m",
        "gate2 fixture revision one",
        cwd=tmp_path,
    )
    revision_one = (
        _git("rev-parse", "HEAD", cwd=tmp_path).stdout.decode("ascii").strip()
    )
    (engine_dir / "strategies.py").write_bytes(b"STRATEGIES CHANGED\n")
    _git("commit", "-q", "-am", "gate2 fixture revision two", cwd=tmp_path)
    revision_two = (
        _git("rev-parse", "HEAD", cwd=tmp_path).stdout.decode("ascii").strip()
    )
    return {
        "root": tmp_path,
        "revision_one": revision_one,
        "revision_two": revision_two,
        "files": files,
    }


def _bundle_paths(revision: str, names: tuple[str, ...], root: Path) -> tuple[str, ...]:
    return tuple(
        f"src/investment_tracker/quant/phase4/engine/{name}" for name in names
    )


def test_clean_exact_blob_sources_produce_a_stable_bundle(temp_repository) -> None:
    root: Path = temp_repository["root"]
    # The fixture leaves the worktree clean at revision_two; the clean exact
    # blob invariant is that, at the producing revision, each entry's blob OID
    # and content hash describe the very bytes in the worktree.
    revision: str = temp_repository["revision_two"]
    names = ("market.py", "strategies.py")
    bundle = source_bundle_identity(root, revision, _bundle_paths(revision, names, root))

    assert isinstance(bundle, SourceBundleIdentity)
    assert bundle.producing_revision == revision
    assert [entry.path for entry in bundle.entries] == list(
        _bundle_paths(revision, names, root)
    )
    for entry, name in zip(bundle.entries, names, strict=True):
        expected_blob = _git(
            "rev-parse",
            f"{revision}:src/investment_tracker/quant/phase4/engine/{name}",
            cwd=root,
        ).stdout.decode("ascii").strip()
        assert entry.git_blob == expected_blob
        worktree_bytes = (
            root / "src" / "investment_tracker" / "quant" / "phase4" / "engine" / name
        ).read_bytes()
        assert entry.content_sha256 == hashlib.sha256(worktree_bytes).hexdigest()
    again = source_bundle_identity(root, revision, _bundle_paths(revision, names, root))
    assert again.bundle_sha256 == bundle.bundle_sha256
    assert tuple(again.entries) == tuple(bundle.entries)


def test_out_of_order_entries_are_rejected_by_the_identity_model() -> None:
    entry_first = SourceBundleEntry(
        path="a.py", git_blob="1" * 40, content_sha256="2" * 64
    )
    entry_second = SourceBundleEntry(
        path="b.py", git_blob="3" * 40, content_sha256="4" * 64
    )
    with pytest.raises(ValueError):
        SourceBundleIdentity(
            producing_revision="5" * 40,
            entries=(entry_second, entry_first),
            bundle_sha256="6" * 64,
        )


def test_bundle_membership_rules_cover_signal_target_and_accounting_sources() -> None:
    bundles = GATE2_SOURCE_BUNDLES
    assert set(bundles) == {
        "family:cross_sectional_absolute_momentum_rotation",
        "family:diversified_time_series_momentum",
        "family:trend_filtered_equal_risk_allocation",
        "family:volatility_managed_relative_momentum",
        "execution",
        "metric",
        "durability",
        "robustness",
        "budget",
        "evidence",
        "authority",
        "artifact",
        "engine",
    }
    prefix = "src/investment_tracker/quant/phase4/engine/"
    family_paths = tuple(
        f"{prefix}{name}"
        for name in ("allocation.py", "market.py", "models.py", "strategies.py")
    )
    for family in (
        "cross_sectional_absolute_momentum_rotation",
        "diversified_time_series_momentum",
        "trend_filtered_equal_risk_allocation",
        "volatility_managed_relative_momentum",
    ):
        assert tuple(bundles[f"family:{family}"]) == family_paths
    execution_paths = tuple(f"{prefix}{name}" for name in ("execution.py",))
    expected_execution = tuple(sorted(set(family_paths) | set(execution_paths)))
    assert tuple(bundles["execution"]) == expected_execution
    assert tuple(bundles["metric"]) == (f"{prefix}metrics.py",)
    assert tuple(bundles["durability"]) == (f"{prefix}durability.py",)
    assert tuple(bundles["robustness"]) == (f"{prefix}robustness.py",)
    assert tuple(bundles["budget"]) == (f"{prefix}budget.py",)
    assert tuple(bundles["evidence"]) == (f"{prefix}evidence.py",)
    assert tuple(bundles["authority"]) == (f"{prefix}authority.py",)
    assert tuple(bundles["artifact"]) == (f"{prefix}artifacts.py",)
    for values in bundles.values():
        assert values == tuple(sorted(set(values)))


def test_engine_bundle_binds_every_tracked_top_level_engine_source() -> None:
    bundles = GATE2_SOURCE_BUNDLES
    prefix = "src/investment_tracker/quant/phase4/engine/"
    expected_engine = tuple(
        f"{prefix}{name}"
        for name in (
            "__init__.py",
            "allocation.py",
            "artifacts.py",
            "authority.py",
            "benchmarks.py",
            "budget.py",
            "conformance.py",
            "durability.py",
            "evidence.py",
            "execution.py",
            "market.py",
            "metrics.py",
            "models.py",
            "robustness.py",
            "source_identity.py",
            "strategies.py",
        )
    )
    assert tuple(bundles["engine"]) == expected_engine


def test_untracked_source_is_rejected(temp_repository) -> None:
    root: Path = temp_repository["root"]
    engine_dir = root / "src" / "investment_tracker" / "quant" / "phase4" / "engine"
    (engine_dir / "untracked.py").write_bytes(b"UNTRACKED\n")
    with pytest.raises(Gate2SealError) as excinfo:
        source_bundle_identity(
            root,
            temp_repository["revision_one"],
            ("src/investment_tracker/quant/phase4/engine/untracked.py",),
        )
    assert excinfo.value.code == "INPUT_BOUNDARY_VIOLATION"


def test_dirty_worktree_bytes_are_rejected(temp_repository) -> None:
    root: Path = temp_repository["root"]
    revision: str = temp_repository["revision_two"]
    (
        root
        / "src"
        / "investment_tracker"
        / "quant"
        / "phase4"
        / "engine"
        / "strategies.py"
    ).write_bytes(b"STRATEGIES DIRTY UNCOMMITTED\n")
    with pytest.raises(Gate2SealError) as excinfo:
        source_bundle_identity(
            root,
            revision,
            ("src/investment_tracker/quant/phase4/engine/strategies.py",),
        )
    assert excinfo.value.code == "IMMUTABLE_ARTIFACT_COLLISION"


def test_missing_tracked_file_is_rejected(temp_repository) -> None:
    root: Path = temp_repository["root"]
    revision: str = temp_repository["revision_two"]
    (
        root
        / "src"
        / "investment_tracker"
        / "quant"
        / "phase4"
        / "engine"
        / "strategies.py"
    ).unlink()
    with pytest.raises(Gate2SealError) as excinfo:
        source_bundle_identity(
            root,
            revision,
            ("src/investment_tracker/quant/phase4/engine/strategies.py",),
        )
    assert excinfo.value.code == "INPUT_BOUNDARY_VIOLATION"


def test_symlinked_source_is_rejected(temp_repository, monkeypatch) -> None:
    root: Path = temp_repository["root"]
    target = (
        root / "src" / "investment_tracker" / "quant" / "phase4" / "engine" / "market.py"
    )
    original = Path.is_symlink

    def pretend(path: Path, *args: Any, **kwargs: Any) -> bool:
        if Path(path) == target:
            return True
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "is_symlink", pretend)
    with pytest.raises(Gate2SealError) as excinfo:
        source_bundle_identity(
            root,
            temp_repository["revision_one"],
            ("src/investment_tracker/quant/phase4/engine/market.py",),
        )
    assert excinfo.value.code == "INPUT_BOUNDARY_VIOLATION"


def test_escaped_source_path_is_rejected(temp_repository) -> None:
    root: Path = temp_repository["root"]
    with pytest.raises(Gate2SealError) as excinfo:
        source_bundle_identity(
            root,
            temp_repository["revision_one"],
            ("src/investment_tracker/quant/phase4/engine/../engine/market.py",),
        )
    assert excinfo.value.code == "INPUT_BOUNDARY_VIOLATION"


def test_reordered_sources_are_rejected(temp_repository) -> None:
    root: Path = temp_repository["root"]
    revision: str = temp_repository["revision_one"]
    ordered = _bundle_paths(revision, ("market.py", "strategies.py"), root)
    with pytest.raises(Gate2SealError) as excinfo:
        source_bundle_identity(
            root,
            revision,
            (ordered[1], ordered[0]),
        )
    assert excinfo.value.code == "INPUT_BOUNDARY_VIOLATION"


def test_wrong_revision_source_is_rejected(temp_repository) -> None:
    root: Path = temp_repository["root"]
    with pytest.raises(Gate2SealError) as excinfo:
        source_bundle_identity(
            root,
            temp_repository["revision_one"],
            ("src/investment_tracker/quant/phase4/engine/strategies.py",),
        )
    assert excinfo.value.code == "IMMUTABLE_ARTIFACT_COLLISION"


def test_malformed_producing_revision_is_rejected(temp_repository) -> None:
    root: Path = temp_repository["root"]
    with pytest.raises(Gate2SealError) as excinfo:
        source_bundle_identity(
            root,
            "deadbeef",
            ("src/investment_tracker/quant/phase4/engine/market.py",),
        )
    assert excinfo.value.code == "INPUT_BOUNDARY_VIOLATION"


def test_duplicate_source_paths_are_rejected(temp_repository) -> None:
    root: Path = temp_repository["root"]
    revision: str = temp_repository["revision_one"]
    path = "src/investment_tracker/quant/phase4/engine/market.py"
    with pytest.raises(Gate2SealError) as excinfo:
        source_bundle_identity(root, revision, (path, path))
    assert excinfo.value.code == "INPUT_BOUNDARY_VIOLATION"
