from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import re
import subprocess

from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
)

from .artifacts import Gate3ArtifactStore
from .authorities import build_fold_authority, build_regime_authority
from .filesystem import resolve_repository_root
from .inputs import load_frozen_authority_inputs
from .models import (
    ArtifactIdentity,
    DataPartitionIdentity,
    Gate3AuthorityError,
    Gate3AuthorityManifest,
    Gate3Preflight,
    SafetyState,
)


GATE1_MANIFEST_IDENTITY = ArtifactIdentity(
    kind="phase4_preregistration_manifest",
    content_sha256="dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89",
    path="results/phase4/gate1/phase4_preregistration_manifest/sha256/dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89/manifest.json",
    sha256="e43ccbb596a9f66222b4e2785b1c40c423e6bb43b54b788e1fdb6358e1cdf146",
)
GATE2_MANIFEST_IDENTITY = ArtifactIdentity(
    kind="phase4_engine_manifest",
    content_sha256="c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6",
    path="results/phase4/gate2/phase4_engine_manifest/sha256/c410b8b496640a7e783eeed11fdda497c0c942fd33c9f5a8ee751681f9243fc6/manifest.json",
    sha256="ce029ee1534d2c073fee332bb27442143a56138a73a417b44c608b0959cb060d",
)
SPLIT_MANIFEST_IDENTITY = ArtifactIdentity(
    kind="phase4_split_manifest",
    content_sha256="b273f79795237caca08d1a10388be8d300e9f4b5f51c818a24456c972c7bb4d7",
    path="results/phase4/readiness/phase4_split_manifest/sha256/b273f79795237caca08d1a10388be8d300e9f4b5f51c818a24456c972c7bb4d7/manifest.json",
    sha256="3300510d6ea86aa077b5a2a2c2dd734d7e3602cc87513910af8db7c004fe0dab",
)
UNIVERSE_MANIFEST_IDENTITY = ArtifactIdentity(
    kind="phase3_universe_manifest",
    content_sha256="de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76",
    path="results/phase3/universes/de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76/manifest.json",
    sha256="2217e84065db40f8cb90480707a9dd0616914eb0ef370f6996ceb3dffa6c7142",
)
_DATASETS = (
    ("SPY", "a4a4f1b5a8450fa924ddadc706aec1101bdf2b495b29151de09e73178e511d05"),
    ("QQQ", "ca2757d1a036ad2722d21456253856b8b92eaeeaad4af3af868ceeb1dba3758e"),
    ("IWM", "0325881a86265152fb7b034711867d963f1d473946cffad513244fbbef1a3c0d"),
    ("TLT", "69318a0e60b0dbe0505c4994caeffc28c4f35ff92f706e0be8770db20a8b0c7c"),
    ("IEF", "68faebff989ae5dcb34eee7ad0502bd5bb84d23212e45c5c625d36b37092887c"),
    ("GLD", "5e0b465a2b4e15311b98632f1c27f6dea147d4df40ee1e22ca18f9788b2823e3"),
    ("VNQ", "cd06e2a58c78c88684ab7a2cee20922a6c29747e49d1af3f994370cd47d1e683"),
    ("XLP", "1e4689611200bd6c9a2725c860898575ceb9eaded6358daab74a05e829f8fb7c"),
)
TRAIN_IDENTITY = DataPartitionIdentity(
    stage="TRAIN",
    actual_start="2014-01-02",
    actual_end="2018-12-31",
    row_count=1258,
    sessions_sha256="7d932a1e45637404e2460107ab0f09b33d74d8a28360533bdb9fdaa96416d995",
    dataset_content_sha256_by_symbol=_DATASETS,
    sha256="54e0747d4723ced4994f9b9ad02c5b9d5feaa151de983f91f2ec4d8fcc2dba33",
)
VALIDATION_IDENTITY = DataPartitionIdentity(
    stage="VALIDATION",
    actual_start="2019-01-02",
    actual_end="2022-12-30",
    row_count=1008,
    sessions_sha256="330dc026e62cea178fc1f28df18ce6479726b4662838bf9454d354c2d00c13d6",
    dataset_content_sha256_by_symbol=_DATASETS,
    sha256="6515cd5957e8d3582140bb03c65ed0ea5ed11613c92a564a6bde0ccd383a7490",
)
SUPERSEDED_MANIFEST_CONTENT_SHA256 = (
    "83f4bec6bade156fc3e54534403e901319dc3fb97a26c27b22df2195fef70cfc"
)


