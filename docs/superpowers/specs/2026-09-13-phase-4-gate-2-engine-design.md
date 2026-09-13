# Phase 4 Gate 2 Engine and Strategy Implementation Design

## Status and Scope

This document specifies Phase 4 Gate 2: an isolated, deterministic,
paper-only multi-asset research engine that implements the four strategy
families already sealed by Phase 4 Gate 1. Gate 2 proves that the engine,
strategy mappings, accounting, evaluation plumbing, and immutable evidence
boundary conform to the sealed contract. It does not run the Phase 4
campaign.

Gate 2 may produce `PHASE4_ENGINE_SEALED` only after its implementation and
verification plan is separately approved, implemented test-first, and
independently reviewed. This design does not authorize Gate 3.

Gate 2 must not:

- evaluate the real Phase 4 VALIDATION campaign;
- expose or persist Phase 4 VALIDATION performance;
- rank candidates, apply the survivor policy, or select a winner;
- generate a new candidate, family, hypothesis, grid value, rule, durability
  threshold, survivor threshold, or budget;
- access `FINAL_HOLDOUT` or a protected-symbol resource;
- download or request market data;
- import or expose provider, brokerage, account, position, funds, order,
  promotion, export, or live-trading capabilities;
- mutate the Gate 1, Phase 2, Phase 3, or readiness evidence; or
- modify TPC-v1.2, REPLAY-v1.0, CALC-v1.2, or ROBUST-v1.0.

Gate 2 is infrastructure and conformance only. Its executable seal uses
synthetic data generated in memory. It does not open repository market-bar
files. A future Gate 3 data boundary will supply exact admitted arrays to the
sealed engine under a separately approved specification.

## Starting Authority

Gate 2 starts from Git revision:

```text
fb1c30a6c9789bddf2033301977fc8e2f3ebc1a0
```

The exact Gate 1 authority is:

| Field | Frozen value |
|---|---|
| Status | `PHASE4_PREREGISTRATION_SEALED` |
| Manifest path | `results/phase4/gate1/phase4_preregistration_manifest/sha256/dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89/manifest.json` |
| Manifest content SHA-256 | `dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89` |
| Manifest envelope SHA-256 | `e43ccbb596a9f66222b4e2785b1c40c423e6bb43b54b788e1fdb6358e1cdf146` |
| Campaign ID | `PHASE4-FIXED-LONG-ONLY-2014-2022-v1` |
| Readiness manifest content/envelope | `4305845b627ed2d369f3e16b26eb0e9ec724c13ea50904fcf5fd4113f264a254` / `25cea5b7cf490a4010244bd03968d342516bb27854b9488dbc9f9cdc2d375471` |
| Universe/DQ digests | `de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76` / `2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75` |
| Family count | 4 |
| Candidate count | 180 |
| Family candidate counts | 54, 36, 36, 54 in sealed ascending-family-ID order |
| Budget positions | contiguous integers 1 through 180 |
| Candidate-population SHA-256 | `15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3` |
| Historical Phase 2 trials | 136, lineage only |
| Initial Phase 4 consumption | 0 |
| Execution series | `QFQ_NORMALIZED` |
| Decision grade | `false` |
| QFQ methodology identity | `ffee9bac3fe329b14d5aebb0f6152f00fc0a86b28d9186c254b5c8f6f8a322fb` |
| Protected-symbol deny-list | `HACK`, `SOXX`, `NLR`, `URNM`, `GEV` |
| Baseline provenance | 2 `EXECUTED_PHASE2_BASELINE`, 2 `SOURCE_DEFINED_PHASE2_GRID_BASELINE`; all comparison-only |

The Gate 2 preflight must load the manifest by this exact path, validate its
exact bytes and canonical envelope, model-validate it with unknown fields
forbidden, and verify every linked artifact by exact content digest, kind,
portable repository-relative POSIX path, and envelope identity. It must
rederive all family, rule-set, parameter-tuple, candidate, trial, population,
and budget identities. It must verify that the Gate 1 producing revision and
readiness-revalidation revision are ancestors of the Gate 2 source revision.

No timestamp, filesystem order, modification time, directory enumeration,
glob, or “latest” lookup may select an authority. A missing, substituted,
symlinked, noncanonical, nonancestor, or mismatched dependency fails closed
before engine conformance begins.

## Execution-Convention Authority

The Phase 4 readiness design and the existing governed constant freeze:

```text
COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN
```

Gate 1 freezes a signal on session `t` executing only on the next eligible
session. It does not identify a different fill point. The authorities are
therefore consistent and Gate 2 binds the following exact convention:

1. A signal and target-weight vector use information available through the
   completed close of eligible session `t`.
2. The target becomes one pending rebalance tagged with `signal_timestamp=t`.
3. It can execute only at the QFQ-normalized open of the immediately next
   eligible session `t+1`.
4. Every fill requires `signal_timestamp < fill_timestamp`.
5. If no eligible successor session exists, the pending target does not fill.
6. Previous positions remain the holdings through the interval from session
   `t` close to session `t+1` open.
7. At the `t+1` open, previous holdings are marked, turnover is calculated,
   sells occur before buys, and friction is deducted.
8. New-position P&L begins only after the `t+1` open execution. The resulting
   holdings then receive `t+1` open-to-close price movement.
9. Residual allocation remains cash. Cash earns zero.

The execution reference is the QFQ-normalized `open`. Friction is recorded
separately rather than relabeling an adverse synthetic price as the provider
open. This is normalized research accounting only:

```text
execution_series = QFQ_NORMALIZED
decision_grade = false
required_successor = UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS
```

If any exact sealed authority is later shown to require another convention,
Gate 2 returns `EXECUTION_CONVENTION_MISMATCH`. It must not choose, infer, or
silently substitute a fill convention.

## Architecture

Gate 2 adds a sibling package without changing the sealed Gate 1 package:

```text
src/investment_tracker/quant/phase4/engine/
  __init__.py
  authority.py
  models.py
  market.py
  allocation.py
  strategies.py
  execution.py
  benchmarks.py
  metrics.py
  durability.py
  robustness.py
  budget.py
  evidence.py
  artifacts.py
  conformance.py
  seal.py
  cli.py
```

Responsibilities are deliberately narrow:

- `authority.py` verifies the exact sealed Gate 1 dependency graph and
  produces a read-only implementation authority. It has no generic file,
  cache, data, network, provider, or discovery API.
- `models.py` contains frozen, extra-forbidden domain and evidence schemas.
- `market.py` validates caller-supplied in-memory multi-asset `open` and
  `close` panels and separates read-only warm-up history from scored sessions.
- `allocation.py` implements equal weight, deterministic capped inverse
  volatility, and portfolio-volatility scaling.
- `strategies.py` maps exactly four sealed semantic family names to pure
  target-weight functions.
- `execution.py` implements the self-financing event ledger and the frozen
  next-session-open convention.
- `benchmarks.py` implements cash and equal-weight buy-and-hold controls using
  the same reset, eligibility, open execution, and friction convention.
- `metrics.py` calculates only supported non-drawdown performance fields.
- `durability.py` calculates calendar-period, rolling-period, losing-streak,
  and concentration evidence under the sealed formulas.
- `robustness.py` provides friction, bootstrap, neighbor, fold, and regime
  evidence plumbing without campaign orchestration or ranking.
- `budget.py` implements pure deterministic budget and family-stop state
  transitions from the sealed candidate order.
- `evidence.py` binds every output to its unchanged candidate and
  implementation identities and enforces unavailable fields.
- `artifacts.py` provides atomic, immutable, content-addressed Gate 2 storage.
- `conformance.py` validates all 180 parameter bindings and runs synthetic
  family/accounting conformance cases without evaluating campaign results.
- `seal.py` revalidates all dependencies, publishes non-final artifacts,
  reads them back, and publishes the Gate 2 manifest last.
- `cli.py` exposes only the provider-free conformance/seal operation.

The package must not import the existing workflow, optimizer/evaluator,
promotion, StrategyBase exporter, provider/data repository, canonical tracker
writers, or trading SDK. It may import NumPy, pandas, Pydantic, standard-library
modules, and exact canonical identity helpers from the unchanged Gate 1
package. Existing backtest, validation, and robustness modules remain
unchanged. Gate 2 does not route its multi-asset execution through the frozen
single-asset ledger because doing so would change the required portfolio-level
cash and allocation semantics.

## Market Input Boundary

`MarketPanel` is an immutable defensive copy with:

- one unique, strictly increasing, timezone-aware session index;
- a stable ordered symbol tuple;
- one `open` and one `close` binary64 column per symbol;
- finite, strictly positive prices;
- identical complete sessions for every symbol; and
- no extra market, corporate-action, fundamental, account, or order field.

The Gate 1 `input_fields = [date, close]` declaration governs strategy signal
inputs: strategy target functions receive the session index and close panel
only. The open panel is a separate execution-only input owned by the ledger;
it is never visible to signal, ranking, allocation, or rebalance decisions.
This separation satisfies both the sealed Gate 1 signal field list and the
governed next-session-open execution convention.

