# Generation-4 Phase-7 Start Boundary Implementation Plan

Date: 2026-09-26

Spec: `docs/superpowers/specs/2026-09-26-generation4-phase7-start-boundary-design.md`

Goal: Implement a one-time, fail-closed Phase-7 start transition that consumes the already-approved Generation-4 Phase-7 entry authorization, freezes the start implementation through a machine-readable start contract, and creates a canonical Phase-7 start artifact without authorizing any Phase-7 performance evaluation.

## Global constraints

- Work on `governance/phase6-successor-dividend-normalization-v3`.
- Required design commit: `c0a01661d7403be3058f4bbd9700642c7714416a`.
- Preserve frozen Phase-7 entry implementation commit `7893306e3c77b85c59f044b787a55579593c678b`.
- Preserve Independent Audit authorization commit `646f8fb9e6b5f90cbd2aef2b6ed2f0e421641ccf`.
- Do not touch `.qwen/`.
- Do not modify `phase7_entry.py` or `phase7_entry_cli.py`.
- Do not modify any Stage-B frozen source.
- Do not read/decrypt the holdout bundle or key.
- Do not call OpenD/provider/broker APIs.
- Do not rerun acquisition or final-holdout evaluation.
- Do not inspect performance metrics for the start decision.
- Do not search/tune candidates or substitute symbols.
- Keep production/live trading false and `RECON-009=OPEN`.
- No Phase-7 performance evaluation is authorized by this work.

## Task 1 — Synthetic start-readiness verifier

Files:

- Create `src/investment_tracker/independent_audit/post_generation3/phase7_start.py`.
- Create `tests/independent_audit/test_generation4_phase7_start.py`.

### RED

Write tests first for:

- valid synthetic entry decision -> `GENERATION4_PHASE7_START_READY`;
- missing Independent Audit authorization;
- invalid authorization;
- wrong authorization ID;
- audit-request hash mismatch;
- candidate/binding/implementation mismatch;
- methodology mismatch;
- locked-symbol order drift;
- any of seven evidence hashes drifting;
- production/live trading true;
- `RECON-009 != OPEN`;
- `paper_only != true`;
- any retry/reuse/search/mutation/substitution/result-dependent-change authority true.

The synthetic fixtures must not use private market observations.

Run:

`python -m pytest -q tests/independent_audit/test_generation4_phase7_start.py`

Confirm RED because the module does not exist.

### GREEN

Implement:

- `Generation4Phase7StartError`;
- stable error constants from the design;
- strict JSON/hash helpers;
- `verify_generation4_phase7_start_readiness(...)`.

The verifier must call the existing `evaluate_generation4_phase7_entry` rather than duplicating the entry decision logic.

It must return identities/governance/hashes only, never performance metrics.

Expected readiness schema:

`GENERATION4-PHASE7-START-READINESS-v1`

Expected status:

`GENERATION4_PHASE7_START_READY`

Run focused tests and commit.

Suggested commit:

`feat: verify Generation 4 Phase 7 start readiness`

## Task 2 — Strict start-contract model and runtime bindings

Files:

- Modify `phase7_start.py`.
- Modify `test_generation4_phase7_start.py`.

### RED

Add tests for strict start contract:

- missing contract;
- unknown fields;
- wrong schema/status/authority;
- wrong frozen entry implementation commit;
- wrong start implementation commit;
- entry gate source hash drift;
- entry CLI source hash drift;
- start module source hash drift;
- start CLI source hash drift;
- entry-authorization file hash drift;
- audit-request hash drift;
- seven evidence-hash drift;
- wrong governance literals.

Use `ConfigDict(extra="forbid", frozen=True)`.

### GREEN

Implement model:

`Generation4Phase7StartContract`

with schema:

`GENERATION4-PHASE7-START-CONTRACT-v1`

and status:

`FROZEN_PRE_START`.

Implement:

`load_generation4_phase7_start_contract(...)`

The loader must recompute all source/file hashes from actual bytes and compare them to the contract and fresh readiness report.

Do not create the real contract yet; tests use synthetic temp files.

Commit.

Suggested commit:

`feat: bind Generation 4 Phase 7 start contract`

## Task 3 — One-time start-artifact writer

Files:

- Modify `phase7_start.py`.
- Modify `test_generation4_phase7_start.py`.

### RED

Add tests for:

- successful start artifact creation;
- artifact schema/status/authority exact;
- `phase7_started=true`;
- `phase7_performance_evaluation_authorized=false`;
- production/live trading false;
- all prohibition flags false;
- `RECON-009=OPEN`;
- `paper_only=true`;
- all identity/evidence/source hashes copied from verified inputs;
- deterministic self-hash verifies;
- second start attempt fails `GEN4_PHASE7_ALREADY_STARTED`;
- malformed existing artifact fails closed;
- any failure before write leaves output absent;
- exclusive-create race maps to fail-closed start error.

### GREEN

Implement:

`start_generation4_phase7(...)`

Behavior:

1. fresh start-readiness verification;
2. strict start-contract validation;
3. build canonical payload;
4. compute self-hash over canonical payload without the self-hash field;
5. create output exclusively with `xb`;
6. read back and verify exact bytes/content;
7. return the created artifact.

