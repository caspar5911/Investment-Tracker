# Phase 4 Readiness Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and execute a bounded, provider-free Phase 4 readiness audit that reproduces the pinned Phase 2 bootstrap evidence, freezes exactly 136 authoritative historical trial identities, and emits immutable Phase 4 split and campaign-configuration evidence without beginning strategy research.

**Architecture:** Add an isolated `investment_tracker.quant.readiness` package with explicit frozen inputs, strict evidence models, canonical identity functions, deterministic Phase 2 representation admission, pinned bootstrap reconstruction, validation warm-up/reset contracts, provider-free Phase 3 dataset verification, immutable artifact storage, and a readiness-only orchestrator. Reuse frozen replay and calculation functions only as read-only dependencies; do not modify the backtest, calculation, robustness, experiment, promotion, Phase 3 universe, provider, or cache implementations.

**Tech Stack:** Python 3.12, Pydantic 2, pandas, NumPy, pyarrow, pytest, standard-library SHA-256 and JSON.

**Spec:** `docs/superpowers/specs/2026-09-12-phase-4-readiness-audit-design.md`

## Global Constraints

- Preserve TPC-v1.2, REPLAY-v1.0, CALC-v1.2, and ROBUST-v1.0 unchanged.
- Preserve every existing Phase 2 and Phase 3 artifact byte-for-byte.
- Keep `FINAL_HOLDOUT` sealed and deny `HACK`, `SOXX`, `NLR`, `URNM`, and `GEV` before symbol-specific access.
- Make no provider calls, downloads, external strategy searches, strategy evaluations, parameter searches, promotions, or canonical tracker writes.
- Do not introduce provider factories, Moomoo imports, brokerage contexts, account queries, position queries, funds queries, order APIs, or live-trading paths.
- Treat QFQ as normalized research simulation only and freeze `decision_grade: false`.
- Treat the 136 Phase 2 trials as historical multiplicity evidence only. Phase 4 starts at zero new trials and has an independent aggregate ceiling of 3,000.
- Observations strictly earlier than the first VALIDATION session may initialize lagged indicators only. Validation execution and accounting start from fresh initial cash, zero positions, and zero pending orders.
- Mark DSR and PBO `UNKNOWN/NOT_IMPLEMENTED`; do not approximate either statistic.
- Preserve `[0.0, 0.0]` only as evidence about the implemented median-daily-return bootstrap statistic.
- Do not weaken, skip, or alter the existing Windows symlink test. If it remains un-runnable because the process lacks symlink privilege, report that exact environment limitation.
- Finish at `PHASE_4_READY` or an explicit fail-closed readiness status. Do not start Phase 4 strategy discovery.

## Frozen Input Map

The implementation must name these inputs directly in `readiness/constants.py`; no latest-file, directory-order, timestamp, or fallback discovery is permitted.

| Input | Frozen identity |
|---|---|
| Phase 2 campaign | `PHASE2-CORRECTED-2010-2022-c33fb075` |
| Preliminary Phase 2 revision | `d4b2dfc3bee03ad81e389cc2e21876f38fbf325f` |
| Final Phase 2 revision | `c33fb0757f0ea8147749130fed90d278aed4fafe` |
| Pinned bootstrap source path | `results/experiments/risk_managed_trend-ee8a71fb71e3d80f-20260911T194002253141Z-bcabf074.json` |
| Pinned bootstrap source byte hash | `438dda42ceacece3c7d3b73512d9898017a4c180e1b368cdc7c6dee299f5d4b5` |
| Pinned bootstrap source artifact identity | `3e72fc05aa1c5d9e0ceca4a935ebb6672cd068d4bdf67b16c5d4fbbb121a797e` |
| Bootstrap vector digest | `878b8400fcf93776feda23c454182d36dca5efd4c32f51d2aa232abf003bf0b5` |
| Phase 3 universe manifest | `results/phase3/universes/de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76/manifest.json` |
| Phase 3 DQ snapshot | `results/phase3/campaigns/PHASE3-ETF-DQ-2014-2022-20260912T0254Z/dq-snapshots/2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75.json` |

The three Phase 2 cache datasets used by the pinned bootstrap source are exact paths, not requests resolved through `ImmutableParquetCache.find()`:

```text
data/cache/moomoo/QQQ/1d/qfq/2010-01-01_2022-12-31/20260911T150943331113Z_3d28b4a98e049170f32db942751632a5a822807200dfb3daa90b07eea17d943f
data/cache/moomoo/TLT/1d/qfq/2010-01-01_2022-12-31/20260911T150945375035Z_56aed15476392a2b351d01096b94a7c34432552f383d994dc03ae8a1fb4aea34
data/cache/moomoo/IEF/1d/qfq/2010-01-01_2022-12-31/20260911T150945612969Z_fa0c89127c6cab2901a7a3a8bb8ed99b23aca4d24e2d42517fe295fb810b1bc9
```

The Phase 3 symbol order is `SPY`, `QQQ`, `IWM`, `TLT`, `IEF`, `GLD`, `VNQ`, `XLP`. Each exact normalized dataset directory is `data/cache/phase3/normalized/sha256/<frozen dataset hash>` using the eight hashes in the specification.

## File Structure

