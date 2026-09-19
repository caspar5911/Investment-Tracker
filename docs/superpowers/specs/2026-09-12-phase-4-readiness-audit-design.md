# Phase 4 Readiness Audit Design

**Status:** Approved design for implementation

**Date:** 2026-09-12

**Scope:** A bounded, provider-free readiness audit. This phase does not perform
strategy discovery, candidate evaluation, parameter search, or promotion.

## Objective

Establish whether the repository is ready to begin a separately approved Phase
4 research campaign by:

1. explaining and verifying the Phase 2 bootstrap interval `[0.0, 0.0]`;
2. freezing exactly 136 authoritative Phase 2 trial identities without counting
   preliminary and final representations as separate trials;
3. freezing the Phase 4 TRAIN/VALIDATION split over the Phase 3 universe; and
4. freezing Phase 4 search limits and methodology before any strategy research.

Successful completion produces `PHASE_4_READY` and stops. It does not authorize
Phase 4 strategy discovery.

## Governing Constraints

- Preserve TPC-v1.2, REPLAY-v1.0, CALC-v1.2, and ROBUST-v1.0 unchanged.
- Preserve every historical Phase 2 and Phase 3 artifact byte-for-byte.
- Keep FINAL_HOLDOUT sealed.
- Do not access HACK, SOXX, NLR, URNM, or GEV.
- Do not download market data or call a provider.
- Do not perform external strategy research.
- Do not create strategy families, run parameter searches, or evaluate new
  strategy candidates.
- Do not introduce brokerage, account, position, funds, trading-context, or
  order APIs.
- Keep all outputs research-only and unable to mutate canonical tracker state.
- Treat QFQ normalized prices as research simulation inputs, not historical
  executable fills.
- Do not implement unadjusted-price or corporate-action accounting in this
  audit.

## Frozen Inputs

### Phase 2 corrected campaign

The authoritative corrected Phase 2 campaign is identified as:

`PHASE2-CORRECTED-2010-2022-c33fb075`

Its deterministic representation selector is the conjunction of:

- `candidate_manifest.git_commit ==
  c33fb0757f0ea8147749130fed90d278aed4fafe`;
- `candidate_manifest.engine_version ==
  QUANT-ENGINE-v1+SEARCH-POLICY-v2`;
- `candidate_manifest.schema_version == RESEARCH-CANDIDATE-MANIFEST-v1`;
- `record.schema_version == QUANT-EXPERIMENT-v1`; and
- the final complete-evidence validation metric schema, including `loss_rate`.

Timestamps, directory traversal order, file names, lexical ordering, and file
modification times must not participate in authoritative representation
selection.

The preserved historical artifact population is:

- 4 original representations at engine version `QUANT-ENGINE-v1`;
- 136 preliminary representations at source revision
  `d4b2dfc3bee03ad81e389cc2e21876f38fbf325f`; and
- 136 final complete-evidence representations at source revision
  `c33fb0757f0ea8147749130fed90d278aed4fafe`.

The preliminary and final corrected-campaign populations contain the same 136
candidate IDs. The final selector must yield exactly one authoritative
representation for each of those 136 candidate IDs.

The preliminary reference population is selected explicitly by source revision
`d4b2dfc3bee03ad81e389cc2e21876f38fbf325f`, engine version
`QUANT-ENGINE-v1+SEARCH-POLICY-v2`, and absence of the final complete-evidence
`loss_rate` field. It is used only to verify candidate-set equality; it is never
authoritative. Original representations are selected explicitly by engine
version `QUANT-ENGINE-v1` and are neither part of the expected corrected set nor
authoritative. Classification that matches more than one representation class
is invalid.

### Phase 3 universe

The only admissible Phase 3 universe manifest is:

`de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76`

The only admissible DQ snapshot is:

`2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75`

The frozen universe, in order, is:

1. SPY
2. QQQ
3. IWM
4. TLT
5. IEF
6. GLD
7. VNQ
8. XLP

The split manifest may depend only on that universe manifest, that DQ snapshot,
and these eight normalized dataset identities:

| Symbol | Normalized dataset SHA-256 |
|---|---|
| SPY | `1d52b313f43dcbe35ded7ab88d403b97e40e82b822b4eaa4aa29552cca5dc0c5` |
| QQQ | `ee3379ac167c4403044c1b36196bf3b2f7e6a85f72ec2f2a8fd5a5dd6b812ed2` |
| IWM | `f4095f49b54455e6fcde42b8dedea58f3723973998fd298d685c49ff991dbb03` |
| TLT | `0e52e47f1dacbc01060ff8178429065d1bf02c8181d705ca8fa5e908e2660ab7` |
| IEF | `a6e7573713d114ef171a43f9c6d4fca9911af0b9dcb39093adb210176fc686e4` |
| GLD | `faa0bff3a8afa09f5bd16c7fd21c0b93b6a4dfbc01e9f7567f70b68f7aeb523b` |
| VNQ | `104349e90a0b823f3980d2df25f88fcd291395e6986addc65eecabf90a17acba` |
| XLP | `986b5949ddef81d603de79e664b63c9ce69d0ba4cbe1a984ef736cbafe16785f` |

No discovery, fallback, latest-version lookup, cache search, or provider call may
replace any frozen input.

## Architecture

Add an isolated `investment_tracker.quant.readiness` package. It consumes
explicit immutable artifact identities and produces content-addressed readiness
artifacts. It must not be imported by the Phase 2 research workflow or Phase 3
universe campaign.

The package has six responsibilities:

- constants: frozen campaign IDs, versions, limits, split dates, and hashes;
- models: frozen, extra-forbid readiness evidence models;
- trials: deterministic authoritative representation selection and trial
  identity;
- bootstrap audit: verification of an already implemented statistic without
  changing it;
- split/config: provider-free construction of frozen Phase 4 manifests; and
- artifacts/report: immutable writes, readback verification, and the readiness
  report.

The readiness orchestrator must accept explicit filesystem roots and the exact
frozen input identities. It may read only local Phase 2 experiment artifacts and
the referenced Phase 3 manifest/snapshot/datasets. It has no data-provider
dependency or provider factory.

## Bootstrap Evidence Audit

### Implemented statistic

`bootstrap_interval()` estimates a percentile interval for the sample median of
individual daily equal-weight portfolio returns.

The Phase 2 call uses:

- input observations: daily percentage changes of the aggregate equal-weight
  validation equity curve after dropping its first missing change;
- resampling unit: one daily portfolio return, sampled independently with
  replacement;
- statistic per resample: median;
- bootstrap samples: 2,000;
- PRNG: `numpy.random.default_rng(0)`;
- lower percentile: 5.0;
- upper percentile: 95.0; and
- percentile implementation: NumPy percentile defaults used by the frozen
  implementation.

The function rejects fewer than two observations, non-finite observations,
fewer than 100 draws, and invalid percentile bounds. A finite degenerate or
zero-inflated sample is admissible and may legitimately return a point
interval.

### Phase 2 observed result

The authoritative source artifact for this bootstrap audit is fixed as:

- kind: `phase2_experiment`;
- normalized repository-relative path:
  `results/experiments/risk_managed_trend-ee8a71fb71e3d80f-20260911T194002253141Z-bcabf074.json`;
- exact-byte content SHA-256:
  `438dda42ceacece3c7d3b73512d9898017a4c180e1b368cdc7c6dee299f5d4b5`;
- canonical artifact identity:
  `3e72fc05aa1c5d9e0ceca4a935ebb6672cd068d4bdf67b16c5d4fbbb121a797e`;
  and
- embedded candidate-manifest digest:
  `378720494019e8904b50222a60f950c99307d57b27a4e40614f4641b8413cc3b`.

No other experiment artifact, candidate, timestamp-selected file, or synthetic
fixture may substitute for this source.

The cache-only reconstruction from that artifact's exact strategy parameters,
execution assumptions, split, and three embedded immutable dataset hashes
contains 1,007 daily return observations:

- 288 negative;
- 368 exactly zero; and
- 351 positive.

The observed sample median is exactly zero. With the frozen seed and 2,000
resamples, all 2,000 resampled medians are exactly zero. The 5th and 95th
percentiles are therefore both exactly `0.0`.