Duplicate sessions or symbols, missing or extra values, nonfinite or
nonpositive prices, timezone-naive indices, mismatched columns, noncanonical
symbol order, or mutation after construction fail before any strategy call.

`ScoredMarketInput` contains two separately identified panels:

- `indicator_warmup`: strictly earlier observations visible only to lagged
  calculations; and
- `scored`: sessions on which signals, fills, portfolio state, and evidence
  may be recorded.

Warm-up rows never produce a signal, fill, holding, cash change, return,
turnover, metric, or pending order. No callable carrying `fit`, `calibrate`,
`optimize`, or `select` behavior is admitted. The initial scored portfolio is
exactly initial cash, zero positions, zero pending targets, zero turnover,
zero realized P&L, and no cost basis. The first scored session may form a
signal after its close; its earliest fill is the second scored session open.

Gate 2 itself accepts only synthetic panels. It contains no repository data
loader. This ensures that sealing cannot accidentally reach TRAIN,
VALIDATION, holdout, provider, or cache resources. Gate 3 must later define a
separate exact data-admission boundary; that future boundary is not part of
Gate 2.

## Fixed Strategy Interface

The only strategy interface is:

```text
PHASE4-FIXED-LONG-ONLY-STRATEGY-v1
```

A strategy instance is constructed from one exact sealed `GridCandidate` and
one exact sealed `StrategyFamilyDefinition`. Construction rederives and binds:

- campaign ID;
- candidate ID and trial ID;
- family and hypothesis IDs;
- family-definition SHA-256;
- rule-set SHA-256;
- parameter-tuple SHA-256;
- grid-spec SHA-256; and
- Gate 2 implementation-bundle SHA-256.

These identities are immutable for the life of the instance and accompany
every target, fill, session state, period, fold, friction case, bootstrap case,
neighbor case, regime case, and evidence record. A changed identity or
parameter value produces `FIXED_STRATEGY_INVARIANT_FAILURE`.

The strategy object exposes no fitting, optimization, calibration, mutation,
adaptive-grid, annual-reset, fold-reset, or parameter-replacement method. It
may evolve only its causal lagged indicator state and fixed rebalance clock.
Rebalance clocks are anchored on the first scored session. A family with a
parameterized interval recomputes on scored offsets `0, interval, 2*interval,
...`; volatility-managed relative momentum uses its sealed structural
interval of 21 sessions. Between eligible rebalances the previous target is
held. An unavailable required indicator at an eligible rebalance admits no
risky asset and targets cash.

## Strategy Algorithms

All calculations use closes through signal session `t`. Symbol ties are
resolved by ascending symbol. No observed return can change an algorithm or
parameter.

### Cross-sectional absolute momentum rotation

For each symbol with sufficient history:

```text
score(t) = close[t-skip_sessions]
           / close[t-lookback_sessions-skip_sessions] - 1
```

Keep finite strictly positive scores, order by descending score then ascending
symbol, take the fixed `top_k`, and assign `1/n` to each selected symbol.
If none is selected, target 100% cash.

### Diversified time-series momentum

For each symbol:

```text
score(t) = close[t] / close[t-lookback_sessions] - 1
```

Admit finite strictly positive scores. Calculate each admitted symbol's sample
standard deviation (`ddof=1`) over exactly `volatility_window` close-to-close
simple returns ending at `t`. A symbol without a finite strictly positive
estimate is ineligible. Allocate in inverse-volatility proportion and apply
the deterministic maximum-asset-weight algorithm below.

### Trend-filtered equal-risk allocation

For each symbol, compute the arithmetic mean of exactly `trend_window` closes
ending at `t`. Admit the symbol only when `close[t]` is strictly greater than
that mean. Calculate volatility and capped inverse-volatility weights exactly
as above, using the fixed `volatility_window` and `maximum_asset_weight`.

### Volatility-managed relative momentum

Calculate positive trailing-return scores as for diversified time-series
momentum, order them by descending score then ascending symbol, and select the
fixed `top_k`. Begin with equal selected weights. From exactly
`volatility_window` complete close-to-close simple-return rows ending at `t`,
calculate the sample covariance matrix (`ddof=1`) for all selected symbols.

```text
annualized_portfolio_volatility
  = sqrt(252 * w' covariance w)
scale = min(1, target_portfolio_volatility
               / annualized_portfolio_volatility)
```

The volatility must be finite and strictly positive. Otherwise the eligible
risky target is empty. Multiply the equal weights by the finite nonnegative
scale. The unused weight remains cash.

### Deterministic maximum-asset-weight redistribution

