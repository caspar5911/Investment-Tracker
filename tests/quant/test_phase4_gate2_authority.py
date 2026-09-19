from __future__ import annotations

from hashlib import sha256
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess

import pytest
from pydantic import ValidationError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    "results/phase4/gate1/phase4_preregistration_manifest/sha256/"
    "dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89/"
    "manifest.json"
)
EXPECTED_READS = (
    MANIFEST_PATH,
    "results/phase4/gate1/baseline_definitions/sha256/"
    "4ce3dedb8d4187a18175f08e22df63f2905ffd9df75aa72f6c11f31249a465b0/"
    "baselines.json",
    "results/phase4/gate1/deterministic_grids/sha256/"
    "40f40573ac8abfc8707231cc05d65e780967b79495c0572c89b988eb1d20f0bd/"
    "grids.json",
    "results/phase4/gate1/durability_policy/sha256/"
    "37195247139733d81a0772c0fe84222e51237198ab33954eb2a4c0e96880843c/"
    "policy.json",
    "results/phase4/gate1/family_budget_policy/sha256/"
    "ae7482967c475216bb09e7c0beb39e179019c6f065ca271ee6f8d51756b478d5/"
    "policy.json",
    "results/phase4/gate1/information_access_policy/sha256/"
    "286d167a06271fa6223641735f22d5b78ab71f0dca7ae7b03561eac2695e485e/"
    "policy.json",
    "results/phase4/gate1/research_report/sha256/"
    "3379e0382b5fcd5c9abffecf216e9243e67ddb77d3386bb1b7c7296bed8fc35a/"
    "report.md",
    "results/phase4/gate1/strategy_family_definitions/sha256/"
    "d3a2744d5c642cf5fd5042df04630ec5fffc02709f0da25c4f326b5e57d9a55c/"
    "families.json",
    "results/phase4/gate1/survivor_policy/sha256/"
    "7529b02a76622d97cf6568290a91142c33409ee4a02c137be6d09c0142655a63/"
    "policy.json",
    "results/research/hypothesis_registry.jsonl",
    "results/research/sources.jsonl",
    "results/research/research_notes.md",
    "results/phase4/readiness/phase4_readiness_manifest/sha256/"
    "4305845b627ed2d369f3e16b26eb0e9ec724c13ea50904fcf5fd4113f264a254/"
    "manifest.json",
    "results/phase4/readiness/phase4_split_manifest/sha256/"
    "b273f79795237caca08d1a10388be8d300e9f4b5f51c818a24456c972c7bb4d7/"
    "manifest.json",
    "results/phase4/readiness/trial_authority/sha256/"
    "fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994/"
    "authority.json",
)


def authority_module():
    return importlib.import_module("investment_tracker.quant.phase4.engine.authority")


def load_authority(root: Path, **kwargs):
    return authority_module().load_gate2_authority(root, **kwargs)


def copy_allowlist(destination: Path) -> Path:
    destination.mkdir()
    for relative in EXPECTED_READS:
        target = destination.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY_ROOT / relative, target)
    return destination


def disable_ancestry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authority_module(), "_verify_ancestry", lambda *_: None)


def create_junction(link: Path, target: Path) -> None:
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.skip(f"junction creation unavailable: {completed.stderr}")


