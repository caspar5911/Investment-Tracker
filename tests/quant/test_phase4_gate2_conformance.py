from __future__ import annotations

import json
import io
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError
from tests.quant.gate2_boundary_guard import (
    Gate2FilesystemBoundaryGuard,
    Gate2FilesystemViolation,
)

try:
    import investment_tracker.quant.phase4.engine.conformance as _conformance_module

    ConformanceInvariant = _conformance_module.ConformanceInvariant
    SyntheticConformanceRecord = _conformance_module.SyntheticConformanceRecord
    run_synthetic_conformance = _conformance_module.run_synthetic_conformance
    _CONFORMANCE_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as _exc:  # pragma: no cover - RED marker
    ConformanceInvariant = None
    SyntheticConformanceRecord = None
    run_synthetic_conformance = None
    _CONFORMANCE_IMPORT_ERROR = _exc

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SYMBOLS = ("SYN-ALPHA", "SYN-BETA", "SYN-DELTA", "SYN-EPSTEIN", "SYN-GAMMA", "SYN-ZETA")
WARMUP_SESSIONS = 300
SCORED_SESSIONS = 400
START_DATE = "2035-01-01"
BASE_PRICE = 100.0
WAVE_AMPLITUDE = 0.25
DAILY_DRIFT = 0.0005
PROTECTED_SYMBOLS = ("HACK", "SOXX", "NLR", "URNM", "GEV")
EXPECTED_INVARIANT_NAMES = (
    "ALL_BINDINGS_CONSTRUCT",
    "TARGET_GENERATION_REBALANCE_CLOCK",
    "REPLAY_ACCOUNTING",
    "FRICTION_CASES",
    "METRICS",
    "DURABILITY",
    "BOOTSTRAP",
    "BUDGET_STATE_MACHINE",
    "FOLD_AUTHORITY_UNBOUND",
    "REGIME_AUTHORITY_UNBOUND",
    "BASELINE_COMPARISON_ONLY",
    "STATIC_SCAN",
)
FORBIDDEN_BOUNDARY_RELATIVE_PATHS = (
    "data/HACK.csv",
    "data/market_bars.csv",
    "results/latest.json",
    "results/phase4/validation_results.json",
    "FINAL_HOLDOUT/GEV.parquet",
    "providers/source.py",
    "cache/provider-response.json",
    "dynamic/discovery.json",
    "results/phase4/gate2/latest.json",
    "results/phase4/gate2/HACK.csv",
    "results/phase4/gate2/market_bars.csv",
    "results/phase4/gate2/validation_results.json",
    "results/phase4/gate2/providers/source.py",
    "results/phase4/gate2/cache/data.json",
    "results/phase4/gate2/dynamic/discovery.json",
)


def _filesystem_guard(root: Path) -> Gate2FilesystemBoundaryGuard:
    from investment_tracker.quant.phase4.engine.authority import (
        PINNED_DIRECT_DEPENDENCIES,
    )
    from investment_tracker.quant.phase4.engine.source_identity import (
        GATE2_SOURCE_BUNDLES,
    )

    return Gate2FilesystemBoundaryGuard(
        root=root,
        source_paths=(root / path for path in GATE2_SOURCE_BUNDLES["engine"]),
        authority_paths=(root / item.path for item in PINNED_DIRECT_DEPENDENCIES),
        generated_root=root / "results" / "phase4" / "gate2",
        source_discovery_roots=(
            root
            / "src"
            / "investment_tracker"
            / "quant"
            / "phase4"
            / "engine",
        ),
    )


def _require_direct_guard_rejection(operation: Any, *, kind: str) -> None:
    try:
        operation()
    except Gate2FilesystemViolation as exc:
        if str(exc).startswith(f"forbidden filesystem {kind}:"):
            return
        raise
    except Exception as exc:
        raise AssertionError(
            f"boundary guard failed before {kind} rejection"
        ) from exc
    raise AssertionError(f"boundary guard failed to reject {kind}")


@pytest.fixture(autouse=True)
def require_conformance_types(request: pytest.FixtureRequest) -> None:
    if _CONFORMANCE_IMPORT_ERROR is not None and (
        "test_conformance_types_are_available" not in request.node.name
    ):
        pytest.skip(f"Gate 2 conformance unavailable: {_CONFORMANCE_IMPORT_ERROR}")


