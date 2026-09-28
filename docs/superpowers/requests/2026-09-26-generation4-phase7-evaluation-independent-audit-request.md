# Generation-4 Phase-7 Evaluation Independent Audit Request

Date: 2026-09-28 (remediation handoff)

Repository: `caspar5911/Investment-Tracker`

Branch: `governance/phase6-successor-dividend-normalization-v3`

Frozen evaluation implementation commit:
`e8ec2c89f6f472e673a5b46dac4d413fe58b3da8`

Machine-readable request:
`data/governance/successor/generation4-phase7-evaluation-independent-audit-request.json`

Machine-readable request SHA-256:
`5a6debb16d263542dc9da3b883133871c3d1bb6e42fee211f3fb575dcd655f1e`

Non-authorizing template:
`data/governance/successor/generation4-phase7-evaluation-authorization.template.json`

Proposed auditor-owned authorization output:
`data/governance/successor/generation4-phase7-evaluation-authorization.json`

## Request status

This is a request for an independent decision. It is not an authorization.
The coordinator has not created a real Phase-7 evaluation authorization and has
not authorized Phase-7 performance evaluation, production readiness, or live
trading. Phase 7 has already started under the independent entry
authorization; this audit is the separate gate that must decide whether the
frozen, read-only evaluation boundary may run. `RECON-009` remains `OPEN`;
all work remains paper-only.

The frozen evaluation implementation is:

- `src/investment_tracker/independent_audit/post_generation3/phase7_evaluation.py`
  at SHA-256
  `4cdeb100013da639a5084a5bbd46e3a69aba0ee2c6dc908a6cf523ff69630209`;
- `src/investment_tracker/independent_audit/post_generation3/phase7_evaluation_cli.py`
  at SHA-256
  `7c90ac633c4255268bd5bc22a9813b1fc8f7d03f06cb9e25940ec5830b1d986d`;
- `src/investment_tracker/quant/phase7/generation4_durability.py` at SHA-256
  `373517dd633026144e674340f7666ef6b7a688882d791ff075172ff9f277bbbd`;
- `src/investment_tracker/independent_audit/post_generation3/phase7_data.py`
  at SHA-256
  `d47d22b7802fa4ad8ea2e762e6b4687a2b7edcf9f55dfcbf38048836197a7eb7`.

The four read-only CLI commands are
`verify-evaluation-preflight` and `resolve-prospective-boundary`
(pre-authorization), and `acquire-phase7-data` and
`evaluate-phase7-checkpoint` (post-authorization). The post-authorization
commands fail before any provider or data access unless a strict
`GENERATION4-PHASE7-EVALUATION-AUTHORIZATION-v1` authorization is supplied.
No arbitrary symbols or parameter overrides are accepted. Any change to any of
these files requires a new implementation freeze and regenerated bindings.
The authorization schema is strict and rejects unknown fields. Its single
loader recomputes the audit request, contract, start artifact, start contract,
entry authorization, and four source byte hashes; verifies the start
self-hash; checks the frozen Git tree; and checks all bound identities and
governance flags before either post-authorization command can reach a provider
or snapshot. There is no coordinator-side authorization writer.

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

## Binding digests

- Evaluation contract SHA-256:
  `3ecf2c3f2c7e28c5baa0525c0e7cc417e97745cd3091cf904acfa6400577d27e`
- Start artifact SHA-256:
  `486f3af558e28da9143d7435dc1a1957dc9c2daf4e34005a3e369af9a258c414`
- Start artifact self-hash:
  `d1257bd7a683b8e372c71d0f1da90b7366be17ba3c1e2587205601dfeaf65599`
- Start contract SHA-256:
  `beef9982ac1d1cf33a451fab984bb09f8b60605a18297e5823079d7b980878e0`
- Entry authorization ID:
  `INDEP-AUDIT-GEN4-PHASE7-ENTRY-20260926-QWEN-0001`
