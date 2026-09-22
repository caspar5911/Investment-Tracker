# Phase 6 Replacement Selection Attempt 1 — Invalidated

Date: 2026-09-21

Authority: **INDEPENDENT_AUDIT**

## Status

`PHASE6_REPLACEMENT_SELECTION_INVALIDATED`

This invalidation does **not** mark the replacement holdout as consumed.

## Reason

The first execution of the preregistered blind replacement selector returned:

- BBCA
- IHD
- GDMA
- BGRN
- FQAL

The emitted selection artifact showed:

- BBCA listing_date = `1970-01-01`
- IHD listing_date = `1970-01-01`
- GDMA listing_date = `1970-01-01`
- BGRN listing_date = `1970-01-01`
- FQAL listing_date = `2016-09-15`

The preregistered protocol states that a missing, malformed, or ambiguous
listing date makes a symbol ineligible. The Unix-epoch value
`1970-01-01` is therefore treated fail-closed as an ambiguous sentinel rather
than as trustworthy listing evidence.

The implementation had accepted that sentinel as an ordinary ISO date. That was
a conformity defect in the selector, not a change in the preregistered
selection rule.

## Safety

The failed selection attempt used only:

`get_stock_basicinfo(Market.US, SecurityType.ETF)`

plus local OpenD log scanning.

No replacement-symbol historical market data was requested by the selector.

No strategy evaluation was executed.

No holdout release envelope was issued.

No encrypted holdout bundle was created.

No Phase 6 consumption marker was written.

Therefore the replacement selection procedure may be rerun after the
implementation is corrected to enforce the already-frozen ambiguous-date rule.

## Corrective action

The selector now:

1. rejects exactly `1970-01-01` as an ambiguous listing-date sentinel; and
2. detects both `US.<ticker>` and exact bare candidate ticker tokens within
   explicit `Qot_RequestHistoryKL` context.

The frozen seed, strategy, evaluation window, ranking algorithm, and all other
selection rules remain unchanged.
