# Phase 4 Gate 3 pre-campaign result schema

## Authorization and boundary

Starting revision: `81aa3060975671376c782e48d4d8051f18265edb`, clean `main`.
This specification is written before candidate #1 and before any candidate
VALIDATION performance is observed. No field or threshold is selected from
campaign results. It defines the complete typed representation and validation
of already authorized evidence. It changes neither Gate 1 policy, Gate 2
execution, Gate 3 authorities, nor the execution methodology.

The terminal status is `GATE3_CAMPAIGN_RESULT_SCHEMA_SEALED`. There is no
campaign orchestrator, candidate execution command, ranking command, survivor
selection, provider, protected-symbol, holdout, export, or trading interface.
Phase 5 is outside this task. Synthetic evidence tests are permitted; real
candidate evidence is neither produced nor read in this task.

All implementation is additive under `quant.phase4.gate3_campaign`. The
14 files bound to execution-methodology revision
`d3de728a2a7f7143d3fc394a8c62e767c91968fa` remain byte-identical, including
the preparation `TrialRecord` guard. A necessary change to any bound file
requires stopping with
`GATE3_RESULT_SCHEMA_REQUIRES_EXECUTION_METHODOLOGY_RESEAL` before editing.

## Exact dependencies

Existing authority and execution preflights must pass before implementation
and again after sealing. No latest-artifact discovery is allowed.

| Authority | Content SHA-256 |
| --- | --- |
| Gate 1 manifest | `dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89` |
| Gate 2 manifest | `c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6` |
| Corrected Gate 3 authority | `705935c9b06b8f592e66e5e71e4541d910b585be6e9a30e46b99fe97b7591d4f` |
| Execution methodology | `9c37e20ccc54132716c3e347b8005d097500a14aeba41d9eedeaf28de3ebe877` |
| Survivor policy | `7529b02a76622d97cf6568290a91142c33409ee4a02c137be6d09c0142655a63` |
| Durability policy | `37195247139733d81a0772c0fe84222e51237198ab33954eb2a4c0e96880843c` |
| Family budget/stop policy container | `ae7482967c475216bb09e7c0beb39e179019c6f065ca271ee6f8d51756b478d5` |
| Candidate population | `15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3` |

Policy identities are full canonical artifact envelopes extracted from the
verified Gate 1 manifest. The stop policy is the existing
`family_stop_policy` member of its family-budget-policy artifact; do not
manufacture a historical standalone stop artifact. TRAIN and VALIDATION use
the exact existing `DataPartitionIdentity` objects (including eight dataset
hashes). The exact 180 Gate 2 `FixedStrategyBinding` objects and their order
are loaded from the manifest's candidate-binding artifact. The engine
implementation identity is its sealed `engine` source-bundle digest.

## Result types and acceptance boundary

`PHASE4-GATE3-CANDIDATE-RESULT-v1` is frozen and extra-forbidden. It contains
no unrestricted dictionary evidence payload. Its top-level fields bind
campaign ID, position, candidate/trial/family/hypothesis IDs, family-definition,
rule-set and parameter-tuple digests, population digest, full TRAIN/VALIDATION
identities, full Gate 1/2/3/execution-methodology identities, engine digest,
evaluation-context digest, schema implementation Git revision, status and
reason. The source revision must equal the implementation revision in the
explicit result-schema seal. A future campaign's orchestrator revision is a
separate campaign-level provenance identity, not a replacement for this one.

The typed evaluation context binds these same authorities, fixed initial cash
100000, 3 bps PRIMARY friction, `COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN`,
`QFQ_NORMALIZED`, and `decision_grade=false`. Its canonical digest is
recomputed. Dataset provenance comes from the frozen partition identities;
this schema does not invent a new market-panel construction convention.

Structural Pydantic construction alone is not authoritative acceptance.
`validate_result` must reconstruct all nested models under strict validation,
verify the exact loaded authority, and compare every derived field with its
recomputed value. The artifact store invokes this validator on write and read;
`model_construct` and `model_copy(update=...)` cannot bypass it. Explicit JSON
decoding converts arrays to declared tuples and canonical UTC timestamp strings
to pandas timestamps only; it never coerces strings or booleans into numbers.
All floating evidence must be finite. Original sealed classes are reused,
with no changes to their validators. Canonical serialization handles their
timestamp fields explicitly and excludes unstable timestamps.

Statuses are `EXECUTED`, `UNKNOWN`, `ABSTAIN`, `SKIPPED_FAMILY_STOP`, and
`CAMPAIGN_EXECUTION_FAILED`. EXECUTED requires the entire typed evidence
structure; individual mathematically unavailable values remain typed UNKNOWN.
The other statuses carry no replay or metric payload and require a nonempty
original reason. UNKNOWN/ABSTAIN denote absence of a completed primary
observation and project unavailable benchmark excess. If primary evidence
exists but a robustness statistic is unavailable, retain EXECUTED with the
complete typed evidence structure and its explicit UNKNOWN statistic; do not
discard a known positive excess by relabeling the whole observation UNKNOWN.

