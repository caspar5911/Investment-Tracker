# Phase 4 Gate 2 Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to implement this plan
> task-by-task. Every production change requires a demonstrated RED before
> implementation and focused GREEN afterward.

**Goal:** Build, independently verify, and immutably seal the isolated Phase 4
Gate 2 multi-asset research engine without executing the Phase 4 campaign.

**Architecture:** Add a sibling `investment_tracker.quant.phase4.engine`
package whose only filesystem authority is a finite, terminal Gate 1
allowlist and whose runtime consumes caller-supplied immutable in-memory
panels. Pure fixed-strategy target functions feed a deterministic
next-session-open portfolio ledger; separate metric, durability, robustness,
budget, evidence, artifact, conformance, and seal modules preserve narrow
interfaces and make every result content-addressed.

**Tech Stack:** Python 3.12, NumPy, pandas, Pydantic 2, standard library,
pytest. No new dependency.

**Spec:**
`docs/superpowers/specs/2026-09-13-phase-4-gate-2-engine-design.md`
at approved commit `4449bedbd80ec52bce0363f0c6df4768c4818a08`.

## Global Constraints

- Work only on `codex/phase4-gate2` in the sibling isolated worktree that
  started from `fb1c30a6c9789bddf2033301977fc8e2f3ebc1a0`.
- Preserve TPC-v1.2, REPLAY-v1.0, CALC-v1.2, ROBUST-v1.0, Gate 1, Phase 2,
  Phase 3, and readiness source/evidence bytes unchanged.
- Verify the exact Gate 1 manifest content SHA-256
  `dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89`
  and envelope SHA-256
  `e43ccbb596a9f66222b4e2785b1c40c423e6bb43b54b788e1fdb6358e1cdf146`.
- Preserve campaign `PHASE4-FIXED-LONG-ONLY-2014-2022-v1`, exactly four
  families, exactly 180 candidate/trial bindings, family counts
  `54,36,36,54`, positions `1..180`, and population SHA-256
  `15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3`.
- Historical Phase 2 trial count remains 136 lineage-only; Phase 4 operational
  consumption begins and remains zero during Gate 2.
- Use `COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN`: close information through `t`, one
  pending target, fill at next eligible `t+1` QFQ-normalized open, strict
  `signal_timestamp < fill_timestamp`, old holdings until fill, friction at
  fill, and new-position P&L only after the open.
- Keep `execution_series=QFQ_NORMALIZED`, `decision_grade=false`, primary
  friction exactly 3 bps, other cases exactly `0,10,25,50` bps, initial cash
  exactly `100000.0`, long-only exposure at most one, and residual cash.
- Keep `max_drawdown` and Calmar `UNKNOWN/null`; keep DSR and PBO
  `UNKNOWN/NOT_IMPLEMENTED/null`. Do not calculate drawdown internally.
- Do not execute Gate 3 or any real Phase 4 TRAIN/VALIDATION strategy replay;
  do not inspect, calculate, expose, or persist Phase 4 validation metrics;
  do not rank candidates or select a survivor.
- Do not access `FINAL_HOLDOUT`; do not fetch, inspect, summarize, infer,
  cache, or derive history for `HACK`, `SOXX`, `NLR`, `URNM`, or `GEV`.
- Do not call providers, download data, perform external strategy research,
  discover strategies/parameters, or introduce brokerage, account, order,
  promotion, export, or trading capability.
- Gate 2 executable conformance uses only deterministic synthetic in-memory
  data. The engine package has no repository market-bar loader.
- Exact fold and regime authorities remain unbound and fail closed as
  `FOLD_AUTHORITY_MISSING` and `REGIME_AUTHORITY_MISSING`; do not infer them.
- Write new evidence only under `results/phase4/gate2/`; publish the engine
  manifest last. Do not modify or weaken the Windows symlink test.
- Every task is sequential: failing tests, intended RED, minimal
  implementation, focused GREEN, relevant regressions, independent task
  review, commit, then the next task.

---

### Task 1: Exact Authority and Base Contract Models

**Files:**

- Create: `src/investment_tracker/quant/phase4/engine/__init__.py`
- Create: `src/investment_tracker/quant/phase4/engine/models.py`
- Create: `src/investment_tracker/quant/phase4/engine/authority.py`
- Test: `tests/quant/test_phase4_gate2_authority.py`
- Test: `tests/quant/test_phase4_gate2_contracts.py`

