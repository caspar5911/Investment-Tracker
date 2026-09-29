# Phase 4 Finalization Design

## Purpose

Finalize Phase 4 from the already-completed Gate 3 validation campaign without changing, rerunning, or extending the frozen research experiment.

The finalization stage has four responsibilities:

1. audit the completed 180-position campaign evidence;
2. apply the preregistered survivor gates exactly as frozen;
3. deterministically select at most one survivor using the frozen ranking policy;
4. publish an append-only Phase 4 final decision artifact and seal.

This stage must not access FINAL_HOLDOUT, protected symbols, providers, brokerage surfaces, or Phase 5 data.

## Authoritative Starting Point

- Campaign commit: `8acd01a2b5a9a070f4f651644920be64afb785dc`
- Campaign status: `GATE3_CAMPAIGN_RESULTS_COMPLETE`
- Campaign result-set content SHA-256:
  `bbefc542547ddc5e541a2390a978cf45a4a25c65603e0d114a6cb7f1fb9f32a8`
- Campaign aggregate SHA-256:
  `cd84547dc82339746c1780ec5a78d9e5f91a9048a46f06ed96b5e745415b47d2`
- Expected population positions: exactly `1..180`
- Frozen candidate population SHA-256:
  `15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3`
- Runner manifest content SHA-256:
  `ac13f1eef4639d5f4476b2a6d07df0434bf5c8d2c95d67330852db303d0aa5d4`

## Governance Invariants

The implementation MUST preserve all existing frozen Phase 4 authority.

It MUST NOT:

- modify candidate results, attempts, receipts, or campaign result-set bytes;
- modify Gate 1, Gate 2, Gate 3, execution-methodology, result-schema, or runner seals;
- modify survivor thresholds, ranking keys, durability rules, family-stop rules, folds, regimes, friction assumptions, bootstrap assumptions, benchmarks, or candidate identities;
- execute or rerun any candidate;
- create new candidate parameters or new strategies;
- access `HACK`, `SOXX`, `NLR`, `URNM`, or `GEV`;
- access FINAL_HOLDOUT;
- make provider/network downloads;
- introduce brokerage/account/order/trading capability;
- use Phase 5 evidence to influence the Phase 4 decision.

Missing decision-critical evidence fails closed. No result may be promoted because of missing evidence.

## Architecture

Create an additive package:

`src/investment_tracker/quant/phase4/finalization/`

The package is independent of campaign execution. It consumes only the already-published campaign evidence and frozen policy authorities.

Recommended files:

- `models.py` — typed immutable audit and final-decision schemas.
- `audit.py` — campaign accounting, identity, receipt/result linkage, and projection audit.
- `selection.py` — applies the frozen survivor policy to audited candidate evidence.
- `artifacts.py` — content-addressed append-only publication and exact-byte readback.
- `methodology.py` — finalization manifest/seal authority binding campaign + frozen policies + source revision.
- `cli.py` — explicit-hash `audit`, `select`, `seal`, and `preflight` commands only.

Tests live under:

`tests/quant/test_phase4_finalization_*.py`

No existing sealed Phase 4 package is modified.

## Data-Independent Finalization Boundary

Phase 4 finalization must not replay market data.

The Gate 3 campaign already produced and immutably published the candidate result artifacts under the sealed result schema. Finalization therefore validates the committed evidence graph itself:

`campaign result set -> ordered candidate result artifacts -> receipts -> attempts`

For every result identity in the result set, finalization verifies:

- artifact kind is exactly `phase4_gate3_candidate_result`;
- path is the canonical content-addressed path;
- content digest and envelope identity are exact;
- candidate-result JSON is canonical and typed;
- population position is exactly the expected ordered position;
- candidate ID is unique and consistent with provenance;
- candidate population digest is the frozen digest;
- runner/result-schema/Gate authorities in provenance are the frozen identities;
- receipt at the same position exists and references the exact result artifact;
- attempted positions have matching attempts bound to the sealed runner authority;
- skipped family-stop positions have no attempt and contain a valid sealed stop witness;
- there are no missing, duplicate, or extra positions;
- there is no `CAMPAIGN_EXECUTION_FAILED` result.

