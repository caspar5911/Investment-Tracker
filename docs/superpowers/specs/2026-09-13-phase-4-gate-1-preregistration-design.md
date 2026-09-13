# Phase 4 Gate 1 Research Governance and Preregistration Design

## Status and Scope

This document specifies Gate 1 of the Phase 4 autonomous strategy research
campaign. Gate 1 produces research governance and preregistration evidence
only. It does not implement or execute a strategy, load market bars, calculate
TRAIN or VALIDATION performance, inspect Phase 4 campaign results, access
`FINAL_HOLDOUT`, or authorize Gate 2 or Gate 3.

Gate 1 is one of three sealed subprojects:

1. **Gate 1 — Research governance and preregistration.** Research sources,
   fixed comparison baselines, immutable hypotheses, family definitions,
   complete parameter grids, budget policy, survivor policy, access policy,
   and a final preregistration seal.
2. **Gate 2 — Engine and strategy implementation.** An isolated
   `investment_tracker.quant.phase4` implementation that consumes the sealed
   Gate 1 definitions. Gate 2 may use synthetic data and TRAIN-only evidence
   but may not generate or inspect Phase 4 VALIDATION performance.
3. **Gate 3 — Campaign execution and selection.** A single execution of the
   already-preregistered candidate population, followed by the frozen
   survivor policy and selection of at most one research candidate.

Gate 1 implementation and execution require a separately approved plan. This
design itself does not seal Gate 1.

The intended deployed result of the campaign is **one fixed long-only
strategy** with one fixed rule set and one fixed parameter tuple that can
remain usable for many years without annual or periodic parameter retuning.
The already-frozen Phase 4 TRAIN/VALIDATION split in Authoritative Frozen
Inputs is unchanged by this deployment objective.

## Governing Principles

- Research is long-only, unlevered, paper-only, and incapable of brokerage,
  account, position, funds, order-routing, or live-trading operations.
- TPC-v1.2, REPLAY-v1.0, CALC-v1.2, and ROBUST-v1.0 remain unchanged.
- Existing Phase 2, Phase 3, and Phase 4 readiness artifacts are immutable.
- Missing decision-critical evidence fails closed to `UNKNOWN` or rejection.
- The goal is falsifiable, economically defensible evidence rather than the
  highest historical CAGR.
- Robustness and long-term durability take precedence over maximizing fitted
  CAGR. High sustainable long-term CAGR, potentially around 15–20% or more,
  is aspirational only; 20% is not an admission, eligibility, ranking, or
  promotion threshold.
- Annual or periodic parameter re-optimization is not part of the intended
  deployed strategy.
- At most one new Phase 4 candidate may eventually be selected.
- `NO_CREDIBLE_STRATEGY_FOUND` is a valid final Gate 3 outcome.
- QFQ inputs support normalized research comparison only. They are not
  evidence of executable historical broker fills.

## Authoritative Frozen Inputs

Gate 1 binds these values without opening the underlying market-bar files:

| Input | Frozen value |
|---|---|
| Phase 3 universe | `SPY`, `QQQ`, `IWM`, `TLT`, `IEF`, `GLD`, `VNQ`, `XLP` |
| Universe digest | `de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76` |
| DQ snapshot digest | `2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75` |
| TRAIN | 2014-01-02 through 2018-12-31; 1,258 sessions |
| VALIDATION declared | 2019-01-01 through 2022-12-30 |
| VALIDATION actual | 2019-01-02 through 2022-12-30; 1,008 sessions |
| Phase 4 readiness manifest content digest | `4305845b627ed2d369f3e16b26eb0e9ec724c13ea50904fcf5fd4113f264a254` |
| Phase 4 readiness manifest envelope identity | `25cea5b7cf490a4010244bd03968d342516bb27854b9488dbc9f9cdc2d375471` |
| Signal series | `QFQ` |
| Execution series | `QFQ_NORMALIZED` |
| Decision grade | `false` |
| New-family limit | 10 |
| Per-family candidate limit | 500 |
| Aggregate candidate limit | 3,000 |
| Initial Phase 4 consumption | 0 |
| Historical Phase 2 trials | 136; separate multiplicity lineage, not Phase 4 consumption |
| Protected-symbol deny-list | `HACK`, `SOXX`, `NLR`, `URNM`, `GEV` |
| DSR | `UNKNOWN / NOT_IMPLEMENTED / null` |
| PBO | `UNKNOWN / NOT_IMPLEMENTED / null` |

The Phase 4 readiness manifest was revalidated on `main` at revision
`b116192d2f8bc814a0f7501b492b981a5ae8f8db`. Its producing revision
`568ea5a35bb7acd88f9e79ad09a05788913872e4` is an ancestor of the current
revision.

No Gate 1 policy, implementation, or seal may change the frozen TRAIN or
VALIDATION boundary, session count, date range, dataset identity, or warm-up
semantics. A changed split is a prerequisite mismatch, not a new Gate 1 input.

## Architecture

Gate 1 is an isolated capability-limited subsystem. A future implementation
will live under:

```text
src/investment_tracker/quant/phase4/
  __init__.py
  preregistration/
    __init__.py
    access.py
    artifacts.py
    baselines.py
    canonical.py
    grids.py
    journal.py
    models.py
    policy.py
    provenance.py
    seal.py
```

Each unit has one responsibility:

- `access.py` admits only exact Gate 1 resources and records every admitted
  read. It rejects a path before opening it.
- `canonical.py` defines canonical JSON bytes, record digests, artifact
  envelopes, and portable repository-relative POSIX paths.
- `journal.py` verifies and appends hash-chained JSON Lines records.
- `models.py` contains frozen, extra-forbidden evidence schemas.
- `provenance.py` verifies the readiness prerequisite and Git-based Phase 2
  baseline provenance without reading market bars.
- `baselines.py` builds the four ineligible comparison-baseline definitions.
- `grids.py` expands complete declarative grids and assigns deterministic
  candidate and trial identities and Phase 4-only budget positions.
- `policy.py` validates source admission, hypothesis lifecycle, family-stop
  policy, fixed-strategy durability policy, survivor policy, and
  information-access policy.
- `artifacts.py` writes immutable content-addressed evidence and rejects
  collisions, symlinks, path escape, and byte mismatches.
- `seal.py` revalidates every dependency and publishes the final Gate 1
  manifest last.

Gate 1 must not import the existing research workflow, optimizer evaluator,
backtest engine, portfolio ledger, performance metrics, data repository,
Moomoo adapter, promotion code, StrategyBase exporter, or any trading SDK.
The existing `workflow.py`, scorer, optimizer, strategies, and frozen modules
remain unchanged.

## Trust and Information Boundaries

### Gate 1 permitted inputs

The Gate 1 read capability admits only:

- the exact committed Phase 4 readiness manifest path and bytes;
- the exact committed Phase 4 readiness trial-authority artifact identified
  below, parsed only for authority metadata, candidate IDs, and artifact
  identities;
- the exact Git commit and blob objects named by the baseline provenance
  policy;
- the Gate 1 source and hypothesis journals being verified or appended;
- the Gate 1 explanatory notes file;
- Gate 1 immutable artifacts already linked by the in-progress seal; and
- caller-supplied, normalized bibliographic source records created from
  external research.

The Phase 3 universe, DQ snapshot, split, and methodology are admitted as
identities already linked by the readiness manifest. Gate 1 does not reopen
their underlying Parquet, metadata, DQ, or session-level evidence.

