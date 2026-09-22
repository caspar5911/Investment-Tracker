# Phase 6 Independent Audit Decision

Date: 2026-09-21  
Authority: **INDEPENDENT_AUDIT**  
Audited coordinator branch: `codex/phase6-final-holdout-preseal`  
Audited HEAD: `659b09feb91813a03636c9e007c891dff4071f80`

## Decision

`PHASE6_AUDIT_UNKNOWN_ABSTAIN`

`FINAL_HOLDOUT_RELEASE_NOT_AUTHORIZED`

No locked FINAL_HOLDOUT symbol data was fetched, inspected, summarized, inferred, or derived during this audit. No holdout bundle was created. No `PHASE6-HOLDOUT-RELEASE-v1` envelope was issued.

The exact pre-access evaluation contract is frozen at:

- `data/phase6/phase6-evaluation-contract.json`
- SHA-256: `f64f31c20172491f6175a176592d463fed36f73ecf2b99542022afa55f50b77e`

The frozen contract selects:

- calendar window: `2023-01-01` through `2025-12-31`;
- exact locked universe: `HACK, SOXX, NLR, URNM, GEV`;
- methodology: Option A, `QFQ-NORMALIZED-RESEARCH-v1`;
- signal prices: `MOOMOO_QFQ`;
- execution/marking: `MOOMOO_QFQ_NORMALIZED`;
- primary friction: `3 bps`;
- fixed friction cases: `0, 3, 10, 25, 50 bps`;
- no result-dependent thresholds;
- DQ-030 remains unresolved, so `max_drawdown` and `calmar` remain UNKNOWN;
- one-time semantics with no retry, tuning, replacement candidate, or methodology switch after access.

The window was selected from pre-existing repository chronology rather than locked-symbol availability or performance. An earlier sealed-access implementation committed on 2026-09-11 encoded TRAIN through 2018, VALIDATION through 2022, and FINAL_HOLDOUT over 2023-2025; the frozen Phase 4 campaign is also identified as `PHASE4-FIXED-LONG-ONLY-2014-2022-v1`. Insufficient history for any locked symbol is therefore a fail-closed DQ outcome, not grounds to alter the window.

## Audit findings

### Verified

1. Frozen Phase 4 identity is preserved:
   - candidate `phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075`;
   - binding `9ff5b11e1b7f381ce574f4b0fc37a16d824e64afa5afeba16be54980c3ed5d3a`;
   - implementation `bebb913887573a293e6a8cf23ad3d28e5fa3bbd2f613995e37741ec4d80f7c6f`;
   - parameters 126 / 21 / 3 / 21;
   - completed-session signal to next eligible open;
   - long-only, no leverage.

2. The sealed Phase 4 finalization decision still records `ONE_FROZEN_SURVIVOR`, population position 150, no final-holdout access, no strategy search after finalization, no parameter mutation, and no provider calls at finalization.

3. Comparing sealed Phase 4 commit `69bb4347cbe577c4a1277335eef778ddf5b177d0` to the audited HEAD shows Phase 4 source and finalization evidence were not modified. Later changes add Phase 5/6 code and evidence.

4. Phase 5 remains formally `PHASE5_UNKNOWN_ABSTAIN` for `INDEPENDENT_SOURCE_SNAPSHOT_MISSING`. The owner waiver explicitly does not convert this to PASS.

5. Phase 6 preseal code validates Independent-Audit-only release authority and the exact frozen candidate/binding/implementation identities.

6. The one-release consumption path exclusive-creates a marker before the first bundle payload read; an attempted second consumption of the same release ID is rejected; a bundle hash failure after payload-read initiation still leaves the release consumed.

7. Phase 6 code has no provider or brokerage execution surface. Repository search found no `place_order`, `OpenSecTradeContext`, `unlock_trade`, or `modify_order` capability. `AGENTS.md` prohibits brokerage/order-routing and real-money actions.

8. No Phase 7 implementation appears in the audited Phase 4-to-HEAD change set, and Phase 6 governance explicitly keeps `phase7_started=false`.

9. Option B cannot be treated as frozen authority: the repository's methodology audit states `UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS` is the required successor and that no dual-price/unadjusted-history implementation was introduced. Option A is therefore the only methodology frozen by this audit.

### Decision-critical blockers

#### IA-BLOCK-001 — prior locked-symbol non-access is not independently provable

Repository artifacts and code guards consistently state `protected_symbols_accessed=[]`, and the Phase 4/5/6 code paths are designed to reject protected symbols. However, the repository does not contain an independent provider-side query log, audit-controlled access log, or equivalent evidence that can prove the coordinator never manually queried the five locked symbols outside the governed code path.

Because the release criteria require Independent Audit to verify that the locked symbols have not previously been accessed, coordinator/self-reported safety flags alone are insufficient for release.

Required closure: provide an independent access-history attestation or provider/audit log covering the locked symbols and the relevant research period, with immutable identity and reviewable provenance.

#### IA-BLOCK-002 — no audit-controlled Moomoo QFQ holdout acquisition/sealing channel is available

The frozen contract requires `MOOMOO_QFQ` / `MOOMOO_QFQ_NORMALIZED` for strict Phase 4 comparability. This audit environment has no Moomoo/OpenD provider session and no pre-existing sealed holdout bundle. Substituting another provider or adjusted-price convention would change the frozen question.

Therefore an exact holdout bundle and its SHA-256 cannot be produced under the frozen contract without an independently controlled Moomoo QFQ acquisition step.

Required closure: Independent Audit must acquire the exact locked-symbol QFQ daily data, plus SPY benchmark data and the required warmup sessions, through an audit-controlled Moomoo/OpenD path after the release prerequisites are satisfied. Missing coverage must fail closed; it must not cause a window change.

#### IA-BLOCK-003 — coordinator-proof pre-consumption sealing is procedural, not enforced

`consume_released_bundle` guarantees marker-before-read for that function, but a plaintext bundle placed in coordinator-accessible storage can still be opened manually before the marker exists. The current repository does not provide cryptographic sealing, an audit-controlled storage capability, or an equivalent technical boundary that prevents such pre-consumption inspection.

The release criteria require the bundle to remain sealed from the coordinator until the one-time consumption boundary.

Required closure: keep the bundle in Independent-Audit-controlled storage and expose it only through the one-time consumption boundary, or add a cryptographic/access-control mechanism whose key/capability is unavailable to the coordinator before the marker is atomically created.

#### IA-BLOCK-004 — green preseal CI is not independently observable in the available repository connection

The branch contains a dedicated `phase6-preseal-static` workflow and the committed tests cover release identity, contract hash binding, marker-before-read, and one-time reuse rejection. However, the available GitHub connection returned no commit status and no workflow run for HEAD `659b09f...`, so this audit cannot independently attest that the required preseal CI actually completed successfully at the audited revision.

Required closure: provide the immutable GitHub Actions run URL/ID (or equivalent signed CI artifact) for the exact audited HEAD showing the Phase 6 preseal workflow green.

## Release consequence

Until all decision-critical blockers are closed, the valid state remains:

`PHASE6_READY_FOR_INDEPENDENT_AUDIT_RELEASE`

with Independent Audit outcome:

`PHASE6_AUDIT_UNKNOWN_ABSTAIN`

No holdout release envelope may be created, no locked-symbol history may be fetched by the coordinator, no Phase 6 evaluation may run, and Phase 7 must not start.

This decision does not approve production readiness and does not alter the formal Phase 5 conclusion.
