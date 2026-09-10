# Worker C — SMH

Scope: complete authorized SMH Phase-A staging evidence under the frozen tracker rules. Verify the known 2:1 split effective 2023-05-05 and apply NORM-v1 deterministically to pre-split history before replay.

The worker MUST NOT write to the canonical Google Sheet. It may use only its immutable coordinator snapshot, canonical SPY snapshot, and authorized Alpaca SIP data. All outputs must include deterministic validation counts, DQ candidates and digests.

The worker MUST NOT access HACK, SOXX, NLR, URNM, GEV. It must not tune thresholds after seeing outcomes, substitute canonical providers, infer missing data, or violate phase/censoring boundaries.

A successful run may be marked only `READY_FOR_COORDINATOR_REVIEW`. Canonical integration, readback, lineage records and Phase Matrix advancement are coordinator-only actions.