@pytest.fixture(scope="module")
def authority() -> Any:
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )

    return load_gate2_authority(REPOSITORY_ROOT)


@pytest.fixture(scope="module")
def market_input() -> Any:
    from investment_tracker.quant.phase4.engine.market import (
        MarketPanel,
        ScoredMarketInput,
    )

    sessions = pd.date_range(START_DATE, periods=WARMUP_SESSIONS + SCORED_SESSIONS, freq="D", tz="UTC")
    rows: list[list[float]] = []
    for index in range(WARMUP_SESSIONS + SCORED_SESSIONS):
        row = []
        for symbol_index in range(len(SYMBOLS)):
            price = (
                BASE_PRICE
                * (1.0 + 0.05 * symbol_index)
                * (
                    1.0
                    + WAVE_AMPLITUDE
                    * np.sin(0.03 * index + 0.5 * symbol_index)
                    + DAILY_DRIFT * index
                )
            )
            row.append(price)
        rows.append(row)
    closes = pd.DataFrame(rows, index=sessions, columns=SYMBOLS)
    opens = closes.shift(1)
    opens.iloc[0] = closes.iloc[0]
    split = WARMUP_SESSIONS
    warmup = MarketPanel.from_frames(
        opens.iloc[:split], closes.iloc[:split], role="WARMUP"
    )
    scored = MarketPanel.from_frames(
        opens.iloc[split:], closes.iloc[split:], role="SCORED"
    )
    return ScoredMarketInput.from_panels(warmup, scored)


def _bundle_set(authority: Any, market_input: Any) -> dict[str, Any]:
    del market_input
    from investment_tracker.quant.phase4.engine.source_identity import (
        GATE2_SOURCE_BUNDLES,
        source_bundle_identity,
    )

    return {
        name: source_bundle_identity(
            REPOSITORY_ROOT, authority.head_revision, tuple(paths)
        )
        for name, paths in GATE2_SOURCE_BUNDLES.items()
    }


def _bundle_names(bundles: dict[str, Any]) -> list[str]:
    from investment_tracker.quant.phase4.engine.source_identity import (
        GATE2_SOURCE_BUNDLES,
    )

    assert set(bundles) == set(GATE2_SOURCE_BUNDLES)
    return list(GATE2_SOURCE_BUNDLES)


def test_conformance_types_are_available() -> None:
    assert _CONFORMANCE_IMPORT_ERROR is None, str(_CONFORMANCE_IMPORT_ERROR)
    assert callable(run_synthetic_conformance)
    assert SyntheticConformanceRecord is not None


def test_panel_symbols_are_never_protected_or_market_symbols(market_input) -> None:
    assert market_input.scored.symbols == SYMBOLS
    assert not set(SYMBOLS) & set(PROTECTED_SYMBOLS)
    first_session = market_input.scored.sessions[0]
    assert first_session.year >= 2035


def test_synthetic_conformance_record_fields(market_input) -> None:
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )

    authority = load_gate2_authority(REPOSITORY_ROOT)
    bundles = _bundle_set(authority, market_input)
    record = run_synthetic_conformance(authority, bundles)

    assert isinstance(record, SyntheticConformanceRecord)
    assert record.label == "SYNTHETIC_CONFORMANCE_ONLY"
    assert record.phase4_trials_consumed == 0
    assert record.candidate_count == 180
    assert record.family_count == 4
    assert record.fold_authority_status == "FOLD_AUTHORITY_MISSING"
    assert record.regime_authority_status == "REGIME_AUTHORITY_MISSING"
    assert record.execution_convention == "COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN"
    assert record.execution_series == "QFQ_NORMALIZED"
    assert record.decision_grade is False
    assert record.warmup_panel_sha256 == market_input.warmup_panel_sha256
    assert record.scored_panel_sha256 == market_input.scored_panel_sha256
    expected_config = {
        "schema_version": "PHASE4-SYNTHETIC-CONFORMANCE-v1",
        "symbols": list(SYMBOLS),
        "warmup_sessions": WARMUP_SESSIONS,
        "scored_sessions": SCORED_SESSIONS,
        "start_date": START_DATE,
        "base_price": BASE_PRICE,
        "wave_amplitude": WAVE_AMPLITUDE,
        "daily_drift": DAILY_DRIFT,
    }
    from investment_tracker.quant.phase4.preregistration.canonical import (
        canonical_sha256,
    )

    assert record.fixture_configuration_sha256 == canonical_sha256(
        expected_config
    )
    digest_fields = (
        "synthetic_target_sha256",
        "synthetic_replay_sha256",
        "synthetic_metric_sha256",
        "synthetic_durability_sha256",
        "synthetic_bootstrap_sha256",
        "synthetic_budget_sha256",
    )
    for field_name in digest_fields:
        value = getattr(record, field_name)
        assert len(value) == 64
        assert set(value) <= set("0123456789abcdef")
    names = tuple(item.name for item in record.invariants)
    assert names == EXPECTED_INVARIANT_NAMES
    assert all(item.status == "PASS" for item in record.invariants)
    expected_bundle_values = tuple(
        (name, bundles[name].bundle_sha256)
        for name in sorted(_bundle_names(bundles))
    )
    assert tuple(record.source_bundle_sha256s) == expected_bundle_values
    assert record.safety == authority.safety
    assert record.unavailable_statistics.max_drawdown is None
    assert record.unavailable_statistics.dsr_reason == "NOT_IMPLEMENTED"


