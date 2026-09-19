# Phase 3 ETF Universe DQ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and execute a quote-only, content-addressed Phase 3 campaign that freezes complete 2014-2022 DQ evidence for all 16 approved ETFs before mechanically selecting six to eight distinct exposure slots.

**Architecture:** Add an isolated `investment_tracker.quant.universe` package for Phase 3 constants, immutable models, canonical hashing/storage, structured validation, selection, reporting, and orchestration. Extend the existing Moomoo quote adapter with a backward-compatible evidence-returning interface that retains every raw response page and calendar diagnostic; leave all frozen replay, calculation, robustness, governed-backtest, experiment, and promotion modules unchanged.

**Tech Stack:** Python 3.12, Pydantic 2, pandas, pyarrow, exchange-calendars, moomoo-api, pytest.

**Spec:** `docs/superpowers/specs/2026-09-12-etf-universe-dq-phase-3-design.md`

## Global Constraints

- Evaluate only 2014-01-01 through 2022-12-31 for admission.
- Treat 2010-2022 and 2013-2022 evidence as non-admitting historical references only.
- Evaluate exactly `SPY QQQ IWM DIA XLK XLF XLE XLV XLI XLP XLY XLU VNQ TLT IEF GLD`.
- Deny `HACK SOXX NLR URNM GEV` before symbol-specific filesystem, cache, provider, or diagnostic access.
- Preserve TPC-v1.2, REPLAY-v1.0, CALC-v1.2, and ROBUST-v1.0 unchanged.
- Use only `OpenQuoteContext`; do not introduce a trading context, account query, order method, or live path.
- Preserve raw provider `code`, `time_key`, OHLCV, pages, request parameters, SDK/OpenD versions, and retrieval time immutably.
- Do not repair, synthesize, interpolate, fill, delete, or move provider bars.
- Complete and freeze all 16 DQ dispositions before selection.
- XNYS alone controls admission; Moomoo calendar evidence is diagnostic only.
- Selection uses only frozen DQ outcomes and the fixed slot/fallback order, stops at eight, and fails closed below six.
- QFQ remains `decision_grade=false`; no strategy or performance inputs are permitted.
- Preserve existing experiment artifacts, keep `FINAL_HOLDOUT` sealed, and do not start Phase 4.

## File Structure

- Create `src/investment_tracker/quant/universe/constants.py`: fixed campaign inputs, versions, and exposure slots.
- Create `src/investment_tracker/quant/universe/models.py`: frozen evidence, DQ, selection, and manifest contracts.
- Create `src/investment_tracker/quant/universe/hashing.py`: canonical JSON/scalar encoding and SHA-256 utilities.
- Create `src/investment_tracker/quant/universe/artifacts.py`: immutable raw, normalized, quarantine, snapshot, report, and manifest storage with readback verification.
- Create `src/investment_tracker/quant/universe/validation.py`: structured Phase 3 DQ assessment and session diagnostics.
- Create `src/investment_tracker/quant/universe/selection.py`: snapshot-gated deterministic exposure selection.
- Create `src/investment_tracker/quant/universe/report.py`: all-candidate DQ report rendering without performance metrics.
- Create `src/investment_tracker/quant/universe/campaign.py`: preflight, acquisition/reuse, DQ freeze, selection, and final freeze orchestration.
- Create `src/investment_tracker/quant/universe/__init__.py`: public Phase 3 entry points only.
- Modify `src/investment_tracker/quant/data/moomoo_client.py`: add raw-page, preflight, and calendar evidence without changing the existing `fetch()` contract.
- Modify `src/investment_tracker/quant/cli.py`: add the quote-only `phase3-universe` command.
- Create focused tests under `tests/quant/` for each Phase 3 boundary.

---

### Task 1: Freeze Campaign Contracts and Canonical Hashing