- Create `src/investment_tracker/quant/readiness/__init__.py`: readiness-only public API.
- Create `src/investment_tracker/quant/readiness/constants.py`: all frozen IDs, paths, hashes, split dates, versions, and budget limits.
- Create `src/investment_tracker/quant/readiness/models.py`: frozen extra-forbid identity, trial, bootstrap, split, configuration, statistic, and readiness contracts.
- Create `src/investment_tracker/quant/readiness/hashing.py`: canonical JSON, repository-path normalization, exact-byte hashes, trial identity, artifact identity, and vector identity.
- Create `src/investment_tracker/quant/readiness/artifacts.py`: write-once/readback-verified readiness storage.
- Create `src/investment_tracker/quant/readiness/trials.py`: deterministic Phase 2 representation classification and authority construction.
- Create `src/investment_tracker/quant/readiness/statistics.py`: deduplicated search-aware inputs and explicit unimplemented results.
- Create `src/investment_tracker/quant/readiness/bootstrap_audit.py`: pinned cache-only reconstruction and narrow-statistic audit.
- Create `src/investment_tracker/quant/readiness/validation.py`: TRAIN warm-up and VALIDATION reset/input boundary.
- Create `src/investment_tracker/quant/readiness/split.py`: provider-free Phase 3 dependency verification and split/config construction.
- Create `src/investment_tracker/quant/readiness/report.py`: bounded readiness report rendering.
- Create `src/investment_tracker/quant/readiness/campaign.py`: readiness orchestration and safety checks.
- Modify `src/investment_tracker/quant/cli.py`: add a fixed-input `phase4-readiness` command only.
- Create focused tests under `tests/quant/` without modifying existing symlink or frozen-engine tests.

---

### Task 1: Freeze Readiness Contracts and Both Identity Domains

**Files:**
- Create: `src/investment_tracker/quant/readiness/__init__.py`
- Create: `src/investment_tracker/quant/readiness/constants.py`
- Create: `src/investment_tracker/quant/readiness/models.py`
- Create: `src/investment_tracker/quant/readiness/hashing.py`
- Test: `tests/quant/test_phase4_readiness_contracts.py`

**Interfaces:**
- Produce `canonical_json_bytes(value: object) -> bytes` and `canonical_sha256(value: object) -> str`.
- Produce `normalize_repository_path(repository_root: Path, path: Path) -> str`.
- Produce `exact_file_sha256(path: Path) -> str`.
- Produce `trial_identity(campaign_id: str, candidate_id: str) -> str`.
- Produce `artifact_identity(repository_root: Path, path: Path, kind: ArtifactKind) -> ReadinessArtifactIdentity`.
- Produce frozen Pydantic models using `ConfigDict(extra="forbid", frozen=True)`.

- [ ] **Step 1: Write failing canonical identity tests**

```python
def test_trial_identity_has_only_campaign_and_candidate_domains():
    expected = canonical_sha256(
        {
            "campaign_id": "PHASE2-CORRECTED-2010-2022-c33fb075",
            "candidate_id": "risk_managed_trend-ee8a71fb71e3d80f",
        }
    )
    assert trial_identity(PHASE2_CAMPAIGN_ID, "risk_managed_trend-ee8a71fb71e3d80f") == expected


def test_artifact_identity_hashes_exact_bytes_kind_and_normalized_path(tmp_path):
    repository = tmp_path / "repo"
    artifact = repository / "results" / "record.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b'{"value":1}\n')
    identity = artifact_identity(repository, artifact, "phase2_experiment")
    envelope = {
        "content_sha256": sha256(b'{"value":1}\n').hexdigest(),
        "kind": "phase2_experiment",
        "path": "results/record.json",
    }
    assert identity.content_sha256 == envelope["content_sha256"]
    assert identity.path == "results/record.json"
    assert identity.sha256 == canonical_sha256(envelope)


def test_trial_and_artifact_identity_are_not_interchangeable(tmp_path):
    identity = make_artifact_identity(tmp_path)
    with pytest.raises(ValidationError):
        AuthoritativeTrial(
            trial_id=identity.sha256,
            campaign_id=PHASE2_CAMPAIGN_ID,
            candidate_id="candidate-a",
            authoritative_artifact=identity,
            non_authoritative_artifacts=(),
        )


@pytest.mark.parametrize(
    "unsafe",
    [Path("../escape.json"), Path("/absolute.json"), Path("a/../b.json")],
)
def test_artifact_paths_reject_non_repository_relative_forms(tmp_path, unsafe):
    with pytest.raises(ArtifactIdentityError):
        normalize_repository_path(tmp_path, unsafe)
```

On platforms where symlinks can be created, add a focused identity-path test proving that a symlinked component is rejected. This is additional coverage and must not alter the existing repository symlink test.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/quant/test_phase4_readiness_contracts.py -q`

Expected: collection failure because `investment_tracker.quant.readiness` does not exist.

- [ ] **Step 3: Implement frozen constants and identity primitives**

Use one controlled `ArtifactKind` literal union. Include versioned kinds for the Phase 2 source, Phase 3 inputs, bootstrap vector/audit, trial authority, split manifest, campaign configuration, readiness manifest, and report.

```python
def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def trial_identity(campaign_id: str, candidate_id: str) -> str:
    return canonical_sha256(
        {"campaign_id": campaign_id, "candidate_id": candidate_id}
    )


def artifact_identity(
    repository_root: Path,
    path: Path,
    kind: ArtifactKind,
) -> ReadinessArtifactIdentity:
    normalized = normalize_repository_path(repository_root, path)
    content_sha256 = exact_file_sha256(path)
    envelope = {
        "content_sha256": content_sha256,
        "kind": kind,
        "path": normalized,
    }
    return ReadinessArtifactIdentity(
        **envelope,
        sha256=canonical_sha256(envelope),
    )
```

`normalize_repository_path` may receive either an absolute path under the repository root or a root-relative path. It must emit only a normalized repository-relative path, reject inputs that resolve outside the repository root, and reject an emitted path with a drive prefix, leading slash, empty, `.` or `..` component, or any existing symlink component. It emits `/` separators on all operating systems. Exact-byte hashing must stream bytes and must never parse or normalize file content.

Model validators must recompute trial identities and artifact-envelope identities. They must distinguish `content_sha256` from `sha256`, where `sha256` is the canonical envelope digest.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase4_readiness_contracts.py -q`