def test_record_carries_no_candidate_performance_or_selection_fields(
    market_input,
) -> None:
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )

    authority = load_gate2_authority(REPOSITORY_ROOT)
    bundles = _bundle_set(authority, market_input)
    record = run_synthetic_conformance(authority, bundles)

    fields = SyntheticConformanceRecord.model_fields
    forbidden_tokens = ("return", "rank", "eligib", "winner", "survivor", "score")
    for field_name in fields:
        lowered = field_name.lower()
        for token in forbidden_tokens:
            assert token not in lowered, f"{field_name} leaks {token}"
    data = record.model_dump()
    data["candidate_returns"] = (0.1,)
    with pytest.raises(ValidationError):
        SyntheticConformanceRecord.model_validate(data)


def test_synthetic_conformance_is_deterministic(market_input) -> None:
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )

    authority = load_gate2_authority(REPOSITORY_ROOT)
    bundles = _bundle_set(authority, market_input)
    first = run_synthetic_conformance(authority, bundles)
    second = run_synthetic_conformance(authority, bundles)
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_synthetic_output_digest_uses_a_canonical_output_envelope() -> None:
    identity = _conformance_module.synthetic_output_identity(
        "target", {"sequence": ["one", None], "version": 1}
    )

    assert identity == "9bc2f4653fd294e59f78e9da54315257a2aa33e73796bf0e44e23ba9adc3b4b9"


def test_bundle_set_missing_key_is_rejected(market_input) -> None:
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )
    from investment_tracker.quant.phase4.engine.models import Gate2SealError

    authority = load_gate2_authority(REPOSITORY_ROOT)
    bundles = _bundle_set(authority, market_input)
    del bundles["budget"]
    with pytest.raises(Gate2SealError) as excinfo:
        run_synthetic_conformance(authority, bundles)
    assert excinfo.value.code == "INPUT_BOUNDARY_VIOLATION"


def test_bundle_set_wrong_path_membership_is_rejected(market_input) -> None:
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )
    from investment_tracker.quant.phase4.engine.models import Gate2SealError
    from investment_tracker.quant.phase4.engine.source_identity import (
        GATE2_SOURCE_BUNDLES,
        SourceBundleEntry,
        SourceBundleIdentity,
    )
    from investment_tracker.quant.phase4.preregistration.canonical import (
        canonical_sha256,
    )

    authority = load_gate2_authority(REPOSITORY_ROOT)
    bundles = _bundle_set(authority, market_input)
    correct_paths = tuple(GATE2_SOURCE_BUNDLES["metric"])
    wrong_paths = ("src/investment_tracker/quant/phase4/engine/market.py",)
    entries = tuple(
        SourceBundleEntry(
            path=path, git_blob="1" * 40, content_sha256="2" * 64
        )
        for path in wrong_paths
    )
    digest = canonical_sha256(
        {
            "schema_version": "PHASE4-SOURCE-BUNDLE-v1",
            "producing_revision": "3" * 40,
            "entries": {
                path: {"git_blob": "1" * 40, "content_sha256": "2" * 64}
                for path in wrong_paths
            },
        }
    )
    assert correct_paths  # keep the reference explicit
    forged = SourceBundleIdentity(
        producing_revision="3" * 40,
        entries=entries,
        bundle_sha256=digest,
    )
    bundles["metric"] = forged
    with pytest.raises(Gate2SealError) as excinfo:
        run_synthetic_conformance(authority, bundles)
    assert excinfo.value.code == "IMPLEMENTATION_BINDING_MISMATCH"


