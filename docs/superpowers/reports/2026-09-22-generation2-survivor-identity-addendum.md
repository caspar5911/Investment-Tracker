# Generation-2 Survivor Implementation & Binding Identity — Addendum

Date: 2026-09-22

Authority: **IMPLEMENTATION AGENT** (paper-only research; no real-holdout access)

Branch: `codex/generation2-implementation`

Parent report: `docs/superpowers/reports/2026-09-22-generation2-agent-execution.md`
(unchanged by this addendum)

Sealed artifact: `data/governance/generation2-campaign/survivor-identity.json`
(schema `GENERATION2-SURVIVOR-IDENTITY-v1`, status
`SURVIVOR_IMPLEMENTATION_AND_BINDING_FROZEN`, generation `GENERATION_2`)

## Why this addendum exists

The coordinator audit of the sealed campaign found that the survivor-freeze
artifact (`survivor-freeze.json`) does not explicitly freeze two required
content identities:

- `implementation_sha256` — the content identity of the exact five
  execution-semantic source modules that produced every sealed number; and
- `binding_sha256` — the content identity of the frozen survivor's parameter
  binding chained against the six prior sealed campaign artifacts.

This repair is **additive**. It freezes those two values on top of the already
sealed evidence without rewriting any historical artifact. It is the last
identity gate that may be added before the project is permitted to cross the
real final-holdout boundary.

## Frozen survivor

- **candidate_id:** `G2-A|lookback=189|skip=21|top_k=1|rebalance=21`
- **family:** `G2-A`
- **candidate_binding** (reconstructed from the frozen grid, byte-for-byte):
  `{candidate_id, family: G2-A, horizon_set: null, lookback: 189, rebalance: 21, skip: 21, top_k: 1, trend_ma: null, vol_lookback: null}`

## Implementation source surface

Exactly five execution-semantic modules are pinned (repo-relative). No other
generation-2 module is part of the implementation surface:

| Source path | SHA-256 |
| --- | --- |
| `src/investment_tracker/quant/generation2/grid.py` | `90d50e239b4ab9a7d04b5836f6eda508b36f19edcc93d003b4201d1d715af2f0` |
| `src/investment_tracker/quant/generation2/strategy.py` | `7dde7b7d6b1f48201358d94020646a9a0cfab328d367b1e904c031ae6913ab40` |
| `src/investment_tracker/quant/generation2/accounting.py` | `d91e21d1483a55f3fd1b97237433b073d1dde7bb5a396b779e2d255659f0e1a9` |
| `src/investment_tracker/quant/generation2/metrics.py` | `60296a74a2c35704ae6f5713716499d78066f85715f6d48d2364a700eef705a7` |
| `src/investment_tracker/quant/generation2/performance.py` | `d037fbc3604a4ff617cf8097b5d8f7951be9778442fdd0e695fa48043330b609` |

Explicitly **excluded** from the surface (verified by test): `validation.py`,
`campaign.py`, `reproduction.py`, `survivor_rehearsal.py`, `phase7_entry.py`.

Implementation surface payload:
`{"schema_version":"GENERATION2-IMPLEMENTATION-SURFACE-v1","interface":"UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1","source_sha256":{...}}`.

## Frozen identity hashes

- **implementation_sha256**
  (`SHA256(canonical_json(implementation_payload))`):
  `35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b`
- **binding_sha256**
  (`SHA256(canonical_json(binding_payload))`, payload schema
  `GENERATION2-SURVIVOR-BINDING-v1`):
  `fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b`
- **identity report_sha256** (self-excluding, over the sealed payload without
  that key):
  `96580b61ddb617f54157cc2ce12f5dc5316dc143321f1aaf214e7a563b5aff87`

## Chained campaign evidence hashes

The identity re-verifies all six prior sealed artifacts (their self-hashes
first) and chains their content hashes into the binding:

| Chained evidence | SHA-256 |
| --- | --- |
| `grid_manifest_sha256` (`generation2-grid-manifest.json`) | `d9758d074c0a169ee9f083663cf5f297c4b8e95b064e490be4b30abd69882540` |
| `train_report_sha256` (`train-campaign-report.json`) | `2dd8a2cb7ec470bdd1193cf2f5e9d83d4971d29633e839976fc4dba4472487d5` |
| `validation_report_sha256` (`validation-report.json`) | `a819b23fae632794224d9d901036983cfb5fc0b004b0f3a1236dbcf86bde9de5` |
| `survivor_freeze_sha256` (`survivor-freeze.json`) | `1b7dcb657d367972ee975b758303204eb2166b25958a3d22fe88e849bb709141` |
| `reproduction_report_sha256` (`reproduction-report.json`) | `1281131aa1c4ac75ddcc2b9f9507cc2957c0c527dd423881e1d7600f45d82f47` |
| `survivor_rehearsal_sha256` (`survivor-rehearsal-report.json`) | `174ed998f6a80674b945d21e83872a0df51460c127310c30563be3e1593888d1` |

## Confirmations

- **The five implementation source files did not change after the survivor
  freeze.** Their current on-disk SHA-256 digests match the values recorded in
  the sealed identity; `verify_survivor_identity` re-hashes each of the five
  files and fails closed with `SURVIVOR_IDENTITY_IMPLEMENTATION_DRIFT` on any
  byte change. No `grid.py`/`strategy.py`/`accounting.py`/`metrics.py`/
  `performance.py` byte differs from what produced the sealed TRAIN,
  VALIDATION, freeze, reproduction, and rehearsal evidence.
- **No TRAIN/VALIDATION rerun was needed or performed.** This addendum only
  reads the six already-sealed artifacts and the five source files; it does not
  re-execute any campaign. The six chained hashes are unchanged from the
  parent Checkpoint-D report.
- **No prospective holdout was selected or accessed.** No real holdout symbol
  was chosen or locked; OpenD was not queried; no historical bars, quotes,
  snapshots, or fundamentals were requested for any holdout candidate.
- **No real Phase 6/7 or trading occurred.** No real acquisition authorization
  was issued, no real Phase 6 was executed, no Phase-7 entry was issued, no
  Phase 7 was started, and no live trading was touched. All evidence remains
  synthetic/research-universe only.

## Verification

The identity is sealed exclusively (second seal is refused,
`SURVIVOR_IDENTITY_EXISTS`) and self-verifying. `verify_survivor_identity`
fails closed with stable codes on any of: artifact self-hash change
(`SURVIVOR_IDENTITY_EVIDENCE_TAMPERED`), implementation source drift
(`SURVIVOR_IDENTITY_IMPLEMENTATION_DRIFT`), candidate id change or
`SURVIVOR_IDENTITY_CANDIDATE_MISMATCH`, candidate-parameter binding change
(`SURVIVOR_IDENTITY_CANDIDATE_BINDING_MISMATCH`), implementation SHA change
(`SURVIVOR_IDENTITY_IMPLEMENTATION_SHA_MISMATCH`), binding SHA change
(`SURVIVOR_IDENTITY_BINDING_SHA_MISMATCH`), any chained report SHA change
(`SURVIVOR_IDENTITY_CHAINED_HASH_MISMATCH`), candidate no longer in the frozen
grid (`SURVIVOR_IDENTITY_CANDIDATE_NOT_IN_FROZEN_GRID`), or survivor differing
from the sealed VALIDATION/survivor-freeze evidence. A tampered identity field
that was re-signed still trips the self-hash gate
(`SURVIVOR_IDENTITY_TAMPERED`).

Gate: `python -m pytest -q tests/quant -k "generation2"` — green.
Scoped: `python -m pytest -q tests/quant/test_generation2_survivor_identity.py`
— green (21 passed).

This completes the coordinator-audit repair. The project remains STOPped at the
forbidden real-holdout boundary.