**Files:**
- Create: `src/investment_tracker/quant/universe/__init__.py`
- Create: `src/investment_tracker/quant/universe/constants.py`
- Create: `src/investment_tracker/quant/universe/models.py`
- Create: `src/investment_tracker/quant/universe/hashing.py`
- Test: `tests/quant/test_phase3_contracts.py`

**Interfaces:**
- Produces: `CAMPAIGN_START`, `CAMPAIGN_END`, `CANDIDATE_POOL`, `EXPOSURE_SLOTS`, `MIN_UNIVERSE_SIZE`, `MAX_UNIVERSE_SIZE`, version constants.
- Produces: `ArtifactIdentity`, `ProviderRequestRecord`, `RawRowReference`, `CalendarDiagnostic`, `SessionDiagnostic`, `CandidateDQResult`, `DQSnapshot`, `FrozenDQSnapshot`, `SelectionDecision`, `SelectionResult`, `UniverseManifest`.
- Produces: `canonical_json_bytes(value) -> bytes`, `canonical_sha256(value) -> str`, `tag_scalar(value) -> dict[str, object]`.

- [ ] **Step 1: Write failing contract and hashing tests**

```python
def test_phase3_contracts_freeze_window_pool_and_limits():
    assert (CAMPAIGN_START.isoformat(), CAMPAIGN_END.isoformat()) == (
        "2014-01-01", "2022-12-31"
    )
    assert len(CANDIDATE_POOL) == 16
    assert MIN_UNIVERSE_SIZE == 6
    assert MAX_UNIVERSE_SIZE == 8

def test_canonical_hash_is_order_independent_and_rejects_non_finite_json():
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})
    assert canonical_sha256({"a": 1, "b": 2}) == (
        "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )
    assert tag_scalar(float("nan")) == {"type": "float", "value": "nan"}
    assert tag_scalar(float("inf")) == {"type": "float", "value": "inf"}

def test_models_reject_extra_fields_and_performance_inputs():
    with pytest.raises(ValidationError, match="candidate pool"):
        DQSnapshot(campaign_id="campaign", candidates=())
    with pytest.raises(ValidationError, match="sharpe"):
        CandidateDQResult.model_validate({**passing_candidate_payload(), "sharpe": 1.0})
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/quant/test_phase3_contracts.py -q`

Expected: collection/import failure because the Phase 3 package does not exist.

- [ ] **Step 3: Implement minimal frozen constants, models, and canonical hashing**

```python
def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()
```

Use Pydantic `ConfigDict(extra="forbid", frozen=True)` throughout. `DQSnapshot` validates the exact fixed window, exact 16-symbol set, unique symbols, and one `PASS`/`FAIL` result per symbol. Do not define any strategy-performance field.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase3_contracts.py -q`

- [ ] **Step 5: Commit the contracts**

```powershell
git add -- src/investment_tracker/quant/universe tests/quant/test_phase3_contracts.py
git commit -m "feat: freeze phase 3 universe contracts"
```

### Task 2: Capture Complete Quote-Only Moomoo Evidence

**Files:**
- Modify: `src/investment_tracker/quant/data/moomoo_client.py`
- Test: `tests/quant/test_phase3_moomoo_evidence.py`
- Test: `tests/quant/test_moomoo_client.py`

**Interfaces:**
- Produces: `MoomooPreflightResult`, `MoomooRawPage`, `MoomooFetchEvidence`, `MoomooCalendarEvidence` dataclasses.
- Produces: `MoomooHistoricalDataSource.fetch_with_evidence(request) -> MoomooFetchEvidence`.
- Produces: `MoomooHistoricalDataSource.fetch_calendar_evidence(request) -> MoomooCalendarEvidence`.
- Changes: `preflight(symbol) -> MoomooPreflightResult`; existing callers may ignore its return value.
- Preserves: `fetch(request) -> tuple[pd.DataFrame, str | None]`.

- [ ] **Step 1: Write failing provider-evidence tests**

```python
def test_fetch_evidence_preserves_raw_pages_code_time_key_and_request_chain():
    evidence = source.fetch_with_evidence(request())
    assert evidence.pages[0].frame.loc[0, "code"] == "US.SPY"
    assert evidence.pages[0].frame.loc[0, "time_key"] == "2024-07-03 00:00:00"
    assert evidence.pages[0].input_page_req_key is None
    assert evidence.pages[0].output_page_req_key == b"next"
    assert evidence.request_parameters["session"] == "RTH"

