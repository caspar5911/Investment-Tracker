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

## Governing Principles

- Research is long-only, unlevered, paper-only, and incapable of brokerage,
  account, position, funds, order-routing, or live-trading operations.
- TPC-v1.2, REPLAY-v1.0, CALC-v1.2, and ROBUST-v1.0 remain unchanged.
- Existing Phase 2, Phase 3, and Phase 4 readiness artifacts are immutable.
- Missing decision-critical evidence fails closed to `UNKNOWN` or rejection.
- The goal is falsifiable, economically defensible evidence rather than the
  highest historical CAGR.
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
  policy, survivor policy, and information-access policy.
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

The only permitted Phase 2 evidence is the fixed Git generator blob and, where
available, explicitly pinned candidate-manifest artifact identities. Gate 1
does not enumerate Phase 2 files and does not read Phase 2 performance fields.

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
- `family_id = "phase4-family-" + SHA-256(canonical family definition)`.
- `candidate_id = "phase4-" + SHA-256(canonical_json({campaign_id,
  hypothesis_id, family_id, parameters}))`.
- `trial_id = SHA-256(canonical_json({campaign_id, candidate_id}))`.

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

The proposed baseline labels and configurations are:

| Baseline ID | Family | Exact parameters | Deterministic Phase 2 candidate ID |
|---|---|---|---|
| `baseline-trend-v1` | `trend` | `fast_window=20`, `slow_window=50`, `allocation=1.0` | `trend-c7473b1efeb67913` |
| `baseline-momentum-v1` | `momentum` | `lookback=126`, `allocation=1.0` | `momentum-beed7614cb8af377` |
| `baseline-trend-momentum-v1` | `trend_momentum` | `fast_window=20`, `slow_window=50`, `momentum_lookback=126`, `allocation=1.0` | `trend_momentum-83046debb18906e9` |
| `baseline-risk-managed-trend-v1` | `risk_managed_trend` | `trend_window=150`, `volatility_window=40`, `target_volatility=0.10`, `maximum_exposure=1.0` | `risk_managed_trend-797646e3271d03bb` |

Each `PHASE4-BASELINE-DEFINITION-v1` record binds:

- baseline ID, family, exact parameters, and deterministic Phase 2 candidate
  ID;
- Phase 2 generator revision
  `c33fb0757f0ea8147749130fed90d278aed4fafe`;
- generator path
  `src/investment_tracker/quant/optimizer/candidate_generator.py`;
- generator Git blob `39ae351c5b83d3f3477ed61f7f00a413fc1cb6d9` and exact-byte SHA-256
  `4db924185136c9ed702196407c62af37d9bdcb10bbbd486dc6984e33ff2e0cf0`;
- the family implementation bundle identity;
- frozen Phase 4 universe and split identities;
- QFQ methodology identity
  `ffee9bac3fe329b14d5aebb0f6152f00fc0a86b28d9186c254b5c8f6f8a322fb`;
- `phase4_family_slots_consumed = 0`;
- `phase4_candidate_trials_consumed = 0`;
- `grid = null`, `eligible_for_selection = false`, and
  `validation_driven_selection = false`.

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
predetermined members of the Phase 2 parameter grids before Phase 4. The
window/lookback/volatility/target-volatility values are the middle values of
their respective ordered dimensions. Allocation or maximum exposure `1.0` is
an admitted Phase 2 value but is the maximum of `(0.25, 0.5, 1.0)`, not its
middle value.

The exact `trend` and `momentum` configurations each have one authoritative
final Phase 2 trial artifact:

- `trend`: content digest
  `556bc481d3978cf028edd19dec1fc05d6becb5d6e09e7e0c0f16ed80bc08846c`,
  envelope identity
  `330dd2c30e977376b844cbf50abfc9858f59a3df0b6ff53246ed5d13423174cb`.
- `momentum`: content digest
  `6495b221716f5f85a1b20fa16da79fe5521ee931119b8985aea9cafc30a6a8eb`,
  envelope identity
  `fb902a7fbb6f0824461c6b005325fcec6717989eb34513c173c37ccc486d9f13`.

The exact `trend_momentum` and `risk_managed_trend` configurations have no
Phase 2 experiment representation because the bounded Phase 2 family searches
stopped before reaching them. Their prior definition is established by the
committed generator blob, not by a completed trial artifact.

Therefore the stronger claim that all four are fully central, previously
evaluated Phase 2 evidence configurations is **not established**. Gate 1 must
fail closed rather than label that claim verified. The baselines may be sealed
only if specification approval explicitly accepts this narrower provenance:

> Each baseline is a predetermined Phase 2 grid member using central signal and
> risk horizons plus a frozen full-exposure comparator; two have authoritative
> Phase 2 trial artifacts and two have source-definition provenance only.

Without that explicit acceptance, baseline status is
`BASELINE_PROVENANCE_UNRESOLVED`, no Gate 1 seal may be created, and Gate 2 may
not begin.

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
- component count and expected failure regimes; and
- a canonical family-definition digest.

Names alone do not establish novelty. The distinction field must compare the
new family mechanically with each Phase 2 baseline. Adding any material filter
or allocation rule to a baseline creates a new family and consumes budget.
The semantic `family_id` excludes timestamps, artifact paths, the expanded
candidate list, and artifact identities. This avoids a circular dependency:
the family binds the declarative `grid_spec_digest`, while the expanded grid
artifact binds the already-derived `family_id` and all candidate identities.

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
expanded candidate list. Gate 2 must reproduce it byte-for-byte before any
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
11. All strategy invariants, identity checks, and evidence completeness checks
    pass.

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
2. parameter-neighborhood positive-return fraction, descending;
3. 25-basis-point friction return retention ratio, descending;
4. benchmark excess return, descending;
5. Sharpe, descending;
6. Sortino, descending;
7. bootstrap lower endpoint, descending;
8. annualized turnover, ascending;
9. period concentration, ascending;
10. preregistered signal-component count, ascending;
11. VALIDATION total return, descending;
12. CAGR, descending; and
13. canonical candidate ID, ascending.