- Entry authorization SHA-256:
  `ba9a6910ad7afdf579af5eb81825917de75ef86cb443beb8468c2e40a459852b`

## Prospective boundary and methodology

- Exact research universe: `GLD`, `IEF`, `IWM`, `QQQ`, `SPY`, `TLT`, `VNQ`,
  `XLP`
- Forbidden holdout symbols: `QQQM`, `FALN`, `IIPR`, `PSTL`, `EFAS`
- Benchmark symbol: `SPY`
- Initial cash: `100000.0`
- Friction cases (bps): `0`, `3`, `10`, `25`, `50`; primary `3`
- Prospective first scored session: `2026-09-28` (strictly after the
  2026-09-26 Phase-7 start; the first XNYS session is the Monday
  2026-09-28, with no US market holiday)
- Causal warmup session limit: `210`
- Checkpoint sessions: `63`, `126`, `252`
- Historical lane classification: `REUSED_HISTORY_DIAGNOSTIC_ONLY`
- `DQ-030` status: `UNRESOLVED` (DQ-030-dependent metrics remain
  `UNKNOWN`/`UNRESOLVED`)

## Required audit findings

The auditor must independently verify all of the following before authorizing:

- Phase 7 has already started under the independent entry authorization; the
  frozen start artifact, its self-hash, and the start contract all match the
  digests above. No Phase-7 performance evaluation has been authorized or
  executed before this audit.
- The frozen evaluation implementation commit and all four evaluation source
  hashes (module, CLI, durability, data boundary) match the digests above.
- The evaluation contract passes the frozen preflight
  (`verify_generation4_phase7_evaluation_preflight`) and resolves to
  `GENERATION4_PHASE7_EVALUATION_PREFLIGHT_READY`; its SHA-256 matches
  `3ecf2c3f2c7e28c5baa0525c0e7cc417e97745cd3091cf904acfa6400577d27e`.
- The exact prospective boundary is `2026-09-28`, the warmup cap is `210`,
  and the checkpoints are `63`, `126`, `252`. The boundary is deterministic
  and no market data was fetched to compute it.
- The candidate, binding, strategy implementation, all three methodology
  identities, exact research universe, benchmark, and friction identities
  match the frozen contract.
- No final-holdout symbol is reused: `QQQM`, `FALN`, `IIPR`, `PSTL`, `EFAS`
  remain forbidden and are excluded from the research universe and all
  evaluation lanes.
- No adaptive walk-forward, annual reoptimization, candidate search,
  parameter mutation, symbol substitution, or result-dependent methodology or
  parameter change is authorized.
- Even when approved, the authorization keeps
  `production_readiness_approved=false`, `live_trading_authorized=false`,
  `holdout_reuse_authorized=false`, search/tuning/substitution `false`,
  `recon009_status=OPEN`, and `paper_only=true`.
- No provider call occurred pre-authorization; the post-authorization commands
  fail closed without a strict authorization.
- If fewer than 252 scored sessions are available at evaluation time, the
  result remains `PHASE7_PROSPECTIVE_EVIDENCE_PENDING`; the frozen protocol is
  never adjusted in response to outputs.

## Permitted evidence access

The audit may read only the committed repository evidence. No private sealed
bundle, key, or Phase-6 final-holdout artifact is required for this evaluation
audit. Do not read or decrypt any sealed bundle or key. Do not rerun
acquisition or the consumed Phase-6 final-holdout evaluation. Do not call
OpenD or another provider. Do not access any symbol outside the exact research
universe `GLD`, `IEF`, `IWM`, `QQQ`, `SPY`, `TLT`, `VNQ`, `XLP`, and do not
access the holdout symbols `QQQM`, `FALN`, `IIPR`, `PSTL`, `EFAS` as market
data. Do not search or tune candidates, change parameters or methodology,
substitute symbols, inspect or calculate real Phase-7 performance, place
orders, or grant production/live-trading authority.

