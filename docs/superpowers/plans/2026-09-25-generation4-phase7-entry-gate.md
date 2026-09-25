# Generation-4 Phase-7 Entry Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only Generation-4 Phase-7 readiness and entry gate that validates the frozen Phase-6 evidence chain and permits paper-only Phase-7 entry only after a separately created Independent Audit authorization.

**Architecture:** Add a Generation-4-specific verifier and CLI under `independent_audit.post_generation3`. The verifier first produces a non-authorizing readiness report from the frozen contract, acquisition authorization, receipt, release, result, marker, and closure; a separate strict authorization loader then binds that report, the implementation commit, source hashes, and audit request before an entry decision can be allowed. Existing Stage-B source files and private holdout bundle/key remain untouched.

**Tech Stack:** Python 3.12, Pydantic 2, pytest 8, hashlib/json/pathlib, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-25-generation4-phase7-entry-gate-design.md`

## Global Constraints

- Work from `governance/phase6-successor-dividend-normalization-v3`; preserve the corrected design commit `63b42826e2b24c39df8c2c607069a476e498ba4e`.
- Do not touch the unrelated untracked `.qwen/` directory.
- Do not modify `src/investment_tracker/independent_audit/post_generation3/stage_b_cli.py` or any Stage-B file whose SHA-256 is bound by `generation4-acquisition-authorization.json`.
- Do not run acquisition, release issuance, final-holdout evaluation, decryption, candidate search, parameter tuning, or symbol substitution.
- Do not read the encrypted bundle or key and do not call a provider or brokerage API.
- Phase-6 success status must equal `PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE`.
- Candidate, binding, implementation, holdout ID, release ID, and ordered symbols must match the frozen Generation-4 contract and every downstream field that carries them.
- `paper_only=true` is authoritative only through the frozen Phase-6 contract and Generation-4 acquisition authorization; do not demand that field from downstream schemas that do not define it.
- `dividend_reconciliation_sha256` is authoritative through the exact Phase-6 contract/acquisition-authorization binding; downstream artifacts are checked only for `successor_normalizer_sha256` and `successor_evaluator_sha256` where present.
- Missing or malformed evidence fails closed; Phase 7 must remain not started, production readiness false, live trading unauthorized, and `RECON-009=OPEN`.
- Coordinator code may load an Independent Audit authorization but must expose no function or command that creates, seals, signs, or writes one.
- No real Phase-7 authorization artifact may be created during implementation or audit-request preparation.

## Governance Requirement to RED-Test Map

| Requirement | RED test(s) before implementation |
|---|---|
| Exact Phase-6 status | `test_readiness_rejects_wrong_phase6_status` |
| One-time consumed | `test_readiness_rejects_unconsumed_result` |
| Phase 7 not started | `test_readiness_rejects_started_state` for result and closure |
| Production readiness false | `test_readiness_rejects_production_approval` across applicable layers |
| Closure eligibility true | `test_readiness_rejects_ineligible_closure` |
| Pre-audit Phase-7 authority false | `test_readiness_rejects_preexisting_phase7_authority` across applicable layers |
| Candidate/binding/implementation exact | `test_readiness_rejects_strategy_identity_drift` parameterized by field and artifact |
| Ordered locked symbols exact | `test_readiness_rejects_locked_symbol_drift` including order-only drift |
| Receipt → release → result → marker → closure hash chain | `test_readiness_rejects_hash_chain_tamper` parameterized by each link |
| Retry forbidden | `test_readiness_rejects_retry_authority` across contract, authorization, receipt, marker, and closure |
| Symbol substitution forbidden | `test_readiness_rejects_symbol_substitution` across contract, authorization, result, and closure |
| Holdout-dependent methodology/parameter changes forbidden | `test_readiness_rejects_result_dependent_change_authority` across result and closure |
| `RECON-009=OPEN` | `test_readiness_rejects_recon009_change` across applicable layers |
| No production/live-trading authority | `test_authorization_rejects_production_or_live_trading_authority`, `test_allowed_report_remains_nonproduction`, and static CLI/source tests |
| Paper-only propagation from upstream only | `test_readiness_accepts_upstream_paper_only_without_downstream_field` and `test_readiness_rejects_upstream_paper_only_change` |
| Dividend-v3 propagation from contract/authorization only | `test_readiness_accepts_dividend_binding_without_downstream_field` and `test_readiness_rejects_dividend_contract_authorization_mismatch` |
| Explicit Independent Audit authorization required | `test_entry_rejects_missing_authorization`, `test_entry_rejects_template`, and `test_entry_accepts_exact_independent_authorization` |
| Authorization is strict and content-bound | `test_authorization_rejects_unknown_field` plus request/source/commit/evidence mismatch parameterization |
| No protected operations or sensitive output | `test_cli_source_exposes_no_mutating_command`, `test_cli_forbidden_output_omits_metrics`, and workflow static checks |

## Review Focus

- A downstream artifact omits an upstream-only governance field: accept the omission only where the frozen schema does not define the field, while still proving the property upstream.
- A JSON file is valid but a byte changes: recompute hashes from bytes and reject every broken chain link.
- Symbols are equal as a set but reordered: reject because locked order is part of identity.
- The authorization binds valid-looking hashes from a different readiness request or implementation commit: reject exact-binding drift.
- A CLI error includes a nested result object: ensure performance keys and values are never serialized in success or failure output.

---

### Task 1: Build the synthetic terminal-chain fixture and first readiness slice

**Files:**
- Create: `tests/independent_audit/test_generation4_phase7_entry.py`
- Create: `src/investment_tracker/independent_audit/post_generation3/phase7_entry.py`

**Interfaces:**
- Consumes: existing `verify_phase6_contract`, `load_acquisition_authorization`, `load_receipt`, and `load_release` functions.
- Produces: `Generation4Phase7EntryError`, the keyword-only `verify_generation4_phase7_readiness` function returning `dict[str, Any]`, `READINESS_SCHEMA`, `READINESS_STATUS`, and stable error-code constants.

- [ ] **Step 1: Add a real-schema synthetic chain builder and write the first RED tests**

Create helpers with these exact interfaces in the test module:

```python
ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/generation4/phase6/evaluation-contract.json"
ACQUISITION_AUTHORIZATION = ROOT / "data/governance/successor/generation4-acquisition-authorization.json"
SELECTION = ROOT / "data/generation4/preaccess/holdout-selection.json"
ATTESTATION = ROOT / "data/generation4/preaccess/virginity-attestation.json"
EVIDENCE = ROOT / "data/generation4/preaccess/virginity-evidence.json"