def test_no_external_seams_are_reachable_during_conformance(
    market_input,
    monkeypatch,
) -> None:
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )

    authority = load_gate2_authority(REPOSITORY_ROOT)
    bundles = _bundle_set(authority, market_input)
    guard = _filesystem_guard(REPOSITORY_ROOT)
    guard.install(monkeypatch)

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("forbidden external seam reached during conformance")

    monkeypatch.setattr("subprocess.run", refuse)
    import socket
    import urllib.request

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)

    original_static_scan = _conformance_module._assert_static_scan_clean

    def injected_forbidden_read() -> None:
        for relative in FORBIDDEN_BOUNDARY_RELATIVE_PATHS:
            def read_probe(relative: str = relative) -> None:
                with io.open(REPOSITORY_ROOT / relative, "rb"):
                    pass

            _require_direct_guard_rejection(read_probe, kind="read")
        original_static_scan()

    monkeypatch.setattr(
        _conformance_module, "_assert_static_scan_clean", injected_forbidden_read
    )
    run_synthetic_conformance(authority, bundles)
    monkeypatch.setattr(
        _conformance_module, "_assert_static_scan_clean", original_static_scan
    )

    def injected_forbidden_discovery() -> None:
        for relative in FORBIDDEN_BOUNDARY_RELATIVE_PATHS:
            def discovery_probe(relative: str = relative) -> None:
                tuple((REPOSITORY_ROOT / relative).iterdir())

            _require_direct_guard_rejection(discovery_probe, kind="discovery")
        original_static_scan()

    monkeypatch.setattr(
        _conformance_module,
        "_assert_static_scan_clean",
        injected_forbidden_discovery,
    )
    run_synthetic_conformance(authority, bundles)
    monkeypatch.setattr(
        _conformance_module, "_assert_static_scan_clean", original_static_scan
    )

    record = run_synthetic_conformance(authority, bundles)
    dump = json.loads(record.model_dump_json())
    rendered = json.dumps(dump)
    for symbol in PROTECTED_SYMBOLS:
        assert symbol not in rendered
    assert "SYN-" in rendered
    assert guard.read_paths
    assert guard.discovery_paths


def test_boundary_oracle_fails_when_read_or_discovery_guard_is_permissive(
    monkeypatch,
    tmp_path: Path,
) -> None:
    unauthorized_file = tmp_path / "data" / "HACK.csv"
    unauthorized_file.parent.mkdir()
    unauthorized_file.write_bytes(b"unauthorized")
    unauthorized_directory = tmp_path / "providers"
    unauthorized_directory.mkdir()
    for method, kind, operation in (
        (
            "_read",
            "read",
            lambda: io.open(unauthorized_file, "rb"),
        ),
        (
            "_discovery",
            "discovery",
            lambda: tuple(unauthorized_directory.iterdir()),
        ),
    ):
        guard = _filesystem_guard(REPOSITORY_ROOT)
        guard.install(monkeypatch)
        monkeypatch.setattr(guard, method, lambda *args: None)
        with pytest.raises(AssertionError, match="boundary guard failed"):
            _require_direct_guard_rejection(operation, kind=kind)
        monkeypatch.undo()


def test_boundary_oracle_rejects_a_fallback_that_spoofs_guard_error() -> None:
    def fallback() -> None:
        raise AssertionError("forbidden filesystem read: fallback")

    with pytest.raises(AssertionError, match="boundary guard failed before read rejection"):
        _require_direct_guard_rejection(fallback, kind="read")


