# Generation-2 Agent Execution Report

Date: 2026-09-22

Authority: **IMPLEMENTATION AGENT** (paper-only research; no real-holdout access)

Branch: `codex/generation2-implementation`

Governance authority commit: `24fbebf135c51af14e26116ee34526ef0dcf1c50`

Execution plan: `docs/superpowers/plans/2026-09-22-generation2-execution-plan.md`

## Final status

Generation 2 **does not terminate**. A credible survivor was selected in
VALIDATION, frozen, independently reproduced, and driven through the complete
synthetic Phase-6 rehearsal pipeline with a fail-closed fault suite.

The agent **STOPs at Checkpoint D** — the forbidden real-holdout boundary.

No real-holdout action was taken:

- no real replacement holdout symbol was selected or locked;
- no historical bars were requested for any prospective holdout;
- no quotes/snapshots/fundamentals/rehab data were requested for holdout
  selection;
- no real acquisition authorization was issued;
- no real Phase 6 was executed;
- no real Phase 7 was started.

All evidence below is synthetic or research-universe only.

## Checkpoint B — Pre-campaign hardening (B-green)

All B tasks were implemented and committed before any Generation-2 candidate
campaign ran. Exit condition met: all synthetic/research-only tests green, and
no candidate campaign executed before the frozen family/grid manifest was
published.

| Task | Scope | Commit |
| --- | --- | --- |
| B1 | Enforce the permanent holdout-exclusion registry in all future blind selectors | `6120e1d` |
| B5 | DQ-030 max-drawdown + Calmar outside sealed Gen-1/Phase-4 code (bundled with B1) | `6120e1d` |
| B8 | Decision-grade `UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1` accounting + tests | `4d75a01` |
| B6 | Independent-source snapshot / result-independent reconciliation interfaces | `1e66a19` |
| B7 | RECON-009 runtime proof harness (not marked resolved from tests alone) | `7910548` |
| B2 | Synthetic Phase-6 dress rehearsal: composite evidence -> authorization -> acquisition -> seal -> release -> evaluation | `8e5a678` |
| B3 | Fault-injection suite (provider failure, partial acquisition, missing/duplicate sessions, corrupt bundle, wrong key, output collision, authorization reuse, interrupted writes, post-write readback failure) | `8e5a678` |
| B4 | Full dress rehearsal as a mandatory synthetic-only CI gate stage | `10e93c5` |

### B-green residual environmental failures (pre-existing, not Gen-2 regressions)

The following failures were observed in the **full** quant suite during the B
gate and are environmental to this machine, not defects in Generation-2
code:

- **Windows MAX_PATH (260-character) limit**: deeply-nested temporary
  fixtures in the full suite exceed the legacy path-length limit on this
  Windows host. The Generation-2 gate uses the scoped synthetic/research
  fixtures, which stay within the limit.
- **15 GB real-data audit tests**: a subset of pre-existing Phase-3/Phase-4
  audit tests materializes the full real ETF dataset (~15 GB) and exceeds the
  600 s foreground tool cap in this environment. These audits are outside the
  Generation-2 synthetic/research gate.

The Generation-2 gate is scoped to synthetic/research data
(`pytest tests/quant -k "generation2"`); it is green. As of this report the
scoped generation-2 suite is **208 tests passing, 0 failing**.

## Checkpoint C — Generation-2 campaign (C1-C7)

The campaign followed the frozen plan exactly: materialize the grid, seal
implementation identities, run the TRAIN-only search, shortlist by the frozen
TRAIN ordering, seal TRAIN before reading VALIDATION, run the fixed 2019-2022
VALIDATION on the shortlist only, apply the frozen pass criteria, select one
survivor by the frozen VALIDATION ordering, freeze identities, reproduce, and
run the survivor through the synthetic Phase-6 rehearsal.

### C1-C7

| Step | Deliverable | Commit |
| --- | --- | --- |
| C1 | Materialize the frozen 162-candidate grid + canonical content-addressed manifest | `b02ed70` |
| C2 | Frozen research data boundary (8 symbols, 2014-2022, content-hash-verified, fail-closed) | `2a8f1f0` |
| C3 | Frozen family signal logic (dual/trend-filtered/vol-scaled/ensemble momentum), DQ-030-aware performance metrics over decision-ledger replays, TRAIN campaign runner + content-addressed seal, and the sealed 162-candidate TRAIN report | `d0c7817`, `d874649`, `d450a98` |
| C4 | VALIDATION campaign (frozen preregistration pass criteria, frozen survivor ordering, sealed self-verifying report) and the sealed 12/12-pass VALIDATION report | `395a465`, `7084dbd` |
| C5 | Freeze survivor candidate/binding/implementation identities (TRAIN + VALIDATION hash chain) | `9700d95` |
| C6 | Deterministic reproduction of the sealed VALIDATION campaign | `a3a5966` |
| C7 | Survivor-bound synthetic Phase-6 rehearsal + 11-case fault suite | `5fdd22b` |

### Survivor

`G2-A|lookback=189|skip=21|top_k=1|rebalance=21`

The TRAIN shortlist produced at most 3 candidates per family (12 total); all 12
shortlist candidates passed the frozen VALIDATION pass criteria; exactly one
survivor was selected by the frozen VALIDATION ordering.

### Sealed, committed evidence

All reports are canonical-JSON, self-hashing (self-excluding `report_sha256`),
content-addressed, and committed under `data/governance/`.

