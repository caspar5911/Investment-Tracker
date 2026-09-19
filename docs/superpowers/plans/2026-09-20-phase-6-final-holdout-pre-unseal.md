# Phase 6 Final-Holdout Pre-Unseal Implementation Plan

1. Freeze the pre-unseal design before any holdout access.
2. Add tests for Independent Audit release-envelope validation.
3. Add tests proving invalid/missing release cannot trigger a payload read.
4. Add one-time exclusive consumption-marker tests.
5. Implement the minimum Phase 6 preseal package to satisfy those contracts.
6. Add a deterministic preflight/readiness artifact.
7. Add CI that verifies Phase 4 authority regressions and scans Phase 6 for
   provider/order-routing surfaces and locked-symbol literals outside the
   governance-only allowlist.
8. Stop before any FINAL_HOLDOUT payload is opened.
