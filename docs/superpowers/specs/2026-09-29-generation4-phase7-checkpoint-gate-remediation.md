# Generation-4 Phase-7 first checkpoint: execution gate remediation

Status: **ENGINEERED; SOURCE AMENDMENT AND CHECKPOINT EXECUTION NOT AUTHORIZED**.
This adds a protective execution boundary to the existing, unchanged strategy
methodology. It does not grant Independent-Audit authority.

## State machine

| State | Meaning | Permitted operation |
| --- | --- | --- |
| `PHASE7_CHECKPOINT_PENDING` | Fewer than 63 verified scored XNYS sessions | Structural status only |
| `PHASE7_CHECKPOINT_READY` | A verified exact-63 snapshot exists for 2026-09-28 through 2026-12-24 | Structural status and Independent-Audit review only |
| `PHASE7_CHECKPOINT_AUTHORIZED` | Independent Audit has issued the separate checkpoint artifact for the exact snapshot, chain digest, contract, and implementation | One governed paper-only calculation |
| `PHASE7_CHECKPOINT_EVALUATED` | The calculation passed required accounting checks and its result was exclusively written and read back | Inspect the immutable result; no automatic decision |
| `PHASE7_UNKNOWN_ABSTAIN` | Any missing, corrupt, conflicting, or unverifiable evidence | Preserve evidence and investigate; no evaluation |

`READY` does not imply `AUTHORIZED`. The current first-checkpoint contract
remains `PREREGISTERED_EXECUTION_BLOCKED` and its SHA-256 remains
`464b53fea8b08b33b3db851d27b3f4c1228ecf9bcb8a88966faa8c2a50d413bf`.
No checkpoint authorization file exists in this engineering handoff.

## General source amendment required now

The original general evaluation authorization binds the original CLI,
durability, and data-boundary source bytes. The protective gate changes those
bytes. The strict original authorization loader therefore rejects acquisition
until Independent Audit issues
`data/governance/successor/generation4-phase7-source-amendment-authorization.json`.
The amendment must bind the original authorization and contract, the unchanged
candidate/universe/benchmark/frictions, the preregistered first-checkpoint
contract, the exact new implementation commit and all listed source hashes.
Its permission to execute the checkpoint remains **false**. No source amendment
is fabricated or self-issued here.

After a valid amendment is present, the existing acquisition authorization
remains the snapshot identity. The collector and acquisition function still
verify it before provider creation. The amendment verifies the protective
source change; it does not reinterpret a return or permit a strategy change.

## Exact evidence boundary

The collector computes the 63rd XNYS session from the frozen first scored
session and checkpoint count. If a collection run occurs after 2026-12-24
without an exact-63 snapshot, it first targets 2026-12-24. Only after that
snapshot is exclusively published and verified may a later session be
collected. If a later snapshot already exists without the exact-63 snapshot,
collection abstains. A 64+ cumulative snapshot is never truncated or used as
the first checkpoint.

The first-checkpoint resolver verifies every local snapshot via the existing
manifest/file/session/price/corporate-action verifier. It pins the first
verified snapshot and selects only the exact-63 snapshot. It hashes the ordered
identities and manifest hashes of all snapshots through the 63rd session. A
later snapshot does not change that digest. Independent Audit must compare the
historical identities with prior durable receipts before signing an exact-63
authorization; the legacy snapshot format itself has no predecessor hash.

## Execution and information boundary

The supported CLI command is:

```text
python -m investment_tracker.independent_audit.post_generation3.phase7_evaluation_cli evaluate-phase7-checkpoint --evaluation-authorization data/governance/successor/generation4-phase7-evaluation-authorization.json --snapshot data/phase7/generation4/prospective/snapshots/<exact-63-snapshot-id>
```

It verifies the first-checkpoint contract, all snapshots, the exact selected
snapshot and chain, source amendment, and separate auditor-owned checkpoint
authorization before loading QFQ/unadjusted bars or corporate actions into
performance-sensitive evaluation state. It accepts no strategy-parameter or
symbol override. The public Python `prospective_checkpoint_report` also
requires an issued, live checkpoint permit before it accesses bars. The pure
replay helper is private and is used only by synthetic methodology tests.

Before authorization, CLI stdout/stderr and gate errors contain structural
codes only. The gate does not print or serialize bars, equity, positions,
signals, trades, or benchmark comparisons. Snapshot manifests continue to
state `performance_computed=false`, `performance_inspected=false`, and
`trading_context_created=false` before checkpoint evaluation.

## Result and decision boundary

The first authorized report uses the frozen 0/3/10/25/50-bps replay, 3-bps
corporate-action-aware SPY benchmark, zero-return cash, QFQ signals, and
unadjusted execution/P&L. It records the frozen first-scored-close return
basis. The writer requires all five total returns, benchmark and excess
comparisons, and the exposure invariant to be available; a missing required
field abstains. DQ-030 drawdown, Calmar, and recovery must remain `UNKNOWN`.
Partial-calendar-month fields are excluded from the immutable first-checkpoint
artifact pending a separate audited complete-month method. Rolling 12-month
return remains `UNKNOWN` at 63 sessions. RECON-009 remains `OPEN`.

The result is exclusively created at
`data/phase7/generation4/checkpoints/first63/checkpoint-result.json`, has a
canonical self-hash, binds the exact snapshot, chain, checkpoint and general
authorizations, contract, implementation, candidate, accounting conventions,
DQ/RECON state, and UTC evaluation time, and is read back before success is
reported. An existing result is never overwritten, including when identical.
An interrupted or conflicting write is `UNKNOWN/ABSTAIN` and requires
Independent-Audit investigation. The artifact is an `EARLY_DIAGNOSTIC`, not a
strategy validation pass; 252 scored sessions remain the first possible
terminal assessment. No outcome triggers tuning, successor creation,
production readiness, or live trading.

## Future operational procedure

1. Independent Audit reviews the code commit and issues the source amendment.
   Until then acquisition and checkpoint execution fail closed.
2. Resume governed collection only after the amendment verifier passes.
   The collector command is
   `python -m investment_tracker.independent_audit.post_generation3.phase7_collector_cli collect-prospective-data`.
   It automatically preserves the exact-63 snapshot before later sessions.
3. At 63/63, run
   `python -m investment_tracker.independent_audit.post_generation3.phase7_collector_cli first-checkpoint-readiness`
   and verify the exact manifest, all file
   hashes/sizes, XNYS dates, accounting files, all earlier snapshot identities,
   and no forbidden holdout access. Do not run evaluation yet.
4. Independent Audit compares the exact snapshot and chain against prior
   receipts, reviews the implementation and unresolved items, then issues the
   checkpoint-specific authorization. The normal CLI cannot create it.
5. Run the evaluation command once. Verify the result's self-hash and readback.
   Preserve all raw snapshots. No automatic strategy action follows.

If the exact-63 snapshot is missing or corrupt, remain `UNKNOWN/ABSTAIN`.
Preserve all existing evidence and obtain an Independent-Audit recovery
decision. Do not substitute a 64+ snapshot or rerun with changed parameters.
