# Candidate v3 — Market-confirmed relative-strength preregistration

## Status

PREREGISTERED DESIGN. No historical price bars for the Candidate-v3 validation
panel may be accessed before this specification is merged and canonically
stamped.

## Reason for a new candidate

Candidate v1 had adverse Phase B. Candidate v2 preserved REPLAY-v1.0 thresholds
and failed a newly preregistered cross-sectional robustness test at RB05 and
RB09. Those results remain permanent evidence.

Candidate v3 is not an attempt to search many thresholds until one passes. It
tests one market-structure hypothesis selected before the new panel is observed.

## Single hypothesis

A pullback/stabilization signal should be accepted as ACCUMULATE only when:

1. the asset remains above its own SMA200;
2. SPY is strictly above its SMA200 on the same completed signal date; and
3. the asset's 20-trading-day return is at least SPY's 20-trading-day return.

The second condition is a new market-regime gate. The third replaces the
REPLAY-v1.0 relative-strength tolerance of asset minus SPY >= -5% with the
natural zero threshold asset minus SPY >= 0.

No other REPLAY-v1.0 threshold changes.

## REPLAY-v2.0 precedence

Missing required asset or SPY inputs => ABSTAIN.

Otherwise:

- TRIM/AVOID if the asset trend fails and asset 20d return < -10%.
- WAIT if asset trend fails, SPY regime gate fails, or chase gate fails.
- WATCH if pullback, stabilization, or zero-threshold relative-strength gate
  fails.
- ACCUMULATE only when all required gates pass.

The 5%-15% pullback band, stabilization definition, 8% chase rule, episode
dedupe, t+1 execution and all other inherited conventions remain unchanged.

## No parameter search

No grid search, optimizer, alternate RS threshold, alternate market moving
average, or symbol substitution is authorized under Candidate-v3. If the
single preregistered candidate fails, that result is preserved and the
candidate stops.

## Frozen validation panel

Before historical access, the panel is fixed to:

- XLV — healthcare
- XLP — consumer staples
- XLY — consumer discretionary
- XLF — financials
- XLRE — real estate
- XBI — biotechnology
- XRT — retail
- ITB — home construction

Benchmark: SPY.

Only current asset identity metadata was checked before panel freeze. No
historical price bars for these eight symbols were inspected when this
specification was written.

Panel substitution after any historical access is prohibited.

## Frozen windows

- warm-up: 2017-01-01 through 2017-12-31
- Candidate-v3 Phase A: 2018-01-01 through 2023-12-31
- Candidate-v3 strict Phase B: 2024-01-01 through 2025-09-07

Phase B must not be fetched unless Phase A and ROBUST-v2.0 pass. C24 partition
isolation applies.

## Calculation and robustness

Candidate v3 uses CALC-v2.0 including C25 close-marked max drawdown.

ROBUST-v2.0 RB01-RB10 apply unchanged, including deterministic RB09
same-session median clusters.

## Strict Phase-B criteria

PHASEB-v2.0 is frozen before panel history:

- >=20 clean matured 20d episodes;
- median 20d excess vs SPY >0;
- median 20d excess vs matched 3.25% cash >0;
- median 60d excess vs SPY >=0;
- >=4 proxies with >=3 matured 20d episodes;
- strict majority of adequately sampled proxies have non-negative median 20d
  SPY excess;
- median 25bps net 20d return > median matched cash hurdle;
- REPLAY median 20d SPY excess >= Simple-Dip median.

Insufficient sample => INCONCLUSIVE. A failed criterion => FAIL.

## Evidence isolation

Candidate-v1 and Candidate-v2 historical results are development context only.
They cannot be relabelled as unseen Candidate-v3 evidence.

HACK, SOXX, NLR, URNM and GEV remain locked and inaccessible.

## Score rule

No score increase occurs for this specification, code, or a favorable Phase-A
backtest alone. The current governed score/cap changes only when the frozen
robustness and downstream OOS gates genuinely pass and canonical evidence is
landed.
