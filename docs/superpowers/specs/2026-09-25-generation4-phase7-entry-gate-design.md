# Generation-4 Phase-7 Entry Gate Design

Date: 2026-09-25

Status: APPROVED DESIGN; IMPLEMENTATION NOT YET AUTHORIZED BY THIS DOCUMENT

## 1. Purpose

Build a Generation-4-specific, read-only Phase-7 entry gate and Independent
Audit authorization workflow. The gate must prove that the completed
Generation-4 Phase-6 evidence is intact and remains within its frozen
governance boundary before a separate Independent Auditor may authorize entry
into paper-only Phase 7.

The implementation must not itself authorize Phase 7. It must not create
production readiness, live-trading authority, brokerage access, a retry of the
final holdout, a new candidate search, a symbol substitution, or a
holdout-dependent methodology or parameter change.

## 2. Verified starting state

The design is based on repository branch
`governance/phase6-successor-dividend-normalization-v3` at authorization commit
`ca9a3043ff49522ad06b68ea6888ceab39080117`. At design time, the remote branch,
local branch, and local `HEAD` all resolve to that commit.

Generation-4 terminal identifiers are:

- generation: `GENERATION_4`;
- candidate: `G2-A|lookback=189|skip=21|top_k=1|rebalance=21`;
- binding SHA-256:
  `fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b`;
- implementation SHA-256:
  `35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b`;
- locked symbols, in frozen order: `QQQM`, `FALN`, `IIPR`, `PSTL`, `EFAS`;
- holdout ID:
  `successor-phase6-holdout-e6aa1f4e9f04b2e905df7cc828c65669`;
- release ID:
  `successor-phase6-release-934966d25eef0b2bfb4b5de289539a05`;
- Phase-6 status:
  `PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE`;
- Phase-7 eligibility: true;
- Phase-7 authorization: false;
- production readiness: false;
- `RECON-009`: `OPEN`;
- paper-only: true.

The private evidence directory is external to the repository. The gate may
read the named JSON evidence, but it must not read the encrypted bundle or key,
decrypt data, call a provider, compute performance, or rerun evaluation.

## 3. Design choice

Implement a dedicated Generation-4 boundary under
`investment_tracker.independent_audit.post_generation3`. Do not extend the
generic `quant.phase7.readiness` helper into a Generation-4 authority and do not
reuse the Generation-2 Phase-7 authorization schema.

The Generation-2 gate is a design reference only. It does not bind the
Generation-4 acquisition receipt, release, one-time consumption marker,
terminal closure, dividend-v3 methodology identities, or the Generation-4
authorization request.

The new boundary has two separate operations:

1. `verify_generation4_phase7_readiness` proves the Phase-6 chain is eligible
   for Independent Audit review. Its result is non-authorizing.
2. `evaluate_generation4_phase7_entry` repeats readiness verification and then
   requires a valid Independent Audit authorization bound to the exact frozen
   implementation, request, and evidence chain.

Neither operation writes an artifact or changes state.

## 4. Components and file ownership

### 4.1 Evidence and authorization verifier

Create
`src/investment_tracker/independent_audit/post_generation3/phase7_entry.py`.

This module owns:

- stable Generation-4 Phase-7 schemas, statuses, and error codes;
- strict JSON loading and SHA-256 helpers;
- read-only verification of the Generation-4 Phase-6 terminal chain;
- the strict Independent Audit authorization model and loader;
- the non-authorizing readiness function;
- the final entry-evaluation function.

It must not expose an authorization writer, sealer, signer, or mutation API.

### 4.2 Command-line boundary

Create
`src/investment_tracker/independent_audit/post_generation3/phase7_entry_cli.py`.

It exposes only:

- `verify-readiness`;
- `evaluate-entry`.

Both commands accept explicit artifact paths, emit one JSON object to stdout,
and perform no writes. Failure must return a nonzero exit code and a stable
`FORBIDDEN` response. Output must contain identities, hashes, and governance
state only; it must not emit Phase-6 performance metrics.

The existing Generation-4 Stage-B CLI and all source files whose identities
are frozen in the acquisition authorization remain byte-unchanged.

### 4.3 Tests and CI

