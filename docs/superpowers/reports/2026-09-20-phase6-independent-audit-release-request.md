# Phase 6 Independent Audit Release Request

Status: READY TO SUBMIT AFTER PRE-UNSEAL CI IS GREEN

## Requested audit action

Independently review the Phase 6 pre-unseal design and decide whether the
FINAL_HOLDOUT may be released for one-time evaluation.

This request does not ask Independent Audit to approve production readiness. It
asks only for a release decision and the immutable identities needed to consume
the holdout exactly once.

## Frozen research identity

- candidate:
  `phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075`
- binding SHA-256:
  `9ff5b11e1b7f381ce574f4b0fc37a16d824e64afa5afeba16be54980c3ed5d3a`
- implementation SHA-256:
  `bebb913887573a293e6a8cf23ad3d28e5fa3bbd2f613995e37741ec4d80f7c6f`
- budget position: `150`
- parameters: lookback 126, skip 21, top-k 3, rebalance 21 sessions
- execution: completed-session signal -> next eligible session open
- long-only, no leverage.

## Carried-forward limitation

Phase 5 remains formally:

`PHASE5_UNKNOWN_ABSTAIN`

because:

`INDEPENDENT_SOURCE_SNAPSHOT_MISSING`

The project owner waived the paid Massive comparison only for continued
non-live research. Phase 6 must not rewrite this limitation.

## What Independent Audit must provide if release is approved

1. An immutable evaluation contract suitable for the released holdout.
2. SHA-256 of that evaluation contract.
3. An immutable holdout bundle.
4. SHA-256 of that holdout bundle.
5. A release envelope conforming exactly to
   `PHASE6-HOLDOUT-RELEASE-v1`:

```json
{
  "schema_version": "PHASE6-HOLDOUT-RELEASE-v1",
  "authority": "INDEPENDENT_AUDIT",
  "status": "FINAL_HOLDOUT_RELEASE_AUTHORIZED",
  "release_id": "<unique immutable release id>",
  "holdout_id": "<immutable holdout id>",
  "candidate_id": "phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075",
  "binding_sha256": "9ff5b11e1b7f381ce574f4b0fc37a16d824e64afa5afeba16be54980c3ed5d3a",
  "implementation_sha256": "bebb913887573a293e6a8cf23ad3d28e5fa3bbd2f613995e37741ec4d80f7c6f",
  "evaluation_contract_sha256": "<64 hex>",
  "holdout_bundle_sha256": "<64 hex>",
  "one_time": true
}
```

## Required audit checks before release

Independent Audit should verify that:

- the candidate and implementation identities match sealed Phase 4 evidence;
- no Phase 6 holdout resource has already been consumed;
- no candidate search or parameter mutation occurred after Phase 4 selection;
- Phase 5 results did not flow back into the frozen strategy;
- the released evaluation contract does not introduce result-dependent
  thresholds or strategy modifications;
- the holdout bundle identity is immutable;
- the bundle is not exposed to research code before the consumption marker is
  written;
- the one-time evaluation cannot be retried to obtain a better result.

## Coordinator behavior after release

The coordinator must validate the release envelope first. It must then
exclusive-create the Phase 6 consumption marker before opening the holdout
payload. Once the payload is opened, the holdout is consumed even if evaluation
fails.

No alternate candidate, tuning, or retry is permitted after consumption.
