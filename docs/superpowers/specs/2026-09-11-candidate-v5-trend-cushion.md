# Candidate v5 — Trend Cushion

## Status

PREREGISTERED BEFORE V5 PANEL PRICE-HISTORY ACCESS.

## Single hypothesis

Candidate v5 tests whether pullback entries are more reliable when the asset is
not merely above SMA200, but remains at least 5% above it.

Frozen ACCUMULATE addition:

`asset_close >= 1.05 * asset_sma200`

Everything else from Candidate-v3 REPLAY-v2.0 remains unchanged, including
SPY>SMA200, 5%-15% prior-60-high pullback, stabilization, non-negative 20-day
relative strength versus SPY, chase prevention, t+1 execution, horizons,
friction, baselines and C24/C25.

No grid search and no repeated Candidate-v5 variants are authorized.

## Research provenance

The hypothesis came from already-seen v2/v3 development histories. Those
results are research only and can never be counted as unseen Candidate-v5
qualification evidence.

## Frozen validation panel

DIA, IJR, VTI, IWF, IWD, QUAL, MTUM, USMV.

Benchmark: SPY.
Warm-up: 2017.
Phase A: 2018-01-01..2023-12-31.
Strict Phase B: 2024-01-01..2025-09-07.

Only current identity/status metadata was inspected before this freeze. No v5
panel price history may be accessed until the implementation is merged, CI is
green and the canonical preregistration row is written/read back.

Panel substitution after historical access is forbidden.

## Robustness and stop rule

ROBUST-v2.0 RB01-RB10 governs Phase A. Failure or inconclusive robustness stops
Candidate v5 and leaves Phase B untouched.

Only a robustness PASS authorizes one strict Candidate-v5 Phase-B evaluation.

## Locked replacement holdout

HACK, SOXX, NLR, URNM and GEV remain inaccessible.

## Scoring

Code, CI and preregistration earn no score increase. The 74 cap can be removed
only after Candidate-v5 robustness PASS. A subsequent strict OOS PASS is
required before a score at or above 80 can be considered.
