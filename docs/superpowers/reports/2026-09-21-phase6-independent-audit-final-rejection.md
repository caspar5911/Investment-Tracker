# Phase 6 Independent Audit Final Release Decision

Date: 2026-09-21

Authority: **INDEPENDENT_AUDIT**

## Decision

`PHASE6_AUDIT_UNKNOWN_ABSTAIN`

`FINAL_HOLDOUT_RELEASE_REJECTED`

Independent Audit does not authorize release of the locked replacement holdout
`HACK, SOXX, NLR, URNM, GEV`.

## Decisive evidence

The project owner supplied the output of the audit-side OpenD access-log
classifier. Its exact JSON payload SHA-256 is:

`7d450b567211e4590434af8aa93c28b943eecc053be2620647d446139c4ce2f0`

The classifier reports:

`HISTORICAL_KLINE_CONTEXT_FOUND`

and identified explicit `Qot_RequestHistoryKL` / protocol 3103 context for
every locked symbol:

- HACK: 6 history-context matches
- SOXX: 12
- NLR: 8
- URNM: 4
- GEV: 2

The audit does not need to inspect the underlying historical prices to resolve
the release question. The release criterion required Independent Audit to
verify that the five locked symbols had not previously been accessed by the
coordinator. That condition can no longer be verified. Under the project's
fail-closed rule, the holdout therefore cannot be certified virgin.

This finding is intentionally stated as
`PRIOR_LOCKED_SYMBOL_HISTORICAL_ACCESS_CANNOT_BE_EXCLUDED`, not as a claim
about what information a human viewed or what performance was observed. The
OpenD evidence is sufficient to defeat the required no-prior-access
attestation.

## Consequences

No `PHASE6-HOLDOUT-RELEASE-v1` envelope is issued.

No real holdout bundle is created.

No Phase 6 strategy evaluation is executed against these five symbols.

No result from these symbols may be used to tune, replace, rerank, or reinterpret
the frozen Phase 4 survivor.

The frozen strategy identity remains unchanged.

Phase 5 remains:

`PHASE5_UNKNOWN_ABSTAIN`

Reason:

`INDEPENDENT_SOURCE_SNAPSHOT_MISSING`

Phase 7 remains unstarted.

Production readiness is not approved.

## Status of the audit tooling

The independent-audit branch still retains the pre-access contract, encrypted
bundle implementation, one-time evaluator, and synthetic conformance tests.
Those components remain useful infrastructure, but they do not authorize use of
a compromised holdout.

## Next governance action

The repository contains no already-frozen blind replacement-holdout procedure
that may be invoked automatically after this rejection.

If the project owner wants a valid one-time final holdout, a new replacement
procedure must first be preregistered **before any candidate replacement symbol
history is inspected**. The procedure must select replacement symbols without
using observed strategy performance and must keep the Phase 4 survivor,
parameters, execution timing, methodology, and frozen evaluation window fixed
unless a separately justified governance decision is made before access.

A replacement must never be chosen because it gives a better result.
