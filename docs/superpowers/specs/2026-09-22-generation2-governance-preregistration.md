# Generation 2 Governance and Research Preregistration

Date: 2026-09-22

Status: **FROZEN BEFORE GENERATION-2 CAMPAIGN EXECUTION**

Authority: **COORDINATOR / INDEPENDENT-AUDIT BOUNDARY**

## Objective

Generation 2 may search for a new paper-only ETF rotation candidate after
Generation 1 terminated at `PHASE6_UNKNOWN_ABSTAIN`.

Generation 2 is a new research generation. It is not a retry of Generation 1
Phase 6.

## Information barrier

Generation 2 strategy design, parameter search, TRAIN ranking, VALIDATION
acceptance, and survivor selection may use only the established research
universe:

- GLD
- IEF
- IWM
- QQQ
- SPY
- TLT
- VNQ
- XLP

Historical information after 2022-12-31 is forbidden for Generation-2 strategy
development.

Chronology remains:

- TRAIN: through 2018-12-31
- VALIDATION: 2019-01-01 through 2022-12-31
- FINAL_HOLDOUT: selected later and never used for development

Earlier observations may be used only as causal warmup when required by a
frozen strategy definition.

The following symbols are permanently excluded from future final-holdout
selection and may not be used to inform Generation-2 tuning:

- research universe: GLD, IEF, IWM, QQQ, SPY, TLT, VNQ, XLP
- Generation-1 original holdout: HACK, SOXX, NLR, URNM, GEV
- Generation-1 replacement holdout: FQAL, FDMO, CSB, FTXO, VNLA

The Generation-1 failed acquisition observation, including the returned FQAL
bars, must not be inspected, summarized, used, or inferred for Generation-2
strategy research.

Only the governance fact that the Generation-1 holdout is contaminated/retired
may be used.

## Paper-only and implementation constraints

- Long only.
- No leverage.
- No short selling.
- No options, futures, inverse ETFs, or brokerage execution.
- Signal from completed information only.
- Earliest fill is the next eligible session after the signal.
- Initial cash: 100000.
- Primary friction: 3 bps on absolute traded notional.
- Required friction cases: 0, 3, 10, 25, 50 bps.
- Candidate search may not alter the final-holdout protocol.

## Generation-2 strategy families

The implementation agent must materialize the exact parameter grids below and
commit their canonical manifest **before running any Generation-2 campaign**.

### G2-A — Dual momentum rotation

Cross-sectional momentum plus an absolute-momentum eligibility filter.

Frozen grid:

- momentum lookback sessions: 63, 126, 189, 252
- skip sessions: 0, 21
- top_k: 1, 2, 3
- rebalance sessions: 21, 42
- ineligible assets receive zero target weight
- if no asset is eligible, remain in cash

Maximum grid size: 48.

### G2-B — Trend-filtered momentum

Cross-sectional momentum with a moving-average trend eligibility filter.

Frozen grid:

- momentum lookback sessions: 63, 126, 252
- trend moving-average sessions: 126, 200, 252
- top_k: 1, 2, 3
- rebalance sessions: 21, 42
- skip sessions: 21
- if no asset is eligible, remain in cash

Maximum grid size: 54.

### G2-C — Volatility-scaled momentum

Cross-sectional momentum with inverse-volatility weighting among selected
eligible assets.

Frozen grid:

- momentum lookback sessions: 63, 126, 252
- volatility lookback sessions: 20, 63
- top_k: 2, 3
- rebalance sessions: 21, 42
- skip sessions: 21
- gross target cap: 1.0
- no leverage; if volatility scaling requests >1.0 gross, normalize down to 1.0
- if no asset is eligible, remain in cash

Maximum grid size: 24.

### G2-D — Multi-horizon momentum ensemble

Rank assets by the equal-weight arithmetic mean of trailing total returns over
the configured horizons.

Frozen grid:

- horizon sets:
  - [21, 63, 126]
  - [63, 126, 252]
  - [21, 126, 252]
