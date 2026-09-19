# Investment Tracker

Deterministic, paper-only infrastructure for governed historical validation and structured investment decision support. This repository never executes trades and does not currently have Independent Audit approval for Production Decision Support v1.

## Local checks

```bash
python -m pip install -e '.[dev]'
pytest
```

See the [architecture](docs/superpowers/specs/2026-09-10-investment-tracker-multi-agent-design.md), [production design](docs/superpowers/specs/2026-09-10-production-decision-support-v1-design.md), and [issue 3 execution status](docs/superpowers/reports/2026-09-10-issue-3-execution-status.md).

## ETF quantitative research

The repository also contains an isolated, SIMULATE-only ETF research subsystem
under `src/investment_tracker/quant`. It uses quote-only Moomoo/OpenD historical
data, immutable local caches, next-open portfolio simulation, chronological
validation, bounded deterministic search, and one-way StrategyBase export.

This subsystem cannot mutate canonical tracker state and does not alter the
frozen replay, calculation, robustness, or governed backtest modules. See the
[quant research guide](src/investment_tracker/quant/README.md) for installation,
commands, evidence boundaries, and known limitations.
