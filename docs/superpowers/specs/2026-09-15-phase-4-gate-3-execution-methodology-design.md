# Phase 4 Gate 3 Pre-Campaign Execution Methodology

Status: PRE-CAMPAIGN DESIGN. This specification is frozen before any Phase 4
candidate is executed on VALIDATION and before candidate VALIDATION performance
is observed. Its methods were selected to resolve accounting and return-index
ambiguities, not from performance. This document does not authorize campaign
execution; the terminal engineering checkpoint is
`GATE3_CAMPAIGN_READY_TO_EXECUTE`.

## Exact governing dependencies

The starting source commit is
`f653dfd0caefd2b33e69419a24c4dc3002196aa0` on `main`. All dependency
identities below must be verified from exact bytes and canonical artifact
envelopes. A mismatch stops preparation; no replacement is discovered by
timestamp or filesystem order.

| Dependency | Content SHA-256 | Envelope SHA-256 |
| --- | --- | --- |
| Gate 1 sealed manifest | `dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89` | `e43ccbb596a9f66222b4e2785b1c40c423e6bb43b54b788e1fdb6358e1cdf146` |
| Gate 2 sealed manifest | `c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6` | `ce029ee1534d2c073fee332bb27442143a56138a73a417b44c608b0959cb060d` |
| Corrected Gate 3 authority manifest | `705935c9b06b8f592e66e5e71e4541d910b585be6e9a30e46b99fe97b7591d4f` | `646a7c004c13db3e5f9561d46897a15c27e7f305303559d04d2dc8828ee7f049` |
| Frozen Gate 3 fold authority | `5cc0c0516b8c816ced7b3b90ff2519680ccd9b0a80722024410bfadb380e67fc` | read from the corrected manifest |
| Frozen Gate 3 regime authority | `9d6e1d81c1e5fdac2fbf50d6e2e1f933ea2bb1d20d6f6e277574704028449454` | read from the corrected manifest |

The exact Phase 4 candidate population has 180 identities at immutable
positions 1–180 and digest
`15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3`.
TRAIN contains 1,258 sessions, ending 2018-12-31, with session identity
`7d932a1e45637404e2460107ab0f09b33d74d8a28360533bdb9fdaa96416d995`.
VALIDATION contains 1,008 sessions, 2019-01-02 through 2022-12-30, with
session identity
`330dc026e62cea178fc1f28df18ce6479726b4662838bf9454d354c2d00c13d6`.
The Gate 3 authority preflight must return Gate 1/Gate 2 `VALID`, population
180, all six authorities `BOUND`, and Gate 3 `READY` before this methodology
may be bound. The superseded Gate 3 authority manifest is never accepted.

No Gate 1, Gate 2, Gate 3 authority, candidate definition, baseline rule,
strategy parameter, Phase 2/3/readiness artifact, or frozen
TPC/REPLAY/CALC/ROBUST module may be modified.

## Eight self-financing comparison-baseline sleeves

The four exact Gate 1 controls are `trend(20,50,1.0)`,
`momentum(126,1.0)`, `trend_momentum(20,50,126,1.0)`, and
`risk_managed_trend(150,40,0.10,1.0)`. Their two executed-trial and two
source-defined-grid provenance classes remain as sealed. They are never
Phase 4 candidates, consume zero Phase 4 budget or family slots, cannot be
selected, and cannot influence candidate rule construction or tuning.

For each control, construct exactly eight independently funded one-symbol
replays, in the frozen order `SPY, QQQ, IWM, TLT, IEF, GLD, VNQ, XLP`. Each
starts with `100000.0 / 8 = 12500.0` cash, zero units, zero pending targets,
and zero P&L at VALIDATION inception. There is no TRAIN portfolio state:
strictly earlier TRAIN `close` may initialize lagged indicators only.

