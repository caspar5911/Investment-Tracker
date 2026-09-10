# Investment Tracker Agent Governance

This repository implements paper-only historical validation and human-approved investment decision support. No trade execution is permitted.

## Frozen governance

All agents MUST preserve these frozen versions unless a separately approved governance change introduces a new version:

- TPC-v1.2
- REPLAY-v1.0
- CALC-v1.2
- ROBUST-v1.0

Historical thresholds MUST NOT be tuned to observed results. Missing decision-critical evidence fails closed to UNKNOWN/ABSTAIN. `max_drawdown` remains UNKNOWN while DQ-030 is unresolved. `STRONG ENTRY` is never produced from price-only replay.

## Locked replacement holdout

The symbols HACK, SOXX, NLR, URNM, GEV are locked. Agents MUST NOT fetch, inspect, summarize, infer, cache, or derive historical information for them unless Independent Audit explicitly authorizes release. Unauthorized access contaminates the holdout and must be treated as a governance incident.

## Canonical evidence boundary

The canonical Google Sheet remains the evidence/control plane. Only the coordinator may mutate canonical Sheet tabs. Workers receive immutable snapshots and produce staging artifacts only. Worker output may be marked only `READY_FOR_COORDINATOR_REVIEW`; it cannot advance canonical Phase Matrix state.

Only the coordinator may perform canonical writes, and every bounded write must be independently validated, written under the single-writer lock, read back, post-write checked, and only then reflected in Run Ledger/Data Quality and Phase Matrix. Phase Matrix is updated last.

## Real-money boundary

No trade execution, brokerage credential handling, order routing, automatic rebalancing, or autonomous real-money action belongs in this repository. Any production decision-support record must continue to require explicit human approval.

Only Independent Audit may approve official Production Decision Support readiness or Promotion Gates. Engineering/evidence scores are non-official and may not override failed hard gates.