The ordered input vector uses schema `BOOTSTRAP-INPUT-VECTOR-v1`. Every value is
converted to its exact Python `float.hex()` representation of the IEEE-754
binary64 value, preserving order, signed zero, and the precise binary value. The
canonical vector payload is:

```json
{"dtype":"IEEE-754-binary64","schema_version":"BOOTSTRAP-INPUT-VECTOR-v1","values_hex":["<ordered float.hex() values>"]}
```

Its canonical JSON uses lexically sorted keys, separators `,` and `:` without
additional whitespace, UTF-8, preserved Unicode, and rejection of non-finite
numbers. The SHA-256 of the canonical payload bytes is frozen as:

`878b8400fcf93776feda23c454182d36dca5efd4c32f51d2aa232abf003bf0b5`

Readiness construction must reproduce all 1,007 values from the pinned source
and its embedded dataset identities, verify this vector digest before
bootstrapping, and persist the full canonical vector as new versioned readiness
evidence. A missing source artifact, altered source bytes, unavailable embedded
dataset, parameter mismatch, observation-count mismatch, or vector-digest
mismatch fails closed. It must not fall back to a controlled fixture.

The experiment JSON stores ordinary finite JSON numbers. The report displays
those stored values without rounding them to zero. The calculation,
serialization, and report agree.

### Classification and permitted claims

The result is mathematically valid for the specifically implemented
median-daily-return statistic. No bootstrap implementation repair is permitted
or required by this audit.

The point interval must not be described as confidence in CAGR, Sharpe, total
return, profitability, robustness, candidate quality, or future performance.
It is not decision-grade evidence. Readiness evidence must identify the narrow
statistic and the exact resampling assumptions wherever `[0.0, 0.0]` appears.

Regression tests must preserve deterministic behavior, the zero-inflated point
interval, validation errors for sparse/non-finite inputs, and full-precision
serialization. Tests must not alter Phase 2 artifacts.

## Authoritative Trial Identity

### Identity domains

Trial identity and artifact identity are separate domains:

- **Trial identity** answers which candidate attempt counts against research
  multiplicity and budget.
- **Artifact identity** identifies one serialized representation of evidence
  for that trial.

The authoritative trial identity is the lowercase hexadecimal SHA-256 of the
UTF-8 bytes of canonical JSON:

```json
{"campaign_id":"PHASE2-CORRECTED-2010-2022-c33fb075","candidate_id":"<candidate_id>"}
```

Canonical JSON means keys sorted lexically, separators `,` and `:` with no
additional whitespace, Unicode preserved, and no non-finite numbers.

Artifact digest, experiment ID, candidate-manifest digest, creation time, and
path must not affect trial identity.

Artifact identity is the lowercase hexadecimal SHA-256 of the UTF-8 bytes of
the following canonical JSON envelope:

```json
{"content_sha256":"<sha256 of exact artifact bytes>","kind":"<artifact kind>","path":"<normalized repository-relative POSIX path>"}
```

The envelope uses lexically sorted keys, separators `,` and `:` without
additional whitespace, preserved Unicode, and no non-finite numbers. The
`content_sha256` field is the lowercase hexadecimal SHA-256 of the exact bytes
stored at `path`. The path must be relative to the repository root, use `/`
separators, contain no drive prefix, leading `/`, empty component, `.` or `..`,
and resolve without symlink traversal. The kind is a versioned controlled
identifier. Changing bytes, path, or kind therefore changes artifact identity
without changing trial identity.

### Deterministic representation admission

The authority builder reads every preserved Phase 2 experiment artifact,
validates its schema and embedded candidate manifest, and classifies each
representation using the frozen selector above. It must then:

1. form the expected candidate-ID set from the preliminary corrected-campaign
   representations;
2. require that set to contain exactly 136 unique candidate IDs;
3. require the final authoritative candidate-ID set to equal the expected set;
4. require exactly one authoritative representation per candidate ID; and
5. emit exactly 136 unique trial identities.

If an expected candidate is missing, a candidate has multiple authoritative
representations, an unexpected candidate is present, a digest is invalid, or
the count differs from 136, construction fails closed. It must not select a
newest, oldest, first, or last representation.