def _canonical_authority_path(identity: ArtifactIdentity, kind: str) -> str:
    return (
        f"results/phase4/gate3/{kind}/sha256/"
        f"{identity.content_sha256}/authority.json"
    )


def validate_gate3_manifest_references(manifest: Gate3AuthorityManifest) -> None:
    if (
        manifest.gate1_manifest != GATE1_MANIFEST_IDENTITY
        or manifest.gate2_manifest != GATE2_MANIFEST_IDENTITY
        or manifest.universe_manifest != UNIVERSE_MANIFEST_IDENTITY
        or manifest.split_manifest != SPLIT_MANIFEST_IDENTITY
        or manifest.train_identity != TRAIN_IDENTITY
        or manifest.validation_identity != VALIDATION_IDENTITY
        or manifest.supersedes_manifest_content_sha256
        != SUPERSEDED_MANIFEST_CONTENT_SHA256
        or manifest.safety != SafetyState()
    ):
        raise Gate3AuthorityError(
            "AUTHORITY_DEPENDENCY_MISMATCH: manifest dependency is not approved"
        )
    for identity, kind in (
        (manifest.fold_authority, "fold_authority"),
        (manifest.regime_authority, "regime_authority"),
    ):
        if identity.kind != kind or identity.path != _canonical_authority_path(
            identity, kind
        ):
            raise Gate3AuthorityError(
                "AUTHORITY_REFERENCE_INVALID: noncanonical authority reference"
            )


