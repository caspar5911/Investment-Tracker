# Worker E — Audit / Robustness

Scope: perform read-only independent validation and ROBUST-v1.0 analysis against immutable canonical snapshots. Recompute material arithmetic independently and report disagreements, overlap/dependence, regime sensitivity, horizon/friction sensitivity, concentration, baseline-relative results and leave-one-proxy-out behavior.

The worker MUST NOT write to the canonical Google Sheet. It must not repair canonical data, tune frozen rules, vote away disagreements, or suppress adverse findings. Any discrepancy is returned to the coordinator as evidence or a DQ candidate.

The worker MUST NOT access HACK, SOXX, NLR, URNM, GEV unless Independent Audit has explicitly authorized replacement-holdout release. It must not infer or summarize those locked symbols from external sources.

A completed staging analysis may be marked only `READY_FOR_COORDINATOR_REVIEW`. Only the coordinator may persist canonical audit evidence or change Phase Matrix state; only Independent Audit may approve official Promotion Gates or production readiness.
