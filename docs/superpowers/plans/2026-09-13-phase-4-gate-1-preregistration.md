# Phase 4 Gate 1 Preregistration Implementation Plan

> **Execution discipline:** implement this plan sequentially with test-driven
> development. Do not start Gate 2 or Gate 3.

**Goal:** Implement, independently review, execute, and seal the provider-free
Phase 4 Gate 1 research-governance subsystem defined by
`docs/superpowers/specs/2026-09-13-phase-4-gate-1-preregistration-design.md`.

**Architecture:** Add an isolated
`investment_tracker.quant.phase4.preregistration` package. It accepts only
exact readiness/Git/provenance identities and normalized literature records,
maintains append-only source and hypothesis journals, expands complete grids,
freezes fixed-strategy durability and survivor policies, writes immutable
content-addressed artifacts, and publishes the Gate 1 seal last. The package
must not import or call market data, provider, backtest, optimizer/evaluator,
promotion/export, tracker-writer, or trading capabilities.

**Technology:** Python 3.12, Pydantic 2, standard library, pytest. No new
dependency.

## Global Constraints

- Preserve TPC-v1.2, REPLAY-v1.0, CALC-v1.2, and ROBUST-v1.0 byte-for-byte.
- Preserve every Phase 2, Phase 3, and readiness artifact byte-for-byte.
- Never read market-bar caches, Phase 4 TRAIN/VALIDATION data or metrics,
  `FINAL_HOLDOUT`, or protected-symbol resources.
- Never invoke a provider, download, strategy evaluation/search, Gate 3,
  account/trading API, promotion, or export path.
- Keep QFQ as `QFQ_NORMALIZED`, `decision_grade=false`.
- Treat the 136 historical Phase 2 trials as multiplicity lineage only. Gate 1
  and Phase 4 candidate consumption begin at zero.
- Treat the four fixed baselines as comparison controls only, with exactly two
  `EXECUTED_PHASE2_BASELINE` and two
  `SOURCE_DEFINED_PHASE2_GRID_BASELINE` records.
- DSR and PBO remain `UNKNOWN / NOT_IMPLEMENTED / null`; `max_drawdown` and
  Calmar remain `UNKNOWN / null` while DQ-030 is unresolved.
- Preserve the existing Windows symlink test unchanged. If Windows denies
  symlink creation with WinError 1314 before the product assertion, report the
  environment limitation; do not weaken or skip the test.
- Use no filesystem discovery to select authoritative inputs. All authority
  paths and identities are exact constants or exact seal links.
- Write Gate 1 artifacts only below `results/research/` and
  `results/phase4/gate1/`. The final manifest is the final fallible write.
- Stop fail-closed on any pinned hash, class count, identity, safety flag,
  frozen split value, or historical byte mismatch.

## Preregistered Research Set

The Gate 1 execution will normalize these nine sources. The source journal,
not this plan, becomes authoritative after sealing.

1. Moskowitz, Ooi, and Pedersen, “Time Series Momentum,” *Journal of Financial
   Economics* 104 (2012), DOI `10.1016/j.jfineco.2011.11.003`.
2. Asness, Moskowitz, and Pedersen, “Value and Momentum Everywhere,” *The
   Journal of Finance* 68 (2013), DOI `10.1111/jofi.12021`.
3. Faber, “A Quantitative Approach to Tactical Asset Allocation,” *The Journal
   of Wealth Management* 9 (2007), DOI `10.3905/jwm.2007.674809`.
4. Maillard, Roncalli, and Teiletche, “The Properties of Equally Weighted Risk
   Contribution Portfolios,” *The Journal of Portfolio Management* 36 (2010),
   DOI `10.3905/jpm.2010.36.4.060`.
5. Moreira and Muir, “Volatility-Managed Portfolios,” *The Journal of Finance*
   72 (2017), DOI `10.1111/jofi.12513`.
6. Barroso and Santa-Clara, “Momentum Has Its Moments,” *Journal of Financial
   Economics* 116 (2015), DOI `10.1016/j.jfineco.2014.11.010`.
