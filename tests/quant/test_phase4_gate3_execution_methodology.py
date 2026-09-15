from __future__ import annotations

from hashlib import sha256
from importlib import import_module
from pathlib import Path
import json
import os

import pytest

from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    canonical_sha256,
)


ROOT = Path(__file__).resolve().parents[2]


def _api():
    return import_module("investment_tracker.quant.phase4.gate3_execution.methodology")


def test_exact_spec_and_canonical_semantic_records_have_stable_identities():
    api = _api()
    spec = api.spec_identity(ROOT)
    raw = (ROOT / api.SPEC_PATH).read_bytes()
    assert spec.content_sha256 == sha256(raw).hexdigest()
    assert spec.sha256 == artifact_envelope_identity(
        content_sha256=spec.content_sha256, kind=spec.kind, path=spec.path
    )
    assert api.spec_identity(ROOT) == spec
    baseline, regime = api.semantic_method_records(ROOT)
    assert baseline["kind"] == "baseline_sleeve_method"
    assert regime["kind"] == "regime_return_method"
    assert baseline["symbols"] == ["SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP"]
    assert baseline["initial_cash_per_sleeve"] == 12500.0
    assert regime["validation_session_count"] == 1008
    assert regime["actual_return_count"] == 1007
    assert regime["first_session_return"] is None
    assert "median" not in regime["conditional_metrics"]
    assert canonical_json_bytes(baseline) == canonical_json_bytes(api.semantic_method_records(ROOT)[0])
    changed = {**baseline, "initial_cash_per_sleeve": 12501.0}
    assert sha256(canonical_json_bytes(changed)).hexdigest() != sha256(canonical_json_bytes(baseline)).hexdigest()


def test_immutable_method_records_reject_collision_noncanonical_json_and_forged_identity(tmp_path):
    api = _api()
    store = api.MethodologyEvidenceStore(tmp_path)
    payload = {"kind": "baseline_sleeve_method", "symbols": ["SPY"]}
    identity = store.write_json("baseline_sleeve_method", payload)
    assert store.write_json("baseline_sleeve_method", payload) == identity
    assert store.verify(identity) == canonical_json_bytes(payload)
    forged = identity.model_copy(update={"sha256": "0" * 64})
    with pytest.raises(ValueError, match="ARTIFACT_IDENTITY_INVALID"):
        store.verify(forged)
    destination = tmp_path.joinpath(*identity.path.split("/"))
    destination.write_bytes(json.dumps(payload, indent=2).encode())
    with pytest.raises(ValueError, match="IMMUTABLE_ARTIFACT_COLLISION"):
        store.write_json("baseline_sleeve_method", payload)
    with pytest.raises(ValueError, match="ARTIFACT_BYTES_INVALID"):
        store.verify(identity)


def test_method_store_rejects_symlink_junction_traversal_and_noncanonical_paths(tmp_path, monkeypatch):
    api = _api()
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, tmp_path / "results", target_is_directory=True)
    with pytest.raises(ValueError, match="ARTIFACT_PATH_INVALID"):
        api.MethodologyEvidenceStore(tmp_path)
    (tmp_path / "results").unlink()
    store = api.MethodologyEvidenceStore(tmp_path)
    identity = store.write_json("regime_return_method", {"kind": "regime_return_method"})
    with pytest.raises(ValueError, match="ARTIFACT_IDENTITY_INVALID"):
        store.verify(identity.model_copy(update={"path": "../outside/record.json"}))
    with pytest.raises(ValueError, match="ARTIFACT_IDENTITY_INVALID"):
        store.verify(identity.model_copy(update={"path": "results/phase4/gate3/execution_methodology/regime_return_method/other.json"}))
    from investment_tracker.quant.phase4.gate3 import filesystem

    original = filesystem.is_redirect
    monkeypatch.setattr(
        filesystem,
        "is_redirect",
        lambda path: path == tmp_path / "results" or original(path),
    )
    with pytest.raises(ValueError, match="ARTIFACT_PATH_INVALID"):
        store.verify(identity)


def test_preflight_requires_explicit_corrected_manifest_and_never_discovers_latest():
    api = _api()
    with pytest.raises(ValueError, match="METHODOLOGY_MANIFEST_MISSING"):
        api.preflight_execution_methodology(ROOT, "0" * 64)
    with pytest.raises(ValueError, match="METHODOLOGY_MANIFEST_MISSING"):
        api.preflight_execution_methodology(ROOT, "latest")
    assert api.CORRECTED_GATE3_MANIFEST.content_sha256 == (
        "705935c9b06b8f592e66e5e71e4541d910b585be6e9a30e46b99fe97b7591d4f"
    )


def _synthetic_semantic_manifest(api):
    from investment_tracker.quant.phase4.engine.source_identity import SourceBundleEntry, SourceBundleIdentity
    from investment_tracker.quant.phase4.gate3.seal import (
        GATE1_MANIFEST_IDENTITY, GATE2_MANIFEST_IDENTITY, TRAIN_IDENTITY, VALIDATION_IDENTITY,
    )

    entries = tuple(
        SourceBundleEntry(path=path, git_blob="1" * 40, content_sha256="2" * 64)
        for path in api.SOURCE_FILES
    )
    revision = "3" * 40
    bundle = SourceBundleIdentity(
        producing_revision=revision,
        entries=entries,
        bundle_sha256=canonical_sha256({
            "schema_version": "PHASE4-SOURCE-BUNDLE-v1",
            "producing_revision": revision,
            "entries": {
                item.path: {"git_blob": item.git_blob, "content_sha256": item.content_sha256}
                for item in entries
            },
        }),
    )
    store = api.MethodologyEvidenceStore(ROOT)
    baseline, regime = api.semantic_method_records(ROOT)
    return api.ExecutionMethodologyManifest(
        spec=api.spec_identity(ROOT),
        baseline_method=store._identity("baseline_sleeve_method", sha256(canonical_json_bytes(baseline)).hexdigest()),
        regime_method=store._identity("regime_return_method", sha256(canonical_json_bytes(regime)).hexdigest()),
        gate1_manifest=GATE1_MANIFEST_IDENTITY,
        gate2_manifest=GATE2_MANIFEST_IDENTITY,
        gate3_authority_manifest=api.CORRECTED_GATE3_MANIFEST,
        candidate_population_sha256=api.POPULATION_SHA256,
        train_identity=TRAIN_IDENTITY,
        validation_identity=VALIDATION_IDENTITY,
        source_revision=revision,
        source_bundle=bundle,
    )