def test_loads_the_exact_terminal_gate1_authority() -> None:
    observed: list[str] = []
    authority = load_authority(REPOSITORY_ROOT, read_observer=observed.append)

    assert authority.starting_revision == "fb1c30a6c9789bddf2033301977fc8e2f3ebc1a0"
    assert authority.manifest_identity.path == MANIFEST_PATH
    assert authority.manifest_identity.content_sha256 == (
        "dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89"
    )
    assert authority.manifest_identity.sha256 == (
        "e43ccbb596a9f66222b4e2785b1c40c423e6bb43b54b788e1fdb6358e1cdf146"
    )
    assert observed == list(EXPECTED_READS)
    assert tuple(item.path for item in authority.direct_dependencies) == EXPECTED_READS

    assert authority.manifest.status == "PHASE4_PREREGISTRATION_SEALED"
    assert authority.manifest.campaign_id == "PHASE4-FIXED-LONG-ONLY-2014-2022-v1"
    assert len(authority.grids.families) == 4
    assert len(authority.grids.candidates) == 180
    assert tuple(item.budget_position for item in authority.grids.candidates) == tuple(
        range(1, 181)
    )
    assert tuple(len(item.candidates) for item in authority.grids.families) == (
        54,
        36,
        36,
        54,
    )
    assert authority.grids.candidate_parameter_population_sha256 == (
        "15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3"
    )
    assert authority.trial_authority.authority.historical_phase2_trial_count == 136
    assert authority.phase4_trials_consumed == 0
    assert authority.baselines.provenance_class_counts == {
        "EXECUTED_PHASE2_BASELINE": 2,
        "SOURCE_DEFINED_PHASE2_GRID_BASELINE": 2,
    }
    assert authority.execution_convention == "COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN"
    assert authority.execution_series == "QFQ_NORMALIZED"
    assert authority.primary_friction_bps == 3
    assert authority.decision_grade is False
    assert authority.qfq_methodology_identity == (
        "ffee9bac3fe329b14d5aebb0f6152f00fc0a86b28d9186c254b5c8f6f8a322fb"
    )
    assert authority.unavailable_statistics.model_dump() == {
        "max_drawdown": None,
        "max_drawdown_status": "UNKNOWN",
        "calmar": None,
        "calmar_status": "UNKNOWN",
        "dsr": None,
        "dsr_status": "UNKNOWN",
        "dsr_reason": "NOT_IMPLEMENTED",
        "pbo": None,
        "pbo_status": "UNKNOWN",
        "pbo_reason": "NOT_IMPLEMENTED",
    }
    assert authority.safety.model_dump() == {
        "real_phase4_campaign_executed": False,
        "validation_strategy_executed": False,
        "validation_metrics_accessed": False,
        "candidates_ranked": False,
        "survivor_selected": False,
        "strategy_search_executed": False,
        "external_strategy_research_performed": False,
        "final_holdout_accessed": False,
        "protected_symbols_accessed": (),
        "provider_calls": 0,
        "downloads": 0,
        "live_trading_capability": False,
        "phase4_trials_consumed": 0,
    }


def test_nested_gate1_dictionaries_cannot_mutate_returned_authority() -> None:
    authority = load_authority(REPOSITORY_ROOT)
    candidate_parameters = dict(authority.grids.candidates[0].raw_parameters)
    family_dimensions = dict(authority.family_definitions[0].parameter_dimensions)
    baseline_parameters = dict(authority.baselines.baselines[0].parameters)
    provenance_counts = dict(authority.baselines.provenance_class_counts)
    manifest_counts = dict(authority.manifest.baseline_provenance_class_counts)
    population_digest = authority.grids.candidate_parameter_population_sha256

    authority.grids.candidates[0].raw_parameters.clear()
    authority.family_definitions[0].parameter_dimensions.clear()
    authority.baselines.baselines[0].parameters.clear()
    authority.baselines.provenance_class_counts.clear()
    authority.manifest.baseline_provenance_class_counts.clear()

    assert authority.grids.candidates[0].raw_parameters == candidate_parameters
    assert authority.family_definitions[0].parameter_dimensions == family_dimensions
    assert authority.baselines.baselines[0].parameters == baseline_parameters
    assert authority.baselines.provenance_class_counts == provenance_counts
    assert authority.manifest.baseline_provenance_class_counts == manifest_counts
    assert authority.grids.candidate_parameter_population_sha256 == population_digest


def test_reconstruction_rejects_malformed_retained_family_payload() -> None:
    payload = load_authority(REPOSITORY_ROOT).model_dump()
    payload["family_definitions_payload"] = b"not-json"

    with pytest.raises(ValidationError):
        authority_module().Gate2Authority.model_validate(payload)


@pytest.mark.parametrize(
    "payload_field",
    (
        "manifest_payload",
        "baseline_definitions_payload",
        "deterministic_grids_payload",
        "family_definitions_payload",
    ),
)
def test_reconstruction_requires_canonical_bytes_for_every_retained_payload(
    payload_field: str,
) -> None:
    payload = load_authority(REPOSITORY_ROOT).model_dump()
    payload[payload_field] += b" "

    with pytest.raises(ValidationError):
        authority_module().Gate2Authority.model_validate(payload)


