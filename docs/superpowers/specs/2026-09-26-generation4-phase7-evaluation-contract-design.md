# Generation-4 Phase-7 Evaluation Contract Design

Date: 2026-09-26

Status: APPROVED DESIGN TARGET; NO PHASE-7 PERFORMANCE EVALUATION AUTHORIZED BY THIS DOCUMENT

## 1. Purpose

Define the separately governed Generation-4 Phase-7 durability/evaluation boundary after the successful Phase-7 start transition.

Phase 7 evaluates the exact frozen candidate without parameter fitting, family search, symbol substitution, annual reoptimization, adaptive walk-forward selection, or result-dependent methodology changes.

The design deliberately separates:

1. **historical durability diagnostics** over already-used research history; and
2. **prospective primary evidence** beginning only after the Phase-7 start timestamp.

Historical diagnostics may be produced for context but can never be relabelled as new out-of-sample evidence or used alone to authorize production.

## 2. Starting state

Required branch state:

`governance/phase6-successor-dividend-normalization-v3`

Required Phase-7 start artifact commit:

`6a8df5367ac6bb1e4cfe02c625ee53963443f996`

Required start state:

- schema `GENERATION4-PHASE7-START-v1`;
- status `GENERATION4_PHASE7_STARTED`;
- candidate `G2-A|lookback=189|skip=21|top_k=1|rebalance=21`;
- `phase7_entry_authorized=true`;
- `phase7_started=true`;
- `phase7_performance_evaluation_authorized=false`;
- `production_readiness_approved=false`;
- `live_trading_authorized=false`;
- `holdout_reuse_authorized=false`;
- `candidate_search_authorized=false`;
- `parameter_mutation_authorized=false`;
- `symbol_substitution_authorized=false`;
- both result-dependent-change flags false;
- `RECON-009=OPEN`;
- paper-only true.

The start artifact self-hash is:

`d1257bd7a683b8e372c71d0f1da90b7366be17ba3c1e2587205601dfeaf65599`

The start-contract SHA-256 is:

`beef9982ac1d1cf33a451fab984bb09f8b60605a18297e5823079d7b980878e0`

## 3. Fixed strategy and methodology

The strategy is immutable:

- family: `G2-A`;
- lookback: 189 sessions;
- skip: 21 sessions;
- top_k: 1;
- rebalance: 21 sessions;
- long only;
- no leverage;
- no short selling;
- signal from completed session;
- earliest fill next eligible session open;
- if no eligible asset exists, remain in cash.

Frozen identities:

- binding SHA-256:
  `fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b`;
- strategy implementation SHA-256:
  `35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b`;
- split normalizer SHA-256:
  `bfbf0de5bdeb39af3535641570f3f9224f5301abb7db9fffc34c580481cace04`;
- dividend reconciliation SHA-256:
  `6baa251d51f6f16be602aa82b08fc46665a4ccdd62f68705821c48c8a28ac9bc`;
- corrected evaluator SHA-256:
  `fb20b368d6d7ac0f698c5ab45e5824aaad73341cccfacc25bc6903b98c9a2b21`.

Accounting remains:

`UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v3`

No Phase-7 result may change any of these identities.

## 4. Exact Phase-7 universe

The Phase-7 evaluation universe is exactly, in this order:

- GLD
- IEF
- IWM
- QQQ
- SPY
- TLT
- VNQ
- XLP

No additional symbol may be requested, substituted, or used as an optimization candidate.

The Generation-4 final-holdout symbols:

- QQQM
- FALN
- IIPR
- PSTL
- EFAS

must never be used by Phase-7 durability evaluation.

Earlier locked/retired holdouts also remain outside the exact allowed universe.

SPY is both an eligible strategy-universe member and the fixed benchmark reference. Benchmark accounting must be computed independently from strategy holdings; benchmark inclusion in the candidate universe does not permit benchmark substitution.

## 5. Frozen friction and execution assumptions

