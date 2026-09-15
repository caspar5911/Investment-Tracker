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
from .inputs import load_frozen_authority_inputs
from .models import (
    ArtifactIdentity,
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
    root = Path(repository_root).resolve(strict=True)
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
    root = Path(repository_root).resolve(strict=True)
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
    _validate_source_revision(root, manifest.source_revision)
    return manifest


def preflight_gate3(
    repository_root: Path, manifest_content_sha256: str
) -> Gate3Preflight:
    manifest = load_and_verify_gate3_authority(repository_root, manifest_content_sha256)
    return Gate3Preflight(candidate_population=manifest.candidate_population, safety=manifest.safety)