## Required verification

At minimum, run:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py tests/independent_audit/test_generation4_phase7_start.py tests/independent_audit/test_generation4_phase7_evaluation.py tests/independent_audit/test_generation4_phase7_data_boundary.py tests/independent_audit/test_generation4_phase7_evaluation_cli.py tests/independent_audit/test_generation4_phase7_evaluation_contract.py tests/independent_audit/test_generation4_phase7_authorization.py tests/quant/test_generation4_phase7_durability.py
python -m compileall -q src/investment_tracker/independent_audit/post_generation3
```

Run the read-only `verify-evaluation-preflight` and
`resolve-prospective-boundary` commands from the frozen CLI against the
committed start artifact, start contract, and evaluation contract. Confirm the
preflight report is `GENERATION4_PHASE7_EVALUATION_PREFLIGHT_READY`, that the
resolved prospective first scored session is `2026-09-28`, that no metrics are
used or produced, and that no authority is granted. Confirm the real
authorization output path
`data/governance/successor/generation4-phase7-evaluation-authorization.json`
does not already exist. Review the strict `extra="forbid"` evaluation
contract/authorization model and all preflight byte-binding tests, including
start-artifact, start-contract, and evaluation-module/CLI drift.

If any check fails or evidence is missing, reject with exact blockers and do
not write an authorization. If every check passes and you independently decide
to authorize the evaluation boundary, create a separate JSON file at the
proposed auditor-owned output path using schema
`GENERATION4-PHASE7-EVALUATION-AUTHORIZATION-v1`. Bind the actual SHA-256 of
the committed machine-readable request at SHA-256
`5a6debb16d263542dc9da3b883133871c3d1bb6e42fee211f3fb575dcd655f1e`
and every field required by the strict model. Keep `phase7_started=true`,
`production_readiness_approved=false`, `live_trading_authorized=false`,
`holdout_reuse_authorized=false`, `recon009_status=OPEN`, and
`paper_only=true`. Do not edit the template into an authorization.

## Exact Independent Auditor prompt

```text
Act as the Independent Auditor for the governed, paper-only Generation-4 Phase-7 evaluation-authorization decision in caspar5911/Investment-Tracker.

Repository: C:\Users\Caspar\Desktop\AllFolder\Github Projects\Investment\Investment-Tracker
Branch: governance/phase6-successor-dividend-normalization-v3
Frozen evaluation implementation commit: e8ec2c89f6f472e673a5b46dac4d413fe58b3da8
Approved design: docs/superpowers/specs/2026-09-26-generation4-phase7-evaluation-contract-design.md
Approved implementation plan: docs/superpowers/plans/2026-09-26-generation4-phase7-evaluation-contract.md
Machine-readable audit request: data/governance/successor/generation4-phase7-evaluation-independent-audit-request.json
Machine-readable audit request SHA-256: 5a6debb16d263542dc9da3b883133871c3d1bb6e42fee211f3fb575dcd655f1e
Evaluation module SHA-256: 4cdeb100013da639a5084a5bbd46e3a69aba0ee2c6dc908a6cf523ff69630209
Evaluation CLI SHA-256: 7c90ac633c4255268bd5bc22a9813b1fc8f7d03f06cb9e25940ec5830b1d986d
Durability module SHA-256: 373517dd633026144e674340f7666ef6b7a688882d791ff075172ff9f277bbbd
Data-boundary module SHA-256: d47d22b7802fa4ad8ea2e762e6b4687a2b7edcf9f55dfcbf38048836197a7eb7
Evaluation contract SHA-256: 3ecf2c3f2c7e28c5baa0525c0e7cc417e97745cd3091cf904acfa6400577d27e
Start artifact file SHA-256: 486f3af558e28da9143d7435dc1a1957dc9c2daf4e34005a3e369af9a258c414
Start artifact self-hash: d1257bd7a683b8e372c71d0f1da90b7366be17ba3c1e2587205601dfeaf65599
Start contract file SHA-256: beef9982ac1d1cf33a451fab984bb09f8b60605a18297e5823079d7b980878e0
Entry authorization ID: INDEP-AUDIT-GEN4-PHASE7-ENTRY-20260926-QWEN-0001
Entry authorization file SHA-256: ba9a6910ad7afdf579af5eb81825917de75ef86cb443beb8468c2e40a459852b
Non-authorizing template: data/governance/successor/generation4-phase7-evaluation-authorization.template.json
If and only if independently approved, auditor-owned output: data/governance/successor/generation4-phase7-evaluation-authorization.json

