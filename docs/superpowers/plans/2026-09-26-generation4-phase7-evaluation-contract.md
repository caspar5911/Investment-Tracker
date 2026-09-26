# Generation-4 Phase-7 Evaluation Contract Implementation Plan

Date: 2026-09-26

Spec:
`docs/superpowers/specs/2026-09-26-generation4-phase7-evaluation-contract-design.md`

Goal: Build and freeze the Generation-4 Phase-7 durability/evaluation protocol without inspecting new Phase-7 performance, then prepare an Independent Audit authorization handoff. No provider access or performance evaluation is allowed before that independent authorization exists.

## Global constraints

- Branch:
  `governance/phase6-successor-dividend-normalization-v3`
- Required starting design commit:
  `9f17e4810ee4a9e364ce2447c3ea7d9c778f1b7b`
- Required Phase-7 start artifact commit:
  `6a8df5367ac6bb1e4cfe02c625ee53963443f996`
- Do not touch `.qwen/`.
- Do not modify Stage-B frozen files.
- Do not modify `phase7_entry.py`, `phase7_entry_cli.py`, `phase7_start.py`, or `phase7_start_cli.py`.
- Do not rerun acquisition or Phase-6 final-holdout evaluation.
- Do not read/decrypt the Phase-6 sealed bundle or key.
- Do not access Generation-4 holdout symbols QQQM/FALN/IIPR/PSTL/EFAS.
- Do not access any symbol outside the exact Phase-7 research universe.
- Do not call OpenD/provider APIs until the later Independent Audit evaluation authorization exists.
- Do not inspect Phase-7 performance before the evaluation contract and authorization are frozen.
- Do not search candidates, tune parameters, substitute symbols, or change methodology.
- Do not create broker/trade/order functionality.
- Keep production/live trading false.
- Keep `RECON-009=OPEN`.
- DQ-030-dependent fields remain UNKNOWN unless a separately authoritative resolution is already bound.

## Frozen identities

Candidate:

`G2-A|lookback=189|skip=21|top_k=1|rebalance=21`

Research universe, exact order:

`GLD, IEF, IWM, QQQ, SPY, TLT, VNQ, XLP`

Benchmark:

`SPY`

Friction cases:

`0, 3, 10, 25, 50`

Primary friction:

`3`

Prospective checkpoints:

`63, 126, 252` scored sessions

Maximum warmup:

`210` sessions

---

## Task 1 — Evaluation-contract model and Phase-7 preflight

Files:

- Create:
  `src/investment_tracker/independent_audit/post_generation3/phase7_evaluation.py`
- Create:
  `tests/independent_audit/test_generation4_phase7_evaluation.py`

### RED

Write synthetic tests first for:

- valid Phase-7 start artifact and start contract;
- wrong start-artifact schema/status;
- `phase7_started=false`;
- `phase7_performance_evaluation_authorized=true` before authorization;
- production/live authority true;
- `RECON-009 != OPEN`;
- `paper_only != true`;
- wrong candidate/binding/implementation;
- wrong split/dividend/evaluator hashes;
- reordered research universe;
- extra/substituted symbol;
- any Generation-4 holdout symbol included;
- wrong benchmark;
- wrong friction cases/primary friction;
- wrong warmup cap;
- wrong checkpoints;
- adaptive walk-forward/reoptimization enabled;
- result-dependent changes enabled.

Expected RED: module/API absent.

### GREEN

Implement:

- `Generation4Phase7EvaluationError`;
- stable error-code constants;
- strict JSON/hash helpers;
- strict `Generation4Phase7EvaluationContract` Pydantic model using
  `ConfigDict(extra="forbid", frozen=True)`;
- `verify_generation4_phase7_evaluation_preflight(...)`.

Preflight validates start state and contract structure only.

It must not call a provider or calculate performance.

Status:

`GENERATION4_PHASE7_EVALUATION_PREFLIGHT_READY`

Commit:

`feat: verify Generation 4 Phase 7 evaluation preflight`

---

## Task 2 — Resolve and freeze prospective session boundary

Files:

- Modify `phase7_evaluation.py`;
- Modify tests.

### RED

Test:

- first prospective scored session is strictly later than
  `started_at_utc`;
- start timestamp on weekend/holiday resolves to next eligible XNYS session;
- boundary uses trading-calendar authority, not naive calendar-day arithmetic;
- warmup sessions precede scored start and are never scored;
- maximum warmup count is 210;
- prospective P&L cannot include any pre-start session.

Use synthetic calendars for unit tests where possible.

### GREEN

Implement a pure deterministic helper that receives a trading-session authority and start timestamp and resolves:

- exact first scored XNYS session;
- warmup boundary;
- scored boundary.

No market prices are read.

The exact resolved first scored session will later be written to the machine-readable evaluation contract.

Commit:

`feat: freeze Generation 4 Phase 7 prospective boundary logic`

---

## Task 3 — Fixed-strategy durability protocol primitives

Files:

- Create:
  `src/investment_tracker/quant/phase7/generation4_durability.py`
- Modify evaluation tests and/or create:
  `tests/quant/test_generation4_phase7_durability.py`

### RED

Prove:

- fixed candidate only;
- no candidate grid;
- no parameter input capable of changing 189/21/1/21;
- no training/reoptimization inside chronological subperiods;
- continuous portfolio state across diagnostic periods;
- exact friction cases 0/3/10/25/50;
- benchmark is SPY;
- metrics are deterministic;
- warmup excluded from scored P&L;
- exact scored-session alignment;
- exposure invariant enforced;
- incomplete data -> UNKNOWN/ABSTAIN rather than row dropping;
- DQ-030-dependent metrics remain UNKNOWN without bound resolution.

### GREEN

Implement only reusable fixed-protocol calculation helpers.

Prefer existing repository durability, benchmark, friction, and accounting primitives where semantically compatible.

Do not duplicate or modify the frozen strategy implementation.

No provider code in this task.

Commit:

`feat: add fixed Generation 4 Phase 7 durability protocol`

---

## Task 4 — Historical diagnostic lane

Files:

- Modify `generation4_durability.py`;
- Modify tests.

### RED

Tests must prove:

- output schema:
  `GENERATION4-PHASE7-HISTORICAL-DURABILITY-v1`;
- classification:
  `REUSED_HISTORY_DIAGNOSTIC_ONLY`;
- no historical report can claim new OOS/virgin evidence;
- no historical report can set production/live authority;
- no historical result changes candidate/methodology;
- incomplete corporate-action evidence -> UNKNOWN;
- 12/36/60-month windows only when complete;
- rolling/subperiod analysis never retrains;
- diagnostic lane cannot produce a production PASS.

### GREEN

Implement historical durability report construction from an already-validated dataset object supplied by the caller.

Do not add provider access.

If the older long-history dataset cannot support a metric, emit UNKNOWN with an explicit reason.

Commit:

`feat: report Generation 4 reused-history durability diagnostics`

---

## Task 5 — Prospective checkpoint lane

Files:

- Modify `generation4_durability.py`;
- Modify tests.

### RED

Tests for:

- schema:
  `GENERATION4-PHASE7-PROSPECTIVE-CHECKPOINT-v1`;
- fewer than 63 sessions remains pending;
- 63 sessions -> EARLY_DIAGNOSTIC;
- 126 -> INTERIM_DIAGNOSTIC;
- 252+ -> PRIMARY_PHASE7_ASSESSMENT eligibility;
- fewer than 252 sessions cannot return COMPLETE;
- no interpolation/synthetic future sessions;
- all five friction cases;
- SPY alignment exact;
- cash comparison exact;
- missing required evidence -> `PHASE7_UNKNOWN_ABSTAIN`;
- complete 252-session evidence ->
  `PHASE7_PROSPECTIVE_EVIDENCE_COMPLETE`;
- no automatic production/live authority on completion.

### GREEN

Implement status semantics exactly as the design.

Do not implement post-hoc profitability thresholds.

Commit:

`feat: add Generation 4 prospective Phase 7 checkpoints`

---

## Task 6 — Provider boundary implementation without real access

Files:

- Create:
  `src/investment_tracker/independent_audit/post_generation3/phase7_data.py`
- Add tests:
  `tests/independent_audit/test_generation4_phase7_data_boundary.py`

### RED

Use fakes/spies to prove:

- no provider object created before evaluation authorization validation;
- exact research universe only;
- order mismatch rejected;
- QQQM/FALN/IIPR/PSTL/EFAS rejected before provider creation;
- any unknown symbol rejected;
- request start cannot exceed warmup need;
- request end cannot exceed requested checkpoint cutoff;
- trade context never created;
- no order methods exist;
- append-only snapshot output;
- existing snapshot never overwritten;
- manifest includes provider/date/symbol/file hashes and
  `trading_context_created=false`.

### GREEN

Implement provider adapter boundary with lazy provider import.

Do not run it against OpenD.

Commit:

`feat: enforce Generation 4 Phase 7 data boundary`

---

## Task 7 — Read-only evaluation CLI and safety checks

Files:

- Create:
  `src/investment_tracker/independent_audit/post_generation3/phase7_evaluation_cli.py`;
- Modify tests;
- Update focused CI workflow.

