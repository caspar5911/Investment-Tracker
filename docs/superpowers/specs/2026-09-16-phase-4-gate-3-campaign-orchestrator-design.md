# Phase 4 Gate 3 campaign orchestrator design

## Status and boundary

This is a PRE-CAMPAIGN design written after the sealed Gate 3 result-schema
authority and before candidate #1. Starting revision is
`ab6e7f592990621179bb7a12a131393674ee783b`.

This design does not inspect candidate VALIDATION performance, rank candidates,
select a survivor, change the frozen 180-candidate population, alter Gate 1
policy, alter Gate 2 execution, alter Gate 3 authorities, alter the sealed
execution methodology, or alter the sealed campaign-result schema. The
orchestrator is an additive subsystem under
`investment_tracker.quant.phase4.gate3_runner`.

The design checkpoint is `GATE3_CAMPAIGN_ORCHESTRATOR_DESIGN_FROZEN`.
The implementation checkpoint is `GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE`.
Neither checkpoint executes candidate #1.

## Exact dependencies

The orchestrator binds and revalidates these exact authorities:

- Gate 1 manifest content
  `dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89`.
- Gate 2 engine manifest content
  `c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6`.
- Corrected Gate 3 authority content
  `705935c9b06b8f592e66e5e71e4541d910b585be6e9a30e46b99fe97b7591d4f`.
- Gate 3 execution-methodology content
  `9c37e20ccc54132716c3e347b8005d097500a14aeba41d9eedeaf28de3ebe877`.
- Gate 3 result-schema manifest content
  `70cabdd78bb5f473fbb94f969c21fd5add185ccc46f00fb217c2b415f404fa96`.
- Result-schema contract content
  `efd5b3a4eb4d77d2cf6f68ad875376b75443e642e3439d698035a3253a3c0979`.
- Candidate population digest
  `15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3`.
- Frozen scored market-panel digest
  `410465adf5765cb2d316eda1d00d718c99f4aa8c3634ce99cda00d11a08496c0`.
- Exact TRAIN and VALIDATION partition identities already linked by those
  authorities.

No dependency is selected by timestamp, directory order, glob, or "latest".

## Architecture

New files live only under:

```text
src/investment_tracker/quant/phase4/gate3_runner/
  __init__.py
  models.py
  dependencies.py
  state.py
  orchestrator.py
  methodology.py
  cli.py
```

The sealed `gate3_campaign` result-schema package remains byte-identical.
The runner imports its exact authority loader, typed result model, validator,
evidence derivation, result store, and result-schema preflight.

Responsibilities:

- `dependencies.py` loads the result-schema authority plus the exact frozen
  TRAIN warm-up panel. The already-sealed scored panel is reused unchanged.
- `models.py` defines frozen runner-plan, attempt, receipt, completion and
  preflight models.
- `state.py` provides deterministic no-overwrite position state. It never
  rewrites a prior position.
- `orchestrator.py` generates fixed targets, performs deterministic replays,
  derives typed evidence and accounts positions.
- `methodology.py` seals the runner source/spec/dependency authority and
  preflights it by explicit content hash.
- `cli.py` exposes `seal`, `preflight`, and a gated `run`. The `run`
  command refuses to begin unless the explicit runner-manifest preflight is
  `GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE`.

The presence of a gated run entrypoint in the sealed runner source is not an
execution event. The runner seal itself carries the zero-execution safety state.

## Frozen market input

The runner reconstructs TRAIN warm-up and VALIDATION from the exact eight
sealed Phase 3 bar artifacts already bound by the split manifest.

TRAIN warm-up uses the 1,258 TRAIN sessions. VALIDATION uses the exact sealed
1,008-session scored panel from the result-schema authority. Actual frozen OPEN
and CLOSE columns are loaded for TRAIN; strategy target generation only consumes
combined close history through `ScoredMarketInput`.

The reconstructed scored member must be byte-for-byte semantically equal to the
already-bound scored panel and must reproduce panel digest
`410465adf5765cb2d316eda1d00d718c99f4aa8c3634ce99cda00d11a08496c0`.
Any mismatch fails before candidate execution.

