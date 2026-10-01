# Generation-4 Phase-7 first checkpoint preregistration

Status: **PREREGISTERED, NON-AUTHORIZING; EXECUTION BLOCKED**

Machine-readable contract:
`data/governance/successor/generation4-phase7-first-checkpoint-contract.json`.
This document and contract were prepared before the 63-session prospective
result existed. They do not authorize evaluation, change the frozen candidate,
or amend the existing Independent-Audit evaluation authorization.

## Already frozen

- The candidate is `G2-A|lookback=189|skip=21|top_k=1|rebalance=21`.
  The ordered universe is GLD, IEF, IWM, QQQ, SPY, TLT, VNQ, XLP; the five
  Generation-4 final-holdout symbols remain forbidden.
- The first scored XNYS session is 2026-09-28. Exactly 210 prior XNYS sessions
  start at 2025-11-24 and end at 2026-09-25. They initialize causal signals
  and portfolio state, and are excluded from scored return calculations.
- Checkpoints are 63, 126, and 252 scored sessions. The 63-session label is
  `EARLY_DIAGNOSTIC`; it is descriptive. The 252-session checkpoint is the
  first possible terminal Phase-7 assessment. At 63, the primary status
  remains `PHASE7_PROSPECTIVE_EVIDENCE_PENDING` even if calculations succeed.
- QFQ bars supply signals. Unadjusted open/close bars and explicit split and
  dividend events supply executions and P&L. Decisions fill at the next
  session's unadjusted open. A sell or buy fee is absolute notional times the
  applicable bps divided by 10,000; cash constrains buys. Split share counts,
  ex-date receivables, and pay-date cash credits follow the frozen ledger.
- Five strategy replays use 0, 3, 10, 25, and 50 bps. The primary comparison
  uses 3 bps, initial cash 100,000, a corporate-action-aware SPY buy-and-hold
  replay at 3 bps, and zero-return cash. Benchmark excess is strategy total
  return minus SPY total return; cash excess is strategy total return.
- The current prospective reporter exposes scored total return for all five
  cases, SPY total return, excess versus SPY and cash, an exposure-invariant
  boolean, and calendar-subperiod fields. Its `scored_total_return` uses the
  first scored session's close equity as its denominator; the first close is
  an observation, while the reported return spans the following 62
  close-to-close intervals at this checkpoint. This basis must be explicitly
  reviewed by Independent Audit before any result is interpreted.
- DQ-030 is `UNRESOLVED` in the Generation-4 contract. Max drawdown, Calmar,
  and recovery remain `UNKNOWN` with reason `DQ-030_UNRESOLVED`. The separate
  Generation-2 resolution does not amend the hash-bound Generation-4 contract.
- RECON-009 is `OPEN`. It is a runtime operational-proof gate requiring alert
  delivery, acknowledgement, failed-delivery retry/escalation, interrupted
  write recovery, and post-write readback. It blocks production readiness,
  not paper-only descriptive calculation by itself. Phase-7 completion does
  not close it.

## Newly preregistered 63-session boundary

The 62nd scored session is 2026-12-23; the 63rd is 2026-12-24; the 64th is
2026-12-28 on XNYS. A 62-session snapshot can yield structural progress only.
At 63, the collector may report `PHASE7_CHECKPOINT_READY` but must not call
an evaluator. The first checkpoint selects **only** a verified, complete
snapshot whose `requested_start` is 2025-11-24, `scored_start` is 2026-09-28,
`requested_end` is 2026-12-24, `warmup_session_count` is 210, and
`scored_session_count` is exactly 63. It contains 273 XNYS sessions per bar
file. A 64+ snapshot is never substituted or truncated for this checkpoint.
If the exact-63 snapshot is missing, the first checkpoint remains
`UNKNOWN/ABSTAIN`; later data cannot change its evidence boundary.

Before any calculation, Independent Audit must verify the current branch,
frozen commit and source hashes, evaluation request/contract/start/entry and
authorization hashes, exact candidate/universe/benchmark/frictions, and all
paper-only prohibitions. It must apply the existing collector snapshot
verifier to **every** local prospective snapshot and reject a corrupt,
duplicate, extra-file, misaligned, or conflicting snapshot. The chosen
snapshot's canonical manifest hash, file hashes and byte sizes, XNYS sessions,
OHLC, QFQ/unadjusted/corporate-action files, and no-holdout/no-performance
flags must pass. The previously recorded first-snapshot hash must still match.
The current snapshot format has no predecessor hash; future append-only claims
need comparison with previously recorded identities, not inference from a
self-consistent manifest alone.

