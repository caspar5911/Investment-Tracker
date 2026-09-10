# Tracker Framework v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, testable Python framework that lets isolated Codex workers prepare Investment Tracker evidence while a single coordinator validates and integrates it without violating frozen governance.

**Architecture:** The repository will contain pure deterministic domain logic plus thin CLI entry points. Worker code never writes the canonical Google Sheet. It consumes immutable snapshots and emits staging manifests/artifacts; the coordinator validates snapshot freshness, holdout safety, schemas, and state transitions before any external canonical write is attempted by the chat/connector layer.

**Tech Stack:** Python 3.12, standard library, `pydantic>=2.8,<3`, `pytest>=8,<9`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-10-investment-tracker-multi-agent-design.md`

## Global Constraints

- Paper-only validation. No trade execution.
- Frozen versions are exactly `TPC-v1.2`, `REPLAY-v1.0`, `CALC-v1.2`, `ROBUST-v1.0`.
- Locked replacement holdout symbols are exactly `HACK`, `SOXX`, `NLR`, `URNM`, `GEV` and must be rejected before provider dispatch.
- Phase A ends `2023-12-31`; Phase B ends `2025-09-07`.
- `max_drawdown` remains UNKNOWN under DQ-030.
- Worker runtime has no canonical Sheet write capability.
- Coordinator is the single canonical writer and must fail closed on stale snapshots or ambiguous evidence.
- Canonical identity is semantic, never based on durable Sheet row numbers.
- Missing required evidence becomes UNKNOWN/ABSTAIN, never inference.

---

### Task 1: Repository scaffold and CI

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.github/workflows/test.yml`
- Create: `src/investment_tracker/__init__.py`
- Create: `tests/test_import.py`

**Interfaces:**
- Produces importable package `investment_tracker` and a CI command `python -m pytest -q`.

- [ ] Add Python project metadata, pytest dependency, package layout, runtime ignores, and GitHub Actions test workflow.
- [ ] Add `tests/test_import.py` asserting the package imports and exposes `__version__`.
- [ ] Run CI and confirm RED because `__version__` does not yet exist.
- [ ] Add minimal `__version__ = "0.1.0"`.
- [ ] Re-run CI and confirm GREEN.

### Task 2: Frozen governance and holdout guard

**Files:**
- Create: `tests/test_governance.py`
- Create: `src/investment_tracker/governance.py`

**Interfaces:**
- Produces `FrozenVersions`, `LOCKED_HOLDOUT`, `PHASE_A_END`, `PHASE_B_END`, `assert_symbol_allowed(symbol: str) -> str`.

- [ ] Write tests proving exact frozen versions and exact locked symbols.
- [ ] Write a test proving `assert_symbol_allowed("HACK")` raises before any downstream call and lowercase input is normalized then rejected.
- [ ] Write a test proving `URA` is accepted and normalized uppercase.
- [ ] Run CI and confirm RED.
- [ ] Implement minimal constants/dataclass and guard.
- [ ] Run CI and confirm GREEN.

### Task 3: Canonical identity and raw digest

**Files:**
- Create: `tests/test_identity.py`
- Create: `src/investment_tracker/identity.py`

**Interfaces:**
- Produces `canonical_bar_key(asset, date) -> str` and `raw_digest_token(...) -> str`.

- [ ] Write tests for exact `ASSET|YYYY-MM-DD|ALPACA_SIP|NORM-v1` key format.
- [ ] Write tests proving integer-like numeric values serialize without trailing `.0` while non-integers preserve significant decimal digits.
- [ ] Write tests reproducing known examples such as `609218 -> "609218"` and `15.495505 -> "15.495505"`.
- [ ] Run CI and confirm RED.
- [ ] Implement deterministic decimal canonicalization using `Decimal(str(value))` and construct RAWv1 token.
- [ ] Run CI and confirm GREEN.

### Task 4: Typed staging and snapshot schemas

