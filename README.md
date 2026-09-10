# Investment Tracker

Deterministic, paper-only infrastructure for governed historical validation and structured investment decision support. This repository never executes trades and does not currently have Independent Audit approval for Production Decision Support v1.

## Local checks

```bash
python -m pip install -e '.[dev]'
pytest
```

See the [architecture](docs/superpowers/specs/2026-09-10-investment-tracker-multi-agent-design.md), [production design](docs/superpowers/specs/2026-09-10-production-decision-support-v1-design.md), and [issue 3 execution status](docs/superpowers/reports/2026-09-10-issue-3-execution-status.md).