def test_provider_failure_returns_auditable_partial_evidence_and_closes_context():
    evidence = source.fetch_with_evidence(request())
    assert evidence.status == "ERROR"
    assert evidence.error == "Moomoo historical request failed: permission denied"
    assert context.closed

def test test_preflight_reads_global_state_with_quote_context_only and closes.
def test_calendar_evidence_uses_code_and_fixed_dates and closes.
```

Also retain the existing guard-before-SDK, pagination-loop, malformed payload, identity, and Eastern-date tests.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/quant/test_phase3_moomoo_evidence.py tests/quant/test_moomoo_client.py -q`

Expected: import/attribute failures for the new evidence API.

- [ ] **Step 3: Implement evidence-returning quote adapter**

Capture each page before normalization, record byte page keys in a deterministic tagged representation, and always close the `OpenQuoteContext` in `finally`. Record exact request values:

```python
{
    "code": f"US.{symbol}", "start": "2014-01-01", "end": "2022-12-31",
    "ktype": "K_DAY", "autype": "QFQ", "fields": ["ALL"],
    "max_count": 1000, "extended_time": False, "session": "RTH",
    "host": host, "port": port,
}
```

`preflight` calls `get_global_state()`, fails unless `RET_OK`, records `server_ver`, quote-login status, program status, SDK version, host, and port, and closes the context. It never inspects trading accounts or unlocks trading.

`fetch_calendar_evidence` calls only `request_trading_days(start=request.start.isoformat(), end=request.end.isoformat(), code=f"US.{symbol}")`, captures the exact returned object/error, and closes the context.

- [ ] **Step 4: Run focused and existing adapter tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase3_moomoo_evidence.py tests/quant/test_moomoo_client.py -q`

- [ ] **Step 5: Commit provider evidence support**

```powershell
git add -- src/investment_tracker/quant/data/moomoo_client.py tests/quant/test_phase3_moomoo_evidence.py tests/quant/test_moomoo_client.py
git commit -m "feat: retain quote provider evidence"
```

### Task 3: Store Immutable Content-Addressed Evidence

**Files:**
- Create: `src/investment_tracker/quant/universe/artifacts.py`
- Test: `tests/quant/test_phase3_artifacts.py`

**Interfaces:**
- Produces: `Phase3ArtifactStore(evidence_root: Path, results_root: Path)`.
- Produces: `write_raw_evidence`, `write_normalized_dataset`, `write_quarantine`, `write_candidate_record`, `find_candidate_record`, `freeze_dq_snapshot`, `load_frozen_snapshot`, `write_report`, and `write_universe_manifest`.
- Consumes: canonical hashes and immutable models from Task 1; raw evidence dataclasses from Task 2.

- [ ] **Step 1: Write failing immutability and round-trip tests**

```python
def test_raw_artifact_preserves_typed_code_time_key_ohlcv_and_page_provenance(tmp_path):
    store = Phase3ArtifactStore(tmp_path / "cache", tmp_path / "results")
    identity = store.write_raw_evidence(two_page_fetch_fixture())
    payload = store.read_json(identity)
    first = payload["pages"][0]
    assert first["input_page_req_key"] == {"type": "null", "value": None}
    assert first["output_page_req_key"] == {"type": "bytes", "value": "6e657874"}
    assert first["rows"][0][0] == {"type": "str", "value": "US.SPY"}
    assert first["rows"][0][1] == {"type": "str", "value": "2024-07-03 00:00:00"}