### Gate 1 forbidden inputs

The access policy rejects before filesystem, cache, provider, or parser access:

- every file below `data/cache/`;
- Phase 4 TRAIN or VALIDATION bars, portfolios, metrics, candidate evidence,
  campaign output, rankings, leaderboards, reports, or exports;
- all `FINAL_HOLDOUT` resources;
- all protected-symbol resources;
- provider endpoints, Moomoo/OpenD contexts, network market-data clients,
  account APIs, trading contexts, and order functions;
- canonical tracker state and Google Sheet/control-plane writers; and
- dynamic paths, globs, directory discovery, timestamps, or “latest file”
  selection for authoritative dependencies.

The only permitted Phase 2 evidence is the fixed Git generator blob, the exact
pinned Phase 4 readiness trial-authority artifact, and the exact two executed
experiment artifact identities named below. Gate 1 does not enumerate Phase 2
files and does not read Phase 2 performance fields. The restricted
trial-authority parser returns only the authority schema/version/count,
candidate IDs, trial IDs, and artifact identity envelopes; it exposes no
numeric strategy-result field to baseline selection or sealing.

### Technical enforcement

The future Gate 1 implementation must provide all of these controls:

1. `Gate1ReadCapability` receives an exact tuple of normalized paths and Git
   object identities. It has no generic `open`, directory-list, glob, cache,
   provider, or URL-fetch method.
2. Every path is normalized and checked for repository containment and
   symlink components before any existence check or read.
3. An AST/import test fails if Gate 1 imports data providers, backtest,
   optimizer/evaluator, metrics, promotion/export, trading, brokerage, or
   canonical tracker writers.
4. An instrumented test filesystem fails if Gate 1 attempts any unlisted read,
   including a forbidden read that would otherwise fail because the file is
   absent.
5. The seal records the sorted exact read set and flags:

   ```text
   VALIDATION_DATA_ACCESS    = false
   VALIDATION_METRICS_ACCESS = false
   CAMPAIGN_RESULTS_ACCESS   = false
   FINAL_HOLDOUT_ACCESSED    = false
   PROTECTED_SYMBOLS_ACCESSED = []
   PROVIDER_CALLS            = 0
   STRATEGY_SEARCH_EXECUTED  = false
   LIVE_TRADING_CAPABILITY   = false
   ```

6. A non-empty/true safety field, an unexpected read, or evidence that Gate 3
   output already influenced the current journals returns
   `GATE1_INFORMATION_BOUNDARY_VIOLATION` and prevents a seal.
7. Gate 1 source ingestion is offline with respect to project providers.
   External web research is performed outside the executable subsystem; only
   normalized cited records enter the journal.

These controls are both structural and runtime-enforced. A comment or operator
attestation alone is insufficient.

## File Layout

Gate 1 creates only new files:

```text
results/research/
  sources.jsonl
  hypothesis_registry.jsonl
  research_notes.md
  campaigns/<replacement-campaign-id>/
    sources.jsonl
    hypothesis_registry.jsonl
    research_notes.md

results/phase4/gate1/
  baseline_definitions/sha256/<content-sha256>/baselines.json
  strategy_family_definitions/sha256/<content-sha256>/families.json
  deterministic_grids/sha256/<content-sha256>/grids.json
  family_budget_policy/sha256/<content-sha256>/policy.json
  durability_policy/sha256/<content-sha256>/policy.json
  survivor_policy/sha256/<content-sha256>/policy.json
  information_access_policy/sha256/<content-sha256>/policy.json
  phase4_preregistration_manifest/sha256/<content-sha256>/manifest.json
```

The JSONL files are genuine JSON Lines: one canonical JSON object plus `LF` per
record. JSONL content is not placed in a misleading `.json` file. The Markdown
notes are explanatory only; the JSONL journals are authoritative.

No mutable “latest” alias is authoritative. All sealed artifacts use exact
content-addressed paths. The final Gate 1 manifest links every authoritative
artifact by both content digest and canonical envelope identity.

The three top-level research files belong exclusively to the first Gate 1
campaign. If a sealed campaign needs a genuine correction, the replacement
uses the campaign-specific subdirectory shown above. The sealed top-level files
remain unchanged and continue to verify against the original manifest.

## Canonical Identities

Canonical JSON uses UTF-8, sorted object keys, compact separators, JSON
booleans/null, no NaN or infinity, no insignificant whitespace, and an ending
`LF` only where the JSONL format requires it. Timestamps are UTC RFC 3339 with
the `Z` suffix and microseconds.

Artifact identity remains distinct from domain identity:

- `content_sha256 = SHA-256(exact_file_bytes)`.
- `artifact_sha256 = SHA-256(canonical_json({content_sha256, kind, path}))`.
- `source_id = "source-" + SHA-256(canonical bibliographic identity)`.
- `hypothesis_id = "phase4-hypothesis-" + SHA-256(canonical hypothesis
  payload excluding timestamp and journal fields)`.
- `family_id = "phase4-family-" + SHA-256(canonical semantic family payload
  excluding family_id, rule_set_sha256, timestamps, journal fields, artifact
  fields, and observed evidence)`.
- `candidate_id = "phase4-" + SHA-256(canonical_json({campaign_id,
  hypothesis_id, family_id, parameters}))`.
- `trial_id = SHA-256(canonical_json({campaign_id, candidate_id}))`.

The fixed-strategy identities use canonical projections rather than an
implementation-defined pairing:

```text
rule_set_sha256 = SHA-256(canonical_json({
  schema_version: "PHASE4-RULE-SET-IDENTITY-v1",
  family_id,
  input_fields,
  warmup_rule,
  signal_algorithm,
  ranking_algorithm,
  allocation_algorithm,
  cash_rule,
  risk_rule,
  rebalance_rule,
  execution_timing_rule,
  long_only_no_leverage_invariants,
  regime_partition_algorithm,
  implementation_interface
}))

parameter_tuple_sha256 = SHA-256(canonical_json({
  schema_version: "PHASE4-PARAMETER-TUPLE-IDENTITY-v1",
  family_id,
  parameters
}))

candidate_parameter_population_sha256 = SHA-256(canonical_json([
  {candidate_id, parameter_tuple_sha256}, ...
]))
```

The population array uses exact sealed family/grid/budget order and contains
every Phase 4 candidate exactly once.

`parameters` is the exact type-tagged, canonical parameter map stored in the
sealed grid row; binary64 values use the already-required canonical hexadecimal
representation. No default, environment value, runtime fit, or omitted
parameter may enter this identity.

The rule-set projection includes every field capable of changing signals,
ranking, allocation, exposure, state transition, rebalance timing, or order
eligibility. It excludes human labels, prose rationale, citations, expected
results, failure-regime prose, timestamps, journal fields, artifact paths,
expanded grid values, and observed metrics. Evaluation-only controls such as
fold boundaries, friction scenarios, bootstrap settings, reporting horizons,
and survivor ranking do not change strategy decisions and are excluded from
`rule_set_sha256`; they are frozen independently by the split, durability, and
survivor artifact identities and must remain constant within their declared
evaluation case.

Every family record stores and rederives `rule_set_sha256`. Every expanded grid
row stores and rederives `parameter_tuple_sha256`; its candidate identity is
also rederived from the same canonical parameters. Candidate evidence in Gate
3 must bind both digests. A changed algorithmic field changes
`rule_set_sha256`; a changed parameter changes `parameter_tuple_sha256` and
`candidate_id`. No timestamp, filename, filesystem order, or observed result
participates in either identity.

