# Generation 4 Stage-B Independent Audit request

Status: **DRAFT / NO ACQUISITION AUTHORITY GRANTED**

Generation 4 Stage A is complete and frozen.

Frozen evidence:
- Stage-A commit: `4883a026ad68afaaaa1b13aecc742c0bf5108b05`
- methodology authorization: `INDEP-AUDIT-GEN4-METHODOLOGY-0001`
- Phase-6 contract status: `FROZEN_PRE_ACCESS`
- historical market-data API called: false
- protected-history access authorized: false
- Phase 7: unauthorized
- RECON-009: OPEN

## Protected identity handling

The five selected identities are now protected.

The auditor may inspect only the already-frozen selection/virginity/contract artifacts and code identities. Do not request or inspect historical prices, returns, corporate-action history, performance, or outside classifications for the selected identities.

The selection was produced by the frozen provider-only static process. No manual substitution is permitted.

## Frozen Stage-A artifacts

- `data/generation4/preaccess/holdout-selection-contract.json`
- `data/generation4/preaccess/holdout-selection.json`
- `data/generation4/preaccess/static-snapshot.json`
- `data/generation4/preaccess/provider-history-ledger.json`
- `data/generation4/preaccess/virginity-evidence.json`
- `data/generation4/preaccess/virginity-attestation.json`
- `data/generation4/phase6/evaluation-contract.json`

## Stage-B runtime chain to audit

Methodology identities already authorized at Stage A:
- split normalizer:
  `src/investment_tracker/quant/successor/corporate_actions_v2.py`
- dividend reconciliation:
  `src/investment_tracker/quant/successor/dividend_reconciliation_v3.py`
- exact audited evaluator:
  `src/investment_tracker/independent_audit/successor/evaluate_dividend_v3.py`

Stage-B infrastructure:
- v2/v1 contract verifier compatibility:
  `src/investment_tracker/independent_audit/successor/phase6_contract.py`
- v2/v1 acquisition authority:
  `src/investment_tracker/independent_audit/successor/acquisition_authority.py`
- one-time acquisition:
  `src/investment_tracker/independent_audit/successor/acquisition.py`
- verified release:
  `src/investment_tracker/independent_audit/successor/release.py`
- terminal closure:
  `src/investment_tracker/independent_audit/successor/closure.py`
- Generation-4 Stage-B CLI:
  `src/investment_tracker/independent_audit/post_generation3/stage_b_cli.py`

Non-authorizing template:
- `data/governance/successor/generation4-acquisition-authorization.template.json`

Tests:
- `tests/independent_audit/test_generation4_stage_b_boundary.py`
- all prior Generation-4 and successor focused tests.

## Required audit checks

1. Verify Stage-A frozen artifacts are unchanged since `4883a026...`.
2. Verify selection status is frozen and virginity status is clean.
3. Verify no historical market-data API was called before Stage B.
4. Verify the Phase-6 contract is exactly `SUCCESSOR-PHASE6-EVALUATION-CONTRACT-v2` / `FROZEN_PRE_ACCESS`.
5. Verify the contract binds the same Stage-A authorized strategy and methodology identities.
6. Verify the on-disk v2 contract is never rewritten by compatibility handling.
7. Verify the compatibility verifier only adds an in-memory alias from `split_normalizer_sha256` to the legacy key expected by the already-audited evaluator/acquisition stack.
8. Verify `evaluate_dividend_v3.py` remains byte-identical to its Stage-A audited SHA-256.
9. Verify the Stage-B v2 authorization schema binds:
   - split normalizer;
   - dividend reconciliation;
   - corrected evaluator;
   - Phase-6 verifier implementation;
   - acquisition-authority implementation;
   - acquisition implementation;
   - release implementation;
   - closure implementation;
   - virginity verifier implementation;
   - Generation-4 Stage-B CLI implementation;
   - frozen Phase-6 contract;
   - frozen selection;
   - virginity attestation;
   - virginity evidence;
   - exact locked symbols.
10. Verify preflight calls only non-consuming SDK capability/quota checks and selected-symbol virginity recheck.
11. Verify the durable acquisition-start marker is created before first historical provider read and read back successfully.
12. Verify historical access is marked true before the first history/corporate-action read.
13. Verify private output must be outside the repository.
14. Verify acquisition obtains QFQ signal bars, unadjusted execution/mark bars, Rehab, dividends, and splits.
15. Verify acquisition does not compute or inspect performance.
16. Verify release validates receipt/bundle/key/hash chain before evaluation.
17. Verify the Generation-4 Stage-B CLI explicitly invokes `evaluate_dividend_v3`, not the obsolete evaluator.
18. Verify one-time evaluation consumption marker/no-retry semantics.
19. Verify any post-access exception ends as `PHASE6_UNKNOWN_ABSTAIN`; no rerun or substitution.
20. Verify closure leaves Phase 7 unauthorized and RECON-009 OPEN.

## If rejected

Do not create authorization and do not access protected history. Report the exact blocker.

## If approved

Create:

`data/governance/successor/generation4-acquisition-authorization.json`

Schema:

`SUCCESSOR-PHASE6-ACQUISITION-AUTHORIZATION-v2`

Use exact audited SHA-256 values for every bound file/artifact.

Required governance:
- authority = `INDEPENDENT_AUDIT`
- status = `SUCCESSOR_FINAL_HOLDOUT_ACQUISITION_AUTHORIZED`
- successor = `GENERATION_4`
- one_time = true
- acquisition-start marker required before provider read = true
- retry after historical access = false
- symbol substitution after access = false
- historical data included in authorization artifact = false
- holdout performance inspected = false
- one-time evaluation after verified release authorized = true
- Phase 7 = false
- production readiness = false
- RECON-009 = OPEN
- paper-only = true

This Stage-B authorization may authorize only the one-time governed Phase-6 acquisition/release/evaluation chain. It does not authorize Phase 7 or production/live trading.