def test_generated_root_allows_only_content_addressed_gate2_artifacts() -> None:
    from investment_tracker.quant.phase4.engine.models import GATE2_ARTIFACT_FILENAMES

    guard = _filesystem_guard(REPOSITORY_ROOT)
    generated = REPOSITORY_ROOT / "results" / "phase4" / "gate2"
    digest = "a" * 64
    for kind, filename in GATE2_ARTIFACT_FILENAMES.items():
        guard._read(generated / kind / "sha256" / digest / filename)
        guard._read(generated / kind / "sha256" / digest / ".tmp-gate2-abcdefgh")

    rejected = (
        "latest/sha256/{digest}/manifest.json",
        "HACK/sha256/{digest}/bars.csv",
        "market_bars/sha256/{digest}/bars.csv",
        "validation/sha256/{digest}/results.json",
        "provider/sha256/{digest}/source.py",
        "cache/sha256/{digest}/response.json",
        "dynamic/sha256/{digest}/discovery.json",
        "engine_contract/sha256/{digest}/wrong.json",
        "engine_contract/sha256/{digest}/.tmp-gate2-not-a-temp",
        "engine_contract/sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/contract.json",
        "engine_contract/sha256/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/contract.json",
        "engine_contract/not-sha256/{digest}/contract.json",
        "engine_contract/sha256/{digest}/nested/contract.json",
    )
    for relative in rejected:
        with pytest.raises(Gate2FilesystemViolation, match="forbidden filesystem read"):
            guard._read(generated / relative.format(digest=digest))

    rejected_directories = (
        "engine_contract/FINAL_HOLDOUT/{digest}",
        "engine_contract/provider/{digest}",
        "engine_contract/cache/{digest}",
        "engine_contract/latest/{digest}",
    )
    for relative in rejected_directories:
        with pytest.raises(
            Gate2FilesystemViolation, match="forbidden filesystem discovery"
        ):
            guard._discovery("iterdir", generated / relative.format(digest=digest))


def test_budget_state_machine_transitions_are_inert() -> None:
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )
    from investment_tracker.quant.phase4.engine.budget import BudgetState
    from investment_tracker.quant.phase4.engine.models import Gate2SealError

    authority = load_gate2_authority(REPOSITORY_ROOT)
    fresh = BudgetState.from_authority(authority)
    assert fresh.phase4_new_trials_consumed == 0
    assert fresh.phase4_new_trials_remaining == 3000
    assert fresh.next_consumption_ordinal == 1
    assert fresh.traversal_cursor == 0
    with pytest.raises(Gate2SealError) as excinfo:
        fresh.record_candidate_outcome(1.0)
    assert excinfo.value.code == "BUDGET_ACCOUNTING_INVALID"

    first_trial = fresh.trial_ids[0]
    consumed = fresh.consume_current(first_trial)
    assert consumed.phase4_new_trials_consumed == 1
    assert consumed.consumption_ordinals[0] == 1
    assert consumed.phase4_new_trials_consumed + consumed.phase4_new_trials_remaining == 3000
    advanced = consumed.record_candidate_outcome(0.01)
    assert advanced.traversal_cursor == 1
    assert advanced.oos_streak == 0

    stopped = consumed
    for _ in range(50):
        stopped = stopped.consume_current(stopped.trial_ids[stopped.traversal_cursor]).record_candidate_outcome(None)
    assert stopped.last_family_reason == "PERSISTENT_OOS_FAILURE"
    assert stopped.oos_streak == 0
    assert stopped.row_states[50] == "SKIPPED_FAMILY_STOP"
    assert stopped.campaign_status == "ACTIVE"

    exhausted = BudgetState.from_authority(authority)
    for _ in range(54):
        exhausted = exhausted.consume_current(
            exhausted.trial_ids[exhausted.traversal_cursor]
        ).record_candidate_outcome(0.01)
    assert exhausted.last_family_reason == "EXHAUSTED_GRID"
    assert exhausted.active_family_index == 1
    assert exhausted.traversal_cursor == 54

    failed = BudgetState.from_authority(authority).fail_campaign()
    assert failed.campaign_status == "CAMPAIGN_EXECUTION_FAILED"
    assert failed.campaign_terminated is True


def test_family_without_candidates_fails_closed() -> None:
    import types

    from investment_tracker.quant.phase4.engine.conformance import (
        _representative_candidate,
    )
    from investment_tracker.quant.phase4.engine.models import Gate2SealError

    family = types.SimpleNamespace(family_id="family:conformance_fixture")
    with pytest.raises(Gate2SealError) as excinfo:
        _representative_candidate((), family)
    assert excinfo.value.code == "FIXED_STRATEGY_INVARIANT_FAILURE"
