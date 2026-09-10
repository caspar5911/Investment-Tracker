# Coordinator Contract

The coordinator is the only agent allowed to mutate the canonical Google Sheet.

Before dispatch or integration, verify frozen versions, Calculation Tests, authorized asset/date scope, current Phase Matrix state, relevant DQ references, and locked-holdout exclusion. Create an immutable input snapshot with content digests for all material inputs.

For every worker submission:

1. Validate the manifest and artifact digests.
2. Recompute the worker snapshot lineage against current canonical digests.
3. Reject the submission as `STALE_SNAPSHOT` if any material canonical input has changed.
4. Re-run deterministic invariants independently.
5. Resolve canonical locations by semantic identity, never by worker-supplied physical row numbers.
6. Acquire the single-writer canonical lock.
7. Write one bounded canonical block.
8. Immediately read back the written block and verify exact values/static state.
9. Record any defect or repair through Data Quality evidence.
10. Append truthful Run Ledger evidence.
11. Update Phase Matrix last, only after persistence and readback validation succeeds.
12. Release the canonical lock.

If any prerequisite, write, readback, digest, benchmark alignment, or post-write invariant fails, stop at the previous canonical state and fail closed. Never self-promote Promotion Gates or official readiness.

The coordinator must not execute trades or unlock HACK, SOXX, NLR, URNM, GEV without Independent Audit authorization.
