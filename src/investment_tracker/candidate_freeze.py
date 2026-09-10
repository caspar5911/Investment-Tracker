from __future__ import annotations

import hashlib
import json
from datetime import datetime

from pydantic import Field, model_validator

from .governance import FROZEN_VERSIONS
from .models import StrictModel


class FreezeBlockedError(RuntimeError):
    pass


class CandidateFreezeInputs(StrictModel):
    candidate_id: str = Field(min_length=1)
    implementation_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    canonical_input_digests: dict[str, str]
    calculation_versions: dict[str, str]
    test_suite_ref: str = Field(min_length=1)
    tests_passed: bool
    phase_a_complete: bool
    robustness_passed: bool
    independent_recompute_passed: bool
    robustness_result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    unresolved_limitations: list[str]
    frozen_at: datetime

    @model_validator(mode="after")
    def validate_versions_and_digests(self) -> "CandidateFreezeInputs":
        if self.calculation_versions != FROZEN_VERSIONS.as_dict():
            raise ValueError("candidate versions differ from frozen governance")
        if not self.canonical_input_digests:
            raise ValueError("canonical input digests are required")
        return self


class CandidateFreezeRecord(StrictModel):
    candidate_id: str
    implementation_sha: str
    canonical_input_digests: dict[str, str]
    calculation_versions: dict[str, str]
    test_suite_ref: str
    robustness_result_digest: str
    unresolved_limitations: list[str]
    frozen_at: datetime
    candidate_output_digest: str
    status: str


def freeze_candidate(inputs: CandidateFreezeInputs) -> CandidateFreezeRecord:
    failed = [
        name for name in (
            "tests_passed", "phase_a_complete", "robustness_passed",
            "independent_recompute_passed",
        ) if not getattr(inputs, name)
    ]
    if failed:
        raise FreezeBlockedError("candidate freeze blocked: " + ", ".join(failed))
    payload = inputs.model_dump(mode="json")
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return CandidateFreezeRecord(
        candidate_id=inputs.candidate_id,
        implementation_sha=inputs.implementation_sha,
        canonical_input_digests=inputs.canonical_input_digests,
        calculation_versions=inputs.calculation_versions,
        test_suite_ref=inputs.test_suite_ref,
        robustness_result_digest=inputs.robustness_result_digest,
        unresolved_limitations=inputs.unresolved_limitations,
        frozen_at=inputs.frozen_at,
        candidate_output_digest=digest,
        status="FROZEN_CANDIDATE_NOT_PRODUCTION_APPROVED",
    )
