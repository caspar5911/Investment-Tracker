# Gate 3 Campaign Result Schema Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans sequentially with independent design and implementation reviews. User has authorized implementation on the exact current main checkpoint.

**Goal:** Seal the authoritative representation of candidate evidence before any real candidate execution.

**Architecture:** Add `quant.phase4.gate3_campaign`; reuse sealed evidence types and pure calculations. Validate records against exact authority objects, recompute projections, and publish immutable artifacts through a separate store. Expose only seal/preflight CLI commands.

**Tech Stack:** Python, Pydantic, pandas, existing canonical SHA-256/Git/artifact helpers, pytest.

**Spec:** `docs/superpowers/specs/2026-09-16-phase-4-gate-3-campaign-result-schema-design.md`

## Global constraints

- No edits to existing source, tests, frozen artifacts or the 14-file methodology bundle.
- No real candidate replay, validation metrics, ranking, selection, campaign orchestration, providers, protected symbols, holdout, trading or Phase 5.
- Exactly 180 sealed positions; exact policy artifacts and prior manifests from the spec.
- `QFQ_NORMALIZED`, `decision_grade=false`; drawdown/Calmar UNKNOWN; DSR/PBO UNKNOWN/NOT_IMPLEMENTED.
- Tests use artificial replays on frozen session labels; they never calculate real candidate performance.
- Every implementation task follows RED, minimal GREEN, focused/regression verification and its own commit. A fresh independent implementation review follows Task 3.

## Task 1: Strict typed representation, dependencies and projections

Create `src/investment_tracker/quant/phase4/gate3_campaign/{__init__,codec,result_schema,validation,dependencies}.py` and `tests/quant/test_phase4_gate3_campaign_result_schema.py`.

Interfaces: `load_dependencies(root)` loads exact authority/policy/binding metadata; `make_provenance(dependencies, position, source_revision)` returns typed identity/context; `derive_evidence(replays, benchmark, cash, neighbors, dependencies)` computes representations only; `validate_result(record, authority, resolver=None)` verifies the whole result and returns an exact typed record. `survivor_projection` returns AVAILABLE with existing `CandidateSurvivorEvidence` or UNKNOWN with reasons. `oos_outcome` uses existing Gate 1 outcome semantics. `canonical_result_bytes` and `decode_result` enforce strict canonical wire representation.

- [ ] Write tests for authority substitution, structural coercion and generic payload rejection; all 12 gates/22 keys, component tampering, unavailable metrics, status/OOS behavior, exact frozen folds/regimes/neighbors/bootstrap and replay accounting. For example:

```python
def test_turnover_cannot_override_fill_evidence(case):
    forged = case.result.model_copy(update={"evidence": case.evidence_with_zero_turnover})
    with pytest.raises(ValueError):
        api.validate_result(forged, case.authority)
```

- [ ] Run `pytest -o addopts='' -q tests/quant/test_phase4_gate3_campaign_result_schema.py`; demonstrate missing module/API RED.
- [ ] Implement extra-forbidden frozen types and strict recursive codec. Bind all identities to verified dependencies and source revision. Recompute sealed pure metrics/durability/fold/bootstrap/regime calculations and compare full evidence. Derive neighbors/projection/stop inputs; resolve skip references and reject unbound or system records. Add no executable strategy interface.
- [ ] Run focused suite and existing policy/preparation regressions; review against the spec.
- [ ] Commit `feat: add typed Gate 3 candidate result validation`.

## Task 2: Immutable result/schema artifact store

Create `gate3_campaign/result_artifacts.py` and `tests/quant/test_phase4_gate3_campaign_result_artifacts.py`.

Interfaces: `ResultArtifactStore(root).write_result(record, authority)` and `.read_result(identity, authority)` always validate complete typed records; store resolves prior stop evidence from exact references. `.write_authority(manifest)` and `.read_authority(content_sha256)` operate only on the fixed schema-authority subtree. Publication uses canonical bytes and existing envelope identity; hard-link no-overwrite commit, safe temp cleanup and redirect checks.

- [ ] Write tests catching overwrite, unequal collision, altered bytes/envelope/path, symlink/reparse/junction traversal, mutated nested model copies and missing skip references. Preserve preparation guard test:

```python
def test_preparation_record_still_cannot_execute(reference):
    with pytest.raises(ValueError, match="PREPARATION_ONLY"):
        TrialRecord.from_reference(reference, status="EXECUTED", reason="OK")
```

- [ ] Run the new file to demonstrate RED for missing store.
- [ ] Implement fixed-kind, fixed-path publication; validate before touching result destinations; identical bytes are idempotent. Decode/revalidate on reads. No caller-provided arbitrary authoritative dictionary API.
- [ ] Run Tasks 1/2 tests and old Gate 3 artifact tests; commit `feat: add immutable Gate 3 result artifacts`.

## Task 3: Result-schema seal and nonexecuting CLI

Create `gate3_campaign/result_methodology.py`, `gate3_campaign/cli.py`, and `tests/quant/test_phase4_gate3_campaign_result_methodology.py`.

Interfaces: `seal_result_schema(root, source_revision) -> ArtifactIdentity`; `preflight_result_schema(root, manifest_content_sha256) -> ResultSchemaPreflight`; `load_result_authority(root, manifest_content_sha256)` supplies the exact validation authority. Schema/source/spec/policy identity is explicit and pinned. Source guard verifies current imported/worktree files against Git blobs and forbids cross-worktree execution. Authority model has strict safety facts and schema/identity algorithm versions.

- [ ] Write tests for missing/wrong explicit hash, source/spec/dependency/policy substitutions, dirty/imported-source mismatch, no candidate-file read, no campaign CLI, and exact old preparation guard.
- [ ] Run tests to demonstrate RED for missing seal/preflight implementation.
- [ ] Implement preflight dependency reuse, semantic authority rederivation, source-byte verification, and final-only authority publication. Avoid circular self-hashes; result source revision is schema implementation revision, separate from future campaign producing revision.
- [ ] Run focused/old Gate 3/Phase 4 regressions; commit `feat: seal additive Gate 3 result schema authority`.

## Task 4: Independent review, verification and evidence-only seal

- [ ] Fresh read-only reviewer assesses all new source against specification/request and confirms zero Critical/Important. Any repair gets a failing regression test before the fix and a separate commit/review.
- [ ] Run `pytest -o addopts='' -q tests/quant/test_phase4_gate3_campaign_result_*.py` through explicit PowerShell file enumeration, all Gate 3 tests, all Phase 4 tests, and `pytest -o addopts='' -q tests/quant`; record exact counts. Do not skip or weaken security tests.
- [ ] Run both existing explicit-hash preflights, then seal using the reviewed full implementation commit:

```powershell
python -m investment_tracker.quant.phase4.gate3_campaign.cli seal --repository-root . --source-revision <reviewed-full-commit>
python -m investment_tracker.quant.phase4.gate3_campaign.cli preflight --repository-root . --manifest-content-sha256 <returned-exact-content-digest>
```

- [ ] Independently verify the new exact-byte content/envelope/source/policy identities and absence of candidate artifacts. Commit only `results/phase4/gate3/campaign_result_schema/` evidence as `evidence: seal pre-campaign Gate 3 result schema`.
- [ ] Rerun all three preflights and verify clean main. Report required identities, commits, tests, review and safety facts; STOP at `GATE3_CAMPAIGN_RESULT_SCHEMA_SEALED`.