@pytest.mark.parametrize(
    ("payload_field", "dependency_kind"),
    (
        ("manifest_payload", "phase4_preregistration_manifest"),
        ("baseline_definitions_payload", "baseline_definitions"),
        ("deterministic_grids_payload", "deterministic_grids"),
        ("family_definitions_payload", "strategy_family_definitions"),
    ),
)
def test_reconstruction_digest_binds_every_retained_payload(
    payload_field: str,
    dependency_kind: str,
) -> None:
    module = authority_module()
    payload = load_authority(REPOSITORY_ROOT).model_dump()
    dependencies = list(payload["direct_dependencies"])
    dependency_index = next(
        index
        for index, dependency in enumerate(dependencies)
        if dependency["kind"] == dependency_kind
    )
    dependency = dict(dependencies[dependency_index])
    mismatched_digest = sha256(payload[payload_field] + b"different").hexdigest()
    dependency["content_sha256"] = mismatched_digest
    dependency["sha256"] = module.artifact_envelope_identity(
        content_sha256=mismatched_digest,
        kind=dependency["kind"],
        path=dependency["path"],
    )
    dependencies[dependency_index] = dependency
    payload["direct_dependencies"] = tuple(dependencies)

    with pytest.raises(ValidationError):
        module.Gate2Authority.model_validate(payload)


def test_reconstruction_rejects_digest_bound_family_grid_disagreement() -> None:
    module = authority_module()
    payload = load_authority(REPOSITORY_ROOT).model_dump()
    family_payload = json.loads(payload["family_definitions_payload"])
    family_payload["families"].reverse()
    mismatched_bytes = module.canonical_json_bytes(family_payload)
    mismatched_content_sha256 = sha256(mismatched_bytes).hexdigest()
    dependencies = list(payload["direct_dependencies"])
    family_index = next(
        index
        for index, dependency in enumerate(dependencies)
        if dependency["kind"] == "strategy_family_definitions"
    )
    family_dependency = dict(dependencies[family_index])
    family_dependency["content_sha256"] = mismatched_content_sha256
    family_dependency["sha256"] = module.artifact_envelope_identity(
        content_sha256=mismatched_content_sha256,
        kind=family_dependency["kind"],
        path=family_dependency["path"],
    )
    dependencies[family_index] = family_dependency
    payload["direct_dependencies"] = tuple(dependencies)
    payload["family_definitions_payload"] = mismatched_bytes

    with pytest.raises(ValidationError):
        module.Gate2Authority.model_validate(payload)


def test_reconstruction_rejects_self_consistent_baseline_substitution() -> None:
    module = authority_module()
    payload = load_authority(REPOSITORY_ROOT).model_dump()
    baseline_payload = json.loads(payload["baseline_definitions_payload"])
    baseline_payload["baselines"][0]["baseline_id"] = "baseline-a-substitute-v1"
    substituted_bytes = module.canonical_json_bytes(baseline_payload)
    substituted_digest = sha256(substituted_bytes).hexdigest()
    dependencies = list(payload["direct_dependencies"])
    baseline_index = next(
        index
        for index, dependency in enumerate(dependencies)
        if dependency["kind"] == "baseline_definitions"
    )
    baseline_dependency = dict(dependencies[baseline_index])
    baseline_dependency["content_sha256"] = substituted_digest
    baseline_dependency["sha256"] = module.artifact_envelope_identity(
        content_sha256=substituted_digest,
        kind=baseline_dependency["kind"],
        path=baseline_dependency["path"],
    )
    dependencies[baseline_index] = baseline_dependency
    payload["direct_dependencies"] = tuple(dependencies)
    payload["baseline_definitions_payload"] = substituted_bytes

    with pytest.raises(ValidationError):
        module.Gate2Authority.model_validate(payload)


def test_reconstruction_rejects_self_consistent_manifest_substitution() -> None:
    module = authority_module()
    payload = load_authority(REPOSITORY_ROOT).model_dump()
    manifest_payload = json.loads(payload["manifest_payload"])
    manifest_payload["runtime_dependency_sha256"] = "0" * 64
    substituted_bytes = module.canonical_json_bytes(manifest_payload)
    substituted_digest = sha256(substituted_bytes).hexdigest()
    manifest_identity = dict(payload["manifest_identity"])
    manifest_identity["content_sha256"] = substituted_digest
    manifest_identity["sha256"] = module.artifact_envelope_identity(
        content_sha256=substituted_digest,
        kind=manifest_identity["kind"],
        path=manifest_identity["path"],
    )
    dependencies = list(payload["direct_dependencies"])
    dependencies[0] = dict(manifest_identity)
    payload["manifest_identity"] = manifest_identity
    payload["manifest_payload"] = substituted_bytes
    payload["direct_dependencies"] = tuple(dependencies)

    with pytest.raises(ValidationError):
        module.Gate2Authority.model_validate(payload)