def test_raw_write_reuses_identical_content(tmp_path):
    store = Phase3ArtifactStore(tmp_path / "cache", tmp_path / "results")
    first = store.write_raw_evidence(two_page_fetch_fixture())
    second = store.write_raw_evidence(two_page_fetch_fixture())
    assert first == second

def test_normalized_parquet_hash_verifies_and_tampering_fails_closed(tmp_path):
    store = Phase3ArtifactStore(tmp_path / "cache", tmp_path / "results")
    identity = store.write_normalized_dataset(valid_bars(), normalized_metadata())
    store.load_normalized_dataset(identity)
    identity.path.joinpath("bars.parquet").write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError):
        store.load_normalized_dataset(identity)

def test_quarantine_is_content_addressed(tmp_path):
    store = Phase3ArtifactStore(tmp_path / "cache", tmp_path / "results")
    first = store.write_quarantine(quarantine_payload())
    second = store.write_quarantine(quarantine_payload())
    assert first == second

def test_candidate_cache_requires_exact_request_and_versions(tmp_path):
    store = populated_candidate_store(tmp_path)
    assert store.find_candidate_record(provider_request(), version_vector()) is not None
    assert store.find_candidate_record(
        provider_request(end="2022-12-30"), version_vector()
    ) is None
    assert store.find_candidate_record(
        provider_request(), version_vector(validator="XNYS-OHLCV-DQ-v2")
    ) is None

def test_locked_symbol_is_denied_before_artifact_root_is_touched(tmp_path):
    occupied = tmp_path / "occupied"
    occupied.write_text("not a directory", encoding="utf-8")
    store = Phase3ArtifactStore(occupied, occupied)
    with pytest.raises(LockedHoldoutError):
        store.find_candidate_record(provider_request(symbol="HACK"), version_vector())
```

Use hand-derived tagged-scalar fixtures. Raw rows encode every column/value with explicit types so `None`, strings, integers, floats, NaN, infinity, timestamps, and bytes remain distinguishable.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/quant/test_phase3_artifacts.py -q`

- [ ] **Step 3: Implement atomic content-addressed storage**

Use exclusive temporary files/directories under the exact destination parent, `os.replace`, SHA-256 directory names, and readback verification. Resolve every destructive cleanup target beneath the configured store root before removal. Do not mutate the existing `ImmutableParquetCache` or historical experiment artifacts.

Logical layout:

```text
<evidence-root>/phase3/raw/moomoo/sha256/<digest>/evidence.json
<evidence-root>/phase3/normalized/sha256/<digest>/{bars.parquet,metadata.json}
<evidence-root>/phase3/quarantine/sha256/<digest>/quarantine.json
<evidence-root>/phase3/candidates/sha256/<digest>/candidate.json
<results-root>/phase3/campaigns/<campaign-id>/dq-snapshots/<digest>.json
<results-root>/phase3/campaigns/<campaign-id>/reports/<digest>.md
<results-root>/phase3/universes/<digest>/manifest.json
```

- [ ] **Step 4: Run artifact tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase3_artifacts.py -q`

- [ ] **Step 5: Commit immutable stores**

```powershell
git add -- src/investment_tracker/quant/universe/artifacts.py tests/quant/test_phase3_artifacts.py
git commit -m "feat: add immutable phase 3 evidence stores"
```

### Task 4: Produce Structured XNYS DQ and Calendar Diagnostics

**Files:**
- Create: `src/investment_tracker/quant/universe/validation.py`
- Test: `tests/quant/test_phase3_validation.py`

**Interfaces:**
- Produces: `Phase3DQValidator.assess(request, fetch_evidence, raw_identity, normalized_identity, calendar_evidence=None) -> CandidateDQResult`.
- Consumes: `BarDataValidator` for unchanged core OHLCV checks and XNYS sessions; raw-row links from Task 2.

- [ ] **Step 1: Write failing structured-DQ tests**

```python
def test_missing_session_has_null_raw_time_key_and_neighbor_raw_rows():
    result = validator.assess(
        request("2024-07-01", "2024-07-03"),
        fetch_fixture(["2024-07-01", "2024-07-03"]),
        raw_identity(),
        normalized_identity(),
    )
    missing = result.missing_sessions[0]
    assert missing.raw_time_key is None
    assert missing.expected_xnys_session.isoformat() == "2024-07-02"
    assert missing.preceding.raw_time_key == "2024-07-01 00:00:00"
    assert missing.following.raw_time_key == "2024-07-03 00:00:00"

