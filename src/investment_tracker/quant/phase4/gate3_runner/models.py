from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity
from investment_tracker.quant.phase4.preregistration.canonical import canonical_sha256


class FrozenRunnerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AttemptRecord(FrozenRunnerModel):
    schema_version: Literal["PHASE4-GATE3-RUNNER-ATTEMPT-v1"] = (
        "PHASE4-GATE3-RUNNER-ATTEMPT-v1"
    )
    campaign_id: Literal["PHASE4-FIXED-LONG-ONLY-2014-2022-v1"] = (
        "PHASE4-FIXED-LONG-ONLY-2014-2022-v1"
    )
    population_position: int = Field(ge=1, le=180)
    candidate_id: str = Field(pattern=r"^phase4-[0-9a-f]{64}$")
    trial_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    family_id: str = Field(pattern=r"^phase4-family-[0-9a-f]{64}$")
    runner_manifest: ArtifactIdentity
    status: Literal["ATTEMPT_STARTED"] = "ATTEMPT_STARTED"


ResultStatus = Literal[
    "EXECUTED",
    "UNKNOWN",
    "ABSTAIN",
    "SKIPPED_FAMILY_STOP",
    "CAMPAIGN_EXECUTION_FAILED",
]


class PositionReceipt(FrozenRunnerModel):
    schema_version: Literal["PHASE4-GATE3-RUNNER-RECEIPT-v1"] = (
        "PHASE4-GATE3-RUNNER-RECEIPT-v1"
    )
    campaign_id: Literal["PHASE4-FIXED-LONG-ONLY-2014-2022-v1"] = (
        "PHASE4-FIXED-LONG-ONLY-2014-2022-v1"
    )
    population_position: int = Field(ge=1, le=180)
    candidate_id: str = Field(pattern=r"^phase4-[0-9a-f]{64}$")
    trial_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    runner_manifest: ArtifactIdentity
    result_artifact: ArtifactIdentity
    result_status: ResultStatus


class CampaignResultSet(FrozenRunnerModel):
    schema_version: Literal["PHASE4-GATE3-CAMPAIGN-RESULT-SET-v1"] = (
        "PHASE4-GATE3-CAMPAIGN-RESULT-SET-v1"
    )
    campaign_id: Literal["PHASE4-FIXED-LONG-ONLY-2014-2022-v1"] = (
        "PHASE4-FIXED-LONG-ONLY-2014-2022-v1"
    )
    runner_manifest: ArtifactIdentity
    expected_positions: Literal[180] = 180
    result_artifacts: tuple[ArtifactIdentity, ...] = Field(min_length=180, max_length=180)
    aggregate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["GATE3_CAMPAIGN_RESULTS_COMPLETE"] = (
        "GATE3_CAMPAIGN_RESULTS_COMPLETE"
    )

    @model_validator(mode="after")
    def validate_aggregate(self) -> "CampaignResultSet":
        if len({item.content_sha256 for item in self.result_artifacts}) != 180:
            raise ValueError("CAMPAIGN_RESULT_SET_DUPLICATE")
        if any(
            item.kind != "phase4_gate3_candidate_result"
            for item in self.result_artifacts
        ):
            raise ValueError("CAMPAIGN_RESULT_SET_KIND_INVALID")
        expected = canonical_sha256(
            {
                "schema_version": "PHASE4-GATE3-CAMPAIGN-RESULT-SET-IDENTITY-v1",
                "runner_manifest": self.runner_manifest.model_dump(mode="json"),
                "results": [item.model_dump(mode="json") for item in self.result_artifacts],
            }
        )
        if self.aggregate_sha256 != expected:
            raise ValueError("CAMPAIGN_RESULT_SET_IDENTITY_MISMATCH")
        return self


__all__ = (
    "AttemptRecord",
    "CampaignResultSet",
    "PositionReceipt",
    "ResultStatus",
)
