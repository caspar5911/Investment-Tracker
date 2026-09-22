# Independent Audit request — successor corporate-action methodology

Status: **DRAFT / NOT APPROVED / NO AUTHORITY GRANTED**

Requested by: coordinator  
Predecessor closure: `f875167f3e758ab3391ff2f961aa740f231568e5`  
Predecessor result: `PHASE6_UNKNOWN_ABSTAIN`  
Phase 7: **NOT AUTHORIZED**  
RECON-009: **OPEN**

## Request

Independent Audit is requested to review the proposed `CORPORATE-ACTION-NORMALIZATION-v2` contract and associated synthetic regression evidence.

The coordinator specifically requests an external decision on all of the following:

1. Whether the successor split-normalization methodology is acceptable, including:
   - Unicode `→` to ASCII `->` normalization;
   - endpoint old-to-new share direction;
   - reciprocal conversion of OpenD rehab `split_ratio` into ledger unit multiplier;
   - rehab ex-date as the effective-date authority;
   - exclusion of known-dated out-of-window records before decision-critical parsing;
   - use of undated US stock-split endpoint records solely as unique corroboration;
   - fail-closed rules for unresolved, duplicate, or conflicting decision-relevant events.

2. Whether the next governed evaluation must be formally designated **Generation 3** or another explicitly named successor generation/protocol. The coordinator makes no naming or authority decision in this draft.

3. Whether a **new virgin holdout** may be selected only after the successor methodology, implementation identity, data sources, evaluation window, metrics, accounting rules, and all development evidence are frozen without use of the consumed Gen2 holdout.

4. If a new holdout is approved, the exact one-time acquisition semantics:
   - pre-access virginity/provenance proof required;
   - explicit signed/committed Independent Audit acquisition authorization required;
   - acquisition-start marker created before first protected historical read;
   - any protected historical access consumes that holdout;
   - no retry or symbol substitution after protected access unless separately and prospectively authorized before access;
   - failure after access results in UNKNOWN/ABSTAIN unless the governing authority already defined another outcome.

5. The exact one-time evaluation/release semantics:
   - sealed acquisition bundle and readback verification required;
   - independent release required before evaluation;
   - one-time consumption marker required before unsealing/evaluation;
   - no methodology/parameter changes using holdout observations;
   - missing or unresolved corporate-action evidence fails closed.

## Explicit non-requests

This document does **not** request or grant:

- permission to reopen or rerun the consumed Gen2 holdout;
- permission to inspect Gen2 holdout performance;
- permission to alter the Gen2 closure;
- Phase-7 entry;
- production readiness;
- closure of RECON-009;
- live trading or order-routing capability.

## Evidence package for review

- `data/governance/successor/corporate-action-normalization-v2.json`
- `src/investment_tracker/quant/successor/corporate_actions_v2.py`
- `tests/quant/test_successor_corporate_actions_v2.py`
- `docs/superpowers/reports/2026-09-23-gen2-phase6-split-root-cause.md`

Independent Audit must issue a separate signed/committed authorization artifact before any protected-history acquisition. Absence of that artifact means **STOP / NO ACCESS**.