CAGR is therefore a late tie-breaker, not the primary objective. Economic
rationale is an admission requirement established by source and hypothesis
evidence, not a result-dependent numerical bonus.

At most the first eligible candidate can receive
`PHASE_4_CANDIDATE_SELECTED`. If none passes, the outcome is
`NO_CREDIBLE_STRATEGY_FOUND`.

## Gate 1 Seal

The final artifact is `PHASE4-PREREGISTRATION-MANIFEST-v1` with status
`PHASE4_PREREGISTRATION_SEALED`. It contains:

- campaign ID;
- producing Git revision and canonical runtime dependency identity;
- Phase 3 universe and DQ digests;
- exact Phase 4 readiness manifest artifact identity;
- source journal path, exact-byte digest, record count, and terminal digest;
- research notes path and exact-byte digest;
- hypothesis journal path, exact-byte digest, record count, and terminal
  digest;
- baseline-definitions artifact identity;
- strategy-family-definitions artifact identity;
- deterministic-grids artifact identity;
- budget and family-stop policy artifact identities;
- survivor-policy artifact identity;
- information-access-policy artifact identity and exact observed-read set;
- admitted source, hypothesis, family, and aggregate candidate counts;
- every schema version;
- QFQ methodology identity and `decision_grade = false`;
- DSR/PBO status;
- all access/safety flags; and
- `baseline_provenance_status = VERIFIED`.

The manifest model recomputes every count and cross-link. It requires exact
agreement between admitted hypotheses, families, grids, candidate identities,
trial identities, and budget positions. It rejects unknown extra fields.

The complete manifest is model-validated and serialized before publication.
All other Gate 1 artifacts are written and independently read back first. The
manifest is published through an atomic, no-overwrite, content-addressed commit
operation as the final fallible write. A failure cannot coexist with a newly
published valid sealed manifest.

After publication, source, note, hypothesis, baseline, family, grid, budget,
stop, survivor, and access-policy mutation is forbidden. A new campaign/version
must be created for any genuine correction.

## Failure Behavior

Every Gate 1 entry point returns a machine-readable failure outcome and never a
partial seal. Required failure codes include:

- `READINESS_MANIFEST_MISMATCH`;
- `BASELINE_PROVENANCE_UNRESOLVED`;
- `SOURCE_CHAIN_INVALID`;
- `SOURCE_EVIDENCE_INSUFFICIENT`;
- `HYPOTHESIS_CHAIN_INVALID`;
- `HYPOTHESIS_SOURCE_MISMATCH`;
- `FAMILY_DEFINITION_MISMATCH`;
- `GRID_INVALID`;
- `FAMILY_BUDGET_EXCEEDED`;
- `AGGREGATE_BUDGET_EXCEEDED`;
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
- the `trend` and `momentum` pinned artifact identities validate without reading
  performance fields;
- absence of exact Phase 2 trial artifacts for the other two baselines is
  represented honestly and cannot be relabeled as completed trial evidence;
- all baseline implementation bundles reproduce;
- any baseline modification changes its identity and forces new-family budget
  treatment;
- baselines have no grid, consume zero budget, and are ineligible for final
  selection.

### Grid and budget tests

- dimension order and Cartesian expansion are stable across input mapping and
  filesystem order;
- candidate and trial identities reproduce from canonical payloads;
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
- every survivor hard gate and lexicographic tie-break is deterministic;
- baselines cannot win even if their diagnostic result is strongest;
- no qualifying candidate yields `NO_CREDIBLE_STRATEGY_FOUND`;
- exactly one best eligible candidate yields one selection;
- every seal dependency is exact, content-addressed, and read back;
- report publication precedes the seal and the seal is the final write;
- no failure result can coexist with a newly published valid seal;
- Phase 2/3/readiness artifacts remain byte-identical;
- the complete existing test suite runs without weakening the Windows symlink
  test.

## Conditions Required Before Gate 2 May Begin

Gate 2 is forbidden until every condition is true:

1. This specification is explicitly approved, including the narrower baseline
   provenance statement or an approved replacement baseline policy.
2. A separate Gate 1 implementation plan is approved and implemented test-first.
3. Gate 1 implementation and all regressions pass independent review.
4. External research is complete through a recorded cutoff.
5. Every citation and source-chain identity validates.
6. Between one and ten hypotheses are admitted with complete family definitions
   and grids.
7. Every grid and aggregate budget calculation reproduces and is within
   500/3,000 limits.
8. Baseline provenance status is exactly `VERIFIED`; unresolved provenance
   prevents sealing.
9. Survivor, family-stop, budget, and access policies are immutable artifacts.
10. All Phase 2, Phase 3, and readiness artifact hashes are unchanged.
11. All Gate 1 access flags remain false/zero/empty.
12. The final manifest validates with status
    `PHASE4_PREREGISTRATION_SEALED` and is committed separately.
13. Independent Audit or other governance authority has not imposed a new
    blocker.

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

Current design state is `DESIGN_COMPLETE_BASELINE_PROVENANCE_UNRESOLVED`.
`PHASE4_PREREGISTRATION_SEALED` has not been produced.