Create
`tests/independent_audit/test_generation4_phase7_entry.py` and add it to the
focused Generation-4 workflow in
`.github/workflows/successor-dividend-normalization-v3.yml`.

Tests use synthetic JSON artifacts and temporary paths. They do not contain or
read protected historical observations. A separate local verification command
may point the CLI at the real private JSON artifacts after the synthetic suite
passes.

### 4.4 Audit handoff artifacts

After the implementation is tested and committed, create:

- `data/governance/successor/generation4-phase7-entry-authorization.template.json`;
- `data/governance/successor/generation4-phase7-entry-independent-audit-request.json`;
- `docs/superpowers/requests/2026-09-25-generation4-phase7-entry-independent-audit-request.md`.

The template is explicitly non-authorizing. The request records
`authority_granted=false`, `phase7_authorized=false`, and the frozen
implementation commit and evidence identities. These handoff artifacts are
committed separately from the implementation so the request can cite the
already-frozen implementation commit.

No real Phase-7 authorization artifact is created by the coordinator.

## 5. Readiness inputs

The readiness verifier receives explicit paths for:

- frozen Generation-4 Phase-6 evaluation contract;
- committed Generation-4 acquisition authorization;
- frozen holdout selection;
- virginity attestation and evidence;
- private acquisition receipt;
- private release;
- private Phase-6 result;
- private one-time consumption marker;
- private Phase-6 closure.

The final entry evaluator additionally receives:

- the committed Independent Audit request;
- the auditor-created Phase-7 entry authorization.

Paths are never discovered using globs. The encrypted bundle, key, acquisition
start marker, provider SDK, and market-data endpoints are outside the Phase-7
gate interface.

## 6. Readiness validation

Every condition below is mandatory. Missing, malformed, extra-authority, or
inconsistent evidence fails closed.

### 6.1 Frozen Phase-6 contract

The contract must verify under the Generation-4-compatible Phase-6 verifier
and must retain:

- schema `SUCCESSOR-PHASE6-EVALUATION-CONTRACT-v2`;
- status `FROZEN_PRE_ACCESS`;
- authority `INDEPENDENT_AUDIT`;
- successor `GENERATION_4`;
- the exact candidate, binding, implementation, strategy parameters, and
  ordered locked symbols from Section 2;
- the frozen split-v2, dividend-v3, and evaluator identities;
- candidate search and parameter mutation forbidden;
- retry after historical access forbidden;
- symbol substitution after access forbidden;
- Phase 7 unauthorized;
- production readiness unapproved;
- `RECON-009` open;
- paper-only true.

### 6.2 Acquisition authorization and receipt

The existing Generation-4 acquisition-authorization loader must accept the
committed v2 authorization against the frozen contract, selection, and
virginity evidence. This revalidates all Stage-B implementation and methodology
identities without making a provider call.

The receipt must satisfy the existing receipt verifier and must match the
contract and acquisition authorization for candidate, binding,
implementation, methodology identities, ordered protected symbols, contract
hash, and holdout ID. It must state:

- sealed bundle created;
- final holdout accessed;
- performance not computed or inspected;
- retry not allowed;
- readback verified.

Receipt verification reads only the receipt JSON. It does not read the sealed
bundle or key.

### 6.3 Release

The release must satisfy the existing release verifier and match the contract
and receipt for:

- holdout and release IDs;
- candidate, binding, implementation, and methodology identities;
- exact ordered locked symbols;
- contract SHA-256;
- acquisition receipt file SHA-256;
- sealed bundle and key hashes recorded by the receipt;
- one-time evaluation authority;
- Phase 7 false, production readiness false, `RECON-009` open, and paper-only
  true.

This verification does not consume or reopen the release.

### 6.4 Evaluation result

The result must be a JSON object with:

- schema `SUCCESSOR-PHASE6-FINAL-HOLDOUT-EVALUATION-v2`;
- authority `COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE`;
- status exactly
  `PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE`;
- the same Generation-4, contract, candidate, binding, implementation,
  methodology, holdout, release, and ordered-symbol identities;