**Interfaces:**

- Produces `Gate2SealError(code: str, message: str)` using only the failure
  codes frozen by the specification.
- Produces frozen, `extra="forbid"` models `DirectDependencyIdentity`,
  `Gate2Authority`, `SafetyAccessState`, and `UnavailableStatistics`.
- Produces
  `load_gate2_authority(repository_root: Path, *, head_revision: str | None = None,
  read_observer: Callable[[str], None] | None = None) -> Gate2Authority`.
- `Gate2Authority` exposes the validated Gate 1 manifest, parsed
  `PreregisteredGrids`, exact family/baseline payloads, ordered direct
  dependencies, and terminal metadata only. Later tasks consume it without
  rereading files.

- [ ] **Step 1: Write authority RED tests**

  Add literal tests that load the pinned manifest and assert the exact manifest
  identities, 15 terminal allowlisted files (manifest; eight artifact
  fields; two journals; research notes; readiness/split/trial artifacts), four
  families, 180 candidates, positions `1..180`, family counts
  `(54,36,36,54)`, population digest, 136 lineage trials, zero Phase 4
  consumption, two/two baseline classes, QFQ flags, unavailable statistics,
  and false/empty/zero safety fields. Instrument `read_observer` and assert
  exact ordered repository-relative POSIX paths.

- [ ] **Step 2: Write fail-closed and static-boundary RED tests**

  Copy only the allowlisted files to a temporary repository fixture. Mutate,
  omit, symlink, escape, or substitute each identity class and assert the
  relevant `GATE1_MANIFEST_MISMATCH`, `GATE1_DEPENDENCY_MISMATCH`,
  `CANDIDATE_POPULATION_MISMATCH`, or `EXECUTION_CONVENTION_MISMATCH` before
  any engine call. Put trap files behind readiness/split/trial terminal links
  and prove they are never read. Add AST/import checks rejecting provider,
  repository, workflow, optimizer, ranking, promotion, export, tracker-writer,
  brokerage, account, order, and trading symbols.

- [ ] **Step 3: Demonstrate RED**

  Run:

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_authority.py tests/quant/test_phase4_gate2_contracts.py -q
  ```

  Expected: collection fails because `investment_tracker.quant.phase4.engine`
  and the declared authority/models do not exist.

- [ ] **Step 4: Implement the finite terminal authority**

  Use the existing Gate 1 canonical helpers and validated Pydantic models.
  Declare every admitted path explicitly; check path shape and every symlink
  component before `read_bytes`; validate exact bytes, content hash, kind,
  path, envelope, cross-links, candidate/trial identities, baseline classes,
  safety flags, and Git ancestry. Do not glob, enumerate, recurse through
  terminal metadata, or expose a generic read method.

- [ ] **Step 5: Demonstrate GREEN and regress authority**

  Run the focused command from Step 3, then:

  ```powershell
  python -m pytest tests/quant/test_phase4_gate1_contracts.py tests/quant/test_phase4_gate1_seal.py tests/quant/test_phase4_readiness_contracts.py tests/quant/test_phase4_trial_authority.py -q
  ```

- [ ] **Step 6: Review and commit**

  Review the diff against the approved specification, obtain independent task
  review with both spec-compliance and code-quality verdicts, resolve all
  Critical/Important findings, then commit:

  ```text
  feat: add Gate 2 authority boundary
  ```

### Task 2: Immutable Synthetic Market Boundary

**Files:**

- Modify: `src/investment_tracker/quant/phase4/engine/models.py`
- Create: `src/investment_tracker/quant/phase4/engine/market.py`
- Test: `tests/quant/test_phase4_gate2_market.py`

**Interfaces:**

- Produces `MarketPanel.from_frames(open_prices: pd.DataFrame,
  close_prices: pd.DataFrame, *, role: Literal["WARMUP","SCORED"])`.
- Produces immutable properties `symbols`, `sessions`, `open_prices`,
  `close_prices`, `role`, and `panel_sha256`; returned frames are defensive
  copies.
- Produces `ScoredMarketInput.from_panels(indicator_warmup: MarketPanel,
  scored: MarketPanel)`, `warmup_panel_sha256`, `scored_panel_sha256`, and a
  combined close-history view unavailable to the execution ledger.
- Consumes no filesystem path and exposes no loader.

- [ ] **Step 1: Write market-boundary RED tests**

  Use hand-built UTC-midnight frames to verify stable symbol sorting, exact
  binary64 value identity, defensive copying, warm-up strictly before scored,
  and role-dependent hashes. Assert rejection of timezone-naive/non-UTC/
  non-midnight/duplicate/non-increasing sessions, duplicate or mismatched
  symbols, missing/extra/nonfinite/nonpositive values, non-binary64 coercion
  ambiguity, overlapping panels, and mutation after construction.

- [ ] **Step 2: Demonstrate RED**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_market.py -q
  ```

  Expected: import failure for the missing market types.