Start with normalized inverse-volatility weights in ascending symbol order.
Iteratively cap weights above `maximum_asset_weight`, remove their mass from
the uncapped pool, and redistribute the remaining allocable mass among
uncapped assets in proportion to their original inverse-volatility scores.
Stop when no weight exceeds the cap or no uncapped asset remains. When
`eligible_count * maximum_asset_weight < 1`, the nonallocable residual remains
cash. Floating comparisons use an absolute tolerance of `1e-12`; output is
then revalidated without tolerance as finite and nonnegative, with total risky
weight no greater than `1 + 1e-12` and canonical stored total clamped to at
most `1.0` only when the excess is within that tolerance.

## Event Ledger and Accounting

The engine uses fractional units and one portfolio-level cash account. Short
positions, borrowing, margin, leverage, negative cash, and negative target
weights are impossible by schema and checked again after every event.

At each scored session:

1. mark pre-existing units at the current QFQ-normalized open;
2. execute only the pending target from the immediately preceding eligible
   signal session;
3. calculate desired asset notional from pre-friction open equity;
4. sell reductions first in ascending symbol order;
5. calculate each fill's one-way friction as
   `abs(fill_notional) * friction_bps / 10_000`;
6. allocate purchases in ascending symbol order, proportionally scaling all
   desired buys when necessary so purchase notional plus friction cannot
   exceed available cash;
7. reject any post-fill negative cash, negative unit, nonfinite state, or
   realized gross exposure above one;
8. mark the resulting holdings at the session close and record close equity;
9. form an eligible signal from information through that close; and
10. store at most one target for the next eligible session.

The reference price recorded in every fill is exactly the QFQ-normalized open.
Turnover is the sum of absolute fill notional. Target and realized weights are
distinct: friction can leave a small additional cash residual, but it cannot
create leverage. A target identical within absolute tolerance `1e-12` creates
no fill.

The first close-equity observation equals initial cash when there was no
eligible prior fill. Daily scored returns are `close_equity.pct_change()` and
therefore a 1,008-session scored panel produces 1,007 daily returns. No return
is synthesized for the reset boundary.

## Friction Cases

Gate 2 freezes the plumbing for exactly these total one-way friction cases:

```text
0, 3, 10, 25, 50 basis points
```

Each case replays the same immutable signal targets and fixed parameters from
the same reset state. A friction case cannot refit, resignal from its own
performance, alter a rebalance date, or change an identity. The engine records
fill-level friction, total turnover, and close equity separately for each
case. Gate 2 tests this behavior with synthetic inputs but publishes no Phase
4 candidate performance.

## Benchmarks and Cash

The cash benchmark is constant initial cash with zero exposure, fills,
turnover, and return.

The universe benchmark is one equal-weight buy-and-hold portfolio over the
exact admitted symbol order. Its equal-weight signal forms at the first scored
session close, executes once at the next eligible session open under the same
friction case, and then holds without rebalance. It begins from the same reset
state and uses the same QFQ-normalized open and close panels. Benchmark excess
return is candidate total return minus this benchmark total return under the
same friction case.

The four Gate 1 Phase 2 baseline definitions remain separately identified,
comparison-only controls. Gate 2 verifies their identities, two/two provenance
classes, zero family-slot consumption, zero candidate-budget consumption, and
ineligibility to win. It does not retune them, convert them into Phase 4
candidates, or execute them during sealing.

## Supported Metrics and Required Unknowns

From one scored close-equity series, Gate 2 supports:

- total return;
- CAGR using actual elapsed calendar days and 365.25 days per year;
- sample annualized volatility from daily returns with `ddof=1` and 252;
- Sharpe as mean daily return divided by sample daily standard deviation,
  multiplied by `sqrt(252)`;
- Sortino as mean daily return divided by the root mean square of
  `minimum(return, 0)`, multiplied by `sqrt(252)`;
- benchmark excess return;
- total one-way turnover;
- annualized one-way turnover under the exact Gate 1 formula;
- average and session-level target and realized gross exposure; and
- time in market.

Nonfinite inputs, a nonpositive equity observation, insufficient observations,
or a zero denominator produce an explicit `UNKNOWN` with a reason where the
metric is not mathematically defined. Missing values are never replaced by
zero.

Every Gate 2 evidence schema must preserve:

```text
max_drawdown = null
max_drawdown_status = UNKNOWN
calmar = null
calmar_status = UNKNOWN
dsr = null
dsr_status = UNKNOWN
dsr_reason = NOT_IMPLEMENTED
pbo = null
pbo_status = UNKNOWN
pbo_reason = NOT_IMPLEMENTED
```

