from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

try:
    import investment_tracker.quant.phase4.engine.seal as _seal_module
    from investment_tracker.quant.phase4.engine.artifacts import Gate2ArtifactStore
    from investment_tracker.quant.phase4.engine.authority import (
        load_gate2_authority,
    )
    from investment_tracker.quant.phase4.engine.conformance import (
        SyntheticConformanceRecord,
    )
    from investment_tracker.quant.phase4.engine.models import (
        CandidateBindingSet,
        DirectDependencyIdentity,
        EngineContract,
        FamilyBindingSet,
        Gate2ArtifactIdentity,
        Gate2SealError,
        Gate2SealResult,
        Phase4EngineManifest,
    )
    from investment_tracker.quant.phase4.engine.source_identity import (
        GATE2_SOURCE_BUNDLES,
        source_bundle_identity,
    )

    seal_gate2 = _seal_module.seal_gate2
    _SEAL_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as _exc:  # pragma: no cover - RED marker
    _seal_module = None
    seal_gate2 = None
    _SEAL_IMPORT_ERROR = _exc


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GATE2_RESULTS = REPOSITORY_ROOT / "results" / "phase4" / "gate2"
STARTING_REVISION = "fb1c30a6c9789bddf2033301977fc8e2f3ebc1a0"
GATE1_MANIFEST_CONTENT_SHA256 = (
    "dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89"
)
NON_FINAL_KINDS = (
    "engine_contract",
    "family_implementation_bindings",
    "candidate_implementation_bindings",
    "synthetic_conformance",
    "phase4_engine_report",
)
WRITE_ORDER = NON_FINAL_KINDS + ("phase4_engine_manifest",)


@pytest.fixture(autouse=True)
def require_seal_types(request: pytest.FixtureRequest) -> None:
    if _SEAL_IMPORT_ERROR is not None and (
        "test_seal_types_are_available" not in request.node.name
    ):
        pytest.skip(f"Gate 2 seal unavailable: {_SEAL_IMPORT_ERROR}")


@pytest.fixture(scope="module")
def sealed_engine() -> Any:
    preexisting = GATE2_RESULTS.exists()
    result = seal_gate2(REPOSITORY_ROOT)
    try:
        yield result
    finally:
        if not preexisting and GATE2_RESULTS.exists():
            shutil.rmtree(GATE2_RESULTS)


def test_seal_types_are_available() -> None:
    assert _SEAL_IMPORT_ERROR is None, str(_SEAL_IMPORT_ERROR)
    assert callable(seal_gate2)


def _head_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        env={
            "GIT_CONFIG_GLOBAL": "NUL",
            "GIT_CONFIG_SYSTEM": "NUL",
            "HOME": str(REPOSITORY_ROOT),
        },
    ).stdout.decode("ascii").strip()


def _store() -> "Gate2ArtifactStore":
    return Gate2ArtifactStore(REPOSITORY_ROOT, REPOSITORY_ROOT / "results")


def _manifest_of(result: Any) -> "Phase4EngineManifest":
    payload = _store().verify(result.manifest)
    return Phase4EngineManifest.model_validate(json.loads(payload))


def test_seal_manifest_schema_status_and_bound_identities(sealed_engine) -> None:
    result: Gate2SealResult = sealed_engine
    assert result.status == "SEALED"
    assert result.manifest.kind == "phase4_engine_manifest"
    manifest = _manifest_of(result)
    assert manifest.schema_version == "PHASE4-ENGINE-MANIFEST-v1"
    assert manifest.status == "SEALED"
    assert manifest.starting_revision == STARTING_REVISION
    assert manifest.head_revision == _head_revision()
    assert manifest.gate1_manifest.content_sha256 == (
        GATE1_MANIFEST_CONTENT_SHA256
    )
    assert manifest.runtime.python_implementation == (
        platform.python_implementation()
    )
    assert manifest.runtime.python_version == platform.python_version()
    assert manifest.runtime.platform == sys.platform
    assert manifest.execution_convention == "COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN"
    assert manifest.execution_series == "QFQ_NORMALIZED"
    assert manifest.primary_friction_bps == 3
    assert manifest.decision_grade is False
    assert manifest.family_count == 4
    assert manifest.candidate_count == 180
    assert manifest.historical_phase2_trials == 136
    assert manifest.phase4_trials_consumed == 0
    assert manifest.fold_status == "FOLD_AUTHORITY_MISSING"
    assert manifest.regime_status == "REGIME_AUTHORITY_MISSING"
    unavailable = manifest.unavailable_statistics
    assert (
        unavailable.max_drawdown is None
        and unavailable.calmar is None
        and unavailable.dsr is None
        and unavailable.pbo is None
    )
    assert (
        unavailable.max_drawdown_status == "UNKNOWN"
        and unavailable.calmar_status == "UNKNOWN"
        and unavailable.dsr_status == "UNKNOWN"
        and unavailable.pbo_status == "UNKNOWN"
    )
    safety = manifest.safety
    assert safety.real_phase4_campaign_executed is False
    assert safety.validation_strategy_executed is False
    assert safety.validation_metrics_accessed is False
    assert safety.candidates_ranked is False
    assert safety.survivor_selected is False
    assert safety.strategy_search_executed is False
    assert safety.external_strategy_research_performed is False
    assert safety.final_holdout_accessed is False
    assert safety.protected_symbols_accessed == ()
    assert safety.provider_calls == 0
    assert safety.downloads == 0
    assert safety.live_trading_capability is False
    assert safety.phase4_trials_consumed == 0


