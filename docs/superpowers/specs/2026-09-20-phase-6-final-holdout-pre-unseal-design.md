# Phase 6 Final-Holdout Pre-Unseal Design

Status: **PRE-UNSEAL / NO HOLDOUT ACCESS AUTHORIZED**

This document defines the portion of Phase 6 that may be completed before any
FINAL_HOLDOUT resource is released. It is intentionally written and committed
before any Phase 6 holdout data is read.

## Purpose

Phase 6 is the one-time final-holdout stage for the exact frozen Phase 4
survivor. Its purpose is to obtain a final, non-retunable test after all
research and long-history evidence has already been observed.

Phase 6 is not Phase 7. It does not implement brokerage integration, forward
paper operations, live order routing, or production decision support.

## Authority entering Phase 6

Phase 6 binds the same frozen survivor used by Phase 5:

- candidate:
  `phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075`
- selected population position: `150`
- implementation SHA-256:
  `bebb913887573a293e6a8cf23ad3d28e5fa3bbd2f613995e37741ec4d80f7c6f`
- binding SHA-256:
  `9ff5b11e1b7f381ce574f4b0fc37a16d824e64afa5afeba16be54980c3ed5d3a`
- parameters:
  `lookback_sessions=126`,
  `skip_sessions=21`,
  `top_k=3`,
  `rebalance_sessions=21`
- signal timing: completed session `t` close -> next eligible `t+1` open
- long-only, no leverage.

The Phase 5 owner waiver is also carried forward. Phase 5 remains formally
`PHASE5_UNKNOWN_ABSTAIN` because
`INDEPENDENT_SOURCE_SNAPSHOT_MISSING`. Phase 6 must never rewrite that state
as a Phase 5 PASS.

## Holdout release authority

Repository governance states that the locked replacement holdout symbols
`HACK, SOXX, NLR, URNM, GEV` may not be fetched, inspected, summarized,
inferred, cached, or derived unless **Independent Audit explicitly authorizes
release**.

The project owner's instruction to prepare Phase 6 authorizes this pre-unseal
engineering work. It does **not** substitute for Independent Audit release of a
locked holdout.

Accordingly:

- no Phase 6 provider client is implemented in the pre-unseal package;
- no locked symbol is requested or inspected;
- no FINAL_HOLDOUT bundle is read;
- no historical information about a locked replacement holdout is inferred;
- no release record is fabricated.

## Independently released holdout contract

A future release record must use schema
`PHASE6-HOLDOUT-RELEASE-v1` and must be supplied by Independent Audit. It must
contain at least:

- `authority = "INDEPENDENT_AUDIT"`;
- `status = "FINAL_HOLDOUT_RELEASE_AUTHORIZED"`;
- a non-empty `holdout_id`;
- exact frozen candidate ID;
- exact frozen binding SHA-256;
- exact frozen implementation SHA-256;
- a SHA-256 identity for the independently supplied evaluation contract;
- a SHA-256 identity for the independently supplied holdout bundle;
- a non-empty release identifier;
- an explicit statement that the release is one-time.

The pre-unseal code validates only the release envelope and frozen-strategy
identity. It must not inspect a holdout bundle while validating the envelope.

## One-time consumption rule

When a valid Independent Audit release is eventually supplied, Phase 6 must
create an immutable consumption marker **before** the first holdout payload is
opened. Marker creation uses exclusive-create semantics. If the marker already
exists, the holdout is considered consumed and evaluation is refused.

A failed evaluation after first payload access does not restore virgin holdout
status. There is no retry, alternate candidate, parameter adjustment, or
replacement holdout merely because the result is disappointing or an
implementation error occurs.

The consumption marker records only non-performance identities needed to prove
which release and frozen candidate were consumed. It must not contain holdout
market data.

## Pre-unseal readiness result

Before release, the strongest permissible Phase 6 result is:

`PHASE6_READY_FOR_INDEPENDENT_AUDIT_RELEASE`

This means only that:

- Phase 4 authority is bound;
- the Phase 5 limitation is carried forward;
- the release schema is frozen;
- one-shot consumption is enforced;
- no holdout/provider access surface exists in the pre-unseal package;
- no real-money capability exists.

It is not a holdout PASS and not production approval.

## Post-release evaluation

The exact evaluation protocol cannot be invented from unreleased holdout
content. Independent Audit must release or identify the sealed evaluation
contract together with the holdout bundle. Phase 6 implementation must bind
that contract by SHA-256 before reading the bundle.

Any later evaluator must satisfy all of the following:

- exact frozen Phase 4 survivor only;
- no candidate search;
- no parameter mutation;
- no result-dependent threshold changes;
- no feedback into Phase 4 or Phase 5;
- paper-only;
- DQ-030 remains unresolved unless separately resolved before evaluation;
- missing decision-critical evidence => UNKNOWN/ABSTAIN;
- final result remains non-production-approved until Independent Audit
  explicitly approves readiness.

## Safety flags

Every Phase 6 pre-unseal record must state:

- `final_holdout_accessed=false`;
- `protected_symbols_accessed=[]`;
- `candidate_search_executed=false`;
- `candidate_parameters_changed=false`;
- `phase4_feedback_written=false`;
- `phase5_feedback_written=false`;
- `live_trading_capability=false`;
- `phase7_started=false`.

## Stop boundary

This pre-unseal implementation stops immediately before Independent Audit
release and holdout consumption. It does not start Phase 7.