def _validate_source_revision(root: Path, revision: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise Gate3AuthorityError("SOURCE_REVISION_INVALID: expected a full commit SHA")
    check = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", revision, "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if check.returncode != 0 or ancestor.returncode != 0:
        raise Gate3AuthorityError("SOURCE_REVISION_INVALID: source commit is not an ancestor of HEAD")


def seal_gate3_authorities(repository_root: Path, *, source_revision: str) -> ArtifactIdentity:
    root = resolve_repository_root(repository_root, code="INPUT_IDENTITY_MISMATCH")
    _validate_source_revision(root, source_revision)
    frozen = load_frozen_authority_inputs(
        root,
        gate1_identity=GATE1_MANIFEST_IDENTITY,
        gate2_identity=GATE2_MANIFEST_IDENTITY,
    )
    fold = build_fold_authority(frozen.validation_sessions)
    regime = build_regime_authority(
        frozen.all_sessions, frozen.close_by_symbol, frozen.validation_sessions
    )
    shared = {
        "frozen_before_gate3_candidate_results": True,
        "source_revision": source_revision,
        "gate1_manifest": frozen.gate1.model_dump(mode="json"),
        "gate2_manifest": frozen.gate2.model_dump(mode="json"),
        "universe_manifest": frozen.universe.model_dump(mode="json"),
        "split_manifest": frozen.split.model_dump(mode="json"),
        "train_identity": frozen.train_identity.model_dump(mode="json"),
        "validation_identity": frozen.validation_identity.model_dump(mode="json"),
        "safety": SafetyState().model_dump(mode="json"),
    }
    store = Gate3ArtifactStore(root)
    fold_identity = store.write_json(
        "fold_authority", {**shared, "authority": asdict(fold)}
    )
    regime_identity = store.write_json(
        "regime_authority", {**shared, "authority": asdict(regime)}
    )
    manifest = Gate3AuthorityManifest(
        source_revision=source_revision,
        supersedes_manifest_content_sha256=SUPERSEDED_MANIFEST_CONTENT_SHA256,
        gate1_manifest=frozen.gate1,
        gate2_manifest=frozen.gate2,
        universe_manifest=frozen.universe,
        split_manifest=frozen.split,
        train_identity=frozen.train_identity,
        validation_identity=frozen.validation_identity,
        fold_authority=fold_identity,
        regime_authority=regime_identity,
        safety=SafetyState(),
    )
    return store.write_json(
        "gate3_authority_manifest", manifest.model_dump(mode="json"), final=True
    )


def load_and_verify_gate3_authority(
    repository_root: Path, manifest_content_sha256: str
) -> Gate3AuthorityManifest:
    if re.fullmatch(r"[0-9a-f]{64}", manifest_content_sha256) is None:
        raise Gate3AuthorityError("AUTHORITY_MANIFEST_MISSING: invalid manifest digest")
    if manifest_content_sha256 == SUPERSEDED_MANIFEST_CONTENT_SHA256:
        raise Gate3AuthorityError(
            "AUTHORITY_MANIFEST_SUPERSEDED: select the corrected explicit authority"
        )
    root = resolve_repository_root(repository_root, code="ARTIFACT_PATH_INVALID")
    relative = (
        "results/phase4/gate3/gate3_authority_manifest/sha256/"
        f"{manifest_content_sha256}/manifest.json"
    )
    store = Gate3ArtifactStore(root)
    manifest_identity = ArtifactIdentity(
        kind="gate3_authority_manifest",
        content_sha256=manifest_content_sha256,
        path=relative,
        sha256=artifact_envelope_identity(
            content_sha256=manifest_content_sha256,
            kind="gate3_authority_manifest",
            path=relative,
        ),
    )
    try:
        payload = store.verify(manifest_identity)
    except Gate3AuthorityError as exc:
        raise Gate3AuthorityError("AUTHORITY_MANIFEST_MISSING: exact manifest not found") from exc
    try:
        parsed = json.loads(payload)
        if canonical_json_bytes(parsed) != payload:
            raise ValueError("noncanonical")
        manifest = Gate3AuthorityManifest.model_validate(parsed)
    except (ValueError, json.JSONDecodeError) as exc:
        raise Gate3AuthorityError("AUTHORITY_MANIFEST_MISMATCH: manifest invalid") from exc
    validate_gate3_manifest_references(manifest)
    _validate_source_revision(root, manifest.source_revision)
    fold_payload = store.verify(manifest.fold_authority)
    regime_payload = store.verify(manifest.regime_authority)
    frozen = load_frozen_authority_inputs(
        root,
        gate1_identity=manifest.gate1_manifest,
        gate2_identity=manifest.gate2_manifest,
    )
    if (
        manifest.gate1_manifest != GATE1_MANIFEST_IDENTITY
        or manifest.gate2_manifest != GATE2_MANIFEST_IDENTITY
        or manifest.universe_manifest != frozen.universe
        or manifest.split_manifest != frozen.split
        or manifest.train_identity != frozen.train_identity
        or manifest.validation_identity != frozen.validation_identity
    ):
        raise Gate3AuthorityError("AUTHORITY_DEPENDENCY_MISMATCH: frozen identities differ")
    expected_fold = {
        "frozen_before_gate3_candidate_results": True,
        "source_revision": manifest.source_revision,
        "gate1_manifest": frozen.gate1.model_dump(mode="json"),
        "gate2_manifest": frozen.gate2.model_dump(mode="json"),
        "universe_manifest": frozen.universe.model_dump(mode="json"),
        "split_manifest": frozen.split.model_dump(mode="json"),
        "train_identity": frozen.train_identity.model_dump(mode="json"),
        "validation_identity": frozen.validation_identity.model_dump(mode="json"),
        "safety": SafetyState().model_dump(mode="json"),
        "authority": asdict(build_fold_authority(frozen.validation_sessions)),
    }
    expected_regime = {
        **{key: value for key, value in expected_fold.items() if key != "authority"},
        "authority": asdict(
            build_regime_authority(
                frozen.all_sessions, frozen.close_by_symbol, frozen.validation_sessions
            )
        ),
    }
    if fold_payload != canonical_json_bytes(expected_fold) or regime_payload != canonical_json_bytes(expected_regime):
        raise Gate3AuthorityError("AUTHORITY_MAPPING_MISMATCH: authority does not recompute")
    return manifest


def preflight_gate3(
    repository_root: Path, manifest_content_sha256: str
) -> Gate3Preflight:
    manifest = load_and_verify_gate3_authority(repository_root, manifest_content_sha256)
    return Gate3Preflight(candidate_population=manifest.candidate_population, safety=manifest.safety)