- skip sessions: 0, 21
- top_k: 1, 2, 3
- rebalance sessions: 21, 42
- require positive ensemble score for eligibility
- if no asset is eligible, remain in cash

Maximum grid size: 36.

No additional strategy family may be added after campaign execution begins.
No grid value may be added, removed, or changed after the first Generation-2
candidate is evaluated.

## Search budget

- Maximum Generation-2 candidates: 162 total from the four frozen grids.
- No adaptive grid expansion.
- No external strategy research after the first campaign begins.
- No result-dependent family replacement.
- Every attempted candidate consumes its deterministic budget position.

## TRAIN procedure

All 162 (or fewer if duplicate canonical candidates collapse) candidates are
evaluated on TRAIN only.

A TRAIN candidate is eligible for family shortlisting only if:

- total return status is AVAILABLE and > 0;
- CAGR status is AVAILABLE and > 0;
- Sharpe status is AVAILABLE and > 0;
- all-session exposure invariant passes;
- 25-bps friction total return is AVAILABLE and > 0;
- candidate identity and implementation binding are valid.

Within each family, shortlist at most three candidates by this frozen
lexicographic order:

1. higher TRAIN Sharpe;
2. higher TRAIN CAGR;
3. lower annualized one-way turnover;
4. ascending candidate_id.

VALIDATION data must not be read while TRAIN search/ranking is executing.

## VALIDATION procedure

Evaluate only the preregistered TRAIN shortlist, maximum 12 candidates.

No parameters, implementations, ranking criteria, or family definitions may
change after VALIDATION begins.

A candidate passes VALIDATION only if all are true:

- total return AVAILABLE and > 0;
- CAGR AVAILABLE and > 0;
- Sharpe AVAILABLE and > 0;
- Sortino AVAILABLE and > 0;
- all-session exposure invariant passes;
- 25-bps friction total return AVAILABLE and > 0;
- rolling-12-month positive fraction AVAILABLE and >= 0.50;
- max drawdown is AVAILABLE under the Generation-2 DQ-030 convention;
- no decision-critical metric required by this preregistration is UNKNOWN.

If no candidate passes, Generation 2 terminates with
`NO_CREDIBLE_GENERATION2_CANDIDATE`.

If multiple candidates pass, choose exactly one survivor by:

1. higher VALIDATION Sharpe;
2. higher VALIDATION CAGR;
3. smaller max-drawdown magnitude;
4. lower annualized one-way turnover;
5. ascending candidate_id.

This selection rule is frozen before VALIDATION.

## Decision-grade accounting requirement

Before any new FINAL_HOLDOUT symbol is selected, the selected Generation-2
candidate must also pass a synthetic and research-universe implementation
rehearsal for the successor accounting model:

`UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS`

The rehearsal must explicitly model:

- unadjusted execution prices;
- splits/share adjustments;
- cash dividends;
- deterministic cash ledger;
- friction;
- next-session execution;
- no same-bar lookahead.

Any unresolved reconciliation defect remains a blocker to real final-holdout
access.

## Final-holdout rule

A new final holdout may be selected only after:

1. Generation-2 survivor is frozen;
2. implementation/binding identities are frozen;
3. all required TRAIN/VALIDATION evidence is sealed;
4. the complete acquisition/seal/release/evaluation pipeline passes a synthetic
   end-to-end dress rehearsal;
5. fault-injection tests pass;
6. Independent Audit authorizes blind holdout selection.

The permanent exclusion registry must be applied before deterministic blind
ranking.

No final-holdout historical price, quote, snapshot, fundamental, rehab, or
corporate-action data may be inspected during selection.

## Phase 7

Phase 7 is forbidden unless the new Phase 6 result status is exactly:

`PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE`

and an explicit Generation-2 Phase-7 entry artifact authorizes progression.

An `UNKNOWN`, `ABSTAIN`, incomplete, consumed-failure, or DQ outcome cannot
enter Phase 7.

## Production

Generation 2 remains paper-only and Experimental.

Completion of Phase 7 does not automatically imply production readiness.
Independent Audit remains required.