The finalizer does not recalculate market replay evidence. It treats the committed Gate 3 result artifact as the already-validated unit of evidence and only projects the survivor fields defined by the frozen result-schema authority.

## Survivor Projection

For each `EXECUTED` result, finalization derives a `CandidateSurvivorEvidence` value using the exact already-frozen projection semantics from the Gate 3 result-schema authority.

The projection uses only fields already present in the immutable result artifact plus frozen candidate/family metadata:

- validation total return;
- cash return;
- benchmark excess return;
- Sharpe and Sortino;
- four fold returns and fold benchmark excess;
- neighborhood count, positive fraction, and median benchmark excess;
- friction returns at exactly 0/3/10/25/50 bps;
- annualized one-way turnover;
- average gross exposure and exposure validity;
- bootstrap 5th-percentile lower endpoint;
- durability metrics;
- frozen family component count;
- DQ-030-dependent fields remaining `None/UNKNOWN`.

If any required projection field is unavailable, the candidate is audited as `UNKNOWN` for survivor eligibility and must not be selected.

The projection code must not introduce any new threshold or interpretation.

## Frozen Survivor Eligibility

Eligibility is exactly the existing frozen `_eligible` behavior in
`phase4.preregistration.policy`.

The finalizer must call the existing frozen policy implementation rather than create a new threshold table.

The hard-gate semantics include:

- non-baseline candidate;
- positive validation total return and greater than cash;
- positive benchmark excess;
- defined positive Sharpe and Sortino;
- at least 3 of 4 folds jointly positive on candidate return and benchmark excess;
- at least 2 valid immediate neighbors;
- neighbor positive fraction at least 2/3;
- median neighbor benchmark excess at least 0;
- friction evidence exactly at 0/3/10/25/50 bps;
- 25 bps return positive;
- frozen 25 bps retention calculation matches;
- positive-fold concentration at most 0.75;
- annualized one-way turnover in [0, 12];
- average gross exposure in [0, 1] and all session exposures valid;
- bootstrap lower endpoint at least 0;
- fixed identities invariant;
- durability evidence complete;
- max drawdown, Calmar, DSR, and PBO remain unavailable as frozen.

## Deterministic Selection

Selection MUST call the existing frozen `select_survivor` policy.

The allowed final decision is exactly one of:

- `ONE_FROZEN_SURVIVOR`
- `NO_CREDIBLE_STRATEGY_FOUND`

If zero candidates are eligible, the outcome is `NO_CREDIBLE_STRATEGY_FOUND`.

If one or more candidates are eligible, `select_survivor` applies the already-frozen 22-key ordering and returns exactly one candidate ID.

No manual tie-break, score, ranking override, or analyst preference is permitted.

## Audit Artifact

Publish one canonical Phase 4 audit artifact containing:

- schema version;
- campaign result-set identity;
- campaign aggregate SHA-256;
- expected/accounted position counts;
- per-status counts;
- exact ordered list of 180 audit rows;
- for each row: population position, candidate ID, result artifact identity, result status, projection status, eligibility status, and deterministic rejection reasons;
- eligible candidate IDs in frozen population order;
- survivor-policy identity;
- durability-policy identity;
- candidate-population digest;
- runner-manifest identity;
- safety assertions.

Rejection reasons must be machine-derived from the frozen hard gates. They are evidence, not a new policy layer.

## Final Decision Artifact

Publish one canonical final decision artifact containing:

- schema version;
- final status;
- audit artifact identity;
- campaign result-set identity;
- survivor-policy identity;
- durability-policy identity;
- selected candidate ID and exact result artifact identity when status is `ONE_FROZEN_SURVIVOR`;
- selected candidate frozen provenance identifiers:
  - population position;
  - family ID;
  - hypothesis ID;
  - rule-set SHA-256;
  - parameter-tuple SHA-256;
  - family-definition SHA-256;