The full 64 hexadecimal digits are stored even when a human-facing label uses
a short prefix. Duplicate representations of one `trial_id` never consume
another budget position or statistical row.

## Hash-Chained Append-Only Journals

### Record envelope

Every `sources.jsonl` and `hypothesis_registry.jsonl` line has this envelope:

```json
{
  "schema_version": "PHASE4-JOURNAL-RECORD-v1",
  "record_kind": "SOURCE|HYPOTHESIS",
  "record_id": "stable-domain-id",
  "recorded_at": "UTC timestamp",
  "predecessor_digest": "64 lowercase hexadecimal digits",
  "payload": {},
  "record_digest": "64 lowercase hexadecimal digits"
}
```

The first record uses 64 zeroes as `predecessor_digest`. `record_digest` is the
SHA-256 of the canonical envelope excluding `record_digest`. Each later record
must name the immediately preceding `record_digest`.

### Append protocol

Before append, the journal writer:

1. rejects a symlink, non-regular file, path escape, non-UTF-8 bytes, missing
   final `LF`, blank line, or noncanonical record;
2. verifies every record ID, digest, predecessor link, and domain payload from
   genesis to terminal record;
3. rejects duplicate domain IDs and duplicate record digests;
4. obtains one repository-local Gate 1 writer lock;
5. re-verifies the terminal digest under the lock;
6. writes exactly one canonical line using append mode, flushes, and fsyncs;
7. reopens and verifies the full chain before reporting success.

The record ID and digest are idempotency keys. If a write or fsync succeeds but
post-write verification cannot complete, the call returns an indeterminate
append failure and Gate 1 cannot seal. A later retry may report success only
when the same record is already the exact valid terminal record; it never
appends a duplicate. A different record at that position is a fatal collision.

Deletion, modification, insertion, duplication, and reordering change either a
record digest, predecessor link, line count, exact-byte file digest, or terminal
digest. All are fatal. A partial trailing record is fatal and is never silently
truncated or repaired.

Once the Gate 1 manifest is published, both journals and the notes file become
sealed inputs. The writer refuses further appends when a valid seal exists. A
genuine correction requires a new `campaign_id` and new journal chain; it may
reference, but never edit, the prior campaign.

## Research Source Governance

### Source priority

Sources use this ordered classification:

1. `PEER_REVIEWED_ACADEMIC`
2. `ACADEMIC_WORKING_PAPER`
3. `SSRN`
4. `ESTABLISHED_QUANTITATIVE_FIRM`
5. `CFA_OR_INSTITUTIONAL`
6. `OFFICIAL_EXCHANGE_OR_MARKET_RESEARCH`
7. `REPUTABLE_QUANTITATIVE_PRACTITIONER`
8. `BLOG_FORUM_OR_SOCIAL_HYPOTHESIS_ONLY`

Tier 8 may suggest a question but can never be the primary support for a
hypothesis or satisfy the primary-source requirement.

### Source payload

A `PHASE4-RESEARCH-SOURCE-v1` payload contains:

- `source_id`, title, ordered authors, publication, year, canonical URL, source
  type, and retrieval date;
- methodology, asset classes, test period, strategy concept, exact reported
  parameters/horizons, economic or behavioral mechanism, claimed findings,
  limitations, and relevance to the frozen universe;
- `primary_evidence_eligible` and a reason;
- `citation_verified`, which must be true only when title, author/publisher,
  year, and URL were checked against the primary landing page or paper; and
- `phase4_validation_information_used = false`.

Claims are paraphrased. Verbatim quotations remain within source and copyright
limits. Missing bibliographic facts use `null` with an explanation; they are
never fabricated.

### Hypothesis support rule

Each sealed hypothesis must cite at least two admitted sources, including at
least one source from tiers 1–3. Both sources must support the stated mechanism
or signal concept, not merely mention the asset class. If the evidence remains
too weak or inapplicable, the idea is recorded in research notes as rejected
and does not consume a family slot.

The research cutoff is an exact UTC timestamp plus the source journal terminal
digest and byte digest. No source added after that cutoff can support the sealed
campaign.

## Hypothesis Lifecycle

A `PHASE4-HYPOTHESIS-v1` payload contains:

- hypothesis ID and supporting source IDs;
- economic/behavioral rationale;
- exact signal concept, entry and exit logic;
- cross-sectional ranking logic or explicit `NOT_APPLICABLE`;
- allocation logic, cash rule, risk rule, and rebalance frequency;
- expected turnover class;
- expected strengths and named failure regimes;
- an immutable deployment declaration with `rule_set_mode = FIXED`,
  `parameter_tuple_mode = FIXED`, `annual_reoptimization = false`, and
  `periodic_reoptimization = false`;
- a preregistered, economically motivated regime-behavior map and any
  deterministic regime partitions used for later diagnostics, with no
  validation-derived boundaries;
- bounded parameter dimensions and allowed typed values;
- the complete deterministic grid definition and expected candidate count;
- distinction from every Phase 2 baseline family;
- implementation requirements and anti-lookahead requirements;
- benchmark expectations;
- falsification conditions;
- simplicity component count; and
- `validation_data_accessed = false`, `validation_metrics_accessed = false`,
  and `campaign_results_accessed = false`.

Lifecycle states are `PROPOSED`, `ADMITTED`, or `REJECTED_BEFORE_TESTING`.
Only `ADMITTED` hypotheses produce families and grids. Rejection never deletes
or rewrites the record. A material change to a signal, parameter domain,
ranking, allocation, cash, risk, rebalance, benchmark, or falsification rule
requires a new hypothesis ID and a new journal record.

At seal time there must be at least one and at most ten admitted hypotheses,
with exactly one new family per admitted hypothesis. If credible research
supports none, Gate 1 ends as `NO_CREDIBLE_PREREGISTRABLE_IDEA`; it does not
create an empty readiness-to-implement seal.

## Fixed Phase 2 Comparison Baselines

The machine authority for Phase 2 trial membership is the already-sealed
readiness artifact with this exact identity:

```text
kind            = trial_authority
path            = results/phase4/readiness/trial_authority/sha256/fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994/authority.json
content_sha256  = fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994
sha256          = 2ab77e480a61c57f1c29395d4e93c2d9302533ab2f67ce364037965d1e1eb3f3
schema_version  = PHASE4-TRIAL-AUTHORITY-EVIDENCE-v1
authority_schema = PHASE4-TRIAL-AUTHORITY-v1
trial_count     = 136
```

Its envelope is already linked by the exact Phase 4 readiness manifest. Gate 1
must verify the authority artifact's exact bytes and envelope before parsing
its identity-only projection. It must not rebuild the authority, enumerate
`results/experiments`, choose a different readiness artifact, or parse Phase 2
performance fields.

The baseline labels, provenance classes, and configurations are:

| Baseline ID | Provenance class | Family | Exact parameters | Deterministic Phase 2 candidate ID |
|---|---|---|---|---|
| `baseline-trend-v1` | `EXECUTED_PHASE2_BASELINE` | `trend` | `fast_window=20`, `slow_window=50`, `allocation=1.0` | `trend-c7473b1efeb67913` |
| `baseline-momentum-v1` | `EXECUTED_PHASE2_BASELINE` | `momentum` | `lookback=126`, `allocation=1.0` | `momentum-beed7614cb8af377` |
| `baseline-trend-momentum-v1` | `SOURCE_DEFINED_PHASE2_GRID_BASELINE` | `trend_momentum` | `fast_window=20`, `slow_window=50`, `momentum_lookback=126`, `allocation=1.0` | `trend_momentum-83046debb18906e9` |
| `baseline-risk-managed-trend-v1` | `SOURCE_DEFINED_PHASE2_GRID_BASELINE` | `risk_managed_trend` | `trend_window=150`, `volatility_window=40`, `target_volatility=0.10`, `maximum_exposure=1.0` | `risk_managed_trend-797646e3271d03bb` |

