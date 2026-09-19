from __future__ import annotations

from itertools import product
from typing import Literal

from pydantic import Field, model_validator

from .canonical import (
    candidate_identity,
    candidate_parameter_population_identity,
    canonical_parameter_map,
    canonical_sha256,
    family_identity,
    parameter_tuple_identity,
    rule_set_identity,
    trial_identity,
)
from .models import FrozenGate1Model
from .policy import HypothesisRecord, validate_hypothesis_registry
from .campaign_definition import RESEARCH_SOURCES


PHASE4_CAMPAIGN_ID = "PHASE4-FIXED-LONG-ONLY-2014-2022-v1"


class BudgetLimitError(ValueError):
    """Raised before publication when a preregistered budget is invalid."""


class GridCandidate(FrozenGate1Model):
    schema_version: Literal["PHASE4-GRID-CANDIDATE-v1"] = "PHASE4-GRID-CANDIDATE-v1"
    campaign_id: Literal["PHASE4-FIXED-LONG-ONLY-2014-2022-v1"] = PHASE4_CAMPAIGN_ID
    hypothesis_id: str
    family_id: str
    raw_parameters: dict[str, int | float]
    parameters: dict[str, dict[str, object]]
    parameter_tuple_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_id: str = Field(pattern=r"^phase4-[0-9a-f]{64}$")
    trial_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget_position: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_identities(self) -> "GridCandidate":
        if self.parameters != canonical_parameter_map(self.raw_parameters):
            raise ValueError("typed parameter map mismatch")
        if self.parameter_tuple_sha256 != parameter_tuple_identity(
            self.family_id, self.parameters
        ):
            raise ValueError("parameter tuple identity mismatch")
        if self.candidate_id != candidate_identity(
            campaign_id=self.campaign_id,
            hypothesis_id=self.hypothesis_id,
            family_id=self.family_id,
            parameters=self.parameters,
        ):
            raise ValueError("candidate identity mismatch")
        if self.trial_id != trial_identity(self.campaign_id, self.candidate_id):
            raise ValueError("trial identity mismatch")
        return self


