# Generation-4 Phase-7 Start Boundary Design

Date: 2026-09-26

Status: APPROVED DESIGN TARGET; IMPLEMENTATION NOT YET PRESENT

## 1. Purpose

Create the smallest governed transition that records Generation-4 Phase 7 as started after the already-approved Independent Audit entry authorization and the successful read-only entry decision.

This boundary is a deterministic state transition only. It does not create a second discretionary approval, does not change the candidate or methodology, does not inspect performance, and does not authorize production, live trading, final-holdout reuse, candidate search, parameter changes, symbol substitution, or result-dependent methodology changes.

The start artifact also does not itself authorize a Phase-7 performance run. Phase-7 durability/evaluation methodology must be frozen separately after the start transition and before any Phase-7 performance evaluation.

## 2. Verified starting state

Repository branch:

`governance/phase6-successor-dividend-normalization-v3`

Independent Audit authorization commit:

`646f8fb9e6b5f90cbd2aef2b6ed2f0e421641ccf`

Frozen Generation-4 Phase-7 entry implementation:

`7893306e3c77b85c59f044b787a55579593c678b`

Entry authorization:

- schema: `GENERATION4-PHASE7-ENTRY-AUTHORIZATION-v1`;
- authority: `INDEPENDENT_AUDIT`;
- status: `GENERATION4_PHASE7_ENTRY_AUTHORIZED`;
- authorization id: `INDEP-AUDIT-GEN4-PHASE7-ENTRY-20260926-QWEN-0001`;
- `phase7_entry_authorized=true`;
- `phase7_started=false`;
- production readiness false;
- live trading false;
- `RECON-009=OPEN`;
- paper-only true.

The read-only entry CLI has already returned:

`GENERATION4_PHASE7_ENTRY_ALLOWED`

with the same candidate, authorization ID, request hash, methodology identities, and seven evidence hashes.

## 3. Authority model

The Independent Audit entry authorization is the sole authority for entering Phase 7.

The start boundary does not invent a new Independent Audit decision. The coordinator may perform the transition only after the start implementation and start contract prove that the exact existing entry authorization remains valid.

The start artifact authority string is:

`COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION`

This means the coordinator records the transition under already-granted Independent Audit authority. It does not mean the coordinator may broaden that authority.

## 4. Architecture

Create:

- `src/investment_tracker/independent_audit/post_generation3/phase7_start.py`;
- `src/investment_tracker/independent_audit/post_generation3/phase7_start_cli.py`;
- `tests/independent_audit/test_generation4_phase7_start.py`.

After the implementation is frozen, create:

- `data/governance/successor/generation4-phase7-start-contract.json`.

The one-time start command then creates:

- `data/governance/successor/generation4-phase7-start.json`.

The start contract is committed before the start command is run. The start artifact is committed only after successful runtime verification.

## 5. Read-only readiness operation

Expose:

`verify_generation4_phase7_start_readiness(...)`

It must:

1. call the existing `evaluate_generation4_phase7_entry` with the real evidence paths, audit request, and Independent Audit authorization;
2. require status `GENERATION4_PHASE7_ENTRY_ALLOWED`;
3. require `phase7_entry_authorized=true`;
4. require `phase7_started=false`;
5. require production/live trading false;
6. require `RECON-009=OPEN`;
7. require paper-only true;
8. require the exact frozen candidate, binding, implementation, methodology identities, holdout/release IDs, and all seven evidence hashes;
9. compute the exact SHA-256 of the entry authorization file and the audit-request file;
10. report readiness only; it must not write a file.

Readiness status:

`GENERATION4_PHASE7_START_READY`

Readiness remains non-mutating.

## 6. Frozen start contract

Schema:

`GENERATION4-PHASE7-START-CONTRACT-v1`

Status:

`FROZEN_PRE_START`

Authority:

`COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION`

The contract must bind:

- generation `GENERATION_4`;
- exact candidate ID;
- exact binding SHA-256;
- exact strategy implementation SHA-256;
- split normalizer SHA-256;
- dividend reconciliation SHA-256;
- successor evaluator SHA-256;
- ordered locked symbols;
- holdout ID;
- release ID;
- Independent Audit authorization ID;
- entry-authorization file SHA-256;
- audit-request SHA-256;
- the seven Phase-6 evidence hashes;
- frozen Phase-7 entry implementation commit;
- Phase-7 entry gate source SHA-256;
- Phase-7 entry CLI source SHA-256;
- frozen Phase-7 start implementation commit;
- Phase-7 start module source SHA-256;
- Phase-7 start CLI source SHA-256.

Required governance literals:

- `phase7_entry_authorized=true`;
- `phase7_started=false`;
- `phase7_performance_evaluation_authorized=false`;
- `production_readiness_approved=false`;
- `live_trading_authorized=false`;
- `retry_authorized=false`;
- `holdout_reuse_authorized=false`;
- `candidate_search_authorized=false`;
- `parameter_mutation_authorized=false`;
- `symbol_substitution_authorized=false`;
- `result_dependent_methodology_change_allowed=false`;
- `result_dependent_parameter_change_allowed=false`;
- `recon009_status=OPEN`;
- `paper_only=true`.

The contract must use a strict Pydantic model with `extra="forbid"`.

The contract does not contain or authorize performance thresholds.

## 7. Runtime source binding

The start command must recompute the SHA-256 of:

- `phase7_entry.py`;
- `phase7_entry_cli.py`;
- `phase7_start.py`;
- `phase7_start_cli.py`;
- the committed entry authorization;
- the committed audit request;
- the start contract.

Any mismatch fails closed before the start artifact is created.

The start implementation commit in the contract is provenance. Source-byte hashes are the runtime drift control.

## 8. Start artifact

Schema:

`GENERATION4-PHASE7-START-v1`

Status:

`GENERATION4_PHASE7_STARTED`

Authority:

`COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION`

The artifact is canonical JSON and is created exclusively. Existing output must never be overwritten.

It must record:

- `started_at_utc`;
- generation, candidate, binding, and strategy implementation identities;
- all three methodology hashes;
- ordered locked symbols;
- holdout/release IDs;
- Independent Audit authorization ID;
- entry-authorization SHA-256;
- audit-request SHA-256;
- start-contract SHA-256;
- entry/start implementation commits and source hashes;
- all seven evidence hashes;
- `phase6_status=PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE`;
- `phase7_entry_authorized=true`;
- `phase7_started=true`;
- `phase7_performance_evaluation_authorized=false`;
- `production_readiness_approved=false`;
- `live_trading_authorized=false`;
- all retry/reuse/search/mutation/substitution/result-dependent-change flags false;
- `recon009_status=OPEN`;
- `paper_only=true`.

The artifact should include a deterministic self-hash computed over the canonical payload without the self-hash field.

## 9. Start command

CLI commands:

- `verify-start-readiness`;
- `start-phase7`.

Both use explicit evidence, request, authorization, and contract paths.

`verify-start-readiness` is read-only.

`start-phase7` may perform exactly one write: exclusive creation of the Phase-7 start artifact.

The command must fail if:

- the start artifact already exists;
- the entry decision no longer passes;
- the authorization/request/evidence/source hashes drift;
- the contract is malformed or has unknown fields;
- any governance prohibition changes;
- Phase 7 already appears started;
- production/live-trading authority is present.

No other output path or mutation command is allowed.

## 10. Failure semantics

Stable error families:

- `GEN4_PHASE7_START_EVIDENCE_INVALID`;
- `GEN4_PHASE7_START_ENTRY_INVALID`;
- `GEN4_PHASE7_START_CONTRACT_MISSING`;
- `GEN4_PHASE7_START_CONTRACT_INVALID`;
- `GEN4_PHASE7_START_BINDING_MISMATCH`;
- `GEN4_PHASE7_START_GOVERNANCE_MISMATCH`;
- `GEN4_PHASE7_ALREADY_STARTED`;
- `GEN4_PHASE7_START_WRITE_FAILED`.

Any missing or inconsistent evidence fails closed.

## 11. TDD requirements

Tests must cover at least:

1. valid synthetic entry chain reaches non-mutating start readiness;
2. missing/invalid Independent Audit authorization fails;
3. wrong authorization ID or authorization-file hash fails;
4. any of the seven evidence hashes drifting fails;
5. entry gate/start gate/start CLI source drift fails;
6. wrong implementation commit fails;
7. reordered locked symbols fails;
8. candidate/binding/implementation/methodology drift fails;
9. any retry/reuse/search/mutation/substitution/result-dependent-change flag becoming true fails;
10. production or live-trading authority fails;
11. `RECON-009` other than `OPEN` fails;
12. `paper_only` other than true fails;
13. unknown contract fields fail;
14. start artifact is created with `phase7_started=true` but performance evaluation false;
15. start artifact cannot be overwritten;
16. failure paths write nothing;
17. CLI exposes no acquisition, evaluation, provider, broker, order, or trading command;
18. start operation never reads the sealed bundle/key;
19. Stage-B and Phase-7 entry frozen source hashes remain unchanged;
20. real repository remains unstarted until the explicit start command is run.

## 12. Freeze sequence

1. implement start module/CLI/tests with RED -> GREEN TDD;
2. run focused and adjacent governance tests;
3. freeze the start implementation commit;
4. compute start-module and start-CLI source hashes;
5. create the machine-readable start contract binding that implementation;
6. commit the start contract separately;
7. run `verify-start-readiness` against the real JSON evidence;
8. run `start-phase7` once;
9. verify the produced artifact;
10. commit only the start artifact;
11. stop before any Phase-7 performance evaluation.

Any change to the start module or CLI after Step 3 requires a new implementation commit and regenerated start contract.

## 13. Phase-7 scope after start

The start artifact permits only the Phase-7 state transition and subsequent design/freeze of a Phase-7 durability/evaluation contract.

It does not itself authorize a performance run.

Before any Phase-7 historical or prospective performance evaluation, create and freeze a separate `GENERATION4-PHASE7-EVALUATION-CONTRACT-v1` specifying the exact data boundary, benchmark, friction cases, walk-forward/durability protocol, metrics, pass/fail or descriptive semantics, and no-tuning rules.

The existing candidate remains:

`G2-A|lookback=189|skip=21|top_k=1|rebalance=21`

and may not be changed based on Phase-6 or Phase-7 results.

## 14. Explicit non-goals

This work does not:

- rerun or reopen the final holdout;
- decrypt/read the bundle or key;
- call OpenD or any provider;
- inspect or use performance metrics for the start decision;
- search candidates;
- tune parameters;
- substitute symbols;
- change split/dividend/evaluator methodology;
- close `RECON-009`;
- approve production;
- authorize live trading or brokerage/order APIs;
- execute Phase-7 durability testing.