Both provenance classes are comparison-only controls. The four controls are
not collectively described as “central Phase 2 configurations.” Exactly two
are executed authoritative Phase 2 trials; exactly two are source-defined
members of the committed Phase 2 generator grid that were not executed as
authoritative Phase 2 trials.

Each `PHASE4-BASELINE-DEFINITION-v1` record binds:

- baseline ID, provenance class, family, exact parameters, and deterministic
  Phase 2 candidate ID;
- Phase 2 generator revision
  `c33fb0757f0ea8147749130fed90d278aed4fafe`;
- generator path
  `src/investment_tracker/quant/optimizer/candidate_generator.py`;
- generator Git blob `39ae351c5b83d3f3477ed61f7f00a413fc1cb6d9` and exact-byte SHA-256
  `4db924185136c9ed702196407c62af37d9bdcb10bbbd486dc6984e33ff2e0cf0`;
- the exact grid dimension definition and the family implementation bundle
  identity;
- frozen Phase 4 universe and split identities;
- QFQ methodology identity
  `ffee9bac3fe329b14d5aebb0f6152f00fc0a86b28d9186c254b5c8f6f8a322fb`;
- `phase4_family_slots_consumed = 0`;
- `phase4_candidate_trials_consumed = 0`;
- `grid = null`, `eligible_for_selection = false`, and
  `validation_driven_selection = false`.

An `EXECUTED_PHASE2_BASELINE` additionally binds one exact authoritative
Phase 2 final-representation artifact path, kind, content digest, envelope
identity, and candidate ID. A `SOURCE_DEFINED_PHASE2_GRID_BASELINE` requires
those trial-artifact fields to be `null` and binds provenance only to the exact
committed generator revision, generator blob and bytes, grid definition,
parameter tuple, deterministic candidate ID, and implementation-bundle
identity. Supplying or inferring a completed historical trial for a
source-defined baseline is a provenance failure.

The Phase 2 strategy files and shared base/indicator/registry files are
byte-identical between the Phase 2 revision and current `main`. Canonical
implementation-bundle digests at the Phase 2 revision are:

| Family | Implementation bundle SHA-256 |
|---|---|
| `trend` | `018fc28b74700ed54fb1f8302bcf656edad462cf0f07377aa2d79cc4bc671af4` |
| `momentum` | `1917eaaf07b46e8ed7388441d61ee90756a7788054a4ebb815945cb6b1791960` |
| `trend_momentum` | `828846b6b6386cad33443631cbf2b4136084cee70e4b540b468ad3cc9c77684c` |
| `risk_managed_trend` | `646b46b349bcb608c5ef6a1142fa4588fb9e077dab57437cca729e49afc7504a` |

### Provenance verification result

The committed Phase 2 generator proves that all four exact configurations were
predetermined members of the Phase 2 parameter grids before Phase 4. Signal
and risk horizons use the pre-existing grid midpoint or central value where
applicable. `allocation = 1.0` and `maximum_exposure = 1.0` are not midpoint
values; they are frozen full-exposure comparator settings admitted by the
pre-existing grid.

The exact `trend` and `momentum` configurations each occur exactly once in the
136-trial authority and bind these exact authoritative final artifacts:

| Family | Kind | Repository-relative POSIX path | Content SHA-256 | Envelope SHA-256 |
|---|---|---|---|---|
| `trend` | `phase2_experiment` | `results/experiments/trend-c7473b1efeb67913-20260911T193719918435Z-d1014884.json` | `556bc481d3978cf028edd19dec1fc05d6becb5d6e09e7e0c0f16ed80bc08846c` | `330dd2c30e977376b844cbf50abfc9858f59a3df0b6ff53246ed5d13423174cb` |
| `momentum` | `phase2_experiment` | `results/experiments/momentum-beed7614cb8af377-20260911T193737197057Z-42f3156e.json` | `6495b221716f5f85a1b20fa16da79fe5521ee931119b8985aea9cafc30a6a8eb` | `fb902a7fbb6f0824461c6b005325fcec6717989eb34513c173c37ccc486d9f13` |

The exact `trend_momentum` and `risk_managed_trend` candidate IDs are absent
from the exact frozen 136-trial authority. They are therefore classified only as
`SOURCE_DEFINED_PHASE2_GRID_BASELINE`; their prior definition is established
by the exact committed generator source revision, grid definition, parameter
tuple, deterministic candidate ID, and implementation identity. Gate 1 must
not manufacture historical trial evidence for either control.

This narrower provenance classification is the approved authority. A baseline
provenance set is `VERIFIED` only when all four identities reproduce, the class
counts are exactly two `EXECUTED_PHASE2_BASELINE` and two
`SOURCE_DEFINED_PHASE2_GRID_BASELINE`, executed controls bind their exact
authoritative artifacts, and source-defined controls bind no trial artifact.
Any broader historical-execution claim returns
`BASELINE_PROVENANCE_UNRESOLVED` and prevents sealing.

No baseline parameter was selected using Phase 4 validation performance. No
Phase 2 numeric performance may be used to choose or alter a baseline. No
baseline may be retuned, searched, optimized, or selected as the Phase 4
winner. All four consume zero Phase 4 family slots and zero Phase 4 candidate
budget.

Any later modification of a baseline signal, filter, allocation, risk rule,
parameter, or implementation bundle makes it a new Phase 4 hypothesis. It then
consumes one family slot and every resulting unique candidate consumes one
Phase 4 trial position. A baseline can never be the Phase 4 winner.

## Strategy-Family Definitions

Each admitted hypothesis maps one-to-one to a
`PHASE4-STRATEGY-FAMILY-DEFINITION-v1` record containing:

- family ID, hypothesis ID, and supporting source IDs;
- human-readable name and economic mechanism;
- exact input fields and permitted use of earlier TRAIN observations for
  indicator warm-up;
- exact signal, ranking, allocation, cash, risk, and rebalance algorithms;
- long-only/no-leverage invariants and maximum gross exposure `1.0`;
- signal-at-session-`t`, fill-at-next-eligible-session convention;
- implementation interface required by Gate 2;
- canonical declarative `grid_spec_digest`, computed from parameter dimensions
  and structural predicates before candidate expansion;
- neighborhood definition based only on adjacent values in that grid;
- component count and expected failure regimes;
- the same fixed-strategy deployment declaration and regime-behavior map
  carried from the hypothesis;
- canonically rederived `rule_set_sha256`; and
- a canonical family-definition digest.

Names alone do not establish novelty. The distinction field must compare the
new family mechanically with each Phase 2 baseline. Adding any material filter
or allocation rule to a baseline creates a new family and consumes budget.
The semantic `family_id` excludes its own derived value,
`rule_set_sha256`, timestamps, artifact paths, the expanded candidate list,
artifact identities, and observed evidence. This avoids a circular dependency:
the family binds the declarative `grid_spec_digest`; `rule_set_sha256` then
binds the already-derived `family_id` and algorithmic projection; and the
expanded grid artifact binds the `family_id`, `parameter_tuple_sha256`, and all
candidate identities.

