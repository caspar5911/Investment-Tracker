from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import shutil

import pytest

from investment_tracker.quant.readiness.artifacts import ReadinessArtifactStore
from investment_tracker.quant.readiness.artifacts import (
    ReadinessArtifactIntegrityError,
)
from investment_tracker.quant.readiness.constants import (
    PHASE3_DATASETS,
    PHASE3_DQ_SNAPSHOT_PATH,
    PHASE3_UNIVERSE_PATH,
    PINNED_BOOTSTRAP_DATASETS,
    PINNED_BOOTSTRAP_SOURCE_PATH,
)
from investment_tracker.quant.readiness.hashing import canonical_sha256
from investment_tracker.quant.readiness.campaign import run_phase4_readiness
from investment_tracker.quant.readiness.report import render_readiness_report


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROTECTED_TREES = (
    "results/experiments",
    "results/phase3",
    "data/cache/phase3",
)


@dataclass(frozen=True)
class ProviderFreeRepository:
    root: Path
    store: ReadinessArtifactStore

    def tamper_pinned_source(self) -> None:
        path = self.root.joinpath(*PINNED_BOOTSTRAP_SOURCE_PATH.split("/"))
        path.write_bytes(path.read_bytes() + b"\n")


def _copy_file(source_root: Path, destination_root: Path, relative: str) -> None:
    source = source_root.joinpath(*relative.split("/"))
    destination = destination_root.joinpath(*relative.split("/"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


@pytest.fixture
def provider_free_repo(tmp_path: Path) -> ProviderFreeRepository:
    root = tmp_path / "repository"
    root.mkdir()
    for source in sorted((REPOSITORY_ROOT / "results/experiments").glob("*.json")):
        relative = source.relative_to(REPOSITORY_ROOT).as_posix()
        _copy_file(REPOSITORY_ROOT, root, relative)
    _copy_file(REPOSITORY_ROOT, root, PHASE3_UNIVERSE_PATH)
    _copy_file(REPOSITORY_ROOT, root, PHASE3_DQ_SNAPSHOT_PATH)
    for dataset in PHASE3_DATASETS:
        _copy_file(REPOSITORY_ROOT, root, f"{dataset.path}/metadata.json")
        _copy_file(REPOSITORY_ROOT, root, f"{dataset.path}/bars.parquet")
    for dataset in PINNED_BOOTSTRAP_DATASETS:
        _copy_file(REPOSITORY_ROOT, root, f"{dataset.path}/metadata.json")
        _copy_file(REPOSITORY_ROOT, root, f"{dataset.path}/bars.parquet")
    return ProviderFreeRepository(
        root=root,
        store=ReadinessArtifactStore(root, root / "results"),
    )


def _tree_digest(repository: Path, relative: str) -> str:
    root = repository.joinpath(*relative.split("/"))
    entries = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        entries.append(
            (
                path.relative_to(root).as_posix(),
                sha256(path.read_bytes()).hexdigest(),
            )
        )
    return canonical_sha256(entries)


def test_readiness_campaign_writes_complete_linked_evidence_last(
    provider_free_repo: ProviderFreeRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[str] = []
    original_write_json = ReadinessArtifactStore.write_json
    original_write_text = ReadinessArtifactStore.write_text

    def tracked_json(self, kind, filename, payload):
        writes.append(kind)
        return original_write_json(self, kind, filename, payload)

    def tracked_text(self, kind, filename, text):
        writes.append(kind)
        return original_write_text(self, kind, filename, text)

    monkeypatch.setattr(ReadinessArtifactStore, "write_json", tracked_json)
    monkeypatch.setattr(ReadinessArtifactStore, "write_text", tracked_text)
    before = {
        relative: _tree_digest(provider_free_repo.root, relative)
        for relative in PROTECTED_TREES
    }

    outcome = run_phase4_readiness(
        provider_free_repo.root,
        provider_free_repo.root / "results",
    )

    after = {
        relative: _tree_digest(provider_free_repo.root, relative)
        for relative in PROTECTED_TREES
    }
    assert outcome.status == "PHASE_4_READY"
    assert outcome.manifest is not None
    assert outcome.summary is not None
    assert before == after
    assert writes == [
        "bootstrap_input_vector",
        "bootstrap_audit",
        "trial_authority",
        "phase4_split_manifest",
        "phase4_campaign_configuration",
        "phase4_readiness_report",
        "phase4_readiness_manifest",
    ]

    manifest = provider_free_repo.store.read_json(outcome.manifest)
    assert manifest["status"] == "PHASE_4_READY"
    assert manifest["historical_phase2_trial_count"] == 136
    assert manifest["phase4_new_trials_consumed"] == 0
    assert manifest["phase4_new_trials_remaining"] == 3000
    for name in (
        "bootstrap_audit",
        "bootstrap_input_vector",
        "trial_authority",
        "split_manifest",
        "campaign_configuration",
    ):
        assert manifest[name]["sha256"]
        provider_free_repo.store.verify(getattr(outcome.summary, name))
    assert outcome.report is not None
    assert manifest["readiness_report"]["sha256"]
    provider_free_repo.store.verify(outcome.report)


def test_readiness_report_is_complete_and_non_circular(
    provider_free_repo: ProviderFreeRepository,
) -> None:
    outcome = run_phase4_readiness(
        provider_free_repo.root,
        provider_free_repo.root / "results",
    )
    assert outcome.summary is not None
    assert outcome.report is not None
    assert outcome.manifest is not None

    report = provider_free_repo.store.read_text(outcome.report)
    assert report == render_readiness_report(outcome.summary)
    for expected in (
        "median daily equal-weight portfolio return",
        "1,007",
        "[0.0, 0.0]",
        "136 historical Phase 2 trials",
        "0 of 3,000",
        "DSR: UNKNOWN/NOT_IMPLEMENTED",
        "PBO: UNKNOWN/NOT_IMPLEMENTED",
        "TRAIN declared: 2014-01-02 through 2018-12-31; actual: 2014-01-02 through 2018-12-31 (1,258 sessions)",
        "VALIDATION declared: 2019-01-01 through 2022-12-30; actual: 2019-01-02 through 2022-12-30 (1,008 sessions)",
        PINNED_BOOTSTRAP_SOURCE_PATH,
        PHASE3_UNIVERSE_PATH,
        PHASE3_DQ_SNAPSHOT_PATH,
        "QFQ_NORMALIZED",
        "QFQ is research-only normalized simulation",
        "Decision grade: false",
        "Provider calls: 0",
        "External strategy research performed: false",
        "Strategy search executed: false",
        "Final holdout accessed: false",
        "Protected symbols accessed: []",
        "Live trading capability: false",
        "No strategy discovery was authorized",
    ):
        assert expected in report
    assert outcome.manifest.path not in report
    assert outcome.manifest.sha256 not in report


def test_fail_closed_campaign_does_not_write_ready_manifest(
    provider_free_repo: ProviderFreeRepository,
) -> None:
    provider_free_repo.tamper_pinned_source()

    outcome = run_phase4_readiness(
        provider_free_repo.root,
        provider_free_repo.root / "results",
    )

    assert outcome.status == "READINESS_FAILED"
    assert outcome.reason_code == "PINNED_BOOTSTRAP_SOURCE_MISMATCH"
    assert outcome.manifest is None
    assert not (
        provider_free_repo.root
        / "results/phase4/readiness/phase4_readiness_manifest"
    ).exists()


def test_configured_repository_path_is_validated_before_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import investment_tracker.quant.readiness.campaign as campaign

    repository = tmp_path / "repository"
    (repository / "child").mkdir(parents=True)
    configured = repository / "child" / ".."
    observed: dict[str, Path] = {}

    class RejectingStore:
        def __init__(self, repository_root: Path, results_root: Path) -> None:
            observed["repository_root"] = repository_root
            raise ReadinessArtifactIntegrityError("configured root rejected")

    monkeypatch.setattr(campaign, "ReadinessArtifactStore", RejectingStore)

    outcome = campaign.run_phase4_readiness(configured, repository / "results")

    assert observed["repository_root"] == configured
    assert outcome.status == "READINESS_FAILED"
    assert outcome.reason_code == "ROOT_VALIDATION_FAILED"


def test_readiness_public_api_exposes_only_bounded_audit_entrypoints() -> None:
    import investment_tracker.quant.readiness as readiness

    assert readiness.run_phase4_readiness is run_phase4_readiness
    assert readiness.render_readiness_report is render_readiness_report
    assert "StrategyBase" not in readiness.__all__
