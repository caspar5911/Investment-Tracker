# Phase 6 Independent Audit Execution and Sealing Specification

Status: **FROZEN PRE-ACCESS**

Date: 2026-09-21

This document describes the implementation procedure for the already frozen
Phase 6 evaluation contract. It does not authorize FINAL_HOLDOUT access.

## Bound evaluation contract

- Contract: `data/phase6/phase6-evaluation-contract.json`
- SHA-256: `f64f31c20172491f6175a176592d463fed36f73ecf2b99542022afa55f50b77e`
- Candidate: `phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075`
- Binding: `9ff5b11e1b7f381ce574f4b0fc37a16d824e64afa5afeba16be54980c3ed5d3a`
- Implementation: `bebb913887573a293e6a8cf23ad3d28e5fa3bbd2f613995e37741ec4d80f7c6f`

No candidate, parameter, strategy family, price methodology, window, or
performance threshold may change after holdout access.

## Authority separation

Coordinator preseal code remains under
`src/investment_tracker/quant/phase6`. It contains no provider client and no
locked-symbol list.

Independent Audit provider and release capabilities live separately under
`src/investment_tracker/independent_audit/phase6`.

The acquisition code may not load the Moomoo/Futu SDK or create an OpenD quote
context until all of these have validated:

1. exact frozen evaluation-contract SHA-256;
2. an Independent-Audit virgin-holdout attestation covering the exact five
   locked symbols;
3. an Independent-Audit acquisition authorization bound to that attestation;
4. a green CI run identity recorded in that authorization.

A simple no-match scan of supplied log files is evidence only. It cannot create
a virgin-holdout attestation automatically.

## Session authority

The evaluation window remains calendar dates
`2023-01-01` through `2025-12-31`.

Eligible sessions are the ordered XNYS sessions in that frozen calendar
window. The warmup is mechanically derived as the immediately preceding 147
XNYS sessions, equal to `lookback_sessions + skip_sessions = 126 + 21`.

The provider request start is the date of the first mechanically derived warmup
session. The provider request end is `2025-12-31`.

Every required session must exist for every locked symbol and SPY. Missing
coverage fails closed. The implementation must not move the window, delay the
start, drop a symbol, replace a symbol, shorten warmup, or retry with another
universe.

Warmup bars are used only for causal signal state. No pre-window fill or
performance metric is permitted.

## Provider and price convention

Independent Audit requests daily Moomoo/OpenD history with:

- `KLType.K_DAY`;
- `AuType.QFQ`;
- `extended_time=False`;
- no trading context.

Only OHLC values required for the research-comparable Phase 4 accounting path
are sealed. No brokerage credentials, order routing, trade unlock, or real
orders are permitted.

The result remains `QFQ-NORMALIZED-RESEARCH-v1`,
`decision_grade=false`.

## Immutable encrypted bundle

Acquisition validates all expected sessions before constructing the bundle.

The plaintext archive is canonical in structure:

- `manifest.json` first;
- one CSV per symbol under `bars/`;
- deterministic member ordering;
- stored ZIP members with fixed metadata;
- SHA-256 and byte count for every member.

The plaintext archive is then encrypted using AES-256-GCM. The frozen
evaluation-contract SHA-256 is authenticated additional data.

Independent Audit records:

- plaintext bundle SHA-256;
- encrypted bundle SHA-256;
- key SHA-256;
- holdout ID;
- provider and adjustment convention;
- authorization SHA-256;
- access safety state.

The encryption key and encrypted bundle must remain outside the repository.
The repository receives no historical locked-symbol payload.

## Release envelope

Only after a sealed acquisition receipt exists may Independent Audit issue
`PHASE6-HOLDOUT-RELEASE-v1`.

The release binds the exact:

- candidate ID;
- binding SHA-256;
- implementation SHA-256;
- evaluation-contract SHA-256;
- holdout ID;
- encrypted-bundle SHA-256;
- one-time flag.

Issuing the release does not compute or inspect holdout performance.

## One-time consumption boundary

The coordinator evaluator:

1. validates the release, contract, receipt and key identity without opening the
   holdout bundle;
2. exclusive-creates the consumption marker;
3. only then reads and hashes the encrypted bundle;
4. decrypts it;
5. verifies the plaintext identity and every archived member;
6. validates exact expected-session coverage;
7. executes the frozen strategy exactly once.

If any failure occurs after the consumption marker is created, the release
remains consumed and the result is `PHASE6_UNKNOWN_ABSTAIN`. There is no
retry, replacement holdout, alternate candidate or parameter change.

## Frozen strategy execution

The evaluator imports the sealed Phase 4 implementation directly:

- `_cross_sectional_absolute_momentum`;
- Phase 4 immutable market panels;
- Phase 4 next-open replay engine;
- Phase 4 friction cases;
- Phase 4 supported metrics;
- Phase 4 durability calculations;
- Phase 4 bootstrap routine.

The scored rebalance clock resets at scored offset zero exactly as the Phase 4
engine does: offset 0, 21, 42, and so on.

A signal is formed on the completed scored-session close and fills only at the
next scored-session open.

The SPY benchmark uses the same scored sessions and the same next-open
execution boundary: the first completed scored session creates a 100% SPY
target for the next eligible open, then holds it. Primary comparison uses the
same 3 bps friction assumption.

The fixed friction ladder remains `0, 3, 10, 25, 50` bps.

## Result semantics

There is no performance PASS threshold in Phase 6.

A technically complete one-time run is recorded as:

`PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE`

A decision-critical DQ or post-consumption execution failure is:

`PHASE6_UNKNOWN_ABSTAIN`

Neither status:

- changes Phase 5 from `PHASE5_UNKNOWN_ABSTAIN`;
- resolves DQ-030;
- makes numeric max drawdown or Calmar permissible;
- approves production readiness;
- authorizes Phase 7;
- permits live trading.