The function may write only the requested start artifact.

Suggested commit:

`feat: create one-time Generation 4 Phase 7 start artifact`

## Task 4 — CLI and static safety boundary

Files:

- Create `src/investment_tracker/independent_audit/post_generation3/phase7_start_cli.py`.
- Modify tests.
- Modify `.github/workflows/successor-dividend-normalization-v3.yml`.

CLI commands only:

- `verify-start-readiness`;
- `start-phase7`.

The start command requires:

- all existing entry evidence paths;
- audit-request path;
- authorization path;
- start-contract path;
- start-output path.

No other mutating command is allowed.

### RED tests

- verify-start-readiness success output;
- start-phase7 synthetic success;
- CLI error returns nonzero canonical JSON;
- no metrics leak;
- no provider/broker/order strings;
- no acquisition/evaluation commands;
- no bundle/key arguments;
- no overwrite option;
- no production/live authority option.

### GREEN

Implement CLI.

Static forbidden strings include at least:

- `OpenTradeContext`;
- `place_order`;
- `modify_order`;
- `cancel_order`;
- `unlock_trade`;
- `acquire-final-holdout`;
- `evaluate-final-holdout`;
- `issue-final-holdout-release`;
- `close-phase6`.

Add focused CI coverage.

Run:

- compileall;
- new start tests;
- Generation-4 entry tests;
- Stage-A/Stage-B boundary tests;
- generic Phase-7 readiness tests;
- Generation-2 Phase-7 tests.

Commit and record the exact frozen start implementation commit.

Suggested commit:

`feat: add Generation 4 Phase 7 start CLI`

Do not modify the start module or CLI after recording this commit unless you intentionally create a new frozen implementation commit and regenerate the contract.

## Task 5 — Freeze machine-readable start contract

After Task 4 is green:

1. record the exact start implementation commit;
2. compute SHA-256 of:
   - `phase7_entry.py`;
   - `phase7_entry_cli.py`;
   - `phase7_start.py`;
   - `phase7_start_cli.py`;
   - audit request;
   - entry authorization;
3. run real `verify-start-readiness` against the JSON-only private chain;
4. confirm no bundle/key/provider access;
5. create `data/governance/successor/generation4-phase7-start-contract.json`.

The contract must bind all fields from Design §6 exactly.

It must explicitly contain:

- `phase7_performance_evaluation_authorized=false`;
- `production_readiness_approved=false`;
- `live_trading_authorized=false`;
- `holdout_reuse_authorized=false`;
- `candidate_search_authorized=false`;
- `parameter_mutation_authorized=false`;
- `symbol_substitution_authorized=false`;
- both result-dependent-change flags false;
- `recon009_status="OPEN"`;
- `paper_only=true`.

Add repository tests proving the committed contract matches the frozen implementation and real public bindings.

Commit the contract separately.

Suggested commit:

`governance: freeze Generation 4 Phase 7 start contract`

## Task 6 — Real start-readiness verification

No file changes.

Run real:

`verify-start-readiness`

using:

- Phase-6 contract;
- acquisition authorization;
- selection;
- virginity attestation;
- virginity evidence;
- private receipt;
- private release;
- private result;
- private consumption marker;
- private closure;
- committed Phase-7 audit request;
- committed Phase-7 entry authorization;
- committed start contract.

Expected:

- `GENERATION4_PHASE7_START_READY`;
- entry authorized true;
- started false;
- performance evaluation authorized false;
- production/live false;
- `RECON-009=OPEN`;
- paper-only true;
- no metrics.

If any mismatch occurs, stop. Do not patch evidence to make it pass.

## Task 7 — Execute the one-time Phase-7 start transition

Run `start-phase7` once against the same inputs.

Output path:

`data/governance/successor/generation4-phase7-start.json`

Expected artifact:

- schema `GENERATION4-PHASE7-START-v1`;
- status `GENERATION4_PHASE7_STARTED`;
- `phase7_entry_authorized=true`;
- `phase7_started=true`;
- `phase7_performance_evaluation_authorized=false`;
- production/live false;
- `RECON-009=OPEN`;
- paper-only true.

Immediately verify:

- self-hash;
- source bindings;
- entry authorization binding;
- all seven evidence hashes;
- no unrelated tracked changes;
- `.qwen/` untouched.

Do not rerun the start command.

Commit only the start artifact.

Suggested commit:

`governance: start Generation 4 Phase 7`

## Task 8 — Final verification and stop

Run focused tests and a bounded repository suite.

Confirm:

- Phase 7 started;
- Phase-7 performance evaluation still unauthorized;
- production readiness false;
- live trading false;
- final holdout reuse false;
- candidate search/mutation false;
- `RECON-009=OPEN`;
- no real Phase-7 evaluation has run.

Report:

- all implementation commits;
- frozen start implementation commit;
- start-contract commit;
- start-artifact commit;
- test counts;
- real start-readiness result;
- final start artifact;
- confirmation no provider/bundle/key/performance evaluation occurred.

Stop.

The next separately governed task is to design and freeze `GENERATION4-PHASE7-EVALUATION-CONTRACT-v1` before any Phase-7 durability/walk-forward performance run.