7. Huang, Li, Wang, and Zhou, “Time Series Momentum: Is It There?,” *Journal of
   Financial Economics* 135 (2020), DOI
   `10.1016/j.jfineco.2019.08.004`.
8. Cederburg, O'Doherty, Wang, and Yan, “On the Performance of
   Volatility-Managed Portfolios,” *Journal of Financial Economics* 138
   (2020), DOI `10.1016/j.jfineco.2020.04.015`.
9. Hurst, Ooi, and Pedersen, “A Century of Evidence on Trend-Following
   Investing,” *The Journal of Portfolio Management* 44 (2017), canonical AQR
   journal-article landing page.

Sources 7 and 8 are explicit counterevidence. Records must state instrument,
sample, leverage/shorting, implementation, and ETF-transfer limitations. No
reported numeric return is used to choose a grid value.

Four new hypotheses are admitted. The persisted family order is derived only
from canonical semantic IDs after hashing:

1. `cross_sectional_absolute_momentum_rotation`: rank all eight ETFs by lagged
   trailing return, admit only positive scores, hold equal weights in the top
   `top_k`, otherwise cash. Grid: `lookback_sessions=(63,126,252)`,
   `skip_sessions=(0,21)`, `top_k=(1,2,3)`,
   `rebalance_sessions=(21,42,63)`. Count 54.
2. `diversified_time_series_momentum`: admit each ETF when its own lagged
   trailing return is positive, then inverse-volatility weight admitted ETFs
   with deterministic cap redistribution and residual cash. Grid:
   `lookback_sessions=(63,126,252)`, `volatility_window=(20,60,120)`,
   `maximum_asset_weight=(0.25,0.50)`, `rebalance_sessions=(5,21)`. Count 36.
3. `volatility_managed_relative_momentum`: rank positive lagged trailing
   returns, equal-weight the top `top_k`, and scale portfolio gross exposure by
   lagged covariance-estimated portfolio volatility with gross cap 1.0. Grid:
   `lookback_sessions=(63,126,252)`, `volatility_window=(20,60)`,
   `target_portfolio_volatility=(0.08,0.12,0.16)`, `top_k=(1,2,3)`;
   `rebalance_sessions=21` is structural. Count 54.
4. `trend_filtered_equal_risk_allocation`: admit ETFs whose lagged close is
   above their lagged simple moving average, then inverse-volatility weight
   admitted ETFs with deterministic cap redistribution and residual cash.
   Grid: `trend_window=(100,150,200)`,
   `volatility_window=(20,60,120)`,
   `maximum_asset_weight=(0.25,0.50)`, `rebalance_sessions=(5,21)`. Count 36.

The aggregate new-candidate count is exactly 180, below all 500/3,000 limits.
Every family is long-only, unlevered, uses signal at session `t` and next
eligible-session execution, and keeps one fixed tuple for the complete
campaign. Float identities use canonical binary64 hexadecimal strings. Common
regime diagnostics use preregistered, lagged sign/relative-return partitions;
no boundary is learned from TRAIN or VALIDATION.

## Task 1: Canonical Identities and Base Models

**Files:**

- Create `src/investment_tracker/quant/phase4/__init__.py`
- Create `src/investment_tracker/quant/phase4/preregistration/__init__.py`
- Create `src/investment_tracker/quant/phase4/preregistration/canonical.py`
- Create `src/investment_tracker/quant/phase4/preregistration/models.py`
- Test `tests/quant/test_phase4_gate1_canonical.py`

1. Write failing tests for canonical UTF-8 JSON, NaN/infinity rejection,
   repository-relative POSIX paths, content/envelope identity separation,
   source/hypothesis/family/candidate/trial identities, and frozen
   extra-forbidden Pydantic models.
2. Write failing tests for the exact `PHASE4-RULE-SET-IDENTITY-v1` projection,
   `PHASE4-PARAMETER-TUPLE-IDENTITY-v1` projection, type-tagged float hex
   values, and ordered candidate/tuple population digest. Prove algorithm and
   parameter changes alter the right identity while labels, timestamps, and
   observed metrics do not.
3. Run `python -m pytest tests/quant/test_phase4_gate1_canonical.py -q` and
   retain the intended import/behavior failures as RED evidence.
