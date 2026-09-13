# Phase 4 Gate 1 Preregistration Report

Status: `PHASE4_PREREGISTRATION_SEALED` once the linked manifest is committed.

- Sources: 9 verified records, including 2 explicit counterevidence records.
- Hypotheses/families: 4 admitted fixed-strategy families; 1 rejected pre-test idea retained.
- Candidate population: 180 (`volatility_managed_relative_momentum=54, trend_filtered_equal_risk_allocation=36, diversified_time_series_momentum=36, cross_sectional_absolute_momentum_rotation=54`).
- Baselines: {'EXECUTED_PHASE2_BASELINE': 2, 'SOURCE_DEFINED_PHASE2_GRID_BASELINE': 2}; all comparison-only and selection-ineligible.
- Budget: Phase 4 starts at 0/3000; positions begin at 1. The 136 historical Phase 2 trials remain separate lineage.
- Deployment objective: one fixed long-only rule set and parameter tuple, with no annual or periodic retuning.
- Survivor priority: durability and robustness precede fitted CAGR; 20% CAGR is not a gate.
- QFQ: `QFQ_NORMALIZED`, `decision_grade=false`.
- Unavailable statistics: max drawdown and Calmar remain `UNKNOWN`; DSR and PBO remain `UNKNOWN / NOT_IMPLEMENTED`.
- Safety: no provider call, strategy execution/search, Phase 4 validation access, holdout access, protected-symbol access, or live-trading capability.

Gate 1 authorizes neither Gate 2 nor Gate 3. The fixed strategy proof remains: preregister, freeze, execute the same tuple through later unseen periods, and measure durability.