TRAIN contributes indicator history only. Every replay starts with the sealed
100000 cash, zero positions, zero pending state and zero P&L on VALIDATION.
There is no TRAIN replay or TRAIN P&L.

## Candidate traversal and budget semantics

The authoritative traversal is the exact Gate 2 binding tuple in immutable
budget-position order 1 through 180. No other sort is permitted.

Each evaluated position is budget-consumed immediately before its first
evaluation attempt. This is represented by a deterministic no-overwrite
`ATTEMPT_STARTED` record derived only from runner authority plus the sealed
binding identity. Re-entering an already-created identical attempt record does
not consume a second position.

A governed `SKIPPED_FAMILY_STOP` position is accounted but not evaluated and
does not create an evaluation attempt.

An attempted position must end in exactly one immutable result receipt. A
campaign with an attempt record but no receipt is an interrupted evaluation and
may resume that same position; it may not advance to another position first.

A receipt that already resolves to a validated result prevents duplicate
evaluation.

## Fixed candidate execution

For one candidate binding:

1. Generate exactly one target slot for every scored session by calling sealed
   `generate_target(authority, binding, market_input, offset)`.
2. The strategy layer itself enforces its sealed rebalance clock, completed
   session-t CLOSE information and next-session due timestamp.
3. Replay the identical target vector at exactly
   `(0, 3, 10, 25, 50)` bps with `replay_targets`.
4. Construct the exact canonical equal-weight benchmark at 3 bps and cash
   benchmark at 0 bps.
5. Evaluate all immediate sealed grid neighbors independently at PRIMARY
   3 bps using each neighbor's own sealed binding and the same frozen
   `ScoredMarketInput`.
6. Pass the five candidate replays, benchmarks and neighbor observations to
   the already-sealed `derive_evidence`.
7. Build `PHASE4-GATE3-CANDIDATE-RESULT-v1` with provenance from
   `make_provenance`, status `EXECUTED`, reason `OK`, and the derived
   evidence.
8. Publish only through `ResultArtifactStore.write_result`, which revalidates
   the complete typed result.

No runner metric, threshold, ranking or survivor implementation exists.

## Neighborhood authority resolution

Immediate-neighbor robustness is an independent robustness evaluation of each
sealed neighbor binding. It is not dependent on whether that neighbor's own
campaign position has already executed.

This is determined by the already-sealed result-schema authority:

- `Dependencies.neighbors(binding)` derives membership from the sealed family
  grid only.
- `derive_evidence` accepts typed `NeighborObservation` replays directly.
- `_neighborhood` recomputes neighbor metrics against the common canonical
  benchmark and rejects missing/injected membership.

Therefore the runner may evaluate a neighbor as a robustness case even when
the neighbor's population position is later in campaign order. That robustness
replay does not create or consume the neighbor's campaign-position result and
does not alter family-stop state.

## Family-stop state

Family-stop behavior is exactly the existing Gate 1 policy:

`PERSISTENT_OOS_FAILURE` is 50 consecutive attempted same-family observations
whose PRIMARY benchmark-excess return is non-positive or unavailable.

- Positive benchmark excess resets the streak to zero.
- Other robustness failures do not increment or terminate the family.
- `UNKNOWN` and `ABSTAIN` observations contribute unavailable benchmark
  excess when such governed statuses already exist.
- A system/evaluation error is not an OOS observation.

When a streak reaches 50, the exact 50 candidate-result artifact identities
ending at the trigger position are frozen as the stop witness. Every later
population position in that same family is written as
`SKIPPED_FAMILY_STOP/PERSISTENT_OOS_FAILURE` and references that same trigger
window. Skips never enter the streak.

Because the fixed population is family-contiguous, a stop cannot cross a family
boundary. The runner revalidates this property before execution.

## Status behavior

Production execution normally produces:

- `EXECUTED` for a completed typed evaluation; or
- `SKIPPED_FAMILY_STOP` after a governed family stop.

The orchestrator does not invent `UNKNOWN` or `ABSTAIN` from generic
exceptions. Those statuses remain available only when a separately governed
upstream condition explicitly supplies them.

Any unexpected strategy, data, accounting, evidence, filesystem or validation
exception creates one typed `CAMPAIGN_EXECUTION_FAILED` result for the
attempted position when provenance can be constructed, publishes its receipt,
and aborts the entire campaign. A subsequent invocation sees that failure and
fails closed; it never skips past it.

## Append-only state and resume

Authoritative candidate result bytes stay in the existing content-addressed
result store.

The runner adds deterministic per-position operational state:

```text
results/phase4/gate3/campaign/
  attempt/position-0001.json
  ...
  receipt/position-0001.json
  ...
```

Attempt and receipt files are canonical JSON, repository-contained,
no-overwrite, exact-byte verified, and protected against symlink/junction/path
escape. They are indexes/state, not replacements for the content-addressed
candidate-result artifact.

Attempt content is fully predetermined from runner authority + candidate
binding, so an interrupted write can be reproduced exactly.

Receipt content binds the exact result artifact identity. A second receipt for
one position is forbidden.

Resume rules:

- receipt present + valid result: never reevaluate;
- attempt present + no receipt: reevaluate only that same position;
- receipt without attempt for an evaluated status: fail closed;
- campaign failure receipt: fail closed permanently for this campaign;
- next unaccounted position is the first position without receipt after all
  earlier positions are validly accounted.

No directory enumeration decides authority; position paths are derived
directly from 1..180.

## Completion

A campaign is result-complete only when all 180 deterministic receipt paths are
present and every receipt resolves to a validated result whose provenance
position/candidate/trial identity matches the sealed binding.

Completion requires:

- exactly 180 accounted positions;
- no duplicate receipt;
- no missing position;
- no unauthorized candidate;
- no `CAMPAIGN_EXECUTION_FAILED` receipt.

The runner may then publish a separate immutable campaign-result-set manifest
binding the ordered 180 result artifact identities and a canonical aggregate
digest. It does not rank or select survivors. The terminal campaign-execution
checkpoint is `GATE3_CAMPAIGN_RESULTS_COMPLETE`.

## Runner authority seal

Before any real candidate run, a separate additive runner authority binds:

- this exact specification;
- implementation source bundle and full Git source revision;
- exact Gate 1/Gate 2/Gate 3 manifests;
- execution-methodology manifest;
- result-schema manifest and contract;
- candidate-population digest and count;
- TRAIN and VALIDATION identities;
- scored-panel digest;
- survivor/durability/family-stop policy identities;
- deterministic traversal and state schema versions;
- zero-execution safety state.

The explicit-hash preflight revalidates all dependencies and source bytes and
returns only `GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE`. It calculates no
candidate or benchmark performance.

## Security and prohibited surfaces

The runner has no provider/download/network market-data client, no Moomoo or
brokerage import, no account/funds/position/order context, no export-to-trading
surface, no FINAL_HOLDOUT path, and no protected-symbol path.

Protected symbols remain `HACK, SOXX, NLR, URNM, GEV`; the exact frozen
eight-symbol market panel is the only admitted market universe.

The subsystem contains no optimizer, candidate generator, parameter mutation,
ranking, survivor selection or Phase 5 behavior.

## Verification gates

Implementation is RED -> GREEN -> regression -> commit -> independent review ->
runner seal.

Synthetic tests must cover exact traversal, target/fill timing, five friction
cases, TRAIN-only warm-up, benchmark construction, independent neighbor
robustness, family-stop streak/reset/witness behavior, attempt/receipt
idempotency, interrupted resume, duplicate prevention, campaign failure,
filesystem redirects, explicit-hash preflight and prohibited imports.

A fresh independent review must report zero Critical and zero Important issues
before the runner authority is sealed.

No real candidate is executed by design, implementation, review, seal or
preflight.