def test_seal_source_bundles_match_independent_bundle_identity(sealed_engine) -> None:
    manifest = _manifest_of(sealed_engine)
    names = [item.bundle_name for item in manifest.source_bundles]
    assert names == sorted(GATE2_SOURCE_BUNDLES)
    assert len(names) == len(set(names)) == 13
    for digest in manifest.source_bundles:
        independent = source_bundle_identity(
            REPOSITORY_ROOT,
            manifest.head_revision,
            GATE2_SOURCE_BUNDLES[digest.bundle_name],
        )
        assert digest.producing_revision == independent.producing_revision
        assert digest.entry_count == len(independent.entries)
        assert digest.bundle_sha256 == independent.bundle_sha256


def test_seal_exact_read_and_write_ledgers(sealed_engine) -> None:
    manifest = _manifest_of(sealed_engine)
    authority = load_gate2_authority(REPOSITORY_ROOT)
    assert manifest.read_ledger == authority.direct_dependencies
    assert len(manifest.read_ledger) == 15
    assert manifest.read_ledger[0].kind == "phase4_preregistration_manifest"
    assert tuple(item.kind for item in manifest.read_ledger[-3:]) == (
        "phase4_readiness_manifest",
        "phase4_split_manifest",
        "trial_authority",
    )
    assert tuple(item.kind for item in manifest.write_ledger) == NON_FINAL_KINDS
    for identity in manifest.write_ledger:
        assert isinstance(identity, Gate2ArtifactIdentity)
        assert identity.path.startswith(
            f"results/phase4/gate2/{identity.kind}/sha256/"
        )


def _payload_keys(payload: bytes) -> set[str]:
    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                keys.add(str(key))
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    keys: set[str] = set()
    walk(json.loads(payload))
    return keys


_FORBIDDEN_KEY_FRAGMENTS = (
    "price",
    "return",
    "metric",
    "rank",
    "eligib",
    "winner",
    "survivor",
    "score",
    "selection",
)


def test_seal_bindings_are_ordered_and_free_of_performance_fields(
    sealed_engine,
) -> None:
    manifest = _manifest_of(sealed_engine)
    authority = load_gate2_authority(REPOSITORY_ROOT)
    store = _store()
    family_payload = store.verify(manifest.write_ledger[1])
    family_set = FamilyBindingSet.model_validate(json.loads(family_payload))
    assert family_set.schema_version == "PHASE4-FAMILY-BINDINGS-v1"
    assert len(family_set.bindings) == 4
    assert [item.family_id for item in family_set.bindings] == [
        family.family_id for family in authority.grids.families
    ]
    candidate_payload = store.verify(manifest.write_ledger[2])
    candidate_set = CandidateBindingSet.model_validate(
        json.loads(candidate_payload)
    )
    assert candidate_set.schema_version == "PHASE4-CANDIDATE-BINDINGS-v1"
    assert len(candidate_set.bindings) == 180
    assert [item.candidate_id for item in candidate_set.bindings] == [
        candidate.candidate_id for candidate in authority.grids.candidates
    ]
    assert [item.budget_position for item in candidate_set.bindings] == list(
        range(1, 181)
    )
    for payload in (family_payload, candidate_payload):
        for key in _payload_keys(payload):
            for fragment in _FORBIDDEN_KEY_FRAGMENTS:
                assert fragment not in key.lower(), (key, fragment)


