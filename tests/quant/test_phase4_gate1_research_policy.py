from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from investment_tracker.quant.phase4.preregistration.campaign_definition import (
    ADMITTED_HYPOTHESES,
    REJECTED_HYPOTHESES,
    RESEARCH_SOURCES,
)
from investment_tracker.quant.phase4.preregistration.policy import (
    HypothesisRecord,
    ResearchSource,
    SourceTier,
    enforce_research_cutoff,
    validate_hypothesis_registry,
)


def test_nine_sources_are_verified_complete_and_never_use_validation_information() -> None:
    assert len(RESEARCH_SOURCES) == 9
    assert len({source.source_id for source in RESEARCH_SOURCES}) == 9
    required = {
        "title", "authors", "publication", "year", "canonical_url",
        "source_type", "retrieved_at", "methodology", "asset_classes",
        "evidence_role",
        "test_period", "strategy_concept", "reported_parameters_horizons",
        "mechanism", "claimed_findings", "limitations",
        "frozen_universe_relevance", "primary_evidence_eligible",
        "primary_evidence_eligibility_reason", "citation_verified",
        "phase4_validation_information_used",
    }
    for source in RESEARCH_SOURCES:
        assert required <= set(source.model_fields)
        assert source.citation_verified is True
        assert source.phase4_validation_information_used is False
        assert source.primary_evidence_eligible is True
        assert 1 <= source.source_type.tier <= 4
    assert sum(source.evidence_role == "COUNTEREVIDENCE" for source in RESEARCH_SOURCES) == 2


def test_independently_checked_bibliographic_corrections_are_frozen() -> None:
    by_doi = {source.canonical_url: source for source in RESEARCH_SOURCES}
    assert by_doi["https://doi.org/10.1016/j.jfineco.2019.08.004"].authors == (
        "Dashan Huang", "Jiangyuan Li", "Liyao Wang", "Guofu Zhou"
    )
    assert by_doi["https://doi.org/10.1016/j.jfineco.2020.04.015"].authors[-1] == (
        "Xuemin (Sterling) Yan"
    )
    aqr = next(source for source in RESEARCH_SOURCES if source.title == "A Century of Evidence on Trend-Following Investing")
    assert aqr.authors[0] == "Brian K. Hurst"
    assert aqr.source_type is SourceTier.PEER_REVIEWED_ACADEMIC


def test_source_tiers_are_closed_and_tier_eight_cannot_be_primary() -> None:
    assert [item.tier for item in SourceTier] == list(range(1, 9))
    source = RESEARCH_SOURCES[0].model_copy(
        update={"source_type": SourceTier.BLOG_FORUM_OR_SOCIAL_HYPOTHESIS_ONLY,
                "primary_evidence_eligible": True}
    )
    with pytest.raises(ValidationError, match="Tier 8"):
        ResearchSource.model_validate(source.model_dump())


def test_missing_bibliographic_fact_requires_explicit_explanation() -> None:
    payload = RESEARCH_SOURCES[0].model_dump()
    payload["publication"] = None
    payload["missing_fact_explanations"] = {}
    with pytest.raises(ValidationError, match="explanation"):
        ResearchSource.model_validate(payload)
    payload["missing_fact_explanations"] = {"publication": "Not stated by source."}
    from investment_tracker.quant.phase4.preregistration.canonical import source_identity
    payload["source_id"] = source_identity(ResearchSource.bibliographic_identity(payload))
    record = ResearchSource.model_validate(payload)
    assert record.publication is None


def test_unverified_or_fabricated_citation_cannot_be_admitted() -> None:
    payload = RESEARCH_SOURCES[0].model_dump()
    payload["citation_verified"] = False
    with pytest.raises(ValidationError, match="verified"):
        ResearchSource.model_validate(payload)
    payload = RESEARCH_SOURCES[0].model_dump()
    payload["source_id"] = "source-" + "0" * 64
    with pytest.raises(ValidationError, match="source identity"):
        ResearchSource.model_validate(payload)