**Files:**
- Create: `tests/test_models.py`
- Create: `src/investment_tracker/models.py`

**Interfaces:**
- Produces `InputSnapshot`, `WorkerManifest`, `ValidationReport`, `MarketBar`, `ReplayDailyRow`, `EpisodeOutcomeRow`, `BaselineRow` Pydantic models.

- [ ] Write tests requiring snapshot ID, dispatch run ID, versions, asset/date scope, SPY digest, DQ refs, Phase Matrix state, input digests, timestamp, and holdout exclusion assertion.
- [ ] Write tests requiring worker manifests to carry the exact snapshot ID/digests consumed.
- [ ] Write tests rejecting unknown/locked assets and invalid version strings.
- [ ] Run CI and confirm RED.
- [ ] Implement minimal strict models with frozen-version validators.
- [ ] Run CI and confirm GREEN.

### Task 5: Snapshot freshness and semantic merge guard

**Files:**
- Create: `tests/test_snapshot_guard.py`
- Create: `src/investment_tracker/snapshot.py`

**Interfaces:**
- Produces `verify_snapshot_fresh(worker_manifest, current_input_digests) -> None` and `StaleSnapshotError`.

- [ ] Test exact-digest match passes.
- [ ] Test any changed material digest raises `StaleSnapshotError` with the changed key names.
- [ ] Test missing current digest fails closed.
- [ ] Run CI and confirm RED.
- [ ] Implement deterministic dictionary comparison.
- [ ] Run CI and confirm GREEN.

### Task 6: Phase Matrix state machine

**Files:**
- Create: `tests/test_phase_state.py`
- Create: `src/investment_tracker/phase_state.py`

**Interfaces:**
- Produces `PhaseState` enum and `assert_transition(current, target, evidence_readback_ok, dq_reconciliation=False)`.

- [ ] Test allowed progression `VALIDATED_NOT_CACHED -> PARTIAL_CACHE -> CACHED_CLEAN/QUARANTINED -> REPLAY_DAILY_COMPLETE -> EPISODES_COMPLETE -> OUTCOMES_COMPLETE -> BASELINES_COMPLETE`.
- [ ] Test skip-ahead transitions fail.
- [ ] Test advancement without readback evidence fails.
- [ ] Test regression fails unless `dq_reconciliation=True`.
- [ ] Run CI RED, implement, then run GREEN.

### Task 7: Coordinator single-writer lock

**Files:**
- Create: `tests/test_lock.py`
- Create: `src/investment_tracker/coordinator_lock.py`

**Interfaces:**
- Produces `CanonicalWriteLock.acquire(path, run_id, scope, snapshot_id)` and `.release(run_id)` plus `LockHeldError` and `StaleLockError`.

- [ ] Test first acquisition creates deterministic JSON runtime state.
- [ ] Test second run cannot acquire an existing lock.
- [ ] Test wrong run cannot release the lock.
- [ ] Test an old lock is reported as stale but never automatically broken.
- [ ] Run CI RED, implement, then run GREEN.

### Task 8: Frozen replay calculations

**Files:**
- Create: `tests/test_replay.py`
- Create: `src/investment_tracker/replay.py`

**Interfaces:**
- Produces pure functions for trend, pullback, stabilization, relative-strength, chase gates, state precedence, and episode-start detection.

- [ ] Write numerical fixture tests for each gate using the exact frozen inequalities.
- [ ] Test state precedence: TRIM/AVOID before WAIT, WAIT before WATCH, ACCUMULATE only when all five gates pass.
- [ ] Test insufficient history returns UNKNOWN/ABSTAIN rather than inference.
- [ ] Test consecutive ACCUMULATE days emit exactly one episode start.
- [ ] Run CI RED, implement, then run GREEN.

### Task 9: Outcome conventions and C24 censoring

**Files:**
- Create: `tests/test_outcomes.py`
- Create: `src/investment_tracker/outcomes.py`

