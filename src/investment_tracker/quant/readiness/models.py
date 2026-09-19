from __future__ import annotations

from pathlib import PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .constants import ArtifactKind
from .hashing import canonical_sha256, trial_identity


class FrozenReadinessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReadinessArtifactIdentity(FrozenReadinessModel):
    kind: ArtifactKind
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_artifact_identity(self) -> "ReadinessArtifactIdentity":
        components = self.path.split("/")
        if (
            "\\" in self.path
            or self.path.startswith("/")
            or PureWindowsPath(self.path).drive
            or any(component in {"", ".", ".."} for component in components)
        ):
            raise ValueError("artifact identity path must be repository-relative POSIX")
        envelope = {
            "content_sha256": self.content_sha256,
            "kind": self.kind,
            "path": self.path,
        }
        if self.sha256 != canonical_sha256(envelope):
            raise ValueError("artifact identity does not match its canonical envelope")
        return self


class AuthoritativeTrial(FrozenReadinessModel):
    trial_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    campaign_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    authoritative_artifact: ReadinessArtifactIdentity
    non_authoritative_artifacts: tuple[ReadinessArtifactIdentity, ...] = ()

    @model_validator(mode="after")
    def validate_trial_identity(self) -> "AuthoritativeTrial":
        if self.trial_id != trial_identity(self.campaign_id, self.candidate_id):
            raise ValueError("trial identity does not match campaign and candidate")
        return self
