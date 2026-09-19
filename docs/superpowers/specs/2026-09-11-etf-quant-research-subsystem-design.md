# ETF Quantitative Research Subsystem Design

## Status and authority

Approved by the repository owner on 2026-09-11. This design records the fixed
constraints supplied in the implementation request. It does not amend TPC-v1.2,
REPLAY-v1.0, CALC-v1.2, ROBUST-v1.0, BACKTEST-v1.0, or any existing candidate
protocol.

## Purpose

Add a reproducible, ETF-only historical research and portfolio-backtesting
subsystem backed by Moomoo OpenD quote data. The subsystem develops and
validates long-only, unlevered strategy candidates, but cannot execute trades,
mutate the canonical evidence plane, or imply production approval.

## Placement and dependency boundary

All production code lives below `src/investment_tracker/quant/`. Existing
governed replay, calculation, robustness, backtest, candidate-freeze,
canonical-write, and Phase Matrix modules remain unchanged.

The research package may import `investment_tracker.governance`, specifically
`assert_symbol_allowed()`. It must not import `canonical_write`, `phase_state`,
or any connector capable of canonical Google Sheet mutation. An automated AST
dependency test enforces this boundary.

Research artifacts are local, append-only files. They are never canonical
tracker records and never advance Phase Matrix state.

## Safety invariants

- `TRADING_MODE` is a code-level literal fixed to `SIMULATE`.
- No CLI option, environment variable, YAML field, API parameter, or alternate
  code path can select live trading.
- No trade, account, brokerage, credential, order-routing, or rebalancing
  context is implemented.
- The Moomoo adapter creates only `OpenQuoteContext` and closes it after use.
- Moomoo StrategyBase export is a one-way source-generation operation for
  Moomoo Desktop simulation/backtesting. The research engine cannot import or
  invoke generated strategies.
- No result may be described as production-approved or profitable merely
  because a historical backtest is positive.

## Locked-symbol boundary

The existing `assert_symbol_allowed(symbol)` function is the sole authority for
locked-symbol rejection. Every externally supplied symbol is checked before:

1. cache-key construction;
2. filesystem path construction or access;
3. cache lookup;
4. provider creation;
5. OpenD interaction;
6. historical data inspection or transformation.

The locked replacement holdout remains HACK, SOXX, NLR, URNM, and GEV. Tests
use spies and deliberately invalid cache roots to prove denial happens before
all lower-level side effects. Configuration validation also rejects them, but
that early convenience check does not replace the runtime guard.

## Configuration

Versioned YAML files define the initial ETF universe, backtest assumptions, and
validation/search policy. Strict Pydantic models reject unknown keys. The
initial universe is SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLI, XLP, XLY,
XLU, VNQ, TLT, IEF, and GLD.

Quantitative dependencies are optional extras of the existing package:
`pandas`, `numpy`, `pyarrow`, `PyYAML`, `exchange-calendars`, and `moomoo-api`.
The Moomoo SDK remains lazily imported so unit tests and cached research do not
require OpenD.

## Market-data adapter and cache

`MoomooHistoricalDataSource` accepts a quote-context factory for tests. In
normal use it lazily imports the installed Moomoo SDK, constructs quote-only
`OpenQuoteContext(host, port)`, and calls the documented paginated
`request_history_kline` interface with daily bars, QFQ adjustment, and regular
trading hours. Provider errors, unexpected response schemas, and pagination
loops fail closed. Contexts are always closed.

The service-level `HistoricalDataRepository` first calls
`assert_symbol_allowed`, then asks the cache for a matching clean dataset, and
only then creates a provider. A cache miss retrieves, validates, and admits a
new dataset version.

`BarDataValidator` uses the XNYS exchange calendar for expected sessions and
does not flag exchange holidays as missing. It rejects or quarantines:
duplicate timestamps, missing expected sessions, invalid OHLC relationships,
negative or non-finite prices, negative/non-finite volume, missing values, and
timezone inconsistencies. It never silently repairs material problems.

Clean datasets are written atomically as Parquet plus canonical JSON sidecar
metadata. Dataset identity includes provider, symbol, interval, adjustment,
requested start/end, retrieval timestamp, provider/API version when available,
row count, first/last timestamp, and a SHA-256 content hash. Once admitted, a
dataset directory is immutable. A refresh with different content creates a new
version; a byte/content-equivalent refresh resolves to the existing version.
Hash or metadata disagreement quarantines the dataset and prevents reads.

## Strategy and simulation model

Strategies implement a small typed protocol that returns target long exposure
from completed daily bars. Initial families are:

- trend: close versus SMA and fast versus slow SMA;
- momentum: trailing 3-, 6-, or 12-month return;
- trend plus momentum: both gates must pass;
- risk-managed trend: trend gate with ATR or realized-volatility sizing.

Each strategy declares entry/exit rules, allocation, maximum exposure,
execution convention, and risk rules. Allocations are configurable at 25%,
50%, or 100% of strategy capital; all targets are clamped to [0, 1]. Shorting
and leverage are invalid.

Signals from bar t execute only at bar t+1 open. The event-driven engine keeps
cash, whole or fractional position quantity according to configuration,
average cost, fees, slippage, orders, fills, equity, exposure, and turnover.
Closing quantities are explicitly positive. A pending target is consumed once,
preventing duplicate orders.