def test_exact_cutoff_excludes_later_source_records() -> None:
    cutoff = datetime(2026, 9, 13, 8, 0, tzinfo=timezone.utc)
    before = RESEARCH_SOURCES[0].model_copy(update={"retrieved_at": cutoff})
    after = RESEARCH_SOURCES[1].model_copy(
        update={"retrieved_at": datetime(2026, 9, 13, 8, 0, 1, tzinfo=timezone.utc)}
    )
    assert enforce_research_cutoff((before,), cutoff) == (before,)
    with pytest.raises(ValueError, match="after research cutoff"):
        enforce_research_cutoff((before, after), cutoff)


def test_four_admitted_hypotheses_have_valid_support_and_one_to_one_families() -> None:
    registry = validate_hypothesis_registry(RESEARCH_SOURCES, ADMITTED_HYPOTHESES)
    assert len(registry) == 4
    assert len({row.hypothesis_id for row in registry}) == 4
    assert len({row.family_semantic_name for row in registry}) == 4
    source_by_id = {source.source_id: source for source in RESEARCH_SOURCES}
    for hypothesis in registry:
        assert hypothesis.lifecycle_state == "ADMITTED"
        assert len(hypothesis.supporting_source_ids) >= 2
        assert any(source_by_id[item].source_type.tier <= 3
                   for item in hypothesis.supporting_source_ids)
        assert hypothesis.rule_set_mode == "FIXED"
        assert hypothesis.parameter_tuple_mode == "FIXED"
        assert hypothesis.annual_reoptimization is False
        assert hypothesis.periodic_reoptimization is False
        assert hypothesis.validation_data_accessed is False
        assert hypothesis.validation_metrics_accessed is False
        assert hypothesis.campaign_results_accessed is False
        assert hypothesis.provider_calls == 0
        assert hypothesis.strategy_search_executed is False
        assert hypothesis.final_holdout_accessed is False
        assert hypothesis.protected_symbols_accessed == ()


def test_tier_eight_only_or_single_source_support_fails_closed() -> None:
    source = RESEARCH_SOURCES[0]
    weak = source.model_copy(
        update={"source_type": SourceTier.BLOG_FORUM_OR_SOCIAL_HYPOTHESIS_ONLY,
                "primary_evidence_eligible": False,
                "primary_evidence_eligibility_reason": "Hypothesis-only source."}
    )
    hypothesis = ADMITTED_HYPOTHESES[0].model_copy(
        update={"supporting_source_ids": (weak.source_id,)}
    )
    with pytest.raises(ValueError, match="at least two"):
        validate_hypothesis_registry((weak,), (hypothesis,))


def test_material_change_changes_identity_but_labels_do_not() -> None:
    original = ADMITTED_HYPOTHESES[0]
    assert original.model_copy(update={"display_name": "A label"}).hypothesis_id == original.hypothesis_id
    changed = original.model_dump(exclude={"hypothesis_id"})
    changed["cash_rule"] = "A materially different cash rule."
    changed["hypothesis_id"] = original.identity_for(changed)
    assert HypothesisRecord.model_validate(changed).hypothesis_id != original.hypothesis_id


def test_rejected_records_are_retained_and_consume_no_family_slot() -> None:
    assert REJECTED_HYPOTHESES
    for rejected in REJECTED_HYPOTHESES:
        assert rejected.lifecycle_state == "REJECTED_BEFORE_TESTING"
        assert rejected.family_semantic_name is None
        assert rejected.family_slots_consumed == 0
        assert rejected.rejection_reason


def test_models_are_frozen_and_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RESEARCH_SOURCES[0].title = "changed"  # type: ignore[misc]
    payload = ADMITTED_HYPOTHESES[0].model_dump()
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        HypothesisRecord.model_validate(payload)
