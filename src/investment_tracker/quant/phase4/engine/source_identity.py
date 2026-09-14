"""Gate 2 source-bundle identity: canonical digests over Git blob bytes."""

from __future__ import annotations

import re
import subprocess
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Literal, Sequence

from pydantic import Field, model_validator

from investment_tracker.quant.phase4.preregistration.canonical import (
    canonical_sha256,
)

from .models import FrozenGate2Model, Gate2SealError

_SCHEMA = "PHASE4-SOURCE-BUNDLE-v1"
_ENGINE_PREFIX = "src/investment_tracker/quant/phase4/engine/"
_REVISION_PATTERN = r"^[0-9a-f]{40}$"
_FAMILIES = (
    "cross_sectional_absolute_momentum_rotation",
    "diversified_time_series_momentum",
    "trend_filtered_equal_risk_allocation",
    "volatility_managed_relative_momentum",
)
_FAMILY_CORE = (
    "allocation.py",
    "market.py",
    "models.py",
    "strategies.py",
)
_ENGINE_FILES = (
    "__init__.py",
    "allocation.py",
    "artifacts.py",
    "authority.py",
    "benchmarks.py",
    "budget.py",
    "cli.py",
    "conformance.py",
    "durability.py",
    "evidence.py",
    "execution.py",
    "market.py",
    "metrics.py",
    "models.py",
    "robustness.py",
    "seal.py",
    "source_identity.py",
    "strategies.py",
)


def _bundle(files: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({_ENGINE_PREFIX + path for path in files})) if files else ()


GATE2_SOURCE_BUNDLES: dict[str, tuple[str, ...]] = {
    **{
        f"family:{family}": _bundle(_FAMILY_CORE) for family in _FAMILIES
    },
    "execution": _bundle((*_FAMILY_CORE, "execution.py")),
    "metric": _bundle(("metrics.py",)),
    "durability": _bundle(("durability.py",)),
    "robustness": _bundle(("robustness.py",)),
    "budget": _bundle(("budget.py",)),
    "evidence": _bundle(("evidence.py",)),
    "authority": _bundle(("authority.py",)),
    "artifact": _bundle(("artifacts.py",)),
    "engine": _bundle(_ENGINE_FILES),
}


class SourceBundleEntry(FrozenGate2Model):
    """One repository-relative POSIX source path bound to its Git blob OID."""

    schema_version: Literal["PHASE4-SOURCE-BUNDLE-ENTRY-v1"] = (
        "PHASE4-SOURCE-BUNDLE-ENTRY-v1"
    )
    path: str = Field(min_length=1)
    git_blob: str = Field(pattern=_REVISION_PATTERN)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="before")
    @classmethod
    def validate_repository_relative_posix(cls, data: object) -> object:
        if isinstance(data, dict) and "path" in data:
            path = str(data["path"])
            parts = PurePosixPath(path).parts
            if (
                not path
                or "\\" in path
                or path.startswith("/")
                or any(part in {"", ".", ".."} for part in parts)
            ):
                raise ValueError(
                    "source-bundle path must be repository-relative POSIX"
                )
        return data


class SourceBundleIdentity(FrozenGate2Model):
    """Canonical digest over the ordered map of path to {git_blob, content}."""

    schema_version: Literal["PHASE4-SOURCE-BUNDLE-v1"] = _SCHEMA
    producing_revision: str = Field(pattern=_REVISION_PATTERN)
    entries: tuple[SourceBundleEntry, ...] = Field(min_length=1)
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_bundle_identity(self) -> "SourceBundleIdentity":
        paths = tuple(entry.path for entry in self.entries)
        if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
            raise ValueError(
                "source-bundle entries must be unique and path-sorted"
            )
        digest = canonical_sha256(
            {
                "schema_version": _SCHEMA,
                "producing_revision": self.producing_revision,
                "entries": {
                    entry.path: {
                        "git_blob": entry.git_blob,
                        "content_sha256": entry.content_sha256,
                    }
                    for entry in self.entries
                },
            }
        )
        if digest != self.bundle_sha256:
            raise ValueError("source-bundle digest does not bind its entries")
        return self


