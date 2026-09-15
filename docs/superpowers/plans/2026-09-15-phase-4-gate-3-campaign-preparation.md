# Phase 4 Gate 3 Campaign Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and seal provider-free Gate 3 execution methodology and campaign infrastructure without running the real 180-candidate VALIDATION campaign.

**Architecture:** Add isolated `quant.phase4.gate3_execution` units for eight segregated comparison-baseline replays, post-replay regime attribution, static sealed-candidate/evidence orchestration, and append-only methodology sealing. Call frozen Gate 2 and Gate 3 APIs without modifying them. An additive preflight binds all exact identities and returns `GATE3_CAMPAIGN_READY_TO_EXECUTE` but cannot run a candidate.

**Tech Stack:** Python 3, pandas, NumPy, Pydantic, PyArrow only for existing authority preflight, pytest, SHA-256 canonical JSON, Git exact-byte identity checks.

**Spec:** `docs/superpowers/specs/2026-09-15-phase-4-gate-3-execution-methodology-design.md`

## Global Constraints

- Starting source commit: `f653dfd0caefd2b33e69419a24c4dc3002196aa0`; approved specification commit: `6676799`.
- Gate 1 manifest content `dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89`; Gate 2 manifest content `c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6`; corrected Gate 3 authority manifest content `705935c9b06b8f592e66e5e71e4541d910b585be6e9a30e46b99fe97b7591d4f`.
- Candidate population 180, positions 1–180, digest `15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3`; TRAIN session digest `7d932a1e45637404e2460107ab0f09b33d74d8a28360533bdb9fdaa96416d995`; VALIDATION session digest `330dc026e62cea178fc1f28df18ce6479726b4662838bf9454d354c2d00c13d6`.
- Preserve sealed Gate 1/Gate 2/Gate 3 authority files and artifacts, exact candidate and baseline rules, and frozen TPC/REPLAY/CALC/ROBUST modules.
- No real VALIDATION candidate execution or candidate metric inspection, ranking, survivor selection, candidate search, provider/download, protected-symbol/FINAL_HOLDOUT, trading/account/order interface, or live capability.
- `QFQ_NORMALIZED`, next eligible OPEN fills, 3-bps primary friction, `decision_grade=false`; `max_drawdown/Calmar=UNKNOWN`, `DSR/PBO=UNKNOWN/NOT_IMPLEMENTED`.
- No `.gitignore` change or historical artifact mutation. All new evidence is content-addressed and append-only.

## File responsibilities

`src/investment_tracker/quant/phase4/gate3_execution/baselines.py` owns eight single-symbol self-financing replays and post-replay aggregate. `regimes.py` owns noncontiguous conditional-return diagnostics from one replay. `campaign.py` owns a static identity-only 180-row plan and typed trial evidence validation; it never searches or runs VALIDATION. `artifacts.py` owns immutable canonical JSON writes and exact-byte identity verification under a new Gate 3 execution-methodology subtree. `methodology.py` owns fixed semantic method records, final manifest, source-bundle identity, and additive explicit-identity preflight. `cli.py` exposes only `seal` and `preflight`. No execution command exists at this checkpoint.

### Task 1: Eight segregated baseline sleeves

**Files:** Create `src/investment_tracker/quant/phase4/gate3_execution/__init__.py`, `baselines.py`; test `tests/quant/test_phase4_gate3_execution_baselines.py`.

**Interfaces:** Consume `Gate2Authority.baselines`, `ScoredMarketInput`, Phase 2 `build_strategy`, sealed Gate 2 `_validated_scored` and `_replay`. Produce `simulate_baseline(authority: Gate2Authority, market: ScoredMarketInput, baseline_id: str) -> BaselineComparison` with `sleeves`, `close_equity`, `daily_returns`; no Phase 4 binding.

- [ ] **Step 1: RED tests.** Use a synthetic eight-column `MarketPanel` with UTC scored/warm-up sessions and exact frozen symbols. Test all four sealed baselines produce exactly eight `PortfolioReplay` sleeves with one distinct symbol and `initial_cash==12500.0`, independent first cash states, same 3-bps fill convention, `signal_timestamp < fill_timestamp`, aggregate equity equal to the literal sum of sleeve equities, and no candidate ID/binding in any baseline replay. Mutate a later symbol close and show another symbol's earlier target/fills remain unchanged. Use a one-symbol fixture with a declining-then-rising QFQ close to prove a present zero target liquidates at next OPEN, while absent pending instructions do not fill. An altered baseline ID or extra symbol must fail closed.

