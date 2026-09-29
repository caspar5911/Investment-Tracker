# Generation-3 Stage-B Independent Audit

## Decision

**APPROVED** on 2026-09-23 at 03:38:59 UTC.

Authorization ID: `INDEP-AUDIT-GEN3-ACQUISITION-0001`

This audit authorizes the governed one-time Generation-3 final-holdout acquisition boundary. It does not authorize Phase 7, production readiness, symbol substitution, retry after historical access, methodology changes, or real-money activity.

## Audited baseline and scope

- Target baseline: `3c83ae07f7ce9ec76d246e749b528a7cded45dc1`
- Stage-A runtime evidence commit: `5f944e03ed56d6174c3e48b1f913c159766f0ccf`
- The six Stage-A evidence blobs are byte-identical between the Stage-A commit and the audited baseline.
- The two intervening commits modify only the frozen Generation-2 exclusion-registry snapshot and its test.
- Protected historical data, selected-symbol prices, returns, corporate actions, and performance were not accessed or inspected during this audit.

## Frozen identities

- Successor: `GENERATION_3`
- Candidate: `G2-A|lookback=189|skip=21|top_k=1|rebalance=21`
- Locked symbols, in frozen order: `ACV`, `GVIP`, `WBIY`, `FCEF`, `FDLO`
- Selection status: `SUCCESSOR_HOLDOUT_SELECTION_FROZEN`
- Virginity status: `COMPOSITE_EVIDENCE_NO_PRIOR_SELECTED_SYMBOL_ACCESS_FOUND`
- Phase-6 contract status: `FROZEN_PRE_ACCESS`
- Historical market-data API called during Stage A: `false`
- Provider-history selected-symbol matches: none
- Retained-log selected-symbol matches: none

The five rank keys reproduce from the frozen selection seed using `sha256(seed_sha256 + "|" + symbol)`, are in ascending order, and preserve positions 1 through 5 without substitution.

## Verified SHA-256 identities

| Artifact | SHA-256 |
|---|---|
| Phase-6 evaluation contract | `6695699d357dd8323a1e00b5b43e2e4d7ed0ff53b03c971d14ccf3e85c00be71` |
| Holdout selection | `1edafd502cd40aa8705cd0a66c24d43016806d842ef6346115863112c503499f` |
| Virginity attestation | `50072657c6c63a73fc4327908c66920b472b4b81fd56491f782c2b8bd0d0fd19` |
| Virginity evidence | `97cc8638b901cc5562b9a0d199c2e553f4016006d210ba1abedbb3cebba32077` |
| Successor normalizer | `bfbf0de5bdeb39af3535641570f3f9224f5301abb7db9fffc34c580481cace04` |
| Successor evaluator | `c933cc2b71bf068f9db1f4656f7fea57ed3a5e0307819abc177897782e63e0ea` |
| Successor acquisition implementation | `86f502e1c0d795162695fccc868d16d3f1dd4a36eb25d626191755b6ba4f4e12` |
| Successor release implementation | `7b39984e331d8479306dfbbc0c96c126aff5c7e1038970328bed6d6e07818f6a` |

The normalizer and evaluator hashes match the Stage-A methodology authorization, holdout selection, and Phase-6 evaluation contract.

## Acquisition-boundary review

The acquisition path satisfies the authorized boundary:

- provider quota and selected-symbol virginity are rechecked without historical reads before consumption;
- an exclusive acquisition-start marker is written, flushed, fsynced, and read back before the first historical request;
- the marker is advanced to `historical_access_started=true` and durably read back before historical access;
- marker exclusivity makes any attempted retry fail closed after acquisition has started;
- symbols are taken only from the hash-bound authorization and frozen Phase-6 contract;
- private output is required to resolve outside the repository;
- QFQ bars are acquired only for signal construction, while unadjusted bars are acquired for execution and marking;
- rehab, dividend, and split sources are acquired for every locked identity and the benchmark;
- the encrypted bundle, key, and receipt are sealed and read back without computing or inspecting performance.

## Release and evaluation review

The release/evaluation path satisfies the frozen contract:

- receipt self-hash, encrypted-bundle hash, key hash, contract hash, authorization hash, and implementation identities are verified;
- a valid release artifact is mandatory before evaluation;
- an exclusive one-time consumption marker is written before encrypted-bundle read/decryption;
- the executing survivor, evaluator, and normalizer identities are reverified;
- only the frozen `G2-A` parameters execute;
- friction cases are exactly `0`, `3`, `10`, `25`, and `50` bps, with `3` bps primary;
- corporate-action normalization v2 reconciles split, rehab, and dividend evidence;
- evaluation exceptions produce `PHASE6_UNKNOWN_ABSTAIN`, remain consumed, and carry no retry authority;
- candidate tuning, parameter mutation, symbol substitution, Phase 7, and production-readiness approval remain forbidden.

## Tests and CI

- Successor compilation: pass
- Focused successor regression suite: 32 passed
- Trading/order API governance boundary: pass
- Prior-holdout protected-symbol source boundary: pass
- Frozen governance-state assertions: pass
- GitHub Actions `successor-corporate-actions-v2` run `35814143462` for `3c83ae0`: success

## Authorization boundary

The next permitted action is the coordinator's governed `preflight-final-holdout` command using the committed Stage-B authorization and the frozen Stage-A artifacts. That preflight is quota/virginity-only and does not consume protected history. A one-time `acquire-final-holdout` may occur only after that preflight passes, with private output outside the repository and no retry after the acquisition-start marker is consumed.