**Interfaces:**
- Produces `horizon_return`, `cash_hurdle`, `apply_friction`, `is_censored`, and `range_metrics_status`.

- [ ] Test entry uses t+1 open supplied by caller and horizon return is horizon-close/entry-open -1.
- [ ] Test 0/10/25 bps round-trip friction subtracts 0/0.001/0.0025 from gross return.
- [ ] Test 3.25% actual-calendar-day cash hurdle.
- [ ] Test Phase-A boundary `2023-12-31` and Phase-B boundary `2025-09-07` censor horizons that cross them.
- [ ] Test any quarantined range date in the interval forces MAE/MFE UNKNOWN while close return remains usable.
- [ ] Run CI RED, implement, then run GREEN.

### Task 10: Baseline definitions

**Files:**
- Create: `tests/test_baselines.py`
- Create: `src/investment_tracker/baselines.py`

**Interfaces:**
- Produces helpers for C17 buy-and-hold eligibility, C18 first-session monthly DCA schedule, and C19 simple-dip episode detection.

- [ ] Test first executable session respects required warm-up/listing boundary.
- [ ] Test DCA selects exactly the first trading session of each calendar month.
- [ ] Test simple dip requires close <= 0.90 * prior60_high and deduplicates consecutive qualifying days.
- [ ] Run CI RED, implement, then run GREEN.

### Task 11: Validation report and worker artifact verifier

**Files:**
- Create: `tests/test_validation.py`
- Create: `src/investment_tracker/validation.py`

**Interfaces:**
- Produces `validate_market_bars`, `validate_replay_rows`, and `validate_manifest_files` returning `ValidationReport` and refusing zero-evidence success.

- [ ] Test duplicates, malformed keys/digests, benchmark mismatch, arithmetic mismatch, and locked symbols each fail validation.
- [ ] Test clean fixtures report exact invariant counts.
- [ ] Run CI RED, implement, then run GREEN.

### Task 12: CLI and agent instructions

**Files:**
- Create: `tests/test_cli.py`
- Create: `src/investment_tracker/cli.py`
- Create: `AGENTS.md`
- Create: `agents/coordinator.md`
- Create: `agents/ura.md`
- Create: `agents/cibr.md`
- Create: `agents/smh.md`
- Create: `agents/copx-xle.md`
- Create: `agents/audit-robustness.md`
- Modify: `pyproject.toml`
- Modify: `README.md`

**Interfaces:**
- Produces command `investment-tracker validate-manifest <path>` and documented agent scopes.

- [ ] Write CLI tests proving locked-holdout manifests are rejected and clean manifests return exit 0.
- [ ] Run CI RED.
- [ ] Implement CLI and console entry point.
- [ ] Add root and role-specific agent instructions preserving single-writer/holdout/governance rules.
- [ ] Document Codex workflow and separation between GitHub code source-of-truth and Google Sheet canonical evidence plane.
- [ ] Run full CI GREEN.

### Task 13: Integration fixture for URA continuation

**Files:**
- Create: `tests/fixtures/ura-2018-sample.json`
- Create: `tests/test_ura_fixture.py`

**Interfaces:**
- Demonstrates that existing canonical URA evidence can be represented and validated without changing frozen rules.

- [ ] Create a small fixture using already-canonical non-holdout URA/SPY evidence only.
- [ ] Test canonical key, digest, date alignment, usable flags, and versions against that fixture.
- [ ] Run RED if fixture support is missing; add only necessary validation glue.
- [ ] Run full test suite GREEN.

### Task 14: PR verification and merge readiness

**Files:**
- Modify only as required by review findings.

- [ ] Verify branch diff contains no credentials, Sheet write tokens, locked-holdout history, or generated runtime lock files.
- [ ] Run complete GitHub Actions test suite and require zero failures.
- [ ] Review against the architecture spec line-by-line.
- [ ] Open PR to `main` with explicit statement that framework code does not itself promote Production Readiness.
- [ ] Merge only after fresh CI and review evidence.
