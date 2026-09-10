# SMH Phase-A worker preflight

Computation stopped before provider dispatch and before any canonical write because the coordinator-issued immutable snapshot is unavailable. Replay Daily, episodes, outcomes, and C17/C18/C19 baselines were not fabricated.

## Exact remaining input

- coordinator-issued immutable SMH Phase-A snapshot containing canonical active SMH and SPY bars, Phase Matrix and DQ lineage, passing frozen Calculation Tests status, authorized scope, evidence refs, dispatch timestamp, and complete material input digests.

The worker will use frozen versions only, inclusive `SMA200[t] = mean(close[t-199] ... close[t])`, t+1-open execution, C24 censoring, exact-date SPY alignment, 3.25% calendar-day cash hurdle, 0/10/25 bps friction, and range-quarantine propagation. It will emit only `READY_FOR_COORDINATOR_REVIEW`; canonical writes remain coordinator-only.

No locked replacement-holdout data was requested, inspected, inferred, or used.