- [ ] **Step 5: Commit contracts and identity domains**

```powershell
git add -- src/investment_tracker/quant/readiness tests/quant/test_phase4_readiness_contracts.py
git commit -m "feat: freeze phase 4 readiness identities"
```

### Task 2: Add Immutable Exact-Byte Readiness Storage

**Files:**
- Create: `src/investment_tracker/quant/readiness/artifacts.py`
- Test: `tests/quant/test_phase4_readiness_artifacts.py`

**Interfaces:**
- Produce `ReadinessArtifactStore(repository_root: Path, results_root: Path)`.
- Produce `write_json(kind, filename, payload) -> ReadinessArtifactIdentity`.
- Produce `write_text(kind, filename, text) -> ReadinessArtifactIdentity`.
- Produce `read_json(identity) -> object` and `read_text(identity) -> str`.
- Produce `verify(identity) -> Path`.

- [ ] **Step 1: Write failing storage tests**

```python
def test_store_uses_exact_content_hash_path_and_envelope_identity(tmp_path):
    store = readiness_store(tmp_path)
    identity = store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
    assert identity.path == (
        f"results/phase4/readiness/phase4_split_manifest/sha256/"
        f"{identity.content_sha256}/manifest.json"
    )
    assert identity.sha256 == canonical_sha256(
        {
            "content_sha256": identity.content_sha256,
            "kind": identity.kind,
            "path": identity.path,
        }
    )
    assert store.read_json(identity) == {"a": 1}


def test_store_reuses_only_exactly_identical_bytes(tmp_path):
    store = readiness_store(tmp_path)
    first = store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
    second = store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})
    assert first == second
    Path(tmp_path, first.path).write_bytes(b"tampered")
    with pytest.raises(ReadinessArtifactIntegrityError):
        store.write_json("phase4_split_manifest", "manifest.json", {"a": 1})


def test_store_rejects_filename_traversal_and_symlinked_output_parent(tmp_path):
    store = readiness_store(tmp_path)
    with pytest.raises(ReadinessArtifactIntegrityError):
        store.write_json("phase4_split_manifest", "../manifest.json", {"a": 1})
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/quant/test_phase4_readiness_artifacts.py -q`

- [ ] **Step 3: Implement atomic write-once storage**

Canonical JSON output bytes come directly from `canonical_json_bytes`. The output layout is:

```text
results/phase4/readiness/<kind>/sha256/<content_sha256>/<filename>
```

Naming the directory by `content_sha256` avoids a circular definition: artifact identity contains the final path, while the path does not contain the artifact-envelope digest. Create temporary files in the verified destination parent, flush and close them, move atomically, compute identity from the final bytes and final normalized path, and read back. An existing exact path is reusable only when its bytes are identical. A byte mismatch, kind mismatch, traversal, non-regular file, or symlink is fatal.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase4_readiness_artifacts.py -q`

- [ ] **Step 5: Commit readiness storage**

```powershell
git add -- src/investment_tracker/quant/readiness/artifacts.py tests/quant/test_phase4_readiness_artifacts.py
git commit -m "feat: add immutable phase 4 readiness storage"
```

### Task 3: Freeze Exactly 136 Historical Phase 2 Trials

**Files:**
- Create: `src/investment_tracker/quant/readiness/trials.py`
- Create: `src/investment_tracker/quant/readiness/statistics.py`
- Test: `tests/quant/test_phase4_trial_authority.py`

**Interfaces:**
- Produce `classify_representation(record: ExperimentRecord) -> RepresentationClass`.
- Produce `build_trial_authority(repository_root: Path, experiments_root: Path) -> TrialAuthorityManifest`.
- Produce `build_search_aware_inputs(authority: TrialAuthorityManifest, records: Mapping[str, ExperimentRecord]) -> SearchAwareInputSet`.
- Produce `unimplemented_search_statistic(name: Literal["DSR", "PBO"], reason: str) -> SearchAwareStatisticResult`.
- Produce `Phase4BudgetState.consume(candidate_id: str) -> Phase4BudgetState` for contract testing only; readiness does not call it.

- [ ] **Step 1: Write failing deterministic-admission tests**

```python
def test_phase2_preserved_evidence_yields_exactly_136_authoritative_trials(repo_root):
    authority = build_trial_authority(repo_root, repo_root / "results/experiments")
    assert authority.historical_phase2_trial_count == 136
    assert len(authority.trials) == 136
    assert len({trial.trial_id for trial in authority.trials}) == 136
    assert all(
        trial.authoritative_artifact.sha256 != trial.trial_id
        for trial in authority.trials
    )


def test_admission_is_independent_of_path_timestamp_and_input_order(experiment_fixtures):
    forward = build_authority_from_records(experiment_fixtures)
    reverse = build_authority_from_records(tuple(reversed(experiment_fixtures)))
    renamed = rename_fixture_paths_and_times(experiment_fixtures)
    assert forward.trials == reverse.trials
    assert tuple(item.trial_id for item in forward.trials) == tuple(
        item.trial_id for item in build_authority_from_records(renamed).trials
    )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unexpected", "ambiguous"])
def test_invalid_authoritative_populations_fail_closed(experiment_fixtures, mutation):
    with pytest.raises(TrialAuthorityError):
        build_authority_from_records(mutate_population(experiment_fixtures, mutation))