```python
def test_sleeve_capital_is_segregated(authority, eight_symbol_market):
    result = simulate_baseline(authority, eight_symbol_market, "baseline-trend-v1")
    assert len(result.sleeves) == 8
    assert tuple(item.symbol for item in result.sleeves) == (
        "SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP"
    )
    assert all(item.replay.initial_cash == 12500.0 for item in result.sleeves)
    assert result.close_equity[0] == 100000.0
    assert result.close_equity == tuple(
        sum(item.replay.close_equity[i] for item in result.sleeves)
        for i in range(len(result.close_equity))
    )
    assert all(item.replay.candidate_id is None for item in result.sleeves)
```

- [ ] **Step 2: Demonstrate RED.** Run `pytest -q tests/quant/test_phase4_gate3_execution_baselines.py`; require failure because `simulate_baseline` is missing, not a fixture/import typo.
- [ ] **Step 3: Minimal GREEN implementation.** Resolve `baseline_id` from exact sealed `authority.baselines`; instantiate `build_strategy(family, parameters)` without changing tuple. Compute each sleeve's causal Phase 2 target series from only its combined QFQ CLOSE; admit only VALIDATION offsets, detect changes with `np.isclose(atol=1e-12, rtol=0)`, validate one aligned optional pending instruction per scored session, and call the frozen `_replay` once per single-symbol panel at `initial_cash=12500.0, friction_bps=3, binding=None`. Validate each recorded fill is next-session OPEN and each one-symbol cash/unit state is nonnegative. Aggregate only equity after eight complete replays.

```python
def _daily_returns(equity: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity)))

def _pending(signal, due, symbol: str, exposure: float):
    if not 0.0 <= exposure <= 1.0:
        raise ValueError("BASELINE_TARGET_INVALID")
    return (signal, due, ((symbol, exposure),))
```

- [ ] **Step 4: GREEN/regression.** Run focused test, `tests/quant/test_phase4_gate2_execution.py`, and `tests/quant/test_phase4_gate2_market.py`; require no unexplained failures. Review `git diff --check` and ensure no sealed file changed.
- [ ] **Step 5: Commit.** `git add src/investment_tracker/quant/phase4/gate3_execution/__init__.py src/investment_tracker/quant/phase4/gate3_execution/baselines.py tests/quant/test_phase4_gate3_execution_baselines.py`; `git commit -m "feat: isolate Gate 3 comparison baseline sleeves"`.

### Task 2: Return-ending regime attribution

**Files:** Create `src/investment_tracker/quant/phase4/gate3_execution/regimes.py`; test `tests/quant/test_phase4_gate3_execution_regimes.py`.

**Interfaces:** Consume one immutable `PortfolioReplay` and frozen `LaggedReturnRegimeAuthority`; produce `attribute_regime_returns(replay: PortfolioReplay, authority: LaggedReturnRegimeAuthority) -> RegimeAttribution` with three ordered vectors and typed valid conditional metrics. No strategy/market input is accepted.

- [ ] **Step 1: RED tests.** Construct a real synthetic continuous scored `MarketPanel` and `PortfolioReplay`, with literal regime mapping. Assert `len(replay.sessions)==1008`, `len(replay.daily_returns)==1007`, return 0 absent at first session, mapping uses sessions[1:] (ending timestamps), exactly 1007 assignments, chronological vector order, conditional compounded result against a hand-derived two-return example `(1.1 * 0.9)-1 == -0.01`, and no CAGR/drawdown/calendar/rolling field. Changed/duplicate/missing regime mapping fails. An empty conditional subset returns `UNKNOWN/NO_RETURN_OBSERVATIONS`, not zero.

```python
def test_first_session_is_labelled_without_a_return(replay_1008, regime_authority):
    result = attribute_regime_returns(replay_1008, regime_authority)
    assert len(replay_1008.daily_returns) == 1007
    assert sum(item.return_observation_count for item in result.regimes) == 1007
    assert result.first_session_label is not None
    assert result.first_session_return is None
    assert all("cagr" not in item.__dict__ for item in result.regimes)
```

- [ ] **Step 2: Demonstrate RED.** Run `pytest -q tests/quant/test_phase4_gate3_execution_regimes.py`; require failure because `attribute_regime_returns` is missing.
- [ ] **Step 3: Minimal GREEN.** Verify authority regime IDs and exact ordered 1008-session map equal replay sessions; zip `replay.sessions[1:]` with `replay.daily_returns` strictly; group by each return-ending session's label. Compute count, positive count/fraction, arithmetic mean, and `math.prod(1+r)-1` only; omit median and prohibited path-dependent metrics. Reject nonfinite returns and incomplete labels.