4. Implement only the canonical primitives and base identity/value models.
5. Rerun the focused test GREEN, review the diff against the specification,
   then run readiness identity regressions:
   `python -m pytest tests/quant/test_phase4_readiness_contracts.py tests/quant/test_phase4_trial_authority.py -q`.
6. Commit: `feat: add Gate 1 canonical identities`.

## Task 2: Exact Read Capability and Static Safety Boundary

**Files:**

- Create `src/investment_tracker/quant/phase4/preregistration/access.py`
- Test `tests/quant/test_phase4_gate1_access.py`
- Test `tests/quant/test_phase4_gate1_contracts.py`

1. Write failing runtime tests showing every unlisted, escaped, symlinked,
   cache, validation, holdout, protected-symbol, provider, and dynamic path is
   rejected before existence lookup or read. Instrument the filesystem call
   seam to prove ordering.
2. Write failing AST/import tests banning imports of workflow, data/provider,
   optimizer/evaluator, backtest, metrics, validation execution, promotion,
   export, brokerage/trading, or canonical tracker writers. Assert the package
   has no generic `open`, glob, listing, URL fetch, or provider method.
3. Write failing tests for exact observed-read recording and all false/zero/
   empty safety flags.
4. Run the two test files and demonstrate RED for missing capability.
5. Implement `Gate1ReadCapability` with exact path/Git-object admission and a
   narrow trial-authority identity projection. Keep web research outside the
   executable subsystem.
6. Run focused GREEN, review, then regress readiness/security tests without
   changing the Windows symlink test.
7. Commit: `feat: enforce Gate 1 read boundary`.

## Task 3: Immutable Artifact Store and Append-Only Journals

**Files:**

- Create `src/investment_tracker/quant/phase4/preregistration/artifacts.py`
- Create `src/investment_tracker/quant/phase4/preregistration/journal.py`
- Test `tests/quant/test_phase4_gate1_artifacts.py`
- Test `tests/quant/test_phase4_gate1_journal.py`

1. Write failing artifact tests for canonical content paths, exact-byte and
   envelope verification, no overwrite, collision, symlink component, path
   escape, malformed kind/filename, read-back, and final no-fallible-post-write
   commit behavior.
2. Write failing journal tests for canonical one-line-plus-LF records, genesis
   and predecessor chains, record/file/terminal digests, duplicate IDs,
   mutation/deletion/insertion/reorder/partial tail/non-UTF-8 rejection,
   idempotent retry, writer lock, and sealed-journal rejection.
3. Demonstrate RED, implement only storage/journal code, demonstrate GREEN, and
   review all file-operation targets.
4. Run readiness artifact regressions and the existing security suite. Record
   WinError 1314 only if the unchanged symlink test cannot create its fixture.
5. Commit: `feat: add immutable Gate 1 evidence storage`.

## Task 4: Machine-Verifiable Baseline Provenance

**Files:**

- Create `src/investment_tracker/quant/phase4/preregistration/provenance.py`
- Create `src/investment_tracker/quant/phase4/preregistration/baselines.py`
- Test `tests/quant/test_phase4_gate1_baselines.py`

1. Write failing tests for the exact readiness manifest, exact sealed
   136-trial authority envelope, and restricted identity-only projection.
   Assert exactly-once authority membership for `trend` and `momentum` and
   absence for `trend_momentum` and `risk_managed_trend`.
2. Write failing tests for the generator revision/blob/content hash, exact grid
   definitions and tuples, deterministic four candidate IDs, exact executed
   artifact paths/kinds/content/envelope identities, and all four implementation
   bundle identities.
3. Write failing tests requiring exact class counts 2/2, null trial-artifact
   fields for source-defined controls, no performance field in the projection,
   full-exposure-comparator wording, zero family/candidate consumption, and
   selection ineligibility.
4. Demonstrate RED. Implement Git object reads and exact-path reads only through
   the capability. Do not enumerate `results/experiments` or parse numeric
   result fields.
5. Demonstrate GREEN; compare every constant with the specification; run Phase
   4 readiness trial-authority regressions.
