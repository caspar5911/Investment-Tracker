# BACKTEST-v1.0 — Governed Backtesting Framework

## Purpose

BACKTEST-v1.0 makes historical validation harder to game. It is not a strategy
change and does not increase the readiness score by itself.

It consumes frozen candidate outputs. It does **not** fetch data, tune rules,
choose a winning panel, or execute trades.

## Qualification boundary

A qualification run must have a preregistered record containing:

- candidate id and exact strategy/calculation/robustness versions;
- fixed qualification dataset id;
- fixed asset panel and benchmark;
- research end date;
- at least three chronological validation folds;
- preregistration timestamp;
- first qualification-history access timestamp;
- deterministic protocol digest.

History access before preregistration is rejected.

A dataset previously used for research or a different candidate/protocol cannot
be relabelled as untouched qualification evidence. Recomputing the exact same
frozen protocol is allowed.

## Leakage controls

For every clean primary episode the framework verifies against the benchmark
trading calendar:

- signal is inside its declared validation fold;
- entry is exactly the next benchmark trading session;
- the 20-session horizon close is the exact required session;
- signal, entry and outcome all remain inside the validation fold;
- the first validation fold starts only after a 20-session research embargo.

Any timing/look-ahead violation blocks evaluation.

## Evidence completeness

For every primary episode all three frozen friction scenarios must exist:

- 0 bps
- 10 bps
- 25 bps

Scenario-invariant fields must agree. Candidate-v2+ max drawdown must be
available for every clean primary observation. Missing evidence is
INCONCLUSIVE, not silently dropped.

## Dependence control

Primary qualification statistics use the 25-bps scenario.

Same-entry-session episodes are first collapsed to one median cross-asset
cluster. The framework then greedily takes chronological clusters at least 20
benchmark sessions apart.

PASS requires:

- at least 20 independent clusters overall;
- at least 5 independent clusters in every validation fold.

This prevents hundreds of overlapping signals from masquerading as hundreds of
independent observations.

## Performance hard gates

The independent stream must satisfy all of the following:

1. median 25-bps net excess return versus SPY > 0;
2. median 25-bps net excess return versus cash > 0;
3. at least two thirds of validation folds have positive median 25-bps excess
   versus SPY;
4. no calendar year contributes more than 50% of clean primary episodes;
5. no single asset contributes more than 50% of clean primary episodes;
6. at least four assets have at least three observations each, and a strict
   majority of adequately sampled assets have non-negative median 25-bps excess
   versus SPY;
7. strategy median excess versus SPY is at least the frozen Simple-Dip
   baseline median;
8. one-sided exact sign-test p-value on independent SPY-excess observations is
   <= 0.10 with at least 20 non-zero trials;
9. a harsher 50-bps stress-friction median remains positive versus both SPY
   and cash.

The report also includes a deterministic 90% bootstrap interval for the
independent median and max-drawdown diagnostics. These are disclosed even when
they are not separate pass/fail thresholds.

## Status semantics

- **PASS**: every hard gate is satisfied and no required evidence is missing.
- **FAIL**: sufficient evidence exists and one or more observed hard gates are
  adverse.
- **INCONCLUSIVE**: evidence is insufficient/incomplete and no observed hard
  failure exists.

If both adverse evidence and missing evidence exist, FAIL wins; missing data
cannot hide a known failure.

## Holdout governance

HACK, SOXX, NLR, URNM and GEV remain inaccessible. BACKTEST-v1.0 calls the
existing holdout guard on every protocol symbol and observation.

Candidate v1-v5 historical results are not rewritten by this framework.
Existing untouched Phase-B partitions remain untouched unless a separately
frozen candidate has first passed its prerequisite gates.

## Readiness scoring

Landing BACKTEST-v1.0 is an engineering/control improvement only.

It does not remove the current robustness cap and does not award an 80 score.
A future candidate must actually PASS this framework on genuinely untouched
qualification evidence, then survive its separately frozen OOS test.