def _git_stdout(root: Path, *args: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise Gate2SealError(
            "INPUT_BOUNDARY_VIOLATION",
            "INPUT_BOUNDARY_VIOLATION: git plumbing unavailable for "
            f"{' '.join(args)}: {exc}",
        ) from exc
    return completed.stdout


def source_bundle_identity(
    repository_root: Path | str,
    producing_revision: str,
    paths: Sequence[str],
) -> SourceBundleIdentity:
    """Bind worktree sources to one Git revision's blob bytes.

    Every path must be a tracked, non-symlinked, repository-relative POSIX
    file whose worktree bytes are bit-identical to the producing revision's
    blob; a dirty or wrong-revision worktree is an immutable collision.
    """

    root = Path(repository_root)
    if not re.fullmatch(_REVISION_PATTERN, producing_revision):
        raise Gate2SealError(
            "INPUT_BOUNDARY_VIOLATION",
            "INPUT_BOUNDARY_VIOLATION: producing revision must be a 40-hex "
            "lowercase Git revision",
        )
    sequence = tuple(paths)
    if not sequence:
        raise Gate2SealError(
            "INPUT_BOUNDARY_VIOLATION",
            "INPUT_BOUNDARY_VIOLATION: source-bundle paths must not be empty",
        )
    if sequence != tuple(sorted(sequence)):
        raise Gate2SealError(
            "INPUT_BOUNDARY_VIOLATION",
            "INPUT_BOUNDARY_VIOLATION: source-bundle paths must be path-sorted",
        )
    if len(set(sequence)) != len(sequence):
        raise Gate2SealError(
            "INPUT_BOUNDARY_VIOLATION",
            "INPUT_BOUNDARY_VIOLATION: source-bundle paths must be unique",
        )

    entries: list[SourceBundleEntry] = []
    for relative in sequence:
        parts = PurePosixPath(relative).parts
        if (
            "\\" in relative
            or relative.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise Gate2SealError(
                "INPUT_BOUNDARY_VIOLATION",
                "INPUT_BOUNDARY_VIOLATION: source path must be a "
                f"repository-relative POSIX path: {relative}",
            )
        worktree = root / relative
        if worktree.is_symlink():
            raise Gate2SealError(
                "INPUT_BOUNDARY_VIOLATION",
                f"INPUT_BOUNDARY_VIOLATION: symlinked source rejected: {relative}",
            )
        if not worktree.is_file():
            raise Gate2SealError(
                "INPUT_BOUNDARY_VIOLATION",
                f"INPUT_BOUNDARY_VIOLATION: source file missing: {relative}",
            )
        worktree_bytes = worktree.read_bytes()
        blob_oid = _git_stdout(
            root, "rev-parse", f"{producing_revision}:{relative}"
        ).decode("ascii").strip()
        blob_bytes = _git_stdout(root, "cat-file", "blob", blob_oid)
        if worktree_bytes != blob_bytes:
            raise Gate2SealError(
                "IMMUTABLE_ARTIFACT_COLLISION",
                "IMMUTABLE_ARTIFACT_COLLISION: worktree bytes differ from "
                f"the producing revision's blob for {relative}",
            )
        entries.append(
            SourceBundleEntry(
                path=relative,
                git_blob=blob_oid,
                content_sha256=sha256(worktree_bytes).hexdigest(),
            )
        )

    return SourceBundleIdentity(
        producing_revision=producing_revision,
        entries=tuple(entries),
        bundle_sha256=canonical_sha256(
            {
                "schema_version": _SCHEMA,
                "producing_revision": producing_revision,
                "entries": {
                    entry.path: {
                        "git_blob": entry.git_blob,
                        "content_sha256": entry.content_sha256,
                    }
                    for entry in entries
                },
            }
        ),
    )


__all__ = (
    "GATE2_SOURCE_BUNDLES",
    "SourceBundleEntry",
    "SourceBundleIdentity",
    "source_bundle_identity",
)
