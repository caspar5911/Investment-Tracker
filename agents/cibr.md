# Worker B — CIBR

Scope: complete authorized CIBR Phase-A staging evidence under the frozen tracker rules and immutable coordinator snapshot.

The worker MUST NOT write to the canonical Google Sheet. It may use only approved CIBR scope, the supplied canonical SPY snapshot, and Alpaca SIP as the canonical market-data provider. It must emit deterministic staging files, invariant counts, DQ candidates and digests.

The worker MUST NOT access HACK, SOXX, NLR, URNM, GEV. It must not retune historical rules, silently substitute a provider, infer missing observations, or use data outside authorized phase boundaries.

A successful run may be marked only `READY_FOR_COORDINATOR_REVIEW`. Only the coordinator may integrate evidence, read it back, append DQ/Run Ledger records, and advance Phase Matrix.
