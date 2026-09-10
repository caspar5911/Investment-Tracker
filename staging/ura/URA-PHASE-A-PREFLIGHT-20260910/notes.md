# URA Phase-A worker preflight

The requested URA 2020–2023 computation stopped before provider dispatch and before any canonical write. The coordinator reports canonical clean caches for 2017 (251 sessions), 2018 (251), and 2019 (252). It also reports 253 fetched Alpaca SIP sessions for 2020, but those rows are not persisted, read back, promoted, or included in a coordinator-issued immutable snapshot. Creating later bars, dates, digests, signals, episodes, outcomes, or baselines would fabricate evidence.

## Exact required input

The coordinator must supply an immutable, digest-identified snapshot containing:

1. Frozen `TPC-v1.2`, `REPLAY-v1.0`, `CALC-v1.2`, and `ROBUST-v1.0` configuration and passing Calculation Tests status.
2. A canonical export and content digest for active URA Market Data through 2019, including raw/normalized OHLCV, trade count, VWAP, split factors, usability flags, source digests, supersession state, and DQ lineage.
3. The coordinator-persisted/read-back 2020 block and its canonical digest; the currently fetched-but-unpersisted 253-session block is not worker input.
4. Authorized Alpaca SIP daily bars for URA from 2021-01-01 through 2023-12-31, or least-privilege credentials permitting the frozen one-symbol/retry/fallback protocol. No provider substitution is allowed.
5. Canonical SPY benchmark sessions and normalized bars covering the indicator lookback, every URA signal entry date, and every horizon close through the Phase-A cutoff, with a cutoff and content digest.
6. URA Phase Matrix state, relevant Data Quality records (including quarantined ranges), canonical calculation conventions, baseline definitions, and semantic-key integration boundaries.
7. A coordinator dispatch run ID, snapshot ID, material input digest map, evidence references, timestamp, authorized URA/date scope, and locked-holdout exclusion assertion.

Replay must use the inclusive canonical convention `SMA200[t] = mean(close[t-199] ... close[t])`. Replay, episodes, outcomes, and baselines remain blocked until the applicable canonical cache is persisted and a fresh snapshot is issued.

After those inputs are supplied, the worker can emit `market-data.csv`, `replay-daily.csv`, `replay-episodes.csv`, `baseline-results.csv`, `validation.json`, DQ candidates if applicable, and a `READY_FOR_COORDINATOR_REVIEW` manifest. Only the coordinator may then verify freshness, acquire the write lock, integrate bounded blocks, read them back, append DQ/Run Ledger evidence, and update Phase Matrix last.

No HACK, SOXX, NLR, URNM, or GEV data was requested, inspected, inferred, or used. No thresholds or frozen rules were modified.