- [ ] **Step 3: Implement minimal immutable panels**

  Normalize columns by ascending symbol, require exact UTC-midnight `DatetimeIndex`,
  coerce once to `float64`, reject values whose exact admitted representation
  is invalid, mark internal arrays read-only, and derive canonical identities
  from role, symbols, ISO session labels, and `float.hex()` open/close rows.

- [ ] **Step 4: Demonstrate GREEN and regress**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_market.py tests/quant/test_phase4_validation_boundary.py tests/quant/test_data_validation.py -q
  ```

- [ ] **Step 5: Independently review and commit**

  Resolve review findings and commit:

  ```text
  feat: validate Gate 2 market inputs
  ```

### Task 3: Fixed Strategy Bindings, Allocations, and Four Target Algorithms

**Files:**

- Modify: `src/investment_tracker/quant/phase4/engine/models.py`
- Create: `src/investment_tracker/quant/phase4/engine/allocation.py`
- Create: `src/investment_tracker/quant/phase4/engine/strategies.py`
- Test: `tests/quant/test_phase4_gate2_allocation.py`
- Test: `tests/quant/test_phase4_gate2_strategies.py`

**Interfaces:**

- Produces `FixedStrategyBinding.from_authority(authority: Gate2Authority,
  candidate_id: str, implementation_sha256: str)` with immutable campaign,
  candidate, trial, family, hypothesis, family-definition, rule-set,
  parameter-tuple, grid-spec, and implementation identities.
- Produces `TargetInstruction(signal_timestamp: pd.Timestamp,
  due_session: pd.Timestamp | None, weights: tuple[tuple[str,float],...],
  binding: FixedStrategyBinding)`.
- Produces `equal_weights`, `capped_inverse_volatility`, and
  `portfolio_volatility_scale` pure allocation functions.
- Produces `generate_target(binding, market_input, scored_offset) ->
  TargetInstruction | None`; `None` means the close is not a
  signal-generation rebalance.

- [ ] **Step 1: Write allocation RED tests**

  Add literal hand calculations for equal weights, inverse-volatility
  proportions, iterative cap redistribution, nonallocable residual cash,
  ascending-symbol determinism, covariance volatility scaling, zero/nonfinite
  volatility cash targets, tolerance/clamp behavior, and rejection of negative
  or gross-over-one weights.

- [ ] **Step 2: Write four-family RED tests**

  For each sealed semantic family, use small synthetic close histories with
  literal expected scores and weights. Cover strict positivity, skip/lookback
  indexing, exact trailing simple-return windows, `ddof=1`, SMA including
  session `t`, covariance ending at `t`, tie-breaking, insufficient history,
  cash target, parameterized clocks, structural 21-session clock, no lookahead,
  and final-session `due_session=None`. Construct every one of the 180 sealed
  candidates exactly once; reject any candidate/family/parameter/identity
  substitution and any fit/calibrate/optimize/select surface.

- [ ] **Step 3: Demonstrate RED**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_allocation.py tests/quant/test_phase4_gate2_strategies.py -q
  ```

- [ ] **Step 4: Implement pure fixed target generation**

  Dispatch only by the exact four semantic names. Present the strategy layer
  with closes through the requested offset, never opens. Decode only the
  sealed typed parameters, preserve identities on every target, return no
  instruction off-clock, and create a cash target when an on-clock indicator
  is unavailable.