The engine must not calculate max drawdown and then merely hide it. No
drawdown-dependent scorer or existing metric bundle that calculates drawdown
may be called by Gate 2.

## Durability Metrics

Gate 2 implements the exact Gate 1 formulas against a caller-supplied expected
session authority. It reports ordered calendar-month and calendar-year
returns, positive-period percentages, average positive and negative month,
worst month and year, longest strictly negative monthly sequence with zero
breaking a sequence, rolling 12- and 36-calendar-month returns, positive year
concentration, and top-three-positive-month concentration.

A calendar period is complete only when its scored sessions exactly equal the
expected admitted sessions for that period. An incomplete period is retained
as `UNKNOWN / INCOMPLETE_PERIOD` and excluded from aggregates. An empty sign
subset produces `UNKNOWN / EMPTY_SUBSET` for its average. A nonpositive
concentration denominator produces `UNKNOWN / NONPOSITIVE_DENOMINATOR`.

Rolling anchors subtract exactly 12 or 36 Gregorian calendar months from the
endpoint, clamp an unavailable target day to that target month's last day,
and use the latest expected scored session on or before that date. A rolling
window is available only when the anchor lies within the scored span and all
expected sessions from anchor through endpoint are present. Otherwise it is
`UNKNOWN / INSUFFICIENT_DATA` or `UNKNOWN / INCOMPLETE_WINDOW`. A fixed-session
or shorter-window proxy is forbidden.

Gate 2 exposes a generic 60-calendar-month implementation for the separately
frozen downstream Phase 5 contract, but a Gate 2 or Gate 3 record cannot use
that value as Phase 4 selection evidence.

## Fixed-Strategy Robustness Plumbing

### Bootstrap

The bootstrap implementation accepts the exact scored daily-return vector and
calculates only the median-daily-return statistic with 2,000 replacement draws,
NumPy generator seed 0, and frozen 5th/95th percentiles. The output is scoped
only to that statistic. It is not generalized into strategy confidence,
drawdown confidence, or search-aware evidence.

### Parameter neighborhoods

Neighbors are exactly the Gate 1 candidates that differ in one parameter
dimension by one adjacent declared value. No synthesized value is permitted.
The plumbing verifies all neighbor identities from the sealed grid and accepts
future Gate 3 return evidence only when it binds one of those identities.

### Continuous subperiod folds

Fold evidence slices one continuous scored replay. It never resets the
portfolio, indicators, pending target, or parameter tuple at a fold boundary.
Fold return is calculated from the continuous equity series at the supplied
boundary anchors; it is not obtained by rerunning or refitting a fold.

Gate 1 requires exactly four chronological folds but its sealed artifacts do
not bind their exact boundary dates or a derivation algorithm. Gate 2 therefore
implements and tests a fail-closed four-fold interface but does not invent
campaign fold boundaries. A future Gate 3 specification must bind an exact
immutable four-fold authority before any campaign execution. Until then,
attempting campaign fold evaluation returns `FOLD_AUTHORITY_MISSING`.

### Regime evidence

Regime plumbing accepts a complete, nonoverlapping mapping from scored session
to a preregistered regime label and checks it against a separately supplied
immutable regime authority. It computes no boundary and cannot fit or infer a
regime. Gate 1 seals qualitative maps and the statement “lagged signs and
relative returns only,” but does not seal a complete numeric partition
algorithm. A future Gate 3 specification must bind that algorithm and its
identity before regime evidence can be produced. Until then, the result is
`REGIME_AUTHORITY_MISSING`, never an inferred partition.

## Budget and Stop-State Plumbing

The pure budget state begins with:

```text
historical_phase2_trials = 136
historical_trials_are_lineage_only = true
phase4_new_trials_consumed = 0
phase4_new_trials_remaining = 3000
first_phase4_budget_position = 1
```

Only an exact sealed Phase 4 `trial_id` at its next contiguous preassigned
position can transition the state. The transition occurs before a future
evaluation starts. A repeated representation of the same trial returns the
existing position without additional consumption. A baseline or Phase 2 trial
cannot transition the state. Candidate 1 consumes position 1, not 137.

Family-stop state accepts candidate outcomes only in sealed family/grid order.
Exactly 50 consecutive nonpositive or unavailable VALIDATION benchmark-excess
outcomes produce `PERSISTENT_OOS_FAILURE`; a positive benchmark-excess outcome
resets the streak. Isolated friction, bootstrap, neighbor, fold-concentration,
absolute-return, exposure, turnover, or other robustness failures do not
increment the streak and cannot terminate a family. System errors produce
`CAMPAIGN_EXECUTION_FAILED`, not a research stop reason.