def test_seal_conformance_artifact_round_trips(sealed_engine) -> None:
    manifest = _manifest_of(sealed_engine)
    payload = _store().verify(manifest.write_ledger[3])
    record = SyntheticConformanceRecord.model_validate(json.loads(payload))
    assert record.label == "SYNTHETIC_CONFORMANCE_ONLY"
    assert record.phase4_trials_consumed == 0
    assert record.candidate_count == 180
    assert record.family_count == 4
    assert [item.name for item in record.invariants] == [
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
    ]


def test_seal_contract_artifact_binds_the_engine_surface(sealed_engine) -> None:
    manifest = _manifest_of(sealed_engine)
    payload = _store().verify(manifest.write_ledger[0])
    contract = EngineContract.model_validate(json.loads(payload))
    assert contract.schema_version == "PHASE4-ENGINE-CONTRACT-v1"
    assert contract.implementation_interface == (
        "PHASE4-FIXED-LONG-ONLY-STRATEGY-v1"
    )
    assert contract.campaign_id == "PHASE4-FIXED-LONG-ONLY-2014-2022-v1"
    assert contract.execution_convention == "COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN"
    assert contract.execution_series == "QFQ_NORMALIZED"
    assert contract.candidate_count == 180
    assert contract.family_count == 4
    assert contract.decision_grade is False


def test_seal_report_artifact_is_utf8_markdown(sealed_engine) -> None:
    manifest = _manifest_of(sealed_engine)
    payload = _store().verify(manifest.write_ledger[4])
    text = payload.decode("utf-8")
    assert text.startswith("# ")
    assert "PHASE4-ENGINE-MANIFEST-v1" in text
    assert "SEALED" in text


def test_seal_write_observer_records_the_sealed_write_order() -> None:
    observed: list[str] = []
    result = seal_gate2(REPOSITORY_ROOT, write_observer=observed.append)
    assert observed == list(WRITE_ORDER)
    assert result.manifest.kind == "phase4_engine_manifest"


def test_seal_repeat_run_is_byte_identical(sealed_engine) -> None:
    again = seal_gate2(REPOSITORY_ROOT)
    assert again.manifest == sealed_engine.manifest
    assert again.written == sealed_engine.written


def test_seal_failure_after_each_non_final_kind_writes_nothing_new() -> None:
    def gate2_files() -> set[Path]:
        if not GATE2_RESULTS.exists():
            return set()
        return {
            path
            for path in GATE2_RESULTS.rglob("*")
            if path.is_file()
        }

    for kind in NON_FINAL_KINDS:
        observed: list[str] = []
        before = gate2_files()
        with pytest.raises(Gate2SealError) as excinfo:
            seal_gate2(
                REPOSITORY_ROOT,
                fail_after_kind=kind,
                write_observer=observed.append,
            )
        assert excinfo.value.code == "SEAL_PUBLICATION_FAILED"
        expected_observed = list(WRITE_ORDER[: NON_FINAL_KINDS.index(kind) + 1])
        assert observed == expected_observed
        assert gate2_files() == before


def test_seal_rejects_invalid_fail_after_kind() -> None:
    for invalid in ("phase4_engine_manifest", "bogus_kind", ""):
        observed: list[str] = []
        with pytest.raises(Gate2SealError) as excinfo:
            seal_gate2(
                REPOSITORY_ROOT,
                fail_after_kind=invalid,
                write_observer=observed.append,
            )
        assert excinfo.value.code == "INPUT_BOUNDARY_VIOLATION"
        assert observed == []


def test_seal_detects_dependency_mutation_between_load_and_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _seal_module._reread_dependency

    def corrupting_reread(root: Path, identity: DirectDependencyIdentity):
        return original(root, identity) + b"tamper"

    monkeypatch.setattr(_seal_module, "_reread_dependency", corrupting_reread)
    observed: list[str] = []
    with pytest.raises(Gate2SealError) as excinfo:
        seal_gate2(
            REPOSITORY_ROOT,
            write_observer=observed.append,
        )
    assert excinfo.value.code == "HISTORICAL_ARTIFACT_MUTATION"
    assert "phase4_engine_manifest" not in observed


def test_seal_existing_collision_fails_closed(sealed_engine) -> None:
    manifest = _manifest_of(sealed_engine)
    store = _store()
    identity = manifest.write_ledger[0]
    payload = store.verify(identity)
    destination = REPOSITORY_ROOT.joinpath(*Path(identity.path).parts)
    destination.write_bytes(payload + b"corruption")
    try:
        with pytest.raises(Gate2SealError) as excinfo:
            seal_gate2(REPOSITORY_ROOT)
        assert excinfo.value.code == "IMMUTABLE_ARTIFACT_COLLISION"
    finally:
        destination.write_bytes(payload)
