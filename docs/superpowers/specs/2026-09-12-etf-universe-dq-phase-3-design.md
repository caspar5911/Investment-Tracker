# Phase 3 ETF Universe Data-Quality and Selection Specification

**Status:** Approved design, implementation pending

**Campaign window:** 2014-01-01 through 2022-12-31, inclusive

**Campaign type:** Data quality and universe construction only

**Decision grade:** False (`decision_grade=false`)

## 1. Purpose

Phase 3 establishes a broader, defensible ETF research universe from a fixed candidate pool. It assesses every candidate over one predeclared historical window, freezes the complete data-quality result, and only then applies a deterministic category-selection algorithm.

This phase does not run strategies, compare returns, optimize parameters, rank candidates by performance, access `FINAL_HOLDOUT`, or create decision-grade evidence. QFQ data may validate the existing normalized research simulation, but adjusted prices are not evidence of historical executable fills. A future unadjusted-price implementation with explicit corporate-action accounting is required before any decision-grade rerun.

## 2. Non-negotiable governance boundaries

- Preserve TPC-v1.2, REPLAY-v1.0, CALC-v1.2, and ROBUST-v1.0 unchanged.
- Never fetch, inspect, summarize, infer, cache, or derive historical information for `HACK`, `SOXX`, `NLR`, `URNM`, or `GEV`.
- Keep `FINAL_HOLDOUT` sealed. The holdout guard must execute before any symbol-specific filesystem lookup, cache lookup, provider request, diagnostic request, or metadata inspection.
- Use quote-only Moomoo APIs. Do not construct or import a trading context, unlock trading, query accounts/positions/funds, or provide an order path.
- Research artifacts are staging evidence only and cannot mutate canonical tracker state or advance the canonical Phase Matrix.
- Do not repair, synthesize, interpolate, forward-fill, backfill, or otherwise alter provider bars.
- Missing decision-critical evidence fails closed.
- No strategy output, price performance, return statistic, or previously observed strategy result may influence admission, fallback choice, or selection order.

## 3. Fixed campaign inputs

### 3.1 Candidate pool

The complete and only permitted Phase 3 candidate pool is:

`SPY`, `QQQ`, `IWM`, `DIA`, `XLK`, `XLF`, `XLE`, `XLV`, `XLI`, `XLP`, `XLY`, `XLU`, `VNQ`, `TLT`, `IEF`, `GLD`.

All 16 candidates must receive a completed Phase 3 DQ disposition before category selection begins. A disposition is either `PASS` or `FAIL`; unavailable or incomplete decision-critical evidence produces `FAIL`, not an omitted candidate.

### 3.2 Fixed evaluation window

Only 2014-01-01 through 2022-12-31 inclusive is evaluated for admission.

The earlier 2010-2022 and 2013-2022 results are historical DQ reference evidence only. They may be cited as prior evidence but cannot:

- replace the fixed-window assessment;
- cause a later start date to be selected;
- admit or exclude a candidate by themselves; or
- alter the frozen exposure order.

No alternate or later window may be introduced after observing the 2014-2022 results.

### 3.3 Frozen exposure order

Selection uses the following predeclared ordered slots and fallback order:

1. Broad US equity: `SPY`, then `DIA`
2. Growth/technology equity: `QQQ`, then `XLK`
3. Small-cap equity: `IWM`
4. Long-duration US Treasury: `TLT`
5. Intermediate US Treasury: `IEF`
6. Gold: `GLD`
7. US real estate: `VNQ`
8. Defensive equity: `XLP`, then `XLV`, then `XLU`
9. Cyclical equity, only if needed to reach the target: `XLI`, then `XLF`, then `XLE`, then `XLY`

Within a slot, the first candidate with a frozen `PASS` is selected and later fallbacks are not selected for that slot. Category order and fallback order are immutable campaign inputs.

The target is eight economically distinct exposures. Selection stops immediately at eight. If fewer than six exposures can be selected, the campaign terminates with exactly `INSUFFICIENT CLEAN DIVERSIFIED UNIVERSE`. A second data provider may be proposed, but this campaign must not shift its dates, repair data, or alter its ordering rules.

## 4. Versioned evidence model

The implementation must define and persist immutable identifiers for every transformation relevant to admission:

- campaign specification version;
- provider and request schema version;
- Moomoo Python SDK version;
- OpenD version when returned by the preflight;
- normalization version;
- XNYS calendar/session source and version;
- validator version;
- DQ snapshot schema version;
- DQ report schema version;
- universe-selection algorithm version; and
- universe-manifest schema version.

