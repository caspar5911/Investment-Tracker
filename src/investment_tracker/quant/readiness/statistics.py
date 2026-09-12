from __future__ import annotations

import math
from typing import Literal, Mapping

from pydantic import Field, model_validator

from investment_tracker.quant.experiments import ExperimentRecord

from .constants import PHASE2_CAMPAIGN_ID
from .models import FrozenReadinessModel
from .trials import (
    HISTORICAL_PHASE2_TRIAL_COUNT,
    TrialAuthorityManifest,
    classify_representation,
)


class SearchAwareInputError(RuntimeError):
    """Raised when trial-keyed statistical inputs are incomplete or inconsistent."""


class Phase4BudgetError(RuntimeError):
    """Raised when Phase 4 operational trial accounting would exceed policy."""


class TrialSharpeInput(FrozenReadinessModel):
    trial_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    value: float | None


class SearchAwareInputSet(FrozenReadinessModel):
    schema_version: Literal["PHASE4-SEARCH-AWARE-INPUTS-v1"] = (
        "PHASE4-SEARCH-AWARE-INPUTS-v1"
    )
    historical_trial_count: Literal[136] = HISTORICAL_PHASE2_TRIAL_COUNT
    multiple_testing_count: Literal[136] = HISTORICAL_PHASE2_TRIAL_COUNT
    ordered_sharpe_trial_ids: tuple[str, ...] = Field(min_length=136, max_length=136)
    ordered_pbo_trial_ids: tuple[str, ...] = Field(min_length=136, max_length=136)
    sharpe_inputs: tuple[TrialSharpeInput, ...] = Field(min_length=136, max_length=136)

    @model_validator(mode="after")
    def validate_trial_keys(self) -> "SearchAwareInputSet":
        sharpe_ids = tuple(item.trial_id for item in self.sharpe_inputs)
        if self.ordered_sharpe_trial_ids != sharpe_ids:
            raise ValueError("Sharpe inputs must match ordered trial IDs")
        if self.ordered_pbo_trial_ids != self.ordered_sharpe_trial_ids:
            raise ValueError("PBO placeholders must match authoritative trial IDs")
        if len(set(self.ordered_sharpe_trial_ids)) != HISTORICAL_PHASE2_TRIAL_COUNT:
            raise ValueError("search-aware trial IDs must be unique")
        return self


class SearchAwareStatisticResult(FrozenReadinessModel):
    schema_version: Literal["PHASE4-SEARCH-STATISTIC-v1"] = (
        "PHASE4-SEARCH-STATISTIC-v1"
    )
    name: Literal["DSR", "PBO"]
    status: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"
    interpretation: Literal["UNKNOWN"] = "UNKNOWN"
    value: None = None
    reason: str = Field(min_length=1)


class Phase4BudgetState(FrozenReadinessModel):
    schema_version: Literal["PHASE4-BUDGET-STATE-v1"] = "PHASE4-BUDGET-STATE-v1"
    historical_phase2_trial_count: Literal[136] = HISTORICAL_PHASE2_TRIAL_COUNT
    phase4_new_trials_consumed: int = Field(default=0, ge=0, le=3000)
    phase4_new_trials_remaining: int = Field(default=3000, ge=0, le=3000)
    phase4_historical_trials_consume_budget: Literal[False] = False
    maximum_new_strategy_families: Literal[10] = 10
    maximum_candidate_trials_per_family: Literal[500] = 500
    maximum_aggregate_new_candidate_trials: Literal[3000] = 3000
    consumed_candidate_ids: tuple[str, ...] = ()
    last_consumed_budget_position: int | None = Field(default=None, ge=1, le=3000)

    @model_validator(mode="after")
    def validate_budget_accounting(self) -> "Phase4BudgetState":
        if self.phase4_new_trials_consumed != len(self.consumed_candidate_ids):
            raise ValueError("Phase 4 consumed count must equal candidate IDs")
        if len(set(self.consumed_candidate_ids)) != len(self.consumed_candidate_ids):
            raise ValueError("Phase 4 candidate IDs must be unique")
        if any(not candidate_id.startswith("phase4-") for candidate_id in self.consumed_candidate_ids):
            raise ValueError("historical candidate IDs cannot consume Phase 4 budget")
        expected_remaining = (
            self.maximum_aggregate_new_candidate_trials
            - self.phase4_new_trials_consumed
        )
        if self.phase4_new_trials_remaining != expected_remaining:
            raise ValueError("Phase 4 remaining count does not match aggregate budget")
        expected_position = (
            self.phase4_new_trials_consumed
            if self.phase4_new_trials_consumed
            else None
        )
        if self.last_consumed_budget_position != expected_position:
            raise ValueError("last consumed position must use Phase 4-only numbering")
        return self

    @classmethod
    def initial(cls) -> "Phase4BudgetState":
        return cls()

    def consume(self, candidate_id: str) -> "Phase4BudgetState":
        if not isinstance(candidate_id, str) or not candidate_id.startswith("phase4-"):
            raise Phase4BudgetError("only Phase 4 candidate IDs may consume budget")
        if candidate_id in self.consumed_candidate_ids:
            raise Phase4BudgetError(f"candidate budget already consumed: {candidate_id}")
        if self.phase4_new_trials_consumed >= self.maximum_aggregate_new_candidate_trials:
            raise Phase4BudgetError("Phase 4 aggregate candidate budget exhausted")
        consumed = self.phase4_new_trials_consumed + 1
        return Phase4BudgetState(
            phase4_new_trials_consumed=consumed,
            phase4_new_trials_remaining=(
                self.maximum_aggregate_new_candidate_trials - consumed
            ),
            consumed_candidate_ids=(*self.consumed_candidate_ids, candidate_id),
            last_consumed_budget_position=consumed,
        )


def build_search_aware_inputs(
    authority: TrialAuthorityManifest,
    records: Mapping[str, ExperimentRecord],
) -> SearchAwareInputSet:
    ordered_ids = tuple(trial.trial_id for trial in authority.trials)
    if set(records) != set(ordered_ids) or len(records) != len(ordered_ids):
        raise SearchAwareInputError(
            "authoritative record trial IDs do not match trial authority"
        )

    sharpe_inputs = []
    for trial in authority.trials:
        record = records[trial.trial_id]
        if (
            trial.campaign_id != PHASE2_CAMPAIGN_ID
            or record.candidate_manifest.candidate_id != trial.candidate_id
            or classify_representation(record) != "FINAL_AUTHORITATIVE"
        ):
            raise SearchAwareInputError(
                f"authoritative record does not match trial ID: {trial.trial_id}"
            )
        raw_sharpe = record.validation_metrics.get("sharpe")
        value = (
            float(raw_sharpe)
            if isinstance(raw_sharpe, (int, float))
            and not isinstance(raw_sharpe, bool)
            and math.isfinite(float(raw_sharpe))
            else None
        )
        sharpe_inputs.append(TrialSharpeInput(trial_id=trial.trial_id, value=value))

    return SearchAwareInputSet(
        ordered_sharpe_trial_ids=ordered_ids,
        ordered_pbo_trial_ids=ordered_ids,
        sharpe_inputs=tuple(sharpe_inputs),
    )


def unimplemented_search_statistic(
    name: Literal["DSR", "PBO"],
    reason: str,
) -> SearchAwareStatisticResult:
    return SearchAwareStatisticResult(name=name, reason=reason)