Reuse the already-frozen Generation-2 / Phase-6 assumptions:

- initial cash: 100000;
- friction basis: absolute traded notional on buys and sells;
- fixed friction cases: 0, 3, 10, 25, 50 bps;
- primary friction: 3 bps;
- signal on completed session;
- next eligible session open execution;
- no same-bar execution;
- fractional shares retained in research ledger;
- no leverage;
- no short selling.

No new friction case may be added after the evaluation contract is frozen.

## 6. Two evidence lanes

### 6.1 Historical durability diagnostics

Purpose: describe how the exact frozen candidate behaves over previously used research history.

Permitted history:

- research universe only;
- no final-holdout symbols;
- no data beyond the already-established research/validation boundary when using legacy research snapshots;
- any longer-history source must already have been acquired under prior governance and must pass its existing manifest/integrity checks.

Historical diagnostics are explicitly:

`REUSED_HISTORY_DIAGNOSTIC_ONLY`

They are never:

- new OOS evidence;
- virgin holdout evidence;
- a basis for parameter changes;
- sufficient for production readiness;
- allowed to override adverse prospective evidence.

The historical lane uses fixed-strategy continuous chronological subperiod analysis. It does not retrain inside folds.

Required diagnostics when supported by evidence:

- total return;
- CAGR;
- Sharpe;
- Sortino;
- annualized one-way turnover;
- benchmark total return;
- benchmark excess return;
- calendar month returns;
- calendar year returns;
- positive month/year fractions;
- average winning/losing month;
- worst month/year;
- longest losing-month sequence;
- rolling 12-, 36-, and 60-month returns where complete;
- return concentration;
- regime consistency;
- exposure invariants;
- friction sensitivity at 0/3/10/25/50 bps.

Any metric unsupported by authoritative evidence is `UNKNOWN`.

DQ-030-dependent drawdown/recovery/Calmar fields remain `UNKNOWN` unless a separately authoritative resolution is explicitly bound. The evaluator may not silently choose a drawdown convention.

### 6.2 Prospective primary evidence

This is the only Phase-7 lane that can become new post-start evidence.

The prospective scored boundary begins at the first eligible XNYS session strictly after the Phase-7 start artifact's `started_at_utc`.

The exact first scored session must be resolved and frozen in the machine-readable contract **before any prospective provider request or performance calculation**.

Warmup:

- up to 210 earlier eligible sessions may be loaded solely for causal initialization of the 189-session lookback plus 21-session skip;
- warmup P&L is excluded;
- warmup observations cannot become scored Phase-7 evidence.

The prospective lane is continuous. Portfolio state is not reset at arbitrary subperiod boundaries.

No data preceding the frozen prospective scored start may be backfilled into prospective P&L.

## 7. Prospective checkpoints

Freeze three observation checkpoints:

- 63 scored sessions: `EARLY_DIAGNOSTIC`;
- 126 scored sessions: `INTERIM_DIAGNOSTIC`;
- 252 scored sessions: `PRIMARY_PHASE7_ASSESSMENT`.

The 63- and 126-session checkpoints are descriptive only and cannot authorize production.

The 252-session checkpoint is the first point at which a terminal Phase-7 assessment may be produced.

If fewer than 252 scored sessions exist, the primary status is:

`PHASE7_PROSPECTIVE_EVIDENCE_PENDING`

No missing future sessions may be synthesized or estimated.

## 8. Prospective primary metrics

At every available checkpoint, report:

- scored-session count;
- total return at all five friction cases;
- primary 3-bps CAGR where mathematically meaningful;
- primary 3-bps Sharpe;
- primary 3-bps Sortino;
- annualized one-way turnover;
- SPY benchmark total return using aligned scored sessions;
- excess return versus SPY;
- excess return versus cash;
- all-session gross-exposure invariant;
- calendar month returns for complete scored months;
- positive-month fraction;
- worst complete month;
- rolling 12-month return only when a complete 12-month scored window exists.

