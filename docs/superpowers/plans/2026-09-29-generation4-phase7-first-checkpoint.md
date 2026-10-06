# Generation-4 Phase-7 First Checkpoint Preregistration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Freeze a non-authorizing, exact-63-session checkpoint boundary and document the current execution blockers before results exist.

**Architecture:** Bind a machine-readable contract to the existing evaluation authorization and frozen source hashes. Add a structural, provider-free readiness resolver that verifies all local snapshots through the existing collector before choosing only an exact-63 snapshot. Leave the hash-pinned evaluator unchanged and execution blocked pending a separate Independent-Audit decision and remediation.

**Tech Stack:** Python 3.12, exchange_calendars, pytest, JSON.

**Spec:** `docs/superpowers/specs/2026-09-29-generation4-phase7-first-checkpoint-preregistration.md`

## Global Constraints

- Do not read real prospective performance, contact a provider, or evaluate a checkpoint.
- Do not edit the frozen evaluation, CLI, durability, or data-boundary sources.
- Exact first checkpoint: 63 XNYS sessions from 2026-09-28 through 2026-12-24; 210 warmup sessions from 2025-11-24.
- The existing authorization remains paper-only and unchanged; a separate checkpoint-specific Independent-Audit action is still required.
- DQ-030 remains UNRESOLVED; RECON-009 remains OPEN.

## Review Focus

- A 62-session snapshot must never become checkpoint-ready.
- A 64+ snapshot cannot stand in for a missing exact-63 snapshot.
- A corrupt earlier snapshot must block readiness even if the exact-63 snapshot is valid.
- Contract or frozen-source drift must block readiness.
- The readiness path must never import or call performance evaluation.

### Task 1: Contract and synthetic boundary tests

**Files:** `data/governance/successor/generation4-phase7-first-checkpoint-contract.json`, `tests/independent_audit/test_generation4_phase7_first_checkpoint.py`.

- [x] Write tests for all bound hashes, exact candidate/universe/frictions, XNYS 62/63/64 dates, DQ/RECON states, permissions, and metric/blocker classifications.
- [x] Run the tests red for the missing structural resolver.

### Task 2: Provider-free structural resolver

**Files:** `src/investment_tracker/independent_audit/post_generation3/phase7_first_checkpoint.py`, `tests/independent_audit/test_generation4_phase7_first_checkpoint.py`.

- [x] Implement strict contract checks and reuse the collector's authorization and full-snapshot verifier.
- [x] Return pending at 62, ready only for an exact-63 verified snapshot, and UNKNOWN/ABSTAIN if 64+ exists without it or any integrity check fails.
- [x] Verify status output is structural and that no evaluator or provider can be called.

### Task 3: Governance verification and delivery

- [x] Review CLI, logs, exceptions, temporary files, metadata, tests, and reporting for early leakage; record existing frozen-path blockers.
- [x] Run focused Phase-7 authorization, integrity, accounting, boundary, contract, durability, collector, and new tests plus compile checks.
- [x] Verify frozen source and authorization byte hashes remain unchanged.
- [x] Commit and push preregistration separately; report exact SHA and CI status.
