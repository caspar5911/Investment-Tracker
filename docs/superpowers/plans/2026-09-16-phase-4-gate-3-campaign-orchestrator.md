# Phase 4 Gate 3 campaign orchestrator implementation plan

**Goal:** implement and seal the deterministic Gate 3 campaign runner without
executing candidate #1.

**Starting branch:** `codex/phase4-gate3-runner`

**Approved design:**
`docs/superpowers/specs/2026-09-16-phase-4-gate-3-campaign-orchestrator-design.md`

## Constraints

- Do not modify prior sealed Gate 1, Gate 2, Gate 3, execution-methodology or
  result-schema source/evidence.
- Add only `quant.phase4.gate3_runner` source, focused tests, runner spec/plan
  and new runner-authority evidence.
- No candidate execution during implementation or tests.
- No VALIDATION candidate performance inspection.
- No provider, protected-symbol, FINAL_HOLDOUT or trading path.
- No new metric, threshold, candidate, ranking rule or survivor rule.

## Task 1 - frozen runner dependencies and market input

Create:

- `src/investment_tracker/quant/phase4/gate3_runner/__init__.py`
- `dependencies.py`
- `tests/quant/test_phase4_gate3_runner_dependencies.py`

RED tests:

- explicit result-schema manifest digest must be accepted and substitutions
  rejected;
- Gate 3 authority, execution methodology and result-schema preflights must all
  pass;
- exact 180 bindings and positions 1..180;
- fixed population digest;
- exact scored panel digest;
- exact TRAIN 1258 / VALIDATION 1008 session identities;
- reconstructed scored panel equals the sealed result-schema scored panel;
- warm-up sessions are strictly earlier and the same frozen eight symbols;
- no protected symbol or provider surface.

GREEN:

- reuse `load_result_authority` and `load_dependencies`;
- reconstruct the exact TRAIN MarketPanel from pinned split/bar artifacts;
- compose one `ScoredMarketInput` with exact frozen TRAIN warm-up + sealed
  VALIDATION scored panel.

Commit:
`feat: bind Gate 3 runner dependencies`.

## Task 2 - append-only position state

Create:

- `models.py`
- `state.py`
- `tests/quant/test_phase4_gate3_runner_state.py`

Models:

- `AttemptRecord`
- `PositionReceipt`
- `CampaignResultSet`

Attempt:

- fixed campaign ID;
- position/candidate/trial/family identities;
- exact runner-manifest identity;
- state `ATTEMPT_STARTED`.

Receipt:

- fixed position/candidate/trial;
- result artifact identity;
- final typed result status.

State paths are deterministic per position and no-overwrite.

RED tests:

- same-byte write idempotent;
- unequal collision fails;
- receipt mismatch fails;
- receipt without matching candidate fails;
- symlink/junction/traversal fails;
- existing valid receipt prevents duplicate evaluation;
- interrupted attempt without receipt is recognized as resumable same-position
  work;
- position outside 1..180 fails.

Commit:
`feat: add append-only Gate 3 runner state`.

## Task 3 - deterministic candidate evaluator

Create/update:

- `orchestrator.py`
- `tests/quant/test_phase4_gate3_runner_orchestrator.py`

Provide small pure units:

- `generate_targets(context, binding)`
- `evaluate_binding(context, authority, binding)`
- `evaluate_neighbor(context, authority, neighbor_binding)`

RED synthetic tests:

- exactly one target slot per scored session;
- same sealed binding on all non-null targets;
- first target uses first scored CLOSE and next-session due;
- no same-bar fill;
- identical target vector is replayed at exactly 0/3/10/25/50 bps;
- PRIMARY = 3 bps;
- benchmark = canonical equal-weight 3 bps;
- cash = canonical zero-friction cash;
- immediate neighbors are exactly `deps.neighbors(binding)`;
- each neighbor uses its own binding and PRIMARY 3 bps;
- neighbor evaluation does not create campaign position state;
- evidence is derived only through sealed `derive_evidence`;
- completed result validates through `validate_result`;
- candidate/parameter/binding mutation fails.

Commit:
`feat: implement deterministic Gate 3 candidate evaluation`.

## Task 4 - traversal, family stop and resume

Extend:

- `orchestrator.py`
- focused runner tests.

Implement:

- exact position order 1..180;
- family-contiguity validation;
- attempt publication immediately before evaluation;
- result publication through `ResultArtifactStore`;
- receipt publication only after result read-back validation;
- resume from existing receipts;
- reevaluate only an attempt-without-receipt same position;
- fail closed on a preexisting `CAMPAIGN_EXECUTION_FAILED`;
- update OOS streak only from sealed `oos_outcome`;
- reset on positive excess;
- trigger at 50;
- write all later same-family positions as `SKIPPED_FAMILY_STOP` using the
  exact immutable 50-result trigger witness;
- never use skip records as OOS observations.

RED tests with an injected synthetic evaluator:

- 49 failures do not stop;
- 50th failure triggers;
- positive candidate resets;
- robustness-only failure with positive excess resets rather than increments;
- stop witness positions are exact trigger-49..trigger;
- later family resumes normally;
- interrupted run does not double-evaluate completed receipts;
- result order always equals population order;
- unexpected evaluator exception produces one
  `CAMPAIGN_EXECUTION_FAILED` result and aborts.

The real evaluator is never invoked in tests.

Commit:
`feat: orchestrate governed Gate 3 campaign traversal`.

## Task 5 - runner authority and gated CLI

Create:

- `methodology.py`
- `cli.py`
- `tests/quant/test_phase4_gate3_runner_methodology.py`

Runner manifest binds:

- orchestrator spec identity;
- exact runner source bundle;
- full source revision;
- Gate 1 / Gate 2 / corrected Gate 3 identities;
- execution-methodology identity;
- result-schema manifest and schema-contract identities;
- population digest/count;
- TRAIN / VALIDATION identities;
- scored market-panel digest;
- survivor / durability / family-stop policy identities;
- state/result-set schema versions;
- zero-execution safety state.

CLI:

- `seal --repository-root --source-revision`
- `preflight --repository-root --manifest-content-sha256`
- `run --repository-root --manifest-content-sha256`

`run` must first call the explicit-hash runner preflight. Tests invoke only
synthetic or rejected run paths; they never execute the real 180-candidate
evaluator.

Expected preflight:

`GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE`.

Commit implementation:
`feat: bind Gate 3 campaign runner without executing candidates`.

## Task 6 - verification and seal

Run on the on-prem worktree before sealing:

- focused runner tests;
- result-schema tests;
- Gate 3 execution/preparation tests;
- Gate 3 authority tests;
- Phase 4 regressions;
- `pytest -q tests/quant`;
- unchanged Windows symlink security test.

Require zero unexplained failures.

Perform independent post-commit review with 0 Critical / 0 Important.

From clean implementation HEAD:

```text
python -m investment_tracker.quant.phase4.gate3_runner.cli seal \
  --repository-root . \
  --source-revision <FULL_IMPLEMENTATION_HEAD>
```

Commit only new runner-authority evidence with:

`evidence: seal Gate 3 campaign runner`.

Then run runner explicit-hash preflight twice and require identical output.
Rerun prior three preflights unchanged.

Final checkpoint:

`GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE`

with candidate execution count zero.

Stop before candidate #1.