## Deterministic Grid Construction

Every parameter is declared with a stable name, type, ordered set of exact
values, units, domain constraints, and rationale. Floats are represented by
canonical hexadecimal values for identity and converted to binary64 only after
validation.

Grid expansion follows this fixed algorithm:

1. validate parameter names and types;
2. sort dimensions by Unicode code-point order of parameter name;
3. preserve the declared canonical value order within each dimension;
4. take the Cartesian product with the last dimension varying fastest;
5. apply only preregistered structural validity predicates, never performance
   predicates;
6. derive candidate IDs and trial IDs;
7. reject duplicate parameter payloads, candidate IDs, and trial IDs;
8. assign families in ascending `family_id` order; and
9. assign aggregate Phase 4 budget positions from 1 through `N` in family/grid
   order.

The grid artifact stores both the declarative dimensions and the entire ordered
expanded candidate list. Each row includes the type-tagged canonical parameter
map and its rederived `parameter_tuple_sha256`, `candidate_id`, `trial_id`, and
budget position. Gate 2 must reproduce it byte-for-byte before any
implementation verification. Gate 3 consumes that list; an LLM, optimizer, or
human cannot choose candidate `N+1` from candidate `N` results.

For every family:

```text
1 <= expected_candidate_count <= 500
```

Across all new families:

```text
1 <= aggregate_candidate_count <= 3000
```

Baseline definitions do not appear in either count.

## Budget and Family-Stop Policy

`PHASE4-BUDGET-POLICY-v1` freezes:

- 10 maximum new families;
- 500 maximum unique candidates per family;
- 3,000 maximum aggregate unique candidates;
- 136 historical Phase 2 trials as separate lineage only;
- initial Phase 4 consumption zero;
- duplicate trial identities consume nothing additional; and
- baseline evaluations consume no Phase 4 budget.

Gate 1 also freezes one `PHASE4-FAMILY-STOP-POLICY-v1` authority. Gate 3 may
record only these family stop reasons:

- `EXHAUSTED_GRID`;
- `PER_FAMILY_BUDGET_EXHAUSTED`;
- `AGGREGATE_BUDGET_EXHAUSTED`;
- `PERSISTENT_OOS_FAILURE`.

`PERSISTENT_OOS_FAILURE` means exactly 50 consecutive Phase 4 candidates in
the fixed family order whose VALIDATION benchmark excess return is non-positive
or unavailable. A candidate with positive benchmark excess return resets the
streak to zero even if another survivor gate rejects it. Parameter-neighborhood,
friction, bootstrap, absolute-return, or other isolated robustness failure
cannot increment this streak and cannot by itself terminate the family. This is
the existing governed family-level OOS-failure meaning without importing its
max-drawdown-dependent scorer.

No “no improvement” threshold, score tuning, discretionary stop, or LLM stop
is permitted. Every attempted candidate consumes its preassigned Phase 4
position before evaluation starts, including a candidate whose evaluation
fails.

An evaluation-system error fails the entire campaign as
`CAMPAIGN_EXECUTION_FAILED`; it is not mislabeled as a family research result.
After all permitted evidence is evaluated, absence of an eligible survivor is
the campaign outcome `NO_CREDIBLE_STRATEGY_FOUND`, not a family stop reason.

## Fixed-Strategy Durability Policy

Gate 1 freezes one `PHASE4-DURABILITY-POLICY-v1` authority. Its deployment
objective is one long-only strategy with one immutable rule set and one exact
parameter tuple, intended to remain usable for many years without annual or
periodic parameter re-optimization. Strategy state may evolve only through
the sealed rules; the rule set, parameter tuple, grid membership, and candidate
identity may not change between calendar periods, validation folds, friction
cases, robustness cases, or regimes.

The primary fixed-strategy proof is:

```text
research/tune on permitted development data
-> freeze the exact strategy and parameter tuple
-> run that same strategy unchanged through later/unseen periods
-> measure durability
```

Within the already-frozen Phase 4 architecture, “research/tune” means bounded
source-based hypothesis and grid preregistration on permitted development
information. It does not authorize parameter fitting to TRAIN performance:
TRAIN observations remain usable only for lagged-indicator warm-up, and no
TRAIN performance may influence VALIDATION. Every exact candidate tuple is
sealed before any Phase 4 VALIDATION access, and VALIDATION results cannot
generate a replacement tuple. Phase 4 is a bounded selection study rather than
final decision-grade deployment proof; the unchanged downstream evaluation is
still required.

The four chronological Phase 4 walk-forward test folds are fixed-strategy
subperiod evaluations of the same continuous VALIDATION replay. They do not
fit, select, optimize, or replace parameters at a fold or calendar boundary.
The validation portfolio resets once to initial cash and zero positions at the
frozen VALIDATION boundary; folds do not introduce additional portfolio resets
or TRAIN P&L. Strictly earlier TRAIN observations may be used only for the
already-frozen lagged-indicator warm-up semantics. The first scored signal is
on a VALIDATION session and executes on the next eligible VALIDATION session.

Adaptive or re-optimized walk-forward research is not primary deployment
evidence and is not permitted in this campaign. It may occur only as a
separately identified, separately preregistered secondary experiment in a
future campaign, and it cannot replace or modify the fixed-strategy proof.

The durability-policy artifact makes this contract machine-verifiable with
these exact fields:

```text
deployment_strategy_count       = 1
position_direction              = LONG_ONLY
rule_set_mode                    = FIXED
parameter_tuple_mode             = FIXED
parameter_fitting_from_train     = false
annual_reoptimization            = false
periodic_reoptimization          = false
primary_proof_mode               = FIXED_PARAMETER_CHRONOLOGICAL
adaptive_walk_forward_in_phase4  = false
cagr_hard_target                 = null
durability_precedes_fitted_cagr  = true
```

The survivor-policy artifact binds the durability-policy identity and exact
ordered ranking-key list. A field mismatch, omitted identity, changed ranking
order, or non-null CAGR hard target is `DURABILITY_POLICY_INVALID`.

### Required durability evidence

Where the frozen Phase 4 data supports the calculation, every candidate
evidence record must include all of the following, derived from the same fixed
VALIDATION return series:

- ordered calendar-month returns and ordered calendar-year returns;
- percentage of positive calendar months and calendar years;
- average positive month and average negative month;
- worst calendar month and worst calendar year;
- longest consecutive sequence of losing calendar months;
- ordered rolling 12-calendar-month returns;
- ordered rolling 3-calendar-year returns;
- calendar-month and calendar-year positive-return concentration;
- top-three-positive-month return concentration;
- parameter-neighborhood stability from the sealed grid;
- friction sensitivity at the already-frozen 0, 3, 10, 25, and 50 basis-point
  cases; and
- performance by each preregistered deterministic regime partition, together
  with a comparison to the hypothesis's economic mechanism and expected
  failure regimes.

Calendar-period return is the compounded return of every scored daily return
whose session belongs to that calendar period. A period is complete only when
the scored series contains every expected session inside the frozen
VALIDATION boundary; an incomplete period is retained with
`availability = UNKNOWN` and is excluded from aggregates. Positive percentage
uses strictly positive complete-period returns divided by the count of complete
periods. A losing month is strictly negative; zero breaks a losing sequence.
Average positive and negative months are arithmetic means of the respective
complete-month subsets and are `null / UNKNOWN` when the subset is empty.

