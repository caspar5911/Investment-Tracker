# ETF Quantitative Research

This package is a paper-only research subsystem. It downloads quote data,
caches immutable datasets, simulates long-only strategies, performs
chronological validation, and produces local research artifacts. It does not
contain a brokerage context, account login, credential store, live-mode switch,
canonical Sheet writer, or Phase Matrix writer.

`TRADING_MODE` is structurally fixed to `SIMULATE` in `constants.py`.

## Installation

Python 3.12 or newer is required.

```powershell
python -m pip install -e ".[dev,quant,moomoo]"
```

`requirements-quant.lock` records the exact environment used for candidate
identity and verification. Candidate manifests hash that lockfile.

## Moomoo OpenD setup

1. Install and start Moomoo OpenD locally.
2. Sign in through OpenD and confirm that the account has the required US quote
   entitlement. This repository does not receive or store those credentials.
3. Leave the quote service on `127.0.0.1:11111`, or pass a different quote host
   and port to the download command.
4. Run the quote-only connectivity check:

```powershell
python -m investment_tracker.quant.cli download --preflight
```

No environment variables are required or read. In particular, there is no
environment variable that enables real-money behavior. Host and port are
explicit command arguments; credentials are managed outside this repository by
OpenD.

The installed and inspected SDK during implementation was `moomoo-api
10.10.7008`. The adapter uses the documented `OpenQuoteContext` and paginated
`request_history_kline` API with `KLType.K_DAY`, `AuType.QFQ`, and
`Session.RTH`. It never constructs an account or trading context.

## Configuration

Defaults live in `defaults/`:

- `universe.yaml`: the configurable US-listed ETF universe;
- `backtest.yaml`: capital, percentage allocation, commission, and slippage;
- `validation.yaml`: TRAIN, VALIDATION, sealed FINAL_HOLDOUT, and search limits.

All models are strict and reject unknown keys. The initial universe is SPY,
QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLI, XLP, XLY, XLU, VNQ, TLT, IEF, and GLD.
The locked replacement holdout is rejected by the repository governance guard
before any cache path, filesystem lookup, provider construction, or historical
inspection.

## Download and cache

The ordinary download command intentionally stops at the end of VALIDATION. It
does not download FINAL_HOLDOUT.

```powershell
python -m investment_tracker.quant.cli download
python -m investment_tracker.quant.cli download --cache-root data/cache --host 127.0.0.1 --port 11111
```

Bars must pass XNYS-calendar validation before admission. Exchange holidays are
not counted as missing sessions. Duplicate or missing sessions, invalid OHLC,
negative values, NaN/infinity, and timezone conflicts cause quarantine or a
closed failure. Material data is never silently repaired.

Each clean dataset version contains `bars.parquet` and `metadata.json`. Metadata
records provider, API version, symbol, interval, adjustment, requested dates,
retrieval time, row count, first/last timestamps, and canonical SHA-256 content
hash. Admission uses an atomic directory move. Equivalent refreshes reuse the
existing version; changed content creates another immutable version.

## One backtest

The following example uses a clean cached SPY dataset and a fixed 50% trend
allocation:

```powershell
python -m investment_tracker.quant.cli backtest --symbol SPY --family trend --parameters '{"fast_window":20,"slow_window":50,"allocation":0.5}'
```

Signals use a completed daily bar and execute at the next daily open. Buys pay
upward slippage; sells receive downward slippage. Commissions debit cash on
both sides. Exposure is confined to [0, 1]; no leverage or shorting is accepted.

Metrics are total return, CAGR using elapsed calendar time, annualized
volatility, maximum drawdown, Sharpe, Sortino, Calmar, completed trade count,
win rate, average win/loss, profit factor, turnover, average exposure, and time
in market. A mathematically undefined metric is `UNKNOWN`, not zero.

Buy-and-hold uses the same next-open engine and period. Cash remains constant.
Multi-ETF portfolios aggregate equal-weight normalized equity curves.

## Optimization and validation

```powershell
python -m investment_tracker.quant.cli optimize
python -m investment_tracker.quant.cli validate --experiments-dir results/experiments
python -m investment_tracker.quant.cli report
```

The four initial families are trend, momentum, trend plus momentum, and
risk-managed trend. Search grids are deterministic and bounded to at most 500
configurations per family. Search stops after 50 candidates without meaningful
improvement, persistent out-of-sample non-improvement, or immediate robustness
deterioration.

Score version `QUANT-SCORE-v1` allocates 20 points to validation CAGR, 15 to
Sharpe, 10 to Sortino, 10 to Calmar, 15 to benchmark excess return, 10 to
walk-forward consistency, 10 to parameter stability, and 10 to friction
resilience. It separately penalizes excessive drawdown, turnover, and
single-period concentration. A missing critical metric makes a candidate
unrankable. The 60-point mechanical research threshold is fixed in code and is
not a production threshold.

Optimizer-facing APIs can load only TRAIN and VALIDATION. FINAL_HOLDOUT exists
only behind `SealedHoldoutEvaluator`. It writes a single-use record before data
loading, so even a failed evaluation consumes that candidate cycle. Holdout
results do not feed an optimizer interface.

## Experiments, promotion, and leaderboard

Every experiment is a new exclusive JSON file below `results/experiments`.
Candidate identity covers strategy source and parameters, universe, data
manifests, split, engine, fees, slippage, execution convention, dependency
lockfile, and git commit.

The lifecycle is:

```text
RESEARCH_ONLY
  -> deterministic gates
  -> VALIDATED_SNAPSHOT
  -> frozen candidate manifest
  -> sealed FINAL_HOLDOUT evaluation
  -> FROZEN_CANDIDATE_NOT_PRODUCTION_APPROVED
```

Promotion adds a new digest-addressed baseline version. It cannot edit existing
baselines, frozen governance constants, canonical Sheets, or Phase Matrix
state. `results/leaderboard.csv` and `results/latest_report.md` are derived
views and may be regenerated from immutable experiments.

## Moomoo StrategyBase export

```powershell
python -m investment_tracker.quant.cli export-moomoo --snapshot results/validated/<digest>.json --symbol SPY --output results/exports/strategy.py
```

Only an immutable `VALIDATED_SNAPSHOT` is accepted. Multi-symbol snapshots need
an explicit symbol already present in the snapshot. The exporter currently
supports exact trend, momentum, and trend-plus-momentum translations. Other
families fail closed.

Generated code uses documented StrategyBase functions, completed daily bars
(`select=2`), cash-only maximum quantity, position checks, pending-order checks,
and an explicit positive close quantity. Generation is one-way: repository code
does not import or run the output. The file is for Moomoo Desktop simulation and
backtest verification only.

## Tests and known environment limitation

```powershell
pytest tests/quant -q
pytest -q
```

On this Windows environment, the pre-existing
`test_manifest_rejects_symlink_artifact` test cannot create its fixture because
the process lacks symlink privilege (`WinError 1314`). That test remains
unchanged. Report this separately from product assertion failures.

Positive fixture or historical results do not demonstrate a durable edge and
do not authorize real-money action. Production Decision Support and Promotion
Gates remain exclusively subject to Independent Audit.
