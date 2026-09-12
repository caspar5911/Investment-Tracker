from __future__ import annotations

import json
from datetime import date
from pathlib import Path
import shutil

import pytest

from investment_tracker.quant.readiness.bootstrap_audit import (
    BootstrapEvidenceError,
    audit_bootstrap_vector,
    load_pinned_bootstrap_source,
    reconstruct_bootstrap_vector,
)
from investment_tracker.quant.readiness.constants import (
    PINNED_BOOTSTRAP_DATASETS,
    PINNED_BOOTSTRAP_SOURCE_ARTIFACT_SHA256,
    PINNED_BOOTSTRAP_SOURCE_CONTENT_SHA256,
    PINNED_BOOTSTRAP_SOURCE_PATH,
    PINNED_BOOTSTRAP_VECTOR_SHA256,
    PINNED_CANDIDATE_MANIFEST_SHA256,
)
from investment_tracker.quant.readiness.hashing import canonical_json_bytes
from investment_tracker.quant.validation.bootstrap import bootstrap_interval


@pytest.fixture(scope="module")
def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def pinned_source(repository_root: Path):
    return load_pinned_bootstrap_source(repository_root)


@pytest.fixture(scope="module")
def pinned_vector(repository_root: Path, pinned_source):
    return reconstruct_bootstrap_vector(repository_root, pinned_source)


def copy_pinned_evidence(repository_root: Path, destination: Path) -> Path:
    copied_root = destination / "repository"
    source = repository_root / Path(PINNED_BOOTSTRAP_SOURCE_PATH)
    target = copied_root / Path(PINNED_BOOTSTRAP_SOURCE_PATH)
    target.parent.mkdir(parents=True)
    shutil.copy2(source, target)
    for dataset in PINNED_BOOTSTRAP_DATASETS:
        shutil.copytree(
            repository_root / Path(dataset.path),
            copied_root / Path(dataset.path),
        )
    return copied_root


def test_pinned_source_has_exact_byte_and_envelope_identity(
    pinned_source,
) -> None:
    assert (
        pinned_source.artifact.content_sha256
        == PINNED_BOOTSTRAP_SOURCE_CONTENT_SHA256
    )
    assert pinned_source.artifact.sha256 == PINNED_BOOTSTRAP_SOURCE_ARTIFACT_SHA256
    assert (
        pinned_source.record.candidate_manifest.digest
        == PINNED_CANDIDATE_MANIFEST_SHA256
    )


def test_reconstructed_vector_matches_frozen_1007_value_digest(
    pinned_vector,
) -> None:
    assert pinned_vector.schema_version == "BOOTSTRAP-INPUT-VECTOR-v1"
    assert pinned_vector.dtype == "IEEE-754-binary64"
    assert len(pinned_vector.values_hex) == 1007
    assert pinned_vector.negative_count == 288
    assert pinned_vector.zero_count == 368
    assert pinned_vector.positive_count == 351
    assert pinned_vector.sha256 == PINNED_BOOTSTRAP_VECTOR_SHA256


def test_audit_rejects_mutated_surrounding_dataset_provenance(
    pinned_source,
    pinned_vector,
) -> None:
    changed_dataset = pinned_vector.datasets[0].model_copy(
        update={
            "path": "data/cache/moomoo/IEF/1d/qfq/substitute",
            "content_hash": "0" * 64,
        }
    )
    changed_vector = pinned_vector.model_copy(
        update={"datasets": (changed_dataset, *pinned_vector.datasets[1:])}
    )

    assert changed_vector.values_hex == pinned_vector.values_hex
    assert changed_vector.sha256 == pinned_vector.sha256
    with pytest.raises(BootstrapEvidenceError, match="dataset provenance"):
        audit_bootstrap_vector(changed_vector, pinned_source)


