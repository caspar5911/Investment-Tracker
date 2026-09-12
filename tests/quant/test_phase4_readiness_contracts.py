from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_tracker.quant.readiness.constants import PHASE2_CAMPAIGN_ID
from investment_tracker.quant.readiness.hashing import (
    ArtifactIdentityError,
    artifact_identity,
    canonical_json_bytes,
    canonical_sha256,
    exact_file_sha256,
    normalize_repository_path,
    trial_identity,
)
from investment_tracker.quant.readiness.models import (
    AuthoritativeTrial,
    ReadinessArtifactIdentity,
)


def make_artifact_identity(tmp_path: Path) -> ReadinessArtifactIdentity:
    repository = tmp_path / "repo"
    artifact = repository / "results" / "record.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b'{"value":1}\n')
    return artifact_identity(repository, artifact, "phase2_experiment")


def test_canonical_json_has_stable_utf8_bytes_and_rejects_nonfinite_numbers() -> None:
    assert canonical_json_bytes({"z": "caf\N{LATIN SMALL LETTER E WITH ACUTE}", "a": 1}) == (
        b'{"a":1,"z":"caf\xc3\xa9"}'
    )
    assert canonical_sha256({"b": 2, "a": 1}) == (
        "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": float("nan")})


def test_trial_identity_has_only_campaign_and_candidate_domains() -> None:
    expected = canonical_sha256(
        {
            "campaign_id": "PHASE2-CORRECTED-2010-2022-c33fb075",
            "candidate_id": "risk_managed_trend-ee8a71fb71e3d80f",
        }
    )
    assert (
        trial_identity(PHASE2_CAMPAIGN_ID, "risk_managed_trend-ee8a71fb71e3d80f")
        == expected
    )


def test_artifact_identity_hashes_exact_bytes_kind_and_normalized_path(
    tmp_path: Path,
) -> None:
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


def test_exact_file_hash_preserves_serialized_bytes(tmp_path: Path) -> None:
    compact = tmp_path / "compact.json"
    pretty = tmp_path / "pretty.json"
    compact.write_bytes(b'{"value":1}\n')
    pretty.write_bytes(b'{\n  "value": 1\n}\n')

    assert exact_file_sha256(compact) == sha256(b'{"value":1}\n').hexdigest()
    assert exact_file_sha256(pretty) == sha256(b'{\n  "value": 1\n}\n').hexdigest()
    assert exact_file_sha256(compact) != exact_file_sha256(pretty)


def test_trial_and_artifact_identity_are_not_interchangeable(tmp_path: Path) -> None:
    identity = make_artifact_identity(tmp_path)
    with pytest.raises(ValidationError):
        AuthoritativeTrial(
            trial_id=identity.sha256,
            campaign_id=PHASE2_CAMPAIGN_ID,
            candidate_id="candidate-a",
            authoritative_artifact=identity,
            non_authoritative_artifacts=(),
        )


def test_identity_models_recompute_digests_and_are_frozen(tmp_path: Path) -> None:
    identity = make_artifact_identity(tmp_path)
    with pytest.raises(ValidationError, match="artifact identity"):
        ReadinessArtifactIdentity.model_validate(
            {**identity.model_dump(), "sha256": "0" * 64},
        )

    trial = AuthoritativeTrial(
        trial_id=trial_identity(PHASE2_CAMPAIGN_ID, "candidate-a"),
        campaign_id=PHASE2_CAMPAIGN_ID,
        candidate_id="candidate-a",
        authoritative_artifact=identity,
        non_authoritative_artifacts=(),
    )
    with pytest.raises(ValidationError, match="frozen"):
        trial.candidate_id = "candidate-b"
    with pytest.raises(ValidationError, match="extra"):
        AuthoritativeTrial.model_validate({**trial.model_dump(), "extra": True})


def test_repository_relative_and_absolute_paths_normalize_identically(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    artifact = repository / "results" / "record.json"
    artifact.parent.mkdir(parents=True)
    artifact.touch()

    assert normalize_repository_path(repository, Path("results/record.json")) == (
        "results/record.json"
    )
    assert normalize_repository_path(repository, artifact) == "results/record.json"


@pytest.mark.parametrize(
    "unsafe",
    [Path("../escape.json"), Path("/absolute.json"), Path("a/../b.json")],
)
def test_artifact_paths_reject_non_repository_relative_forms(
    tmp_path: Path, unsafe: Path
) -> None:
    with pytest.raises(ArtifactIdentityError):
        normalize_repository_path(tmp_path, unsafe)


def test_artifact_paths_reject_empty_root_and_outside_absolute_paths(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()

    with pytest.raises(ArtifactIdentityError):
        normalize_repository_path(repository, Path("."))
    with pytest.raises(ArtifactIdentityError):
        normalize_repository_path(repository, tmp_path / "outside.json")


@pytest.mark.skipif(os.name == "nt", reason="literal backslash is a Windows separator")
def test_artifact_paths_reject_literal_backslash_on_posix(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    artifact = repository / "results" / "record\\name.json"
    artifact.parent.mkdir(parents=True)
    artifact.touch()

    with pytest.raises(ArtifactIdentityError):
        normalize_repository_path(repository, artifact)


def test_artifact_paths_reject_existing_symlink_components(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    target = repository / "target"
    link = repository / "linked"
    target.mkdir(parents=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(ArtifactIdentityError, match="symlink"):
        normalize_repository_path(repository, link / "record.json")
