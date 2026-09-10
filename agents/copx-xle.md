# Worker D — COPX / XLE

Scope: complete COPX first and then XLE Phase-A staging evidence under frozen tracker rules. Preserve deterministic corporate-action handling; XLE's verified later split rule must remain explicit so future Phase-B processing cannot drift.

The worker MUST NOT write to the canonical Google Sheet. It may use only immutable coordinator snapshots, approved canonical SPY inputs, and Alpaca SIP for authorized symbol/date scopes. Produce deterministic staging files, validation counts, DQ candidates and digests.

The worker MUST NOT access HACK, SOXX, NLR, URNM, GEV. No threshold tuning, provider substitution, inferred sessions, phase leakage or silent repair is permitted.

A successful worker run may be marked only `READY_FOR_COORDINATOR_REVIEW`. The coordinator alone performs canonical writes, readback, DQ/Run Ledger updates and Phase Matrix advancement.
