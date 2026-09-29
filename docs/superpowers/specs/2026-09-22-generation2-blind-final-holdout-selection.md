# Generation 2 Blind Final-Holdout Selection Protocol

Date: 2026-09-22

Status: **FROZEN BEFORE CANDIDATE-UNIVERSE QUERY**

Authority: **INDEPENDENT_AUDIT**

## Pre-query correction

The first local selector invocation failed closed with `GEN2_HOLDOUT_SELECTION_REGISTRY_MISMATCH` while verifying frozen inputs. The failure occurred before `_load_sdk()` / `OpenQuoteContext`, so no OpenD context was opened, no static candidate universe was queried, and no provider access ledger was queried. The registry identity was recomputed using the repository's canonical `registry_content_sha256()` semantics and corrected before the first candidate-universe query. Because the deterministic seed binds the registry SHA-256, the seed was correspondingly recomputed before any eligible symbol or rank was observed. This correction does not consume or retry a holdout selection.

## Purpose

Select exactly five previously unused US-listed ETFs for the Generation-2
FINAL_HOLDOUT without inspecting performance-linked information.

This is not strategy research and must not change the frozen survivor.

Frozen survivor:

`G2-A|lookback=189|skip=21|top_k=1|rebalance=21`

Frozen identities:

- survivor identity report SHA-256:
  `96580b61ddb617f54157cc2ce12f5dc5316dc143321f1aaf214e7a563b5aff87`
- binding SHA-256:
  `fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b`
- implementation SHA-256:
  `35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b`
- permanent exclusion-registry SHA-256:
  `de8abace734cd6b1550d68d79166c806203435e1e7f7b48a236f497c32b9bf61`

## Evaluation chronology

The project chronology remains unchanged:

- TRAIN: through 2018-12-31
- VALIDATION: 2019-01-01 through 2022-12-31
- FINAL_HOLDOUT: 2023-01-01 through 2025-12-31

The frozen survivor uses a 189-session momentum lookback and 21-session skip,
so the final-holdout acquisition must provide **210 completed pre-window
sessions** for signal warmup.

Using the XNYS calendar, the earliest required warmup session for the first
2023 scored session is **2022-03-03**. Therefore a candidate whose trustworthy
static listing date is later than 2022-03-03 is ineligible.

## Permitted provider calls during selection

Only two OpenD interfaces are permitted:

1. `get_stock_basicinfo(Market.US, SecurityType.ETF)`
2. `get_history_kl_quota(get_detail=True)`

The first may contribute only:

- code;
- name;
- listing date;
- delisting flag;
- stock/security type.

The second is access-control evidence only. It may contribute symbol identity
and request-time metadata from the current provider quota ledger. It must not
be treated as lifetime provider history.

No history, quotes, snapshots, current-kline, order-book, ticker, fundamental,
financial, rehab/corporate-action, or trading API may be called during
selection.

## Permanent exclusions

Before deterministic ranking, the selector must load and verify:

`data/governance/holdout-exclusion-registry.json`

All 18 symbols in that registry are permanently ineligible.

No manual exception is allowed.

## Additional contamination controls

A candidate is also ineligible when either source below indicates prior
historical access:

### Provider current-period quota ledger

If `get_history_kl_quota(get_detail=True)` includes the candidate symbol, it is
excluded before ranking.

This evidence is explicitly limited to the provider's current quota-history
window and is not represented as lifetime history.

### Retained local OpenD logs

All supplied retained OpenD log files are hashed.

The selector scans explicit `Qot_RequestHistoryKL` / protocol-3103 context and
collects exact candidate symbols found within eight lines before or after each
history-request marker.

Both `US.<symbol>` and exact bare-symbol forms are recognized.

Ambiguous parsing fails closed.

## Static eligibility

A candidate is eligible only if all conditions hold:

1. It is returned by the full US ETF static-info call.
2. Code is canonical `US.<SYMBOL>`.
3. It is not delisted.
4. Listing date is a trustworthy ISO date no later than 2022-03-03.
5. Missing, malformed, or provider sentinel `1970-01-01` listing dates are
   ineligible.
6. Name is nonempty and not `unknown stock`.
7. It is not in the permanent exclusion registry.
8. Name does not conservatively indicate leverage, inverse exposure, ETN,
   daily bull/bear/long/short products, or standalone +/-1X, 2X, or 3X style
   leverage.
9. It does not appear in the current provider history-quota detail.
10. It does not appear in retained local protocol-3103 history context.

No liquidity, AUM, volume, price, volatility, return, drawdown, or performance
filter is permitted.

## Deterministic seed

Seed material is frozen as:

`GENERATION2-BLIND-FINAL-HOLDOUT-v1|96580b61ddb617f54157cc2ce12f5dc5316dc143321f1aaf214e7a563b5aff87|fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b|35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b|de8abace734cd6b1550d68d79166c806203435e1e7f7b48a236f497c32b9bf61|2023-01-01|2025-12-31|2022-03-03`

Its SHA-256 is:

`51bc792c6550a3b49e608acf12343153223d29325cbbad97fbbf4785a61a348c`

For each eligible symbol `S`:

`rank_key = SHA256(seed_sha256 + "|" + S)`

Sort ascending by rank key, then ascending symbol.

The first five are the only selected final-holdout symbols.

No human or agent may reorder, replace, remove, add, or retry the ranking.

## Failure behavior

If fewer than five eligible uncontaminated ETFs remain:

`GENERATION2_HOLDOUT_SELECTION_UNKNOWN_ABSTAIN`

Do not loosen eligibility and do not change the seed.

## Post-selection boundary

Successful selection freezes symbol identities only.

It does **not** authorize historical access.

After selection:

1. preserve static snapshot, provider-ledger snapshot, and local-log manifests;
2. capture composite virginity evidence;
3. freeze the exact Generation-2 Phase-6 evaluation contract;
4. run CI/audit;
5. issue a separate one-time acquisition authorization.

Until then, no selected holdout history or corporate-action data may be read.

## Independent-source limitation

Generation-2 independent-source provenance remains unresolved
(`independent_source_established=false`).

Selection may proceed because it uses no holdout performance/history, but real
historical acquisition remains subject to the independent-audit pre-access
review. No production-readiness approval may be inferred.

## Prohibited actions

Do not:

- inspect price history before selection;
- query current price or quote data;
- use volume, AUM, spread, analyst/fundamental data, returns, volatility,
  drawdown, or strategy results;
- alter the seed after seeing selected names;
- manually substitute a selected symbol;
- test alternative sets;
- use selected-symbol information to tune the frozen survivor;
- access selected-symbol history before separate authorization;
- start Phase 7.