Version values must identify actual executable logic. A code or dependency change capable of changing evidence, session expectations, normalization, validation, or selection requires a new version or campaign and must not silently overwrite an existing artifact.

## 5. Provider request contract

For each permitted symbol, the quote-only request is fixed to:

- code: `US.<symbol>`;
- start: `2014-01-01`;
- end: `2022-12-31`;
- kline type: `KLType.K_DAY`;
- adjustment type: `AuType.QFQ`;
- requested fields: the adapter's declared historical-bar field set;
- maximum count per page: the adapter's fixed value, not exceeding the SDK limit;
- regular US historical session handling as declared by the adapter; and
- pagination solely through the returned `page_req_key` until it is null.

The exact serialized request parameters, including enum values, page size, host, port, session choice, and date bounds, are evidence. Credentials and secrets must never be stored.

Initial historical-candlestick requests must respect the documented frequency and rolling symbol-quota limits. Pagination requests use the SDK's returned page key and must not be mistaken for new initial requests. Provider errors, malformed frames, pagination failures, and interrupted downloads fail closed for the affected candidate and retain available evidence.

The quote context must always be closed, including on exceptions. No trade context is permitted.

## 6. Cache and acquisition rules

The locked-symbol guard runs before all cache or provider interaction. For an allowed candidate:

1. Reuse an existing exact-window cache only if its immutable metadata, hashes, request parameters, versions, raw-evidence references, and normalized dataset all verify.
2. A cache without the raw evidence required by this specification is insufficient for a Phase 3 `PASS`; obtain fresh provider evidence if quotas and connectivity permit.
3. Never silently extend, splice, or reinterpret a cache from a different window or version.
4. Write newly acquired raw evidence and normalized datasets immutably. An identity collision with different bytes is a hard failure.
5. Quarantine invalid datasets and retain their raw evidence; quarantine must not transform a failing candidate into a passing one.

No provider request may be made for a symbol once adequate verified Phase 3 evidence for the exact request identity already exists.

## 7. Raw provider evidence

Every provider response page must be preserved before normalization. The evidence must retain:

- exact returned column names and column order;
- every returned row and scalar value, including exact raw `code` and `time_key` values;
- page order and the request/response page-key chain;
- provider return status and error text where applicable;
- acquisition timestamp;
- request parameters;
- SDK and OpenD versions when available; and
- a cryptographic identity derived from deterministic, canonical bytes.

Raw-evidence identities must be content-addressed and referenced—not copied ambiguously—through the DQ snapshot, DQ report, and universe manifest. The canonical encoding and hash algorithm are part of the evidence schema version.

Normalized Parquet is a derived immutable artifact with its own hash. Its identity never substitutes for the raw-evidence identity.

## 8. Normalization

Normalization is deterministic, documented, and versioned. It must:

- verify the returned raw `code` matches the requested `US.<symbol>`;
- parse the raw daily `time_key` using the documented US-market semantics;
- map each bar to one normalized session date and one timezone-aware timestamp under the declared convention;
- preserve raw row linkage so every normalized bar can be traced to its raw evidence and raw row; and
- leave OHLCV values unchanged apart from declared type conversion.

Normalization must not invent a row or provider timestamp for an expected but absent session.

## 9. Data-quality assessment

DQ is executed for all 16 candidates against the same fixed XNYS session set for the campaign window. The validator checks at least:

- required schema and types;
- nonempty data and fixed-window coverage;
- parseable, timezone-consistent timestamps;
- duplicate timestamps or normalized session dates;
- strict chronological ordering;
- finite numeric values;
- nonnegative OHLC and volume;
- valid OHLC relationships;
- exact expected XNYS session membership;
- missing expected sessions;
- unexpected provider sessions; and
- raw code consistency.

Any admission-critical validator issue yields `FAIL`. Warnings that are expressly non-admission-critical must be enumerated by validator version and may not be reclassified after results are observed.

### 9.1 Missing-session evidence

For each `MISSING_SESSION`, the record must contain:

- `raw_time_key: null`, because no provider row exists;
- the expected XNYS session date;
- the immediately preceding and following raw Moomoo rows, where present;
- each surrounding row's exact raw `code` and `time_key`;
- each surrounding row's normalized session date;
- the relevant raw-evidence identity and row identities; and
- the Moomoo `request_trading_days()` diagnostic result where available.

The implementation must not synthesize or infer a missing provider timestamp.

### 9.2 Unexpected-session evidence

For each `UNEXPECTED_SESSION`, the record must contain:

- the exact raw provider `time_key` and `code`;
- its normalized session date;
- the immediately preceding and following raw Moomoo rows, where present;
- the expected XNYS context;
- the relevant raw-evidence identity and row identities; and
- the Moomoo `request_trading_days()` diagnostic result where available.

### 9.3 Cause classification

DQ classification is separate from causal diagnosis. The existence of a missing or unexpected session does not establish provider corruption. Unless retained evidence establishes the cause, `cause` is `UNKNOWN`. Labels such as `provider_corruption_confirmed` are forbidden without independent, affirmative evidence.

## 10. Calendar diagnostics

XNYS is the sole admission calendar. Moomoo `request_trading_days()` results are diagnostic evidence only.

For each diagnosed session anomaly, the system records whether the Moomoo calendar and XNYS calendar `AGREE`, `DISAGREE`, or the comparison is `UNAVAILABLE`, with the raw diagnostic response and request identity when available. Agreement or disagreement:

- must never override the XNYS-based validator result;
- must never admit a dataset that otherwise fails;
- must never repair or create a bar; and
- must never change the category-selection order.

Moomoo-vs-XNYS agreement is provenance and diagnostic context, not an admission override.

## 11. Mandatory two-stage freeze

DQ and selection are separate irreversible stages.

### Stage A: complete and freeze DQ

1. Assess all 16 candidates.
2. Produce one explicit `PASS` or `FAIL` disposition for every candidate.
3. Include all issue records, quarantine references, raw-evidence identities, normalized-data hashes, provider request parameters, SDK/OpenD versions, normalization version, calendar source/version, validator version, and diagnostic calendar evidence.
4. Canonically serialize the complete DQ snapshot and calculate its digest.
5. Write it immutably and verify its digest by readback.

Category selection is prohibited until Stage A is complete. A partial snapshot cannot be selected from. Once frozen, the selector consumes the snapshot as read-only input; subsequent evidence requires a new campaign rather than mutation.

### Stage B: deterministic category selection

1. Verify the frozen snapshot digest and confirm it contains exactly the fixed 16-candidate pool and fixed window.
2. Traverse the frozen exposure slots and fallbacks in order.
3. Select only the first `PASS` candidate in each slot.
4. Use the cyclical slot only if needed to reach the target.
5. Stop at eight selected exposures.
6. If fewer than six are selected, emit `INSUFFICIENT CLEAN DIVERSIFIED UNIVERSE` and do not create an admitted universe manifest.

The selector's input contract excludes prices, returns, strategy identifiers, scores, rankings, and performance metrics. Its decision log records only slot, ordered candidates, frozen DQ disposition, chosen candidate, and deterministic reason.

## 12. DQ report

The human-readable DQ report is generated from the frozen DQ snapshot and deterministic selection result. It must cover all 16 candidates, including failures and quarantines, and clearly separate:

- observed DQ facts;
- diagnostic calendar evidence;
- causal classification;
- selection mechanics; and
- governance conclusions.

The report is immutable and content-hashed. It must not include strategy performance or recommend a symbol based on returns.

## 13. Universe manifest and provenance chain

When and only when six to eight exposures are selected, write an immutable universe manifest. It contains:

- campaign identifier and specification version;
- fixed candidate pool and its digest;
- fixed window;
- frozen exposure order and selection-algorithm version;
- selected symbols, categories, and deterministic selection reasons;
- explicit rejected/skipped candidates with DQ-only reasons;
- QFQ methodology declaration and `decision_grade=false`;
- `final_holdout_accessed=false`;
- confirmation that no live-trading path exists;
- DQ snapshot identity and digest;
- DQ report identity and digest;
- every referenced raw-evidence identity;
- every selected normalized Parquet identity and dataset hash;
- exact provider request parameters associated with each dataset;
- provider, SDK, and OpenD versions where available;
- normalization version;
- XNYS calendar source/version;
- validator version;
- cache/evidence schema versions;
- source revision and dependency/environment identity sufficient to reproduce validation; and
- a manifest digest calculated from canonical serialized content.

The provenance chain is therefore:

`raw provider evidence -> normalized dataset -> validator result -> frozen DQ snapshot -> deterministic selection -> DQ report -> universe manifest`

Every arrow is backed by explicit identities and digests. The manifest references both the DQ snapshot digest and DQ report digest. Missing or unverifiable links fail closed and prohibit manifest admission.

No `VALIDATED_SNAPSHOT` or StrategyBase export is created in Phase 3.

## 14. Artifact layout and immutability

