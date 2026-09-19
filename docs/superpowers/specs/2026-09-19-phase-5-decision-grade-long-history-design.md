# Phase 5 Decision-Grade Long-History Durability Design

Status: PRE-EXECUTION DESIGN. This document defines Phase 5 before authoritative
Phase 5 market data is acquired or any Phase 5 performance result is evaluated.
It does not authorize FINAL_HOLDOUT access, protected-symbol access, strategy
retuning, brokerage execution, or Phase 6.

## Purpose and governing question

Phase 5 implements the already-sealed downstream contract
`PHASE5-LONG-HISTORY-DURABILITY-CONTRACT-v1` without modifying any Phase 4
authority or evidence.

The governing question remains exactly:

> Can this exact frozen strategy remain useful for many years without periodic retuning?

Phase 5 has two linked responsibilities:

1. reconstruct the frozen Phase 4 survivor on decision-grade, historically
   executable market data with explicit corporate-action and cash accounting;
2. evaluate the same unchanged strategy over the longest defensible common
   history available for the frozen eight-ETF universe.

Phase 5 is not a new strategy search. A weak Phase 5 result is accepted as
evidence and cannot cause a new Phase 4 winner, parameter change, ETF
substitution, or revised Phase 4 ranking.

## Sealed Phase 4 authority

Phase 5 starts only from the sealed Phase 4 finalization state:

- Phase 4 evidence commit:
  `69bb4347cbe577c4a1277335eef778ddf5b177d0`
- Phase 4 final status: `ONE_FROZEN_SURVIVOR`
- finalization decision content SHA-256:
  `913d14c1061c2cbbb16e66b448b715952c4a360dbda299500eacd0fd61156958`
- finalization audit content SHA-256:
  `684c80fddf5557ff45fe03d8e6fab9ee65c8402f5c18af49f14b4c3188b00411`
- finalization manifest content SHA-256:
  `a4b18e3a97b662b8e2a9134647d759b95bafa41b3f1a53716b77505b2a275281`
- selected candidate:
  `phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075`
- selected population position: `150`
- family:
  `cross_sectional_absolute_momentum_rotation`
- family ID:
  `phase4-family-fc27985857d177a02f837a76301d681b9c96cc67e41813207d0916d253a1a86d`
- family-definition SHA-256:
  `f39ffaa60053374a6715bdba22190a4151555105bfb0cdb4229190cb12dd95ae`
- hypothesis ID:
  `phase4-hypothesis-5d6dab4566bca8c68915f2c9058f34a870f77cc5042b92f6c5ea1a222eaf3fbb`
- parameter-tuple SHA-256:
  `059b8b6c0c574f68c1a0248a08811ca3049e61937b33665ff28472bddeb43737`
- rule-set SHA-256:
  `9b7dfadb7a0cf4fdd4c179f70dbff409a8d57bace871ca054bc2ad9e3cd77b0d`
- frozen parameters:
  `lookback_sessions=126`,
  `skip_sessions=21`,
  `top_k=3`,
  `rebalance_sessions=21`
- execution timing: completed session `t` close signal -> next eligible
  session `t+1` open.
- long-only, no leverage, no shorting.

Any mismatch in these identities stops Phase 5 before data access.

## Safety and information boundary

Phase 5 is paper-only historical validation.

The following are forbidden:

- FINAL_HOLDOUT access;
- any historical lookup, fetch, inference, cache read, summary, or derivation
  for HACK, SOXX, NLR, URNM, or GEV;
- candidate search or evaluation of the other 179 Phase 4 candidates;
- parameter mutation, periodic reoptimization, annual refit, or adaptive
  strategy logic;
- ETF substitution or synthetic proxy history;
- feedback from Phase 5 into the sealed Phase 4 selection;
- brokerage order placement, credential handling, or real-money capability;
- changing the frozen Phase 4 survivor policy or historical Phase 4 evidence.

