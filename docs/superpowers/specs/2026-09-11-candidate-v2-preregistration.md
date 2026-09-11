# Investment Tracker Candidate v2 — Preregistration

## Status

**PREREGISTERED — awaiting genuinely unseen evidence.**

This document defines Candidate v2 before any Candidate-v2 qualification
evidence is collected. It does not relabel Candidate v1, repair Candidate-v1
Phase B, or authorize replacement-holdout access.

## Why v2 exists

Candidate v1 produced useful engineering evidence but cannot progress on the
same validation claim:

- `ROBUST-v1.0` remains INCONCLUSIVE because RB09 did not preregister a
  deterministic same-session cross-proxy tie treatment.
- Candidate-v1 strict Phase B was adverse.
- DQ-030 left max drawdown undefined for `CALC-v1.2`.
- DQ-046 exposed a multi-writer canonical-persistence risk.

All of those findings remain part of the permanent Candidate-v1 audit trail.

## Anti-tuning boundary

Candidate v2 **does not change REPLAY-v1.0 signal thresholds**.

The entry/state-machine definitions C01-C24 remain inherited unless this
document explicitly says otherwise. In particular, trend, pullback,
stabilization, relative strength, chase, signal precedence, episode dedupe,
t+1 execution, horizons, SPY comparison, cash hurdle, friction, baselines,
split normalization, listing-aware warm-up, and partition isolation are not
altered to improve historical returns.

Candidate-v1 Phase A and Phase B have already been seen. They may be cited as
legacy development/diagnostic evidence, but they are permanently ineligible to
be called genuinely unseen Candidate-v2 OOS evidence.

## Version set

- Candidate: `CANDIDATE-v2.0`
- Control plane: `TPC-v1.2`
- Signal rules: `REPLAY-v1.0` inherited unchanged
- Calculation rules: `CALC-v2.0`
- Robustness protocol: `ROBUST-v2.0`

## CALC-v2.0: C25 max drawdown

C25 is the only new calculation convention in this preregistration.

For an executable episode/horizon:

1. Start the mark-to-market path at the t+1 entry open with high-water value
   equal to the entry open.
2. For each trading session in the horizon, mark using the split-normalized
   usable close.
3. High-water is the maximum of entry open and every prior usable close.
4. Session drawdown is `close / high_water - 1`.
5. `max_drawdown` is the minimum session drawdown.
6. Friction is not embedded in max drawdown; friction remains represented in
   `return_net`.
7. MAE/MFE remain separate intraday range metrics.
8. Any missing/unusable close in the path makes max drawdown UNKNOWN.
9. C24-censored horizons have max drawdown UNKNOWN.

C25 resolves the *definition* gap represented by DQ-030 for CALC-v2.0 only.
Candidate-v1/CALC-v1.2 historical max_drawdown fields remain UNKNOWN and must
not be backfilled.

## ROBUST-v2.0: RB09 same-session rule

RB01-RB08 and RB10 criteria are inherited unchanged from ROBUST-v1.0.

RB09 is replaced prospectively with a deterministic dependence rule:

1. Use clean, matured 20-trading-day Candidate-v2 episode outcomes at 0 bps.
2. Group all proxy episodes with the exact same executable entry session into
   one same-session cluster.
3. The cluster representative is the equal-weight median 20-day excess return
   versus exact-timing SPY across the cluster's proxies.
4. Sort clusters chronologically.
5. Select the earliest eligible cluster, then exclude subsequent clusters until
   an entry at least 20 benchmark trading sessions later. Repeat.
6. Require at least 20 selected non-overlapping clusters; fewer is INCONCLUSIVE.
7. PASS requires the median representative 20-day SPY excess across selected
   clusters to be >= 0. A negative median is FAIL.

This removes the arbitrary asset-order tie choice that made RB09-v1
inconclusive. The threshold remains the original non-negative-median criterion;
it is not selected from Candidate-v1 Phase-B performance.

## Replacement holdout remains locked

The following historical symbols remain inaccessible:

- HACK
- SOXX
- NLR
- URNM
- GEV