- [ ] **Step 5: Demonstrate GREEN and regress Gate 1 grids**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_allocation.py tests/quant/test_phase4_gate2_strategies.py tests/quant/test_phase4_gate1_grids.py tests/quant/test_strategies.py -q
  ```

- [ ] **Step 6: Independently review and commit**

  Resolve findings and commit:

  ```text
  feat: implement Gate 2 strategy targets
  ```

### Task 4: Next-Session-Open Portfolio Ledger and Benchmarks

**Files:**

- Modify: `src/investment_tracker/quant/phase4/engine/models.py`
- Create: `src/investment_tracker/quant/phase4/engine/execution.py`
- Create: `src/investment_tracker/quant/phase4/engine/benchmarks.py`
- Test: `tests/quant/test_phase4_gate2_execution.py`
- Test: `tests/quant/test_phase4_gate2_benchmarks.py`

**Interfaces:**

- Produces frozen `Fill`, `SessionState`, and `PortfolioReplay` models.
- Produces `replay_targets(scored: MarketPanel,
  targets: Sequence[TargetInstruction], *, friction_bps: int,
  initial_cash: float = 100000.0) -> PortfolioReplay`.
- Produces `cash_benchmark(scored: MarketPanel) -> PortfolioReplay` and
  `equal_weight_buy_and_hold(scored: MarketPanel, *, friction_bps: int) ->
  PortfolioReplay`.

- [ ] **Step 1: Write causal-ledger RED tests**

  Hand-calculate fixtures proving: signal at close `t` fills only at open
  `t+1`; strict timestamp order; a final signal never fills; old units receive
  close-to-next-open movement; new units receive only open-to-close movement;
  sells precede buys; one-way friction uses reference-open notional; fractional
  units and residual cash; buy scaling under high friction; zero/negative
  cash, units, targets, and exposure are impossible.

- [ ] **Step 2: Write rebalance and benchmark RED tests**

  Prove desired notionals use current pre-cost open equity and current
  open-marked holdings, so an unchanged requested target rebalances drift on a
  scheduled execution. Prove an open without a due target preserves units,
  while a non-signal close may follow a due open fill. Verify notional tolerance
  `1e-12 * max(1, open_equity)`, first scored equity `100000.0`, zero-interest
  cash, no reset leakage, cash benchmark, and one-fill equal-weight buy/hold.

- [ ] **Step 3: Demonstrate RED**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_execution.py tests/quant/test_phase4_gate2_benchmarks.py -q
  ```

- [ ] **Step 4: Implement the event ledger minimally**

  Process sessions in order: open mark, due target, desired notional, sells,
  friction, proportionally scaled buys, invariant checks, close mark, state.
  Make fill ordering deterministic by ascending symbol and preserve every
  strategy identity on fills and states. Implement benchmarks through the same
  ledger rather than a separate accounting shortcut.

- [ ] **Step 5: Demonstrate GREEN and regress frozen backtests**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_execution.py tests/quant/test_phase4_gate2_benchmarks.py tests/quant/test_backtest_engine.py tests/quant/test_metrics_and_benchmarks.py -q
  ```

- [ ] **Step 6: Independently review and commit**

  Resolve findings and commit:

  ```text
  feat: add Gate 2 portfolio execution
  ```

### Task 5: Supported Metrics and Durability Evidence

**Files:**

- Modify: `src/investment_tracker/quant/phase4/engine/models.py`
- Create: `src/investment_tracker/quant/phase4/engine/metrics.py`
- Create: `src/investment_tracker/quant/phase4/engine/durability.py`
- Test: `tests/quant/test_phase4_gate2_metrics.py`
- Test: `tests/quant/test_phase4_gate2_durability.py`

**Interfaces:**

- Produces `calculate_metrics(replay: PortfolioReplay,
  benchmark: PortfolioReplay) -> SupportedMetrics`.
- Produces `ExpectedSessionAuthority(sessions: tuple[pd.Timestamp,...],
  sha256: str)` and
  `calculate_durability(replay: PortfolioReplay,
  expected: ExpectedSessionAuthority, *, horizons: tuple[int,...]=(12,36)) ->
  DurabilityEvidence`.
- Evidence uses explicit `MetricValue(value, status, reason)` so numeric zero
  cannot equal missing.

- [ ] **Step 1: Write metric RED tests from literals**

  Hand-calculate total return, actual-day CAGR with 365.25, sample volatility
  `ddof=1`, Sharpe, downside-RMS Sortino, same-friction benchmark excess,
  turnover, annualized turnover, post-close realized exposure, carried target
  exposure, time in market, and cash. Cover insufficient observations,
  nonpositive equity, nonfinite input, and zero denominators as explicit
  `UNKNOWN`. Assert no drawdown call or field is computed and all frozen
  unavailable fields have exact status/reason/null values.

- [ ] **Step 2: Write durability RED tests from literals**

  Cover complete/incomplete month and year compounding, strict positive
  percentages, signed-month averages, worst periods, zero-broken losing-month
  streaks, month/year positive-return concentration, top-three-positive-month
  concentration, and every empty/nonpositive-denominator reason. Cover exact
  Gregorian 12/36/60-month anchors across weekends, holidays, leap days, and
  month ends; verify ordered rolling values plus minimum, median, and positive
  fraction, with `INSUFFICIENT_DATA` and `INCOMPLETE_WINDOW` fail-closed paths.

- [ ] **Step 3: Demonstrate RED**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_metrics.py tests/quant/test_phase4_gate2_durability.py -q
  ```

