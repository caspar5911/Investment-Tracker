# Phase 4 Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit the immutable 180-position Gate 3 campaign, apply the already-frozen survivor policy, deterministically select at most one candidate, and publish a content-addressed Phase 4 final decision and seal without rerunning research or touching FINAL_HOLDOUT.

**Architecture:** Add an isolated `phase4.finalization` package that reads the exact sealed campaign result set and runner receipts/attempts, validates the evidence graph, projects survivor evidence from committed candidate results using the existing Gate 3 projection semantics, calls the existing frozen survivor policy, and publishes append-only audit/decision/seal artifacts. The package never replays market data and never calls provider, brokerage, holdout, search, ranking override, or candidate-generation surfaces.

**Tech Stack:** Python 3, Pydantic, existing Phase 4 canonical JSON / ArtifactIdentity / filesystem containment utilities, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-18-phase-4-finalization-design.md`

## Global Constraints

- Campaign commit is `8acd01a2b5a9a070f4f651644920be64afb785dc`.
- Campaign result-set content SHA-256 is `bbefc542547ddc5e541a2390a978cf45a4a25c65603e0d114a6cb7f1fb9f32a8`.
- Campaign aggregate SHA-256 is `cd84547dc82339746c1780ec5a78d9e5f91a9048a46f06ed96b5e745415b47d2`.
- Candidate population is exactly 180 positions and digest `15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3`.
- Runner manifest content SHA-256 is `ac13f1eef4639d5f4476b2a6d07df0434bf5c8d2c95d67330852db303d0aa5d4`.
- No candidate execution/rerun, parameter change, new strategy, policy change, provider access, download, protected-symbol access, FINAL_HOLDOUT access, trading capability, or Phase 5 work.
- Missing survivor-critical evidence makes that candidate ineligible/UNKNOWN.
- Existing `phase4.preregistration.policy._eligible` and `select_survivor` remain the only hard-gate and deterministic selection authority.
- Existing Gate 3 candidate result bytes and prior authority seals remain byte-identical.
- Finalization outputs are canonical, content-addressed, append-only, path-contained, and explicitly preflighted by content hash.

---

### Task 1: Define immutable finalization schemas and RED policy tests

**Files:**
- Create: `tests/quant/test_phase4_finalization_models.py`
- Create: `src/investment_tracker/quant/phase4/finalization/__init__.py`
- Create: `src/investment_tracker/quant/phase4/finalization/models.py`

**Interfaces:**
- Produces: `AuditRow`, `Phase4Audit`, `Phase4Decision`, `FinalizationManifest`, `FinalizationSafetyState`.
- Consumes: existing `ArtifactIdentity` and frozen policy evidence types.

- [ ] **Step 1: Write failing schema tests**
  Test strict/frozen models, allowed final statuses, exact 180 audit rows, selected-candidate consistency, and zeroed safety state.
- [ ] **Step 2: Run the model tests and verify RED**
  Run: `python -m pytest -q tests/quant/test_phase4_finalization_models.py`
  Expected: import/module failures because production package does not yet exist.
- [ ] **Step 3: Implement minimal immutable schemas**
  Add strict Pydantic models with no policy thresholds duplicated in the schemas.
- [ ] **Step 4: Run model tests and verify GREEN**
  Expected: all model tests pass.
- [ ] **Step 5: Commit**
  Message: `feat: define Phase 4 finalization evidence models`

### Task 2: Audit the sealed campaign evidence graph

**Files:**
- Create: `tests/quant/test_phase4_finalization_audit.py`
- Create: `src/investment_tracker/quant/phase4/finalization/audit.py`

**Interfaces:**
- Consumes: explicit campaign result-set identity, `RunnerStateStore`, `ResultArtifactStore`, sealed runner/result-schema authorities.
- Produces: `audit_campaign(repository_root, campaign_result_set_identity) -> Phase4Audit` and internal machine-derived rejection reasons.

- [ ] **Step 1: Write failing tests for exact accounting and authority linkage**
  Cover exact 1..180 ordering, missing/duplicate/extra positions, canonical result identities, receipt/result linkage, attempt rules, exact runner binding, skipped-family-stop semantics, execution-failure rejection, deterministic enumeration-independent output, and UNKNOWN projection handling.
- [ ] **Step 2: Run audit tests and verify RED**
  Expected: missing `audit_campaign`.
- [ ] **Step 3: Implement minimal audit**
  Read the explicit result-set path only; verify all 180 receipts and attempts; read candidate result artifacts; use existing candidate-result validation/projection semantics without market replay; derive eligibility by calling the frozen policy implementation and derive human-readable rejection reasons by comparing the already-projected fields to the exact existing gates without changing their outcome.
- [ ] **Step 4: Run audit tests and verify GREEN**
- [ ] **Step 5: Commit**
  Message: `feat: audit sealed Phase 4 campaign evidence`

### Task 3: Deterministic survivor selection

**Files:**
- Create: `tests/quant/test_phase4_finalization_selection.py`
- Create: `src/investment_tracker/quant/phase4/finalization/selection.py`

**Interfaces:**
- Consumes: a validated `Phase4Audit`.
- Produces: `select_phase4_decision(audit) -> Phase4Decision`.

- [ ] **Step 1: Write failing tests**
  Cover zero eligible -> `NO_CREDIBLE_STRATEGY_FOUND`; one eligible -> exact frozen survivor; multiple eligible -> exact existing `select_survivor` ordering; non-AVAILABLE projection never selected; decision selected result identity/provenance matches the audited row.
- [ ] **Step 2: Run selection tests and verify RED**
- [ ] **Step 3: Implement selection as a thin wrapper**
  Call existing `select_survivor`; no independent ranking implementation or tie-break.
- [ ] **Step 4: Run selection tests and verify GREEN**
- [ ] **Step 5: Commit**
  Message: `feat: apply frozen Phase 4 survivor selection`

### Task 4: Content-addressed audit and decision artifacts

**Files:**
- Create: `tests/quant/test_phase4_finalization_artifacts.py`
- Create: `src/investment_tracker/quant/phase4/finalization/artifacts.py`

**Interfaces:**
- Produces: `FinalizationArtifactStore.write_audit/read_audit`, `write_decision/read_decision`.
- Paths:
  - `results/phase4/finalization/audit/sha256/<content>/audit.json`
  - `results/phase4/finalization/decision/sha256/<content>/decision.json`

- [ ] **Step 1: Write failing artifact-store tests**
  Cover canonical bytes, content/envelope identities, idempotent equal publication, unequal collision rejection, explicit identity readback, symlink/path escape rejection.
- [ ] **Step 2: Run tests and verify RED**
- [ ] **Step 3: Implement minimal append-only store using existing containment/canonical helpers**
- [ ] **Step 4: Run tests and verify GREEN**
- [ ] **Step 5: Commit**
  Message: `feat: publish immutable Phase 4 finalization artifacts`

### Task 5: Finalization authority seal and explicit-hash preflight

**Files:**
- Create: `tests/quant/test_phase4_finalization_methodology.py`
- Create: `src/investment_tracker/quant/phase4/finalization/methodology.py`
- Create: `src/investment_tracker/quant/phase4/finalization/cli.py`

**Interfaces:**
- Produces:
  - `seal_finalization(repository_root, source_revision, audit_identity, decision_identity) -> ArtifactIdentity`
  - `preflight_finalization(repository_root, manifest_content_sha256) -> FinalizationPreflight`
  - CLI commands `audit`, `select`, `seal`, `preflight`.

- [ ] **Step 1: Write failing methodology/CLI tests**
  Cover exact spec identity, exact source bundle/revision, explicit campaign/result-schema/runner/policy/audit/decision bindings, explicit-hash-only preflight, prohibited-surface scan, and safety state.
- [ ] **Step 2: Run tests and verify RED**
- [ ] **Step 3: Implement the seal/store/preflight**
  The seal is nonexecuting and content-addressed under `results/phase4/finalization/manifest/sha256/<content>/manifest.json`.
- [ ] **Step 4: Run tests and verify GREEN**
- [ ] **Step 5: Commit**
  Message: `feat: seal Phase 4 finalization authority`

### Task 6: Execute finalization against the real committed campaign

**Files:**
- Create only append-only artifacts under `results/phase4/finalization/`.

**Interfaces:**
- Consumes exact campaign result-set hash.
- Produces real audit, deterministic decision, and finalization seal.

- [ ] **Step 1: Run the full focused test suite**
  Run: `python -m pytest -q tests/quant/test_phase4_finalization_*.py`
- [ ] **Step 2: Run relevant existing Phase 4 regressions**
  Run the finalization tests plus existing Gate 3 runner/result-schema/preregistration policy tests available in CI.
- [ ] **Step 3: Execute audit using the explicit result-set identity**
  Require all 180 positions valid and zero `CAMPAIGN_EXECUTION_FAILED`.
- [ ] **Step 4: Execute deterministic selection**
  Record exactly one of `ONE_FROZEN_SURVIVOR` or `NO_CREDIBLE_STRATEGY_FOUND`.
- [ ] **Step 5: Publish audit and decision**
  Re-read both by explicit identities and require exact canonical bytes.
- [ ] **Step 6: Record clean implementation source revision**
  No source changes after this revision.
- [ ] **Step 7: Seal finalization**
  Bind exact spec, source bundle/revision, campaign, policies, audit and decision.
- [ ] **Step 8: Run explicit-hash preflight twice**
  Require deterministic `PHASE4_FINALIZATION_SEALED`.
- [ ] **Step 9: Commit only generated finalization evidence**
  Message: `evidence: seal Phase 4 final decision`

### Task 7: Independent review and completion verification

**Files:**
- No production changes unless a real defect is found through a RED regression test.

**Interfaces:**
- Verifies the final branch from campaign commit through final seal.

- [ ] **Step 1: Review diff against the approved design**
  Confirm no existing candidate result, attempt, receipt, result set, prior seal, survivor policy, strategy, or market-data code changed.
- [ ] **Step 2: Verify prohibited surfaces**
  No protected symbols, FINAL_HOLDOUT, provider/network calls, brokerage/order APIs, candidate execution/rerun, strategy search, or Phase 5 start.
- [ ] **Step 3: Verify all focused tests freshly**
- [ ] **Step 4: Verify finalization preflight freshly**
- [ ] **Step 5: Report exact outcome and hashes**
  Include eligible count, selected candidate (if any), audit/decision/manifest identities, source revision, test counts, and safety assertions.