SKIPPED_FAMILY_STOP requires `PERSISTENT_OOS_FAILURE` plus exactly the 50
consecutive evaluated same-family population positions ending at the triggering
position, their unique trial IDs and evidence artifact identities. Every later
skip may reference that same trigger window, never a window of skipped records.
The trigger precedes the skipped position. Authoritative validation and store
read/write resolve all 50 references, verify their identity/order/family/status,
and derive nonpositive/unavailable excess from their validated observations.
Only EXECUTED/UNKNOWN/ABSTAIN observations may contribute. Unresolved references
fail closed; neither caller-supplied streaks nor excess summaries are trusted.
Skipped records and system failure have no `CandidateOOSOutcome`
projection and is never silently incremented as research failure. No new stop
rule is introduced.

## Replay and component evidence

EXECUTED embeds existing `PortfolioReplay` objects for the candidate's five
friction cases, and the primary equal-weight buy-and-hold and cash benchmarks.
They have the exact 1008 scored session labels from the frozen fold authority,
initial cash 100000, reset cash/zero positions at the first session, and exactly
1007 actual close-to-close returns. PRIMARY is the 3 bps replay. Benchmark
replays carry no candidate binding; every candidate state/fill has the exact
sealed binding. Symbols are restricted to the frozen eight. Fills must be at
the next scored session after their signal, with the sealed friction rate.
Before metric calculation require total turnover to equal the sum of absolute
fill notionals, fill notional to agree with units delta times reference open,
and friction to agree with absolute notional times bps/10000. Reconcile units
and cash forward from reset using the fills and derive realized exposure from
close equity and cash. Use the engine's existing numeric-accounting tolerance
only for binary64 rounding; no tolerance changes a research threshold.
This validates representation and internal linkage; checking all raw fill
prices against dataset bars remains the engine/campaign replay responsibility.

Every component is linked through its canonical content digest and primary
replay digest. Its candidate and binding identities, when exposed by its
sealed type, must match. Calendar, fold, bootstrap and regime evidence inherit
the unchanged binding from the one primary replay. Neighbors have their own
sealed bindings, each immutable, plus an explicit relationship to the focal
candidate; they must not be falsely relabeled as the focal candidate.

Reuse `SupportedMetrics` and `calculate_metrics(primary, benchmark)` exactly,
including total return, CAGR, annualized volatility, Sharpe, Sortino, excess,
total/annualized turnover, target/realized exposure series and means, and time
in market. Recompute from embedded replays and compare every field. Cash return
comes from the embedded cash benchmark, whose equity stays at initial cash.
`UnavailableStatistics` forbids numeric drawdown, Calmar, DSR or PBO. Their
existing UNKNOWN/reason fields remain unchanged under DQ-030.

Reuse engine `DurabilityEvidence` and `calculate_durability` with the exact
expected-session authority. Compare month/year labels and returns, positive
fractions, signed averages, worst periods, losing streak, concentrations and
12/36-month windows and summaries. Phase 4 does not require 60-month evidence;
`rolling_60` must remain absent. Legitimate empty-subset UNKNOWN values are
preserved; required decision inputs that are unavailable prevent a survivor
projection. Completeness is derived from recomputation, never a caller flag.

Reuse `FoldSliceEvidence` for candidate and benchmark. The four IDs are
`FOLD_2019`, `FOLD_2020`, `FOLD_2021`, `FOLD_2022`. Continuous equity anchors are
the first validation close, then each preceding fold's last close, through
each current fold's final close. This implements Gate 2's continuous-boundary
ratio and the exact frozen calendar membership without portfolio reset or a
synthetic first return. Reuse `slice_continuous_folds`; derive excess by paired
candidate-minus-benchmark fold return, joint positive count, and largest
positive return divided by sum of positive returns (UNKNOWN if nonpositive).

Use a strict serialization projection of the sealed `RegimeAttribution` and
`ConditionalRegime` dataclasses. Recompute using `attribute_regime_returns`
and the exact frozen mapping. Preserve three regime IDs, all 1008 labels,
1007 ending-session assignments, counts, positive fraction, mean, conditional
compounding and status/reason. No path-dependent subset metrics are admitted.

Reuse `FrictionEvidence` and its exact cases `(0,3,10,25,50)`; preserve each
case's replay digest, identity, equity, total return and turnover. Derive those
values from the matching embedded replay. The stored retention ratio must
equal the existing 25/3 definition and UNKNOWN denominator behavior. A
nonpositive primary return already fails the existing selection gate.

Neighborhood membership is the complete sorted set returned by the sealed
family's `neighbors(parameter_tuple_sha256)`. Each entry has its exact binding,
status/reason and, if available, its primary replay and SupportedMetrics.
Recompute its metrics against the same benchmark. No additional neighbor trial
is generated or executed. Derive valid count, positive count/fraction and
median excess from available return/excess pairs. Fewer than two valid neighbors
is `UNKNOWN/INSUFFICIENT_VALID_NEIGHBORS`. Missing, duplicate and injected IDs
are rejected. Availability is determined by evidence, not a caller flag.

