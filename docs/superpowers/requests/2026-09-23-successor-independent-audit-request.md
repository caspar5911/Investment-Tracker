# Independent Audit request — governed Phase-6 successor

Status: **DRAFT / NOT APPROVED / NO AUTHORITY GRANTED**

Requested by: coordinator  
Predecessor closure: `f875167f3e758ab3391ff2f961aa740f231568e5`  
Predecessor result: `PHASE6_UNKNOWN_ABSTAIN`  
Predecessor holdout: consumed; retry forbidden  
Phase 7: **NOT AUTHORIZED**  
RECON-009: **OPEN**

## Purpose

Independent Audit is requested to review the complete proposed successor path for the failed Gen2 Phase-6 evaluation. The consumed Gen2 holdout is not reopened, inspected, retried, or used for tuning.

The proposal preserves the exact frozen survivor while replacing only the defective corporate-action normalization boundary with the versioned `CORPORATE-ACTION-NORMALIZATION-v2` methodology.

## Methodology review

Please approve or reject:

- Unicode `→` and ASCII `->` normalization;
- endpoint split direction as old units → new units, with ledger multiplier `new/old`;
- OpenD rehab `split_ratio` as adjustment direction `old/new`, converted to ledger units by reciprocal;
- rehab `ex_div_date` as the effective-date authority;
- filtering known-dated out-of-window records before decision-critical rate reconciliation;
- undated US split-endpoint rows as corroboration only, never date authority;
- unique one-to-one source reconciliation;
- fail-closed behavior for decision-relevant missing, duplicate, conflicting, or ambiguous events;
- accounting version `UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v2`;
- preservation of the frozen survivor and existing 0/3/10/25/50 bps friction cases;
- preservation of Gen2 metric definitions including the prospective DQ030 convention.

The audit must also decide whether the successor is formally **Generation 3** or another explicitly named successor. The coordinator does not make that decision.

## Two-stage authority model

### Stage A — methodology + blind-selection authorization

If the methodology is accepted, Independent Audit must create and commit a real artifact using:

`data/governance/successor/successor-methodology-authorization.template.json`

The real artifact must use schema:

`SUCCESSOR-PHASE6-METHODOLOGY-AUTHORIZATION-v1`

It must bind:

- the predecessor closure;
- the exact survivor candidate/binding/implementation;
- the exact corporate-action contract;
- the exact successor normalizer and evaluator source hashes;
- the formal successor name;
- evaluation window, warmup, listing cutoff, selection count, and deterministic seed;
- the updated permanent exclusion registry.

Stage A may authorize **blind static selection only**. It must keep:

- `protected_history_access_authorized = false`;
- `phase7_authorized = false`;
- production readiness false;
- RECON-009 open.

After Stage A, the code may:

1. seal the successor holdout-selection contract;
2. query only permitted static ETF metadata plus provider quota history;
3. apply all permanent exclusions, including the consumed Gen2 identities;
4. deterministically select a new virgin holdout;
5. capture composite virginity evidence without requesting bars;
6. seal the successor Phase-6 evaluation contract.

### Stage B — one-time acquisition + evaluation authorization

Only after Stage-A selection, virginity, and the Phase-6 contract are frozen may Independent Audit create and commit a real artifact using:

`data/governance/successor/successor-acquisition-authorization.template.json`

The real artifact must use schema:

`SUCCESSOR-PHASE6-ACQUISITION-AUTHORIZATION-v1`

It must bind:

- exact selected identities;
- exact Phase-6 contract;
- exact selection and virginity hashes;
- exact survivor, normalizer, and evaluator identities;
- exact acquisition and release implementation hashes;
- one-time acquisition semantics;
- one-time evaluation after a verified release;
- no retry or symbol substitution after historical access.

Stage B still must keep Phase 7 and production readiness unauthorized.

## Irreversible boundary

After a valid Stage-B authorization:

1. run the non-consuming acquisition preflight;
2. create and durably read back the exclusive acquisition-start marker;
3. only then request protected historical data;
4. any protected historical access consumes the selected holdout;
5. no retry after access;
6. seal QFQ signal bars, unadjusted execution/mark bars, rehab data, dividends, and stock-split endpoint evidence;
7. verify artifact readback without computing or inspecting performance;
8. issue the deterministic verified release;
9. create the one-time evaluation-consumption marker;
10. evaluate exactly once;
11. terminate as either:
   - `PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE`, or
   - `PHASE6_UNKNOWN_ABSTAIN`;
12. seal the terminal Phase-6 closure.

No holdout outcome may change parameters, methodology, selection, or strategy.

## Explicit non-requests

This request does **not** request or grant:

- reopening or rerunning the consumed Gen2 holdout;
- inspecting the consumed Gen2 holdout performance;
- changing the Gen2 closure or status;
- using protected observations for methodology development;
- Phase-7 entry;
- production readiness;
- closure of RECON-009;
- live trading or order-routing capability.

## Review package

Methodology and root cause:

- `data/governance/successor/corporate-action-normalization-v2.json`
- `src/investment_tracker/quant/successor/corporate_actions_v2.py`
- `docs/superpowers/reports/2026-09-23-gen2-phase6-split-root-cause.md`
- `docs/superpowers/reviews/2026-09-23-successor-corporate-actions-v2-review.md`
- `tests/quant/test_successor_corporate_actions_v2.py`

Authority and selection:

- `src/investment_tracker/independent_audit/successor/authority.py`
- `src/investment_tracker/independent_audit/successor/selection_contract.py`
- `src/investment_tracker/independent_audit/successor/holdout_selection.py`
- `src/investment_tracker/independent_audit/successor/virginity.py`
- `tests/independent_audit/test_successor_authority.py`
- `tests/independent_audit/test_successor_holdout_selection.py`

Phase-6 execution:

- `src/investment_tracker/independent_audit/successor/phase6_contract.py`
- `src/investment_tracker/independent_audit/successor/acquisition_authority.py`
- `src/investment_tracker/independent_audit/successor/acquisition.py`
- `src/investment_tracker/independent_audit/successor/release.py`
- `src/investment_tracker/independent_audit/successor/evaluate.py`
- `src/investment_tracker/independent_audit/successor/closure.py`
- `src/investment_tracker/independent_audit/successor/cli.py`
- `tests/independent_audit/test_successor_phase6_boundary.py`

Independent Audit must create the real authorization artifacts. The templates themselves grant **no authority**. Until the appropriate authorization exists, the required state is **STOP / NO PROTECTED-HISTORY ACCESS**.