Implementation must keep provider evidence, normalized caches, quarantines, campaign snapshots, reports, and admitted universe manifests in distinct namespaces. Suggested logical layout:

- raw evidence: content-addressed provider-evidence namespace;
- normalized cache: exact request/version-addressed Parquet namespace;
- quarantine: immutable candidate failure bundle referencing raw evidence;
- campaign: DQ snapshot, decision log, and report under a unique campaign identifier;
- universe: admitted manifest under its content digest.

Existing experiment artifacts are preserved unchanged. Research output remains unable to mutate canonical tracker state.

## 15. Failure behavior

The campaign stops safely when any campaign-wide invariant cannot be established, including:

- protected-symbol guard failure;
- inability to produce a complete 16-candidate frozen DQ snapshot;
- snapshot or evidence hash mismatch;
- ambiguous or mutable provenance;
- selection input containing performance data;
- fewer than six clean, distinct exposures; or
- any attempted `FINAL_HOLDOUT` or trading-context access.

Candidate-specific provider or DQ failures quarantine that candidate and produce `FAIL`; they do not alter the window or frozen ordering. A provider outage may leave decision-critical evidence incomplete, which is a candidate `FAIL` and may ultimately cause the campaign-wide insufficient-universe stop.

## 16. Required regression and integration tests

The implementation plan must include tests proving:

1. the holdout guard runs before cache, filesystem metadata, and provider interaction;
2. all locked symbols are rejected without side effects;
3. no trade-context imports or calls exist in the Phase 3 path;
4. the provider adapter preserves all raw pages and exact `code`/`time_key` fields;
5. pagination, page size, enums, session, QFQ, cleanup, and error paths match the official Moomoo contract;
6. exact-window verified cache reuse avoids a provider call;
7. insufficient or mismatched cache evidence fails closed or triggers permitted reacquisition;
8. normalization is deterministic and raw-row traceable;
9. missing-session evidence stores `raw_time_key: null` plus surrounding raw context;
10. unexpected-session evidence stores the exact raw `time_key` plus surrounding raw context;
11. no missing timestamp or bar is synthesized;
12. calendar agreement/disagreement remains diagnostic and cannot override admission;
13. cause defaults to `UNKNOWN` without affirmative causal evidence;
14. the selector cannot run on a partial or unhashed DQ snapshot;
15. the frozen DQ snapshot covers exactly all 16 candidates before selection;
16. selection follows the exact category/fallback order, uses no performance field, and stops at eight;
17. fewer than six selections yields exactly `INSUFFICIENT CLEAN DIVERSIFIED UNIVERSE` and no admitted manifest;
18. manifest provenance verifies snapshot/report digests, raw-evidence identities, request parameters, SDK version, normalization version, and validator version;
19. immutable artifacts cannot be overwritten with different content;
20. existing frozen replay, calculation, robustness, governed-backtest, and Phase 1/2 tests remain unchanged and pass; and
21. the existing symlink failure remains documented as an environment limitation and its test is not weakened.

## 17. Completion report

At campaign completion, report:

- fixed evaluated window;
- full candidate pool;
- per-candidate DQ disposition;
- successful datasets and date coverage;
- failed/quarantined datasets and exact issue classifications;
- missing/unexpected-session raw evidence and diagnostic calendar status;
- raw-evidence, normalized-data, DQ snapshot, DQ report, and manifest identities;
- provider request parameters and relevant versions;
- frozen DQ snapshot confirmation before selection;
- deterministic category decision log;
- selected universe and exposure categories;
- whether the six-symbol minimum and eight-symbol target were met;
- stop reason;
- QFQ `decision_grade=false` status;
- `final_holdout_accessed` status; and
- confirmation that no live-trading path exists.

Strategy metrics—including CAGR, drawdown, Sharpe, Sortino, Calmar, excess return, walk-forward results, optimization counts, robustness, and friction results—are out of scope and must not be computed or reported in Phase 3.

## 18. Acceptance criteria

Phase 3 is complete only when either:

1. all 16 candidates have immutable, verified DQ dispositions; the snapshot was frozen before selection; six to eight exposures were mechanically selected; the DQ report and universe provenance chain verify; and an immutable, non-decision-grade manifest was produced; or
2. all obtainable evidence and failures were preserved, the campaign failed closed with an explicit governed stop reason, and no admitted universe manifest was produced.

In both outcomes, no data is repaired, no strategy-performance input is used, `FINAL_HOLDOUT` remains sealed, existing artifacts remain intact, canonical tracker state is unchanged, and no live-trading path exists.