For each rolling horizon, subtract exactly 12 or 36 Gregorian calendar months
from endpoint session date `t`, clamping an unavailable day to the last day of
that target month. The anchor is the latest scored XNYS session on or before
that date. Rolling return is `equity(t) / equity(anchor) - 1`. A window is
available only when the target anchor date is within the frozen scored span and
all expected sessions from the anchor through `t` are present. The evidence
stores the ordered anchor/endpoint/return series or an immutable content
identity for that exact series, plus the minimum, median, and positive-window
percentage. When no complete window exists, that horizon is
`UNKNOWN / INSUFFICIENT_DATA`; it is never approximated with a fixed session
count or a shorter calendar window.

For positive period returns `p_i`, positive-return concentration is
`max(p_i) / sum(p_i)`. Top-three-positive-month concentration is the sum of the
three largest positive month returns, or all positive months when fewer than
three exist, divided by the sum of all positive month returns. A non-positive
denominator produces `null / UNKNOWN`. These diagnostics answer whether
performance depends disproportionately on a small number of periods; Gate 1
does not invent a pass/fail threshold for them.

The policy schema records exact formulas, horizon calendar offsets and anchor
rules, period completeness rules, sign conventions, missing-value behavior,
rank direction, and immutable policy identity. Required supported evidence
that is absent or calculated under a different formula is `UNKNOWN` and fails
evidence completeness; no value is imputed. The policy does not require every
month or year to be profitable and creates no return threshold merely to
manufacture a survivor.

High CAGR remains desirable, including the aspirational possibility of a
sustainable 15–20% or greater long-term CAGR, but robustness and durability
take precedence over maximizing fitted CAGR. A candidate with slightly lower
CAGR and stronger preregistered durability evidence may outrank a fragile
higher-CAGR candidate. Robustness gates may not be weakened to cross any CAGR
target.

## Survivor Policy Freeze

The survivor policy is declarative, immutable, and applied only in Gate 3. It
does not use the existing `QUANT-SCORE-v1` because that scorer requires
`max_drawdown` and Calmar, both unavailable under DQ-030.

### Metric availability

- `max_drawdown = UNKNOWN / null` for every Phase 4 record.
- `calmar = UNKNOWN / null` because its denominator is the unresolved maximum
  drawdown convention.
- DSR and PBO remain `UNKNOWN / NOT_IMPLEMENTED / null`.
- An unavailable metric is never imputed, inferred, or converted to zero.

### Hard eligibility gates

A candidate is eligible for final ordering only when all are true:

1. VALIDATION total return is greater than zero and exceeds cash return.
2. VALIDATION benchmark excess return against the frozen equal-weight
   buy-and-hold universe benchmark is greater than zero.
3. VALIDATION Sharpe and Sortino are both defined and greater than zero.
4. At least three of four preregistered chronological walk-forward test folds
   have positive return and positive benchmark excess return.
5. At least two-thirds of valid immediate grid neighbors have positive
   VALIDATION return, and the median neighbor benchmark excess return is not
   negative. A boundary candidate uses all existing immediate neighbors; fewer
   than two valid neighbors yields `UNKNOWN` and rejection.
6. Return remains positive at total friction of 25 basis points per rebalance.
   The 0, 3, 10, 25, and 50 basis-point cases are all recorded; 50 basis points
   is diagnostic rather than a hard gate.
7. No single walk-forward fold contributes more than 75% of the sum of
   positive fold returns. A non-positive sum yields concentration `UNKNOWN` and
   rejection.
8. Annualized one-way turnover is defined, finite, non-negative, and no more
   than 12.0 times portfolio equity.
9. Average gross exposure is defined and remains within `[0.0, 1.0]`; every
   session-level target and realized gross exposure also remains in that range.
10. The lower endpoint of the preregistered 2,000-draw, seed-0 bootstrap
    interval for median daily portfolio return is not negative.
11. One exact candidate ID, family-definition digest, rule-set digest, and
    parameter-tuple digest apply unchanged to every session, calendar period,
    fold, regime, friction case, and robustness case. Any refit,
    re-optimization, parameter substitution, or annual/periodic adaptation is
    an invariant failure.
12. Every supported monthly, yearly, rolling-period, concentration, regime,
    neighborhood, and friction field required by
    `PHASE4-DURABILITY-POLICY-v1` is present, formula-versioned, and linked to
    the exact candidate return evidence; all other strategy invariants,
    identity checks, and evidence completeness checks pass.

Failure of any hard gate rejects the candidate. Missing required evidence is
`UNKNOWN` and rejects; it never passes by omission.

Annualized one-way turnover is calculated as:

```text
(sum of absolute buy and sell notional / mean daily portfolio equity)
* (252 / number of scored return sessions)
```

The friction retention ratio used for ordering is the 25-basis-point total
return divided by the 3-basis-point total return. The denominator is positive
because hard gate 1 has already passed; otherwise the ratio is `UNKNOWN` and
the candidate is rejected. Period concentration is the largest positive fold
return divided by the sum of positive fold returns.

### Robustness-first ordering

If more than one candidate passes every hard gate, order candidates
lexicographically by:

1. walk-forward joint return/benchmark consistency, descending;
2. percentage of positive calendar years, descending;
3. minimum rolling 3-year return, descending;
4. minimum rolling 12-month return, descending;
5. longest losing-month sequence, ascending;
6. worst calendar-year return, descending;
7. worst calendar-month return, descending;
8. positive calendar-year return concentration, ascending;
9. top-three-positive-month return concentration, ascending;
10. percentage of positive calendar months, descending;
11. parameter-neighborhood positive-return fraction, descending;
12. 25-basis-point friction return retention ratio, descending;
13. benchmark excess return, descending;
14. Sharpe, descending;
15. Sortino, descending;
16. bootstrap lower endpoint, descending;
17. annualized turnover, ascending;
18. walk-forward positive-return concentration, ascending;
19. preregistered signal-component count, ascending;
20. VALIDATION total return, descending;
21. CAGR, descending; and
22. canonical candidate ID, ascending.

The comparison uses full-precision canonical metric values; display rounding
never affects order. A metric that is supported but `UNKNOWN` has already
failed evidence completeness. A structurally unsupported rolling horizon sorts
after a supported value and otherwise continues to the next key, although the
frozen 2019-01-02 through 2022-12-30 VALIDATION span supports both
12-calendar-month and 3-calendar-year rolling horizons when return evidence is
complete.

CAGR is therefore a late tie-breaker rather than the primary objective.
Calendar consistency, rolling-period stability, losing-streak control,
concentration, neighboring-parameter stability, and friction robustness can
cause a lower-CAGR candidate to outrank a fragile higher-CAGR candidate.
Economic rationale and regime explainability are admission requirements
established by source, hypothesis, and preregistered regime evidence, not
result-dependent numerical bonuses.

At most the first eligible candidate can receive
`PHASE_4_CANDIDATE_SELECTED`. If none passes, the outcome is
`NO_CREDIBLE_STRATEGY_FOUND`.

## Downstream Phase 5 Long-History Requirement

If and only if Phase 4 selects exactly one credible candidate, the Phase 4
selection evidence must freeze that exact strategy implementation, rule-set
digest, parameter tuple, candidate identity, and methodology identity before
Phase 5 begins. Phase 5 must evaluate the **same frozen strategy unchanged** on
the longest defensible clean historical dataset available for the frozen
eight-ETF universe. The desired common history is approximately 15–20 years
when reliable common history permits it; it is not a required length.