Only an additional explicit Independent-Audit checkpoint decision may release
the exact-63 evidence to an evaluated calculation. That decision must bind
this preregistration, the exact selected snapshot, frozen implementation,
and the existing authorization. No existing general evaluation authorization
is treated as this checkpoint-specific decision. A technical computation
`PASS` or data-integrity `PASS` is not a strategy validation `PASS`.

## Metric disposition at 63

The existing prospective implementation defines total-return replay for each
frozen friction case and the corporate-action-aware 3-bps SPY/cash comparisons.
These are the only numeric comparison fields currently wired to its
prospective report. The gross-exposure invariant is boolean, not a portfolio
exposure series. Fees are applied in the ledger, but a separate aggregate
friction-cost or trade-count field is not present. Positive-month fraction is
not a trade hit rate.

The earlier design names primary CAGR, Sharpe, Sortino, and annualized
one-way turnover. Generation-2 helpers define them (365.25 calendar-day
CAGR; 252-session annualized Sharpe/Sortino; turnover from traded notional),
but the frozen prospective report does not emit them. It also does not emit
volatility, trade count, time-in-market/exposure fraction, trade win rate, or
MAE/MFE. None may be filled in ad hoc at the checkpoint. They remain
`UNKNOWN` or absent pending a separately frozen and audited implementation.

The frozen reporter currently includes partial first/last calendar months
in its monthly series, even though the design requests complete scored
months. Calendar-month returns, positive-month fraction, and worst complete
month therefore need an independently reviewed complete-month implementation
before use as decision evidence. A complete 12-month scored window cannot
exist at 63 sessions, so rolling 12-month return is `UNKNOWN/INSUFFICIENT_DATA`.
No annualized return, Sharpe, drawdown, alpha, hit-rate, or other unstated
metric is inferred from available values.

## Decision and information boundary

At fewer than 63 sessions: structural `PENDING` only, with no strategy
performance calculation or disclosure. At exactly 63 verified sessions:
structural `PHASE7_CHECKPOINT_READY` only. A missing or failed binding,
authorization, snapshot, accounting reconciliation, or required metric makes
the future checkpoint `UNKNOWN/ABSTAIN` and leaves raw evidence untouched.
If separately authorized and technically successful, the first checkpoint
may be a descriptive `EARLY_DIAGNOSTIC` with primary Phase-7 evidence still
`PENDING` until 252. No favorable pass/fail threshold, automatic `CONTINUE`
verdict, candidate change, search, tuning, production approval, or live
authority is created. RECON-009 remains a production gate.

The eventual report must be written once, read back, and content-bound to
the exact snapshot, this contract, the checkpoint-specific audit decision,
the existing evaluation authorization, and frozen source identities. An
unsuccessful write or readback is `UNKNOWN/ABSTAIN`; no report is published.

## Execution blockers and leakage review

The current hash-pinned `evaluate-phase7-checkpoint` command can produce a
performance-bearing `PHASE7_PROSPECTIVE_EVIDENCE_PENDING` report from a
three-session synthetic snapshot. It has no 63-session or separate checkpoint
authorization gate, and its fixed cutoff is 252. It validates one supplied
snapshot rather than the full append-only history. Its reporter calculates
metrics before the 63-session checkpoint and exposes them in CLI JSON.
The current CLI test explicitly exercises that three-session path. This is
an existing pre-checkpoint leakage defect; a pending status does not hide the
metrics. The prospective metric and monthly-completeness gaps above also
remain. Changing these pinned sources would invalidate the existing
evaluation authorization and stop governed collection until re-freeze and
Independent-Audit reauthorization. This task leaves them byte-identical and
marks checkpoint execution blocked. No debug/log/intermediate performance
output is authorized before the separate checkpoint decision.

No prospective bar, signal, position, strategy-return, or benchmark-return
data was read or calculated to prepare this preregistration. The only
session computations were XNYS calendar counts.