Gate 2 tests these pure transitions with synthetic outcomes. It does not
consume or persist an operational Phase 4 trial position.

## Evidence Identity and Completeness

Every future evaluation case is identified independently from its artifact:

```text
evaluation_case_sha256 = SHA-256(canonical_json({
  schema_version: "PHASE4-EVALUATION-CASE-v1",
  candidate_id,
  family_definition_sha256,
  rule_set_sha256,
  parameter_tuple_sha256,
  engine_implementation_sha256,
  evidence_kind,
  case_id
}))
```

`case_id` is a sealed friction value, neighbor trial ID, fold ID, regime ID,
bootstrap configuration ID, or `PRIMARY`. It never contains an observed
metric. Artifact identity remains SHA-256 of the canonical envelope containing
the exact-byte content digest, normalized repository-relative POSIX path, and
artifact kind.

Evidence models reject extra fields. They require identity agreement across
all cases and distinguish numeric zero from unavailable evidence. Gate 2 does
not define or invoke a candidate ranking function. Survivor-policy validation
is limited to proving that required fields and unavailable statuses can be
represented without changing the sealed policy.

## Immutable Gate 2 Artifacts

Gate 2 may create only:

```text
results/phase4/gate2/
  engine_contract/sha256/<content-sha256>/contract.json
  family_implementation_bindings/sha256/<content-sha256>/bindings.json
  candidate_implementation_bindings/sha256/<content-sha256>/bindings.json
  synthetic_conformance/sha256/<content-sha256>/conformance.json
  phase4_engine_report/sha256/<content-sha256>/report.md
  phase4_engine_manifest/sha256/<content-sha256>/manifest.json
```

The engine-contract artifact binds the exact Gate 1 manifest identity,
execution convention, QFQ methodology, unavailable fields, module boundary,
friction cases, accounting rules, and formula/schema versions.

Family bindings contain exactly four rows in sealed family order. Each row
binds the Gate 1 family/rule-set identities to the Gate 2 implementation
bundle. Candidate bindings contain exactly 180 rows in sealed candidate order,
with unchanged candidate, trial, family, parameter-tuple, rule-set, budget,
and implementation identities. They contain no price, return, metric, rank,
eligibility, or selection field and consume no operational budget.

Synthetic conformance uses one deterministic in-memory generator with clearly
nonhistorical values. It exercises every family implementation, allocations,
execution timing, friction, accounting, metrics, durability, robustness, and
budget state machine. The published record contains fixture/configuration and
output digests plus invariant pass/fail results, not candidate-performance
scores. It must be labeled `SYNTHETIC_CONFORMANCE_ONLY` and
`phase4_trials_consumed = 0`.

Artifacts are canonical UTF-8 JSON or exact UTF-8 Markdown, content-addressed,
written atomically without overwrite, fsynced, read back, and rehashed.
Symlink components, path escape, nonregular files, collisions, and mismatched
existing bytes fail closed. The manifest is the final fallible write.

## Gate 2 Manifest

`PHASE4-ENGINE-MANIFEST-v1` contains:

- status `PHASE4_ENGINE_SEALED`;
- producing Git revision and runtime dependency identity;
- exact starting revision;
- exact Gate 1 manifest content and envelope identities;
- all verified linked Gate 1/readiness artifact identities;
- candidate-population digest, four family identities, and exactly 180
  candidate bindings;
- engine source-bundle and per-family implementation-bundle identities;
- execution convention `COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN`;
- `execution_series = QFQ_NORMALIZED` and `decision_grade = false`;
- engine-contract, family-binding, candidate-binding, synthetic-conformance,
  and report artifact identities;
- formula and schema versions;
- historical Phase 2 count 136 and Phase 4 operational consumption 0;
- `max_drawdown` and Calmar `UNKNOWN / null`;
- DSR and PBO `UNKNOWN / NOT_IMPLEMENTED / null`;
- `fold_authority_status = NOT_BOUND_GATE3_REQUIRED`;
- `regime_authority_status = NOT_BOUND_GATE3_REQUIRED`;
- exact source and output read/write ledgers; and
- every safety/access field below.

Required safety/access values are:

```text
REAL_PHASE4_CAMPAIGN_EXECUTED = false
VALIDATION_STRATEGY_EXECUTED = false
VALIDATION_METRICS_ACCESSED = false
CANDIDATES_RANKED = false
SURVIVOR_SELECTED = false
STRATEGY_SEARCH_EXECUTED = false
EXTERNAL_STRATEGY_RESEARCH_PERFORMED = false
FINAL_HOLDOUT_ACCESSED = false
PROTECTED_SYMBOLS_ACCESSED = []
PROVIDER_CALLS = 0
DOWNLOADS = 0
LIVE_TRADING_CAPABILITY = false
PHASE4_TRIALS_CONSUMED = 0
```