The authority artifact records every trial identity, campaign ID, candidate ID,
authoritative artifact identity, non-authoritative representation identities,
selector version, source revisions, and aggregate counts. Historical artifacts
remain in place.

## Search-Aware Statistical Boundary

All search-aware consumers must operate on the authoritative 136-trial set,
never raw artifact count.

The 136 trials are historical Phase 2 multiplicity and research-lineage
evidence. They do not consume, offset, reduce, seed, or otherwise alter the
Phase 4 operational candidate budget. Phase 4 begins with exactly zero new
candidate trials consumed and may add at most 3,000 new candidate trials under
its own campaign identity. Reports and APIs must expose the two counts as
separate named fields; they must never expose a combined `136 + new` value as
Phase 4 budget consumption.

The readiness layer may prepare deterministic, trial-keyed inputs for:

- campaign trial count;
- multiple-testing count;
- Deflated Sharpe Ratio inputs;
- Probability of Backtest Overfitting inputs; and
- future search-budget accounting.

Duplicate preliminary/final/original representations of the same campaign and
candidate cannot add rows, trials, statistics, or budget consumption.

This audit does not implement Deflated Sharpe Ratio or PBO estimators. Their
result status must be `NOT_IMPLEMENTED`, and any decision-level interpretation
must be `UNKNOWN`. Missing, malformed, ambiguous, or insufficient inputs also
produce `UNKNOWN` and a machine-readable reason. No normal approximation,
heuristic penalty, proxy statistic, silently reduced matrix, or fabricated
precision is permitted.

Regression tests must prove that adding duplicate representations leaves the
trial count, multiple-testing count, ordered Sharpe input identities, ordered
PBO input identities, and search-budget count unchanged. Tests must also prove
that DSR/PBO result requests fail closed as `UNKNOWN/NOT_IMPLEMENTED`. Separate
budget tests must prove that the historical count remains 136 while Phase 4
consumption starts at zero, and that the first Phase 4 trial consumes budget
position one rather than position 137.

## Frozen Phase 4 Temporal Split

**Split policy version:** `PHASE4-TEMPORAL-SPLIT-v1`

The calendar partitions are:

- TRAIN: 2014-01-02 through 2018-12-31; and
- VALIDATION: 2019-01-01 through 2022-12-30.

For each of the eight frozen datasets, the actual validated provider-session
coverage within those partitions is:

- TRAIN: 1,258 sessions, 2014-01-02 through 2018-12-31; and
- VALIDATION: 1,008 sessions, 2019-01-02 through 2022-12-30.

The 2019 calendar boundary remains 2019-01-01 even though the first validated
XNYS/provider session is 2019-01-02. No row crosses the calendar partition.

### Validation warm-up and reset semantics

Phase 4 validation may expose observations strictly earlier than the first
VALIDATION session only as read-only lagged-indicator warm-up. Earlier
observations may initialize rolling windows, exponential state, or equivalent
causal indicator state whose value at a VALIDATION session depends only on
observations earlier than or equal to that session.

Warm-up data must not:

- fit, optimize, calibrate, select, or alter parameters;
- contribute TRAIN returns, equity, P&L, fills, trades, positions, turnover,
  exposure, or performance metrics to VALIDATION;
- carry a TRAIN position, pending order, cash balance, cost basis, or portfolio
  state into VALIDATION;
- use TRAIN performance to select a candidate, parameter, warm-up length, or
  validation treatment; or
- emit a TRAIN-dated signal for execution in VALIDATION.

Immediately before VALIDATION, the simulated portfolio resets to the frozen
initial cash with zero positions, zero pending orders, zero turnover, zero
realized P&L, and no inherited cost basis. The first signal eligible for scoring
must be timestamped on an actual VALIDATION session. Execution may occur only
on the next eligible VALIDATION session under the frozen
`COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN` convention. If there is no next eligible
VALIDATION session, no execution occurs.

VALIDATION metrics begin from the reset initial capital and contain no TRAIN
P&L. Tests must demonstrate that changing TRAIN prices outside the causal
warm-up needed for the first VALIDATION indicator does not change reset
portfolio state, that no TRAIN performance field reaches validation selection,
and that signals/executions before their eligible VALIDATION sessions are
rejected. This audit freezes these semantics but does not execute a strategy.