Max drawdown, Calmar, and recovery metrics remain `UNKNOWN` under unresolved DQ-030 unless separately resolved before the contract is frozen.

No metric is permitted to trigger parameter changes.

## 9. Phase-7 assessment semantics

The contract must not invent thresholds from Phase-6 or Phase-7 observed performance.

For the first version, Phase-7 result status is evidence-oriented rather than a production verdict:

- `PHASE7_PROSPECTIVE_EVIDENCE_PENDING`: fewer than 252 scored sessions and no integrity failure;
- `PHASE7_PROSPECTIVE_EVIDENCE_COMPLETE`: at least 252 scored sessions and all required non-DQ metrics/invariants are available;
- `PHASE7_UNKNOWN_ABSTAIN`: required evidence is missing, inconsistent, contaminated, or cannot be reconciled;
- `PHASE7_GOVERNANCE_FAILURE`: a frozen identity, boundary, or prohibition is violated.

A complete Phase-7 result does not mean profitable, production-ready, or live-trading approved.

The report must expose the actual performance values without converting them into a post-hoc pass/fail threshold.

Any later production-readiness gate must be separately preregistered and independently audited before using these results for a production decision.

## 10. Machine-readable evaluation contract

Create:

`data/governance/successor/generation4-phase7-evaluation-contract.json`

Schema:

`GENERATION4-PHASE7-EVALUATION-CONTRACT-v1`

Status:

`FROZEN_PRE_EVALUATION`

Authority:

`COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION`

It must bind:

- exact start artifact file SHA-256 and embedded self-hash;
- exact start-contract SHA-256;
- exact entry authorization ID and file SHA-256;
- frozen entry implementation commit/source hashes;
- frozen start implementation commit/source hashes;
- frozen Phase-7 evaluation implementation commit/source hashes;
- candidate/binding/strategy implementation;
- all three methodology hashes;
- exact ordered research universe;
- exact forbidden Generation-4 holdout symbols;
- SPY benchmark;
- friction model and cases;
- initial cash;
- prospective first scored XNYS session;
- warmup session limit 210;
- checkpoint session counts 63/126/252;
- fixed metric set;
- historical-lane classification;
- prospective-lane status semantics;
- DQ-030 handling;
- no-retuning rules.

Required governance fields:

- `phase7_started=true`;
- `phase7_performance_evaluation_authorized=false`;
- `production_readiness_approved=false`;
- `live_trading_authorized=false`;
- `holdout_reuse_authorized=false`;
- `candidate_search_authorized=false`;
- `parameter_mutation_authorized=false`;
- `symbol_substitution_authorized=false`;
- `adaptive_walk_forward_authorized=false`;
- `annual_reoptimization_authorized=false`;
- `result_dependent_methodology_change_allowed=false`;
- `result_dependent_parameter_change_allowed=false`;
- `recon009_status=OPEN`;
- `paper_only=true`.

Use strict `extra="forbid"`.

## 11. Separate Independent Audit authorization

Freezing the contract does not itself permit provider access or performance evaluation.

Create an Independent Audit handoff after the evaluation implementation and contract are frozen.

Authorization schema:

`GENERATION4-PHASE7-EVALUATION-AUTHORIZATION-v1`

Authority:

`INDEPENDENT_AUDIT`

Status:

`GENERATION4_PHASE7_EVALUATION_AUTHORIZED`

The authorization must bind:

- evaluation contract SHA-256;
- start artifact SHA-256;
- entry authorization SHA-256;
- evaluation implementation commit and source hashes;
- exact universe and prospective boundary;
- methodology/friction/checkpoint identities;
- all governance prohibitions.

Only this authorization may set:

`phase7_performance_evaluation_authorized=true`

It must keep:

- production readiness false;
- live trading false;
- holdout reuse false;
- search/mutation/substitution false;
- adaptive walk-forward/reoptimization false;
- result-dependent changes false;
- `RECON-009=OPEN`;
- paper-only true.

