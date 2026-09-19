# ETF Quantitative Research Subsystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an ETF-only, quote-data-driven, deterministic research and portfolio-backtesting subsystem that is incapable of live trading or canonical tracker mutation.

**Architecture:** Add an isolated `investment_tracker.quant` package with guarded data access, immutable Parquet datasets, completed-bar strategies, next-open simulation, stage-scoped validation APIs, append-only experiments, and one-way Moomoo StrategyBase export. Existing frozen and canonical modules remain unchanged; the quant package may reuse only the existing governance symbol guard.

**Tech Stack:** Python 3.12, Pydantic 2, pandas, NumPy, PyArrow, PyYAML, exchange-calendars, optional/lazy `moomoo-api`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-11-etf-quant-research-subsystem-design.md`

## Global Constraints

- Preserve TPC-v1.2, REPLAY-v1.0, CALC-v1.2, and ROBUST-v1.0 unchanged.
- Do not modify existing replay, calculation, robustness, governed backtest, canonical-write, or Phase Matrix modules.
- Call `assert_symbol_allowed(symbol)` before cache-key construction, filesystem access, provider creation, or historical inspection.
- Keep HACK, SOXX, NLR, URNM, and GEV inaccessible.
- `TRADING_MODE` is structurally fixed to `SIMULATE`; no configuration, CLI, environment, or hidden live-trading path exists.
- Research outputs are append-only local artifacts and cannot mutate canonical tracker state.
- FINAL_HOLDOUT is accessible only to the sealed evaluator and never feeds optimizer APIs.
- Generated Moomoo code is one-way, simulation/backtest-only, and uses only supplied documented StrategyBase functions.
- Undefined evidence is `None`/`UNKNOWN`; no metric is fabricated.
- Preserve the existing Windows symlink test unchanged and report its privilege failure separately.

---

### Task 1: Package safety, strict configuration, and dependency boundary

**Files:**
- Create: `src/investment_tracker/quant/__init__.py`
- Create: `src/investment_tracker/quant/constants.py`
- Create: `src/investment_tracker/quant/configuration.py`
- Create: `src/investment_tracker/quant/defaults/universe.yaml`
- Create: `src/investment_tracker/quant/defaults/backtest.yaml`
- Create: `src/investment_tracker/quant/defaults/validation.yaml`
- Modify: `pyproject.toml`
- Create: `tests/quant/test_configuration_and_boundaries.py`

**Interfaces:**
- Consumes: `investment_tracker.governance.assert_symbol_allowed(symbol: str) -> str`.
- Produces: `TRADING_MODE`, `UniverseConfig`, `BacktestConfig`, `ValidationConfig`, `QuantConfig`, and `load_quant_config(path: Path | None) -> QuantConfig`.

- [ ] **Step 1: Write failing configuration and boundary tests**

```python
def test_config_rejects_locked_symbol():
    with pytest.raises(LockedHoldoutError):
        UniverseConfig(version="UNIVERSE-v1", symbols=["SPY", "HACK"])

def test_unknown_config_key_is_rejected():
    with pytest.raises(ValidationError):
        BacktestConfig(version="BACKTEST-CONFIG-v1", initial_capital=10_000,
                       allocation=1.0, commission_bps=1, slippage_bps=2,
                       allow_fractional=True, leverage=False, mystery=True)

def test_quant_package_has_no_canonical_mutation_imports():
    assert forbidden_quant_imports(Path("src/investment_tracker/quant")) == []
```

- [ ] **Step 2: Run tests and confirm imports/models are missing**

Run: `pytest tests/quant/test_configuration_and_boundaries.py -q`
Expected: collection failure because `investment_tracker.quant` does not exist.

- [ ] **Step 3: Implement literal simulation mode, strict models, YAML loader, defaults, and AST import scan**

```python
TRADING_MODE: Final[Literal["SIMULATE"]] = "SIMULATE"

