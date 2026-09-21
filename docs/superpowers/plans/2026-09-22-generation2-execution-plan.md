# Generation 2 Execution Plan

Date: 2026-09-22

Governance authority commit:
`24fbebf135c51af14e26116ee34526ef0dcf1c50`

## Checkpoint A — Generation 1 closure

- [x] Freeze Phase 6 consumed-failure closure.
- [x] Freeze Generation-1 terminal state.
- [x] Freeze permanent holdout exclusions.
- [x] Add fail-closed Phase-7 entry guard.
- [ ] Merge PR #27 after all required CI passes.

## Checkpoint B — Pre-campaign implementation hardening

Agent-owned implementation work:

- [ ] Enforce permanent holdout exclusion registry in all future blind selectors.
- [ ] Build complete synthetic Phase-6 dress rehearsal:
  composite evidence -> authorization -> acquisition -> seal -> release -> evaluation.
- [ ] Add fault injection for provider failure, partial acquisition, missing/duplicate
  sessions, corrupt bundle, wrong key, output collision, authorization reuse,
  interrupted writes, and post-write readback failure.
- [ ] Make full dress rehearsal a mandatory CI gate.
- [ ] Implement Generation-2 DQ-030 max drawdown + Calmar outside sealed
  Generation-1/Phase-4 code.
- [ ] Implement independent-source snapshot/reconciliation interfaces.
- [ ] Implement RECON-009 runtime proof harness; do NOT mark RECON-009 resolved
  from tests alone.
- [ ] Implement decision-grade unadjusted corporate-action accounting and tests.

Exit condition: all synthetic/research-only tests green. No Generation-2 candidate
campaign has run before frozen family/grid manifest publication.

## Checkpoint C — Generation 2 campaign

- [ ] Materialize canonical frozen family/grid manifest exactly matching the
  preregistration.
- [ ] Seal implementation identities before campaign execution.
- [ ] Run TRAIN-only search on the eight research symbols through 2018.
- [ ] Shortlist at most 3 candidates/family using frozen TRAIN ordering.
- [ ] Seal TRAIN evidence before reading VALIDATION.
- [ ] Run fixed 2019-2022 VALIDATION on shortlist only.
- [ ] Apply frozen pass criteria.
- [ ] If none pass: terminate as NO_CREDIBLE_GENERATION2_CANDIDATE.
- [ ] If one or more pass: choose one survivor using frozen VALIDATION ordering.
- [ ] Freeze survivor candidate/binding/implementation identities.
- [ ] Reproduce evidence from independent-source snapshot if available.
- [ ] Run exact selected implementation through complete synthetic Phase-6
  dress rehearsal and fault suite.

Exit condition: frozen credible survivor + green dress rehearsal, or terminal
NO_CREDIBLE_GENERATION2_CANDIDATE.

## Checkpoint D — Stop before real holdout

The agent MUST STOP here.

Forbidden without a new Independent-Audit authorization:

- selecting/locking a real replacement final holdout;
- requesting historical bars for any prospective holdout;
- requesting quotes/snapshots/fundamentals/rehab data for prospective holdout
  selection;
- issuing a real acquisition authorization;
- executing real Phase 6;
- starting real Phase 7.

The coordinator will perform the blind holdout-selection/audit sequence after
reviewing Checkpoints B-C.

## Checkpoint E — Future real Phase 6

Coordinator + local OpenD only after Checkpoint D review:

- blind static-only selection;
- provider quota + retained-log virginity evidence;
- freeze exact Phase-6 contract;
- green CI;
- one-time acquisition authorization;
- one-time acquisition/seal;
- independent release;
- one-time evaluation;
- UNKNOWN/ABSTAIN on any consumed failure.

## Checkpoint F — Phase 7 and readiness

Only if Phase 6 completes successfully:

- preregister Phase 7;
- fixed-strategy durability/forward evidence;
- decision-grade/research-accounting reconciliation;
- paper-only shadow operation;
- stale-data, DQ, provenance, recovery monitoring;
- RECON-009 real runtime proof;
- final independent audit.

Production-readiness approval remains separate and is never implied by Phase-7
completion.
