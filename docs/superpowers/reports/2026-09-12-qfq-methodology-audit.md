# QFQ Price Methodology Audit

## Decision

The current methodology is versioned as `QFQ-NORMALIZED-RESEARCH-v1` and is
explicitly `decision_grade=false`. It may be used only for normalized,
percentage-based research simulation. It does not establish that adjusted
prices were historically executable fills.

## Current data flow

Moomoo daily history is requested with `AuType.QFQ`. The official local API
reference defines QFQ as forward adjustment and identifies US `time_key`
values as US Eastern market time. The adapter preserves the returned OHLCV
values and converts the Eastern market date to a UTC session label; it does
not reconstruct unadjusted prices or corporate-action events.

### A. Signal calculations

All current indicators receive QFQ bars:

- trend and momentum use adjusted close;
- ATR uses adjusted high, low and close;
- realized volatility uses adjusted close returns.

This provides a continuous normalized series for signal calculations across
splits and distributions.

### B. Simulated execution and accounting

The current workflow passes the same QFQ frame to `run_backtest`. A signal
formed on one completed QFQ bar executes at the next QFQ open. Position
quantity, mark-to-market value, slippage and commission are therefore computed
in adjusted-price units. With fractional percentage sizing and proportional
costs, a uniform rescaling of all OHLC prices leaves the simulated equity curve
unchanged; the regression suite verifies this property.

That scale invariance validates internal normalized-simulation consistency
only. It does not mean the QFQ open was an observable historical execution
price, and the resulting share quantities are not historical quantities.

## Corporate actions and limitations

The engine does not currently ingest an explicit distribution, split or other
corporate-action ledger. QFQ transformations may incorporate those events into
the price series, but the simulator does not separately book dividend cash,
withholding, reinvestment, split quantities or event-date rounding. Absolute
cash flows, share counts and fills must therefore not be interpreted as
historical execution records.

## Required successor

Decision-grade reruns require a separately versioned methodology named
`UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS`. It must:

1. retain adjusted prices for signal continuity where appropriate;
2. use aligned actual/unadjusted bars for execution and marking;
3. ingest and validate explicit splits and distributions;
4. specify dividend cash, tax, reinvestment and fractional-share policy;
5. include all signal, execution and corporate-action dataset identities in
   the candidate manifest;
6. receive fixture-based accounting tests before any provider-backed rerun.

No unadjusted history is downloaded and no dual-price engine is introduced in
this phase.

## Effect on existing experiments

All existing experiment artifacts remain immutable. Their reported results
used QFQ prices for both signals and normalized execution. They require rerun
under corrected optimizer semantics for research comparison, and require a
future unadjusted-price plus corporate-action methodology before they can be
treated as decision-grade evidence. Neither rerun occurs in this phase.