- [ ] **Step 4: Implement supported calculations only**

  Derive all values from the scored close-equity/state series. Use every scored
  close for average equity/exposure and `len(closes)-1` for return-session
  turnover annualization. Match calendar sessions exactly before aggregation.
  Do not import the frozen metric bundle because it calculates drawdown.

- [ ] **Step 5: Demonstrate GREEN and regress policy math**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_metrics.py tests/quant/test_phase4_gate2_durability.py tests/quant/test_phase4_gate1_policies.py tests/quant/test_metrics_and_benchmarks.py -q
  ```

- [ ] **Step 6: Independently review and commit**

  Resolve findings and commit:

  ```text
  feat: add Gate 2 metrics and durability
  ```

### Task 6: Friction, Bootstrap, Neighborhood, Fold, Regime, and Budget Plumbing

**Files:**

- Modify: `src/investment_tracker/quant/phase4/engine/models.py`
- Create: `src/investment_tracker/quant/phase4/engine/robustness.py`
- Create: `src/investment_tracker/quant/phase4/engine/budget.py`
- Test: `tests/quant/test_phase4_gate2_robustness.py`
- Test: `tests/quant/test_phase4_gate2_budget.py`

**Interfaces:**

- Produces `run_friction_cases(scored, targets) -> FrictionEvidence` with exact
  cases `(0,3,10,25,50)` and `primary_bps=3`.
- Produces `bootstrap_median_daily_return(returns) -> BootstrapEvidence` using
  exactly 2,000 replacement draws, `np.random.default_rng(0)`, median statistic,
  and 5th/95th percentiles.
- Produces `neighbor_trial_ids(family, parameter_tuple_sha256)` from sealed
  adjacent values only; `slice_continuous_folds` and `partition_regimes`
  require exact external authorities and otherwise raise the frozen codes.
- Produces pure `BudgetState.from_authority(authority)`,
  `consume_current(trial_id)`, `record_candidate_outcome(...)`, and
  `terminate_family(reason)` transitions without persistence.

- [ ] **Step 1: Write robustness RED tests**

  Verify identical target identities across friction cases, primary mapping to
  3 bps, primary-series use by bootstrap/fold/regime/neighbor/stop evidence,
  25/3 retention, deterministic bootstrap literal output, statistic-only
  wording, exact sealed neighbors, no synthesized values, continuous fold
  slicing without reset, complete nonoverlapping regime maps, and fail-closed
  missing authorities.

- [ ] **Step 2: Write budget RED tests**

  Verify 136 remains lineage-only, start `0/3000`, candidate position 1 has
  consumption ordinal 1, duplicate representations do not consume, baselines
  cannot enter, and only the current cursor trial can start. Verify exactly 50
  consecutive primary benchmark-excess outcomes that are nonpositive or
  unavailable stop a family; positive resets; isolated robustness failures
  never increment or terminate. Exercise stop at position 50, skipped 51-54,
  position 55 consumed as ordinal 51, plus `EXHAUSTED_GRID`, unreachable
  per-family/aggregate limits, and campaign-system-error semantics.

- [ ] **Step 3: Demonstrate RED**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_robustness.py tests/quant/test_phase4_gate2_budget.py -q
  ```