def test_unexpected_session_preserves_exact_raw_time_key_and_neighbors():
    result = assess_dates(["2024-07-03", "2024-07-04", "2024-07-05"])
    unexpected = result.unexpected_sessions[0]
    assert unexpected.raw_time_key == "2024-07-04 00:00:00"
    assert unexpected.normalized_date.isoformat() == "2024-07-04"
    assert unexpected.preceding.raw_time_key == "2024-07-03 00:00:00"
    assert unexpected.following.raw_time_key == "2024-07-05 00:00:00"

def test_moomoo_disagreement_is_diagnostic_and_result_remains_fail():
    result = assess_missing_with_calendar(provider_open_dates=[])
    assert result.missing_sessions[0].calendar.state == "DISAGREE"
    assert result.status == "FAIL"

def test_cause_defaults_unknown_and_no_bar_is_repaired_or_mutated():
    fetch = fetch_fixture(["2024-07-01", "2024-07-03"])
    before = fetch.normalized.copy(deep=True)
    result = assess(fetch)
    assert result.missing_sessions[0].cause == "UNKNOWN"
    pd.testing.assert_frame_equal(fetch.normalized, before)
    assert len(fetch.normalized) == 2

def test_timezone_conflict_fails_closed():
    fetch = fetch_fixture(["2024-07-03", "2024-07-05"])
    fetch.normalized.index = fetch.normalized.index.tz_localize(None)
    result = assess(fetch)
    assert result.status == "FAIL"
    assert "TIMEZONE_CONFLICT" in {issue.code for issue in result.issues}
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/quant/test_phase3_validation.py -q`

- [ ] **Step 3: Implement minimal structured assessment**

Derive structured missing/unexpected sets from the fixed XNYS sessions and normalized index. Locate chronological raw neighbors using normalization row links. For missing sessions, hard-code `raw_time_key=None`; never infer it. Classify diagnostic state as `AGREE_OPEN`, `AGREE_CLOSED`, `DISAGREE`, or `UNAVAILABLE`, but compute `status` solely from XNYS/core issues. Keep `cause="UNKNOWN"` unless an explicit future evidence rule is versioned.

- [ ] **Step 4: Run Phase 3 and existing validator tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase3_validation.py tests/quant/test_data_validation.py -q`

- [ ] **Step 5: Commit structured validation**

```powershell
git add -- src/investment_tracker/quant/universe/validation.py tests/quant/test_phase3_validation.py
git commit -m "feat: add structured phase 3 DQ diagnostics"
```

### Task 5: Gate Mechanical Selection on a Frozen Complete Snapshot

**Files:**
- Create: `src/investment_tracker/quant/universe/selection.py`
- Test: `tests/quant/test_phase3_selection.py`

**Interfaces:**
- Produces: `select_universe(snapshot_ref: ArtifactIdentity, store: Phase3ArtifactStore) -> SelectionResult`.
- Consumes: only a verified, read-back `DQSnapshot`; never consumes frames, prices, or metrics.

- [ ] **Step 1: Write failing selection-gate tests**