The split manifest records:

- split-policy version;
- Phase 3 universe artifact identity and digest;
- Phase 3 DQ snapshot identity and digest;
- ordered selected symbols;
- exact normalized dataset identity for each symbol;
- declared TRAIN and VALIDATION ranges;
- actual first/last validated session and row count per dataset and partition;
- `final_holdout_accessed: false`;
- `provider_calls: 0`; and
- its canonical content digest.

Construction must hash-verify and read back every dependency. Any mismatched
symbol, order, digest, row count, boundary, missing session within an admitted
dataset, or extra dependency prevents a split manifest from being written.

## Frozen Phase 4 Campaign Configuration

**Configuration version:** `PHASE4-CAMPAIGN-CONFIG-v1`

Freeze these upper bounds before strategy research:

- maximum new strategy families: 10;
- maximum candidate trials per family: 500; and
- maximum aggregate new candidate trials: 3,000.

Phase 4 operational budget state is initialized as:

- `historical_phase2_trial_count: 136`;
- `phase4_new_trials_consumed: 0`;
- `phase4_new_trials_remaining: 3000`; and
- `phase4_historical_trials_consume_budget: false`.

Only future candidates created under the Phase 4 campaign identity may
increment `phase4_new_trials_consumed`. Preliminary, final, or original Phase 2
representations cannot increment it.

The configuration also freezes:

- frozen universe digest:
  `de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76`;
- Phase 4 split-manifest identity;
- `signal_series: QFQ`;
- `execution_series: QFQ_NORMALIZED`;
- `decision_grade: false`;
- `external_strategy_research_performed: false`;
- `strategy_search_executed: false`;
- `final_holdout_accessed: false`;
- `protected_symbols_accessed: []`;
- `provider_calls: 0`; and
- `live_trading_capability: false`.

The aggregate limit is independent of the per-family product. Consumers must
enforce all three limits and stop at the first applicable bound. This audit only
freezes the configuration; it does not exercise a search budget.

## Immutable Artifacts

Use canonical SHA-256 and write-once/readback-verified storage under
`results/phase4/readiness/` for:

- bootstrap audit evidence;
- the full canonical 1,007-observation bootstrap input-vector evidence;
- Phase 2 trial-authority manifest;
- Phase 4 split manifest;
- Phase 4 campaign configuration;
- Phase 4 readiness manifest; and
- a human-readable readiness report.

The readiness manifest links all other readiness artifacts and records their
digests, source revision, dependency identity, safety flags, and final status.
An existing path may be reused only when its bytes are identical. A collision
or hash mismatch is fatal.

The final status is `PHASE_4_READY` only when all input identities, trial
authority, bootstrap audit, split, configuration, artifact readback, tests, and
safety scans pass. Any missing decision-critical readiness evidence produces a
fail-closed status with an explicit reason.

## Data Flow

```text
preserved Phase 2 experiment artifacts
        |
        v
deterministic representation classification
        |
        v
136 canonical trial identities --------> search-aware input boundary

frozen Phase 3 universe manifest
        + frozen DQ snapshot
        + eight exact normalized datasets
        |
        v
provider-free split verification
        |
        v
frozen split manifest
        |
        v
frozen Phase 4 campaign configuration

bootstrap audit + trial authority + split + configuration
        |
        v
readiness manifest and report
```

No arrow in this flow reaches a provider, FINAL_HOLDOUT, strategy generator,
optimizer, backtest campaign, promotion registry, canonical tracker state, or
trading API.

## Failure Semantics

The readiness audit fails closed for:

- bootstrap evidence that cannot reproduce the stored statistic;
- any attempt to generalize the bootstrap interval beyond its declared
  statistic;
- ambiguous or missing authoritative trial representations;
- an authoritative trial count other than 136;
- artifact/trial identity conflation;
- an unimplemented search-aware statistic represented as a number;
- any Phase 3 universe, snapshot, or dataset identity mismatch;
- any split boundary or session-count mismatch;
- an altered campaign limit or QFQ methodology flag;
- a provider-call path;
- protected-symbol or FINAL_HOLDOUT access;
- historical artifact mutation; or
- introduction of a trading/account/order path.