If the frozen eight-ETF universe does not support the desired history, Phase 5
reports the actual longest defensible common history. It must not:

- alter, refit, or re-optimize parameters because of long-history results;
- substitute an unavailable ETF to manufacture a longer common history;
- create synthetic proxy history without a separately preregistered and
  independently approved methodology; or
- allow additional-history evidence to influence or revise the already
  completed Phase 4 candidate selection.

The Phase 5 evidence boundary is one-way: a committed Phase 4 selection may be
an input to a future Phase 5 specification, but no Phase 5 dataset, result,
metric, failure, or interpretation may flow back into Phase 4 ranking or
selection. This requirement does not authorize Phase 5 execution, provider
access, protected-symbol access, or release of `FINAL_HOLDOUT`.

At minimum, the long-history durability evaluation reports:

- CAGR;
- calendar-year and calendar-month returns;
- positive-year and positive-month percentages;
- average winning month and average losing month;
- worst year and worst month;
- longest losing-month sequence;
- rolling 12-month and rolling 3-year returns;
- rolling 5-calendar-year returns when complete 60-calendar-month windows
  exist;
- return concentration and dependence on a small number of periods;
- recovery characteristics;
- consistency with the preregistered economic mechanism across regimes;
- realistic cost and slippage sensitivity; and
- drawdown metrics only after DQ-030 is formally resolved under separately
  approved governance.

The Phase 5 question is exactly: “Can this exact frozen strategy remain useful
for many years without periodic retuning?” A long-history failure may prevent
later promotion, but it does not authorize retroactive Phase 4 retuning or a
different Phase 4 winner.

## Gate 1 Seal

The final artifact is `PHASE4-PREREGISTRATION-MANIFEST-v1` with status
`PHASE4_PREREGISTRATION_SEALED`. It contains:

- campaign ID;
- producing Git revision and canonical runtime dependency identity;
- Phase 3 universe and DQ digests;
- exact Phase 4 readiness manifest artifact identity;
- exact Phase 4 readiness 136-trial-authority artifact identity;
- source journal path, exact-byte digest, record count, and terminal digest;
- research notes path and exact-byte digest;
- hypothesis journal path, exact-byte digest, record count, and terminal
  digest;
- baseline-definitions artifact identity;
- strategy-family-definitions artifact identity;
- deterministic-grids artifact identity;
- the sorted `{family_id, rule_set_sha256}` set and a canonical aggregate
  digest over the ordered `{candidate_id, parameter_tuple_sha256}` population;
- budget and family-stop policy artifact identities;
- fixed-strategy durability-policy artifact identity;
- survivor-policy artifact identity;
- information-access-policy artifact identity and exact observed-read set;
- admitted source, hypothesis, family, and aggregate candidate counts;
- every schema version;
- QFQ methodology identity and `decision_grade = false`;
- DSR/PBO status;
- all access/safety flags; and
- `baseline_provenance_status = VERIFIED`, with exact provenance-class counts
  `{EXECUTED_PHASE2_BASELINE: 2,
  SOURCE_DEFINED_PHASE2_GRID_BASELINE: 2}`; and
- the exact machine-verifiable deployment fields from
  `PHASE4-DURABILITY-POLICY-v1`, including
  `deployment_strategy_count = 1`, `position_direction = LONG_ONLY`,
  `rule_set_mode = FIXED`, `parameter_tuple_mode = FIXED`,
  `annual_reoptimization = false`, and
  `periodic_reoptimization = false`.

The manifest model recomputes every count and cross-link. It requires exact
agreement between admitted hypotheses, families, grids, candidate identities,
trial identities, and budget positions. It rejects unknown extra fields.

The complete manifest is model-validated and serialized before publication.
All other Gate 1 artifacts are written and independently read back first. The
manifest is published through an atomic, no-overwrite, content-addressed commit
operation as the final fallible write. A failure cannot coexist with a newly
published valid sealed manifest.

After publication, source, note, hypothesis, baseline, family, grid, budget,
stop, durability, survivor, and access-policy mutation is forbidden. A new
campaign/version must be created for any genuine correction.

## Failure Behavior

Every Gate 1 entry point returns a machine-readable failure outcome and never a
partial seal. Required failure codes include:

- `READINESS_MANIFEST_MISMATCH`;
- `FROZEN_SPLIT_MISMATCH`;
- `BASELINE_PROVENANCE_UNRESOLVED`;
- `SOURCE_CHAIN_INVALID`;
- `SOURCE_EVIDENCE_INSUFFICIENT`;
- `HYPOTHESIS_CHAIN_INVALID`;
- `HYPOTHESIS_SOURCE_MISMATCH`;
- `FAMILY_DEFINITION_MISMATCH`;
- `GRID_INVALID`;
- `FAMILY_BUDGET_EXCEEDED`;
- `AGGREGATE_BUDGET_EXCEEDED`;
- `DURABILITY_POLICY_INVALID`;
- `SURVIVOR_POLICY_INVALID`;
- `GATE1_INFORMATION_BOUNDARY_VIOLATION`;
- `HISTORICAL_ARTIFACT_MUTATION`;
- `IMMUTABLE_ARTIFACT_COLLISION`; and
- `SEAL_PUBLICATION_FAILED`.

No failure handler repairs, deletes, truncates, substitutes, discovers a newer
artifact, relaxes a threshold, or falls back to a provider. Existing historical
bytes are hashed before and after the Gate 1 operation and must match.

## Required Tests Before Gate 1 Implementation Is Accepted

### Readiness and access tests

- exact readiness content/envelope identity validates;
- substituted, missing, symlinked, malformed, or nonancestor readiness evidence
  fails closed;
- every forbidden path is rejected before `open`, cache lookup, glob, provider,
  or parser interaction;
- Gate 1 cannot import validation execution, bar data, backtest, optimizer,
  provider, promotion/export, tracker mutation, or trading modules;
- all safety flags and the exact read ledger are enforced by the seal model;
- protected symbols and `FINAL_HOLDOUT` are rejected before any lookup.

### Journal tests

- canonical source and hypothesis records append exactly one `LF`-terminated
  line;
- genesis, predecessor, terminal, record, and exact-file digests reproduce;
- modification, deletion, insertion, duplication, reorder, invalid UTF-8,
  partial tail, noncanonical JSON, and duplicate ID all fail;
- concurrent append attempts respect the single writer lock;
- a sealed journal rejects append without altering bytes;
- corrections require a new campaign chain.

### Source and hypothesis tests

- every hypothesis has two admitted sources and at least one tier 1–3 source;
- tier-8-only support fails;
- citation fields cannot be invented or silently omitted;
- source cutoff excludes later records;
- a material hypothesis change produces a different hypothesis ID;
- rejected hypotheses remain in the chain and consume no family slot;
- zero or more than ten admitted hypotheses prevents a seal.

### Baseline tests

- the Phase 2 generator revision, blob, bytes, grid dimensions, and all four
  candidate IDs reproduce exactly;
- the exact pinned readiness trial-authority envelope and bytes validate,
  expose exactly 136 unique candidate identities, and are read without
  filesystem enumeration;
- provenance classes reproduce with exactly two
  `EXECUTED_PHASE2_BASELINE` and two
  `SOURCE_DEFINED_PHASE2_GRID_BASELINE` records;
- the `trend` and `momentum` pinned artifact identities validate without reading
  performance fields and each candidate ID occurs exactly once in the pinned
  trial authority;