A nonempty, true, or nonzero value where false/empty/zero is required prevents
the seal.

## Source and Implementation Identities

Every Gate 2 source path is normalized to repository-relative POSIX form. Its
exact worktree bytes must match its Git blob at the producing revision before
sealing. The source-bundle digest is canonical SHA-256 over the ordered map of
path to `{git_blob, content_sha256}`.

Each family implementation bundle includes `market.py`, `allocation.py`,
`strategies.py`, and all shared source files able to change signal or target
weights. The execution implementation bundle separately includes all files
able to change order eligibility, accounting, cash, fill, friction, or P&L.
Metric, durability, robustness, budget, evidence, authority, artifact, and seal
bundles are separately identified. The manifest binds all of them so a future
change cannot masquerade as the sealed Gate 2 engine.

## Failure Behavior

Gate 2 fails closed with a machine-readable code and publishes no valid final
manifest after any failure. Required codes include:

- `GATE1_MANIFEST_MISMATCH`;
- `GATE1_DEPENDENCY_MISMATCH`;
- `CANDIDATE_POPULATION_MISMATCH`;
- `EXECUTION_CONVENTION_MISMATCH`;
- `IMPLEMENTATION_BINDING_MISMATCH`;
- `INPUT_BOUNDARY_VIOLATION`;
- `MARKET_PANEL_INVALID`;
- `LONG_ONLY_INVARIANT_FAILURE`;
- `ACCOUNTING_INVARIANT_FAILURE`;
- `FIXED_STRATEGY_INVARIANT_FAILURE`;
- `DURABILITY_EVIDENCE_INVALID`;
- `BUDGET_ACCOUNTING_INVALID`;
- `FOLD_AUTHORITY_MISSING`;
- `REGIME_AUTHORITY_MISSING`;
- `FORBIDDEN_CAPABILITY_PRESENT`;
- `HISTORICAL_ARTIFACT_MUTATION`;
- `IMMUTABLE_ARTIFACT_COLLISION`; and
- `SEAL_PUBLICATION_FAILED`.

No failure handler repairs, deletes, truncates, substitutes, downloads,
discovers a newer artifact, changes a rule, retries with a different parameter,
or relaxes an invariant. Historical artifacts are hashed before and after the
operation and must remain byte-identical.

## Required Tests

### Authority and isolation

- exact Gate 1 and linked artifact identities validate;
- missing, substituted, malformed, symlinked, noncanonical, or nonancestor
  authority fails before engine invocation;
- regenerated family/grid/candidate/trial/population identities reproduce;
- exactly 4 families and 180 unique candidates in positions 1 through 180;
- imports and AST tokens prove absence of providers, repositories, workflows,
  optimizers, promotion/export, canonical writers, trading, and ranking;
- an instrumented filesystem proves no market-bar, validation, holdout,
  protected-symbol, provider, or “latest” lookup occurs;
- every historical dependency remains byte-identical.

### Strategy targets

- all four algorithms reproduce hand-calculated synthetic examples;
- signal values use no observation after session `t`;
- symbol tie-breaking is deterministic;
- insufficient or invalid indicator history targets cash;
- inverse-volatility caps redistribute deterministically and retain
  nonallocable residual cash;
- portfolio-volatility scaling uses the exact covariance window and cannot
  exceed gross exposure one;
- reordering input mappings cannot change targets or identities;
- all 180 sealed parameter tuples construct exactly once and no other tuple
  constructs.

### Execution and accounting

- a session-`t` close signal fills only at session-`t+1` open;
- every fill has `signal_timestamp < fill_timestamp`;
- a final-session signal never fills;
- previous holdings earn close-to-next-open movement before rebalance;
- new holdings earn only post-open movement;
- sells precede buys and friction is charged at each fill;
- zero-friction hand calculations reproduce exactly;
- on a fixed flat-price positive-turnover synthetic path, increasing friction
  strictly reduces final equity;
- targets and realized exposures remain long-only and unlevered;
- high friction proportionally scales buys and cannot create negative cash;
- residual allocation remains cash;
- first scored equity equals reset initial cash and 1,008 sessions imply 1,007
  daily returns;
- mutation, NaN, infinity, nonpositive prices, misalignment, duplicates, and
  timezone-naive inputs fail before execution.

