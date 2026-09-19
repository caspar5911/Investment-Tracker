# Phase 5 Long-History Durability and Decision-Grade Reconstruction

Status: FROZEN BEFORE AUTHORITATIVE PHASE 5 PERFORMANCE IS OBSERVED.

## Governing authority

Phase 5 starts only because Phase 4 ended with exactly one frozen survivor. The
authoritative Phase 4 finalization commit is
`69bb4347cbe577c4a1277335eef778ddf5b177d0`, with decision content SHA-256
`913d14c1061c2cbbb16e66b448b715952c4a360dbda299500eacd0fd61156958`.

The only strategy admitted to Phase 5 is population position 150:

- candidate: `phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075`
- family: `cross_sectional_absolute_momentum_rotation`
- parameters: lookback=126, skip=21, top_k=3, rebalance=21 sessions
- binding: `9ff5b11e1b7f381ce574f4b0fc37a16d824e64afa5afeba16be54980c3ed5d3a`
- implementation: `bebb913887573a293e6a8cf23ad3d28e5fa3bbd2f613995e37741ec4d80f7c6f`

No parameter, family, ranking, candidate, rule, or rebalance change is permitted.
Phase 5 results may not feed back into Phase 4.

## Existing frozen Phase 5 contract

This phase implements `PHASE5-LONG-HISTORY-DURABILITY-CONTRACT-v1` from the
sealed Gate 1 policy. It answers: "Can this exact frozen strategy remain useful
for many years without periodic retuning?" The desired common history is
approximately 15–20 years if defensible. The actual longest common history is
reported, never synthesized.

Required reporting includes CAGR, calendar year/month returns, positive
year/month percentages, average winning/losing month, worst year/month, longest
losing month sequence, rolling 12/36/60-month results where complete, return
concentration, recovery characteristics, regime consistency, and realistic
cost/slippage.

DQ-030 remains unresolved. Therefore max drawdown, Calmar, and any recovery
quantity that requires a drawdown convention remain UNKNOWN rather than
redefined in Phase 5.

## Provider authorization and safety boundary

The user's explicit Phase 5 authorization on 2026-09-19 authorizes provider
access for the ordinary Phase 4 universe only. It does not authorize FINAL_HOLDOUT
release or protected-symbol access.

The only Phase 5 universe is the sealed eight-symbol universe:
`GLD, IEF, IWM, QQQ, SPY, TLT, VNQ, XLP`.

The locked replacement holdout symbols remain prohibited. The exporter and
loader fail closed if any protected symbol is requested or appears in evidence.
No brokerage order routing or live-trading surface is introduced.

## Primary data source

Moomoo OpenD is the primary Phase 5 acquisition source.

For every symbol, OpenD must export:

1. Daily `AuType.NONE` candlesticks for actual historical OPEN/CLOSE used for
   fills and mark-to-market.
2. Daily `AuType.QFQ` candlesticks used only by the unchanged Phase 4 signal
   algorithm, preserving the research strategy's signal representation.
3. `get_rehab(code)` adjustment/corporate-action records for explicit raw-ledger
   handling.

The requested acquisition window is 2004-01-01 through 2022-12-30. The
backtester takes the intersection of actual returned sessions and reports the
longest defensible common history. It never fabricates pre-inception data.

OpenD QFQ prices are never used as executable fill prices in Phase 5.

## Corporate actions

Raw holdings are explicitly transformed on the OpenD ex-dividend/rehab date
before that session's OPEN execution:

- forward split: units multiplied by `split_base / split_ert`
- consolidation/join: units multiplied by `join_ert / join_base`
- ordinary and special cash dividends: cash credited per pre-open held unit
- unsupported nonzero bonus/transfer/allotment fields fail closed

This ex-date cash-credit convention is frozen before results and is used to
preserve self-financing total-return accounting when OpenD does not expose a
separate historical payment-date cash ledger.

## Strategy and execution

The Phase 5 signal generator calls the committed Phase 4
`_cross_sectional_absolute_momentum` implementation with the exact frozen
`FixedStrategyBinding`. There is no copied or modified Phase 5 ranking logic.

The first scored session is the first common session with at least
`lookback + skip = 147` strictly earlier/common signal observations available.
Portfolio state begins with 100,000 cash and zero units. Indicator history does
not carry portfolio P&L.

On each rebalance session:

- session t QFQ close history generates the frozen target after t closes
- target executes only at the next common session t+1 raw `AuType.NONE` OPEN
- the portfolio marks at raw `AuType.NONE` CLOSE
- long only, no borrowing, no shorting, no leverage
- primary one-way friction is the frozen 3 bps
- stress replays use 10, 25, and 50 bps without changing targets or parameters

A final-session signal remains unfilled.

## Regime analysis

Phase 5 reuses the Phase 4 regime algorithm, not the Phase 4 2019–2022 mapping:
lagged 126-session sign breadth across the exact eight assets, using the
strictly lagged numerator and denominator. At least six positive assets means
`broad_positive_trend`; at least six negative means
`broad_negative_trend`; otherwise `mixed_cross_asset`.

The algorithm is fixed; the long-history mapping is newly derived only because
the sessions are different.

## Evidence and outcome

Phase 5 engineering can produce one of:

- `READY_FOR_PASS_REVIEW`: complete OpenD bundle, all mandatory integrity
  checks pass, exact frozen strategy replay completed, required durability
  evidence produced.
- `ABSTAIN_DATA_INCOMPLETE`: provider/corporate-action/common-history evidence
  is missing or unsupported.
- `ABSTAIN_IDENTITY_MISMATCH`: Phase 4 identity or implementation differs.
- `ABSTAIN_GOVERNANCE`: protected/holdout/live-trading boundary is violated.

`READY_FOR_PASS_REVIEW` is deliberately not an investment recommendation and
not an automatic Phase 6 authorization. The final Phase 5 PASS/FAIL review is a
separate checkpoint after the evidence exists. FINAL_HOLDOUT remains closed.