def test_duplicate_representations_do_not_inflate_search_inputs(authority_fixture):
    base = build_search_aware_inputs(*authority_fixture)
    duplicated = build_search_aware_inputs(*with_non_authoritative_duplicates(authority_fixture))
    assert duplicated.historical_trial_count == base.historical_trial_count == 136
    assert duplicated.multiple_testing_count == base.multiple_testing_count == 136
    assert duplicated.ordered_sharpe_trial_ids == base.ordered_sharpe_trial_ids
    assert duplicated.ordered_pbo_trial_ids == base.ordered_pbo_trial_ids


def test_phase4_budget_starts_at_zero_and_first_trial_is_position_one():
    state = Phase4BudgetState.initial()
    assert state.historical_phase2_trial_count == 136
    assert state.phase4_new_trials_consumed == 0
    assert state.phase4_new_trials_remaining == 3000
    assert state.phase4_historical_trials_consume_budget is False
    first = state.consume("phase4-candidate-0001")
    assert first.phase4_new_trials_consumed == 1
    assert first.last_consumed_budget_position == 1


def test_unimplemented_search_statistics_never_return_a_number():
    for name in ("DSR", "PBO"):
        result = unimplemented_search_statistic(name, "ESTIMATOR_NOT_IMPLEMENTED")
        assert result.status == "NOT_IMPLEMENTED"
        assert result.interpretation == "UNKNOWN"
        assert result.value is None
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/quant/test_phase4_trial_authority.py -q`

- [ ] **Step 3: Implement deterministic classification and authority construction**

Read every `results/experiments/*.json` byte, derive its canonical artifact identity, validate it as `ExperimentRecord`, and rely on the embedded manifest validator to verify its digest. Classify with explicit predicates:

- `ORIGINAL`: engine `QUANT-ENGINE-v1`.
- `PRELIMINARY_CORRECTED`: preliminary revision, corrected engine, correct schemas, and no `loss_rate` in validation metrics.
- `FINAL_AUTHORITATIVE`: final revision, corrected engine, correct schemas, and `loss_rate` present in validation metrics.
- `OUT_OF_SCOPE`: valid historical representation outside those predicates.
- `AMBIGUOUS`: more than one class predicate matched; fail immediately.

Do not inspect `created_at`, `recorded_at`, filename, directory enumeration position, or modification time in selection. Build the expected candidate set from preliminary corrected records, require exactly 136, require equality with the final set, and require one final record per candidate. Sort output only by canonical `candidate_id` after admission. Record all non-authoritative representation identities for lineage.

`build_search_aware_inputs` accepts authority as the row authority and joins numeric fields by `trial_id`; raw artifact rows can never become additional observations. PBO inputs remain keyed placeholders because no compatible trial-by-fold return matrix is implemented. DSR/PBO requests always return the explicit nonnumeric fail-closed model.

Keep budget state separate from historical trial authority. Its validators enforce maximum families 10, maximum per family 500, maximum aggregate 3,000, unique Phase 4 candidate IDs, and no historical IDs. No combined budget count field may exist.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase4_trial_authority.py -q`

- [ ] **Step 5: Commit trial authority and search boundaries**

```powershell
git add -- src/investment_tracker/quant/readiness/trials.py src/investment_tracker/quant/readiness/statistics.py tests/quant/test_phase4_trial_authority.py
git commit -m "feat: freeze authoritative phase 2 trials"
```

### Task 4: Reproduce the Pinned 1,007-Return Bootstrap Vector

**Files:**
- Create: `src/investment_tracker/quant/readiness/bootstrap_audit.py`
- Test: `tests/quant/test_phase4_bootstrap_audit.py`

**Interfaces:**
- Produce `load_pinned_bootstrap_source(repository_root: Path) -> PinnedBootstrapSource`.
- Produce `reconstruct_bootstrap_vector(repository_root: Path, source: PinnedBootstrapSource) -> BootstrapInputVector`.
- Produce `audit_bootstrap_vector(vector: BootstrapInputVector, source: PinnedBootstrapSource) -> BootstrapAudit`.

- [ ] **Step 1: Write failing pinned-evidence tests**

```python
def test_pinned_source_has_exact_byte_and_envelope_identity(repo_root):
    source = load_pinned_bootstrap_source(repo_root)
    assert source.artifact.content_sha256 == PINNED_BOOTSTRAP_SOURCE_CONTENT_SHA256
    assert source.artifact.sha256 == PINNED_BOOTSTRAP_SOURCE_ARTIFACT_SHA256
    assert source.record.candidate_manifest.digest == PINNED_CANDIDATE_MANIFEST_SHA256


def test_reconstructed_vector_matches_frozen_1007_value_digest(repo_root):
    source = load_pinned_bootstrap_source(repo_root)
    vector = reconstruct_bootstrap_vector(repo_root, source)
    assert vector.schema_version == "BOOTSTRAP-INPUT-VECTOR-v1"
    assert vector.dtype == "IEEE-754-binary64"
    assert len(vector.values_hex) == 1007
    assert vector.negative_count == 288
    assert vector.zero_count == 368
    assert vector.positive_count == 351
    assert vector.sha256 == PINNED_BOOTSTRAP_VECTOR_SHA256


def test_audit_reproduces_all_zero_medians_and_point_interval(repo_root):
    source = load_pinned_bootstrap_source(repo_root)
    vector = reconstruct_bootstrap_vector(repo_root, source)
    audit = audit_bootstrap_vector(vector, source)
    assert audit.draws == 2000
    assert audit.seed == 0
    assert audit.zero_resampled_medians == 2000
    assert audit.interval == (0.0, 0.0)
    assert audit.claim_scope == "MEDIAN_DAILY_EQUAL_WEIGHT_PORTFOLIO_RETURN_ONLY"
    assert audit.decision_grade is False


@pytest.mark.parametrize("failure", ["source_bytes", "manifest", "dataset", "vector"])
def test_pinned_bootstrap_mismatch_fails_without_fixture_fallback(repo_root, failure):
    with pytest.raises(BootstrapEvidenceError):
        run_with_pinned_evidence_mutation(repo_root, failure)
```

Add direct regression cases for sparse observations, non-finite observations, fewer than 100 draws, invalid percentile bounds, and full-precision JSON serialization. Reuse the frozen `bootstrap_interval` in those tests; do not edit it.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/quant/test_phase4_bootstrap_audit.py -q`

- [ ] **Step 3: Implement exact source verification and cache-only reconstruction**

Verify the pinned experiment's exact bytes and canonical envelope before parsing it. Validate the record, manifest digest, candidate ID, strategy family and parameters, three data manifest hashes, split, fee/slippage assumptions, execution convention, and stored interval.

For each of QQQ, TLT, and IEF, open the exact frozen cache directory from `constants.py`, validate `metadata.json`, hash the Parquet-loaded normalized frame with the existing `content_hash`, and require equality with both the cache metadata and the source manifest. Do not call `ImmutableParquetCache.find()` because it performs newest-by-time selection.

Build the strategy from the exact embedded family and parameters. Slice the exact embedded VALIDATION period, run the unchanged `run_backtest` independently from fresh initial cash for each symbol, combine the equity curves with unchanged `aggregate_equal_weight`, and compute `pct_change(fill_method=None).dropna()`. Convert each ordered Python float to `float.hex()` and build exactly:

```python
{
    "dtype": "IEEE-754-binary64",
    "schema_version": "BOOTSTRAP-INPUT-VECTOR-v1",
    "values_hex": [value.hex() for value in ordered_returns],
}
```

The vector `sha256` is the canonical SHA-256 of only that payload. Counts and source identities are surrounding evidence fields and are not part of the frozen vector digest. Reject non-finite values and any mismatch in count, sign counts, or vector digest.

Decode the verified vector with `float.fromhex`, call unchanged `bootstrap_interval` with 2,000 draws, seed 0, and 5th/95th percentiles, and separately reproduce all resampled medians using the same NumPy operations solely to record that all 2,000 equal zero. Require the computed interval to equal the source's stored validation fields without display rounding. The model permits only the narrow claim scope shown in the test.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase4_bootstrap_audit.py -q`

- [ ] **Step 5: Commit the pinned bootstrap audit**

```powershell
git add -- src/investment_tracker/quant/readiness/bootstrap_audit.py tests/quant/test_phase4_bootstrap_audit.py
git commit -m "feat: reproduce pinned phase 2 bootstrap evidence"
```

### Task 5: Freeze Validation Warm-Up and Portfolio Reset Semantics

**Files:**
- Create: `src/investment_tracker/quant/readiness/validation.py`
- Test: `tests/quant/test_phase4_validation_boundary.py`

**Interfaces:**
- Produce `ValidationWarmupPolicy` and `ValidationResetState` models.
- Produce `prepare_validation_inputs(bars, target_builder, split, warmup_sessions, initial_cash) -> ValidationExecutionInputs`.
- Produce `run_validation_from_reset(inputs, assumptions) -> BacktestResult` as a thin call into unchanged `run_backtest`.

- [ ] **Step 1: Write failing boundary tests**

```python
def test_train_rows_are_visible_only_to_lagged_indicator_initialization():
    inputs = prepare_validation_inputs(
        bars=bars_fixture(),
        target_builder=rolling_target_builder(window=3),
        split=split_fixture(),
        warmup_sessions=2,
        initial_cash=100_000.0,
    )
    assert tuple(inputs.indicator_warmup.index) == tuple(train_index()[-2:])
    assert tuple(inputs.execution_bars.index) == tuple(validation_index())
    assert tuple(inputs.scored_targets.index) == tuple(validation_index())
    assert inputs.selection_inputs == ()


def test_prices_before_declared_causal_warmup_cannot_change_validation_result():
    original = prepare_fixture_inputs()
    mutated = prepare_fixture_inputs(mutate_train_before_warmup=True)
    assert original.scored_targets.equals(mutated.scored_targets)
    assert original.reset_state == mutated.reset_state


def test_validation_portfolio_resets_and_contains_no_train_pnl():
    result = run_validation_from_reset(prepare_fixture_inputs(), assumptions())
    assert result.equity_curve.iloc[0] == assumptions().initial_capital
    assert result.cash_curve.iloc[0] == assumptions().initial_capital
    assert result.position_curve.iloc[0] == 0.0
    assert all(fill.timestamp in validation_index() for fill in result.fills)
    assert result.fills[0].timestamp == validation_index()[1]


def test_first_scored_signal_is_validation_dated_and_executes_next_validation_session():
    inputs = prepare_fixture_inputs(first_validation_target=1.0)
    assert inputs.scored_targets.index[0] == validation_index()[0]
    result = run_validation_from_reset(inputs, assumptions())
    assert result.fills[0].timestamp == validation_index()[1]


def test_last_validation_signal_without_next_session_does_not_execute():
    inputs = prepare_fixture_inputs(last_validation_target=1.0)
    result = run_validation_from_reset(inputs, assumptions())
    assert not any(fill.timestamp > validation_index()[-1] for fill in result.fills)
```

Add rejection tests for a target builder that exposes fit/calibrate/select methods, TRAIN-dated scored targets, warm-up derived from a performance field, inherited positions/cash/cost basis/pending orders, and validation metrics containing TRAIN returns.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/quant/test_phase4_validation_boundary.py -q`

- [ ] **Step 3: Implement the validation-only input adapter**

`prepare_validation_inputs` accepts an explicitly predeclared nonnegative `warmup_sessions`. It slices only that many sessions immediately preceding the first actual VALIDATION session, joins those rows to VALIDATION solely while calling the pure target builder, then discards every pre-VALIDATION target. It returns:

- the read-only warm-up frame;
- VALIDATION-only execution bars;
- VALIDATION-indexed scored targets;
- `ValidationResetState(initial_cash, positions={}, pending_orders=(), turnover=0.0, realized_pnl=0.0, cost_basis={})`; and
- an empty, typed `selection_inputs` tuple.

The adapter must not accept training metrics, fitting callbacks, candidate selectors, inherited ledgers, or portfolio state. A protocol exposes only `__call__(bars: pd.DataFrame) -> pd.Series`. The first scored target is on an actual VALIDATION row. Passing the VALIDATION-only bars and targets to unchanged `run_backtest` preserves next-session execution and guarantees there is no execution after the last validation row.

This task freezes and tests semantics only. Do not run any historical candidate or add these helpers to the current Phase 2 workflow.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase4_validation_boundary.py -q`

- [ ] **Step 5: Commit validation-boundary contracts**

```powershell
git add -- src/investment_tracker/quant/readiness/validation.py tests/quant/test_phase4_validation_boundary.py
git commit -m "feat: freeze phase 4 validation reset semantics"
```

### Task 6: Build Provider-Free Split and Campaign Configuration Manifests

**Files:**
- Create: `src/investment_tracker/quant/readiness/split.py`
- Test: `tests/quant/test_phase4_split_and_config.py`

**Interfaces:**
- Produce `verify_phase3_dependencies(repository_root: Path) -> VerifiedPhase3Inputs`.
- Produce `build_split_manifest(inputs: VerifiedPhase3Inputs) -> Phase4SplitManifest`.
- Produce `build_campaign_configuration(split: ReadinessArtifactIdentity) -> Phase4CampaignConfiguration`.

- [ ] **Step 1: Write failing dependency and split tests**

```python
def test_split_uses_only_frozen_phase3_inputs_and_exact_symbol_order(repo_root):
    verified = verify_phase3_dependencies(repo_root)
    split = build_split_manifest(verified)
    assert split.symbols == ("SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP")
    assert split.phase3_universe_digest == PHASE3_UNIVERSE_SHA256
    assert split.phase3_dq_snapshot_digest == PHASE3_DQ_SNAPSHOT_SHA256
    assert split.provider_calls == 0
    assert split.final_holdout_accessed is False


def test_every_symbol_has_exact_declared_and_actual_partitions(repo_root):
    split = build_split_manifest(verify_phase3_dependencies(repo_root))
    for partition in split.partitions:
        assert partition.train.declared_start.isoformat() == "2014-01-02"
        assert partition.train.actual_start.isoformat() == "2014-01-02"
        assert partition.train.actual_end.isoformat() == "2018-12-31"
        assert partition.train.row_count == 1258
        assert partition.validation.declared_start.isoformat() == "2019-01-01"
        assert partition.validation.actual_start.isoformat() == "2019-01-02"
        assert partition.validation.actual_end.isoformat() == "2022-12-30"
        assert partition.validation.row_count == 1008
        assert set(partition.train.sessions).isdisjoint(partition.validation.sessions)


def test_configuration_separates_historical_trials_from_new_budget(split_identity):
    config = build_campaign_configuration(split_identity)
    assert config.maximum_new_strategy_families == 10
    assert config.maximum_candidate_trials_per_family == 500
    assert config.maximum_aggregate_new_candidate_trials == 3000
    assert config.historical_phase2_trial_count == 136
    assert config.phase4_new_trials_consumed == 0
    assert config.phase4_new_trials_remaining == 3000
    assert config.phase4_historical_trials_consume_budget is False
    assert config.decision_grade is False


def test_dependency_mismatch_fails_without_discovery_or_provider_fallback(repo_root):
    with pytest.raises(Phase3DependencyError):
        verify_phase3_dependencies(copy_with_tampered_dataset(repo_root))
```

Add cases for universe-path mismatch, DQ snapshot mismatch, selected-symbol order mismatch, missing or extra dataset dependency, content hash mismatch, wrong session boundary/count, missing admitted session, duplicate session, QFQ flag change, and any protected symbol.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/quant/test_phase4_split_and_config.py -q`

- [ ] **Step 3: Implement exact local verification and manifest builders**

Open only the exact universe and DQ paths in `constants.py`. Verify their existing canonical digests according to the Phase 3 format, derive new exact-byte canonical artifact identities for lineage, and require the universe manifest's DQ reference, selected order, decision-grade flag, provider/bar-repair counts, and eight dataset identities to match the specification.

For each exact normalized dataset directory, verify `metadata.json`, load `bars.parquet`, recompute existing Phase 3 `content_hash`, require the frozen digest, and require the index to be unique, increasing, and exactly equal across all eight admitted datasets. Partition locally by calendar boundaries. Record declared dates, actual dates, row counts, and session digests; never construct a data source or repository.

The campaign configuration requires a written split artifact identity as input and freezes:

```python
{
    "historical_phase2_trial_count": 136,
    "phase4_new_trials_consumed": 0,
    "phase4_new_trials_remaining": 3000,
    "phase4_historical_trials_consume_budget": False,
    "maximum_new_strategy_families": 10,
    "maximum_candidate_trials_per_family": 500,
    "maximum_aggregate_new_candidate_trials": 3000,
    "signal_series": "QFQ",
    "execution_series": "QFQ_NORMALIZED",
    "decision_grade": False,
    "provider_calls": 0,
    "external_strategy_research_performed": False,
    "strategy_search_executed": False,
    "final_holdout_accessed": False,
    "protected_symbols_accessed": [],
    "live_trading_capability": False,
}
```

Pydantic validators must reject an aggregate budget inferred as 136 plus 3,000 and reject any initial consumed count other than zero.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase4_split_and_config.py -q`

- [ ] **Step 5: Commit provider-free split and configuration builders**

```powershell
git add -- src/investment_tracker/quant/readiness/split.py tests/quant/test_phase4_split_and_config.py
git commit -m "feat: freeze provider-free phase 4 manifests"
```

### Task 7: Orchestrate the Readiness Audit and Render the Report

**Files:**
- Create: `src/investment_tracker/quant/readiness/report.py`
- Create: `src/investment_tracker/quant/readiness/campaign.py`
- Modify: `src/investment_tracker/quant/readiness/__init__.py`
- Modify: `src/investment_tracker/quant/cli.py`
- Test: `tests/quant/test_phase4_readiness_campaign.py`
- Test: `tests/quant/test_phase4_readiness_cli.py`

**Interfaces:**
- Produce `run_phase4_readiness(repository_root: Path, results_root: Path) -> Phase4ReadinessOutcome`.
- Produce `render_readiness_report(summary: Phase4ReadinessSummary) -> str`.
- Add CLI command `phase4-readiness --repository-root <path> --results-root <path>`.

- [ ] **Step 1: Write failing orchestration and CLI tests**

```python
def test_readiness_campaign_writes_complete_linked_evidence(provider_free_repo):
    outcome = run_phase4_readiness(
        provider_free_repo.root,
        provider_free_repo.root / "results",
    )
    assert outcome.status == "PHASE_4_READY"
    assert outcome.manifest is not None
    manifest = provider_free_repo.store.read_json(outcome.manifest)
    assert manifest["historical_phase2_trial_count"] == 136
    assert manifest["phase4_new_trials_consumed"] == 0
    assert manifest["bootstrap_audit"]["sha256"]
    assert manifest["bootstrap_input_vector"]["sha256"]
    assert manifest["trial_authority"]["sha256"]
    assert manifest["split_manifest"]["sha256"]
    assert manifest["campaign_configuration"]["sha256"]


def test_fail_closed_campaign_does_not_write_ready_manifest(provider_free_repo):
    provider_free_repo.tamper_pinned_source()
    outcome = run_phase4_readiness(
        provider_free_repo.root,
        provider_free_repo.root / "results",
    )
    assert outcome.status == "READINESS_FAILED"
    assert outcome.reason_code == "PINNED_BOOTSTRAP_SOURCE_MISMATCH"
    assert outcome.manifest is None


def test_cli_has_no_provider_strategy_or_budget_override_options():
    options = phase4_option_strings(parser())
    assert "--host" not in options
    assert "--port" not in options
    assert "--symbol" not in options
    assert "--family" not in options
    assert "--parameters" not in options
    assert "--max-trials" not in options


def test_cli_reports_ready_without_strategy_or_provider_execution(repo_root, capsys):
    code = main(
        [
            "phase4-readiness",
            "--repository-root",
            str(repo_root),
            "--results-root",
            str(repo_root / "results"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "PHASE_4_READY"
    assert payload["provider_calls"] == 0
    assert payload["strategy_search_executed"] is False
```

Add a full-tree before/after digest fixture proving that `results/experiments/`, `results/phase3/`, and `data/cache/phase3/` remain byte-identical. Add import-graph/source scans proving the readiness package does not import Moomoo, provider repositories, optimizer/search, promotion, StrategyBase export, account/order/trading symbols, or canonical tracker writers.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/quant/test_phase4_readiness_campaign.py tests/quant/test_phase4_readiness_cli.py -q`

- [ ] **Step 3: Implement ordered fail-closed orchestration**

Run gates in this order:

1. Validate configured roots and record byte digests of all protected historical artifact trees.
2. Verify and reconstruct the pinned bootstrap source/vector; write the full canonical vector.
3. Reproduce the bootstrap audit; write its evidence.
4. Build exactly 136 authoritative trial identities and deduplicated search-aware inputs; write authority evidence.
5. Materialize explicit DSR and PBO `UNKNOWN/NOT_IMPLEMENTED` results.
6. Verify the exact frozen Phase 3 universe, DQ snapshot, and eight datasets.
7. Build and write the split manifest.
8. Build and write the campaign configuration from the written split identity.
9. Re-read and identity-verify every new artifact.
10. Recompute protected historical tree digests and fail if any byte changed.
11. Run in-process safety assertions for zero provider calls, no protected symbols, no holdout access, no strategy search, and no live capability.
12. Build a complete readiness summary, write the report from that summary, then write the readiness manifest linking the report and every other readiness artifact.

The canonical full vector payload itself is stored as `vector.json`, not replaced by a summary fixture. Each readiness artifact is written independently before its identity is linked by the readiness manifest. The report is rendered from the complete summary of the first six evidence artifacts and does not attempt to contain its own identity or the not-yet-written readiness-manifest identity. The readiness manifest is written last and links the report plus every preceding evidence artifact. If a decision-critical gate fails, return `READINESS_FAILED` with a machine-readable reason and do not write a `PHASE_4_READY` manifest.

The report must state the exact bootstrap statistic and counts, the 136 historical trials, Phase 4 budget zero of 3,000, DSR/PBO status, all split ranges/counts, all artifact paths and identities, QFQ methodology, `decision_grade: false`, provider/external-research/strategy-search/holdout/protected-symbol/live-trading statuses, and the fact that no strategy discovery was authorized.

The CLI imports readiness code lazily inside `_phase4_readiness`. It accepts roots only; it has no provider, symbol, strategy, candidate, or budget override.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase4_readiness_campaign.py tests/quant/test_phase4_readiness_cli.py -q`

- [ ] **Step 5: Commit orchestration and CLI**

```powershell
git add -- src/investment_tracker/quant/readiness src/investment_tracker/quant/cli.py tests/quant/test_phase4_readiness_campaign.py tests/quant/test_phase4_readiness_cli.py
git commit -m "feat: add bounded phase 4 readiness audit"
```

### Task 8: Execute the Provider-Free Audit and Commit New Evidence

**Files:**
- Create: `results/phase4/readiness/bootstrap_input_vector/sha256/<content-sha256>/vector.json`
- Create: `results/phase4/readiness/bootstrap_audit/sha256/<content-sha256>/audit.json`
- Create: `results/phase4/readiness/trial_authority/sha256/<content-sha256>/authority.json`
- Create: `results/phase4/readiness/phase4_split_manifest/sha256/<content-sha256>/manifest.json`
- Create: `results/phase4/readiness/phase4_campaign_configuration/sha256/<content-sha256>/configuration.json`
- Create: `results/phase4/readiness/phase4_readiness_manifest/sha256/<content-sha256>/manifest.json`
- Create: `results/phase4/readiness/phase4_readiness_report/sha256/<content-sha256>/report.md`

- [ ] **Step 1: Snapshot protected historical artifact hashes**

Run a read-only script that writes its comparison baseline outside the protected trees and covers:

```text
results/experiments/
results/phase3/
data/cache/phase3/
```

Record repository-relative paths and exact-byte SHA-256 values. The implementation must compare this baseline again after the readiness run.

- [ ] **Step 2: Run the fixed-input readiness command once**

Run:

```powershell
python -m investment_tracker.quant.cli phase4-readiness --repository-root . --results-root results
```

Expected: JSON status `PHASE_4_READY`, `provider_calls: 0`, `strategy_search_executed: false`, `phase4_new_trials_consumed: 0`, and identities for all seven new artifacts.

- [ ] **Step 3: Independently validate generated evidence**

Recompute every exact-byte content hash and every canonical envelope hash from disk. Parse all JSON with the frozen models. Confirm:

- the stored vector contains exactly 1,007 ordered `float.hex()` values and has frozen digest `878b8400fcf93776feda23c454182d36dca5efd4c32f51d2aa232abf003bf0b5`;
- bootstrap output is exactly `[0.0, 0.0]`, with 2,000 zero medians and the narrow claim scope;
- trial authority contains exactly 136 unique historical trials;
- DSR/PBO have no numeric value;
- split contains eight ordered datasets with 1,258 TRAIN and 1,008 VALIDATION rows each;
- configuration contains historical count 136, consumed count zero, remaining count 3,000, and no combined consumption;
- every safety flag remains false/empty as required; and
- protected historical artifact hashes exactly match the pre-run baseline.

- [ ] **Step 4: Commit only the new Phase 4 readiness evidence**

```powershell
git add -- results/phase4/readiness
git commit -m "research: record phase 4 readiness evidence"
```

Do not add or alter Phase 2, Phase 3, provider, cache, holdout, baseline, promotion, leaderboard, or StrategyBase artifacts.

### Task 9: Run the Complete Verification Suite and Report the Gate

**Files:**
- Modify only if a new Phase 4 defect is proven: files introduced in Tasks 1-7 and their new tests.
- Do not modify existing frozen modules or weaken any existing test.

- [ ] **Step 1: Run focused readiness tests**

```powershell
python -m pytest tests/quant/test_phase4_readiness_contracts.py tests/quant/test_phase4_readiness_artifacts.py tests/quant/test_phase4_trial_authority.py tests/quant/test_phase4_bootstrap_audit.py tests/quant/test_phase4_validation_boundary.py tests/quant/test_phase4_split_and_config.py tests/quant/test_phase4_readiness_campaign.py tests/quant/test_phase4_readiness_cli.py -q
```

Expected: all new readiness tests pass.

- [ ] **Step 2: Run existing quant regressions**

```powershell
python -m pytest tests/quant -q
```

Expected: all runnable quant tests pass. If the known symlink privilege case fails, preserve its test unchanged and record the exact error as an environment limitation.

- [ ] **Step 3: Run all repository tests**

```powershell
python -m pytest -q
```

Expected: all runnable tests pass, subject only to the unchanged documented Windows symlink privilege limitation.

- [ ] **Step 4: Compile and check dependency consistency**

```powershell
python -m compileall -q src tests
python -m pip check
```

Expected: compilation succeeds and installed dependencies are consistent.

- [ ] **Step 5: Run governance and mutation scans**

Use repository-scoped, read-only scans to confirm:

- no protected symbol appears in any new readiness artifact or readiness code except the centralized deny-list safety assertion;
- no `FINAL_HOLDOUT` access record is true;
- no readiness import or call references Moomoo/provider constructors, trading contexts, account/funds/position queries, order methods, strategy search, promotion, or canonical tracker writes;
- no historical Phase 2/3 artifact byte hash changed; and
- no source file outside the planned readiness package and CLI integration changed.

- [ ] **Step 6: Verify content identities and repository diff**

Run:

```powershell
git diff --check
git status --short
git log --oneline -12
```

Recompute all seven output identities independently. Confirm the only expected uncommitted paths are pre-existing user files, including the untracked `docs/moomoo/` directory if it is still present.

- [ ] **Step 7: Produce the completion report and stop**

Report every item required by the specification: bootstrap cause/scope and repair status, exact authority campaign/count, duplicate invariance, DSR/PBO status, split ranges/counts, artifact paths/digests, frozen universe/DQ identities, 10/500/3,000 limits, separate Phase 4 zero consumption, QFQ and `decision_grade: false`, provider/external-research/search/holdout/protected-symbol/live-trading statuses, test results, unchanged symlink limitation, and commits.

If every gate passes, report `PHASE_4_READY`. Do not begin strategy discovery, candidate evaluation, parameter optimization, promotion, or StrategyBase export.