class UniverseConfig(StrictQuantModel):
    version: Literal["UNIVERSE-v1"]
    symbols: tuple[str, ...]

    @field_validator("symbols")
    @classmethod
    def allowed_unique_symbols(cls, values):
        normalized = tuple(assert_symbol_allowed(v) for v in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("universe symbols must be unique")
        return normalized
```

- [ ] **Step 4: Run focused and existing tests**

Run: `pytest tests/quant/test_configuration_and_boundaries.py tests/test_governance.py -q`
Expected: all focused tests pass.

- [ ] **Step 5: Commit the slice**

```powershell
git add pyproject.toml src/investment_tracker/quant tests/quant/test_configuration_and_boundaries.py
git commit -m "feat: add guarded quant configuration"
```

### Task 2: Typed bar model and calendar-aware data validation

**Files:**
- Create: `src/investment_tracker/quant/data/__init__.py`
- Create: `src/investment_tracker/quant/data/models.py`
- Create: `src/investment_tracker/quant/data/validation.py`
- Create: `tests/quant/test_data_validation.py`

**Interfaces:**
- Produces: `DataRequest`, `DatasetMetadata`, `DataQualityIssue`, `DataValidationReport`, `DataQualityError`, and `BarDataValidator.validate(frame, request) -> DataValidationReport`.

- [ ] **Step 1: Write failing tests for valid sessions, holiday handling, duplicates, OHLC, negatives, NaNs, and timezone conflicts**

```python
def test_exchange_holiday_is_not_reported_missing():
    frame = daily_bars(["2024-07-03", "2024-07-05"])
    report = BarDataValidator("XNYS").validate(frame, request("2024-07-03", "2024-07-05"))
    assert report.clean

@pytest.mark.parametrize("mutation,code", [
    (lambda f: pd.concat([f, f.iloc[[0]]]), "DUPLICATE_TIMESTAMP"),
    (lambda f: f.assign(high=0.5), "INVALID_OHLC"),
    (lambda f: f.assign(volume=-1), "NEGATIVE_VOLUME"),
    (lambda f: f.assign(close=np.nan), "NAN_VALUE"),
])
def test_material_defects_fail_closed(mutation, code):
    report = BarDataValidator("XNYS").validate(mutation(valid_frame()), request())
    assert not report.clean
    assert code in {issue.code for issue in report.issues}
```

- [ ] **Step 2: Run and verify expected missing-module failures**

Run: `pytest tests/quant/test_data_validation.py -q`
Expected: collection failure for missing data validation module.

- [ ] **Step 3: Implement immutable request/metadata models and non-mutating validator**

```python
expected = calendar.sessions_in_range(request.start, request.end)
observed = frame.index.normalize()
missing = expected.difference(observed)
if len(missing):
    issues.append(DataQualityIssue("MISSING_SESSION", tuple(map(str, missing))))
```

- [ ] **Step 4: Run validation tests**

Run: `pytest tests/quant/test_data_validation.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit the slice**

```powershell
git add src/investment_tracker/quant/data tests/quant/test_data_validation.py
git commit -m "feat: validate ETF bar datasets"
```

### Task 3: Immutable versioned Parquet cache and guarded repository

**Files:**
- Create: `src/investment_tracker/quant/data/cache.py`
- Create: `src/investment_tracker/quant/data/repository.py`
- Create: `tests/quant/test_cache_repository.py`

**Interfaces:**
- Consumes: `DataRequest`, `DatasetMetadata`, `BarDataValidator`, and `assert_symbol_allowed`.
- Produces: `ImmutableParquetCache.find(request)`, `admit(request, frame, report)`, `HistoricalDataRepository.load(request)`, and `content_hash(frame)`.

- [ ] **Step 1: Write failing tests proving denial-before-filesystem/provider, atomic admission, hash verification, immutability, quarantine, and refresh versioning**

```python
def test_locked_symbol_is_denied_before_cache_or_provider(tmp_path):
    cache = ExplodingCache()
    factory = ExplodingProviderFactory()
    repo = HistoricalDataRepository(cache, factory, validator())
    with pytest.raises(LockedHoldoutError):
        repo.load(request(symbol="HACK"))

def test_different_refresh_creates_new_immutable_version(tmp_path):
    cache = ImmutableParquetCache(tmp_path)
    first = cache.admit(req, frame_a, clean_report)
    second = cache.admit(req, frame_b, clean_report)
    assert first.path != second.path
    assert first.metadata.content_hash != second.metadata.content_hash
    assert first.path.exists()
```

- [ ] **Step 2: Run and verify behavior is absent**

Run: `pytest tests/quant/test_cache_repository.py -q`
Expected: import or attribute failures for cache/repository APIs.

- [ ] **Step 3: Implement canonical frame hashing, atomic temporary-directory admission, immutable version directories, readback verification, quarantine, and guard-first orchestration**

```python
def load(self, request: DataRequest) -> CachedDataset:
    symbol = assert_symbol_allowed(request.symbol)
    guarded = request.model_copy(update={"symbol": symbol})
    cached = self._cache.find(guarded)
    if cached is not None:
        return cached
    provider = self._provider_factory()
    frame, provider_version = provider.fetch(guarded)
    report = self._validator.validate(frame, guarded)
    return self._cache.admit(guarded, frame, report, provider_version)
```

- [ ] **Step 4: Run cache and data tests**

Run: `pytest tests/quant/test_cache_repository.py tests/quant/test_data_validation.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit the slice**

```powershell
git add src/investment_tracker/quant/data tests/quant/test_cache_repository.py
git commit -m "feat: add immutable guarded market data cache"
```

### Task 4: Quote-only paginated Moomoo adapter

**Files:**
- Create: `src/investment_tracker/quant/data/moomoo_client.py`
- Create: `tests/quant/test_moomoo_client.py`

**Interfaces:**
- Consumes: `DataRequest`.
- Produces: `MoomooHistoricalDataSource.fetch(request) -> tuple[pd.DataFrame, str | None]`.

- [ ] **Step 1: Write failing contract tests for lazy import, US symbol mapping, daily QFQ arguments, pagination, loop detection, error propagation, and context closing**

```python
def test_fetch_pages_daily_qfq_and_closes_context():
    context = FakeQuoteContext(pages=[page_one, page_two])
    frame, version = MoomooHistoricalDataSource(context_factory=lambda **_: context).fetch(req)
    assert list(frame.index) == expected_dates
    assert context.calls[0]["code"] == "US.SPY"
    assert context.calls[0]["ktype"] == FakeKLType.K_DAY
    assert context.calls[0]["autype"] == FakeAuType.QFQ
    assert context.closed
```

- [ ] **Step 2: Run and verify missing adapter failure**

Run: `pytest tests/quant/test_moomoo_client.py -q`
Expected: collection failure for missing adapter.

- [ ] **Step 3: Implement adapter using only documented quote APIs**

```python
ret, data, next_key = context.request_history_kline(
    code=f"US.{request.symbol}", start=request.start.isoformat(),
    end=request.end.isoformat(), ktype=sdk.KLType.K_DAY,
    autype=sdk.AuType.QFQ, fields=[sdk.KL_FIELD.ALL],
    max_count=1000, page_req_key=page_key,
    extended_time=False, session=sdk.Session.RTH,
)
```

- [ ] **Step 4: Run adapter and repository tests**

Run: `pytest tests/quant/test_moomoo_client.py tests/quant/test_cache_repository.py -q`
Expected: all tests pass without importing the real SDK.

- [ ] **Step 5: Commit the slice**

```powershell
git add src/investment_tracker/quant/data/moomoo_client.py tests/quant/test_moomoo_client.py
git commit -m "feat: add quote-only Moomoo history adapter"
```

### Task 5: Explainable strategy families and indicators

**Files:**
- Create: `src/investment_tracker/quant/strategies/__init__.py`
- Create: `src/investment_tracker/quant/strategies/base.py`
- Create: `src/investment_tracker/quant/strategies/indicators.py`
- Create: `src/investment_tracker/quant/strategies/trend.py`
- Create: `src/investment_tracker/quant/strategies/momentum.py`
- Create: `src/investment_tracker/quant/strategies/trend_momentum.py`
- Create: `src/investment_tracker/quant/strategies/risk_managed.py`
- Create: `src/investment_tracker/quant/strategies/registry.py`
- Create: `tests/quant/test_strategies.py`

**Interfaces:**
- Produces: `StrategyDefinition`, `SignalFrame`, `sma`, `momentum`, `atr`, `realized_volatility`, and four strategy implementations returning target exposures in [0, 1].

- [ ] **Step 1: Write failing hand-calculated indicator and completed-bar signal tests**

```python
def test_sma_uses_only_current_and_prior_values():
    values = pd.Series([10.0, 20.0, 30.0, 999.0])
    assert sma(values, 3).iloc[2] == 20.0

def test_trend_target_is_long_only_and_capped():
    strategy = TrendStrategy(fast=2, slow=3, allocation=0.5)
    targets = strategy.targets(frame_with_closes([1, 2, 3, 2]))
    assert targets.tolist() == [0.0, 0.0, 0.5, 0.0]
```

- [ ] **Step 2: Run and verify missing strategy APIs**

Run: `pytest tests/quant/test_strategies.py -q`
Expected: collection failure for missing strategy package.

- [ ] **Step 3: Implement deterministic indicators and strategies with explicit metadata**

```python
class StrategyDefinition(Protocol):
    family: str
    parameters: Mapping[str, int | float | str]
    entry_rule: str
    exit_rule: str
    position_sizing: str
    maximum_exposure: float
    execution_timing: Literal["NEXT_BAR_OPEN"]
    risk_rules: str
    def targets(self, bars: pd.DataFrame) -> pd.Series: ...
```

- [ ] **Step 4: Run strategy tests**

Run: `pytest tests/quant/test_strategies.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit the slice**

```powershell
git add src/investment_tracker/quant/strategies tests/quant/test_strategies.py
git commit -m "feat: add explainable ETF strategies"
```

### Task 6: Next-open portfolio engine, friction, metrics, and benchmarks

**Files:**
- Create: `src/investment_tracker/quant/backtest/__init__.py`
- Create: `src/investment_tracker/quant/backtest/models.py`
- Create: `src/investment_tracker/quant/backtest/friction.py`
- Create: `src/investment_tracker/quant/backtest/portfolio.py`
- Create: `src/investment_tracker/quant/backtest/engine.py`
- Create: `src/investment_tracker/quant/backtest/metrics.py`
- Create: `src/investment_tracker/quant/backtest/benchmark.py`
- Create: `tests/quant/test_backtest_engine.py`
- Create: `tests/quant/test_metrics_and_benchmarks.py`

**Interfaces:**
- Consumes: validated OHLCV frames and target exposure series.
- Produces: `ExecutionAssumptions`, `Fill`, `Trade`, `BacktestResult`, `run_backtest`, `calculate_metrics`, `buy_and_hold`, and `cash_benchmark`.

- [ ] **Step 1: Write failing manually calculable execution/accounting tests**

```python
def test_signal_on_day_one_executes_at_day_two_open():
    bars = bars_from(open=[10, 20, 30], close=[11, 21, 31])
    result = run_backtest(bars, pd.Series([1.0, 1.0, 0.0], index=bars.index), assumptions())
    assert result.fills[0].timestamp == bars.index[1]
    assert result.fills[0].reference_price == 20

def test_fee_and_slippage_reduce_cash_and_round_trip_return():
    result = run_backtest(two_bar_fixture(), targets=[1.0, 0.0],
                          assumptions=assumptions(commission_bps=10, slippage_bps=20))
    assert result.final_equity == pytest.approx(derived_terminal_equity)
```

- [ ] **Step 2: Write failing literal metric tests**

```python
def test_max_drawdown_from_known_equity_path():
    metrics = calculate_metrics(series([100, 120, 90, 108]))
    assert metrics.max_drawdown == pytest.approx(-0.25)

def test_undefined_ratios_are_none():
    metrics = calculate_metrics(series([100, 100, 100]))
    assert metrics.sharpe is None
    assert metrics.sortino is None
    assert metrics.calmar is None
```

- [ ] **Step 3: Run and verify missing engine/metric failures**

Run: `pytest tests/quant/test_backtest_engine.py tests/quant/test_metrics_and_benchmarks.py -q`
Expected: collection failures for missing backtest package.

- [ ] **Step 4: Implement target-to-order deltas, adverse fills, cash/position ledger, t+1 scheduling, metrics, matching benchmarks, and aggregate portfolio results**

```python
for position in range(1, len(bars)):
    target = float(targets.iloc[position - 1])
    portfolio.rebalance_at_open(bars.iloc[position], target, assumptions)
    portfolio.mark_to_close(bars.iloc[position])
```

- [ ] **Step 5: Run backtest, strategy, and benchmark tests**

Run: `pytest tests/quant/test_backtest_engine.py tests/quant/test_metrics_and_benchmarks.py tests/quant/test_strategies.py -q`
Expected: all tests pass.

- [ ] **Step 6: Commit the slice**

```powershell
git add src/investment_tracker/quant/backtest tests/quant/test_backtest_engine.py tests/quant/test_metrics_and_benchmarks.py
git commit -m "feat: add next-open ETF backtest engine"
```

### Task 7: Stage-scoped splits, walk-forward validation, and sealed holdout

**Files:**
- Create: `src/investment_tracker/quant/validation/__init__.py`
- Create: `src/investment_tracker/quant/validation/splits.py`
- Create: `src/investment_tracker/quant/validation/access.py`
- Create: `src/investment_tracker/quant/validation/walk_forward.py`
- Create: `src/investment_tracker/quant/validation/holdout.py`
- Create: `tests/quant/test_validation_isolation.py`
- Create: `tests/quant/test_walk_forward.py`

**Interfaces:**
- Produces: `DataStage`, `SplitDefinition`, `ResearchDataView`, `generate_walk_forward_folds`, `FrozenCandidateManifest`, and `SealedHoldoutEvaluator.evaluate`.

- [ ] **Step 1: Write failing tests that optimizer-facing views cannot name/load FINAL_HOLDOUT and that folds are chronological/disjoint**

```python
def test_research_view_rejects_final_holdout():
    view = ResearchDataView(store)
    with pytest.raises(HoldoutAccessError):
        view.load("SPY", DataStage.FINAL_HOLDOUT)

def test_walk_forward_folds_are_chronological_and_disjoint():
    folds = generate_walk_forward_folds(sessions, train_years=5, test_years=1)
    assert all(f.train_end < f.test_start <= f.test_end for f in folds)
    assert all(a.test_end < b.test_start for a, b in pairwise(folds))
```

- [ ] **Step 2: Write failing tests for candidate digest completeness and one-use holdout closure**

```python
def test_candidate_digest_changes_when_fee_model_changes():
    assert manifest(fee_bps=1).digest != manifest(fee_bps=2).digest

def test_holdout_evaluation_closes_candidate_cycle(tmp_path):
    evaluator.evaluate(frozen_manifest, tmp_path)
    with pytest.raises(HoldoutReuseError):
        evaluator.evaluate(frozen_manifest, tmp_path)
```

- [ ] **Step 3: Run and verify missing validation APIs**

Run: `pytest tests/quant/test_validation_isolation.py tests/quant/test_walk_forward.py -q`
Expected: collection failures for missing validation package.

- [ ] **Step 4: Implement typed stage APIs, hashed splits/manifests, rolling folds, and append-only sealed use records**

```python
class ResearchDataView:
    def load(self, symbol: str, stage: Literal[DataStage.TRAIN, DataStage.VALIDATION]):
        if stage is DataStage.FINAL_HOLDOUT:
            raise HoldoutAccessError("FINAL_HOLDOUT is sealed")
        return self._store.load(symbol, stage)
```

- [ ] **Step 5: Run validation tests**

Run: `pytest tests/quant/test_validation_isolation.py tests/quant/test_walk_forward.py -q`
Expected: all tests pass.

- [ ] **Step 6: Commit the slice**

```powershell
git add src/investment_tracker/quant/validation tests/quant/test_validation_isolation.py tests/quant/test_walk_forward.py
git commit -m "feat: seal final holdout access"
```

### Task 8: Robustness, sensitivity, deterministic scoring, and bounded search

**Files:**
- Create: `src/investment_tracker/quant/validation/robustness.py`
- Create: `src/investment_tracker/quant/validation/bootstrap.py`
- Create: `src/investment_tracker/quant/optimizer/__init__.py`
- Create: `src/investment_tracker/quant/optimizer/candidate_generator.py`
- Create: `src/investment_tracker/quant/optimizer/scorer.py`
- Create: `src/investment_tracker/quant/optimizer/evaluator.py`
- Create: `src/investment_tracker/quant/optimizer/search.py`
- Create: `tests/quant/test_robustness_scoring.py`
- Create: `tests/quant/test_optimizer.py`

**Interfaces:**
- Produces: `neighbor_parameters`, `friction_scenarios`, `bootstrap_interval`, `ScoreBreakdown`, `score_candidate`, `CandidateGenerator`, `SearchBudget`, `SearchResult`, and `run_search`.

- [ ] **Step 1: Write failing tests for neighboring parameters, cost stress, score penalties, missing-metric rejection, deterministic enumeration, 500 cap, and 50-stale stop**

```python
def test_unstable_neighbor_performance_reduces_score():
    stable = score_candidate(evidence(parameter_stability=0.9))
    unstable = score_candidate(evidence(parameter_stability=0.2))
    assert stable.total > unstable.total

def test_search_never_exceeds_family_budget():
    result = run_search(generator(700), evaluator, SearchBudget(max_candidates=500, patience=50))
    assert result.evaluated_count == 500
    assert result.stop_reason == "MAX_CANDIDATES"
```

- [ ] **Step 2: Run and verify missing optimizer APIs**

Run: `pytest tests/quant/test_robustness_scoring.py tests/quant/test_optimizer.py -q`
Expected: collection failures for missing modules.

- [ ] **Step 3: Implement deterministic neighborhood/friction/date tests, seeded bootstrap, fixed score weights, fail-closed required metrics, and bounded ordered search**

```python
for parameters in generator:
    if evaluated == budget.max_candidates:
        return SearchResult(..., stop_reason="MAX_CANDIDATES")
    evidence = evaluator(parameters)
    if evidence.robustness_deteriorated:
        return SearchResult(..., stop_reason="ROBUSTNESS_DETERIORATED")
    stale = 0 if evidence.score > best + budget.meaningful_improvement else stale + 1
    if stale >= budget.patience:
        return SearchResult(..., stop_reason="NO_MEANINGFUL_IMPROVEMENT_50")
```

- [ ] **Step 4: Run optimizer and validation tests**

Run: `pytest tests/quant/test_robustness_scoring.py tests/quant/test_optimizer.py tests/quant/test_walk_forward.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit the slice**

```powershell
git add src/investment_tracker/quant/validation src/investment_tracker/quant/optimizer tests/quant/test_robustness_scoring.py tests/quant/test_optimizer.py
git commit -m "feat: add deterministic robust strategy search"
```

### Task 9: Append-only experiments, validated snapshots, and baseline promotion

**Files:**
- Create: `src/investment_tracker/quant/experiments.py`
- Create: `src/investment_tracker/quant/promotion.py`
- Create: `tests/quant/test_experiments_and_promotion.py`

**Interfaces:**
- Produces: `ExperimentRecord`, `ExperimentStore.append`, `ValidatedSnapshot`, `PromotionGate`, `promote_candidate`, and read-only `BaselineRegistry`.

- [ ] **Step 1: Write failing tests for unique immutable experiments, complete manifests, failed promotion gates, and non-overwriting baseline versions**

```python
def test_experiment_store_never_overwrites(tmp_path):
    store = ExperimentStore(tmp_path)
    store.append(record(experiment_id="exp-1"))
    with pytest.raises(ArtifactExistsError):
        store.append(record(experiment_id="exp-1"))

def test_promotion_creates_new_snapshot_without_mutating_baseline(tmp_path):
    before = baseline_path.read_bytes()
    snapshot = promote_candidate(candidate, passed_gate(), registry)
    assert baseline_path.read_bytes() == before
    assert snapshot.status == "VALIDATED_SNAPSHOT"
```

- [ ] **Step 2: Run and verify missing artifact APIs**

Run: `pytest tests/quant/test_experiments_and_promotion.py -q`
Expected: import failures for missing modules.

- [ ] **Step 3: Implement canonical JSON hashing, exclusive file creation, immutable snapshots, explicit gates, and additive baseline version directories**

```python
with path.open("x", encoding="utf-8") as handle:
    json.dump(record.model_dump(mode="json"), handle, sort_keys=True, separators=(",", ":"))
```

- [ ] **Step 4: Run experiment, optimizer, and boundary tests**

Run: `pytest tests/quant/test_experiments_and_promotion.py tests/quant/test_optimizer.py tests/quant/test_configuration_and_boundaries.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit the slice**

```powershell
git add src/investment_tracker/quant/experiments.py src/investment_tracker/quant/promotion.py tests/quant/test_experiments_and_promotion.py
git commit -m "feat: add immutable research promotion artifacts"
```

### Task 10: Reports and research CLI

**Files:**
- Create: `src/investment_tracker/quant/reports/__init__.py`
- Create: `src/investment_tracker/quant/reports/generate_report.py`
- Create: `src/investment_tracker/quant/cli.py`
- Create: `tests/quant/test_reports_and_cli.py`

**Interfaces:**
- Consumes: immutable experiment/snapshot artifacts.
- Produces: deterministic leaderboard rows, Markdown report, and `download`, `backtest`, `optimize`, `validate`, `report`, `export-moomoo` commands.

- [ ] **Step 1: Write failing tests for UNKNOWN rendering, deterministic ranking, safe command surface, and absence of trading-mode options**

```python
def test_missing_metrics_render_unknown():
    report = render_report([experiment(sharpe=None)])
    assert "Sharpe: UNKNOWN" in report

def test_cli_has_no_live_or_trade_switches():
    help_text = parser().format_help().lower()
    assert "live" not in help_text
    assert "trade" not in help_text
```

- [ ] **Step 2: Run and verify missing report/CLI APIs**

Run: `pytest tests/quant/test_reports_and_cli.py -q`
Expected: collection failure for missing modules.

- [ ] **Step 3: Implement read-only artifact reporting and CLI orchestration with non-zero fail-closed exits**

```python
subcommands = ("download", "backtest", "optimize", "validate", "report", "export-moomoo")
for name in subcommands:
    subparsers.add_parser(name)
```

- [ ] **Step 4: Run report, artifact, and CLI tests**

Run: `pytest tests/quant/test_reports_and_cli.py tests/quant/test_experiments_and_promotion.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit the slice**

```powershell
git add src/investment_tracker/quant/reports src/investment_tracker/quant/cli.py tests/quant/test_reports_and_cli.py
git commit -m "feat: add quant reports and safe CLI"
```

### Task 11: Documented one-way Moomoo StrategyBase exporter

**Files:**
- Create: `src/investment_tracker/quant/moomoo/__init__.py`
- Create: `src/investment_tracker/quant/moomoo/strategybase_exporter.py`
- Create: `tests/quant/test_strategybase_exporter.py`

**Interfaces:**
- Consumes: immutable `ValidatedSnapshot` for a supported strategy.
- Produces: `export_strategy(snapshot, destination) -> Path` and no execution/import API.

- [ ] **Step 1: Review all of `docs/moomoo/Algo Manual.md` in bounded chunks and record the exact documented functions required for MA, bar close, position quantity, order lookup, market order, and close position**

Run: `$lines = Get-Content 'docs/moomoo/Algo Manual.md'; for ($i=0; $i -lt $lines.Count; $i+=800) { $lines[$i..([Math]::Min($i+799,$lines.Count-1))] }`
Expected: all 15,866 lines reviewed before source generation.

- [ ] **Step 2: Write failing tests for validated-only input, supported-rule translation, positive close quantity, duplicate-order prevention, no filesystem/network/import execution, and no live-trading path**

```python
def test_export_requires_validated_snapshot(tmp_path):
    with pytest.raises(ExportBlockedError):
        export_strategy(research_only_snapshot(), tmp_path / "strategy.py")

def test_exported_source_uses_positive_close_quantity_and_no_live_api(tmp_path):
    source = export_strategy(validated_trend_snapshot(), tmp_path / "strategy.py").read_text()
    assert "qty=self.position_qty" in source
    assert "OpenTradeContext" not in source
    assert "LIVE" not in source
```

- [ ] **Step 3: Run and verify missing exporter failure**

Run: `pytest tests/quant/test_strategybase_exporter.py -q`
Expected: collection failure for missing exporter.

- [ ] **Step 4: Implement template rendering with an allowlist of documented identifiers and exclusive output creation**

```python
if snapshot.status != "VALIDATED_SNAPSHOT":
    raise ExportBlockedError("Moomoo export requires VALIDATED_SNAPSHOT")
if snapshot.strategy.family not in SUPPORTED_FAMILIES:
    raise ExportBlockedError("strategy cannot be represented exactly")
```

- [ ] **Step 5: Run exporter and safety-boundary tests**

Run: `pytest tests/quant/test_strategybase_exporter.py tests/quant/test_configuration_and_boundaries.py -q`
Expected: all tests pass.

- [ ] **Step 6: Commit the slice**

```powershell
git add src/investment_tracker/quant/moomoo tests/quant/test_strategybase_exporter.py
git commit -m "feat: export validated strategies to Moomoo"
```

### Task 12: Documentation, offline demonstration, and final verification

**Files:**
- Modify: `README.md`
- Create: `src/investment_tracker/quant/README.md`
- Create: `requirements-quant.lock`
- Create: `tests/quant/test_end_to_end.py`
- Create when evidence exists: `results/leaderboard.csv`
- Create when evidence exists: `results/latest_report.md`

**Interfaces:**
- Consumes: all prior package APIs and deterministic fixture data.
- Produces: documented installation/OpenD/CLI workflow, dependency fingerprint, and a reproducible offline end-to-end research result; provider-backed claims remain unavailable until OpenD is reachable.

- [ ] **Step 1: Write a failing end-to-end test that runs a small train/validation search, persists experiments, promotes only a passing snapshot, and exports it without holdout access**

```python
def test_offline_research_pipeline_never_accesses_holdout_or_canonical_state(tmp_path):
    result = run_fixture_pipeline(tmp_path, fixture_universe=("SPY", "QQQ"))
    assert result.experiment_count > 0
    assert result.final_holdout_accessed is False
    assert result.snapshot.status == "VALIDATED_SNAPSHOT"
    assert result.export_path.exists()
```

- [ ] **Step 2: Run and verify the fixture orchestrator is absent**

Run: `pytest tests/quant/test_end_to_end.py -q`
Expected: failure for missing end-to-end orchestration.

- [ ] **Step 3: Implement the minimal fixture orchestration and document exact commands and limitations**

```text
python -m pip install -e ".[dev,quant]"
python -m investment_tracker.quant.cli download --config <path>
python -m investment_tracker.quant.cli backtest --config <path>
python -m investment_tracker.quant.cli optimize --config <path>
python -m investment_tracker.quant.cli validate --config <path>
python -m investment_tracker.quant.cli report --results results/experiments
python -m investment_tracker.quant.cli export-moomoo --snapshot <path> --output <path>
```

- [ ] **Step 4: Install declared dependencies and record exact versions in `requirements-quant.lock`**

Run: `python -m pip install -e ".[dev,quant]"`
Expected: installation succeeds without a paid dependency.

- [ ] **Step 5: Run all quant tests and the full repository suite**

Run: `pytest tests/quant -q`
Expected: all quant tests pass.

Run: `pytest -q`
Expected: all product assertions pass; the unchanged Windows symlink test may fail with WinError 1314 and is reported separately.

- [ ] **Step 6: Run provider/OpenD preflight without requesting any locked symbol**

Run: `python -m investment_tracker.quant.cli download --config src/investment_tracker/quant/defaults/universe.yaml --preflight`
Expected: either quote-only OpenD connectivity succeeds or the command fails closed with an explicit unavailable status and no historical claims.

- [ ] **Step 7: If OpenD is reachable, run the configured research budget without FINAL_HOLDOUT; otherwise generate only the deterministic fixture report**

Run: `python -m investment_tracker.quant.cli optimize --config src/investment_tracker/quant/defaults/validation.yaml`
Expected: append-only experiments, a deterministic leaderboard, a stop reason, and `final_holdout_accessed=false`.

- [ ] **Step 8: Commit documentation and verified artifacts**

```powershell
git add README.md requirements-quant.lock src/investment_tracker/quant/README.md tests/quant/test_end_to_end.py results/leaderboard.csv results/latest_report.md
git commit -m "docs: complete ETF quant research workflow"
```

## Plan self-review

- Spec coverage: all safety, data, simulation, validation, optimizer, audit,
  export, CLI, and documentation requirements map to Tasks 1-12.
- Placeholder scan: no deferred implementation markers are present.
- Type consistency: `DataRequest`, `DatasetMetadata`, `ResearchDataView`,
  `FrozenCandidateManifest`, `ValidatedSnapshot`, and `BacktestResult` are
  introduced before downstream consumers.
- Scope: tasks are ordered so every slice is independently testable; no task
  changes an existing frozen or canonical module.
