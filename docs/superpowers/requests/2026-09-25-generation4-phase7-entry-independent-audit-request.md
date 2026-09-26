# Generation-4 Phase-7 Entry Independent Audit Request

Date: 2026-09-25

Repository: `caspar5911/Investment-Tracker`

Branch: `governance/phase6-successor-dividend-normalization-v3`

Frozen implementation commit: `7893306e3c77b85c59f044b787a55579593c678b`

Machine-readable request:
`data/governance/successor/generation4-phase7-entry-independent-audit-request.json`

Non-authorizing template:
`data/governance/successor/generation4-phase7-entry-authorization.template.json`

Proposed auditor-owned authorization output:
`data/governance/successor/generation4-phase7-entry-authorization.json`

## Request status

This is a request for an independent decision. It is not an authorization.
The coordinator has not created a real Phase-7 authorization, has not marked
Phase 7 started, and has not approved production readiness or live trading.
`RECON-009` remains `OPEN`; all work remains paper-only.

The frozen entry verifier and CLI are:

- `src/investment_tracker/independent_audit/post_generation3/phase7_entry.py`
  at SHA-256
  `63738d5e71aec76adcdc8206567083a78b6d45737b97b7d538b0f239623a75e3`;
- `src/investment_tracker/independent_audit/post_generation3/phase7_entry_cli.py`
  at SHA-256
  `7110c7a695e97f7351fc19ffd9433b8d3d95f2f7464668d9a214ec19d4966dfc`.

Any change to either file requires a new implementation freeze and regenerated
bindings. The authorization schema is strict and rejects unknown fields. There
is no coordinator-side authorization writer.

## Frozen identities

- Candidate: `G2-A|lookback=189|skip=21|top_k=1|rebalance=21`
- Binding SHA-256:
  `fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b`
- Strategy implementation SHA-256:
  `35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b`
- Split/corporate-action normalizer SHA-256:
  `bfbf0de5bdeb39af3535641570f3f9224f5301abb7db9fffc34c580481cace04`
- Dividend reconciliation v3 SHA-256:
  `6baa251d51f6f16be602aa82b08fc46665a4ccdd62f68705821c48c8a28ac9bc`
- Corrected evaluator v3 SHA-256:
  `fb20b368d6d7ac0f698c5ab45e5824aaad73341cccfacc25bc6903b98c9a2b21`
- Ordered locked symbols: `QQQM`, `FALN`, `IIPR`, `PSTL`, `EFAS`
- Holdout ID:
  `successor-phase6-holdout-e6aa1f4e9f04b2e905df7cc828c65669`
- Release ID:
  `successor-phase6-release-934966d25eef0b2bfb4b5de289539a05`

## Seven evidence hashes

1. Phase-6 contract:
   `88cb0f7a958facf47af3311933d2d64821277107a73a0b7a1336cdb0a98af923`
2. Generation-4 acquisition authorization:
   `1e04f0b3ae070218f24a3f3a7884b96059e486b09655d287ace172f9178b85e8`
3. Acquisition receipt:
   `98d6e5696749382df706a39c461135a3d897b9c8654b0bae5d8e3b75d58426bb`
4. Release:
   `75ff62f5ebb3ff7f0051eedc3d9e5020cc951acd294e64fb81883e4d06492c6d`
5. Evaluation result:
   `73f8fa006219855522ecb3dab264078bd494ae8a1474542f58be7556c88facfc`
6. Evaluation consumption marker:
   `5841029bb3c29b164399150318cb3590591c96d0ef87a55e61f5e0973615848c`
7. Phase-6 closure:
   `58d5d4ee63cca02ebad8a64be8f57a86c5ac4e986bc4e89a16818bb73d3c0330`

## Required audit findings

The auditor must independently verify all of the following before authorizing:

- Phase-6 status is exactly
  `PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE` and
  `one_time_consumed=true`.
- Phase 7 has not started, no Phase-7 authority exists before this audit,
  production readiness is false, live trading is false, and `RECON-009=OPEN`.
- Candidate, binding, strategy implementation, all three methodology
  identities, and ordered locked symbols match the frozen contract.
- The existing strict Generation-4 acquisition-authorization loader validates
  the contract, selection, virginity evidence, and Stage-B source identities
  before the acquisition-authorization file hash is calculated.
- The receipt, release, result, marker, and closure carry every methodology
  identity defined by their frozen schemas. They are not required to carry a
  direct dividend-v3 field where their schemas never defined one. Dividend-v3
  is proven by the exact contract-to-acquisition-authorization binding.
- `paper_only=true` is proven by the frozen Phase-6 contract and Generation-4
  acquisition authorization. Downstream schemas are not required to invent a
  `paper_only` field.
- Receipt bytes bind into the release and closure; release bytes bind into the
  closure; result bytes bind into the marker and closure; marker bytes bind
  into the closure.
- The closure is the terminal Phase-6 artifact. Before authorization it is
  fully validated for schema, identities, governance, and internal evidence
  hashes, and its actual SHA-256 is reported. No closure self-hash exists or
  may be invented. Once the audit request and authorization bind the closure
  digest, any closure byte drift must fail with
  `GEN4_PHASE7_AUTHORIZATION_MISMATCH`.
- Retry, holdout reuse, candidate search, symbol substitution, and
  result-dependent methodology or parameter changes remain forbidden.
