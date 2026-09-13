from __future__ import annotations

from hashlib import sha256
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
from typing import Literal

from pydantic import Field, model_validator

from .models import FrozenGate1Model, Gate1ArtifactIdentity


PROTECTED_SYMBOLS = frozenset({"HACK", "SOXX", "NLR", "URNM", "GEV"})


class Gate1AccessError(RuntimeError):
    """Raised when a Gate 1 read exceeds or violates its exact capability."""


class Gate1GitObjectIdentity(FrozenGate1Model):
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: str = Field(min_length=1)
    blob: str = Field(pattern=r"^[0-9a-f]{40}$")
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_path(self) -> "Gate1GitObjectIdentity":
        posix = PurePosixPath(self.path)
        windows = PureWindowsPath(self.path)
        if (
            "\\" in self.path
            or self.path.startswith("/")
            or windows.drive
            or windows.is_absolute()
            or any(part in {"", ".", ".."} for part in posix.parts)
        ):
            raise ValueError("Git object path must be repository-relative POSIX")
        return self


class Gate1SafetyStatus(FrozenGate1Model):
    validation_data_access: Literal[False] = False
    validation_metrics_access: Literal[False] = False
    campaign_results_access: Literal[False] = False
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()
    provider_calls: Literal[0] = 0
    strategy_search_executed: Literal[False] = False
    live_trading_capability: Literal[False] = False


class Gate1AccessEvidence(FrozenGate1Model):
    schema_version: Literal["PHASE4-GATE1-ACCESS-EVIDENCE-v1"] = (
        "PHASE4-GATE1-ACCESS-EVIDENCE-v1"
    )
    observed_reads: tuple[str, ...] = ()
    safety: Gate1SafetyStatus = Gate1SafetyStatus()

    @model_validator(mode="after")
    def validate_reads(self) -> "Gate1AccessEvidence":
        if self.observed_reads != tuple(sorted(set(self.observed_reads))):
            raise ValueError("observed reads must be unique and sorted")
        return self


def _forbidden_path_reason(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    tokens = {
        token.upper()
        for token in re.split(r"[/_.-]+", normalized)
        if token
    }
    if lower == "data/cache" or lower.startswith("data/cache/"):
        return "market cache"
    if "final_holdout" in lower:
        return "FINAL_HOLDOUT"
    protected = sorted(tokens.intersection(PROTECTED_SYMBOLS))
    if protected:
        return f"protected symbol {protected[0]}"
    parts = tuple(part.lower() for part in PurePosixPath(normalized).parts)
    if len(parts) >= 3 and parts[:2] == ("results", "phase4"):
        if any(
            part in {
                "validation",
                "candidate_evidence",
                "campaign",
                "leaderboard",
                "ranking",
                "selection",
                "exports",
            }
            for part in parts[2:]
        ):
            return "Phase 4 campaign or validation output"
    return None


def _artifact_key(
    identity: Gate1ArtifactIdentity,
) -> tuple[str, str, str, str]:
    return (
        identity.kind,
        identity.path,
        identity.content_sha256,
        identity.sha256,
    )


def _git_key(
    identity: Gate1GitObjectIdentity,
) -> tuple[str, str, str, str]:
    return (
        identity.revision,
        identity.path,
        identity.blob,
        identity.content_sha256,
    )


class Gate1ReadCapability:
    def __init__(
        self,
        repository_root: Path,
        *,
        artifacts: tuple[Gate1ArtifactIdentity, ...] = (),
        git_objects: tuple[Gate1GitObjectIdentity, ...] = (),
    ) -> None:
        try:
            repository = Path(repository_root).resolve(strict=True)
        except OSError as exc:
            raise Gate1AccessError("repository root must exist") from exc
        if not repository.is_dir():
            raise Gate1AccessError("repository root must be a directory")
        for identity in artifacts:
            reason = _forbidden_path_reason(identity.path)
            if reason is not None:
                raise Gate1AccessError(
                    f"forbidden Gate 1 resource: {identity.path}: {reason}"
                )
        for identity in git_objects:
            reason = _forbidden_path_reason(identity.path)
            if reason is not None:
                raise Gate1AccessError(
                    f"forbidden Gate 1 resource: {identity.path}: {reason}"
                )
        artifact_keys = tuple(_artifact_key(item) for item in artifacts)
        git_keys = tuple(_git_key(item) for item in git_objects)
        if len(artifact_keys) != len(set(artifact_keys)):
            raise Gate1AccessError("duplicate admitted artifact identity")
        if len(git_keys) != len(set(git_keys)):
            raise Gate1AccessError("duplicate admitted Git object identity")
        self._repository_root = repository
        self._artifact_keys = frozenset(artifact_keys)
        self._git_keys = frozenset(git_keys)
        self._observed_reads: set[str] = set()

    def _artifact_path(self, identity: Gate1ArtifactIdentity) -> Path:
        candidate = self._repository_root
        for component in PurePosixPath(identity.path).parts:
            candidate = candidate / component
            if candidate.is_symlink():
                raise Gate1AccessError(
                    f"artifact path contains symlink component: {identity.path}"
                )
        return candidate

    def read_admitted_artifact(self, identity: Gate1ArtifactIdentity) -> bytes:
        if _artifact_key(identity) not in self._artifact_keys:
            raise Gate1AccessError(f"artifact is not admitted: {identity.path}")
        path = self._artifact_path(identity)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise Gate1AccessError(f"admitted artifact is unreadable: {identity.path}") from exc
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise Gate1AccessError(
                f"admitted artifact content digest mismatch: {identity.path}"
            )
        self._observed_reads.add(
            f"artifact:{identity.kind}:{identity.path}:{identity.content_sha256}"
        )
        return payload

    def read_admitted_git_object(self, identity: Gate1GitObjectIdentity) -> bytes:
        if _git_key(identity) not in self._git_keys:
            raise Gate1AccessError(f"Git object is not admitted: {identity.path}")
        object_name = f"{identity.revision}:{identity.path}"
        resolved = subprocess.run(
            ["git", "rev-parse", object_name],
            cwd=self._repository_root,
            check=False,
            capture_output=True,
        )
        if resolved.returncode != 0 or resolved.stdout.decode("ascii").strip() != identity.blob:
            raise Gate1AccessError(f"admitted Git blob mismatch: {identity.path}")
        read = subprocess.run(
            ["git", "cat-file", "blob", identity.blob],
            cwd=self._repository_root,
            check=False,
            capture_output=True,
        )
        if read.returncode != 0:
            raise Gate1AccessError(f"admitted Git object is unreadable: {identity.path}")
        payload = read.stdout
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise Gate1AccessError(f"admitted Git content digest mismatch: {identity.path}")
        self._observed_reads.add(
            "git:"
            f"{identity.revision}:{identity.path}:{identity.blob}:"
            f"{identity.content_sha256}"
        )
        return payload

    def evidence(self) -> Gate1AccessEvidence:
        return Gate1AccessEvidence(
            observed_reads=tuple(sorted(self._observed_reads)),
            safety=Gate1SafetyStatus(),
        )
