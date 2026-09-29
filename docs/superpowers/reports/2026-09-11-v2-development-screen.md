# Candidate v2 Development Screen - 2026-09-11

## Purpose

Document exploratory work performed on already-seen Candidate-v1 Phase-B evidence after the adverse OOS result. This report is research evidence only. It must never be cited as clean v2 validation.

## Baseline

Candidate v1 produced 119 unique ACCUMULATE episodes in Phase B.

- matured 20-day observations: 114
- median 20-day excess vs SPY: -0.802%
- matured 60-day observations: 110
- median 60-day excess vs SPY: -3.227%

The frozen C19 Simple-Dip baseline produced:

- 72 matured 20-day observations, median excess vs SPY +0.902%
- 71 matured 60-day observations, median excess vs SPY -1.001%

## Structural variants tested

Only existing concepts were recombined; no locked-holdout data was accessed.

1. Tighten the v1 relative-strength gate from asset_ret20 >= SPY_ret20 - 5% to asset_ret20 >= SPY_ret20.
2. Add a broad market gate requiring SPY above its 200-day SMA.
3. Combine 1 and 2.
4. Require v1 ACCUMULATE and the pre-existing C19 10% Simple-Dip condition.
5. Explore a 10% dip with stabilization using existing v1 components.

None produced a sufficiently broad and convincing improvement after semantic episode deduplication.

The most important negative finding was the stabilization experiment: a naive implementation looked materially stronger only because it allowed repeated re-entry confirmations inside one continuous dip. After enforcing one confirmation per underlying dip episode, its 20-day median result became negative. The attractive result was therefore rejected as sample inflation rather than promoted.

## Decision

Do not continue threshold search on Candidate-v1 Phase A/B.

Use Candidate-v1 Phase A/B only as development/failure-analysis evidence from this point forward. Keep C19 Simple-Dip as a benchmark, not as an automatically promoted replacement candidate.

Proceed with protocol hardening first:

- deterministic max-drawdown convention for future v2 episodes;
- deterministic equal-weight RB09 same-session basket rule;
- single-writer canonical evidence controls;
- explicit fresh-validation requirement before v2 promotion.

## Holdout statement

No historical data for HACK, SOXX, NLR, URNM, or GEV was accessed for this development screen.