```python
def test_selection_rejects_tampered_snapshot(tmp_path):
    store, frozen = frozen_store(tmp_path, clean_symbols=set(CANDIDATE_POOL))
    Path(frozen.path).write_text("{}", encoding="utf-8")
    with pytest.raises(ArtifactIntegrityError):
        select_universe(frozen, store)

def test_snapshot_order_does_not_change_selection(tmp_path):
    clean = {"DIA", "XLK", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLV", "XLI"}
    forward = select_from_statuses(tmp_path / "a", clean, CANDIDATE_POOL)
    reverse = select_from_statuses(tmp_path / "b", clean, tuple(reversed(CANDIDATE_POOL)))
    assert forward.selected_symbols == reverse.selected_symbols

def test_first_clean_fallback_wins_without_duplicate_slot_inflation(tmp_path):
    result = select_from_statuses(tmp_path, set(CANDIDATE_POOL), CANDIDATE_POOL)
    assert result.selected_symbols[:2] == ("SPY", "QQQ")
    assert "DIA" not in result.selected_symbols
    assert "XLK" not in result.selected_symbols

def test_cyclical_slot_is_used_only_below_eight_and_selection_stops_at_eight(tmp_path):
    clean = {"SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "XLP", "XLI", "XLF"}
    result = select_from_statuses(tmp_path, clean, CANDIDATE_POOL)
    assert result.selected_symbols == ("SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "XLP", "XLI")

def test_fewer_than_six_returns_exact_fail_closed_reason(tmp_path):
    result = select_from_statuses(tmp_path, {"SPY", "QQQ", "TLT", "IEF", "GLD"}, CANDIDATE_POOL)
    assert result.stop_reason == "INSUFFICIENT_CLEAN_DIVERSIFIED_UNIVERSE"
    assert result.admitted is False

def test_selection_contract_rejects_strategy_performance_fields():
    with pytest.raises(ValidationError, match="sharpe"):
        SelectionResult.model_validate({**valid_selection_payload(), "sharpe": 1.0})
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/quant/test_phase3_selection.py -q`

- [ ] **Step 3: Implement fixed-order selector**

Load and hash-verify the snapshot inside the selector, rebuild status by symbol, traverse `EXPOSURE_SLOTS` in declared order, select the first `PASS`, and stop at eight. Return `INSUFFICIENT_CLEAN_DIVERSIFIED_UNIVERSE` below six; otherwise return `PHASE_3_UNIVERSE_FROZEN`. The decision log records slot, ordered candidates, frozen DQ statuses, selected symbol, and reason only.

- [ ] **Step 4: Run selection tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase3_selection.py -q`

- [ ] **Step 5: Commit deterministic selection**

```powershell
git add -- src/investment_tracker/quant/universe/selection.py tests/quant/test_phase3_selection.py
git commit -m "feat: gate deterministic universe selection"
```

### Task 6: Orchestrate the Campaign and Render the DQ Report

**Files:**
- Create: `src/investment_tracker/quant/universe/report.py`
- Create: `src/investment_tracker/quant/universe/campaign.py`
- Test: `tests/quant/test_phase3_campaign.py`

**Interfaces:**
- Produces: `run_phase3_campaign(source, store, *, campaign_id, retrieved_at=None) -> CampaignOutcome`.
- Produces: `render_dq_report(snapshot, selection) -> str`.
- Consumes: exact candidate pool/window, provider evidence API, store, validator, and selector.

- [ ] **Step 1: Write failing end-to-end campaign tests with a quote-only fake**

```python
def test_campaign_assesses_all_16_freezes_snapshot_then_selects_and_manifests(tmp_path):
    outcome = run_phase3_campaign(fake_source, store, campaign_id="test-campaign")
    assert fake_source.requested_symbols == list(CANDIDATE_POOL)
    assert outcome.stop_reason == "PHASE_3_UNIVERSE_FROZEN"
    assert 6 <= len(outcome.selected_symbols) <= 8
    assert store.events.index("snapshot_readback_verified") < store.events.index("selection_started")

