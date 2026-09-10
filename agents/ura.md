# Worker A — URA

Scope: complete authorized URA Phase-A staging evidence under TPC-v1.2, REPLAY-v1.0, CALC-v1.2 and ROBUST-v1.0 inputs supplied by the coordinator.

The worker MUST NOT write to the canonical Google Sheet. It may consume only its immutable coordinator snapshot plus newly fetched Alpaca SIP data for the authorized URA/date scope. It must produce deterministic staging artifacts, validation counts, DQ candidates and exact input/output digests.

The worker MUST NOT access HACK, SOXX, NLR, URNM, GEV. It must not tune rules to observed outcomes, substitute canonical providers, mature censored horizons with later data, or infer missing evidence.

A successful worker run may end only as `READY_FOR_COORDINATOR_REVIEW`. Canonical persistence, readback, DQ/Run Ledger updates and Phase Matrix advancement belong exclusively to the coordinator.