- absence of exact Phase 2 trial artifacts for the other two baselines is
  proven by candidate-ID absence from the pinned 136-trial authority, is
  represented by required `null` artifact fields, and cannot be relabeled as
  completed trial evidence;
- the source-defined controls reproduce from the exact committed generator
  revision, blob bytes, grid definition, tuple, candidate ID, and
  implementation identity;
- full exposure is labeled a comparator setting rather than a midpoint, and
  no Phase 2 numeric performance or Phase 4 validation evidence is accepted as
  baseline-selection input;
- all baseline implementation bundles reproduce;
- any baseline modification changes its identity and forces new-family budget
  treatment;
- baselines have no grid, consume zero budget, and are ineligible for final
  selection.

### Grid and budget tests

- dimension order and Cartesian expansion are stable across input mapping and
  filesystem order;
- candidate and trial identities reproduce from canonical payloads;
- rule-set, parameter-tuple, and ordered candidate/parameter-population
  identities reproduce, and algorithm/parameter changes alter the appropriate
  identities while timestamps, labels, and observed results do not;
- budget positions start at 1 rather than 137;
- duplicates do not consume budget;
- family 11, candidate 501, or aggregate candidate 3,001 fails before append;
- every neighborhood is derived only from adjacent values already in the
  sealed grid;
- no adaptive candidate-generation API exists.

### Policy and seal tests

- isolated robustness failure cannot terminate a family;
- `PERSISTENT_OOS_FAILURE` requires exactly 50 consecutive failures and a
  passing candidate resets the streak;
- max drawdown, Calmar, DSR, and PBO remain unavailable and cannot affect rank;
- the frozen TRAIN/VALIDATION split and warm-up semantics reproduce exactly and
  cannot be replaced by a durability-policy field;
- every candidate keeps one rule-set digest and parameter-tuple digest across
  all sessions, periods, folds, regimes, friction cases, and robustness cases;
- an annual, fold-level, or periodic refit/re-optimization attempt fails the
  fixed-strategy invariant;
- calendar month/year returns, positive percentages, positive/negative month
  averages, worst periods, and longest losing-month sequence reproduce from
  deterministic fixtures;
- rolling 12-, 36-, and downstream 60-calendar-month anchor and completeness
  rules reproduce exactly across weekends, exchange holidays, leap years, and
  month ends, and insufficient history returns
  `UNKNOWN / INSUFFICIENT_DATA` rather than a fixed-session or shorter proxy;
- positive-period concentration and top-three-positive-month concentration
  reproduce, including zero-denominator `UNKNOWN` behavior;
- supported durability evidence cannot be omitted or calculated with a
  different formula version;
- every survivor hard gate and lexicographic tie-break is deterministic;
- a lower-CAGR candidate with stronger earlier durability keys outranks a
  fragile higher-CAGR candidate;
- the fixed-strategy proof is primary and no adaptive walk-forward result can
  enter the Phase 4 rank;
- baselines cannot win even if their diagnostic result is strongest;
- no qualifying candidate yields `NO_CREDIBLE_STRATEGY_FOUND`;
- exactly one best eligible candidate yields one selection;
- every seal dependency is exact, content-addressed, and read back;
- report publication precedes the seal and the seal is the final write;
- no failure result can coexist with a newly published valid seal;
- the seal binds the durability-policy artifact, fixed-strategy deployment
  fields, and exact two/two baseline provenance-class counts;
- the downstream Phase 5 contract freezes the selected identity, prohibits
  feedback into Phase 4, and cannot itself authorize data or provider access;
- Phase 2/3/readiness artifacts remain byte-identical;
- the complete existing test suite runs without weakening the Windows symlink
  test.

## Conditions Required Before Gate 2 May Begin

Gate 2 is forbidden until every condition is true:

1. This specification and the approved two-class baseline provenance statement
   are explicitly approved.
2. A separate Gate 1 implementation plan is approved and implemented test-first.
3. Gate 1 implementation and all regressions pass independent review.
4. External research is complete through a recorded cutoff.
5. Every citation and source-chain identity validates.
6. Between one and ten hypotheses are admitted with complete family definitions
   and grids.
7. Every grid and aggregate budget calculation reproduces and is within
   500/3,000 limits.
8. Baseline provenance status is exactly `VERIFIED`, with exact two/two class
   counts; unresolved or overstated provenance prevents sealing.
9. Survivor, fixed-strategy durability, family-stop, budget, and access
   policies are immutable artifacts.
10. All Phase 2, Phase 3, and readiness artifact hashes are unchanged.
11. All Gate 1 access flags remain false/zero/empty.
12. The final manifest validates with status
    `PHASE4_PREREGISTRATION_SEALED` and is committed separately.
13. Independent Audit or other governance authority has not imposed a new
    blocker.
14. The manifest binds the one-strategy, long-only, fixed-rule,
    fixed-parameter, no-periodic-reoptimization deployment objective.

Gate 2 approval does not authorize Gate 3, validation execution, candidate
evaluation, selection, promotion, export, or Phase 5.

## Migration and Compatibility

- Gate 1 adds a new isolated package and new result trees; it does not modify
  existing Phase 2, Phase 3, readiness, strategy, optimizer, backtest,
  calculation, robustness, promotion, or export modules.
- Existing CLI commands retain their signatures. A future Gate 1 CLI is a new
  command with exact bounded paths and no market-data/provider options.
- Existing experiment and readiness schemas are not extended or rewritten.
- The four baselines reuse existing strategy implementations by verified byte
  identity; they do not register as new Phase 4 strategies.
- Gate 2 may introduce new multi-asset interfaces only inside
  `investment_tracker.quant.phase4`. It must consume Gate 1 artifacts rather
  than modify them.
- Gate 3 evidence will use new Phase 4 schemas and paths. It will not append to
  Phase 2 experiment storage or canonical tracker state.
- No new dependency is required for the Gate 1 design. External research uses
  cited web sources, not a project market-data provider or trading package.

## Design-Time Verification and Current Access Status

This specification was prepared without running a strategy, backtest,
optimizer, candidate search, TRAIN evaluation, VALIDATION evaluation,
walk-forward analysis, friction analysis, or bootstrap analysis.

The only repository evidence inspected for baseline provenance was:

- committed Git source/history for the Phase 2 deterministic generator and
  strategy implementations;
- candidate-manifest identity/classification for the four exact proposed
  candidate IDs; and
- the already committed Phase 4 readiness manifest.

No Phase 4 validation data or metric was generated or inspected. No market-bar
cache, provider, protected-symbol resource, `FINAL_HOLDOUT`, trading API, or
canonical tracker state was accessed. Strategy search was not executed.

The approved provenance-and-durability clarification update inspected only
this specification, repository Git metadata, and the identity-only projection
of the already-sealed readiness manifest and 136-trial authority needed to pin
baseline membership and artifact envelopes. It did not inspect any strategy
performance metric, ranking, selection outcome, Phase 4 search result, Phase 4
validation data or metric, market bar, provider state, protected-symbol
resource, or `FINAL_HOLDOUT`. The disclosed non-performance Phase 2
identity/classification projection was the only search-lineage evidence read.
No strategy, search, backtest, or Gate 3 was executed.

Current design state is `DESIGN_COMPLETE_PROVENANCE_AND_DURABILITY_APPROVED`.
`PHASE4_PREREGISTRATION_SEALED` has not been produced.