6. Commit: `feat: verify Gate 1 comparison baselines`.

## Task 5: Source and Hypothesis Governance

**Files:**

- Create `src/investment_tracker/quant/phase4/preregistration/policy.py`
- Create `src/investment_tracker/quant/phase4/preregistration/campaign_definition.py`
- Test `tests/quant/test_phase4_gate1_research_policy.py`

1. Write failing tests for all source schema fields, source-tier enum,
   citation verification, null-with-explanation behavior, no fabricated facts,
   cutoff enforcement, and `phase4_validation_information_used=false`.
2. Write failing tests for immutable hypothesis lifecycle, two-source and
   tier-1-to-3 minimum support, rejected-record retention, material-change
   identity change, one-to-one admitted family mapping, and all false access
   flags.
3. Encode the nine normalized sources and four exact hypotheses listed above,
   including limitations/counterevidence and complete algorithm/grid prose.
   This module is declarative input only and contains no market/result reader.
4. Demonstrate RED, implement models/validators/declarations, demonstrate
   GREEN, and manually cross-check each DOI/landing page against the research
   source.
5. Run access/contract/journal regressions.
6. Commit: `feat: preregister Gate 1 research hypotheses`.

## Task 6: Family Definitions, Deterministic Grids, and Budget

**Files:**

- Create `src/investment_tracker/quant/phase4/preregistration/grids.py`
- Extend `src/investment_tracker/quant/phase4/preregistration/models.py`
- Extend `src/investment_tracker/quant/phase4/preregistration/policy.py`
- Test `tests/quant/test_phase4_gate1_grids.py`

1. Write failing tests for one family per admitted hypothesis, baseline
   distinctions, exact algorithm fields, `rule_set_sha256`, typed dimensions,
   structural predicates, deterministic Cartesian order, adjacent-only
   neighborhoods, row tuple/candidate/trial identities, and aggregate digest.
2. Assert exact family counts `(54,36,54,36)` by semantic name and aggregate
   count 180 regardless of input mapping/filesystem order.
3. Assert Phase 4 budget positions start at 1, not 137; historical trials and
   baselines consume zero; duplicates do not inflate counts; limits 11/501/3001
   fail before append; no adaptive generation API exists.
4. Demonstrate RED, implement minimal pure expansion and budget validation,
   demonstrate GREEN, and inspect serialized full grid output.
5. Run all Gate 1 tests plus optimizer/readiness regressions to prove isolation.
6. Commit: `feat: freeze Gate 1 families and grids`.

## Task 7: Fixed-Strategy Durability, Stop, and Survivor Policies

**Files:**

- Extend `src/investment_tracker/quant/phase4/preregistration/policy.py`
- Extend `src/investment_tracker/quant/phase4/preregistration/models.py`
- Test `tests/quant/test_phase4_gate1_policies.py`

1. Write failing tests for exact `PERSISTENT_OOS_FAILURE`: 50 consecutive
   non-positive/unavailable validation benchmark-excess outcomes; positive
   excess resets; isolated robustness, friction, bootstrap, neighborhood, or
   other failures never increment or terminate a family.
2. Write failing tests for the exact fixed long-only deployment fields,
   immutable rule/tuple identities across every evaluation case, no TRAIN
   fitting, no annual/fold/periodic reoptimization, unchanged split/warm-up/
   reset/next-session rules, null CAGR hard target, and fixed-parameter
   chronological proof mode.
3. Write synthetic-only tests for calendar month/year compounding, positive
   percentages, average positive/negative month, worst periods, losing-month
   streak, Gregorian 12/36/60-month rolling anchors, period completeness,
   concentration, and `UNKNOWN / INSUFFICIENT_DATA` behavior.
4. Write survivor tests for every existing hard gate, supported durability
   evidence completeness, exact robustness-first lexicographic keys, lower-CAGR
   durable candidate outranking fragile high-CAGR candidate, one winner, no
   baseline winner, and `NO_CREDIBLE_STRATEGY_FOUND`.
5. Assert max drawdown, Calmar, DSR, and PBO stay unavailable. Assert the Phase
   5 contract is one-way, same-tuple, no substitution/proxy/feedback/provider
   authorization, with drawdown conditional on DQ-030 resolution.
