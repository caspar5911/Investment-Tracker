# Phase 6 Blind Replacement-Holdout Selection Protocol

Status: **PREREGISTERED BEFORE REPLACEMENT UNIVERSE ACQUISITION**

Date: 2026-09-21

Authority: **INDEPENDENT_AUDIT**

## Reason

The originally locked Phase 6 replacement holdout
`HACK, SOXX, NLR, URNM, GEV` was rejected after project-owner-supplied OpenD
logs showed `Qot_RequestHistoryKL` context for every symbol.

The rejected symbols remain unusable. Their market history and any later
performance result must not influence replacement selection.

## Purpose

Select exactly five new US-listed ETFs for the one-time Phase 6 FINAL_HOLDOUT
without inspecting price history, returns, volatility, drawdown, momentum,
strategy performance, benchmark-relative performance, liquidity, AUM, volume,
spread, analyst data, fundamentals, or any other performance-linked measure.

This protocol is frozen before the replacement ETF universe is requested.

## Frozen inputs

The selection rule is bound to:

- original Phase 6 evaluation-contract SHA-256:
  `f64f31c20172491f6175a176592d463fed36f73ecf2b99542022afa55f50b77e`;
- rejected-holdout classification SHA-256:
  `7d450b567211e4590434af8aa93c28b943eecc053be2620647d446139c4ce2f0`;
- frozen Phase 4 candidate:
  `phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075`;
- frozen binding:
  `9ff5b11e1b7f381ce574f4b0fc37a16d824e64afa5afeba16be54980c3ed5d3a`;
- frozen implementation:
  `bebb913887573a293e6a8cf23ad3d28e5fa3bbd2f613995e37741ec4d80f7c6f`.

The selection seed is the SHA-256 hex digest of the ASCII string:

`PHASE6-BLIND-REPLACEMENT-v1|f64f31c20172491f6175a176592d463fed36f73ecf2b99542022afa55f50b77e|7d450b567211e4590434af8aa93c28b943eecc053be2620647d446139c4ce2f0`

No later result may change that seed.

## Permitted metadata acquisition

Independent Audit may call only Moomoo/OpenD static-security metadata for the
candidate population:

`get_stock_basicinfo(Market.US, SecurityType.ETF)`

The static call may use only:

- security code;
- security name;
- security type;
- listing date;
- delisting flag.

Moomoo documents this interface as static stock information and exposes
`listing_date` and `delisting`. The listing-date field is deprecated by the
provider, so a missing, malformed, or ambiguous listing date makes the symbol
ineligible rather than permitting another data source to be substituted after
selection begins.

No historical-kline, snapshot, quote, order book, ticker, fundamental,
financial, rehab/corporate-action, or trading API may be called during
selection.

## Eligibility rule

A security is eligible only when all conditions hold:

1. Moomoo returns it from the full US `SecurityType.ETF` static-information
   request.
2. Code is a nonempty `US.<symbol>` value and the canonical symbol consists
   only of uppercase ASCII letters, digits, dot, or hyphen.
3. `delisting == false`.
4. `listing_date` is a valid ISO date no later than `2022-06-02`, the first
   required 147-session warmup date for the frozen 2023-2025 evaluation
   window.
5. Name is nonempty and is not `unknown stock`.
6. Symbol is not one of the Phase 4/5 research symbols:
   `GLD, IEF, IWM, QQQ, SPY, TLT, VNQ, XLP`.
7. Symbol is not one of the rejected holdout symbols:
   `HACK, SOXX, NLR, URNM, GEV`.
8. The normalized uppercase security name does not match any of these
   conservative leveraged/inverse exclusions:
   - contains `LEVERAGED`, `INVERSE`, `ULTRA`, `ULTRAPRO`,
     `ULTRASHORT`, or `BEAR`;
   - contains a standalone `1X`, `2X`, `3X`, `-1X`, `-2X`, or
     `-3X`;
   - contains `ETN`;
   - contains both `DAILY` and any of `BULL`, `BEAR`, `LONG`,
     `SHORT`.
9. The local OpenD access-log snapshot contains no symbol occurrence in
   explicit `Qot_RequestHistoryKL` / protocol-3103 context for that symbol.

The access-log condition is contamination control only. It does not inspect
prices or performance.

## Log-snapshot rule

The selection command must hash every supplied OpenD log file and record the
complete ordered file manifest in the selection evidence.

Historical-request contamination is detected generically from the logs before
the final five are chosen:

- identify explicit `Qot_RequestHistoryKL` / protocol-3103 context;
- conservatively collect every `US.<symbol>` token within eight lines before
  or after that context;
- treat every collected symbol as historically accessed;
- do not inspect or emit historical values.

If log parsing is ambiguous, fail closed.

## Deterministic ranking

For each eligible, uncontaminated symbol `S`, compute:

`rank_key = SHA256(selection_seed + "|" + S)`

where all text is ASCII and `S` is the uppercase symbol without the `US.`
prefix.

Sort ascending by:

1. `rank_key`;
2. symbol as a deterministic tie-breaker.

The first five symbols are the replacement holdout.

No human may reorder, substitute, remove, or add symbols after ranking.

## Insufficient-candidate behavior

If fewer than five eligible uncontaminated symbols remain, selection status is:

`PHASE6_REPLACEMENT_SELECTION_UNKNOWN_ABSTAIN`

The rule must not be loosened and no alternative seed may be tried.

## Post-selection freeze

A successful selection emits a non-performance manifest containing:

- protocol/version identity;
- exact seed and seed SHA-256;
- static metadata snapshot SHA-256;
- log-manifest SHA-256;
- eligibility counts;
- excluded-symbol counts by reason;
- ordered top-five symbols;
- ordered rank keys;
- exact Phase 4 candidate/binding/implementation identities;
- safety flags asserting no historical market-data call was used by the
  selector.

Immediately after successful selection, the five symbols become the only
permitted replacement FINAL_HOLDOUT symbols.

No price/history access is allowed until Independent Audit freezes an amended
Phase 6 evaluation contract and explicitly authorizes acquisition.

## Evaluation invariants after replacement

Replacement changes only the holdout symbol set and the identities derived from
that set.

The following remain unchanged:

- candidate;
- parameters `126 / 21 / top_k=3 / rebalance=21`;
- long-only and no portfolio leverage;
- signal at completed session `t` -> next eligible `t+1` open;
- evaluation calendar `2023-01-01` through `2025-12-31`;
- 147-session signal warmup;
- `QFQ-NORMALIZED-RESEARCH-v1`;
- `decision_grade=false`;
- initial cash `100000`;
- friction cases `0, 3, 10, 25, 50` bps;
- primary friction `3` bps;
- DQ-030 remains unresolved;
- Phase 5 remains `PHASE5_UNKNOWN_ABSTAIN`;
- no performance PASS threshold;
- one-time marker-before-read semantics;
- no Phase 7;
- no production-readiness approval.

## Forbidden actions

After this protocol is committed, do not:

- inspect replacement price history before selection;
- use current price, returns, volatility, volume, AUM, spread, analyst ratings,
  fundamentals, or strategy results to choose replacements;
- change the seed because the selected symbols are undesirable;
- manually swap a selected symbol;
- use historical data to test whether a different replacement set looks
  better;
- retry the selector with another ranking method;
- alter the frozen strategy because of replacement selection.

Any such action invalidates the replacement holdout.
