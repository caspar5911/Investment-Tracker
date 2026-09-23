# Generation-3 Successor Stage-A Independent Audit Authorization

Date: 2026-09-23

Authority: **INDEPENDENT_AUDIT**

## Decision

`APPROVED` (Stage A only)

Independent Audit issues the real Stage-A methodology and blind virgin-holdout
selection authorization for the Phase-6 successor, formally named `GENERATION_3`.

Artifact:

`data/governance/successor/successor-methodology-authorization.json`

Schema: `SUCCESSOR-PHASE6-METHODOLOGY-AUTHORIZATION-v1`
Status: `SUCCESSOR_PHASE6_METHODOLOGY_AUTHORIZED`
Authority: `INDEPENDENT_AUDIT`
Approval: `INDEP-AUDIT-GEN3-METHODOLOGY-0001`

This is a re-audit after the coordinator's CI fix commit
`5148cd754e063404de059e5e87260e58aa4157a9`
(`ci: word-bound protected-symbol guard`). The prior sole blocker — the
protected-symbol guard `! grep -R -nE 'BNO|GBIL|CWS|ESG|VICI'` false-positiving
on the substring `ESG` inside the unrelated cryptography identifier `AESGCM`
(6 matches across `evaluate.py` and `acquisition.py`) — is resolved by
word-bounding the pattern to `\b(BNO|GBIL|CWS|ESG|VICI)\b`. The fix touches
only `.github/workflows/successor-corporate-actions-v2.yml` (1 file, 1 line);
no source, test, data, or methodology file changed. Successor CI run
`35807761634` is reported green; a local replication of the corrected guard
over the successor source/test set returns 0 matches.

## Verification (all 9 areas re-confirmed at commit `5148cd7`)

1. Predecessor Gen2 closure unchanged and consumed/UNKNOWN:
   `data/generation2/phase6/phase6-final-holdout-closure.json` is
   `status=PHASE6_UNKNOWN_ABSTAIN`, `evaluation.one_time_consumed=true`,
   `retry_authorized=false`, `replacement_authorized=false`,
   `symbol_substitution_authorized=false`, `phase7.authorized=false`,
   `recon009_status=OPEN`.
2. Corporate-action v2 normalization logic correct (Unicode/ASCII arrows,
   endpoint old→new units, rehab reciprocal direction, effective-date/window
   handling, fail-closed ambiguity) — `corporate_actions_v2.py`.
3. Frozen survivor intact: `G2-A|lookback=189|skip=21|top_k=1|rebalance=21`,
   `binding_sha256=fd482e…`, `implementation_sha256=35a3ad…` (unchanged).
4. All 23 previously used/contaminated symbols permanently excluded via
   `data/governance/holdout-exclusion-registry.json`.
5. Blind successor selection uses only allowed static metadata, provider
   quota, and retained local log evidence; no prices/returns/history;
   `historical_market_data_api_called=false`.
6. Normalizer/evaluator/authority contracts hash-bound and fail closed.
7. Stage-A leaves `protected_history_access_authorized=false`,
   `phase7_authorized=false`, `production_readiness_approved=false`,
   `recon009_status=OPEN`.
8. Focused successor tests: 32/32 pass
   (`test_successor_corporate_actions_v2.py` 17,
   `test_successor_authority.py` 7,
   `test_successor_holdout_selection.py` 3,
   `test_successor_phase6_boundary.py` 5).
9. Specific files reviewed: audit request, methodology-authorization
   template, all `src/.../independent_audit/successor/**`,
   `src/.../quant/successor/**`, and the successor tests.

## Hash-bound identity (sha256 of audited files at `5148cd7`)

- `corporate_action_contract_sha256` =
  `d233aae7f1489d4d3d2ea854a6a2d0e8b473034a1ad4f31effcbdd126f9f1992`
  (`data/governance/successor/corporate-action-normalization-v2.json`)
- `successor_normalizer_sha256` =
  `bfbf0de5bdeb39af3535641570f3f9224f5301abb7db9fffc34c580481cace04`
  (`src/investment_tracker/quant/successor/corporate_actions_v2.py`)
- `successor_evaluator_sha256` =
  `c933cc2b71bf068f9db1f4656f7fea57ed3a5e0307819abc177897782e63e0ea`
  (`src/investment_tracker/independent_audit/successor/evaluate.py`)
- `holdout_exclusion_registry_sha256` =
  `4c376f86b5a0102c81008ef2c88401351b511df8ba3ba9f24ef381b7889152c6`
  (`data/governance/holdout-exclusion-registry.json`)

`load_methodology_authorization` validates the committed artifact against the
real files above and the predecessor closure: all hashes match, no
`SUCCESSOR_*_IDENTITY_MISMATCH` / `SUCCESSOR_PREDECESSOR_CLOSURE_MISMATCH`.

## Governance parameters and rationale

- `evaluation_calendar_start` = `2023-01-01`, `evaluation_calendar_end` =
  `2025-12-31`: a three-year out-of-sample research evaluation window.
- `required_pre_window_sessions` = `210`: lookback (189) + skip (21), enough
  to warm the survivor's signal at the window start.
- `selection_count` = `5`: matches the predecessor Phase-6 holdout cardinality.
- `listing_cutoff` = `2022-03-03`: strictly before window start; ensures
  ~10 months of listing history for the 210 pre-window sessions.
- `selection_seed_sha256` =
  `82fab8615a43e46bf0fae91f6c666ddd701f18f90c0b1224d42a2b41abfbbfc0`,
  derived as `sha256("INDEPENDENT_AUDIT_GENERATION_3_PHASE6_BLIND_HOLDOUT_SELECTION_v1")`
  for reproducibility.

## Consequences

The Stage-A authorization grants only: successor methodology and a one-time
blind virgin-holdout selection. It does NOT grant protected-history access,
does NOT authorize Phase 7, does NOT approve production readiness, and leaves
`RECON-009` OPEN.

No Stage-B acquisition authorization is created
(`SUCCESSOR-PHASE6-ACQUISITION-AUTHORIZATION-v1` is not issued).

## Next governance action

Coordinator may proceed with the Stage-A pipeline: seal the selection contract,
run the static-metadata + provider-quota query, apply the 23-symbol exclusion,
perform the deterministic blind selection, capture composite virginity, and
seal the Phase-6 evaluation contract. Stage-B acquisition remains gated on
that. Phase 7, production, and `RECON-009` closure remain out of scope.