### Reset and fixed-strategy invariants

- warm-up rows affect only causal lagged indicators;
- no warm-up signal, pending target, position, cash, P&L, turnover, or metric
  enters the scored period;
- first signal is on a scored session and earliest fill is the next scored
  open;
- changing observations outside the required causal warm-up cannot change the
  first scored indicator;
- fit/calibrate/optimize/select APIs are rejected structurally;
- candidate/rule/parameter/implementation identities cannot change across
  sessions, years, folds, friction, neighbor, bootstrap, or regime cases;
- folds are slices of one continuous replay and never reset or retune.

### Metrics, durability, and robustness

- total return, CAGR, volatility, Sharpe, Sortino, benchmark excess, turnover,
  exposure, and cash reproduce hand calculations;
- max drawdown and Calmar remain uncalculated `UNKNOWN`; DSR/PBO remain
  `UNKNOWN / NOT_IMPLEMENTED`;
- complete and incomplete month/year handling reproduces exactly;
- positive percentages, average signed months, worst periods, and losing-month
  sequence reproduce, including zero breaking a streak;
- Gregorian 12/36/60-month anchoring handles weekends, holidays, month ends,
  and leap years without fixed-session proxies;
- concentration and empty-denominator `UNKNOWN` behavior reproduce;
- bootstrap uses exactly 2,000 draws, seed 0, the median-daily-return
  statistic, and 5th/95th percentiles;
- neighbors come only from adjacent sealed grid values;
- missing fold or regime authority fails closed rather than inferring one;
- friction cases are exactly 0/3/10/25/50 bps and cannot alter signals.

### Budget, evidence, and sealing

- 136 historical trials never consume Phase 4 budget;
- initial Phase 4 consumption is zero and first candidate position is one;
- duplicate representations cannot consume twice;
- baseline identities cannot enter the Phase 4 budget ledger;
- isolated robustness failures cannot increment or terminate the OOS streak;
- exactly 50 consecutive nonpositive/unavailable benchmark-excess outcomes
  stop a family and a positive outcome resets the streak;
- candidate and implementation identities bind every synthetic evidence case;
- evidence cannot contain a rank, winner, eligibility result, or unsealed
  metric;
- content-addressed artifacts reject collision, symlink, path escape,
  noncanonical bytes, and read-back mismatch;
- all non-final artifacts precede the final manifest;
- no failure can coexist with a newly published valid manifest;
- the seal records every safety value exactly and leaves Phase 4 consumption
  at zero;
- the unchanged Windows symlink security test and full repository suite pass.

## Gate 2 Completion Conditions

Gate 2 may report `PHASE4_ENGINE_SEALED` only when:

1. this design and a separate detailed implementation plan are approved;
2. the starting revision and all sealed Gate 1 dependencies still validate;
3. all implementation tasks demonstrate RED before production code and GREEN
   afterward;
4. exactly four family implementations bind exactly 180 sealed candidates;
5. synthetic conformance passes without campaign execution or operational
   budget consumption;
6. focused, governance, security, and complete repository suites pass;
7. independent task reviews and a final whole-branch review have no unresolved
   load-bearing finding;
8. all historical evidence remains byte-identical;
9. the manifest is published last and independently revalidated; and
10. all safety/access fields remain false, empty, or zero as required.

The seal does not authorize Gate 3. Exact fold and regime authorities remain
mandatory pre-Gate-3 dependencies and may not be inferred from performance.

## Design-Time Access and Safety Record

This design was written without running a Phase 4 strategy candidate,
campaign, validation evaluation, ranking, selection, parameter search,
external strategy search, provider call, download, export, promotion, or
trading operation. No Phase 4 validation metric, `FINAL_HOLDOUT` resource, or
protected-symbol historical resource was opened.

The worktree preflight mechanically hash-verified the exact sealed Gate 1 and
readiness dependency chain. To reproduce the existing repository test
baseline in an isolated Git worktree, only the exact ignored eight Phase 3
dataset directories, three allowed bootstrap dataset directories, and
preserved Phase 2 experiment evidence were copied from the source checkout to
ignored worktree paths. The broader cache and untracked `docs/moomoo/` tree
were not copied. Existing dependency tests read and hash-validated the frozen
Phase 3 datasets, including their already-frozen session coverage, but no
strategy was run and no performance metric was generated or inspected.

The exact next-session-open convention was confirmed from the already-written
readiness specification and governed constant before this document was
created. No sealed Gate 1 or readiness artifact contradicted it.

Current design state: `GATE2_DESIGN_AWAITING_INDEPENDENT_REVIEW`.
