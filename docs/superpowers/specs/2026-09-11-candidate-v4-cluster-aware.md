# Candidate v4 — Cluster-Aware Relative Opportunity

## Status

PREREGISTERED BEFORE V4 PANEL HISTORICAL ACCESS.

## Research question

Candidate v3 passed nine of ten robustness checks but failed dependence
sensitivity. The v4 hypothesis addresses that structural weakness directly:
overlapping cross-asset ACCUMULATE signals are competing allocations of the
same finite capital, not automatically independent opportunities.

This is one theory-driven hypothesis. No threshold grid search, panel search
after history access, or repeated v4 variants are authorized.

## Frozen versions

- Candidate: CANDIDATE-v4.0
- Signal: REPLAY-v3.0
- Calculation: CALC-v2.0
- Robustness: ROBUST-v2.0
- Phase B acceptance: PHASEB-v3.0
- Control plane: TPC-v1.2

## Inherited per-asset signal

REPLAY-v3.0 inherits REPLAY-v2.0 unchanged:

- asset close > asset SMA200;
- SPY close > SPY SMA200;
- pullback remains 5%-15% below prior-60 normalized close high;
- close > prior close and close >= SMA5;
- asset 20d return >= SPY 20d return;
- existing chase prevention and state precedence remain unchanged.

No per-asset return/pullback/trend threshold is changed from Candidate v3.

## New portfolio selector

For each completed signal session:

1. Find all clean assets whose inherited REPLAY-v2.0 state is ACCUMULATE.
2. If more than one qualifies on the same date, select the asset with greatest
   `asset_ret20 - SPY_ret20`.
3. Exact score ties use lexical ticker order.
4. Once an opportunity is selected, no additional global opportunity may be
   selected for 20 benchmark trading sessions.
5. The next candidate is considered only when the cooldown has expired.
6. Future candidate strength is never inspected when making today's choice.

The 20-session cooldown is not optimized: it matches the preregistered primary
20-day efficacy/dependence horizon.

## Fixed validation panel

Frozen before price-history access:

QQQ, IWM, MDY, EFA, EEM, VNQ, RSP, IJH

Benchmark: SPY.

Identity/status checks only were performed before this freeze. Historical bars
for this v4 panel are prohibited until the canonical v4 preregistration record
exists.

Warm-up: 2017.
Phase A: 2018-01-01 through 2023-12-31.
Strict Phase B: 2024-01-01 through 2025-09-07.

No panel substitution is allowed after the first v4 historical request.

## Robustness gate

ROBUST-v2.0 RB01-RB10 remain the gate. Because selected entries are already
globally separated by 20 benchmark sessions, RB09 must operate on the selected
entry stream and still requires at least 20 observations and median 20d SPY
excess >=0.

A robustness failure stops v4. Phase B must remain unaccessed.

## Phase-B gate

Only if robustness passes may the frozen v4 Phase B be accessed once.

PHASEB-v3.0 requires:

- >=20 matured 20d selected opportunities;
- >=4 panel assets with >=2 matured 20d selected opportunities;
- median 20d excess vs SPY >0;
- median 20d excess vs cash >0;
- median 60d excess vs SPY >=0;
- strict majority of adequately sampled assets with non-negative median 20d
  SPY excess;
- median 25bps net return > matched median cash hurdle;
- median 20d SPY excess >= simple-dip median 20d SPY excess.

Any failed criterion is a failed Phase B. No threshold/panel repair is allowed
after seeing v4 results.

## Holdout protection

HACK, SOXX, NLR, URNM and GEV remain inaccessible. Candidate v4 does not
authorize any fetch, cache inspection, summary, inference, or derived statistic
for them.

## Score rule

No score increase is earned by this specification, code, CI, or preregistration.
The 74 robustness cap can be removed only by a genuine Candidate-v4 robustness
PASS. The 79 Phase-B cap can be removed only by a subsequent strict OOS PASS.
