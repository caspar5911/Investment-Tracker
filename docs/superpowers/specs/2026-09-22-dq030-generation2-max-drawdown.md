# DQ-030 Resolution for Generation 2

Date: 2026-09-22

Status: **RESOLVED PROSPECTIVELY FOR GENERATION 2**

Issue: `DQ-030 UNDEFINED_MAX_DRAWDOWN_CONVENTION`

Generation 1 evidence is not reinterpreted. Its previously UNKNOWN max-drawdown
and Calmar fields remain UNKNOWN.

## Frozen Generation-2 max-drawdown convention

Input series:

1. primary-friction (3 bps) scored-session close equity;
2. prepend the portfolio's exact initial cash as observation 0;
3. observations must be finite and strictly positive.

For equity observations `E_0 ... E_n`:

- running peak: `P_t = max(E_0 ... E_t)`
- drawdown fraction: `D_t = E_t / P_t - 1`
- maximum-drawdown magnitude:
  `MDD = max_t(0, -D_t)`

Therefore max drawdown is reported as a **non-negative loss magnitude** in
`[0, 1)` for a valid positive-equity replay.

Examples:

- no decline from any prior peak => MDD = 0.0
- peak 100 followed by trough 80 => MDD = 0.20

The calculation uses only close equity. Intraday high/low prices are not used
for portfolio max drawdown.

## Validation

Max drawdown is UNKNOWN if:

- equity series is empty;
- any equity is non-finite;
- any equity is <= 0;
- initial cash is missing/non-positive;
- replay/session identity is invalid.

No imputation or clipping is permitted.

## Calmar

Generation-2 Calmar is:

`CAGR / MDD`

only when:

- CAGR status is AVAILABLE;
- MDD status is AVAILABLE;
- MDD > 0.

If MDD == 0, Calmar is UNKNOWN with reason
`NONPOSITIVE_DENOMINATOR`.

If CAGR or MDD is UNKNOWN, Calmar is UNKNOWN and carries the applicable
upstream reason.

A negative CAGR with positive MDD produces a negative available Calmar value;
it is not clipped.

## Scope

This convention applies to Generation-2 TRAIN, VALIDATION, Phase 6, and Phase 7
evidence.

It may not be changed after the first Generation-2 campaign evaluation begins.
