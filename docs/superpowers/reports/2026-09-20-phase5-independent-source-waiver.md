# Phase 5 Independent-Source Verification Waiver

Date: 2026-09-20  
Branch: `codex/phase5-decision-grade-reconstruction`  
Recorded from repository HEAD before this note: `e8d80184635409a888e6a0e82e8645ceeef82984`

## Decision

The project owner elects not to purchase or upgrade Massive historical-stock
data access solely to perform the Phase 5 independent-provider comparison.

This is an explicit cost/operational waiver only. It does **not** redefine the
frozen Phase 5 methodology, convert missing independent evidence into a PASS,
or claim that OpenD has been independently verified.

## Evidence state at waiver

The completed OpenD evaluation reached the independent-source gate with:

- formal status: `PHASE5_UNKNOWN_ABSTAIN`;
- sole reported reason: `INDEPENDENT_SOURCE_SNAPSHOT_MISSING`;
- signal-equivalence status: `MATCH`;
- signal-equivalence comparisons: 48 / 48;
- safety flags clean, including:
  - `final_holdout_accessed=false`;
  - `protected_symbols_accessed=[]`;
  - `candidate_search_executed=false`;
  - `candidate_parameters_changed=false`;
  - `phase4_feedback_written=false`;
  - `live_trading_capability=false`;
  - `phase6_started=false`.
- mechanically derived decision-grade accounting start: `2019-12-24`;
- latest unsupported dividend ex-date: `2019-12-23`;
- primary 3-bps durability reconstruction remained positive;
- 50-bps friction reconstruction also remained positive.

The project attempted a Massive historical daily-bar check after reaching this
gate. The connected Massive account returned `NOT_ENTITLED`. No alternate
independent provider was substituted after performance was observed.

## Allowed interpretation

For project-owner research continuation, the OpenD reconstruction may be
treated as **OpenD-validated, independently unverified research evidence**.

The following statement is permitted:

> The project owner accepts the OpenD-only Phase 5 evidence as sufficient to
> continue non-live research and engineering work without paying for an
> independent-data subscription.

The following statements are **not** permitted:

- `PHASE5_DURABILITY_SUPPORTED`;
- independent-provider reconciliation passed;
- decision-grade Phase 5 completed under the frozen contract;
- production readiness approved;
- real-money readiness established;
- Independent Audit approved.

The formal frozen-contract conclusion therefore remains:

`PHASE5_UNKNOWN_ABSTAIN`

Reason:

`INDEPENDENT_SOURCE_SNAPSHOT_MISSING`

## Governance

This waiver does not:

- alter the frozen Phase 4 survivor or parameters;
- access FINAL_HOLDOUT;
- access HACK, SOXX, NLR, URNM, or GEV;
- authorize brokerage/order-routing capability;
- authorize Phase 6 or Phase 7;
- permit historical evidence to be rewritten as if the independent gate passed;
- permit a later provider substitution to be represented as preregistered.

If independent verification is performed later, it must be recorded as a
subsequent evidence event and the formal Phase 5 conclusion may only change
through the existing frozen classifier and required review gates.