Commands before Independent Audit authorization:

- `verify-evaluation-preflight`;
- `resolve-prospective-boundary`.

Do not yet expose a command that performs provider acquisition or calculates real performance unless it requires a strict evaluation authorization.

If adding post-authorization commands in the same implementation, they must be:

- `acquire-phase7-data`;
- `evaluate-phase7-checkpoint`;

and both must fail before provider/data access when authorization is absent/invalid.

No command may accept arbitrary symbols or parameter overrides.

Static forbidden API strings include trade/order APIs and trading contexts.

Run compile/focused/adjacent tests.

Commit and record exact evaluation implementation commit:

`feat: add Generation 4 Phase 7 evaluation boundary`

This becomes the frozen evaluation implementation commit.

Do not modify evaluation source after this point without regenerating the contract and audit request.

---

## Task 8 — Create machine-readable evaluation contract

Files:

- Create:
  `data/governance/successor/generation4-phase7-evaluation-contract.json`;
- Add repository tests.

Before writing the contract:

1. verify the current start artifact;
2. calculate start-artifact file SHA-256;
3. verify embedded start-artifact self-hash;
4. verify start-contract SHA-256;
5. calculate evaluation module/CLI/durability/data-boundary source hashes;
6. resolve exact first prospective scored XNYS session from the committed start timestamp;
7. do not fetch any market data.

The contract must contain exact values, not placeholders.

Required status:

`FROZEN_PRE_EVALUATION`

Required:

`phase7_performance_evaluation_authorized=false`

Commit separately:

`governance: freeze Generation 4 Phase 7 evaluation contract`

---

## Task 9 — Independent Audit evaluation-authorization handoff

Files:

- Create non-authorizing template:
  `data/governance/successor/generation4-phase7-evaluation-authorization.template.json`;
- Create request:
  `data/governance/successor/generation4-phase7-evaluation-independent-audit-request.json`;
- Create Markdown auditor request:
  `docs/superpowers/requests/2026-09-26-generation4-phase7-evaluation-independent-audit-request.md`.

Authorization schema:

`GENERATION4-PHASE7-EVALUATION-AUTHORIZATION-v1`

Template:

- authority `NONE`;
- status `DRAFT_TEMPLATE_NOT_AUTHORIZATION`.

Audit request must bind:

- frozen evaluation implementation commit;
- evaluation source hashes;
- evaluation contract SHA-256;
- start artifact SHA-256;
- entry authorization SHA-256;
- exact universe;
- prospective first scored session;
- warmup cap/checkpoints;
- methodology/friction identities;
- no-retuning governance.

The coordinator must not create the real evaluation authorization.

Commit handoff separately:

`audit: request Generation 4 Phase 7 evaluation authorization`

Stop.

---

## Task 10 — Independent Audit

A separate auditor must:

- inspect the frozen implementation and contract;
- confirm no Phase-7 performance was inspected before freeze;
- confirm exact prospective boundary;
- confirm no final-holdout reuse;
- confirm no adaptive walk-forward/reoptimization;
- run synthetic/focused tests;
- verify no provider call occurred pre-authorization;
- either reject or create:

`data/governance/successor/generation4-phase7-evaluation-authorization.json`

with schema:

`GENERATION4-PHASE7-EVALUATION-AUTHORIZATION-v1`

and status:

`GENERATION4_PHASE7_EVALUATION_AUTHORIZED`.

Even when approved:

- production=false;
- live trading=false;
- holdout reuse=false;
- search/tuning/substitution=false;
- RECON-009 OPEN;
- paper-only true.

Do not perform real provider access in the audit step.

---

## Task 11 — Post-authorization execution (not part of the pre-audit implementation run)

Only after a valid Independent Audit evaluation authorization exists:

1. run authorized data acquisition for exact research universe;
2. create append-only prospective snapshot;
3. optionally run reused-history diagnostic;
4. run prospective checkpoint only for actually available scored sessions;
5. if fewer than 252 sessions exist, status remains
   `PHASE7_PROSPECTIVE_EVIDENCE_PENDING`;
6. never adjust the frozen protocol in response to outputs.

Because Phase 7 started on 2026-09-26, the primary 252-session Phase-7 assessment necessarily requires future market sessions. No model estimate or backfill may substitute for them.

## Verification expectations

Before audit handoff:

- all new focused tests green;
- adjacent Generation-4 governance tests green;
- compileall green;
- static no-trading checks green;
- no provider call;
- no Phase-7 performance output produced;
- no final-holdout symbol accessed;
- no production/live authority;
- `.qwen/` untouched.

Full-suite legacy/resource failures must be reported separately and must not be hidden.