## 12. Provider/data-access boundary

No provider access is allowed before the Independent Audit evaluation authorization exists.

After authorization, provider access is limited to the exact research universe and the exact date range required for:

- <=210 warmup sessions before prospective scored start; and
- scored sessions from the frozen prospective start through the requested checkpoint cutoff.

Requests containing any other symbol fail before provider creation.

The provider layer must never create a trade context or use order APIs.

Every acquired prospective snapshot must have:

- provider identity;
- requested symbols in exact frozen order;
- requested date range;
- retrieved-at timestamp;
- file hashes;
- manifest hash;
- `trading_context_created=false`;
- `protected_holdout_symbols_accessed=[]`.

Snapshots are append-only/content-addressed. Existing snapshots may not be overwritten.

## 13. Evaluation outputs

Historical diagnostic report:

`GENERATION4-PHASE7-HISTORICAL-DURABILITY-v1`

Prospective checkpoint report:

`GENERATION4-PHASE7-PROSPECTIVE-CHECKPOINT-v1`

Every report binds:

- evaluation contract;
- evaluation authorization;
- start artifact;
- dataset/snapshot manifest;
- candidate and methodology identities;
- checkpoint/session boundaries;
- exact friction case;
- benchmark alignment;
- governance flags.

Reports must state:

- paper-only;
- production false;
- live trading false;
- no tuning performed;
- no final-holdout reuse.

## 14. One-way information rule

After the first prospective performance value is inspected:

- the contract cannot change;
- the universe cannot change;
- the candidate cannot change;
- thresholds/status semantics cannot change;
- checkpoint boundaries cannot change;
- friction assumptions cannot change;
- methodology cannot change.

A defect may cause `UNKNOWN/ABSTAIN` and a separately governed successor generation, but may not be patched to improve the same Phase-7 result.

## 15. TDD requirements

Tests must prove at least:

1. exact start artifact and contract bindings;
2. exact candidate/methodology identities;
3. exact ordered research universe;
4. any Generation-4 holdout symbol rejected before provider creation;
5. any extra/substituted symbol rejected;
6. prospective start is strictly after start timestamp;
7. warmup capped at 210 and excluded from scored P&L;
8. fixed checkpoints 63/126/252;
9. fewer than 252 sessions returns pending, not pass/fail;
10. missing evidence returns unknown/abstain;
11. no adaptive/reoptimized folds;
12. portfolio state remains continuous across diagnostic subperiods;
13. all five friction cases fixed;
14. SPY benchmark alignment exact;
15. DQ-030 metrics remain unknown without authoritative resolution;
16. historical lane labelled reused-history diagnostic only;
17. historical results cannot authorize production;
18. no result-dependent parameter/methodology path exists;
19. strict evaluation authorization required before provider/evaluator access;
20. no broker/trade/order APIs;
21. provider snapshots append-only/content-addressed;
22. production/live-trading remain false in every output.

## 16. Freeze and execution sequence

1. implement contract verifier, fixed-protocol evaluator, and synthetic tests;
2. freeze evaluation implementation commit;
3. resolve prospective first scored XNYS session from the already-committed start timestamp;
4. create and commit the machine-readable evaluation contract;
5. run non-performance preflight only;
6. create Independent Audit request/template;
7. Independent Audit either rejects or creates evaluation authorization;
8. only after authorization, acquire permitted research-universe data;
9. historical diagnostic may run;
10. prospective checkpoints may run only as sessions become available;
11. never modify frozen protocol in response to results.

## 17. Explicit non-goals

This phase does not:

- reuse Generation-4 final-holdout symbols;
- rerun Phase 6;
- search candidates;
- tune parameters;
- perform adaptive walk-forward fitting;
- reset/reoptimize annually;
- close RECON-009;
- resolve DQ-030 by assumption;
- approve production;
- authorize live trading;
- connect brokerage/order routing.
