from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile

from investment_tracker.quant.phase4.engine.source_identity import source_bundle_identity
from investment_tracker.quant.phase4.gate3.filesystem import contained_path, resolve_repository_root
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity, Gate3AuthorityError
from investment_tracker.quant.phase4.gate3.seal import _validate_source_revision
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    normalize_repository_path,
)

from .artifacts import FinalizationArtifactStore
from .audit import (
    CAMPAIGN_AGGREGATE_SHA256,
    CAMPAIGN_RESULT_SET_IDENTITY,
    CANDIDATE_POPULATION_SHA256,
    RESULT_SCHEMA_MANIFEST_IDENTITY,
    RUNNER_MANIFEST_IDENTITY,
)
from .models import FinalizationManifest, FinalizationPreflight, Phase4Decision


SPEC_PATH = "docs/superpowers/specs/2026-09-18-phase-4-finalization-design.md"
SOURCE_FILES = tuple(
    sorted(
        "src/investment_tracker/quant/phase4/finalization/" + name
        for name in (
            "__init__.py",
            "artifacts.py",
            "audit.py",
            "cli.py",
            "methodology.py",
            "models.py",
            "selection.py",
        )
    )
)


def spec_identity(repository_root: Path) -> ArtifactIdentity:
    root = resolve_repository_root(
        repository_root,
        code="PHASE4_FINALIZATION_SPEC_MISMATCH",
    )
    try:
        path = contained_path(
            root,
            tuple(SPEC_PATH.split("/")),
            code="PHASE4_FINALIZATION_SPEC_MISMATCH",
        )
    except Gate3AuthorityError as exc:
        raise ValueError("PHASE4_FINALIZATION_SPEC_MISMATCH") from exc
    if path.is_symlink() or not path.is_file():
        raise ValueError("PHASE4_FINALIZATION_SPEC_MISMATCH")
    content = sha256(path.read_bytes()).hexdigest()
    return ArtifactIdentity(
        kind="phase4_finalization_spec",
        content_sha256=content,
        path=SPEC_PATH,
        sha256=artifact_envelope_identity(
            content_sha256=content,
            kind="phase4_finalization_spec",
            path=SPEC_PATH,
        ),
    )