def test_reconstruction_rejects_reordered_manifest_dependencies() -> None:
    payload = load_authority(REPOSITORY_ROOT).model_dump()
    dependencies = list(payload["direct_dependencies"])
    dependencies[3], dependencies[4] = dependencies[4], dependencies[3]
    payload["direct_dependencies"] = tuple(dependencies)

    with pytest.raises(ValidationError):
        authority_module().Gate2Authority.model_validate(payload)


@pytest.mark.parametrize(
    "dependency_kind",
    ("hypothesis_journal", "source_journal", "research_notes"),
)
def test_reconstruction_rejects_substituted_manifest_byte_projection(
    dependency_kind: str,
) -> None:
    payload = load_authority(REPOSITORY_ROOT).model_dump()
    dependencies = list(payload["direct_dependencies"])
    dependency_index = next(
        index
        for index, dependency in enumerate(dependencies)
        if dependency["kind"] == dependency_kind
    )
    dependency = dict(dependencies[dependency_index])
    dependency["content_sha256"] = "0" * 64
    dependencies[dependency_index] = dependency
    payload["direct_dependencies"] = tuple(dependencies)

    with pytest.raises(ValidationError):
        authority_module().Gate2Authority.model_validate(payload)


@pytest.mark.parametrize("mode", ["missing", "mutated"])
def test_manifest_identity_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    repository = copy_allowlist(tmp_path / "repository")
    disable_ancestry(monkeypatch)
    manifest = repository / MANIFEST_PATH
    if mode == "missing":
        manifest.unlink()
    else:
        manifest.write_bytes(manifest.read_bytes() + b"\n")

    with pytest.raises(authority_module().Gate2SealError) as caught:
        load_authority(repository, head_revision="a" * 40)
    assert caught.value.code == "GATE1_MANIFEST_MISMATCH"


@pytest.mark.parametrize("relative", EXPECTED_READS[1:])
def test_every_direct_dependency_is_exact_byte_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
) -> None:
    repository = copy_allowlist(tmp_path / "repository")
    disable_ancestry(monkeypatch)
    dependency = repository / relative
    dependency.write_bytes(dependency.read_bytes() + b"corrupt")

    with pytest.raises(authority_module().Gate2SealError) as caught:
        load_authority(repository, head_revision="a" * 40)
    assert caught.value.code == "GATE1_DEPENDENCY_MISMATCH"


def test_missing_direct_dependency_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = copy_allowlist(tmp_path / "repository")
    disable_ancestry(monkeypatch)
    (repository / EXPECTED_READS[-1]).unlink()

    with pytest.raises(authority_module().Gate2SealError) as caught:
        load_authority(repository, head_revision="a" * 40)
    assert caught.value.code == "GATE1_DEPENDENCY_MISMATCH"


def test_symlinked_dependency_fails_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = copy_allowlist(tmp_path / "repository")
    disable_ancestry(monkeypatch)
    relative = EXPECTED_READS[1]
    dependency = repository / relative
    target = tmp_path / "substitute.json"
    target.write_bytes(dependency.read_bytes())
    dependency.unlink()
    try:
        dependency.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(authority_module().Gate2SealError) as caught:
        load_authority(repository, head_revision="a" * 40)
    assert caught.value.code == "GATE1_DEPENDENCY_MISMATCH"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction coverage")
def test_junctioned_dependency_directory_fails_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = copy_allowlist(tmp_path / "repository")
    disable_ancestry(monkeypatch)
    junction = repository / "results" / "phase4" / "gate1" / "baseline_definitions"
    target = tmp_path / "external-baseline-definitions"
    shutil.move(junction, target)
    create_junction(junction, target)
    try:
        with pytest.raises(authority_module().Gate2SealError) as caught:
            load_authority(repository, head_revision="a" * 40)
        assert caught.value.code == "GATE1_DEPENDENCY_MISMATCH"
    finally:
        junction.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction coverage")