Errors must be explicit and machine-readable. Silent fallback, best-effort
selection, approximation, timestamp-based selection, and partial readiness are
not permitted.

## Test Requirements

Use test-driven implementation. Tests must cover:

### Bootstrap

- deterministic seeded bootstrap;
- zero-inflated observations yielding the exact `[0.0, 0.0]` median interval;
- all 2,000 frozen-seed resampled medians being zero for the audited fixture;
- sparse and non-finite observation rejection;
- invalid draw and percentile rejection;
- no rounding or serialization mutation; and
- rejection of broader confidence claims in the audit model;
- exact-byte and canonical-envelope verification of the pinned authoritative
  source artifact;
- exact reconstruction of the 1,007 ordered returns from its embedded inputs;
- canonical `float.hex()` vector serialization and frozen vector digest; and
- failure rather than fallback when the pinned artifact or vector mismatches.

### Trial authority

- canonical trial-identity hashing over campaign ID and candidate ID;
- trial identity differing from artifact identity;
- explicit selector admission for the corrected final representation;
- preliminary/original representation exclusion;
- independence from timestamp, file name, and input order;
- missing, duplicate, and unexpected authoritative representation rejection;
- exactly 136 authoritative trials from the preserved evidence fixture;
- duplicate representations not inflating campaign or multiple-testing count;
- duplicate representations not inflating DSR/PBO input identity sets;
- duplicate representations not inflating future budget consumption; and
- DSR/PBO status remaining `UNKNOWN/NOT_IMPLEMENTED`.

### Split and configuration

- exact Phase 3 universe, snapshot, symbol order, and eight dataset hashes;
- no fallback or latest-artifact discovery;
- exact declared and actual session boundaries;
- exact 1,258/1,008 per-symbol partition counts;
- disjoint TRAIN/VALIDATION partitions;
- TRAIN-only causal indicator warm-up without fitting or performance leakage;
- portfolio reset to initial cash and zero positions before VALIDATION;
- exclusion of TRAIN P&L from all VALIDATION metrics;
- first scored signal on a VALIDATION session and execution only on the next
  eligible VALIDATION session;
- content-addressed split/config/readiness manifests;
- immutable write collision, path-traversal, and symlink rejection;
- fixed limits 10/500/3,000;
- separate historical count 136 and Phase 4 consumed count zero;
- first future Phase 4 trial consuming budget position one, not 137;
- QFQ/QFQ_NORMALIZED and `decision_grade: false`;
- no provider dependency or call;
- FINAL_HOLDOUT and protected-symbol denial; and
- no strategy or trading imports.

## Verification

Before reporting readiness, run:

- focused Phase 4 readiness tests;
- authoritative trial-count regression tests;
- bootstrap regression tests;
- complete quant test suite;
- all runnable repository tests;
- Python compilation;
- dependency consistency check;
- readiness artifact validation and readback;
- split-manifest digest verification;
- trial-authority digest and count verification;
- protected-symbol source and cache scan;
- FINAL_HOLDOUT access scan;
- forbidden trading API scan;
- historical Phase 2/3 artifact digest comparison; and
- `git diff --check`.

The known Windows symlink privilege failure remains an environment limitation.
Its test must not be weakened, skipped, or changed to claim a green repository
suite.

## Completion Report

The completion report must state:

1. the exact cause and scope of the Phase 2 `[0.0, 0.0]` interval;
2. whether the bootstrap implementation is valid and whether a repair occurred;
3. the authoritative campaign and exact 136-trial count;
4. proof that duplicate representations do not inflate search-aware inputs;
5. DSR and PBO status;
6. declared and actual TRAIN/VALIDATION ranges;
7. split-manifest path and digest;
8. campaign-configuration path and digest;
9. frozen universe and DQ snapshot digests;
10. limits 10/500/3,000;
11. QFQ methodology and `decision_grade: false`;
12. external-research, strategy-search, provider-call, FINAL_HOLDOUT,
    protected-symbol, and live-trading statuses;
13. tests and any remaining environment failures; and
14. commits.

If every readiness gate passes, report `PHASE_4_READY` and stop. Do not begin
Phase 4 strategy discovery automatically.
