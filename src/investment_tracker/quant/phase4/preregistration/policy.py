from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Mapping

from pydantic import Field, field_validator, model_validator

from .canonical import hypothesis_identity, source_identity
from .models import FrozenGate1Model


class SourceTier(str, Enum):
    PEER_REVIEWED_ACADEMIC = "PEER_REVIEWED_ACADEMIC"
    ACADEMIC_WORKING_PAPER = "ACADEMIC_WORKING_PAPER"
    SSRN = "SSRN"
    ESTABLISHED_QUANTITATIVE_FIRM = "ESTABLISHED_QUANTITATIVE_FIRM"
    CFA_OR_INSTITUTIONAL = "CFA_OR_INSTITUTIONAL"
    OFFICIAL_EXCHANGE_OR_MARKET_RESEARCH = "OFFICIAL_EXCHANGE_OR_MARKET_RESEARCH"
    REPUTABLE_QUANTITATIVE_PRACTITIONER = "REPUTABLE_QUANTITATIVE_PRACTITIONER"
    BLOG_FORUM_OR_SOCIAL_HYPOTHESIS_ONLY = "BLOG_FORUM_OR_SOCIAL_HYPOTHESIS_ONLY"

    @property
    def tier(self) -> int:
        return list(type(self)).index(self) + 1


class ResearchSource(FrozenGate1Model):
    schema_version: Literal["PHASE4-RESEARCH-SOURCE-v1"] = "PHASE4-RESEARCH-SOURCE-v1"
    source_id: str = Field(pattern=r"^source-[0-9a-f]{64}$")
    title: str | None
    authors: tuple[str, ...] | None
    publication: str | None
    year: int | None
    canonical_url: str | None
    source_type: SourceTier
    evidence_role: Literal["SUPPORT", "COUNTEREVIDENCE"]
    retrieved_at: datetime
    methodology: str
    asset_classes: str
    test_period: str | None
    strategy_concept: str
    reported_parameters_horizons: str | None
    mechanism: str
    claimed_findings: str
    limitations: str
    frozen_universe_relevance: str
    primary_evidence_eligible: bool
    primary_evidence_eligibility_reason: str
    citation_verified: bool
    phase4_validation_information_used: Literal[False] = False
    missing_fact_explanations: dict[str, str] = Field(default_factory=dict)

    @staticmethod
    def bibliographic_identity(payload: Mapping[str, object]) -> dict[str, object]:
        return {
            "title": payload.get("title"),
            "authors": payload.get("authors"),
            "publication": payload.get("publication"),
            "year": payload.get("year"),
            "canonical_url": payload.get("canonical_url"),
        }

    @model_validator(mode="after")
    def validate_source(self) -> "ResearchSource":
        missing = {
            name
            for name in ("title", "authors", "publication", "year", "canonical_url")
            if getattr(self, name) is None
        }
        if missing - set(self.missing_fact_explanations):
            raise ValueError("each missing bibliographic fact requires an explanation")
        if any(not value.strip() for value in self.missing_fact_explanations.values()):
            raise ValueError("missing-fact explanations must be non-empty")
        if not self.citation_verified:
            raise ValueError("sealed source citations must be verified")
        if (
            self.source_type is SourceTier.BLOG_FORUM_OR_SOCIAL_HYPOTHESIS_ONLY
            and self.primary_evidence_eligible
        ):
            raise ValueError("Tier 8 cannot be primary evidence eligible")
        expected = source_identity(self.bibliographic_identity(self.model_dump(mode="json")))
        if self.source_id != expected:
            raise ValueError("source identity does not match bibliographic identity")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("retrieval time must be timezone-aware")
        return self


HypothesisState = Literal["PROPOSED", "ADMITTED", "REJECTED_BEFORE_TESTING"]


