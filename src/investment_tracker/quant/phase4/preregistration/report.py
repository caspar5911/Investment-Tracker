from __future__ import annotations

from .campaign_definition import RESEARCH_SOURCES
from .grids import PreregisteredGrids
from .baselines import BaselineDefinitionSet


def build_research_notes() -> bytes:
    lines = [
        "# Phase 4 Gate 1 Research Notes",
        "",
        "This preregistration uses literature for mechanism and falsifiable rule design only. "
        "No reported performance number selected a parameter, and no Phase 4 validation information was used.",
        "",
        "## Evidence synthesis",
        "",
    ]
    for source in sorted(RESEARCH_SOURCES, key=lambda item: item.source_id):
        lines.extend((
            f"### {source.title}", "",
            f"- Citation: {', '.join(source.authors or ())} ({source.year}), "
            f"{source.publication}. {source.canonical_url}",
            f"- Role: {source.evidence_role}; tier: {source.source_type.value}.",
            f"- Mechanism: {source.mechanism}",
            f"- Transfer limits: {source.limitations}",
            f"- Frozen-universe relevance: {source.frozen_universe_relevance}", "",
        ))
    lines.extend((
        "## Campaign constraints", "",
        "The four admitted families are fixed, long-only, unlevered rule sets with complete "
        "predeclared grids. The intended survivor is one fixed parameter tuple usable without "
        "annual or periodic retuning. Durability, neighboring-parameter stability, calendar and "
        "rolling-period consistency, friction robustness, and economic explainability precede "
        "fitted CAGR. A sustainable 15–20% or higher CAGR is aspirational, never a threshold.",
        "",
        "The two counterevidence records prevent treating time-series momentum or volatility "
        "management as universal. Futures, long-short, leverage, reconstructed histories, factor "
        "portfolios, same-close fills, and total-return indices do not establish executable fills "
        "for this QFQ-normalized ETF simulation.", "",
        "Rejected alternative: short-horizon reversal was not admitted because the bounded "
        "campaign lacks directly transferable support and the idea is expected to be materially "
        "friction-sensitive.", "",
    ))
    return ("\n".join(lines)).encode("utf-8")


def build_gate1_report(
    baselines: BaselineDefinitionSet, grids: PreregisteredGrids
) -> bytes:
    counts = ", ".join(
        f"{family.family_semantic_name}={len(family.candidates)}"
        for family in grids.families
    )
    text = f"""# Phase 4 Gate 1 Preregistration Report

Status: `PHASE4_PREREGISTRATION_SEALED` once the linked manifest is committed.

- Sources: 9 verified records, including 2 explicit counterevidence records.
- Hypotheses/families: 4 admitted fixed-strategy families; 1 rejected pre-test idea retained.
- Candidate population: 180 (`{counts}`).
- Baselines: {baselines.provenance_class_counts}; all comparison-only and selection-ineligible.
- Budget: Phase 4 starts at 0/3000; positions begin at 1. The 136 historical Phase 2 trials remain separate lineage.
- Deployment objective: one fixed long-only rule set and parameter tuple, with no annual or periodic retuning.
- Survivor priority: durability and robustness precede fitted CAGR; 20% CAGR is not a gate.
- QFQ: `QFQ_NORMALIZED`, `decision_grade=false`.
- Unavailable statistics: max drawdown and Calmar remain `UNKNOWN`; DSR and PBO remain `UNKNOWN / NOT_IMPLEMENTED`.
- Safety: no provider call, strategy execution/search, Phase 4 validation access, holdout access, protected-symbol access, or live-trading capability.

Gate 1 authorizes neither Gate 2 nor Gate 3. The fixed strategy proof remains: preregister, freeze, execute the same tuple through later unseen periods, and measure durability.
"""
    return text.encode("utf-8")
