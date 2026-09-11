# Candidate v2 Protocol Preregistration

## Status

Protocol hardening preregistered; signal candidate not yet frozen.

This document was created after Candidate v1 Phase B was observed. It therefore does not convert any previously seen data into out-of-sample evidence and does not increase the governed readiness score by itself.

Candidate v1 remains preserved as-is. Its Phase-B result was adverse and ROBUST-v1.0 remains inconclusive because RB09 did not preregister same-session cross-proxy tie handling.

## Governance boundary

For Candidate v2, all Candidate-v1 historical evidence through the frozen Phase-B end 2025-09-07 is now SEEN DEVELOPMENT EVIDENCE. It may be used to understand failure modes, but it may not be represented as new validation or holdout evidence for v2.

The replacement holdout symbols remain inaccessible:

- HACK
- SOXX
- NLR
- URNM
- GEV

No v2 work may fetch, inspect, cache, summarize, infer, or use their historical data unless a future Independent Audit explicitly authorizes release under a valid preregistered candidate.

No Phase-A or Phase-B v1 row may be deleted, rewritten, or re-labelled to improve Candidate v1.

## Development screen completed before this preregistration

A small structural screen was run only on already-seen Phase-B evidence to test whether an obvious repair justified further work. These results are development-only.

| Development variant | Unique episodes | 20d median excess vs SPY | 60d median excess vs SPY | Decision |
| --- | ---: | ---: | ---: | --- |
| Candidate v1 | 119 | -0.802% | -3.227% | Reference; adverse |
| Relative strength tightened to SPY | 57 | -1.424% | -4.798% | Reject |
| SPY > SMA200 market gate | 112 | -1.424% | -3.693% | Reject |
| Tight RS + market gate | 52 | -2.315% | -5.678% | Reject |
| v1 AND frozen 10% Simple-Dip condition | 34 | -0.226% | +0.672% | Reject: weak 20d and poor breadth |
| Frozen Simple-Dip baseline | 82 starts / 72 matured 20d | +0.902% | -1.001% | Retain as benchmark only |

A follow-up confirmation experiment was also rejected after correcting repeated firing within one underlying dip episode. The initially attractive result depended on multiple confirmations inside the same dip and therefore inflated effective sample count.

The screen did not identify a defensible signal-rule repair. Further threshold search on the same data is prohibited for this iteration because it would increase overfitting risk.

## V2-PROTOCOL-v0.1

This preregistration fixes two protocol ambiguities independently of signal-return optimization.

### C25 - deterministic maximum drawdown

For future v2 episodes:

1. execution remains t+1 open;
2. initialize episode equity to 1.0 at the entry open;
3. for each eligible in-partition trading session, set equity to session_close / entry_open;
4. maintain the running maximum of that equity path;
5. per-session drawdown is equity / running_peak - 1;
6. max_drawdown is the minimum per-session drawdown over the horizon;
7. the value is therefore zero or negative;
8. intraday highs/lows are not used;
9. transaction friction is not embedded in this drawdown metric; friction remains reported separately in return_net;
10. if the horizon is censored or required closes are unusable, max drawdown is UNKNOWN.

This convention is chosen for determinism and separation from range-quarantine issues. It is not selected because it improves historical results.

Candidate-v1 max_drawdown fields remain UNKNOWN under DQ-030; no retrospective backfill is permitted.

### RB09-v2 - deterministic same-session dependence handling

For the future robustness protocol:

1. map every eligible episode entry to its exact benchmark trading-session index;
2. when multiple proxies enter on the same benchmark session, combine ALL of them into one equal-weight cross-proxy basket observation;
3. do not pick a proxy by alphabetic order, historical return, score, or any other tie-break;
4. sort basket observations only by benchmark session index;
5. select the earliest basket, then the next basket whose entry-session index is at least 20 sessions after the prior selected basket;
6. continue until exhausted;
7. calculate the frozen RB09 statistic on these non-overlapping session baskets.

This removes the ambiguity discovered in ROBUST-v1.0 without choosing a favorable asset from a tie.

## Candidate-v2 signal rule

NOT FROZEN YET.

The development screen did not justify a threshold tweak or a simple extension of Candidate v1. Candidate v2 should not be created merely to make the already-seen Phase B look better.

Before a signal rule can be frozen, the design must have:

- a concise economic/market rationale independent of the observed Phase-B winners;
- no asset whitelist selected from historical performance;
- no use of the locked replacement holdout;
- a bounded number of parameters;
- explicit state precedence and abstention behavior;
- a frozen benchmark and friction treatment;
- minimum episode-breadth requirements;
- a preregistered acceptance test on genuinely new evidence.

## Future validation

A future v2 freeze must happen BEFORE its validation evidence is observed.

Eligible validation sources are:

1. genuine prospective paper episodes recorded after the v2 freeze; or
2. another clean panel explicitly selected and authorized by Independent Audit before its history is inspected.

Candidate-v1 Phase A/B cannot serve as v2 OOS evidence because it is already seen.

The locked replacement holdout cannot be used as a shortcut around a failed Candidate v1 and remains locked.

## Score consequence

This protocol work improves specification quality but earns no automatic readiness points. The non-official governed score remains capped by the failed/inconclusive Candidate-v1 validation state until a future candidate earns fresh supportive evidence.

## Acceptance principle

A v2 candidate is worth freezing only if its rationale can be stated before looking at its validation result. If a proposed rule exists mainly because it makes the known Phase-B sample look better, it is not a defensible candidate.