def test_pure_validator_binds_approved_dependencies_without_campaign_execution():
    api = _api()
    manifest = _synthetic_semantic_manifest(api)
    state = api.validate_execution_methodology(ROOT, manifest)
    assert state.gate1 == state.gate2 == state.gate3_authorities == "VALID"
    assert state.baseline_methodology == state.regime_attribution_methodology == "BOUND"
    assert state.source_bundle == state.execution_methodology == "DECLARED"
    assert state.candidate_population == 180
    assert state.gate3 == "STRUCTURALLY_BOUND"
    assert state.safety.candidate_executed is False
    assert state.safety.validation_candidate_performance_accessed is False
    assert state.safety.phase4_trials_consumed == 0


def test_pure_validator_rejects_mutated_dependencies_and_superseded_authority():
    api = _api()
    manifest = _synthetic_semantic_manifest(api)
    for field, altered in (
        ("gate1_manifest", manifest.gate1_manifest.model_copy(update={"content_sha256": "0" * 64})),
        ("gate2_manifest", manifest.gate2_manifest.model_copy(update={"content_sha256": "0" * 64})),
        ("gate3_authority_manifest", manifest.gate3_authority_manifest.model_copy(update={"content_sha256": "83f4bec6bade156fc3e54534403e901319dc3fb97a26c27b22df2195fef70cfc"})),
        ("candidate_population_sha256", "0" * 64),
        ("train_identity", manifest.train_identity.model_copy(update={"sessions_sha256": "0" * 64})),
        ("validation_identity", manifest.validation_identity.model_copy(update={"sessions_sha256": "0" * 64})),
        ("spec", manifest.spec.model_copy(update={"content_sha256": "0" * 64})),
        ("baseline_method", manifest.baseline_method.model_copy(update={"content_sha256": "0" * 64})),
        ("regime_method", manifest.regime_method.model_copy(update={"content_sha256": "0" * 64})),
        ("source_revision", "0" * 40),
    ):
        with pytest.raises(ValueError, match="METHODOLOGY_DEPENDENCY_MISMATCH"):
            api.validate_execution_methodology(ROOT, manifest.model_copy(update={field: altered}))
    with pytest.raises(ValueError):
        api.ExecutionMethodologyManifest.model_validate({**manifest.model_dump(mode="json"), "extra": "not allowed"})


def test_source_bundle_has_exact_seven_approved_files_and_no_latest_discovery():
    api = _api()
    assert api.SOURCE_FILES == tuple(sorted(
        "src/investment_tracker/quant/phase4/gate3_execution/" + name
        for name in ("__init__.py", "baselines.py", "regimes.py", "campaign.py", "artifacts.py", "methodology.py", "cli.py")
    ))


def test_cli_exposes_only_quote_free_seal_and_explicit_preflight():
    cli = import_module("investment_tracker.quant.phase4.gate3_execution.cli")
    for forbidden in ("run", "execute", "campaign", "evaluate", "rank", "select", "winner", "trade", "order", "account"):
        with pytest.raises(SystemExit) as exc:
            cli.main([forbidden])
        assert exc.value.code == 2


def test_trial_record_is_preparation_only_and_cannot_masquerade_as_executed_campaign_evidence(tmp_path):
    from investment_tracker.quant.phase4.gate3_execution.campaign import TrialRecord

    record = TrialRecord.model_fields
    assert "result" in record
    from investment_tracker.quant.phase4.engine.authority import load_gate2_authority
    from investment_tracker.quant.phase4.engine.models import Phase4EngineManifest
    from investment_tracker.quant.phase4.gate3_execution.campaign import prepare_campaign_plan

    authority = load_gate2_authority(ROOT)
    gate2_path = ROOT / "results/phase4/gate2/phase4_engine_manifest/sha256/c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6/manifest.json"
    gate2 = Phase4EngineManifest.model_validate_json(gate2_path.read_bytes())
    row = prepare_campaign_plan(authority, gate2)[0]
    with pytest.raises(ValueError, match="PREPARATION_ONLY"):
        TrialRecord.from_reference(row, status="EXECUTED", reason="", result={"cagr": 999})
    with pytest.raises(ValueError, match="PREPARATION_ONLY"):
        TrialRecord.from_reference(row, status="UNKNOWN", reason="MISSING", result={"cagr": 999})
    from investment_tracker.quant.phase4.gate3_execution.artifacts import TrialEvidenceStore

    original = TrialRecord.from_reference(row, status="UNKNOWN", reason="MISSING")
    forged = original.model_copy(update={"status": "EXECUTED", "result": {"cagr": 999}})
    with pytest.raises(ValueError, match="PREPARATION_ONLY"):
        TrialEvidenceStore(tmp_path).write(forged)
