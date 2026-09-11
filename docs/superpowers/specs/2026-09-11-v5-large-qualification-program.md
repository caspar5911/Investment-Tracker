# Candidate v5 — Large Qualification Program (V5-LARGE-Q1)

## Purpose

This is one authorized enlargement of Candidate v5's qualification evidence.
It does **not** create Candidate v6 and does **not** alter Candidate-v5 rules.

The purpose is to determine whether the existing REPLAY-v2.1 hypothesis can
produce at least 20 genuinely independent opportunities across multiple market
regimes under BACKTEST-v1.0.

## Freeze boundary

This specification, code and panel identity checks are completed before any
historical price bars are requested for V5-LARGE-Q1.

Only current asset identity/status metadata was checked before freeze.

## Candidate rules

Unchanged from Candidate v5:

- Candidate: CANDIDATE-v5.0
- Signal: REPLAY-v2.1
- Calculation: CALC-v2.0
- Qualification evaluator: BACKTEST-v1.0
- Asset close must be at least 5% above its SMA200 for ACCUMULATE, in addition
  to the previously frozen Candidate-v3 market-regime, pullback,
  stabilization, relative-strength and chase rules.

No threshold search, cooldown change, panel substitution or new signal rule is
authorized.

## Qualification dataset

Dataset id: **V5-LARGE-Q1**

Benchmark: **SPY**

Frozen panel:

- IVV
- IWB
- IWS
- IWP
- IWN
- IWO
- EPP
- EWJ
- EWU
- EWG
- EWC
- EWA
- EWZ
- EWW
- EWH
- EWS

The panel is disjoint from all Candidate v1-v5 development/qualification
panels and from the locked replacement holdout.

## Temporal separation

Research boundary: **2007-12-31**

Fold 1: **2008-02-01 through 2011-12-30**

Fold 2: **2012-01-03 through 2014-12-31**

Fold 3: **2015-01-02 through 2017-12-29**

The first fold starts after the BACKTEST-v1.0 20-session embargo. These years
are also separated from the 2018-2023 data used for Candidate-v5 development.

## PASS requirements

BACKTEST-v1.0 controls are binding and may not be relaxed after seeing results:

- at least 20 non-overlapping independent observations overall;
- at least 5 independent observations in each of 3 folds;
- median 25-bps net excess return > 0 versus both SPY and cash;
- at least 2/3 folds positive versus SPY;
- no calendar year or single asset > 50% concentration;
- at least 4 adequately sampled assets and a strict majority non-negative;
- strategy median must be at least the frozen Simple-Dip baseline median;
- exact one-sided sign-test p <= 0.10 with >=20 non-zero trials;
- 50-bps stress median remains positive versus SPY and cash;
- complete 0/10/25-bps friction scenarios;
- exact t+1 execution and exact 20-session outcome timing;
- Candidate-v2+ max-drawdown evidence complete.

Any observed hard failure => FAIL.
Insufficient/missing evidence with no hard failure => INCONCLUSIVE.

## Stop rule

V5-LARGE-Q1 is evaluated once after canonical preregistration.

If it fails or is inconclusive, its rules, panel, dates and thresholds are not
changed and rerun as if they were the same qualification attempt. A new
historical panel search is not automatically authorized.

## Locked holdout

HACK, SOXX, NLR, URNM and GEV remain inaccessible. No fetch, cache lookup,
derived statistic, summary or inference involving their historical data is
authorized.

## Score rule

Preregistration, implementation and CI do not raise the readiness score.
Only a genuine BACKTEST-v1.0 PASS can remove the current robustness cap.