def test_failed_provider_evidence_is_quarantined_and_in_snapshot(tmp_path):
    outcome = run_with_provider_failure(tmp_path, failed_symbol="IWM")
    snapshot = load_snapshot(outcome)
    iwm = next(item for item in snapshot.candidates if item.symbol == "IWM")
    assert iwm.status == "FAIL"
    assert iwm.raw_evidence is not None
    assert iwm.quarantine is not None
    assert len(snapshot.candidates) == 16

def test_report_covers_all_candidates_and_has_no_performance_metrics(tmp_path):
    outcome = run_clean_campaign(tmp_path)
    report = Path(outcome.dq_report.path).read_text(encoding="utf-8")
    assert all(symbol in report for symbol in CANDIDATE_POOL)
    assert all(term not in report for term in ("CAGR", "Sharpe", "drawdown", "strategy score"))

def test_campaign_never_requests_reference_or_later_windows(tmp_path):
    source = recording_source()
    run_phase3_campaign(source, artifact_store(tmp_path), campaign_id="fixed-window")
    assert {(call.start.isoformat(), call.end.isoformat()) for call in source.fetch_calls} == {
        ("2014-01-01", "2022-12-31")
    }

def test_manifest_references_complete_provenance(tmp_path):
    outcome = run_clean_campaign(tmp_path)
    manifest = load_manifest(outcome)
    assert manifest.dq_snapshot.sha256 == outcome.dq_snapshot.sha256
    assert manifest.dq_report.sha256 == outcome.dq_report.sha256
    assert len(manifest.raw_evidence) == 16
    assert manifest.normalization_version == NORMALIZATION_VERSION
    assert manifest.validator_version == VALIDATOR_VERSION
    assert all(item.provider_request.max_count == 1000 for item in manifest.candidates)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/quant/test_phase3_campaign.py -q`

- [ ] **Step 3: Implement the campaign in mandatory order**

```text
guard fixed pool -> preflight -> acquire/reuse all 16 -> preserve raw -> normalize/store
-> validate/diagnose/quarantine -> build all 16 DQ results -> freeze/readback snapshot
-> deterministic selection -> render/hash report -> manifest only if at least six
-> readback/hash verification -> CampaignOutcome
```

The manifest contains all required provenance and `decision_grade=false`, `final_holdout_accessed=false`, `strategy_performance_used=false`, `strategy_backtests_executed=0`, `bars_repaired=0`, and `live_trading_capability=false`.

- [ ] **Step 4: Run campaign tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase3_campaign.py -q`

- [ ] **Step 5: Commit campaign orchestration**

```powershell
git add -- src/investment_tracker/quant/universe/report.py src/investment_tracker/quant/universe/campaign.py tests/quant/test_phase3_campaign.py
git commit -m "feat: orchestrate phase 3 universe freeze"
```

### Task 7: Add the Quote-Only Phase 3 CLI

**Files:**
- Modify: `src/investment_tracker/quant/cli.py`
- Modify: `src/investment_tracker/quant/universe/__init__.py`
- Test: `tests/quant/test_phase3_cli.py`
- Test: `tests/quant/test_configuration_and_boundaries.py`

**Interfaces:**
- Produces CLI: `python -m investment_tracker.quant.cli phase3-universe --host 127.0.0.1 --port 11111 --evidence-root data/cache --results-root results`.

- [ ] **Step 1: Write failing CLI and forbidden-API tests**