class StrategyFamilyDefinition(FrozenGate1Model):
    schema_version: Literal["PHASE4-STRATEGY-FAMILY-DEFINITION-v1"] = (
        "PHASE4-STRATEGY-FAMILY-DEFINITION-v1"
    )
    family_id: str = Field(pattern=r"^phase4-family-[0-9a-f]{64}$")
    family_semantic_name: str
    hypothesis_id: str
    supporting_source_ids: tuple[str, ...]
    human_name: str
    economic_mechanism: str
    input_fields: tuple[str, ...]
    warmup_rule: str
    signal_algorithm: str
    ranking_algorithm: str
    allocation_algorithm: str
    cash_rule: str
    risk_rule: str
    rebalance_rule: str
    execution_timing_rule: str
    long_only_no_leverage_invariants: tuple[str, ...]
    regime_partition_algorithm: str
    implementation_interface: str
    parameter_dimensions: dict[str, tuple[dict[str, object], ...]]
    structural_parameters: dict[str, dict[str, object]]
    structural_predicates: tuple[str, ...]
    grid_spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    neighborhood_rule: Literal["ADJACENT_DECLARED_VALUE_IN_EXACTLY_ONE_DIMENSION"]
    component_count: int
    expected_failure_regimes: tuple[str, ...]
    baseline_distinction: str
    rule_set_mode: Literal["FIXED"] = "FIXED"
    parameter_tuple_mode: Literal["FIXED"] = "FIXED"
    annual_reoptimization: Literal[False] = False
    periodic_reoptimization: Literal[False] = False
    long_only: Literal[True] = True
    leverage_allowed: Literal[False] = False
    maximum_gross_exposure: Literal[1.0] = 1.0
    expected_candidate_count: int = Field(ge=1, le=500)
    rule_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    family_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidates: tuple[GridCandidate, ...]

    @model_validator(mode="after")
    def validate_definition(self) -> "StrategyFamilyDefinition":
        semantic = _family_semantic_projection(self)
        if self.family_id != family_identity(semantic):
            raise ValueError("family identity mismatch")
        expected_grid = canonical_sha256({
            "parameter_dimensions": self.parameter_dimensions,
            "structural_parameters": self.structural_parameters,
            "structural_predicates": self.structural_predicates,
        })
        if self.grid_spec_sha256 != expected_grid:
            raise ValueError("grid specification identity mismatch")
        if self.rule_set_sha256 != rule_set_identity(
            self.family_id, self.model_dump(mode="json")
        ):
            raise ValueError("rule-set identity mismatch")
        definition_payload = self.model_dump(
            mode="json", exclude={"candidates", "family_definition_sha256"}
        )
        expected_definition = canonical_sha256({
            "schema_version": "PHASE4-FAMILY-DEFINITION-IDENTITY-v1",
            "family_definition": definition_payload,
        })
        if self.family_definition_sha256 != expected_definition:
            raise ValueError("family definition identity mismatch")
        if len(self.candidates) != self.expected_candidate_count:
            raise ValueError("expanded grid count mismatch")
        names = tuple(self.parameter_dimensions)
        values = tuple(
            tuple(_decode_value(value) for value in self.parameter_dimensions[name])
            for name in names
        )
        expected_rows = tuple(
            dict(zip(names, combination, strict=True)) for combination in product(*values)
        )
        observed_rows = tuple(candidate.raw_parameters for candidate in self.candidates)
        if observed_rows != expected_rows:
            raise ValueError("candidates do not reproduce the declared Cartesian grid")
        if any(
            candidate.family_id != self.family_id
            or candidate.hypothesis_id != self.hypothesis_id
            for candidate in self.candidates
        ):
            raise ValueError("candidate family or hypothesis cross-link mismatch")
        return self

    def neighbors(self, parameter_tuple_sha256: str) -> tuple[GridCandidate, ...]:
        by_tuple = {item.parameter_tuple_sha256: item for item in self.candidates}
        if parameter_tuple_sha256 not in by_tuple:
            raise ValueError("unknown parameter tuple")
        target = by_tuple[parameter_tuple_sha256]
        raw_dimensions = {
            name: tuple(_decode_value(value) for value in values)
            for name, values in self.parameter_dimensions.items()
        }
        adjacent: list[GridCandidate] = []
        for candidate in self.candidates:
            changed = [
                name
                for name in raw_dimensions
                if candidate.raw_parameters[name] != target.raw_parameters[name]
            ]
            if len(changed) != 1:
                continue
            name = changed[0]
            values = raw_dimensions[name]
            left = values.index(target.raw_parameters[name])
            right = values.index(candidate.raw_parameters[name])
            if abs(left - right) == 1:
                adjacent.append(candidate)
        return tuple(adjacent)


class BudgetPolicy(FrozenGate1Model):
    schema_version: Literal["PHASE4-BUDGET-POLICY-v1"] = "PHASE4-BUDGET-POLICY-v1"
    maximum_new_families: Literal[10] = 10
    maximum_candidates_per_family: Literal[500] = 500
    maximum_aggregate_candidates: Literal[3000] = 3000
    historical_phase2_trials: Literal[136] = 136
    historical_trials_are_lineage_only: Literal[True] = True
    initial_phase4_consumption: Literal[0] = 0
    baseline_family_slots_consumed: Literal[0] = 0
    baseline_candidate_trials_consumed: Literal[0] = 0
    duplicates_consume_additional_budget: Literal[False] = False
    first_future_budget_position: Literal[1] = 1
    admitted_family_count: int
    aggregate_candidate_count: int