- [ ] **Step 4: Implement deterministic pure plumbing**

  Keep robustness inputs identity-bound and reject any observed metric embedded
  in case IDs. Keep population position, cursor, and consumption ordinal
  separate; skipped rows have no ordinal and consume nothing. These APIs must
  not write an operational trial or orchestrate a campaign.

- [ ] **Step 5: Demonstrate GREEN and regress**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_robustness.py tests/quant/test_phase4_gate2_budget.py tests/quant/test_robustness_scoring.py tests/quant/test_phase4_gate1_policies.py tests/quant/test_phase4_gate1_grids.py -q
  ```

- [ ] **Step 6: Independently review and commit**

  Resolve findings and commit:

  ```text
  feat: add Gate 2 robustness and budget
  ```

### Task 7: Evaluation Identities and Immutable Gate 2 Artifact Store

**Files:**

- Modify: `src/investment_tracker/quant/phase4/engine/models.py`
- Create: `src/investment_tracker/quant/phase4/engine/evidence.py`
- Create: `src/investment_tracker/quant/phase4/engine/artifacts.py`
- Test: `tests/quant/test_phase4_gate2_evidence.py`
- Test: `tests/quant/test_phase4_gate2_artifacts.py`

**Interfaces:**

- Produces `evaluation_context_identity(...)` with every exact panel, reset,
  expected-session, fold/regime availability, initial-cash, friction,
  convention, series, and decision-grade field from the specification.
- Produces `evaluation_case_identity(...)` binding candidate/family/rule/
  parameter/implementation/context/evidence-kind/case ID.
- Produces extra-forbidden evidence records with immutable unavailable fields
  and no rank, winner, eligibility, selection, or unsealed metric field.
- Produces `Gate2ArtifactStore.write_json`, `write_bytes`, `verify`, and
  `commit_manifest` for the six exact Gate 2 artifact kinds.

- [ ] **Step 1: Write identity/evidence RED tests**

  Use fixed literal SHA-256 expectations. Prove any open/close bit, symbol
  order, session, warm-up/scored role, reset field, expected-session authority,
  fold/regime identity/status, initial cash, primary friction, execution field,
  candidate identity, or case changes the correct digest. Prove metrics never
  enter identities, missing fold/regime states cannot execute those cases, and
  forbidden evidence fields are rejected.

- [ ] **Step 2: Write artifact RED tests**

  Verify canonical UTF-8 JSON bytes, Markdown exact bytes, kind/path/envelope
  identities, atomic no-overwrite publication, idempotent identical bytes,
  collision rejection, symlink component rejection using the unchanged
  Windows-capable environment, path/filename escape rejection, read-back
  rehashing, temporary cleanup, and manifest-only final commit semantics.

- [ ] **Step 3: Demonstrate RED**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_evidence.py tests/quant/test_phase4_gate2_artifacts.py -q
  ```

- [ ] **Step 4: Implement identities, schemas, and storage**

  Reuse Gate 1 canonical JSON/path/envelope primitives. Permit only the exact
  six `results/phase4/gate2/` kinds and filenames. Use exclusive hard-link
  publication, fsync, no overwrite, exact read-back, and final-manifest last
  behavior; do not add cleanup methods to production solely for tests.