The authorized Phase 5 market universe is exactly, in canonical symbol order:

`GLD, IEF, IWM, QQQ, SPY, TLT, VNQ, XLP`.

Provider calls are permitted only for these eight symbols and only after the
Phase 5 methodology is sealed. Provider access authorization is new Phase 5
authorization and does not mutate the historical Gate 1 record where provider
access was correctly recorded as not yet authorized.

## Historical window

The Phase 5 acquisition cutoff is frozen before data acquisition. The requested
end is the latest fully completed regular U.S. session on or before
2026-09-18. The actual end is the latest session at or before that cutoff for
which the full eight-symbol decision-grade panel passes data-quality checks.

The start is derived mechanically after acquisition as the maximum of the eight
symbols' first defensible daily-history session. No ETF may be substituted and
no proxy may extend the history. The report records the actual common start,
end, session count, and calendar duration.

The desired history remains approximately 15–20 years when defensible, but the
contract requires the longest defensible common history rather than a forced
length.

For comparison with the sealed Phase 4 campaign, Phase 5 also emits an exact
2019-01-02 through 2022-12-30 reconstruction slice when those sessions are
present. Earlier observations may initialize indicators only; portfolio state
for that comparison slice begins fresh at its first scored session.

## Authoritative data source: Moomoo OpenD

OpenD is the authoritative Phase 5 acquisition source.

Daily bars are requested with the equivalent of:

- `request_history_kline`
- `KLType.K_DAY`
- `AuType.NONE`
- regular-session daily bars
- no extended-hours data
- explicit start/end
- paged retrieval
- OPEN, HIGH, LOW, CLOSE, volume and session timestamp retained.

QFQ/BFQ prices are never used for Phase 5 fills, marking, or accounting.

Corporate-action evidence is acquired through OpenD adjustment/corporate-action
interfaces, including:

- `get_rehab`
- dividend history
- stock-split/reverse-split history.

Raw provider responses are normalized into canonical records, but the original
response payload or an exact-byte export of it is hashed and retained in
lineage. Every request records provider, OpenD/API version when available,
symbol, request type, requested range, retrieval timestamp, returned range,
row count, and SHA-256 identity.

The acquisition adapter must reject a protected symbol before opening an OpenD
connection or calling any provider method.

## Independent cross-check source

Massive may be used only as a secondary data-verification source for the same
authorized eight symbols. It cannot replace OpenD silently.

The independent check covers:

- unadjusted daily session dates;
- raw OPEN and CLOSE on fill-relevant sessions;
- dividend events and cash amounts;
- split/reverse-split events and ratios.

A discrepancy is material when it changes a generated target, a corporate
action entitlement, a split-adjusted unit count, or a fill/reference price by
more than the stricter of USD 0.01 or 1 basis point of the OpenD reference.
Material discrepancies require explicit reconciliation evidence; otherwise the
Phase 5 outcome is `UNKNOWN_ABSTAIN`.

Alpha Vantage is non-authoritative for this phase. A failed premium-endpoint
capability check must not be represented as decision-grade evidence.

## Two separate strategy paths

Phase 5 separates target identity from signal-data verification.

### A. Sealed-target execution reconstruction

The primary performance reconstruction must not regenerate or choose a new
strategy target from Phase 5 outcomes.

The selected Phase 4 result artifact is an immutable authority. The 0-bps
sealed replay is used only to reconstruct the selected asset set for each
fill-eligible scheduled Phase 4 rebalance. On the due session immediately
after a scheduled signal, the post-fill state identifies the selected asset
set. The frozen strategy definition determines equal weight `1/n` across
that set, with residual cash when fewer than `top_k` assets are positive.

This yields a sealed Phase 4 target-decision sequence without reading or
reranking the other 179 candidates. The final scored signal with no eligible
next session is not a performance fill and is excluded from target-execution
equivalence.

For the long-history period outside the original Phase 4 VALIDATION range,
targets are generated by the exact frozen strategy implementation described
below; no Phase 4 target sequence exists outside that historical range.