- `selected_candidate_id = null` when status is `NO_CREDIBLE_STRATEGY_FOUND`;
- explicit statement that Phase 5 feedback into Phase 4 is forbidden;
- safety state.

The artifact must not contain a new subjective score.

## Phase 4 Final Seal

The finalization seal binds:

- this exact design/spec identity;
- finalization source bundle identity;
- source Git revision;
- campaign result-set identity;
- campaign aggregate SHA-256;
- candidate-population identity;
- runner manifest identity;
- result-schema authority identity;
- frozen survivor-policy identity;
- frozen durability-policy identity;
- audit artifact identity;
- final decision artifact identity.

Allowed seal status:

`PHASE4_FINALIZATION_SEALED`

The seal is content-addressed, append-only, and requires explicit-hash preflight. No latest-pointer discovery is allowed.

## Safety State

Every audit, decision, and seal must explicitly record:

- `candidate_executed = false` for the finalization stage;
- `candidate_rerun = false`;
- `strategy_search_executed = false`;
- `candidate_parameters_changed = false`;
- `survivor_policy_changed = false`;
- `final_holdout_accessed = false`;
- `protected_symbols_accessed = []`;
- `provider_calls = 0`;
- `downloads = 0`;
- `live_trading_capability = false`;
- `phase5_started = false`.

## Error Handling

Finalization fails closed.

Examples:

- malformed or missing campaign artifact -> `PHASE4_FINALIZATION_EVIDENCE_INVALID`;
- missing/duplicate population position -> `PHASE4_FINALIZATION_ACCOUNTING_INVALID`;
- result/receipt/attempt authority mismatch -> `PHASE4_FINALIZATION_AUTHORITY_MISMATCH`;
- unexpected campaign execution failure result -> `PHASE4_FINALIZATION_CAMPAIGN_FAILED`;
- unavailable survivor-critical projection -> candidate remains ineligible/UNKNOWN;
- immutable artifact collision -> reject publication;
- path escape/symlink/reparse redirect -> reject publication;
- source revision/spec/source-bundle mismatch -> preflight failure.

Errors must not trigger candidate reruns or policy changes.

## Testing Requirements

Tests must be written before implementation and cover:

1. exact 180-position accounting;
2. duplicate/missing/extra position rejection;
3. canonical result identity and receipt linkage;
4. runner authority binding;
5. no campaign execution failure accepted;
6. skipped family-stop handling;
7. survivor projection available/unknown behavior;
8. rejection reason derivation for each frozen hard gate;
9. existing frozen `select_survivor` is the sole selection authority;
10. deterministic output independent of filesystem enumeration order;
11. zero-eligible -> `NO_CREDIBLE_STRATEGY_FOUND`;
12. one/multiple eligible -> deterministic one candidate;
13. content-addressed audit/decision/seal identities;
14. idempotent publication;
15. immutable unequal collision rejection;
16. explicit-hash preflight;
17. symlink/path/reparse protection;
18. prohibited-surface scan for provider/holdout/protected-symbol/trading/search APIs.

The existing relevant Phase 4 tests must remain unchanged and passing.

## Completion Criteria

Phase 4 is complete only when:

- the campaign evidence audit is valid for all 180 positions;
- survivor evidence is projected deterministically from sealed artifacts;
- the frozen policy yields exactly one allowed decision outcome;
- audit and final decision artifacts are published;
- the finalization seal is published;
- explicit-hash preflight is deterministic;
- previous Phase 4 evidence remains byte-identical;
- FINAL_HOLDOUT remains untouched.

If the outcome is `ONE_FROZEN_SURVIVOR`, Phase 5 may begin only with that exact frozen strategy and with no retuning.

If the outcome is `NO_CREDIBLE_STRATEGY_FOUND`, Phase 4 ends without opening FINAL_HOLDOUT.
