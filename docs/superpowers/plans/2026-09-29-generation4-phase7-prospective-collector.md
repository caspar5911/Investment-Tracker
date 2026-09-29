# Generation-4 Phase-7 Prospective Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add safe automatic prospective collection and provider-free structural status.

**Architecture:** New collector and CLI modules orchestrate the frozen authorization, calendar, request, and acquisition functions. A read-only snapshot verifier gates both status and collection; staged acquisition is published only after verification.

**Tech Stack:** Python 3.12, exchange_calendars, pandas, pytest.

**Spec:** docs/superpowers/specs/2026-09-29-generation4-phase7-prospective-collector-design.md

## Global Constraints

- Do not edit hash-pinned Phase-7 data, evaluation, CLI, or durability sources.
- Do not call a real provider or evaluate real performance in implementation tests.
- Preserve exact universe GLD, IEF, IWM, QQQ, SPY, TLT, VNQ, XLP.
- Preserve first scored session 2026-09-28, 210 warmup sessions, and 63/126/252 checkpoints.
- Preserve the existing authorization, contract, start artifact, and first snapshot bytes.
- Do not expose symbol, date, clock, candidate, or output-path overrides in the CLI.

## Review Focus

- A corrupt latest snapshot must stop collection before provider creation.
- An in-progress market session must never enter the request.
- A failed staged acquisition must not replace or invalidate prior evidence.
- A concurrent destination must not be overwritten.
- Status must never invoke provider or performance code.

### Task 1: Read-only snapshot verification and structural status

**Files:** Create src/investment_tracker/independent_audit/post_generation3/phase7_collector.py and tests/independent_audit/test_generation4_phase7_collector.py.

**Interfaces:** Produce verify_snapshot(path, authorization), prospective_status(), and a structural status mapping.

- [ ] Write tests for completed-session calendar, exact 210 warmup boundary, authentic and tampered snapshot verification, forbidden files, and 62/63/126/252 status.
- [ ] Run the new tests and confirm failure for missing collector behavior.
- [ ] Implement the minimum read-only verifier and status path using frozen helpers.
- [ ] Run the new tests and confirm pass.

### Task 2: Governed collection

**Files:** Modify phase7_collector.py and test_generation4_phase7_collector.py.

**Interfaces:** Produce collect_prospective_data() with no user-provided acquisition scope.

- [ ] Write tests for authorization-before-provider, no-op idempotence, exact derived request, staged append-only success, failed acquisition cleanup, failed verification, and destination conflict.
- [ ] Run the new tests and confirm expected failure.
- [ ] Implement staged acquisition through the frozen Phase-7 acquisition function, followed by read-only verification and non-replacing publication.
- [ ] Run the new tests and confirm pass.

### Task 3: CLI and final governance review

**Files:** Create src/investment_tracker/independent_audit/post_generation3/phase7_collector_cli.py and tests/independent_audit/test_generation4_phase7_collector_cli.py.

**Interfaces:** Produce collect-prospective-data and prospective-status subcommands with no scope overrides.

- [ ] Write CLI tests for provider-free status, structured fail-closed output, no arbitrary overrides, and absence of performance calls.
- [ ] Run the CLI tests and confirm expected failure.
- [ ] Implement the minimal CLI.
- [ ] Run new and required existing Generation-4 tests, compile checks, and static security review.
- [ ] Run the provider-free status command on the current local snapshot.
- [ ] Commit and push the collector separately from prior governance commits.