### B. Causal decision-grade signal reconstruction

For every long-history signal timestamp, the signal engine computes the exact
frozen momentum rule using a corporate-action-consistent history constructed
only from information effective on or before that signal timestamp.

For symbol `s` at signal session `t`:

`score = close[t-skip] / close[t-lookback-skip] - 1`

with `lookback=126` and `skip=21`. Only positive finite scores are
eligible; sorting is descending score then ascending symbol; the first three
are selected; selected assets receive equal weights.

Raw OpenD closes are transformed for signal comparability using only OpenD
rehabilitation rows whose ex-dividend/effective date is no later than the
signal timestamp. Future corporate-action rows are forbidden. Event-level
forward factors are applied chronologically to observations that precede each
effective event. The implementation records the exact factor/event rows used
for each signal-window identity.

If the provider adjustment semantics cannot be reproduced unambiguously from
documented OpenD factor fields, the signal-equivalence gate is UNKNOWN rather
than inventing a formula.

Within the original Phase 4 2019–2022 VALIDATION interval, the causal
decision-grade generated selected-symbol set must match the sealed Phase 4
selected-symbol set at every comparable fill-eligible rebalance. Any
unreconciled mismatch is a decision-grade contradiction and prevents a
supported Phase 5 conclusion.

This separate equivalence test prevents a raw-price execution replay from
quietly becoming a different strategy.

## Decision-grade portfolio accounting

All execution and marking use OpenD `AuType.NONE` raw prices.

A target formed after session `t` closes is eligible only for the next
available regular session `t+1` OPEN. Same-session fills are impossible.
A final signal without a next eligible session remains unfilled.

Accounting is self-financing and keeps separate:

- cash available for trading;
- units by symbol;
- declared dividend receivables;
- settled dividends;
- transaction friction;
- portfolio equity.

### Dividends

For a cash distribution, entitlement is determined from units held across the
provider-documented ex-date boundary. On ex-date, the entitled amount becomes a
receivable and is included in economic equity but is not spendable cash. On the
provider-documented pay date, the receivable moves to cash. Missing
decision-critical ex-date, amount, currency, or pay-date evidence is
`UNKNOWN`; it is not imputed.

Gross distributions are modeled. Investor-specific withholding tax is reported
as outside this frozen Phase 5 base accounting unless a separately approved,
account-specific tax methodology is added. Phase 5 therefore does not by
itself establish real-money after-tax readiness.

### Splits and reverse splits

A split/reverse split effective before a session open adjusts held units before
that open using the provider-documented ratio. It does not create P&L. Raw
prices remain raw. Fractional units are retained to preserve the existing
continuous-unit backtest convention. Broker lot/fractional-share restrictions
belong to later Moomoo implementation-equivalence testing.

Any other corporate action that changes economic ownership and is not modeled
causes `UNKNOWN_ABSTAIN` for affected history rather than silent omission.

### Friction

Use the existing frozen one-way notional friction cases:
`0, 3, 10, 25, 50` bps. The primary comparison remains 3 bps. Friction is
charged on absolute traded notional. No performance-informed fee or slippage
assumption may be introduced.

Cash earns zero unless a separately frozen methodology authorizes otherwise.

## Benchmark

Phase 5 preserves the existing Gate 3 equal-funded eight-asset comparison
benchmark on decision-grade data.

Each of the eight symbols receives one eighth of initial capital and is entered
at the first eligible next-session raw OPEN under the same friction convention.
Each sleeve is self-financing and receives its own dividends and split unit
changes. Sleeves are aggregated analytically; capital is not periodically
reset to equal weights.

Benchmark construction cannot influence strategy targets.

## Data-quality gates

Before performance evaluation, the canonical dataset must pass:

- exact authorized symbol set and no protected symbol;
- monotonically increasing unique regular-session dates;
- finite positive OHLC;
- `LOW <= min(OPEN,CLOSE) <= max(OPEN,CLOSE) <= HIGH`;
- no duplicate bars;
- no silent forward/backward adjustment in the raw panel;
- common-session construction documented and reproducible;
- no missing bar on a strategy fill session;
- corporate-action records sorted, unique, typed and attributable;
- every modeled split ratio positive and internally valid;
- every modeled dividend amount finite and nonnegative;
- all decision-critical provider discrepancies resolved;
- exact raw-input and normalized-dataset hashes reproducible.

Missing noncritical volume may be reported without blocking a price-only
strategy, but missing OPEN/CLOSE or decision-critical corporate-action evidence
fails closed.

## Durability analysis

The exact unchanged strategy is run once over the longest defensible common
history and once over the exact Phase 4 comparison slice.

Required reporting follows the sealed Phase 5 downstream contract:

- CAGR;
- calendar-year returns;
- calendar-month returns;
- positive-year percentage;
- positive-month percentage;
- average winning month;
- average losing month;
- worst year;
- worst month;
- longest losing-month sequence;
- rolling 12-calendar-month returns;
- rolling 36-calendar-month returns;
- rolling 60-calendar-month returns when complete;
- positive-return concentration;
- top-period concentration;
- recovery characteristics not requiring unresolved max drawdown;
- regime-consistency diagnostics using frozen regime logic where applicable;
- realistic friction sensitivity;
- annualized one-way turnover;
- average and maximum long-only gross-exposure validity;
- Sharpe and Sortino under the existing calculation convention;
- bootstrap evidence only through the existing frozen implementation when its
  assumptions are applicable.

DQ-030 remains unresolved. Therefore `max_drawdown=null` and
`calmar=null`. DSR and PBO remain `null / NOT_IMPLEMENTED` and cannot
affect the Phase 5 conclusion.

## Preregistered Phase 5 conclusion rule

No new performance threshold is invented from Phase 5 results.

A final status is one of:

### PHASE5_DURABILITY_SUPPORTED

Allowed only when all identity, safety, data-quality, accounting,
corporate-action, cross-source, and signal-equivalence gates pass, and the
long-history reconstruction satisfies every applicable candidate-independent
hard condition already frozen in the Phase 4 survivor policy:

- total return is positive and above zero-return cash;
- benchmark excess return is positive;
- Sharpe is available and positive;
- Sortino is available and positive;
- the 25-bps friction total return is positive;
- annualized one-way turnover is available and between 0 and 12 inclusive;
- average gross exposure is in [0,1];
- every session satisfies long-only/no-leverage exposure invariants;
- bootstrap lower endpoint is available and nonnegative when the frozen
  bootstrap method is applicable;
- fixed strategy identity is invariant;
- required durability evidence is complete;
- max drawdown, Calmar, DSR and PBO remain absent as required.

Phase 4 gates that inherently require the 180-candidate neighborhood or the
Phase 4-specific walk-forward selection competition are not recreated in Phase
5 and are not replaced by new thresholds. Their sealed Phase 4 evidence remains
lineage only.

### PHASE5_DURABILITY_CONTRADICTED

Used when required data are decision-grade and complete but an applicable
frozen hard condition fails, or when the decision-grade signal-equivalence
check produces an unreconciled target mismatch.

### PHASE5_UNKNOWN_ABSTAIN

Used when a decision-critical input, corporate action, provider reconciliation,
identity proof, accounting proof, or required applicable metric cannot be
established. UNKNOWN never becomes PASS by omission.

The conclusion is evidence about later promotion only. It never changes Phase
4.

## Architecture

Add an isolated package:

`src/investment_tracker/quant/phase5/`

with focused modules for:

- `authority.py` — exact Phase 4 identity binding and Phase 5 authorization;
- `opend.py` — protected-symbol-safe OpenD acquisition/export adapter;
- `dataset.py` — canonical raw-bar/corporate-action normalization and hashes;
- `reconciliation.py` — independent-source discrepancy evidence;
- `signals.py` — causal corporate-action signal history and equivalence;
- `targets.py` — sealed Phase 4 target-decision extraction;
- `accounting.py` — raw-price cash/units/receivable/split replay;
- `benchmark.py` — exact decision-grade benchmark reconstruction;
- `durability.py` — required long-history metrics using existing formulas
  whenever an existing frozen implementation is available;
- `artifacts.py` — immutable content-addressed Phase 5 evidence;
- `cli.py` — provider acquisition, preflight, reconstruction and seal
  commands with no trading surface.

The package may import sealed Phase 4 read-only models/calculation helpers but
must not modify Phase 4 code or artifacts.

## OpenD execution boundary

The authoritative OpenD acquisition must run in an environment where OpenD is
reachable and authenticated for quote access. The repository CLI supports a
local export workflow so OpenD does not need to run in GitHub Actions.

The local acquisition command produces immutable provider exports and a
manifest. The subsequent normalization, tests, reconstruction, durability
analysis, and sealing are deterministic and provider-free from those pinned
exports.

GitHub Actions may verify committed or supplied immutable evidence, but it must
not fake an OpenD connection or silently substitute another provider.

## Evidence and sealing

Phase 5 writes only additive content-addressed evidence below
`results/phase5/`.

At minimum the final manifest binds:

- this exact spec identity;
- exact Phase 4 finalization decision/audit/manifest identities;
- exact frozen candidate/binding identities;
- Phase 5 authorization record;
- OpenD provider-export identities;
- normalized dataset identity;
- actual common-history window;
- corporate-action evidence identity;
- reconciliation evidence identity;
- signal-equivalence evidence identity;
- target-sequence identity;
- accounting/replay identities for every friction case;
- benchmark identity;
- durability-report identity;
- final decision identity;
- source-bundle identity and producing Git revision;
- safety flags, including
  `final_holdout_accessed=false`,
  `protected_symbols_accessed=[]`,
  `candidate_search_executed=false`,
  `candidate_parameters_changed=false`,
  `phase4_feedback_written=false`,
  `live_trading_capability=false`,
  and `phase6_started=false`.

Artifacts are written before the final manifest. The final manifest is the last
fallible write. Re-running from identical pinned inputs must produce identical
canonical content hashes.

## Testing and review gates

Implementation follows RED -> GREEN -> regression -> commit.

Required tests include:

- exact Phase 4 authority and selected-candidate binding;
- provider call rejection before connection for every protected symbol;
- exact eight-symbol allowlist;
- OpenD paging and `AuType.NONE` enforcement;
- rejection of adjusted execution bars;
- canonical provider-export and dataset hashes;
- OHLC and session DQ invariants;
- dividend entitlement/receivable/pay-date accounting;
- split and reverse-split unit continuity;
- no same-session fills;
- next-open execution;
- no negative cash beyond numerical dust;
- no short units or gross exposure above one;
- sealed Phase 4 target extraction from deterministic fixtures;
- causal signal adjustment that never consumes future corporate actions;
- original VALIDATION target-set equivalence;
- independent-source discrepancy fail-closed behavior;
- exact benchmark sleeve isolation;
- 0/3/10/25/50-bps friction results;
- calendar and rolling 12/36/60-month durability calculations;
- DQ-030 enforcement keeping max drawdown and Calmar null;
- DSR/PBO absence;
- deterministic conclusion classification;
- no trading/order/account imports or methods;
- no FINAL_HOLDOUT or protected-symbol access surface;
- Phase 4 historical evidence remains byte-identical.

A final independent review must find zero Critical and zero Important issues
before Phase 5 is sealed.

## Stop boundary

Phase 5 stops after its immutable final decision and manifest are produced.
It does not open FINAL_HOLDOUT, start Phase 6, create Moomoo order-routing
logic, or perform forward paper trading.