def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()

def _canonical(value: dict[str, object]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

def _write(path: Path, value: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))
    return path
```

`_valid_chain` must load the frozen contract and acquisition authorization, construct a self-hashed receipt with the exact frozen receipt fields, derive the release ID using the production canonical seed, and then write a result, marker, and closure whose file hashes point to the actual temporary bytes. Deliberately omit `paper_only` and `dividend_reconciliation_sha256` from receipt, release, result, marker, and closure.

Build the fixture in this fixed order so each downstream digest is computed
from already-written bytes: contract/selection/attestation/evidence copies →
receipt plus `receipt_sha256` → release plus derived release ID → result →
marker with result hash → closure with contract/receipt/release/result/marker
hashes. Return a dictionary with the exact keys `contract`,
`acquisition_authorization`, `selection`, `virginity_attestation`,
`virginity_evidence`, `receipt`, `release`, `result`, `marker`, and `closure`.
`_readiness` passes those ten paths to
`verify_generation4_phase7_readiness` using the public keyword names in Step 3.

Add these tests before creating the source module:

```python
def test_readiness_accepts_upstream_paper_only_without_downstream_field(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    report = _readiness(paths)
    assert report["status"] == "GENERATION4_PHASE7_READY_FOR_INDEPENDENT_AUDIT"
    assert report["paper_only"] is True
    for name in ("receipt", "release", "result", "marker", "closure"):
        assert "paper_only" not in json.loads(paths[name].read_text(encoding="utf-8"))

def test_readiness_accepts_dividend_binding_without_downstream_field(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    report = _readiness(paths)
    contract = json.loads(paths["contract"].read_text(encoding="utf-8"))
    assert report["dividend_reconciliation_sha256"] == contract["methodology"]["dividend_reconciliation_sha256"]
    for name in ("receipt", "release", "result"):
        assert "dividend_reconciliation_sha256" not in json.loads(paths[name].read_text(encoding="utf-8"))

def test_readiness_rejects_dividend_contract_authorization_mismatch(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    contract = json.loads(paths["contract"].read_text(encoding="utf-8"))
    contract["methodology"]["dividend_reconciliation_sha256"] = "0" * 64
    _write(paths["contract"], contract)
    with pytest.raises(Generation4Phase7EntryError) as excinfo:
        _readiness(paths)
    assert excinfo.value.code == GEN4_PHASE7_IDENTITY_MISMATCH
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py
```

Expected: collection fails because `post_generation3.phase7_entry` does not exist. This is the required RED state.

- [ ] **Step 3: Implement strict loading, upstream verification, and the corrected propagation semantics**

Create the source module with these exact public signatures:

```python
class Generation4Phase7EntryError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(code if not detail else f"{code}:{detail}")
```

Implement `verify_generation4_phase7_readiness` with keyword-only `Path`
parameters named `phase6_contract_path`, `acquisition_authorization_path`,
`selection_path`, `virginity_attestation_path`, `virginity_evidence_path`,
`acquisition_receipt_path`, `release_path`, `phase6_result_path`,
`consumption_marker_path`, and `phase6_closure_path`, returning
`dict[str, Any]`.

Implementation order inside the function:

1. verify the v2 Generation-4 contract and exact frozen candidate, strategy, ordered symbols, governance booleans, and all three methodology identities;
2. load the v2 acquisition authorization against that contract and assert `paper_only is True` and exact three-way methodology equality;
3. call the existing receipt and release loaders;
4. load result, marker, and closure as dictionaries;
5. verify only `successor_normalizer_sha256` and `successor_evaluator_sha256` in downstream schemas that contain them;
6. verify the marker through contract/release/result identities rather than methodology fields;
7. return only identities, file hashes, and governance state—never metrics.

Catch `OSError`, `json.JSONDecodeError`, `ValueError`, and `SuccessorAcquisitionAuthorityError` at the appropriate boundary and map them to the stable Generation-4 error codes without treating any exception as readiness.

- [ ] **Step 4: Run the three tests and confirm GREEN**

Run:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py -k "upstream_paper_only or dividend_binding or dividend_contract_authorization_mismatch"
```

Expected: 3 passed.

- [ ] **Step 5: Commit the first readiness slice**

```powershell
git add -- src/investment_tracker/independent_audit/post_generation3/phase7_entry.py tests/independent_audit/test_generation4_phase7_entry.py
git diff --cached --check
git commit -m "feat: verify Generation 4 Phase 7 readiness evidence"
```

### Task 2: Complete fail-closed governance and hash-chain coverage

**Files:**
- Modify: `tests/independent_audit/test_generation4_phase7_entry.py`
- Modify: `src/investment_tracker/independent_audit/post_generation3/phase7_entry.py`

**Interfaces:**
- Consumes: `_valid_chain`, `_readiness`, and `verify_generation4_phase7_readiness` from Task 1.
- Produces: complete readiness enforcement for all 14 user requirements and the full receipt → release → result → marker → closure chain.

- [ ] **Step 1: Write the complete RED governance matrix**

Add individually named or parameterized tests using this exact case matrix:

| Test | Mutations | Expected code family |
|---|---|---|
| `test_readiness_rejects_wrong_phase6_status` | result status `None`, `PHASE6_UNKNOWN_ABSTAIN`, `PHASE6_COMPLETE` | `GEN4_PHASE7_GOVERNANCE_MISMATCH` |
| `test_readiness_rejects_unconsumed_result` | result `one_time_consumed=true→false` | `GEN4_PHASE7_GOVERNANCE_MISMATCH` |
| `test_readiness_rejects_started_state` | result `phase7_started=true`; closure `phase7.started=true` | `GEN4_PHASE7_GOVERNANCE_MISMATCH` |
| `test_readiness_rejects_production_approval` | contract, acquisition authorization, release, result, and closure production field `false→true` | governance or upstream identity failure |
| `test_readiness_rejects_ineligible_closure` | closure eligibility `true→false` | `GEN4_PHASE7_GOVERNANCE_MISMATCH` |
| `test_readiness_rejects_preexisting_phase7_authority` | contract, acquisition authorization, release, result, and closure authority `false→true` | governance or upstream identity failure |
| `test_readiness_rejects_strategy_identity_drift` | candidate, binding, and implementation fields, one artifact at a time | `GEN4_PHASE7_IDENTITY_MISMATCH` |
| `test_readiness_rejects_locked_symbol_drift` | replacement and order-only swap | `GEN4_PHASE7_IDENTITY_MISMATCH` |
| `test_readiness_rejects_hash_chain_tamper` | one byte in receipt, release, result, marker, and closure | `GEN4_PHASE7_CHAIN_MISMATCH` |
| `test_readiness_rejects_retry_authority` | contract, acquisition authorization, receipt, marker, and closure retry field | governance or upstream identity failure |
| `test_readiness_rejects_symbol_substitution` | contract, acquisition authorization, result, and closure substitution field | governance or upstream identity failure |
| `test_readiness_rejects_result_dependent_change_authority` | result candidate-search/parameter flags; closure methodology/parameter flags | `GEN4_PHASE7_GOVERNANCE_MISMATCH` |
| `test_readiness_rejects_recon009_change` | contract, acquisition authorization, release, result, and closure `OPEN→CLOSED` | governance or upstream identity failure |
| `test_readiness_rejects_upstream_paper_only_change` | contract and acquisition authorization `true→false` | governance or upstream identity failure |

Use this concrete pattern for result mutations; equivalent helpers apply to
other artifact shapes:

```python
def test_readiness_rejects_unconsumed_result(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    result = json.loads(paths["result"].read_text(encoding="utf-8"))
    result["one_time_consumed"] = False
    _write(paths["result"], result)
    with pytest.raises(Generation4Phase7EntryError) as excinfo:
        _readiness(paths)
    assert excinfo.value.code == GEN4_PHASE7_GOVERNANCE_MISMATCH
```

Mutation helpers must repair upstream hashes only when the test is targeting a semantic mismatch rather than a hash mismatch. Hash-chain tests must change raw bytes without repairing downstream hashes so the expected failure is specifically `GEN4_PHASE7_CHAIN_MISMATCH`.

- [ ] **Step 2: Run the matrix and confirm RED**

Run:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py
```

Expected: the new matrix fails because Task 1 does not yet enforce every downstream invariant and chain link.

- [ ] **Step 3: Implement exact field and chain validators**

Add focused private helpers rather than one monolithic conditional:

```python
def _require_equal(actual: object, expected: object, *, code: str, field: str) -> None:
    if actual != expected:
        raise Generation4Phase7EntryError(code, field)

def _require_false(value: object, *, field: str) -> None:
    _require_equal(value, False, code=GEN4_PHASE7_GOVERNANCE_MISMATCH, field=field)

def _require_true(value: object, *, field: str) -> None:
    _require_equal(value, True, code=GEN4_PHASE7_GOVERNANCE_MISMATCH, field=field)
```

Add `_verify_contract_and_authorization`, `_verify_result`, `_verify_marker`,
and `_verify_closure` with keyword-only dependencies. Each helper returns only
the verified dictionary/model it owns, compares every field listed in the
specification, and calls `_require_equal`, `_require_false`, or `_require_true`
so errors cannot silently fall through.

Use exact identity equality and list equality. Never convert locked symbols to sets. Require closure hash fields to equal hashes recomputed from actual files. Require result and closure pre-audit authority/start state to remain false, and require all retry/substitution/change flags in the schemas that carry them.

- [ ] **Step 4: Run focused and adjacent suites and confirm GREEN**

Run:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py tests/independent_audit/test_generation4_stage_b_boundary.py tests/quant/test_phase7_readiness.py tests/quant/test_generation2_phase7_entry.py
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit the completed readiness gate**

```powershell
git add -- src/investment_tracker/independent_audit/post_generation3/phase7_entry.py tests/independent_audit/test_generation4_phase7_entry.py
git diff --cached --check
git commit -m "test: enforce Generation 4 Phase 7 governance chain"
```

### Task 3: Add strict Independent Audit authorization and entry decision

**Files:**
- Modify: `tests/independent_audit/test_generation4_phase7_entry.py`
- Modify: `src/investment_tracker/independent_audit/post_generation3/phase7_entry.py`

**Interfaces:**
- Consumes: the readiness report and file paths from Tasks 1–2.
- Produces: `Generation4Phase7Authorization`, `load_generation4_phase7_authorization`, and `evaluate_generation4_phase7_entry` returning `dict[str, Any]`.

- [ ] **Step 1: Write RED authorization and entry tests**

Add helpers named `_audit_request` and `_authorization`; they accept the
temporary directory and readiness report, while `_authorization` also accepts
the request path and an optional overrides dictionary. Add this concrete first
test:

```python
def test_entry_rejects_missing_authorization(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    request = _audit_request(tmp_path, _readiness(paths))
    with pytest.raises(Generation4Phase7EntryError) as excinfo:
        _entry(paths, request, tmp_path / "missing-authorization.json")
    assert excinfo.value.code == GEN4_PHASE7_AUTHORIZATION_MISSING
```

Complete the RED set with `test_entry_rejects_template`,
`test_authorization_rejects_unknown_field`,
`test_authorization_rejects_binding_drift`,
`test_authorization_rejects_production_or_live_trading_authority`,
`test_entry_accepts_exact_independent_authorization`,
`test_allowed_report_remains_nonproduction`, and
`test_actual_repository_without_real_authorization_is_forbidden`.

Parameterize binding drift over implementation commit, request hash, gate hash,
CLI hash, candidate, binding, strategy implementation, all three methodology
hashes, ordered symbols, holdout/release IDs, and all six evidence hashes.
Every case must assert `GEN4_PHASE7_AUTHORIZATION_INVALID` for schema/literal
violations or `GEN4_PHASE7_AUTHORIZATION_MISMATCH` for valid-shaped but
incorrect bindings.

The synthetic authorization may be built in test memory and written to `tmp_path`; it is not repository governance evidence. The template rejection test uses a synthetic `DRAFT_TEMPLATE_NOT_AUTHORIZATION` payload until the real non-authorizing template is added after the implementation freeze.

- [ ] **Step 2: Run authorization tests and confirm RED**

Run:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py -k "authorization or entry or allowed_report"
```

Expected: failures because the authorization model and entry evaluator do not exist.

- [ ] **Step 3: Implement the strict authorization model and loader**

Define a Pydantic model with `ConfigDict(extra="forbid", frozen=True)` and exact literals:

```python
class Generation4Phase7Authorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["GENERATION4-PHASE7-ENTRY-AUTHORIZATION-v1"]
    authority: Literal["INDEPENDENT_AUDIT"]
    status: Literal["GENERATION4_PHASE7_ENTRY_AUTHORIZED"]
    authorization_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    signed_by: str = Field(min_length=1, max_length=256)
    approved_at_utc: str = Field(min_length=1)
    generation: Literal["GENERATION_4"]
    implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    audit_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_gate_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase7_cli_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_id: Literal["G2-A|lookback=189|skip=21|top_k=1|rebalance=21"]
    binding_sha256: Literal["fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"]
    implementation_sha256: Literal["35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"]
    split_normalizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dividend_reconciliation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locked_symbols: tuple[str, ...]
    holdout_id: str = Field(min_length=1)
    release_id: str = Field(min_length=1)
    phase6_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_consumption_marker_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase6_closure_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase6_status: Literal["PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"]
    one_time_consumed: Literal[True]
    phase7_entry_authorized: Literal[True]
    phase7_started: Literal[False]
    retry_authorized: Literal[False]
    holdout_reuse_authorized: Literal[False]
    candidate_search_authorized: Literal[False]
    symbol_substitution_authorized: Literal[False]
    result_dependent_methodology_change_allowed: Literal[False]
    result_dependent_parameter_change_allowed: Literal[False]
    production_readiness_approved: Literal[False]
    live_trading_authorized: Literal[False]
    recon009_status: Literal["OPEN"]
    paper_only: Literal[True]
```

Implement `load_generation4_phase7_authorization` with keyword-only
`authorization_path`, `audit_request_path`, `phase7_entry_path`,
`phase7_cli_path`, and `readiness` parameters. Implement
`evaluate_generation4_phase7_entry` with the two request/authorization paths,
optional source paths defaulting to the module and sibling CLI, and the same
ten explicit readiness paths used by the readiness verifier.

The loader must parse an exact audit-request schema with `authority_granted=false` and `phase7_authorized=false`, recompute its file hash, recompute the gate and CLI source hashes, and compare every authorization binding to the fresh readiness report. It must never write the authorization. The final report must keep `phase7_started=false`, production/live trading false, `RECON-009=OPEN`, and paper-only true.

- [ ] **Step 4: Run the complete test module and confirm GREEN**

Run:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py
```

Expected: all tests pass.

- [ ] **Step 5: Commit authorization verification without an authorization artifact**

```powershell
git add -- src/investment_tracker/independent_audit/post_generation3/phase7_entry.py tests/independent_audit/test_generation4_phase7_entry.py
git diff --cached --check
git commit -m "feat: require independent Generation 4 Phase 7 authority"
```

### Task 4: Add the read-only CLI and focused CI boundary

**Files:**
- Create: `src/investment_tracker/independent_audit/post_generation3/phase7_entry_cli.py`
- Modify: `tests/independent_audit/test_generation4_phase7_entry.py`
- Modify: `.github/workflows/successor-dividend-normalization-v3.yml`

**Interfaces:**
- Consumes: `verify_generation4_phase7_readiness` and `evaluate_generation4_phase7_entry`.
- Produces: `main(argv: list[str] | None = None) -> int` with only `verify-readiness` and `evaluate-entry` subcommands.

- [ ] **Step 1: Write RED CLI and static-boundary tests**

Add `test_cli_verify_readiness_emits_non_authorizing_report`,
`test_cli_evaluate_entry_requires_authorization`,
`test_cli_forbidden_output_omits_metrics`,
`test_cli_source_exposes_no_mutating_command`, and
`test_stage_b_bound_source_hashes_remain_frozen`.

The source test must contain these exact assertions:

```python
def test_cli_source_exposes_no_mutating_command():
    source = Path(phase7_entry_cli.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "acquire-final-holdout",
        "issue-final-holdout-release",
        "evaluate-final-holdout",
        "close-phase6",
        "OpenTradeContext",
        "place_order",
        "modify_order",
        "cancel_order",
        "unlock_trade",
    ):
        assert forbidden not in source
```

The source-boundary test must reject the strings `acquire-final-holdout`, `issue-final-holdout-release`, `evaluate-final-holdout`, `close-phase6`, `OpenTradeContext`, `place_order`, `modify_order`, `cancel_order`, and `unlock_trade` in the new CLI. It must also assert there is no authorization writer function such as `seal_generation4_phase7_authorization` or `write_generation4_phase7_authorization` in either new module.

- [ ] **Step 2: Run CLI tests and confirm RED**

Run:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py -k "cli or bound_source"
```

Expected: import or assertion failures because the CLI does not exist.

- [ ] **Step 3: Implement the two-command, no-write CLI**

Use required explicit path arguments shared by both commands:

```text
--phase6-contract
--acquisition-authorization
--selection
--virginity-attestation
--virginity-evidence
--acquisition-receipt
--release
--phase6-result
--consumption-marker
--phase6-closure
```

`evaluate-entry` additionally requires `--audit-request` and `--authorization`. Catch only `Generation4Phase7EntryError`; print canonical JSON containing `status="FORBIDDEN"`, `code`, and `detail`, and return `1`. Successful commands print their report and return `0`. Neither command accepts an output path.

- [ ] **Step 4: Extend focused CI**

Add `tests/independent_audit/test_generation4_phase7_entry.py` to the focused pytest command. Add the new verifier, CLI, and test file to the existing governance grep scope while preserving the protected-symbol and order/trading API checks. Do not add any private path or private artifact to CI.

- [ ] **Step 5: Run CLI, focused workflow-equivalent, and compile checks**

```powershell
python -m compileall -q src/investment_tracker/independent_audit/post_generation3
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py tests/independent_audit/test_generation4_stage_a_boundary.py tests/independent_audit/test_generation4_stage_b_boundary.py tests/independent_audit/test_post_generation3_authority.py tests/independent_audit/test_successor_dividend_evaluator_v3.py tests/quant/test_successor_corporate_actions_v2.py tests/quant/test_successor_dividend_reconciliation_v3.py
rg -n "OpenTradeContext|place_order|modify_order|cancel_order|unlock_trade|TrdEnv" src/investment_tracker/independent_audit/post_generation3/phase7_entry.py src/investment_tracker/independent_audit/post_generation3/phase7_entry_cli.py
```

Expected: compile exits 0, focused tests pass, and `rg` returns no matches.

- [ ] **Step 6: Commit and record the frozen implementation commit**

```powershell
git add -- src/investment_tracker/independent_audit/post_generation3/phase7_entry.py src/investment_tracker/independent_audit/post_generation3/phase7_entry_cli.py tests/independent_audit/test_generation4_phase7_entry.py .github/workflows/successor-dividend-normalization-v3.yml
git diff --cached --check
git commit -m "feat: add Generation 4 Phase 7 entry CLI"
git rev-parse HEAD
```

The full 40-character output is the implementation commit bound by the later audit request. Do not modify the two source modules after recording it; any fix requires a new implementation commit and regenerated request bindings.

### Task 5: Verify the repository and real private readiness without authorizing entry

**Files:**
- No file changes.

**Interfaces:**
- Consumes: the frozen implementation commit and existing private Generation-4 JSON evidence.
- Produces: fresh test evidence and one non-authorizing readiness JSON object for use in the audit request.

- [ ] **Step 1: Run the full test suite from the implementation commit**

```powershell
python -m pytest -q
```

Expected: zero failures. Report every failing test by name if the suite is not green; do not proceed to the audit request while any failure remains unexplained.

- [ ] **Step 2: Confirm Stage-B frozen source identities and tracked cleanliness**

Run the real Generation-4 acquisition-authorization loader test and inspect status:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_stage_b_boundary.py::test_valid_synthetic_generation4_stage_b_authorization_binds_full_runtime
git diff --check
git status --short
```

Expected: test passes; no tracked changes; only the pre-existing untracked `.qwen/` may appear.

- [ ] **Step 3: Run read-only readiness against the real JSON chain**

Use only the contract, acquisition authorization, selection/virginity JSON, receipt, release, result, marker, and closure paths. Do not provide the bundle or key:

```powershell
python -m investment_tracker.independent_audit.post_generation3.phase7_entry_cli verify-readiness --phase6-contract data/generation4/phase6/evaluation-contract.json --acquisition-authorization data/governance/successor/generation4-acquisition-authorization.json --selection data/generation4/preaccess/holdout-selection.json --virginity-attestation data/generation4/preaccess/virginity-attestation.json --virginity-evidence data/generation4/preaccess/virginity-evidence.json --acquisition-receipt "C:\Users\Caspar\Desktop\Investment-Tracker-Private\generation4\successor-phase6-holdout-e6aa1f4e9f04b2e905df7cc828c65669.receipt.json" --release "C:\Users\Caspar\Desktop\Investment-Tracker-Private\generation4\successor-phase6-holdout-e6aa1f4e9f04b2e905df7cc828c65669.release.json" --phase6-result "C:\Users\Caspar\Desktop\Investment-Tracker-Private\generation4\successor-phase6-holdout-e6aa1f4e9f04b2e905df7cc828c65669.phase6-result.json" --consumption-marker "C:\Users\Caspar\Desktop\Investment-Tracker-Private\generation4\evaluation-markers\successor-phase6-release-934966d25eef0b2bfb4b5de289539a05.consumed.json" --phase6-closure "C:\Users\Caspar\Desktop\Investment-Tracker-Private\generation4\successor-phase6-holdout-e6aa1f4e9f04b2e905df7cc828c65669.phase6-closure.json"
```

Expected: `GENERATION4_PHASE7_READY_FOR_INDEPENDENT_AUDIT`, `authority_granted=false`, `phase7_authorized=false`, production/live trading false, `RECON-009=OPEN`, and no metrics in output.

- [ ] **Step 4: Prove the real repository remains forbidden without authorization**

Run `evaluate-entry` with the future authorization path absent after the request exists, or exercise the dedicated test before request creation. Expected: nonzero with `GEN4_PHASE7_AUTHORIZATION_MISSING`; no file is written.

### Task 6: Create the non-authorizing Independent Audit handoff after the implementation freeze

**Files:**
- Create: `data/governance/successor/generation4-phase7-entry-authorization.template.json`
- Create: `data/governance/successor/generation4-phase7-entry-independent-audit-request.json`
- Create: `docs/superpowers/requests/2026-09-25-generation4-phase7-entry-independent-audit-request.md`
- Modify: `tests/independent_audit/test_generation4_phase7_entry.py`
- Modify: `.github/workflows/successor-dividend-normalization-v3.yml`

**Interfaces:**
- Consumes: frozen implementation commit, gate/CLI source hashes, corrected design, and real readiness report.
- Produces: a non-authorizing template and audit request; no `GENERATION4-PHASE7-ENTRY-AUTHORIZATION-v1` artifact.

- [ ] **Step 1: Write RED repository-artifact tests**

Add constants for the committed template and request paths, then implement
`test_committed_phase7_template_cannot_authorize_entry`,
`test_committed_phase7_request_is_non_authorizing_and_binds_implementation`,
and `test_real_repository_entry_stays_forbidden_without_authorization`.

The request assertion core is:

```python
request = json.loads(REQUEST.read_text(encoding="utf-8"))
assert request["schema_version"] == "GENERATION4-PHASE7-ENTRY-INDEPENDENT-AUDIT-REQUEST-v1"
assert request["status"] == "READY_FOR_INDEPENDENT_AUDIT"
assert request["authority_granted"] is False
assert request["phase7_authorized"] is False
assert request["production_readiness_approved"] is False
assert request["live_trading_authorized"] is False
assert request["recon009_status"] == "OPEN"
assert request["paper_only"] is True
```

The request test must assert the exact implementation commit from Task 4, actual gate/CLI hashes, actual evidence hashes from Task 5, `authority_granted=false`, `phase7_authorized=false`, `production_readiness_approved=false`, `live_trading_authorized=false`, `recon009_status="OPEN"`, and `paper_only=true`.

- [ ] **Step 2: Run the three tests and confirm RED**

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py -k "committed_phase7 or real_repository_entry"
```

Expected: failures because the template and request do not exist.

- [ ] **Step 3: Create the template and machine-readable request**

Use `apply_patch`. The template must have:

```json
{
  "schema_version": "GENERATION4-PHASE7-ENTRY-AUTHORIZATION-TEMPLATE-v1",
  "status": "DRAFT_TEMPLATE_NOT_AUTHORIZATION",
  "authority": "NONE",
  "note": "Independent Audit must create a separate GENERATION4-PHASE7-ENTRY-AUTHORIZATION-v1 artifact. This template grants no Phase-7, production, live-trading, retry, substitution, search, methodology-change, or parameter-change authority.",
  "required_schema": "GENERATION4-PHASE7-ENTRY-AUTHORIZATION-v1"
}
```

The request must use schema `GENERATION4-PHASE7-ENTRY-INDEPENDENT-AUDIT-REQUEST-v1`, status `READY_FOR_INDEPENDENT_AUDIT`, and exact computed values—never placeholder strings—for the implementation commit, gate/CLI hashes, all three methodology hashes, ordered symbols, holdout/release IDs, and six evidence-file hashes. It must remain non-authorizing.

- [ ] **Step 4: Create the Markdown audit request and exact auditor prompt**

The Markdown request must state the reviewed implementation commit and source hashes; enumerate every evidence-chain and governance check from the specification; state that downstream schemas do not carry `paper_only` or direct dividend-v3 identity unless frozen fields exist; forbid bundle/key reads and all reruns; and instruct the auditor to either reject with exact blockers or create a separate authorization artifact matching the strict schema.

End the document with a fenced prompt that can be copied verbatim. The prompt must identify the repository, branch, implementation commit, request path, template path, private JSON evidence paths, audit scope, forbidden actions, required tests, and exact authorized output path. It must explicitly say that the auditor—not the coordinator—owns any real authorization decision.

- [ ] **Step 5: Update CI paths and run GREEN verification**

Add the template, JSON request, and Markdown request paths to the workflow triggers. Then run:

```powershell
python -m pytest -q tests/independent_audit/test_generation4_phase7_entry.py
python -m pytest -q
git diff --check
```

Expected: focused and full suites pass, and whitespace validation succeeds.

- [ ] **Step 6: Commit only the audit handoff artifacts and their tests/CI bindings**

```powershell
git add -- data/governance/successor/generation4-phase7-entry-authorization.template.json data/governance/successor/generation4-phase7-entry-independent-audit-request.json docs/superpowers/requests/2026-09-25-generation4-phase7-entry-independent-audit-request.md tests/independent_audit/test_generation4_phase7_entry.py .github/workflows/successor-dividend-normalization-v3.yml
git diff --cached --check
git commit -m "audit: request Generation 4 Phase 7 entry review"
git rev-parse HEAD
```

Confirm the commit contains no real authorization file and no private evidence. Report both the frozen implementation commit and audit-request commit, then provide the exact prompt from the request document. Stop without running `evaluate-entry` successfully and without marking Phase 7 started.
