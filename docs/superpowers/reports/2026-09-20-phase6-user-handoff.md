# Phase 6 User Handoff Checklist

This checklist begins only after the Phase 6 pre-unseal branch is green.

## Do not do yet

- Do not fetch or inspect any locked replacement-holdout history.
- Do not run OpenD requests for a locked replacement-holdout symbol.
- Do not create your own `PHASE6-HOLDOUT-RELEASE-v1` record.
- Do not change the frozen strategy parameters.
- Do not start Phase 7.

## What is already prepared by the coordinator

- frozen Phase 6 pre-unseal design;
- exact Phase 4 survivor identity binding;
- explicit carry-forward of the Phase 5 independent-source waiver;
- Independent Audit-only release envelope;
- one-time holdout consumption marker;
- preflight CLI;
- dedicated CI safety checks;
- Independent Audit release-request template.

## Your remaining boundary

The next valid Phase 6 event is an **Independent Audit release decision**.

If release is approved, obtain the exact release envelope, evaluation-contract
file and holdout-bundle file identified by that release. Do not open or inspect
the holdout bundle manually.

At that point the coordinator can validate identities and provide the exact
single-use execution command. The command must write the consumption marker
before it reads the holdout payload.

If Independent Audit does not release the holdout, Phase 6 remains
`PHASE6_READY_FOR_INDEPENDENT_AUDIT_RELEASE`; that is a valid governed stop,
not a failed backtest.