Reuse `BootstrapEvidence` and `bootstrap_median_daily_return` over the exact
primary 1007-return vector. Bind vector SHA-256 and recompute sample size,
observed median, 5th/95th endpoints, 2000 draws, seed 0. `[0.0,0.0]` is evidence
only for this median-daily-return statistic, never broader confidence.

Comparison baseline references are optional typed identities with the exact
four frozen baseline IDs and `eligible_for_selection=false`. They cannot
replace the equal-weight/cash benchmark evidence, become candidate IDs, or
affect candidate identity, eligibility or ordering.

## Survivor and stop projections

Reuse the existing `CandidateSurvivorEvidence`; never add a competing selection
model. All its fields are deterministic projections of the verified components.
The 12 Gate 1 hard gates are unchanged: positive return above cash; positive
benchmark excess; positive defined Sharpe/Sortino; at least three jointly
positive folds; at least two valid neighbors with >=2/3 positive returns and
nonnegative median excess; positive 25 bps return; positive-fold concentration
<=0.75; finite annualized turnover in [0,12]; all target/realized exposures in
[0,1]; median-return bootstrap lower bound >=0; invariant strategy identity;
complete required evidence. Unknown decision-critical values yield a typed
UNKNOWN projection with exact missing-field reasons and no fabricated numeric
projection. Research rejection is distinct from execution status. The
nonoptional numeric fields of Gate 1 must never be filled with sentinel zeros.

All 22 ordering inputs are preserved in the sealed order: joint-fold consistency,
positive-year fraction, minimum rolling36, minimum rolling12, losing-month
streak, worst year, worst month, year concentration, top-three-month
concentration, positive-month fraction, neighbor fraction, friction retention,
excess, Sharpe, Sortino, bootstrap lower endpoint, turnover, fold concentration,
signal-component count, total return, CAGR, candidate ID. Signal-component count
comes only from the sealed family definition. No ranking or survivor selection
is performed by this subsystem. An optional stored projection must match the
recomputed typed projection field-for-field. No manual eligibility flag exists.

Family-stop input is the primary benchmark excess, even if another robustness
gate fails. Reuse `CandidateOOSOutcome` and `update_oos_failure_streak` semantics:
50 consecutive nonpositive/unavailable excesses; positive excess resets; isolated
other failures do not increment it. System error raises
`CAMPAIGN_EXECUTION_FAILED` and skipped records raise `SKIPPED_NOT_OBSERVATION`
when an OOS projection is requested.

## Canonical artifacts and seal

Result content identity is SHA-256 of the entire canonical JSON representation,
including all evidence, derived projections, reasons and provenance. Artifact
identity is the existing SHA-256 canonical envelope of exact-byte content
SHA-256, normalized repository-relative POSIX path, and artifact kind. All
components are ordered deterministically; display rounding never participates.

A separate additive store uses
`results/phase4/gate3/campaign_result_schema/` for authority evidence and
`results/phase4/gate3/campaign/candidate_result/` for future result artifacts.
The latter is exercised only in temporary synthetic-test roots now. Writes are
atomic no-overwrite publications, idempotent for identical bytes, and fail on
unequal collisions. Canonical path/envelope/bytes are verified on read. Reject
traversal, symlinks and all Windows reparse/junction redirects before access.

The final authority binds this specification content/envelope, schema/version,
canonical identity algorithm, exact Gate 1/2/3/execution references, three policy
references, 180-population digest, partitions, engine digest, implementation Git
revision, complete new implementation source bundle and fixed safety facts.
The source loader rejects revision mismatch, modified files and cross-worktree
imports; it compares exact worktree and imported source bytes with committed
blobs. No old evidence is overwritten. The authority is published last after
all checks, and committed in a separate evidence-only commit.

The CLI exposes only `seal --source-revision` and
`preflight --manifest-content-sha256`. Explicit-hash preflight verifies all
dependencies, all new source/spec bytes and the complete semantic schema
contract, returning `GATE3_CAMPAIGN_RESULT_SCHEMA_SEALED` with policy and source
bindings BOUND and old gates VALID. It reads no candidate result files and
calculates no candidate performance.

## Verification and completion

Independent design review must have zero Critical/Important findings before
implementation; commit the specification and plan separately. Implement using
RED, GREEN, regression, commit, then independent implementation review. Tests
cover all identity substitutions, nested strict types/coercions, nonfinite
values, all required evidence omissions and derived-field tampering, exact
fold/regime/friction/neighborhood/bootstrap/durability semantics, projection
completeness, statuses, canonical identities and filesystem attacks. Preserve
the existing preparation EXECUTED rejection and unchanged security tests.

Run focused, Gate 3, Phase 4 and full `pytest -q tests/quant` suites, recording
exact counts. After implementation review PASS, seal and independently verify
the new authority; rerun all three preflights. Report commits, identities,
coverage, review, tests and access facts, then stop before candidate #1.