class FinalizationAuthorityStore:
    def __init__(self, repository_root: Path) -> None:
        try:
            self.root = resolve_repository_root(
                repository_root,
                code="PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID",
            )
            contained_path(
                self.root,
                ("results", "phase4", "finalization", "manifest"),
                code="PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID") from exc

    def _path(self, content: str) -> Path:
        if re.fullmatch(r"[0-9a-f]{64}", content) is None:
            raise ValueError("ARTIFACT_IDENTITY_INVALID")
        try:
            return contained_path(
                self.root,
                (
                    "results",
                    "phase4",
                    "finalization",
                    "manifest",
                    "sha256",
                    content,
                    "manifest.json",
                ),
                code="PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("PHASE4_FINALIZATION_ARTIFACT_PATH_INVALID") from exc

    def identity(self, content: str) -> ArtifactIdentity:
        path = self._path(content)
        relative = normalize_repository_path(self.root, path)
        return ArtifactIdentity(
            kind="phase4_finalization_manifest",
            content_sha256=content,
            path=relative,
            sha256=artifact_envelope_identity(
                content_sha256=content,
                kind="phase4_finalization_manifest",
                path=relative,
            ),
        )

    def write(self, manifest: FinalizationManifest) -> ArtifactIdentity:
        payload = canonical_json_bytes(manifest.model_dump(mode="json"))
        identity = self.identity(sha256(payload).hexdigest())
        destination = self._path(identity.content_sha256)
        if destination.exists() or destination.is_symlink():
            if (
                destination.is_symlink()
                or not destination.is_file()
                or destination.read_bytes() != payload
            ):
                raise ValueError("IMMUTABLE_ARTIFACT_COLLISION")
            return identity
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(
            prefix=".tmp-phase4-finalization-manifest-",
            dir=destination.parent,
        )
        temporary = Path(name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if destination.read_bytes() != payload:
                    raise ValueError("IMMUTABLE_ARTIFACT_COLLISION")
        finally:
            temporary.unlink(missing_ok=True)
        return identity

    def read(self, identity: ArtifactIdentity) -> FinalizationManifest:
        expected = self.identity(identity.content_sha256)
        if identity != expected:
            raise ValueError("ARTIFACT_IDENTITY_INVALID")
        path = self._path(identity.content_sha256)
        if path.is_symlink() or not path.is_file():
            raise ValueError("FINALIZATION_MANIFEST_MISSING")
        payload = path.read_bytes()
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise ValueError("ARTIFACT_BYTES_INVALID")
        try:
            parsed = json.loads(payload)
            if canonical_json_bytes(parsed) != payload:
                raise ValueError("noncanonical")
            manifest = FinalizationManifest.model_validate_json(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ValueError("ARTIFACT_BYTES_INVALID") from exc
        return manifest


def _validate_manifest(root: Path, manifest: FinalizationManifest) -> tuple:
    if manifest.spec != spec_identity(root):
        raise ValueError("PHASE4_FINALIZATION_SPEC_MISMATCH")
    _validate_source_revision(root, manifest.source_revision)
    if source_bundle_identity(root, manifest.source_revision, SOURCE_FILES) != manifest.source_bundle:
        raise ValueError("PHASE4_FINALIZATION_SOURCE_MISMATCH")
    if (
        manifest.campaign_result_set != CAMPAIGN_RESULT_SET_IDENTITY
        or manifest.campaign_aggregate_sha256 != CAMPAIGN_AGGREGATE_SHA256
        or manifest.candidate_population_sha256 != CANDIDATE_POPULATION_SHA256
        or manifest.runner_manifest != RUNNER_MANIFEST_IDENTITY
        or manifest.result_schema_manifest != RESULT_SCHEMA_MANIFEST_IDENTITY
    ):
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
    artifacts = FinalizationArtifactStore(root)
    audit = artifacts.read_audit(manifest.audit_artifact)
    decision = artifacts.read_decision(manifest.decision_artifact)
    if (
        audit.campaign_result_set != manifest.campaign_result_set
        or audit.campaign_aggregate_sha256 != manifest.campaign_aggregate_sha256
        or audit.candidate_population_sha256 != manifest.candidate_population_sha256
        or audit.runner_manifest != manifest.runner_manifest
        or audit.result_schema_manifest != manifest.result_schema_manifest
        or audit.survivor_policy != manifest.survivor_policy
        or audit.durability_policy != manifest.durability_policy
        or decision.audit_artifact != manifest.audit_artifact
        or decision.campaign_result_set != manifest.campaign_result_set
        or decision.survivor_policy != manifest.survivor_policy
        or decision.durability_policy != manifest.durability_policy
    ):
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
    return audit, decision


def seal_finalization(
    repository_root: Path,
    *,
    source_revision: str,
    audit_identity: ArtifactIdentity,
    decision_identity: ArtifactIdentity,
) -> ArtifactIdentity:
    root = resolve_repository_root(
        repository_root,
        code="PHASE4_FINALIZATION_SOURCE_MISMATCH",
    )
    _validate_source_revision(root, source_revision)
    artifacts = FinalizationArtifactStore(root)
    audit = artifacts.read_audit(audit_identity)
    decision = artifacts.read_decision(decision_identity)
    if decision.audit_artifact != audit_identity:
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
    bundle = source_bundle_identity(root, source_revision, SOURCE_FILES)
    manifest = FinalizationManifest(
        spec=spec_identity(root),
        source_revision=source_revision,
        source_bundle=bundle,
        campaign_result_set=CAMPAIGN_RESULT_SET_IDENTITY,
        campaign_aggregate_sha256=CAMPAIGN_AGGREGATE_SHA256,
        candidate_population_sha256=CANDIDATE_POPULATION_SHA256,
        runner_manifest=RUNNER_MANIFEST_IDENTITY,
        result_schema_manifest=RESULT_SCHEMA_MANIFEST_IDENTITY,
        survivor_policy=audit.survivor_policy,
        durability_policy=audit.durability_policy,
        audit_artifact=audit_identity,
        decision_artifact=decision_identity,
    )
    _validate_manifest(root, manifest)
    return FinalizationAuthorityStore(root).write(manifest)


def preflight_finalization(
    repository_root: Path,
    manifest_content_sha256: str,
) -> FinalizationPreflight:
    if re.fullmatch(r"[0-9a-f]{64}", manifest_content_sha256) is None:
        raise ValueError("FINALIZATION_MANIFEST_MISSING")
    root = resolve_repository_root(
        repository_root,
        code="PHASE4_FINALIZATION_EVIDENCE_INVALID",
    )
    store = FinalizationAuthorityStore(root)
    identity = store.identity(manifest_content_sha256)
    try:
        manifest = store.read(identity)
    except (OSError, ValueError) as exc:
        raise ValueError("FINALIZATION_MANIFEST_MISSING") from exc
    audit, decision = _validate_manifest(root, manifest)
    return FinalizationPreflight(
        manifest=identity,
        decision_status=decision.status,
        eligible_candidate_count=len(audit.eligible_candidate_ids),
    )