Each sleeve calls the unmodified committed Phase 2 strategy's `targets()` on
its own causal QFQ `close` history only. The strictly earlier TRAIN warm-up
and scored VALIDATION signal closes use the same pinned QFQ series;
The sealed Gate 2 scored execution panel uses QFQ_NORMALIZED OPEN for fills
and QFQ_NORMALIZED CLOSE for marking/equity. Its causal session-t CLOSE is
the QFQ close available to the baseline signal after session t closes; no
execution OPEN, future CLOSE, or fill/P&L information enters that signal.
Signal and marking use the same pinned adjusted close values, never mixed
price scales. This research-normalized representation is not evidence of
historical executable fills; `decision_grade=false` remains fixed.
At each VALIDATION close, the resulting
single-asset exposure lies in `[0,1]`. A target is submitted on the first
scored signal or when it differs from the last submitted target under the
committed Phase 2 change detector `np.isclose(atol=1e-12, rtol=0)`. An absent
(`None`) pending instruction creates no fill; a present numeric zero-exposure
target is a cash target that liquidates existing sleeve holdings at its next
eligible OPEN. The target submitted on session `t` can fill only at
the next eligible session `t+1` QFQ-normalized OPEN, under the sealed Gate 2
long-only accounting kernel and 3-bps primary one-way friction. No same-session
close fill, open-priced signal, short, leverage, cash interest, or periodic
parameter update is permitted. The first scored signal is on VALIDATION, and
its first fill is at the next VALIDATION open. A final-session signal with no
next eligible session remains unfilled.

The comparison adapter invokes the sealed Gate 2 replay kernel with a
single-symbol QFQ_NORMALIZED OPEN/CLOSE scored execution panel,
`initial_cash=12500.0`, and no Phase 4 candidate
binding. It must not fabricate a `FixedStrategyBinding` to pass the
candidate-only `replay_targets()` public API. Using the same kernel as Gate 2
benchmarks preserves its next-open fill, turnover, friction, cash, and
long-only conventions without changing the sealed engine. Each sleeve has a
separate kernel invocation and therefore separate cash, units, fill ledger,
and equity state. No sleeve ever refers to another sleeve's cash or holdings;
no pooled portfolio execution or cross-sleeve rebalance exists.

Before calling the private kernel, the isolated adapter enforces the public
Gate 2 target-alignment contract itself: exactly one optional pending
instruction per scored session; a present signal timestamp equals its scored
session; a due timestamp is exactly the next scored session (or `null` only
for the final scored session); weights contain only the sleeve's single
symbol with exposure in `[0,1]`; and the source is the fixed baseline ID,
rule, and parameter tuple rather than a Phase 4 candidate binding. Any
malformed, duplicate, noncausal, extra-symbol, or out-of-range instruction
fails closed before replay. Every recorded fill must satisfy
`signal_timestamp < fill_timestamp` and match that validated next-open due
session. `_replay` is lower-level than `replay_targets()` and must not be
assumed to validate untrusted pending instructions.

The one comparison portfolio per baseline is analytical aggregation *after*
the eight replays: `aggregate_close_equity[t] = sum(sleeve_close_equity_i[t])`
for every scored session. Aggregate daily returns are the Gate 2 convention
`aggregate_close_equity.pct_change()`, yielding 1,007 actual returns.
Initial aggregate capital is exactly 100000.0; aggregate risky exposure is
the sum of the sleeves' risky close value divided by aggregate close equity,
and cannot exceed one because each sleeve is self-financing and unlevered.
Aggregate capital lineage remains eight fixed original 12500.0 ownership
slices; it is never reset to 1/8 of current aggregate equity. The rejected
method `target_weight_i = (1/8) × exposure_i` in one pooled ledger must not be
used or claimed to preserve self-financing sleeves.

Baseline output is diagnostic and comparison-only. It carries baseline ID,
provenance class, exact rule/parameter/implementation identities, eight
sleeve identities, initial cash, QFQ-normalized execution methodology,
aggregate equity/return identity, and `eligible_for_selection=false`.
Baseline IDs never enter the 180-trial ledger or survivor-policy input.

## Return-ending-session regime attribution

The single continuous 1,008-session VALIDATION replay is completed before
regime attribution. The sealed Gate 2 daily-return series is
`close_equity.pct_change()`: exactly 1,007 returns ending on scored sessions
2 through 1,008. No first-session zero, TRAIN-to-VALIDATION return, or
other reset-boundary observation is synthesized. The first scored session
retains its frozen regime label but has no attributable return.

Every actual return ending at session `t` is assigned to the frozen regime
label of that *ending* session, never the preceding session. The complete
frozen map covers all 1,008 sessions exactly once; the three chronological
conditional return vectors partition all 1,007 returns exactly once. A
missing, duplicate, altered, or extra mapping fails closed. Regime labels
are post-replay diagnostics only and cannot enter signals, target weights,
trading eligibility, friction, portfolio state, or replay branching.