- An allowed entry decision still reports `phase7_started=false`,
  `production_readiness_approved=false`, `live_trading_authorized=false`,
  `recon009_status=OPEN`, and `paper_only=true`.

## Permitted evidence access

The audit may read only the committed repository evidence and these private
JSON artifacts:

- `C:\Users\Caspar\Desktop\Investment-Tracker-Private\generation4\successor-phase6-holdout-e6aa1f4e9f04b2e905df7cc828c65669.receipt.json`
- `C:\Users\Caspar\Desktop\Investment-Tracker-Private\generation4\successor-phase6-holdout-e6aa1f4e9f04b2e905df7cc828c65669.release.json`
- `C:\Users\Caspar\Desktop\Investment-Tracker-Private\generation4\successor-phase6-holdout-e6aa1f4e9f04b2e905df7cc828c65669.phase6-result.json`
- `C:\Users\Caspar\Desktop\Investment-Tracker-Private\generation4\evaluation-markers\successor-phase6-release-934966d25eef0b2bfb4b5de289539a05.consumed.json`
- `C:\Users\Caspar\Desktop\Investment-Tracker-Private\generation4\successor-phase6-holdout-e6aa1f4e9f04b2e905df7cc828c65669.phase6-closure.json`

Do not read or decrypt the sealed bundle or key. Do not rerun acquisition or
the consumed final-holdout evaluation. Do not call OpenD or another provider.
Do not search or tune candidates, change parameters or methodology, substitute
symbols, place orders, or grant production/live-trading authority.

## Required verification

At minimum, run:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py tests/independent_audit/test_generation4_stage_a_boundary.py tests/independent_audit/test_generation4_stage_b_boundary.py tests/independent_audit/test_post_generation3_authority.py tests/independent_audit/test_successor_dividend_evaluator_v3.py tests/quant/test_successor_corporate_actions_v2.py tests/quant/test_successor_dividend_reconciliation_v3.py
python -m compileall -q src/investment_tracker/independent_audit/post_generation3
```

Run the real `verify-readiness` command shown in the approved plan/specification
using only the ten JSON paths. Confirm the output has all seven hashes, contains
no performance metrics, and grants no authority. Confirm the real authorization
output path does not already exist. Review the strict model and all authorization
drift tests, including acquisition-authorization and closure byte drift.

If any check fails or evidence is missing, reject with exact blockers and do
not write an authorization. If every check passes and you independently decide
to authorize entry, create a separate JSON file at the proposed auditor-owned
output path using schema `GENERATION4-PHASE7-ENTRY-AUTHORIZATION-v1`. Bind the
actual SHA-256 of the committed machine-readable request and every field
required by the strict model. Do not edit the template into an authorization.

## Exact Independent Auditor prompt

```text
Act as the Independent Auditor for the governed, paper-only Generation-4 Phase-7 entry decision in caspar5911/Investment-Tracker.

Repository: C:\Users\Caspar\Desktop\AllFolder\Github Projects\Investment\Investment-Tracker
Branch: governance/phase6-successor-dividend-normalization-v3
Frozen implementation commit: 7893306e3c77b85c59f044b787a55579593c678b
Approved design: docs/superpowers/specs/2026-09-25-generation4-phase7-entry-gate-design.md
Machine-readable audit request: data/governance/successor/generation4-phase7-entry-independent-audit-request.json
Non-authorizing template: data/governance/successor/generation4-phase7-entry-authorization.template.json
If and only if independently approved, auditor-owned output: data/governance/successor/generation4-phase7-entry-authorization.json

Independently inspect the frozen implementation, approved design, machine-readable request, committed public evidence, and the five private JSON evidence files listed in the Markdown request. Verify the exact candidate, binding, strategy implementation, all three methodology identities, ordered locked symbols, holdout/release IDs, all seven evidence hashes, the full receipt -> release -> result -> marker -> closure chain, terminal-closure semantics, one-time consumption, and every fail-closed governance condition. Verify that paper-only authority comes from the frozen Phase-6 contract and acquisition authorization, and that dividend-v3 identity comes from their exact binding rather than invented downstream fields. Verify the request, gate, CLI, acquisition-authorization, and closure byte bindings and the strict extra-forbid authorization schema.

Run the focused tests and compile checks stated in the Markdown request, plus the real JSON-only verify-readiness command. Confirm readiness is non-authorizing, Phase 7 has not started, production and live trading remain unauthorized, RECON-009 remains OPEN, retry/reuse/search/substitution/result-dependent changes remain forbidden, and no metrics are used for authorization.

Forbidden: do not read/decrypt the sealed bundle or key; do not rerun acquisition or final-holdout evaluation; do not call OpenD or any provider; do not tune/search candidates; do not change parameters or methodology; do not substitute symbols; do not create trading or production authority.

The auditor—not the coordinator—owns the decision. If any evidence or check fails, reject and report exact blockers without creating an authorization. If every check passes and you independently approve entry, create a separate data/governance/successor/generation4-phase7-entry-authorization.json matching GENERATION4-PHASE7-ENTRY-AUTHORIZATION-v1 exactly, binding the actual request SHA-256 and all required identities/hashes. The authorization may permit only separately governed paper-only Phase-7 entry; it must keep phase7_started=false, production_readiness_approved=false, live_trading_authorized=false, recon009_status=OPEN, and paper_only=true. Do not use or modify the template as the real authorization.
```