class PreregisteredGrids(FrozenGate1Model):
    schema_version: Literal["PHASE4-DETERMINISTIC-GRIDS-v1"] = "PHASE4-DETERMINISTIC-GRIDS-v1"
    campaign_id: Literal["PHASE4-FIXED-LONG-ONLY-2014-2022-v1"] = PHASE4_CAMPAIGN_ID
    families: tuple[StrategyFamilyDefinition, ...]
    candidates: tuple[GridCandidate, ...]
    candidate_parameter_population_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget_policy: BudgetPolicy

    @model_validator(mode="after")
    def validate_population(self) -> "PreregisteredGrids":
        if self.families != tuple(sorted(self.families, key=lambda row: row.family_id)):
            raise ValueError("families must be family-ID sorted")
        if tuple(row.budget_position for row in self.candidates) != tuple(
            range(1, len(self.candidates) + 1)
        ):
            raise ValueError("budget positions must be contiguous from one")
        flattened = tuple(item for family in self.families for item in family.candidates)
        if flattened != self.candidates:
            raise ValueError("family grids do not match aggregate candidate order")
        population = tuple(
            {"candidate_id": row.candidate_id,
             "parameter_tuple_sha256": row.parameter_tuple_sha256}
            for row in self.candidates
        )
        if self.candidate_parameter_population_sha256 != candidate_parameter_population_identity(population):
            raise ValueError("candidate population identity mismatch")
        if self.budget_policy.aggregate_candidate_count != len(self.candidates):
            raise ValueError("budget aggregate count mismatch")
        if self.budget_policy.admitted_family_count != len(self.families):
            raise ValueError("budget admitted family count mismatch")
        return self


ALGORITHMS = {
    "cross_sectional_absolute_momentum_rotation": {
        "input_fields": ("date", "close"),
        "warmup_rule": "Earlier TRAIN closes may initialize lagged returns only; no fit or P&L carryover.",
        "signal_algorithm": "At t, compute close[t-skip]/close[t-lookback-skip]-1 for each ETF.",
        "ranking_algorithm": "Keep positive finite scores; sort descending score then ascending symbol; select top_k.",
        "allocation_algorithm": "Assign equal weight 1/n to selected ETFs.",
        "cash_rule": "No eligible ETF means 100% cash; any residual remains cash.",
        "risk_rule": "No short, leverage, or gross exposure above 1.0.",
        "rebalance_rule": "Recompute every parameterized rebalance_sessions from the first scored session.",
    },
    "diversified_time_series_momentum": {
        "input_fields": ("date", "close"),
        "warmup_rule": "Earlier TRAIN closes may initialize lagged return and volatility indicators only; no fit or P&L carryover.",
        "signal_algorithm": "At t, admit each ETF only when its lookback_sessions trailing return is positive.",
        "ranking_algorithm": "NOT_APPLICABLE; process admitted symbols in ascending symbol order.",
        "allocation_algorithm": "Inverse lagged volatility weights with deterministic iterative maximum_asset_weight cap redistribution.",
        "cash_rule": "No eligible ETF means 100% cash; non-redistributable residual remains cash.",
        "risk_rule": "Finite positive volatility required; no short, leverage, or gross exposure above 1.0.",
        "rebalance_rule": "Recompute every parameterized rebalance_sessions from the first scored session.",
    },
    "volatility_managed_relative_momentum": {
        "input_fields": ("date", "close"),
        "warmup_rule": "Earlier TRAIN closes may initialize return and covariance indicators only; no fit or P&L carryover.",
        "signal_algorithm": "At t, compute each ETF's lookback_sessions trailing return and admit only positive scores.",
        "ranking_algorithm": "Sort descending score then ascending symbol and select fixed top_k.",
        "allocation_algorithm": "Equal weight selected ETFs, then scale by target_portfolio_volatility divided by lagged covariance volatility.",
        "cash_rule": "No eligible ETF means 100% cash; exposure below 1.0 leaves residual cash.",
        "risk_rule": "Scale is finite, nonnegative, and capped so gross exposure never exceeds 1.0.",
        "rebalance_rule": "Recompute every fixed 21 observations from the first scored session.",
    },
    "trend_filtered_equal_risk_allocation": {
        "input_fields": ("date", "close"),
        "warmup_rule": "Earlier TRAIN closes may initialize moving-average and volatility indicators only; no fit or P&L carryover.",
        "signal_algorithm": "At t, admit each ETF only when lagged close is strictly above its trend_window simple moving average.",
        "ranking_algorithm": "NOT_APPLICABLE; process admitted symbols in ascending symbol order.",
        "allocation_algorithm": "Inverse lagged volatility weights with deterministic iterative maximum_asset_weight cap redistribution.",
        "cash_rule": "No eligible ETF means 100% cash; non-redistributable residual remains cash.",
        "risk_rule": "Finite positive volatility required; no short, leverage, or gross exposure above 1.0.",
        "rebalance_rule": "Recompute every parameterized rebalance_sessions from the first scored session.",
    },
}