```python
def test_phase3_cli_runs_campaign_and_prints_paths_and_digests(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("investment_tracker.quant.universe.run_phase3_campaign", fake_campaign)
    code = main(["phase3-universe", "--evidence-root", str(tmp_path), "--results-root", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["stop_reason"] == "PHASE_3_UNIVERSE_FROZEN"
    assert payload["dq_snapshot"]["sha256"] == "a" * 64
    assert payload["universe_manifest"]["sha256"] == "b" * 64

def test_phase3_cli_has_no_window_symbol_strategy_or_refresh_override():
    subparsers = next(
        action for action in parser()._actions if isinstance(action, argparse._SubParsersAction)
    )
    option_strings = {
        option
        for action in subparsers.choices["phase3-universe"]._actions
        for option in action.option_strings
    }
    assert option_strings.isdisjoint(
        {"--start", "--end", "--symbol", "--strategy", "--refresh"}
    )

def test_quant_ast_has_no_forbidden_trading_api():
    forbidden = {
        "OpenSecTradeContext", "OpenFutureTradeContext", "OpenCryptoTradeContext",
        "place_order", "modify_order", "cancel_order", "unlock_trade",
        "get_acc_list", "position_list_query", "accinfo_query",
    }
    assert scan_python_names(Path("src/investment_tracker/quant"), forbidden) == []
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/quant/test_phase3_cli.py tests/quant/test_configuration_and_boundaries.py -q`

- [ ] **Step 3: Implement minimal CLI command**

Construct only `MoomooHistoricalDataSource`, `Phase3ArtifactStore`, and `run_phase3_campaign`. Print a canonical JSON outcome. Do not call backtest, TRAIN, VALIDATION, optimizer, external research, or promotion/export code.

- [ ] **Step 4: Run CLI/boundary tests and verify GREEN**

Run: `python -m pytest tests/quant/test_phase3_cli.py tests/quant/test_configuration_and_boundaries.py -q`

- [ ] **Step 5: Commit the CLI**

```powershell
git add -- src/investment_tracker/quant/cli.py src/investment_tracker/quant/universe/__init__.py tests/quant/test_phase3_cli.py tests/quant/test_configuration_and_boundaries.py
git commit -m "feat: expose quote-only phase 3 campaign"
```

### Task 8: Run Provider Campaign and Verify Frozen Artifacts

**Files:**
- Create at runtime: content-addressed ignored artifacts beneath `data/cache/phase3/` and `results/phase3/`.
- Do not modify tracked frozen modules or existing experiment artifacts.

**Interfaces:**
- Consumes: `phase3-universe` CLI from Task 7 and authenticated OpenD at `127.0.0.1:11111`.
- Produces: complete DQ snapshot/report and, only with six or more slots, the universe manifest.

- [ ] **Step 1: Run all implementation verification before provider access**

```powershell
python -m pytest tests/quant/test_phase3_contracts.py tests/quant/test_phase3_moomoo_evidence.py tests/quant/test_phase3_artifacts.py tests/quant/test_phase3_validation.py tests/quant/test_phase3_selection.py tests/quant/test_phase3_campaign.py tests/quant/test_phase3_cli.py -q
python -m pytest tests/quant -q
```

- [ ] **Step 2: Run the quote-only OpenD preflight and fixed campaign**

```powershell
python -m investment_tracker.quant.cli phase3-universe --host 127.0.0.1 --port 11111 --evidence-root data/cache --results-root results
```

Stop on a genuine provider/preflight blocker. Never supply a symbol/window override.

- [ ] **Step 3: Validate generated artifacts and governed scans**

Run the artifact verifier exposed by the models/store, recompute DQ snapshot and manifest digests, confirm exact candidate/window coverage, scan caches for protected symbols, scan Phase 3 output for `FINAL_HOLDOUT`, and AST-scan quant source for forbidden trading APIs.

- [ ] **Step 4: Run complete final verification**

```powershell
python -m pytest tests/quant -q
python -m pytest -q
python -m compileall -q src tests
python -m pip check
git diff --check
```

The one known `test_manifest_rejects_symlink_artifact` Windows privilege failure may remain. Do not edit or weaken that test.

- [ ] **Step 5: Commit implementation and report metadata, not ignored datasets**

Commit only intended source/tests/docs. Keep content-addressed runtime evidence in its governed ignored locations unless the repository's established policy explicitly tracks a small manifest/report. Record exact commit IDs in the completion report.