6. Demonstrate RED, implement pure policy/calculation functions, demonstrate
   GREEN, review for any validation-derived threshold, and run robustness/
   walk-forward/readiness regressions.
7. Commit: `feat: freeze Gate 1 durability policies`.

## Task 8: Seal Orchestrator, Report, and CLI

**Files:**

- Create `src/investment_tracker/quant/phase4/preregistration/seal.py`
- Create `src/investment_tracker/quant/phase4/preregistration/report.py`
- Create `src/investment_tracker/quant/phase4/preregistration/cli.py`
- Test `tests/quant/test_phase4_gate1_seal.py`
- Test `tests/quant/test_phase4_gate1_cli.py`

1. Write failing integration tests in temporary repositories for dependency
   cross-links, exact counts, source cutoff, journals, notes digest, baseline
   2/2 status, family/grid/population identities, policy identities, QFQ and
   unavailable-statistic fields, fixed-strategy fields, exact read ledger, and
   every safety flag.
2. Write failure-injection tests proving report/evidence publication precedes
   seal, the seal is the final write, and no failed call can coexist with a new
   valid seal. Test every specified failure code and no repair/substitution/
   provider fallback.
3. Write CLI tests for one provider-free exact-root command and structured
   JSON success/failure. The CLI exposes no dates, symbols, provider, trading,
   search, or validation-result arguments.
4. Demonstrate RED, implement the orchestrator/report/CLI, demonstrate GREEN,
   and review write ordering and failure handling.
5. Run the complete Gate 1 suite and all readiness/Phase 3 contract tests.
6. Commit: `feat: add Gate 1 sealing workflow`.

## Task 9: Independent Implementation Review

1. Ask an independent reviewer to inspect Tasks 1–8 against the authoritative
   specification and this plan. The reviewer must not edit files or access
   validation, market bars, providers, holdout, protected symbols, or result
   metrics.
2. Resolve every material finding with a fresh RED test, minimal fix, GREEN,
   regressions, and a dedicated review-fix commit.
3. Obtain an explicit clean re-review before Gate 1 execution.

## Task 10: Execute and Seal Gate 1 Once

**Generated files:**

- `results/research/sources.jsonl`
- `results/research/hypothesis_registry.jsonl`
- `results/research/research_notes.md`
- Content-addressed evidence below `results/phase4/gate1/`

1. Record the exact UTC research cutoff and independently recheck all nine
   citations. Generate the research notes as a comprehensive, citation-backed
   artifact covering mechanism, transfer limits, counterevidence, fixed grids,
   and rejected alternatives. Do not include or inspect project performance.
2. Snapshot exact hashes of protected Phase 2/Phase 3/readiness trees before
   execution.
3. Run the provider-free Gate 1 CLI exactly once against the repository root.
   Stop immediately on any mismatch; do not repair, substitute, or discover a
   newer artifact.
4. Verify the journal chains, all content/envelope identities, class counts,
   exact 180-candidate population, budget positions, policies, fixed-strategy
   fields, access ledger, false/zero safety fields, report, and final seal.
5. Recompute protected historical tree hashes and require byte equality.
6. Commit only newly generated `results/research/` and
   `results/phase4/gate1/` evidence:
   `research: seal Phase 4 Gate 1 preregistration`.

## Task 11: Complete Verification and Stop

1. Run focused Gate 1 tests.
2. Run all quant, readiness, universe, governance, security, and full repository
   tests. Do not weaken the Windows symlink test; classify only the known
   fixture-creation WinError 1314 as an environment limitation.
3. Verify `git diff`, `git status`, commit boundaries, artifact identities,
   access flags, and absence of changes to frozen modules/evidence.
4. Report the spec path/commit, implementation commits, source/hypothesis/
   family/candidate counts, baseline 2/2 provenance, exact durability contract,
   artifact/seal identities, verification results, and all prohibited-access/
   execution statuses.
5. If and only if every Gate 1 condition passes, report
   `PHASE4_PREREGISTRATION_SEALED`, then stop. Do not begin Gate 2 or Gate 3.