Candidate v2 does not authorize provider requests, cache inspection,
summaries, inference, or derived statistics for those histories. They remain
locked unless future Independent Audit authorization occurs after the required
gates pass.

## Candidate-v2 eligible evidence

Candidate-v2 qualification evidence must be generated **after the canonical
preregistration timestamp** and must have been unavailable to the candidate
design at freeze time.

No Candidate-v1 Phase-A or Phase-B result may be reused as unseen Candidate-v2
OOS evidence.

Prospective paper decisions must be recorded before outcomes and must never be
backfilled.

## Promotion logic

Candidate v2 does not inherit Candidate-v1 PASS claims automatically.

To remove the current 74-point robustness cap, Candidate v2 must first produce
genuinely eligible evidence satisfying the frozen ROBUST-v2.0 criteria.

To remove the 79-point Phase-B cap, it must then pass a separately declared,
genuinely unseen OOS validation partition under the already-frozen candidate.

Operational blockers such as RECON-009 and DQ-046 must also be resolved through
runtime evidence. Code or documentation alone does not close those controls.

## Governance principle

Negative results remain evidence. Candidate versions may improve methodology,
but no version may rewrite or hide a prior adverse result to manufacture a
higher readiness score.


## Frozen unseen cross-sectional validation panel

Before any historical price request for these symbols, Candidate v2 fixes the
following validation panel:

| Symbol | Role |
| --- | --- |
| XLI | broad U.S. industrials |
| XLU | utilities |
| XLB | materials |
| XME | metals and mining |
| XOP | oil and gas exploration/production |
| IGV | software |
| XSD | semiconductors |
| IYT | transportation |

The benchmark is SPY.

Only current asset-identity metadata was checked before this panel was frozen.
No historical bars for these eight panel symbols were inspected before
preregistration.

The panel cannot be substituted after historical access begins. Provider
failure, insufficient history, or a new data-quality problem becomes
UNKNOWN/ABSTAIN for the affected evidence; it does not permit replacing a weak
symbol with a more favorable one.

### Fixed validation windows

- Warm-up only: 2017-01-01 through 2017-12-31.
- Candidate-v2 Phase A: 2018-01-01 through 2023-12-31.
- Candidate-v2 strict Phase B: 2024-01-01 through 2025-09-07.
- Benchmark: exact-session SPY.
- C24 partition isolation remains mandatory.

Candidate-v2 Phase-B history must not be fetched until Candidate-v2 Phase A and
ROBUST-v2.0 have been computed and the candidate remains frozen without rule
changes. A failed Phase-A or robustness result is recorded as failure; it does
not authorize tuning and retrying under the same candidate identifier.

## PHASEB-v2.0 acceptance criteria

The following criteria are frozen before any panel history is inspected.

A Candidate-v2 Phase-B PASS requires all of the following:

1. At least 20 clean matured 20-trading-day REPLAY episodes overall.
2. Median 20-day excess return versus exact-timing SPY is strictly greater than
   zero.
3. Median 20-day excess return versus the matched 3.25% cash hurdle is strictly
   greater than zero.
4. Median 60-day excess return versus SPY is non-negative.
5. At least four panel proxies have at least three matured 20-day episodes.
6. A strict majority of adequately sampled proxies have non-negative median
   20-day SPY excess.
7. At 25 bps total round-trip friction, median 20-day net return is strictly
   greater than the median matched cash hurdle.
8. REPLAY median 20-day SPY excess is at least the frozen Simple-Dip median
   20-day SPY excess.

Insufficient sample produces INCONCLUSIVE. Once the minimum sample exists,
failure of any performance criterion produces FAIL. No failed criterion may be
redefined after seeing results under the same candidate.

## Score consequence

The present 74-point cap is not removed by this preregistration itself.

- ROBUST-v2.0 must first PASS on genuinely eligible Candidate-v2 evidence before
  the robustness cap can be removed.
- PHASEB-v2.0 must then PASS on still-unseen Phase-B panel history before the
  Phase-B cap can be removed.
- DQ-046 and RECON-009 require runtime operational proof independently of model
  efficacy.

The scoring weights and caps are not changed to target 80.