def _family_semantic_projection(
    family: StrategyFamilyDefinition,
) -> dict[str, object]:
    return {
        "schema_version": "PHASE4-STRATEGY-FAMILY-SEMANTIC-v1",
        "family_semantic_name": family.family_semantic_name,
        "hypothesis_id": family.hypothesis_id,
        "supporting_source_ids": family.supporting_source_ids,
        "input_fields": family.input_fields,
        "warmup_rule": family.warmup_rule,
        "signal_algorithm": family.signal_algorithm,
        "ranking_algorithm": family.ranking_algorithm,
        "allocation_algorithm": family.allocation_algorithm,
        "cash_rule": family.cash_rule,
        "risk_rule": family.risk_rule,
        "rebalance_rule": family.rebalance_rule,
        "execution_timing_rule": family.execution_timing_rule,
        "long_only_no_leverage_invariants": family.long_only_no_leverage_invariants,
        "regime_partition_algorithm": family.regime_partition_algorithm,
        "implementation_interface": family.implementation_interface,
        "parameter_dimensions": family.parameter_dimensions,
        "structural_parameters": family.structural_parameters,
        "structural_predicates": family.structural_predicates,
        "grid_spec_sha256": family.grid_spec_sha256,
        "baseline_distinction": family.baseline_distinction,
    }


def _decode_value(value: dict[str, object]) -> int | float:
    if value["type"] == "int":
        return int(str(value["value"]))
    if value["type"] == "float64_hex":
        return float.fromhex(str(value["value"]))
    raise ValueError("unsupported parameter value")


def _family_semantic_payload(hypothesis: HypothesisRecord) -> dict[str, object]:
    algorithm = ALGORITHMS[hypothesis.family_semantic_name or ""]
    dimensions = {
        name: tuple(canonical_parameter_map({name: value})[name] for value in values)
        for name, values in sorted(hypothesis.parameter_dimensions.items())
    }
    structural = (
        {"rebalance_sessions": canonical_parameter_map({"rebalance_sessions": 21})["rebalance_sessions"]}
        if hypothesis.family_semantic_name == "volatility_managed_relative_momentum"
        else {}
    )
    grid_spec = {
        "parameter_dimensions": dimensions,
        "structural_parameters": structural,
        "structural_predicates": ("ALL_CARTESIAN_ROWS_VALID",),
    }
    return {
        "schema_version": "PHASE4-STRATEGY-FAMILY-SEMANTIC-v1",
        "family_semantic_name": hypothesis.family_semantic_name,
        "hypothesis_id": hypothesis.hypothesis_id,
        "supporting_source_ids": hypothesis.supporting_source_ids,
        "input_fields": algorithm["input_fields"],
        "warmup_rule": algorithm["warmup_rule"],
        "signal_algorithm": algorithm["signal_algorithm"],
        "ranking_algorithm": algorithm["ranking_algorithm"],
        "allocation_algorithm": algorithm["allocation_algorithm"],
        "cash_rule": algorithm["cash_rule"],
        "risk_rule": algorithm["risk_rule"],
        "rebalance_rule": algorithm["rebalance_rule"],
        "execution_timing_rule": "A signal formed on session t executes only on the next eligible session.",
        "long_only_no_leverage_invariants": ("weights are nonnegative", "sum of risky weights is at most 1.0", "no borrowing or shorting"),
        "regime_partition_algorithm": hypothesis.regime_partition_rule,
        "implementation_interface": "PHASE4-FIXED-LONG-ONLY-STRATEGY-v1",
        "parameter_dimensions": dimensions,
        "structural_parameters": structural,
        "structural_predicates": ("ALL_CARTESIAN_ROWS_VALID",),
        "grid_spec_sha256": canonical_sha256(grid_spec),
        "baseline_distinction": hypothesis.baseline_distinction,
    }


