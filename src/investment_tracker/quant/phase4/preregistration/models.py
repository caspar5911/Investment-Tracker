from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .canonical import artifact_envelope_identity


ArtifactKind = Literal[
    "phase4_readiness_manifest",
    "phase4_split_manifest",
    "trial_authority",
    "phase2_experiment",
    "baseline_definitions",
    "strategy_family_definitions",
    "deterministic_grids",
    "family_budget_policy",
    "durability_policy",
    "survivor_policy",
    "information_access_policy",
    "research_report",
    "phase4_preregistration_manifest",
]


class FrozenGate1Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Gate1ArtifactIdentity(FrozenGate1Model):
    kind: ArtifactKind
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_envelope(self) -> "Gate1ArtifactIdentity":
        posix = PurePosixPath(self.path)
        windows = PureWindowsPath(self.path)
        if (
            "\\" in self.path
            or self.path.startswith("/")
            or windows.drive
            or windows.is_absolute()
            or any(part in {"", ".", ".."} for part in posix.parts)
        ):
            raise ValueError("artifact path must be repository-relative POSIX")
        expected = artifact_envelope_identity(
            content_sha256=self.content_sha256,
            kind=self.kind,
            path=self.path,
        )
        if self.sha256 != expected:
            raise ValueError("artifact identity does not match canonical envelope")
        return self