- `one_time_consumed=true`;
- `candidate_search_executed=false`;
- `candidate_parameters_changed=false`;
- `holdout_symbol_substitution_executed=false`;
- `phase7_authorized=false`;
- `phase7_started=false`;
- `production_readiness_approved=false`;
- `recon009_status=OPEN`.

The verifier ignores performance values for authorization purposes and must not
copy them into its report.

### 6.5 Consumption marker

The marker must retain:

- schema `SUCCESSOR-PHASE6-HOLDOUT-CONSUMPTION-v1`;
- status `FINAL_HOLDOUT_RELEASE_CONSUMED`;
- the same release, holdout, candidate, and contract identities;
- evaluation status exactly equal to the required successful Phase-6 status;
- evaluation-result SHA-256 equal to the actual result file;
- result readback verified;
- retry not allowed.

### 6.6 Closure

The closure must retain:

- schema `SUCCESSOR-PHASE6-FINAL-HOLDOUT-CLOSURE-v1`;
- authority `COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE`;
- the required successful Phase-6 status;
- the same Generation-4, candidate, binding, implementation, methodology,
  ordered-symbol, holdout, and release identities;
- exact file hashes for the Phase-6 contract, acquisition receipt, release,
  evaluation result, and consumption marker;
- `holdout_consumed=true`;
- `retry_authorized=false`;
- `symbol_substitution_authorized=false`;
- holdout-dependent methodology changes forbidden;
- holdout-dependent parameter changes forbidden;
- `eligible_for_independent_entry_review=true`;
- `authorized=false` before audit;
- `entry_artifact_created=false`;
- `started=false`;
- production readiness false;
- `RECON-009` open.

### 6.7 Readiness result

Only after all checks pass, return a report with schema
`GENERATION4-PHASE7-ENTRY-READINESS-v1` and status
`GENERATION4_PHASE7_READY_FOR_INDEPENDENT_AUDIT`.

The report includes the frozen identities and actual file hashes needed by the
auditor. It also states:

- `authority_granted=false`;
- `phase7_authorized=false`;
- `phase7_started=false`;
- `production_readiness_approved=false`;
- `live_trading_authorized=false`;
- `recon009_status=OPEN`;
- `paper_only=true`.

Readiness is evidence for review, not permission to enter Phase 7.

## 7. Independent Audit authorization schema

The real authorization schema is
`GENERATION4-PHASE7-ENTRY-AUTHORIZATION-v1`, with status
`GENERATION4_PHASE7_ENTRY_AUTHORIZED` and authority `INDEPENDENT_AUDIT`.

Unknown fields are forbidden. The authorization must include:

- auditor-issued authorization ID, signer identity, and approval timestamp;
- generation `GENERATION_4`;
- a 40-character lowercase hexadecimal implementation commit;
- SHA-256 of the committed audit-request JSON;
- SHA-256 identities of `phase7_entry.py` and `phase7_entry_cli.py`;
- candidate, binding, strategy implementation, split normalizer, dividend
  reconciliation, and evaluator identities;
- exact ordered locked symbols;
- holdout and release IDs;
- file hashes for the Phase-6 contract, receipt, release, result, consumption
  marker, and closure;
- the exact successful Phase-6 status;
- `one_time_consumed=true`;
- `phase7_entry_authorized=true`;
- `phase7_started=false`;
- `retry_authorized=false`;
- `holdout_reuse_authorized=false`;
- `candidate_search_authorized=false`;
- `symbol_substitution_authorized=false`;
- `result_dependent_methodology_change_allowed=false`;
- `result_dependent_parameter_change_allowed=false`;
- `production_readiness_approved=false`;
- `live_trading_authorized=false`;
- `recon009_status=OPEN`;
- `paper_only=true`.

The authorization loader recomputes the request, gate, CLI, and evidence-file
hashes and compares every bound value with a fresh readiness report. The
implementation commit is provenance for the auditor-reviewed code; current
source-byte hashes remain the runtime drift check because the request and
future authorization necessarily live in commits after the implementation
commit.

The template uses a distinct template schema, authority `NONE`, and status
`DRAFT_TEMPLATE_NOT_AUTHORIZATION`; it must be rejected by the loader.

## 8. Final entry result