def _expand_family(hypothesis: HypothesisRecord) -> StrategyFamilyDefinition:
    semantic = _family_semantic_payload(hypothesis)
    family_id = family_identity(semantic)
    names = tuple(sorted(hypothesis.parameter_dimensions))
    values = tuple(hypothesis.parameter_dimensions[name] for name in names)
    candidates: list[GridCandidate] = []
    for combination in product(*values):
        raw = dict(zip(names, combination, strict=True))
        typed = canonical_parameter_map(raw)
        tuple_sha = parameter_tuple_identity(family_id, typed)
        candidate_id = candidate_identity(
            campaign_id=PHASE4_CAMPAIGN_ID,
            hypothesis_id=hypothesis.hypothesis_id,
            family_id=family_id,
            parameters=typed,
        )
        candidates.append(
            GridCandidate(
                hypothesis_id=hypothesis.hypothesis_id,
                family_id=family_id,
                raw_parameters=raw,
                parameters=typed,
                parameter_tuple_sha256=tuple_sha,
                candidate_id=candidate_id,
                trial_id=trial_identity(PHASE4_CAMPAIGN_ID, candidate_id),
                budget_position=0,
            )
        )
    if len({row.candidate_id for row in candidates}) != len(candidates):
        raise BudgetLimitError("duplicate candidates in family grid")
    payload = {
        **semantic,
        "schema_version": "PHASE4-STRATEGY-FAMILY-DEFINITION-v1",
        "family_id": family_id,
        "human_name": hypothesis.display_name,
        "economic_mechanism": hypothesis.economic_behavioral_rationale,
        "neighborhood_rule": "ADJACENT_DECLARED_VALUE_IN_EXACTLY_ONE_DIMENSION",
        "component_count": hypothesis.simplicity_component_count,
        "expected_failure_regimes": hypothesis.named_failure_regimes,
        "rule_set_mode": "FIXED",
        "parameter_tuple_mode": "FIXED",
        "annual_reoptimization": False,
        "periodic_reoptimization": False,
        "long_only": True,
        "leverage_allowed": False,
        "maximum_gross_exposure": 1.0,
        "expected_candidate_count": hypothesis.expected_candidate_count,
    }
    payload["rule_set_sha256"] = rule_set_identity(family_id, payload)
    payload["family_definition_sha256"] = canonical_sha256({
        "schema_version": "PHASE4-FAMILY-DEFINITION-IDENTITY-v1",
        "family_definition": payload,
    })
    return StrategyFamilyDefinition(**payload, candidates=tuple(candidates))


def validate_budget_counts(
    family_count: int,
    candidate_ids: list[str] | tuple[str, ...],
    per_family_candidate_ids: dict[str, list[str] | tuple[str, ...]],
) -> int:
    if family_count > 10:
        raise BudgetLimitError("new family limit exceeded")
    if family_count < 1:
        raise BudgetLimitError("at least one family is required")
    for values in per_family_candidate_ids.values():
        if len(set(values)) > 500:
            raise BudgetLimitError("per-family candidate limit exceeded")
    unique = len(set(candidate_ids))
    if unique > 3000:
        raise BudgetLimitError("aggregate candidate limit exceeded")
    if unique < 1:
        raise BudgetLimitError("at least one candidate is required")
    return unique


def build_preregistered_grids(
    hypotheses: tuple[HypothesisRecord, ...],
) -> PreregisteredGrids:
    validate_hypothesis_registry(RESEARCH_SOURCES, hypotheses)
    families = sorted((_expand_family(row) for row in hypotheses), key=lambda row: row.family_id)
    next_position = 1
    positioned_families: list[StrategyFamilyDefinition] = []
    all_candidates: list[GridCandidate] = []
    for family in families:
        positioned = tuple(
            row.model_copy(update={"budget_position": next_position + offset})
            for offset, row in enumerate(family.candidates)
        )
        next_position += len(positioned)
        updated = family.model_copy(update={"candidates": positioned})
        positioned_families.append(updated)
        all_candidates.extend(positioned)
    count = validate_budget_counts(
        len(positioned_families),
        [row.candidate_id for row in all_candidates],
        {row.family_id: [item.candidate_id for item in row.candidates] for row in positioned_families},
    )
    population = tuple(
        {"candidate_id": row.candidate_id, "parameter_tuple_sha256": row.parameter_tuple_sha256}
        for row in all_candidates
    )
    return PreregisteredGrids(
        families=tuple(positioned_families),
        candidates=tuple(all_candidates),
        candidate_parameter_population_sha256=candidate_parameter_population_identity(population),
        budget_policy=BudgetPolicy(admitted_family_count=len(positioned_families), aggregate_candidate_count=count),
    )
