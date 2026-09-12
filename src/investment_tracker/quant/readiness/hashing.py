from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import ArtifactKind

if TYPE_CHECKING:
    from .models import ReadinessArtifactIdentity


class ArtifactIdentityError(ValueError):
    """Raised when an artifact cannot be assigned a safe repository identity."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def trial_identity(campaign_id: str, candidate_id: str) -> str:
    return canonical_sha256(
        {"campaign_id": campaign_id, "candidate_id": candidate_id}
    )


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor) if path.anchor else Path()
    parts = path.parts[1:] if path.anchor else path.parts
    for part in parts:
        current /= part
        if current.is_symlink():
            raise ArtifactIdentityError(f"artifact path contains symlink component: {current}")


def normalize_repository_path(repository_root: Path, path: Path) -> str:
    root = Path(repository_root)
    candidate_input = Path(path)

    if not root.exists() or not root.is_dir():
        raise ArtifactIdentityError("repository root must be an existing directory")
    _reject_symlink_components(root.absolute())

    if any(part in {".", ".."} for part in candidate_input.parts):
        raise ArtifactIdentityError("artifact path cannot contain dot components")
    if candidate_input == Path("."):
        raise ArtifactIdentityError("artifact path cannot be empty")
    if not candidate_input.is_absolute() and (
        candidate_input.drive or candidate_input.root or candidate_input.anchor
    ):
        raise ArtifactIdentityError("artifact path cannot have a drive or root prefix")

    root_resolved = root.resolve(strict=True)
    candidate = (
        candidate_input
        if candidate_input.is_absolute()
        else root_resolved / candidate_input
    )
    _reject_symlink_components(candidate.absolute())
    candidate_resolved = candidate.resolve(strict=False)

    try:
        relative = candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ArtifactIdentityError("artifact path escapes repository root") from exc

    normalized = relative.as_posix()
    components = normalized.split("/")
    if (
        not normalized
        or normalized.startswith("/")
        or relative.drive
        or any(component in {"", ".", ".."} for component in components)
    ):
        raise ArtifactIdentityError("artifact path is not normalized repository-relative POSIX")
    return normalized


def exact_file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_identity(
    repository_root: Path,
    path: Path,
    kind: ArtifactKind,
) -> ReadinessArtifactIdentity:
    from .models import ReadinessArtifactIdentity

    normalized = normalize_repository_path(repository_root, path)
    artifact_path = Path(path)
    if not artifact_path.is_absolute():
        artifact_path = Path(repository_root).resolve(strict=True) / artifact_path
    content_sha256 = exact_file_sha256(artifact_path)
    envelope = {
        "content_sha256": content_sha256,
        "kind": kind,
        "path": normalized,
    }
    return ReadinessArtifactIdentity(
        **envelope,
        sha256=canonical_sha256(envelope),
    )