- [ ] **Step 5: Demonstrate GREEN and regress security**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_evidence.py tests/quant/test_phase4_gate2_artifacts.py tests/quant/test_phase4_gate1_artifacts.py tests/quant/test_cache_repository.py -q
  ```

- [ ] **Step 6: Independently review and commit**

  Resolve findings and commit:

  ```text
  feat: add Gate 2 evidence storage
  ```

### Task 8: Implementation Bundles and Synthetic Conformance

**Files:**

- Create: `src/investment_tracker/quant/phase4/engine/conformance.py`
- Create: `src/investment_tracker/quant/phase4/engine/source_identity.py`
- Test: `tests/quant/test_phase4_gate2_conformance.py`
- Test: `tests/quant/test_phase4_gate2_source_identity.py`

**Interfaces:**

- Produces `source_bundle_identity(repository_root, producing_revision,
  paths) -> SourceBundleIdentity`, requiring each worktree byte to equal its
  Git blob and hashing the ordered POSIX path to `{git_blob,content_sha256}`.
- Produces per-family, execution, metric, durability, robustness, budget,
  evidence, authority, artifact, conformance, and seal bundle identities.
- Produces `run_synthetic_conformance(authority, bundle_set) ->
  SyntheticConformanceRecord` labeled `SYNTHETIC_CONFORMANCE_ONLY` with
  `phase4_trials_consumed=0`, fixture/configuration digests, invariant results,
  and no candidate performance score.

- [ ] **Step 1: Write source-identity RED tests**

  In a temporary Git repository, verify clean exact-blob success and rejection
  of untracked, dirty, missing, symlinked, escaped, reordered, or wrong-revision
  sources. Assert every signal/target-changing source enters each family
  bundle and every accounting-changing source enters the execution bundle.

- [ ] **Step 2: Write synthetic-conformance RED tests**

  Build clearly nonhistorical in-memory panels and prove all four family
  implementations and all 180 bindings construct, allocation/timing/friction/
  accounting/metrics/durability/bootstrap/budget invariants run, fold/regime
  remain explicitly unbound, baseline identities remain comparison-only, and
  no output contains candidate returns, rank, eligibility, winner, or survivor.
  Use instrumented filesystem/network seams to assert no market-bar,
  validation-result, holdout, protected, provider, dynamic/latest, export, or
  trading access.

- [ ] **Step 3: Demonstrate RED**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_source_identity.py tests/quant/test_phase4_gate2_conformance.py -q
  ```

- [ ] **Step 4: Implement bundle and conformance orchestration**

  Generate the synthetic fixture in memory from a fixed formula and hash its
  configuration. Run only conformance assertions; retain pass/fail identities,
  not performance. Static-scan the engine package for forbidden imports and
  public APIs before returning a passing record.

- [ ] **Step 5: Demonstrate GREEN and regress the engine**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_source_identity.py tests/quant/test_phase4_gate2_conformance.py tests/quant/test_phase4_gate2_authority.py tests/quant/test_phase4_gate2_market.py tests/quant/test_phase4_gate2_strategies.py tests/quant/test_phase4_gate2_execution.py tests/quant/test_phase4_gate2_metrics.py tests/quant/test_phase4_gate2_durability.py tests/quant/test_phase4_gate2_robustness.py tests/quant/test_phase4_gate2_budget.py -q
  ```

- [ ] **Step 6: Independently review and commit**

  Resolve findings and commit:

  ```text
  feat: add Gate 2 synthetic conformance
  ```

### Task 9: Engine Seal, Report, and Provider-Free CLI

**Files:**

- Modify: `src/investment_tracker/quant/phase4/engine/models.py`
- Create: `src/investment_tracker/quant/phase4/engine/seal.py`
- Create: `src/investment_tracker/quant/phase4/engine/cli.py`
- Test: `tests/quant/test_phase4_gate2_seal.py`
- Test: `tests/quant/test_phase4_gate2_cli.py`

**Interfaces:**

- Produces `seal_gate2(repository_root: Path, *, fail_after_kind: str | None =
  None, write_observer: Callable[[str],None] | None = None) -> Gate2SealResult`.
- Publishes contract, four family bindings, 180 candidate bindings, synthetic
  conformance, and report before committing one
  `PHASE4-ENGINE-MANIFEST-v1` last.
- CLI accepts only `--repository-root` and prints the manifest JSON/status; it
  has no data, candidate, parameter, provider, export, order, or trading option.

- [ ] **Step 1: Write seal RED tests**

  Verify exact schema/status, starting/Gate 1/runtime/source/bundle identities,
  execution fields, unavailable fields, 136/zero accounting, fold/regime
  unbound statuses, 15 allowlisted files including the manifest plus terminal
  metadata, exact read/
  write ledgers, four ordered family and 180 ordered candidate bindings, and
  every false/empty/zero safety field. Verify bindings contain no price,
  return, metric, rank, eligibility, or selection field.

- [ ] **Step 2: Write publication/CLI RED tests**

  Inject failure after every non-final artifact and prove no new valid manifest
  appears. Prove each dependency is rehashed before and after, mutation fails
  closed, existing collisions fail, all artifacts read back, manifest is the
  final observed fallible write, repeat is byte-identical, and CLI exposes no
  forbidden option or module. Include a subprocess integration test in a
  temporary clean Git repository.

- [ ] **Step 3: Demonstrate RED**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_seal.py tests/quant/test_phase4_gate2_cli.py -q
  ```