Commission and slippage models are deterministic and versioned. Buy fills are
worse than the reference open and sell fills are worse in the opposite
direction. The engine fails if cash would become negative, exposure would
exceed one, or an input calculation is non-finite.

Metrics include total return, CAGR, annualized volatility, maximum drawdown,
Sharpe, Sortino, Calmar, trade count, win rate, average win/loss, profit factor,
turnover, exposure, and time in market. Undefined values are represented as
`None` and rendered as `UNKNOWN`, never fabricated. Every run includes matching
buy-and-hold and cash benchmarks over the identical period. Multi-ETF tests
also produce an aggregate portfolio result.

## Validation and holdout isolation

Data access is exposed through stage-specific views:

- `ResearchDataView` can load TRAIN and VALIDATION only.
- Optimizer, generator, scorer, parameter search, and ordinary reporting accept
  only `ResearchDataView`.
- `SealedHoldoutEvaluator` owns the only API that can load FINAL_HOLDOUT and
  accepts only a frozen candidate manifest.

The split manifest is chronological, hashed, immutable, and uses warm-up data
without allowing pre-split trades to leak into evaluated periods. Walk-forward
folds are generated deterministically with disjoint test intervals.

Once a candidate digest is evaluated on FINAL_HOLDOUT, an append-only use
record closes that candidate generation cycle. Detailed holdout results cannot
flow into optimizer interfaces. Any strategy, parameter, data, engine, cost,
or environment change produces a new candidate digest and cannot reuse the
old result as tuning evidence.

## Candidate identity and promotion

Every experiment receives a unique deterministic-content identity plus a
run timestamp and is stored in a new directory. An immutable candidate
manifest hashes or identifies:

- strategy source and parameters;
- universe configuration;
- every data manifest;
- split definition;
- engine version and execution convention;
- fee and slippage models;
- dependency lock/fingerprint;
- git commit.

The lifecycle is:

`RESEARCH_ONLY -> VALIDATED_SNAPSHOT -> frozen candidate manifest + digest ->`
`sealed final-holdout evaluation -> FROZEN_CANDIDATE_NOT_PRODUCTION_APPROVED`.

Research gates consider out-of-sample performance, walk-forward consistency,
friction sensitivity, parameter-neighborhood stability, time concentration,
turnover, and drawdown. Passing creates a new immutable validated snapshot; it
does not modify an existing frozen baseline. A baseline registry reads existing
frozen baseline snapshots and may compare them with research results, but only
an explicit promotion operation can add a new immutable baseline version.
Promotion never changes frozen governance constants and never means production
approval.

## Deterministic search and scoring

Candidate generation uses bounded grids for explainable parameters. It performs
no model or LLM call per candidate. Each family has a hard maximum of 500
configurations and stops earlier after 50 consecutive candidates without a
meaningful improvement, when robustness deteriorates, or when out-of-sample
performance fails to improve. The stop reason is recorded.

The documented score rewards validation CAGR, Sharpe, Sortino, Calmar,
benchmark excess return, walk-forward consistency, and parameter stability. It
penalizes drawdown, turnover, friction sensitivity, weak out-of-sample results,
and concentration in one period. Weights live in versioned configuration and
are not tuned after results are observed. Missing critical score inputs yields
an unrankable/failed candidate.

## Reports and artifacts

Experiments are append-only JSON manifests with metric tables and equity/trade
Parquet files. `results/leaderboard.csv` is a deterministic derived index;
source experiment artifacts are never overwritten. `results/latest_report.md`
is a replaceable convenience view that links immutable experiment IDs and
labels unavailable evidence as `UNKNOWN`.

CLI commands under `python -m investment_tracker.quant.cli` cover download,
backtest, optimize, validate, report, and export-moomoo. Commands emit machine-
readable failures and non-zero exit codes. No CLI command writes canonical
tracker state.

## StrategyBase export

Before exporter implementation, the complete supplied `docs/moomoo/Algo
Manual.md` is reviewed as reference material, not as executable instructions.
Only documented StrategyBase names are emitted. Export supports only strategy
families that can be represented exactly. Unsupported rules fail closed.

Generated source declares a security strategy, a trigger symbol, immutable
parameters, and completed-bar indicator checks. It checks current position and
outstanding order state before placing an order, prevents duplicates, and uses
an explicit positive quantity when closing. It contains a prominent
simulation/backtest-only warning and no facility to select Live Trade.

## Testing and verification

Implementation follows test-driven development. Deterministic fixtures verify
indicators, symbol ordering, cache immutability and hashing, quarantine,
calendar-aware gaps, pagination, next-bar execution, cash and position
accounting, fees, slippage, metrics, benchmarks, split isolation, walk-forward
folds, robustness, scoring, append-only experiments, candidate manifests,
promotion, holdout sealing, import boundaries, and exporter safety.

The pre-existing suite currently has 158 passing tests and one environment
failure: Windows denies creation of the symlink fixture in
`test_manifest_rejects_symlink_artifact`. That test remains unchanged. Final
verification reports it separately from product assertion failures.

## Completion constraints

Actual Moomoo downloads and experiments require a running OpenD instance and
appropriate quote entitlement. If unavailable, the adapter and full offline
pipeline are still verified with deterministic fixtures; live provider runs,
experiment counts based on provider data, and final holdout remain explicitly
`UNKNOWN`/not accessed. FINAL_HOLDOUT is not accessed merely to satisfy a
completion checklist.