```python
for session, daily_return in zip(replay.sessions[1:], replay.daily_returns, strict=True):
    regime = mapping[session.strftime("%Y-%m-%d")]
    vectors[regime].append(float(daily_return))
```

- [ ] **Step 4: GREEN/regression.** Run focused test plus `tests/quant/test_phase4_gate2_robustness.py` and `tests/quant/test_phase4_gate3_authorities.py`; review diff and sealed-file status.
- [ ] **Step 5: Commit.** `git add src/investment_tracker/quant/phase4/gate3_execution/regimes.py tests/quant/test_phase4_gate3_execution_regimes.py`; `git commit -m "feat: attribute Gate 3 returns to frozen regimes"`.

### Task 3: Identity-only campaign plan and append-only trial evidence

**Files:** Create `src/investment_tracker/quant/phase4/gate3_execution/campaign.py`, `artifacts.py`; test `tests/quant/test_phase4_gate3_execution_campaign.py`.

**Interfaces:** Consume exact `Gate2Authority`, `Phase4EngineManifest`, and Gate 3 preflight identity; produce `prepare_campaign_plan(...) -> tuple[CandidateReference, ...]` and `TrialEvidenceStore.write(record: TrialRecord) -> ArtifactIdentity`. Preparation does not load VALIDATION market bars or calculate candidate returns.

- [ ] **Step 1: RED tests.** Use sealed real identity-only authority and temporary output root. Assert exactly 180 immutable `(position,candidate_id,trial_id,family_id)` rows, positions 1–180, 180 unique candidate/trial IDs, fixed population digest, zero budget consumption. Inject duplicate/gap/181/mutated tuple and require fail-closed. Write synthetic `UNKNOWN` and `ABSTAIN` records with distinct reasons; verify content-addressed path/envelope, exact bytes, idempotent same-byte write, collision failure on changed bytes, no vanished failure record, and symlink/junction path rejection. Verify evidence never includes ranking/winner or provider/trading API.

```python
def test_campaign_plan_is_only_sealed_population(authority, gate2_manifest):
    rows = prepare_campaign_plan(authority, gate2_manifest)
    assert len(rows) == 180
    assert tuple(row.population_position for row in rows) == tuple(range(1, 181))
    assert len({row.trial_id for row in rows}) == 180
    assert all(row.status == "UNATTEMPTED" for row in rows)
```

- [ ] **Step 2: Demonstrate RED.** Run `pytest -q tests/quant/test_phase4_gate3_execution_campaign.py`; require missing API failure.
- [ ] **Step 3: Minimal GREEN.** Validate the pinned Gate 2 manifest's population digest/count and the exact grid order without generation. Define frozen, extra-forbidden typed records with `status` in `UNATTEMPTED, EXECUTED, UNKNOWN, ABSTAIN, SKIPPED_FAMILY_STOP` and mandatory nonempty reason for non-executed evidence. Use canonical JSON bytes, exact-byte SHA-256, canonical kind/path/content envelope, atomic hard-link create, and existing Gate 3 contained-path checks. No repository evidence is written by tests, only temporary artifacts.

```python
if tuple(item.population_position for item in rows) != tuple(range(1, 181)):
    raise ValueError("CANDIDATE_POPULATION_MISMATCH")
if len({item.trial_id for item in rows}) != 180:
    raise ValueError("CANDIDATE_POPULATION_MISMATCH")
```

- [ ] **Step 4: GREEN/regression.** Run focused test plus Gate 2 authority/evidence and Gate 3 seal tests; verify `git diff --check` and no historical result change.
- [ ] **Step 5: Commit.** `git add src/investment_tracker/quant/phase4/gate3_execution/campaign.py src/investment_tracker/quant/phase4/gate3_execution/artifacts.py tests/quant/test_phase4_gate3_execution_campaign.py`; `git commit -m "feat: prepare sealed Gate 3 population and evidence boundary"`.

### Task 4: Methodology identity, additive preflight, and quote-free CLI

**Files:** Create `src/investment_tracker/quant/phase4/gate3_execution/methodology.py`, `cli.py`; test `tests/quant/test_phase4_gate3_execution_methodology.py`.

**Interfaces:** Consume explicit corrected Gate 3 authority content digest and source revision; produce `seal_execution_methodology(repository_root: Path, source_revision: str) -> ArtifactIdentity` and `preflight_execution_methodology(repository_root: Path, manifest_content_sha256: str) -> MethodologyPreflight`. CLI has only `seal/preflight`, no candidate evaluation command.