`evaluate_generation4_phase7_entry` first performs a fresh readiness
verification. It then loads and validates the Independent Audit authorization.

On success it returns schema `GENERATION4-PHASE7-ENTRY-DECISION-v1` and status
`GENERATION4_PHASE7_ENTRY_ALLOWED`. The report binds the authorization ID,
implementation commit, request hash, evidence-chain hashes, candidate,
holdout, and release. It must continue to report:

- `phase7_started=false`;
- `production_readiness_approved=false`;
- `live_trading_authorized=false`;
- `recon009_status=OPEN`;
- `paper_only=true`.

This report permits only the separately governed start of paper-only Phase 7.
It does not itself mark Phase 7 started and grants no production or trading
authority.

## 9. Failure behavior

All failures raise a Generation-4-specific exception carrying a stable code.
The minimum code families are:

- `GEN4_PHASE7_EVIDENCE_INVALID`;
- `GEN4_PHASE7_GOVERNANCE_MISMATCH`;
- `GEN4_PHASE7_IDENTITY_MISMATCH`;
- `GEN4_PHASE7_CHAIN_MISMATCH`;
- `GEN4_PHASE7_AUTHORIZATION_MISSING`;
- `GEN4_PHASE7_AUTHORIZATION_INVALID`;
- `GEN4_PHASE7_AUTHORIZATION_MISMATCH`.

The verifier must distinguish a missing authorization from malformed or
mismatched authorization, but none of those states may produce a partially
allowed result. Missing evidence, unknown fields in the authorization, a hash
read error, or any unrecognized status fails closed.

## 10. TDD and verification

Implementation follows red-green-refactor. Tests must first fail because the
new API is absent, then cover at least:

1. a complete synthetic chain reaches non-authorizing readiness;
2. every required Phase-6 result boolean and exact status fails independently;
3. closure eligibility false, authorization true-before-audit, entry-artifact
   created, or started true fails;
4. production readiness true or `RECON-009` other than `OPEN` fails at every
   applicable layer;
5. candidate, binding, implementation, methodology, symbol order, holdout, or
   release mismatch fails;
6. tampering with receipt, release, result, marker, or closure bytes breaks the
   hash chain;
7. retry, symbol substitution, candidate search, methodology change, or
   parameter change authority fails;
8. missing authorization and the non-authorizing template fail;
9. unknown authorization fields and wrong authority fail;
10. request, source, implementation-commit, or evidence binding drift fails;
11. a valid synthetic Independent Audit authorization permits entry while
    production, live trading, and `RECON-009` remain unchanged;
12. CLI failures are nonzero and expose no performance metrics;
13. the actual repository without a real authorization remains forbidden;
14. source-bound Stage-B acquisition files remain unchanged;
15. static governance checks find no trading/order API and no provider or
    evaluation command in the new Phase-7 boundary.

After focused tests pass, run the full repository test suite. Then run the
readiness CLI once against the existing private JSON evidence. Do not pass the
bundle or key, and do not run acquisition or evaluation commands.

## 11. Freeze and audit handoff

The implementation freeze sequence is:

1. complete TDD and verification;
2. commit source, tests, and CI as the implementation commit;
3. confirm the committed source hashes and clean tracked worktree;
4. run the real-evidence `verify-readiness` operation from that commit;
5. create the non-authorizing JSON and Markdown Independent Audit request and
   authorization template, binding the implementation commit and readiness
   hashes;
6. commit only those handoff artifacts;
7. provide the exact auditor prompt and both commit IDs to the user.

The coordinator stops there. Independent Audit must review the frozen
implementation and evidence and either reject the request or create a separate
real authorization artifact. The coordinator must not create, populate, sign,
or simulate that real authorization as repository evidence.

## 12. Explicit non-goals

This work does not:

- rerun acquisition or final-holdout evaluation;
- decrypt or inspect the sealed holdout bundle;
- tune, select, replace, or search candidates or symbols;
- alter strategy parameters, split-v2, dividend-v3, or Phase-6 methodology;
- mark Phase 7 started;
- close `RECON-009`;
- approve production readiness;
- add brokerage credentials, order APIs, execution, or live trading.