For each conditional vector, bind `return_observation_count`,
`positive_return_count` (strictly `r > 0`),
`positive_return_percentage = positive_count/count`,
`arithmetic_mean_session_return = sum(r)/count`, and
`conditional_compounded_return = product(1+r)-1` in original chronological
order. These are pure Gate 3 post-replay arithmetic diagnostics, not a new
Gate 2 metric or a survivor threshold. If a conditional vector is empty,
count is zero and numeric summaries are `UNKNOWN` with reason
`NO_RETURN_OBSERVATIONS`; zero is not imputed. Median is omitted because the
sealed `SupportedMetrics` contract does not expose a regime-session median.

`conditional_compounded_return` is not CAGR, annual/calendar return, or a
continuous holding-period return. Noncontiguous subsets cannot receive
calendar-month/year returns, rolling 12/36-month returns, drawdown, Calmar,
recovery duration, calendar-adjacent losing streaks, or regime-only
annualized turnover. Those remain full continuous-path metrics only.
`max_drawdown` and Calmar remain `UNKNOWN` under DQ-030; DSR and PBO remain
`UNKNOWN/NOT_IMPLEMENTED`. No proxy value is calculated.

## Provider-free runner and immutable methodology evidence

New code is confined to an isolated Gate 3 execution namespace; it may call
sealed Gate 2 and Gate 3 authority APIs but may not alter their files or
artifacts. The runner has no provider, download, export, account, order, or
trading interface and no candidate discovery, retuning, ranking, or survivor
selection during this preparation. Its static campaign plan accepts only the
explicit 180 sealed identities and positions 1–180, and rejects any duplicate,
gap, substitution, extra candidate, or parameter change. Future evaluation
must record each attempted or legitimately skipped trial append-only with
exact population position, trial identity, typed status, and reason.
`UNKNOWN` and `ABSTAIN` remain distinct outcomes with original reasons;
neither is omitted, coerced to success/failure, or imputed as zero. An
execution failure cannot silently remove a candidate result. Synthetic
conformance tests may exercise the adapter; the real Phase 4 VALIDATION
campaign is not run at this checkpoint.

The documentation file's exact-byte `content_sha256` and canonical envelope
SHA-256 (kind `phase4_gate3_execution_spec`, normalized repository-relative
POSIX path) bind the written design without a self-referential digest. Two
canonical semantic method records, kinds `baseline_sleeve_method` and
`regime_return_method`, contain the exact frozen fields above and have
content SHA-256 and canonical envelopes. Their digest is calculated before
candidate performance exists. A final append-only
`gate3_execution_methodology_manifest` binds those method identities, the
spec identity, exact Gate 1/Gate 2/Gate 3 manifest identities, candidate
population digest, TRAIN/VALIDATION identities, runner source-bundle digest,
and full source Git commit. It is the last write under
`results/phase4/gate3/execution_methodology/`; any collision with unequal
bytes, symlink/junction redirect, or changed reference fails closed.
Previous Gate 3 authority evidence remains byte-identical.

The execution preflight must verify the *explicitly pinned* methodology
manifest and all exact dependencies before reporting Gate 1/Gate 2/Gate 3
authorities `VALID`, baseline/regime methods `BOUND`, population 180, and
`GATE3_CAMPAIGN_READY_TO_EXECUTE`. It must not execute a candidate or expose
VALIDATION performance. The existing authority-only preflight remains
unchanged and still reports `READY`; the methodology preflight is a separate
additive boundary.

## Test, review, and stop gates

Implementation is RED → GREEN → relevant regression → commit. Tests prove
eight cash-isolated sleeves and exact aggregation; causal close signals and
next-open QFQ-normalized fills under 3 bps; no fabricated candidate binding;
1,008 labels but only 1,007 return assignments to ending-session labels;
chronological conditional compounding and prohibited-metric absence; static
180-position campaign integrity with `UNKNOWN`/`ABSTAIN` reason retention;
immutable evidence and fail-closed paths;
and no provider, protected-symbol, holdout, or trading surface.

An independent design review must find zero Critical and zero Important
issues before implementation. A fresh post-commit implementation review
must meet the same gate. Focused runner tests, Phase 4 regressions, the full
quant suite, and final preflight must be freshly verified. The terminal status
is `GATE3_CAMPAIGN_READY_TO_EXECUTE`. No real candidate #1 is executed, no
candidate VALIDATION metric is read or ranked, and Phase 4 Gate 3 campaign
remains unstarted until a later explicit checkpoint authorizes it.
