# Generation-4 Phase-7 prospective collector design

## Purpose

Accumulate completed XNYS sessions under the existing paper-only Generation-4
Phase-7 evaluation authorization without manual date-window construction.
Collection reports structural progress only. It never invokes a strategy
checkpoint or exposes performance.

## Frozen boundary

The authorization pins the existing Phase-7 data, evaluation, CLI, and
durability source bytes. The collector therefore lives in new modules and
does not edit those frozen files. It calls the existing authorization loader,
request validator, snapshot writer, and acquisition function. The research
universe, candidate, 2026-09-28 scored boundary, 210-session warmup, and
63/126/252 checkpoints come only from verified authorization and frozen
constants. The CLI accepts no symbol, date, clock, candidate, or output-path
override.

## Read-only status

Read the trusted UTC system clock and XNYS calendar to identify the latest
fully completed session. Verify the authorization before examining snapshots.
Validate every existing snapshot's schema, canonical manifest hash, seeded
snapshot ID, file table, file bytes and sizes, symbol hashes, exact XNYS
sessions, OHLC validity, and non-performance governance flags. Reject extra
files, paths outside the snapshot, duplicate end dates, and corrupted
evidence. Report only latest completed/acquired dates, scored-session count,
next checkpoint, remaining sessions, snapshot ID, and verification status.
Missing or inconsistent evidence returns UNKNOWN/ABSTAIN.

## Collection

Perform the same read-only checks first. If the latest acquired session is
already the latest completed session, return NO_NEW_COMPLETED_SESSION before
provider creation. If there is no accepted snapshot, or a later completed
session exists, derive the warmup start from the 210 XNYS sessions immediately
before 2026-09-28. Build the exact request with the frozen Phase-7 builder.

Call the frozen acquisition function into a temporary directory on the same
filesystem as the final snapshot root. Validate the completed temporary
snapshot with the same read-only validator, then move only that complete
content-addressed directory into the governed snapshots directory. An
existing destination is never replaced. Failure leaves prior snapshots
unchanged and no new accepted snapshot; it returns UNKNOWN/ABSTAIN.

At exactly 63, 126, or 252 scored sessions, report
PHASE7_CHECKPOINT_READY as structural metadata. No checkpoint evaluation is
triggered.

## Security and testing

Use a new collector CLI with two commands: collect-prospective-data and
prospective-status. Neither command imports or calls a brokerage or order
context. Tests use synthetic snapshots and a fake acquisition boundary;
they never call OpenD. Tests cover the clock/calendar, authorization ordering,
idempotent no-op, tampered evidence, append-only publication, failure cleanup,
holdout exclusion, checkpoint statuses, and CLI provider-free status.