- [ ] **Step 1: RED tests.** In a temporary contained repository fixture, pin exact spec bytes/envelope, Gate 1/Gate 2/Gate 3 authority manifests, population/TRAIN/VALIDATION identities, two canonical method records, runner source-bundle bytes/Git commit. Assert different method fields change digest; changed dependency/spec/source bytes fail closed; superseded Gate 3 manifest fails; extra/malformed/symlink/junction reference fails before read; `preflight` returns baseline/regime `BOUND`, Gate 3 `GATE3_CAMPAIGN_READY_TO_EXECUTE`, and safety false/zero without calling any strategy or data provider. Existing authority-only preflight output remains `READY` unchanged.

```python
def test_methodology_preflight_is_nonexecuting(repo_fixture, pinned_manifest):
    result = preflight_execution_methodology(repo_fixture, pinned_manifest)
    assert result.gate3 == "GATE3_CAMPAIGN_READY_TO_EXECUTE"
    assert result.baseline_methodology == "BOUND"
    assert result.regime_attribution_methodology == "BOUND"
    assert result.candidate_population == 180
    assert result.safety.candidate_executed is False
```

- [ ] **Step 2: Demonstrate RED.** Run `pytest -q tests/quant/test_phase4_gate3_execution_methodology.py`; require missing API failure.
- [ ] **Step 3: Minimal GREEN.** Build two canonical semantic method records from the committed spec, read exact spec bytes and canonical envelope, call existing `preflight_gate3()` with corrected pinned manifest, verify exact Gate 1/Gate 2/population/TRAIN/VALIDATION references, bind canonical SHA-256 of runner source files to a full ancestor Git commit and exact Git blob bytes, write method records first and combined manifest last via new append-only artifact store. Preflight accepts explicit combined manifest content hash only, validates all approved references before dereference, verifies bytes/envelopes/source, and returns a frozen safety state. No `run/evaluate` CLI subcommand exists.

```python
if preflight_gate3(root, CORRECTED_MANIFEST_CONTENT_SHA256).gate3 != "READY":
    raise ValueError("GATE3_AUTHORITY_MISMATCH")
if manifest.candidate_population_sha256 != POPULATION_SHA256:
    raise ValueError("CANDIDATE_POPULATION_MISMATCH")
```

- [ ] **Step 4: GREEN/regression.** Run focused test, all `tests/quant/test_phase4_gate3_*.py`, and Phase 4 regressions. Check no sealed file changed and no candidate performance was calculated.
- [ ] **Step 5: Commit implementation only.** `git add src/investment_tracker/quant/phase4/gate3_execution/methodology.py src/investment_tracker/quant/phase4/gate3_execution/cli.py tests/quant/test_phase4_gate3_execution_methodology.py`; `git commit -m "feat: bind Gate 3 execution methodology without campaign access"`.

### Task 5: Verification, independent review, and methodology evidence seal

**Files:** Add only newly generated `results/phase4/gate3/execution_methodology/` evidence after implementation review PASS. No source or earlier evidence mutation.

- [ ] **Step 1: Fresh tests.** Run all focused Gate 3 execution tests, Phase 4 regression tests, and `pytest -q tests/quant`; record exact pass/skip/failure counts. The unchanged Windows symlink security test must run normally.
- [ ] **Step 2: Fresh independent post-commit review.** Give reviewer the spec, plan, implementation commit range, test output, and access boundaries. Require 0 Critical/0 Important; fix genuine defects via new RED/GREEN cycle and commit before sealing.
- [ ] **Step 3: Evidence seal.** From a clean implementation HEAD, run quote-free `python -m investment_tracker.quant.phase4.gate3_execution.cli seal --repository-root . --source-revision <full implementation HEAD>`. Stage only new execution-methodology evidence, verify exact bytes and `git diff --cached --check`, and commit `evidence: seal Gate 3 execution methodology`.
- [ ] **Step 4: Final preflight/determinism.** Run the additive explicit-hash CLI preflight on the committed evidence twice and require identical output/identity; rerun the old Gate 3 authority-only preflight and require its `READY` unchanged. Check exact 180 identity-only rows, zero real candidate evaluation, no provider/holdout/protected/trading access, and clean git status.
- [ ] **Step 5: Stop/report.** Report spec path/commit, two method digests, combined manifest identity, implementation/evidence commits, focused/regression/full quant counts, two review verdicts, final `GATE3_CAMPAIGN_READY_TO_EXECUTE`, and all negative safety/access facts. Do not execute candidate #1 or start Phase 4 Gate 3 campaign.
