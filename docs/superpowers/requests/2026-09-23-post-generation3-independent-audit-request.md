# Independent Audit request — post-Generation-3 dividend successor

Status: **DRAFT / NOT APPROVED / NO AUTHORITY GRANTED**

Predecessor:
- formal name: `GENERATION_3`
- closure commit: `df9a0c974a392f414dc9b44551b544aa64e8e7f6`
- Phase-6 result: `PHASE6_UNKNOWN_ABSTAIN`
- terminal reason: `ValueError:SUCCESSOR_PHASE6_DIVIDEND_AMOUNT_AMBIGUOUS`
- holdout consumed: true
- retry: forbidden
- Phase 7: unauthorized
- RECON-009: OPEN

## Request

Independent Audit is requested to approve or reject the proposed successor dividend-reconciliation methodology and its exact implementation identities.

The consumed Generation-3 holdout must not be reopened, retried, substituted, or inspected.

The auditor must also decide the formal successor name. `GENERATION_4` is the natural next name, but the coordinator does not grant that name.

## Proposed methodology change

Generation-3 treated the corporate-actions endpoint `statement` free-text distribution-plan field as a numeric dividend amount source.

The proposed successor removes numeric statement parsing.

Amount authority becomes structured Rehab fields:
- ordinary cash: `per_cash_div` mapped from protocol `dividend`;
- special cash: `special_dividend` mapped from protocol `spDividend`.

The corporate-actions dividend endpoint remains mandatory for:
- event existence corroboration;
- ex-date reconciliation;
- pay-date authority;
- source-record identity;
- non-empty distribution-plan evidence.

Its `statement` text is not numeric authority.

Split normalization remains `CORPORATE-ACTION-NORMALIZATION-CONTRACT-v2` unchanged.

## Evidence boundary

No consumed Generation-3 protected-history record was inspected to design this fix.

Evidence is limited to:
- the committed terminal failure reason;
- frozen source code;
- public Moomoo/OpenD documentation;
- official open-source Python SDK mapping;
- synthetic fixtures.

## Files to audit

Methodology:
- `data/governance/successor/dividend-reconciliation-v3.json`
- `src/investment_tracker/quant/successor/dividend_reconciliation_v3.py`
- `src/investment_tracker/quant/successor/corporate_actions_v2.py`

Evaluator:
- `src/investment_tracker/independent_audit/successor/evaluate_dividend_v3.py`

Authority:
- `src/investment_tracker/independent_audit/post_generation3/authority.py`
- `data/governance/successor/post-generation3-methodology-authorization.template.json`

Tests:
- `tests/quant/test_successor_dividend_reconciliation_v3.py`
- `tests/independent_audit/test_successor_dividend_evaluator_v3.py`
- `tests/independent_audit/test_post_generation3_authority.py`
- existing split-v2 regression suite.

Root-cause report:
- `docs/superpowers/reports/2026-09-23-generation3-dividend-ambiguity-root-cause.md`

## Audit decisions required

1. Approve or reject structured Rehab fields as dividend amount authority.
2. Approve or reject endpoint `statement` as non-numeric corroboration only.
3. Verify official SDK mapping:
   - `per_cash_div = rehab.dividend`;
   - `special_dividend = rehab.spDividend`.
4. Verify split-v2 methodology is unchanged.
5. Verify the frozen survivor is unchanged:
   `G2-A|lookback=189|skip=21|top_k=1|rebalance=21`.
6. Verify the Generation-3 closure/evaluator are unchanged.
7. Verify all 28 contaminated symbols are permanently excluded.
8. Verify tests and the dedicated successor-dividend CI.
9. Decide the formal successor name.
10. If approved, issue only Stage-A methodology/blind-selection authorization.

## If approved

Create:

`data/governance/successor/post-generation3-methodology-authorization.json`

using schema:

`SUCCESSOR-PHASE6-METHODOLOGY-AUTHORIZATION-v2`

Bind exact SHA-256 identities for:
- split contract;
- dividend contract;
- split normalizer;
- dividend reconciliation module;
- successor evaluator;
- 28-symbol exclusion registry.

The authorization must keep:
- protected-history access = false;
- one-time acquisition required = true;
- retry after historical access = false;
- symbol substitution after access = false;
- result-dependent methodology change = false;
- Phase 7 = false;
- production readiness = false;
- RECON-009 = OPEN;
- paper-only = true.

It may authorize only methodology + future blind selection of a new virgin holdout.

Do not issue any acquisition authorization at this stage.

## Explicit non-requests

This request does not authorize:
- Generation-3 rerun;
- Generation-3 performance inspection;
- new holdout history access;
- Phase 7;
- production readiness;
- RECON-009 closure;
- live trading/order routing.