def test_audit_reproduces_all_zero_medians_and_point_interval(
    pinned_source,
    pinned_vector,
) -> None:
    audit = audit_bootstrap_vector(pinned_vector, pinned_source)
    assert audit.draws == 2000
    assert audit.seed == 0
    assert audit.zero_resampled_medians == 2000
    assert audit.interval == (0.0, 0.0)
    assert audit.claim_scope == "MEDIAN_DAILY_EQUAL_WEIGHT_PORTFOLIO_RETURN_ONLY"
    assert audit.decision_grade is False


def test_reconstruction_rejects_a_source_model_with_a_different_train_split(
    repository_root: Path,
    pinned_source,
) -> None:
    changed_record = pinned_source.record.model_copy(
        update={"train_period": (date(2011, 1, 1), date(2018, 12, 31))}
    )
    changed_source = pinned_source.model_copy(update={"record": changed_record})

    with pytest.raises(BootstrapEvidenceError, match="manifest evidence"):
        reconstruct_bootstrap_vector(repository_root, changed_source)


@pytest.mark.parametrize("failure", ["source_bytes", "manifest", "dataset", "vector"])
def test_pinned_bootstrap_mismatch_fails_without_fixture_fallback(
    repository_root: Path,
    pinned_source,
    pinned_vector,
    tmp_path: Path,
    failure: str,
) -> None:
    if failure == "source_bytes":
        copied_root = copy_pinned_evidence(repository_root, tmp_path)
        source_path = copied_root / Path(PINNED_BOOTSTRAP_SOURCE_PATH)
        source_path.write_bytes(source_path.read_bytes() + b"\n")
        with pytest.raises(BootstrapEvidenceError, match="source"):
            load_pinned_bootstrap_source(copied_root)
    elif failure == "manifest":
        invalid_manifest = pinned_source.record.candidate_manifest.model_copy(
            update={"digest": "0" * 64}
        )
        invalid_record = pinned_source.record.model_copy(
            update={"candidate_manifest": invalid_manifest}
        )
        invalid_source = pinned_source.model_copy(update={"record": invalid_record})
        with pytest.raises(BootstrapEvidenceError, match="manifest"):
            reconstruct_bootstrap_vector(repository_root, invalid_source)
    elif failure == "dataset":
        copied_root = copy_pinned_evidence(repository_root, tmp_path)
        metadata_path = (
            copied_root / Path(PINNED_BOOTSTRAP_DATASETS[0].path) / "metadata.json"
        )
        metadata = json.loads(metadata_path.read_bytes())
        metadata["row_count"] = 1
        metadata_path.write_bytes(canonical_json_bytes(metadata))
        copied_source = load_pinned_bootstrap_source(copied_root)
        with pytest.raises(BootstrapEvidenceError, match="dataset"):
            reconstruct_bootstrap_vector(copied_root, copied_source)
    else:
        invalid_vector = pinned_vector.model_copy(update={"sha256": "0" * 64})
        with pytest.raises(BootstrapEvidenceError, match="vector"):
            audit_bootstrap_vector(invalid_vector, pinned_source)


@pytest.mark.parametrize(
    ("values", "arguments", "message"),
    [
        ([0.0], {}, "at least two finite"),
        ([0.0, float("nan")], {}, "at least two finite"),
        ([0.0, float("inf")], {}, "at least two finite"),
        ([0.0, 1.0], {"draws": 99}, "at least 100"),
        (
            [0.0, 1.0],
            {"lower_percentile": 95.0, "upper_percentile": 5.0},
            "percentiles are invalid",
        ),
    ],
)
def test_frozen_bootstrap_rejects_invalid_inputs(
    values: list[float],
    arguments: dict[str, float | int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        bootstrap_interval(values, **arguments)


def test_canonical_json_preserves_full_precision_floats() -> None:
    assert canonical_json_bytes(
        {
            "lower": -0.11183240544317852,
            "upper": 0.10356543333709656,
        }
    ) == (
        b'{"lower":-0.11183240544317852,'
        b'"upper":0.10356543333709656}'
    )