class HypothesisRecord(FrozenGate1Model):
    schema_version: Literal["PHASE4-HYPOTHESIS-v1"] = "PHASE4-HYPOTHESIS-v1"
    hypothesis_id: str = Field(pattern=r"^phase4-hypothesis-[0-9a-f]{64}$")
    display_name: str
    lifecycle_state: HypothesisState
    supporting_source_ids: tuple[str, ...]
    economic_behavioral_rationale: str
    signal_concept: str
    entry_logic: str
    exit_logic: str
    cross_sectional_ranking_logic: str
    allocation_logic: str
    cash_rule: str
    risk_rule: str
    rebalance_frequency: str
    expected_turnover_class: str
    expected_strengths: tuple[str, ...]
    named_failure_regimes: tuple[str, ...]
    rule_set_mode: Literal["FIXED"] = "FIXED"
    parameter_tuple_mode: Literal["FIXED"] = "FIXED"
    annual_reoptimization: Literal[False] = False
    periodic_reoptimization: Literal[False] = False
    regime_behavior_map: dict[str, str]
    regime_partition_rule: str
    parameter_dimensions: dict[str, tuple[int | float, ...]]
    complete_grid_definition: str
    expected_candidate_count: int = Field(ge=0)
    baseline_distinction: str
    implementation_requirements: tuple[str, ...]
    anti_lookahead_requirements: tuple[str, ...]
    benchmark_expectations: str
    falsification_conditions: tuple[str, ...]
    simplicity_component_count: int = Field(ge=0)
    family_semantic_name: str | None
    family_slots_consumed: Literal[0, 1]
    rejection_reason: str | None = None
    validation_data_accessed: Literal[False] = False
    validation_metrics_accessed: Literal[False] = False
    campaign_results_accessed: Literal[False] = False
    provider_calls: Literal[0] = 0
    strategy_search_executed: Literal[False] = False
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()

    @classmethod
    def semantic_payload(cls, payload: Mapping[str, object]) -> dict[str, object]:
        excluded = {
            "hypothesis_id", "display_name", "schema_version",
            "validation_data_accessed", "validation_metrics_accessed",
            "campaign_results_accessed", "provider_calls",
            "strategy_search_executed", "final_holdout_accessed",
            "protected_symbols_accessed",
        }
        return {key: value for key, value in payload.items() if key not in excluded}

    @classmethod
    def identity_for(cls, payload: Mapping[str, object]) -> str:
        return hypothesis_identity(cls.semantic_payload(payload))

    @model_validator(mode="after")
    def validate_lifecycle_and_identity(self) -> "HypothesisRecord":
        if self.hypothesis_id != self.identity_for(self.model_dump(mode="json")):
            raise ValueError("hypothesis identity does not match semantic payload")
        if self.lifecycle_state == "ADMITTED":
            if self.family_semantic_name is None or self.family_slots_consumed != 1:
                raise ValueError("admitted hypothesis must consume exactly one family slot")
            if self.rejection_reason is not None:
                raise ValueError("admitted hypothesis cannot have a rejection reason")
        elif self.lifecycle_state == "REJECTED_BEFORE_TESTING":
            if self.family_semantic_name is not None or self.family_slots_consumed != 0:
                raise ValueError("rejected hypothesis cannot define or consume a family")
            if not self.rejection_reason:
                raise ValueError("rejected hypothesis requires a reason")
        return self


def enforce_research_cutoff(
    sources: tuple[ResearchSource, ...], cutoff: datetime
) -> tuple[ResearchSource, ...]:
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("research cutoff must be timezone-aware")
    if any(source.retrieved_at > cutoff for source in sources):
        raise ValueError("source retrieved after research cutoff")
    return sources


def validate_hypothesis_registry(
    sources: tuple[ResearchSource, ...], hypotheses: tuple[HypothesisRecord, ...]
) -> tuple[HypothesisRecord, ...]:
    source_by_id = {source.source_id: source for source in sources}
    if len(source_by_id) != len(sources):
        raise ValueError("duplicate source identity")
    admitted = tuple(row for row in hypotheses if row.lifecycle_state == "ADMITTED")
    if not 1 <= len(admitted) <= 10:
        raise ValueError("admitted hypothesis count must be between one and ten")
    families = [row.family_semantic_name for row in admitted]
    if len(set(families)) != len(families):
        raise ValueError("admitted hypotheses must map one-to-one to families")
    for hypothesis in admitted:
        if len(set(hypothesis.supporting_source_ids)) < 2:
            raise ValueError("admitted hypothesis requires at least two sources")
        try:
            support = tuple(source_by_id[item] for item in hypothesis.supporting_source_ids)
        except KeyError as exc:
            raise ValueError("hypothesis cites an unknown source") from exc
        if not all(source.primary_evidence_eligible for source in support):
            raise ValueError("hypothesis support must be primary-evidence eligible")
        if not any(source.source_type.tier <= 3 for source in support):
            raise ValueError("hypothesis needs at least one tier 1-3 source")
    return hypotheses
