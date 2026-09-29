# Generation-4 Phase-7 first-checkpoint gate: dependency and authority map

Prepared before changing production code. No prospective performance or holdout data was read.

## ALREADY_FROZEN

- `generation4-phase7-start.json` and `generation4-phase7-start-contract.json` fix the start, candidate, paper-only status, and entry authorization.
- `generation4-phase7-evaluation-contract.json` fixes the evaluation implementation commit `5149ac70d2561abff4b2cc6d2b8c75dbedfa3bd2`, source hashes, ordered universe, SPY benchmark, 0/3/10/25/50-bps schedule, 3-bps primary case, 210-session warmup, 2026-09-28 first scored session, and 63/126/252 checkpoints.
- `generation4-phase7-evaluation-authorization.json` is Independent-Audit owned and binds the frozen evaluation CLI and durability source bytes. Its SHA-256 is `35c767097e135319f059060ca01553160f8ae492b9571769a90bafe1a4585812`. It permits paper-only prospective evaluation in general; it does not identify a first-checkpoint snapshot.
- `generation4-phase7-first-checkpoint-contract.json` (SHA-256 `464b53fea8b08b33b3db851d27b3f4c1228ecf9bcb8a88966faa8c2a50d413bf`) fixes the first-checkpoint boundary at exactly 63 scored XNYS sessions through 2026-12-24, with 210 warmup sessions beginning 2025-11-24. A later snapshot cannot substitute for a missing exact-63 snapshot. It has authority `NONE` and `checkpoint_evaluation_authorized=false`.
- `phase7_collector.verify_snapshot` checks manifest schema/content hash, file bytes/sizes, exact file set, bar alignment and OHLC, symbol order, conventions, and no-performance/no-holdout flags. `_verified_snapshots` checks all local snapshots before returning history.
- `phase7_first_checkpoint.first_checkpoint_readiness` selects exact-63 structural evidence only. `phase7_collector` reports structural progress and never evaluates.
- `generation4_durability` contains the frozen strategy replay, five friction cases, SPY/cash comparison, and DQ-030 `UNKNOWN` handling. The Generation-2 accounting replay supplies next-open fills and explicit corporate actions.

## BYPASS ROOT CAUSE

`phase7_evaluation_cli._evaluate_checkpoint_command` accepts a caller-supplied snapshot after only the general evaluation authorization, reads bars/actions, and calls `prospective_checkpoint_report`. The public `prospective_checkpoint_report` computes a report from caller-supplied `ProspectiveCheckpoint` data without any checkpoint-specific authority. Synthetic tests demonstrate a three-scored-session report. Both entry points are supported execution paths.

## NEEDS_IMPLEMENTATION

1. An exact-63, provider-free preflight that verifies the existing first-checkpoint contract, every local snapshot, frozen identities, and an exact selected manifest before any performance-sensitive object is built.
2. A separate Independent-Audit checkpoint authorization schema, strict loader, template, and request. It must bind the exact selected snapshot and implementation. The production artifact is absent until Independent Audit acts.
3. A public evaluation entry boundary requiring the verified checkpoint permit; the legacy direct CLI path must delegate to it. The pure computation implementation remains private and is callable only after the gate in production.
4. An immutable, read-back verified result writer that refuses any second result for the same first checkpoint.
5. Collector logic to preserve the exact-63 cumulative snapshot before acquiring a later session when collection was skipped.
6. Synthetic adversarial tests and CI coverage.

## REQUIRES_NEW_INDEPENDENT_AUDIT_AUTHORITY

The existing authorization cryptographically binds the original CLI, durability, and data-boundary source bytes. Changing those files makes the original general authorization fail closed, including for acquisition, unless Independent Audit approves a separate exact-source amendment. The amendment binds the unchanged original authorization, the first-checkpoint contract, and the new committed source bytes; it grants no checkpoint evaluation permission. Engineering cannot issue the amendment or edit the auditor-owned original authorization. A separate first-checkpoint authorization can be issued only after the exact-63 snapshot exists and passes audit. Neither artifact is issued in this engineering task.

## STILL_UNRESOLVED

- DQ-030 remains `UNRESOLVED`; max drawdown, Calmar, and recovery stay `UNKNOWN` for Generation 4.
- RECON-009 remains `OPEN`; five runtime evidence classes are still required for production readiness.
- The old snapshot format has no predecessor hash. Individual manifests are content-bound, but append-only history additionally requires comparison against recorded earlier snapshot identities.
- The frozen prospective reporter's first-scored-close return basis and partial-month fields require Independent-Audit review before interpretation; no performance threshold is frozen for the 63-session descriptive checkpoint.

## Dependency direction

`start + evaluation contract + general authorization` -> `collector snapshot chain` -> `first-checkpoint contract + exact-63 structural readiness` -> `separate checkpoint authorization` -> `performance-sensitive load/replay` -> `immutable result`. General evaluation authorization does not imply checkpoint authorization. Structural READY does not imply AUTHORIZED.