- [ ] **Step 4: Implement report and final seal**

  Revalidate authority first; derive clean Git/source identities; run
  synthetic conformance; build all payloads in memory; publish and verify each
  non-final artifact; rehash the finite authority set; assert repository writes
  are confined to Gate 2; build the report; commit the manifest last. Map every
  exception to a frozen machine-readable failure code and never repair,
  substitute, retry with altered inputs, or publish a success after failure.

- [ ] **Step 5: Demonstrate GREEN and run complete pre-seal regression**

  ```powershell
  python -m pytest tests/quant/test_phase4_gate2_seal.py tests/quant/test_phase4_gate2_cli.py -q
  python -m pytest -q
  ```

- [ ] **Step 6: Independently review and commit**

  Resolve findings and commit:

  ```text
  feat: seal Phase 4 Gate 2 engine
  ```

### Task 10: Execute the Fixed Gate 2 Seal and Independently Verify It

**Files:**

- Create only content-addressed files below: `results/phase4/gate2/`
- Do not modify source, tests, specifications, plans, or earlier evidence.

**Interfaces:**

- Consumes the exact committed Task 9 source revision and exact sealed Gate 1
  authority.
- Produces one immutable `PHASE4_ENGINE_SEALED` manifest and its linked Gate 2
  artifacts with Phase 4 trial consumption still zero.

- [ ] **Step 1: Record the clean execution baseline**

  Record HEAD, `git status --short`, exact Gate 1 dependency hashes, existing
  Gate 2 tree absence, and safety fields. Fail closed on any mismatch; never
  delete or replace an existing artifact.

- [ ] **Step 2: Run the provider-free seal once**

  ```powershell
  python -m investment_tracker.quant.phase4.engine.cli --repository-root .
  ```

  Expected: one `PHASE4_ENGINE_SEALED` result, no provider/data arguments, and
  writes only beneath `results/phase4/gate2/`.

- [ ] **Step 3: Verify identities independently**

  Recompute exact-byte SHA-256 and canonical envelope identity for the manifest
  and every linked Gate 2 artifact using a separate verification test/script.
  Recompute source bundles from Git, family/candidate bindings from Gate 1,
  direct-dependency before/after hashes, write order, and safety/access values.
  Assert 4 families, 180 bindings, 136 historical trials, zero Gate 2 campaign
  trials, `PRIMARY=3`, QFQ non-decision-grade flags, unavailable statistics,
  and fold/regime Gate 3 requirements.

- [ ] **Step 4: Run the unchanged security and full suites**

  ```powershell
  python -m pytest tests/quant/test_cache_repository.py -q
  python -m pytest -q
  ```

  The existing Windows symlink test must run unchanged and pass.

- [ ] **Step 5: Commit only newly generated evidence**

  Confirm `git status --short` names only new files under
  `results/phase4/gate2/`, then
  commit:

  ```text
  evidence: seal Phase 4 Gate 2 engine
  ```

- [ ] **Step 6: Final independent whole-branch review**

  Review the complete range from
  `fb1c30a6c9789bddf2033301977fc8e2f3ebc1a0` through final HEAD against the
  approved specification and this plan. Require independent verification of
  every generated identity, all information boundaries, RED/GREEN records,
  commit boundaries, source/evidence immutability, and absence of Gate 3,
  validation metrics, ranking, survivor selection, providers, protected data,
  export, and trading. Resolve all Critical/Important or other load-bearing
  findings, rerun affected tests, and revalidate the immutable seal without
  overwriting it.

- [ ] **Step 7: Stop at Gate 2**

  Report `PHASE4_ENGINE_SEALED`, all commits, focused/full test results,
  manifest/content/envelope/source/bundle/candidate identities, direct
  dependency hashes, write paths, and every safety/access field. Do not create
  a Gate 3 plan, load campaign data, or execute any candidate.