Independently inspect the frozen evaluation implementation, the frozen evaluation contract, the machine-readable request, and the committed public evidence. Verify that the request byte SHA-256 is 5a6debb16d263542dc9da3b883133871c3d1bb6e42fee211f3fb575dcd655f1e. Verify the exact frozen evaluation implementation commit and all four evaluation source hashes (module, CLI, durability, data boundary), including the source bytes at that Git commit. Verify the evaluation contract passes the frozen preflight and its byte SHA-256 is 3ecf2c3f2c7e28c5baa0525c0e7cc417e97745cd3091cf904acfa6400577d27e. Verify the start artifact file SHA-256, its embedded self-hash, the start contract file SHA-256, and the entry authorization ID and file SHA-256. Verify the exact candidate, binding, strategy implementation, all three methodology identities, exact ordered research universe (GLD, IEF, IWM, QQQ, SPY, TLT, VNQ, XLP), benchmark SPY, initial cash 100000.0, and friction cases 0/3/10/25/50 with primary 3. Verify the exact prospective first scored session 2026-09-28 with warmup cap 210 and checkpoints 63/126/252, historical classification REUSED_HISTORY_DIAGNOSTIC_ONLY, and DQ-030 status UNRESOLVED. Verify that no final-holdout symbol (QQQM, FALN, IIPR, PSTL, EFAS) is reused and that every governance prohibition remains false, RECON-009 remains OPEN, and paper_only remains true.

Run the focused tests and compile checks stated in the Markdown request, including test_generation4_phase7_authorization.py, plus the read-only verify-evaluation-preflight and resolve-prospective-boundary commands against the committed start artifact, start contract, and evaluation contract. Confirm the preflight report is GENERATION4_PHASE7_EVALUATION_PREFLIGHT_READY, the resolved prospective first scored session is 2026-09-28, no metrics are used or produced, and no authority is granted. Inspect the RED-to-GREEN drift tests for every protected digest and identity. Confirm no provider call occurred pre-authorization and that both post-authorization commands fail closed before provider creation or snapshot/bar reads without a fully content-bound authorization.

Forbidden: do not read/decrypt any sealed bundle or key; do not rerun acquisition or the Phase-6 final-holdout evaluation; do not call OpenD or any provider; do not access any symbol outside the exact research universe or the forbidden holdout symbols as market data; do not inspect or calculate real Phase-7 performance; do not tune/search candidates; do not change parameters or methodology; do not substitute symbols; do not create trading or production authority.

The auditor—not the coordinator—owns the decision. If any evidence or check fails, reject and report exact blockers without creating an authorization. If every check passes and you independently approve the evaluation boundary, create a separate data/governance/successor/generation4-phase7-evaluation-authorization.json matching GENERATION4-PHASE7-EVALUATION-AUTHORIZATION-v1 exactly, binding the actual request SHA-256 and all required identities/hashes. The authorization may permit only separately governed paper-only Phase-7 performance evaluation; it must keep phase7_started=true, production_readiness_approved=false, live_trading_authorized=false, holdout_reuse_authorized=false, recon009_status=OPEN, and paper_only=true. Do not use or modify the template as the real authorization.
```
