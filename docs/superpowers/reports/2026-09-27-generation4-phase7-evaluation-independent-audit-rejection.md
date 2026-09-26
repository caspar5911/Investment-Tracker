# Generation-4 Phase-7 Evaluation Independent Audit — REJECTED

Date: 2026-09-27

Authority: Independent Audit

Audited branch: `governance/phase6-successor-dividend-normalization-v3`

Audited handoff commit:

`a529cc6f087651b4f5effbc6f3af9812bda67eb5`

Frozen evaluation implementation commit:

`de3aa468d63e5157c935c6af867b0492573510c6`

Evaluation contract SHA-256:

`113f51002c1b10eb3de5d861a8d8c54781d9f97c6deb14e5e9be542b17a8ba6b`

Machine-readable audit-request SHA-256:

`d4ab7b00f389fd801f2180ae6ed682dd09d35a6eb2b7a47848183a047da8b16e`

Auditor-only GitHub Actions run:

`36274558455`

## Verdict

**REJECTED — no Phase-7 evaluation authorization created.**

The implementation passes its focused runtime/CI checks, but the post-authorization authority boundary is materially weaker than the approved design and audit request.

## Checks that passed

The isolated Independent Audit workflow checked out the exact audited handoff commit and passed:

- the seven required focused Phase-7 test files;
- Python compilation of `post_generation3`;
- frozen source/file SHA-256 verification;
- evaluation-contract SHA-256 verification;
- real read-only `verify-evaluation-preflight`;
- XNYS-calendar resolution of the first prospective scored session to `2026-09-28`;
- absent-authorization fail-closed checks for both `acquire-phase7-data` and `evaluate-phase7-checkpoint`;
- static no-trading/no-authorization-writer checks.

The preflight returned:

`GENERATION4_PHASE7_EVALUATION_PREFLIGHT_READY`

The prospective boundary resolved to:

- first scored session: `2026-09-28`;
- warmup limit: `210`;
- warmup excluded from scored P&L: true.

No provider was called and no real Phase-7 performance was calculated.

## Blocking finding — evaluation authorization is not content-bound strongly enough

The approved design and committed audit request require the real
`GENERATION4-PHASE7-EVALUATION-AUTHORIZATION-v1` artifact to bind the actual audit request, frozen evaluation implementation/source identities, evaluation contract, start evidence, candidate/methodology identities, exact universe/boundary, and governance prohibitions.

The implemented runtime authorization model in
`src/investment_tracker/independent_audit/post_generation3/phase7_data.py`
does not provide that full binding.

### 1. Required authorization fields are absent

The strict `Generation4Phase7EvaluationAuthorization` model does not contain all required audit bindings, including at least:

- `audit_request_sha256`;
- frozen evaluation implementation commit;
- evaluation module SHA-256;
- evaluation CLI SHA-256;
- durability module SHA-256;
- data-boundary module SHA-256;
- candidate binding SHA-256;
- strategy implementation SHA-256;
- split-normalizer SHA-256;
- dividend-reconciliation SHA-256;
- successor-evaluator SHA-256;
- start-artifact self-hash;
- start-contract SHA-256;
- initial cash;
- historical-lane classification;
- DQ-030 status.

Because the model uses `extra="forbid"`, an auditor cannot add these required fields to the real authorization without making the artifact invalid.

### 2. Digest fields present in the model are not verified against actual evidence

The model does contain:

- `evaluation_contract_sha256`;
- `start_artifact_sha256`;
- `entry_authorization_sha256`.

However, `verify_generation4_phase7_evaluation_authorization` validates only the JSON shape and selected frozen literals. It does not recompute or compare those SHA-256 fields against the actual committed evaluation contract, start artifact, or entry authorization.

This is demonstrated by the test helper in
`tests/independent_audit/test_generation4_phase7_data_boundary.py`, which uses arbitrary synthetic values such as `"a" * 64`, `"b" * 64`, and `"c" * 64` for these evidence digests and still exercises the accepted authorization path.

### 3. Provider/evaluator commands rely on the weaker loader

The post-authorization CLI commands validate the supplied authorization through the `phase7_data.py` loader before provider/data access, but they do not require or independently verify the bound audit request, evaluation contract, start artifact/start contract, entry authorization, or frozen source identities.

Therefore a structurally valid authorization with incorrect evidence digests could pass the current authorization boundary and reach the provider path.

That violates the approved content-addressed governance design.

## Required remediation

Before a Phase-7 evaluation authorization may be issued:

1. Expand the strict evaluation-authorization schema to include every binding required by the approved design/audit request.
2. Implement one authoritative loader that:
   - recomputes the actual audit-request SHA-256;
   - recomputes the evaluation contract/start artifact/start contract/entry authorization SHA-256 values;
   - verifies the start-artifact self-hash;
   - recomputes the four frozen evaluation source SHA-256 values;
   - verifies the frozen evaluation implementation commit;
   - verifies candidate/binding/implementation and all methodology identities;
   - verifies exact universe, benchmark, initial cash, friction cases, prospective boundary, warmup/checkpoints, historical classification, DQ-030 state, and all governance prohibitions.
3. Require both post-authorization commands to pass this authoritative loader before provider creation or snapshot/data reads.
4. Add RED tests proving every required digest/identity drift fails before provider creation or snapshot read.
5. Remove synthetic acceptance tests that permit arbitrary unrelated evidence digests, or replace them with internally consistent synthetic evidence files and computed hashes.
6. Re-freeze the changed evaluation implementation and regenerate:
   - evaluation implementation/source hashes;
   - evaluation contract;
   - Independent Audit request/template.
7. Re-run Independent Audit.

## Preserved governance state

- Phase 7 remains started.
- Phase-7 performance evaluation remains unauthorized.
- No real evaluation authorization exists.
- Production readiness remains false.
- Live trading remains false.
- Holdout reuse remains false.
- Candidate search/tuning/substitution remain false.
- `RECON-009` remains `OPEN`.
- Work remains paper-only.
- No provider or market-data access was performed by this audit.