def test_repository_root_ancestor_junction_fails_before_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    copy_allowlist(real_parent / "repository")
    alias_parent = tmp_path / "alias-parent"
    create_junction(alias_parent, real_parent)
    disable_ancestry(monkeypatch)
    try:
        with pytest.raises(authority_module().Gate2SealError) as caught:
            load_authority(alias_parent / "repository", head_revision="a" * 40)
        assert caught.value.code == "GATE1_MANIFEST_MISMATCH"
    finally:
        alias_parent.rmdir()


def test_terminal_metadata_links_are_not_traversed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = copy_allowlist(tmp_path / "repository")
    disable_ancestry(monkeypatch)
    readiness = json.loads((repository / EXPECTED_READS[-3]).read_bytes())
    split = json.loads((repository / EXPECTED_READS[-2]).read_bytes())
    trial = json.loads((repository / EXPECTED_READS[-1]).read_bytes())
    trap_paths = (
        readiness["bootstrap_input_vector"]["path"],
        split["partitions"][0]["bars_artifact"]["path"],
        trial["authority"]["trials"][0]["authoritative_artifact"]["path"],
    )
    traps: set[Path] = set()
    for relative in trap_paths:
        trap = repository.joinpath(*PurePosixPath(relative).parts)
        trap.parent.mkdir(parents=True, exist_ok=True)
        trap.write_text("must not be read", encoding="utf-8")
        traps.add(trap)
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path in traps:
            raise AssertionError(f"terminal dependency traversed: {path}")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    observed: list[str] = []

    authority = load_authority(
        repository,
        head_revision="a" * 40,
        read_observer=observed.append,
    )

    assert authority.readiness_manifest.protected_tree_digests
    assert observed == list(EXPECTED_READS)
    assert set(trap_paths).isdisjoint(observed)


def test_nonancestor_head_fails_as_manifest_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = authority_module()

    class Completed:
        returncode = 1
        stdout = b""

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: Completed())
    with pytest.raises(module.Gate2SealError) as caught:
        load_authority(REPOSITORY_ROOT, head_revision="a" * 40)
    assert caught.value.code == "GATE1_MANIFEST_MISMATCH"


def test_candidate_population_substitution_has_specific_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = copy_allowlist(tmp_path / "repository")
    disable_ancestry(monkeypatch)
    module = authority_module()
    grid_path = repository / EXPECTED_READS[2]
    payload = json.loads(grid_path.read_bytes())
    payload["candidate_parameter_population_sha256"] = "0" * 64
    altered = module.canonical_json_bytes(payload)
    grid_path.write_bytes(altered)

    manifest_path = repository / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_bytes())
    identity = manifest["deterministic_grids"]
    identity["content_sha256"] = sha256(altered).hexdigest()
    identity["sha256"] = module.artifact_envelope_identity(
        content_sha256=identity["content_sha256"],
        kind=identity["kind"],
        path=identity["path"],
    )
    altered_manifest = module.canonical_json_bytes(manifest)
    manifest_path.write_bytes(altered_manifest)
    monkeypatch.setattr(
        module,
        "GATE1_MANIFEST_IDENTITY",
        module.Gate1ArtifactIdentity(
            kind="phase4_preregistration_manifest",
            path=MANIFEST_PATH,
            content_sha256=sha256(altered_manifest).hexdigest(),
            sha256=module.artifact_envelope_identity(
                content_sha256=sha256(altered_manifest).hexdigest(),
                kind="phase4_preregistration_manifest",
                path=MANIFEST_PATH,
            ),
        ),
    )

    with pytest.raises(module.Gate2SealError) as caught:
        load_authority(repository, head_revision="a" * 40)
    assert caught.value.code == "CANDIDATE_POPULATION_MISMATCH"


def test_execution_convention_substitution_has_specific_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = authority_module()
    monkeypatch.setattr(module.quant_constants, "EXECUTION_CONVENTION", "substituted")
    with pytest.raises(module.Gate2SealError) as caught:
        load_authority(REPOSITORY_ROOT)
    assert caught.value.code == "EXECUTION_CONVENTION_MISMATCH"