| Artifact | `report_sha256` |
| --- | --- |
| `generation2-grid-manifest.json` | `d9758d074c0a169ee9f083663cf5f297c4b8e95b064e490be4b30abd69882540` |
| `generation2-campaign/train-campaign-report.json` | `2dd8a2cb7ec470bdd1193cf2f5e9d83d4971d29633e839976fc4dba4472487d5` |
| `generation2-campaign/validation-report.json` | `a819b23fae632794224d9d901036983cfb5fc0b004b0f3a1236dbcf86bde9de5` |
| `generation2-campaign/survivor-freeze.json` | `1b7dcb657d367972ee975b758303204eb2166b25958a3d22fe88e849bb709141` |
| `generation2-campaign/reproduction-report.json` | `1281131aa1c4ac75ddcc2b9f9507cc2957c0c527dd423881e1d7600f45d82f47` |
| `generation2-campaign/survivor-rehearsal-report.json` | `174ed998f6a80674b945d21e83872a0df51460c127310c30563be3e1593888d1` |

C6 reproduction status is `REPRODUCTION_CONFIRMED` with
`independent_source_established=false`: the reproduction re-ran the sealed
VALIDATION campaign deterministically and matched the sealed report, but no
independent-source snapshot was available to establish cross-source
independence. C7 rehearsal status is
`SURVIVOR_SYNTHETIC_PHASE6_REHEARSAL_PASSED`, chaining the validation report
(`a819b23f...`) and the survivor freeze (`1b7dcb65...`), with the frozen
survivor's grid record bound as the AES-256-GCM evaluation-contract AAD and the
11-case fault suite all passing fail-closed.

## Governance discrepancies (both flagged per mission directive)

The compact mission summary contained two figures that conflict with the frozen
authoritative governance documents. The agent implemented the **frozen**
sources, not the summary. Both are flagged here.

### (a) VALIDATION pass-criteria mismatch

- **Mission compact summary cited:** "Sharpe >= 5.0, CAGR >= 5.0, max
  drawdown <= 20 percent, OOS Sharpe >= 3.0."
- **Authoritative frozen preregistration**
  (`docs/superpowers/specs/2026-09-22-generation2-governance-preregistration.md`,
  "VALIDATION procedure") instead requires, all true:
  - total return AVAILABLE and > 0;
  - CAGR AVAILABLE and > 0;
  - Sharpe AVAILABLE and > 0;
  - Sortino AVAILABLE and > 0;
  - all-session exposure invariant passes;
  - 25-bps friction total return AVAILABLE and > 0;
  - rolling-12-month positive fraction AVAILABLE and >= 0.50;
  - max drawdown is AVAILABLE under the Generation-2 DQ-030 convention;
  - no decision-critical metric required by the preregistration is UNKNOWN.

  This is implemented in
  `src/investment_tracker/quant/generation2/validation.py::assess_pass`.

- An exhaustive search confirmed **no governance document** contains the
  "5.0 / 20% / 3.0" absolute thresholds, and there is no out-of-sample
  window to which an "OOS Sharpe" could attach (the holdout is forbidden
  before a fully-passing synthetic rehearsal).
- **Decision:** implemented the FROZEN PREREGISTRATION criteria. The summary's
  absolute thresholds were not enforced.

### (b) Holdout-exclusion count: 18 vs 23

- **Mission compact summary stated:** 23 excluded symbols.
- **Authoritative registry** `data/governance/holdout-exclusion-registry.json`,
  field `permanent_exclusions`, holds **18** distinct symbols in three groups:
  - 8 research-universe: GLD, IEF, IWM, QQQ, SPY, TLT, VNQ, XLP
    (`PHASE4_PHASE5_RESEARCH_UNIVERSE`);
  - 5 Generation-1 original holdout: HACK, SOXX, NLR, URNM, GEV
    (`GENERATION1_ORIGINAL_HOLDOUT_PRIOR_HISTORICAL_ACCESS_CANNOT_BE_EXCLUDED`);
  - 5 Generation-1 replacement holdout: FQAL, FDMO, CSB, FTXO, VNLA
    (`GENERATION1_REPLACEMENT_HOLDOUT_FROZEN_AND_CONSUMED`).
- The machine preregistration
  `data/governance/generation2-preregistration.json`, field
  `permanent_holdout_exclusions`, lists the same 18 distinct symbols.
- **Decision:** enforce all registry symbols dynamically (read from the
  registry at selection time; never hardcode 23). The count is 18.

## Checkpoint D — Stop before real holdout

Per the frozen execution plan, the agent MUST STOP here. The following are
**forbidden without a new Independent-Audit authorization** and were not
performed:

- selecting/locking a real replacement final holdout;
- requesting historical bars for any prospective holdout;
- requesting quotes/snapshots/fundamentals/rehab data for prospective holdout
  selection;
- issuing a real acquisition authorization;
- executing real Phase 6;
- starting real Phase 7.

The coordinator performs the blind holdout-selection/audit sequence after
reviewing Checkpoints B-C.

## Phase 7 and beyond

Phase 7 is forbidden unless the new Phase 6 result status is exactly
`PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE` **and** an explicit
Generation-2 Phase-7 entry artifact authorizes progression. An `UNKNOWN`,
`ABSTAIN`, incomplete, consumed-failure, or DQ outcome cannot enter Phase 7.

A separate **future Phase-7 infrastructure** deliverable (implementation only,
synthetic/research data) enforces that guard: Phase-7 entry remains impossible
without the exact Phase-6 status and the explicit entry artifact, and the
`ci_gate` authority flags remain `false`. Production-readiness approval is
separate and is never implied by Phase-7 completion.

## Verification

- Scoped Generation-2 synthetic/research suite
  (`pytest tests/quant -k "generation2"`): **208 passed, 0 failed** at the time
  of this report.
- All sealed reports recompute their self-excluding `report_sha256` on
  verification and are fail-closed against tampering.
- Working tree is clean at each checkpoint boundary; `.qwen/` is untracked and
  is never committed.
