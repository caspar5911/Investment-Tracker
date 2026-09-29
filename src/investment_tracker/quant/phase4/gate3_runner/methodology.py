from __future__ import annotations

from hashlib import sha256
from importlib import import_module
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Literal

from pydantic import Field

from investment_tracker.quant.phase4.engine.models import FrozenGate2Model
from investment_tracker.quant.phase4.engine.source_identity import (
    SourceBundleIdentity,
    source_bundle_identity,
)
from investment_tracker.quant.phase4.gate3.filesystem import (
    contained_path,
    resolve_repository_root,
)
from investment_tracker.quant.phase4.gate3.models import (
    ArtifactIdentity,
    DataPartitionIdentity,
    Gate3AuthorityError,
    SafetyState,
)
from investment_tracker.quant.phase4.gate3.seal import (
    GATE1_MANIFEST_IDENTITY,
    GATE2_MANIFEST_IDENTITY,
    TRAIN_IDENTITY,
    VALIDATION_IDENTITY,
    _validate_source_revision,
    preflight_gate3,
)
from investment_tracker.quant.phase4.gate3_campaign import result_methodology
from investment_tracker.quant.phase4.gate3_execution.campaign import POPULATION_SHA256
from investment_tracker.quant.phase4.gate3_execution.methodology import (
    CORRECTED_GATE3_MANIFEST,
    preflight_execution_methodology,
)
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    normalize_repository_path,
)

from .dependencies import (
    RESULT_SCHEMA_CONTENT,
    SCORED_PANEL_SHA256,
    load_runner_dependencies,
)


SPEC_PATH = (
    "docs/superpowers/specs/"
    "2026-09-16-phase-4-gate-3-campaign-orchestrator-design.md"
)
SPEC_CONTENT_SHA256 = (
    "6d4c2ba976bf5d388ea5bf490bac1e441d0256fc6b786c94a0292e2feebae3c3"
)
SOURCE_FILES = tuple(
    sorted(
        "src/investment_tracker/quant/phase4/gate3_runner/" + name
        for name in (
            "__init__.py",
            "cli.py",
            "dependencies.py",
            "methodology.py",
            "models.py",
            "orchestrator.py",
            "state.py",
        )
    )
)
BUNDLE_FILES = tuple(sorted((*SOURCE_FILES, SPEC_PATH)))


class RunnerManifest(FrozenGate2Model):
    schema_version: Literal["PHASE4-GATE3-CAMPAIGN-RUNNER-AUTHORITY-v1"] = (
        "PHASE4-GATE3-CAMPAIGN-RUNNER-AUTHORITY-v1"
    )
    status: Literal["GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE"] = (
        "GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE"
    )
    spec: ArtifactIdentity
    gate1_manifest: ArtifactIdentity
    gate2_manifest: ArtifactIdentity
    gate3_authority_manifest: ArtifactIdentity
    execution_methodology: ArtifactIdentity
    result_schema_manifest: ArtifactIdentity
    result_schema_contract: ArtifactIdentity
    survivor_policy: ArtifactIdentity
    durability_policy: ArtifactIdentity
    family_stop_policy_container: ArtifactIdentity
    candidate_population_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_count: Literal[180] = 180
    train_identity: DataPartitionIdentity
    validation_identity: DataPartitionIdentity
    scored_market_panel_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_bundle: SourceBundleIdentity | None
    attempt_schema: Literal["PHASE4-GATE3-RUNNER-ATTEMPT-v1"] = (
        "PHASE4-GATE3-RUNNER-ATTEMPT-v1"
    )
    receipt_schema: Literal["PHASE4-GATE3-RUNNER-RECEIPT-v1"] = (
        "PHASE4-GATE3-RUNNER-RECEIPT-v1"
    )
    result_set_schema: Literal["PHASE4-GATE3-CAMPAIGN-RESULT-SET-v1"] = (
        "PHASE4-GATE3-CAMPAIGN-RESULT-SET-v1"
    )
    run_entrypoint: Literal["EXPLICIT_HASH_PREFLIGHT_GATED"] = (
        "EXPLICIT_HASH_PREFLIGHT_GATED"
    )
    safety: SafetyState = SafetyState()


class RunnerPreflight(FrozenGate2Model):
    gate1: Literal["VALID"] = "VALID"
    gate2: Literal["VALID"] = "VALID"
    gate3_authorities: Literal["VALID"] = "VALID"
    execution_methodology: Literal["BOUND"] = "BOUND"
    result_schema: Literal["BOUND"] = "BOUND"
    candidate_population: Literal[180] = 180
    runner_source_bundle: Literal["BOUND"] = "BOUND"
    campaign_runner: Literal["BOUND"] = "BOUND"
    status: Literal["GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE"] = (
        "GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE"
    )
    manifest: ArtifactIdentity
    safety: SafetyState = SafetyState()


def spec_identity(root: Path) -> ArtifactIdentity:
    repository = resolve_repository_root(root, code="RUNNER_SPEC_MISMATCH")
    path = contained_path(
        repository,
        tuple(SPEC_PATH.split("/")),
        code="RUNNER_SPEC_MISMATCH",
    )
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError("RUNNER_SPEC_MISMATCH") from exc
    content = sha256(payload).hexdigest()
    if content != SPEC_CONTENT_SHA256:
        raise ValueError("RUNNER_SPEC_MISMATCH")
    return ArtifactIdentity(
        kind="phase4_gate3_runner_spec",
        content_sha256=content,
        path=SPEC_PATH,
        sha256=artifact_envelope_identity(
            content_sha256=content,
            kind="phase4_gate3_runner_spec",
            path=SPEC_PATH,
        ),
    )


class RunnerAuthorityStore:
    def __init__(self, root: Path) -> None:
        try:
            self.root = resolve_repository_root(root, code="ARTIFACT_PATH_INVALID")
            contained_path(
                self.root,
                ("results", "phase4", "gate3", "campaign_runner"),
                code="ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("ARTIFACT_PATH_INVALID") from exc

    def _path(self, content: str) -> Path:
        if re.fullmatch(r"[0-9a-f]{64}", content) is None:
            raise ValueError("RUNNER_MANIFEST_MISSING")
        try:
            return contained_path(
                self.root,
                (
                    "results",
                    "phase4",
                    "gate3",
                    "campaign_runner",
                    "runner_manifest",
                    "sha256",
                    content,
                    "manifest.json",
                ),
                code="ARTIFACT_PATH_INVALID",
            )
        except Gate3AuthorityError as exc:
            raise ValueError("ARTIFACT_PATH_INVALID") from exc

    def identity(self, document: dict[str, object]) -> ArtifactIdentity:
        payload = canonical_json_bytes(document)
        content = sha256(payload).hexdigest()
        path = self._path(content)
        relative = normalize_repository_path(self.root, path)
        return ArtifactIdentity(
            kind="gate3_campaign_runner_manifest",
            content_sha256=content,
            path=relative,
            sha256=artifact_envelope_identity(
                content_sha256=content,
                kind="gate3_campaign_runner_manifest",
                path=relative,
            ),
        )

    def write(self, document: dict[str, object]) -> ArtifactIdentity:
        payload = canonical_json_bytes(document)
        identity = self.identity(document)
        path = self._path(identity.content_sha256)
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
                raise ValueError("IMMUTABLE_ARTIFACT_COLLISION")
            return identity
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path(identity.content_sha256)
        handle, name = tempfile.mkstemp(
            prefix=".tmp-gate3-runner-seal-",
            dir=path.parent,
        )
        temporary = Path(name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
                    raise ValueError("IMMUTABLE_ARTIFACT_COLLISION")
        finally:
            temporary.unlink(missing_ok=True)
        return identity

    def read(self, identity: ArtifactIdentity) -> dict[str, object]:
        if identity.kind != "gate3_campaign_runner_manifest":
            raise ValueError("RUNNER_MANIFEST_MISSING")
        path = self._path(identity.content_sha256)
        relative = normalize_repository_path(self.root, path)
        expected = ArtifactIdentity(
            kind=identity.kind,
            content_sha256=identity.content_sha256,
            path=relative,
            sha256=artifact_envelope_identity(
                content_sha256=identity.content_sha256,
                kind=identity.kind,
                path=relative,
            ),
        )
        if identity != expected:
            raise ValueError("RUNNER_MANIFEST_MISSING")
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ValueError("RUNNER_MANIFEST_MISSING") from exc
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise ValueError("RUNNER_MANIFEST_MISSING")
        parsed = json.loads(payload)
        if canonical_json_bytes(parsed) != payload:
            raise ValueError("RUNNER_MANIFEST_MISSING")
        return parsed


def _result_schema_links(root: Path) -> tuple[ArtifactIdentity, ArtifactIdentity]:
    state = result_methodology.preflight_result_schema(root, RESULT_SCHEMA_CONTENT)
    identity, manifest = result_methodology._load_manifest(root, RESULT_SCHEMA_CONTENT)
    if (
        state.status != "GATE3_CAMPAIGN_RESULT_SCHEMA_SEALED"
        or state.manifest != identity
    ):
        raise ValueError("RUNNER_RESULT_SCHEMA_MISMATCH")
    return identity, manifest.schema_contract


def _verify_imported_sources(root: Path, bundle: SourceBundleIdentity) -> None:
    entries = {entry.path: entry for entry in bundle.entries}
    for relative in SOURCE_FILES:
        dotted = relative.removeprefix("src/").removesuffix(".py").replace("/", ".")
        if dotted.endswith(".__init__"):
            dotted = dotted.removesuffix(".__init__")
        module = import_module(dotted)
        imported = getattr(module, "__file__", None)
        expected = (root / relative).resolve()
        if imported is None or Path(imported).resolve() != expected:
            raise ValueError("RUNNER_SOURCE_MISMATCH")
        entry = entries.get(relative)
        if entry is None or sha256(expected.read_bytes()).hexdigest() != entry.content_sha256:
            raise ValueError("RUNNER_SOURCE_MISMATCH")


def declared_manifest(
    root: Path,
    source_revision: str,
    source_bundle: SourceBundleIdentity | None,
) -> RunnerManifest:
    runner = load_runner_dependencies(root)
    deps = runner.campaign
    survivor, durability, family_stop = deps.policy_identities
    gate3 = preflight_gate3(root, CORRECTED_GATE3_MANIFEST.content_sha256)
    if gate3.gate3 != "READY":
        raise ValueError("RUNNER_DEPENDENCY_MISMATCH")
    execution = preflight_execution_methodology(
        root,
        deps.execution.content_sha256,
    )
    if execution.gate3 != "GATE3_CAMPAIGN_READY_TO_EXECUTE":
        raise ValueError("RUNNER_DEPENDENCY_MISMATCH")
    result_schema, result_contract = _result_schema_links(root)
    return RunnerManifest(
        spec=spec_identity(root),
        gate1_manifest=GATE1_MANIFEST_IDENTITY,
        gate2_manifest=GATE2_MANIFEST_IDENTITY,
        gate3_authority_manifest=CORRECTED_GATE3_MANIFEST,
        execution_methodology=deps.execution,
        result_schema_manifest=result_schema,
        result_schema_contract=result_contract,
        survivor_policy=survivor,
        durability_policy=durability,
        family_stop_policy_container=family_stop,
        candidate_population_sha256=POPULATION_SHA256,
        train_identity=TRAIN_IDENTITY,
        validation_identity=VALIDATION_IDENTITY,
        scored_market_panel_sha256=SCORED_PANEL_SHA256,
        source_revision=source_revision,
        source_bundle=source_bundle,
    )


def validate_manifest(
    root: Path,
    manifest: RunnerManifest,
    *,
    require_source: bool = True,
) -> None:
    expected = declared_manifest(root, manifest.source_revision, manifest.source_bundle)
    fields = set(RunnerManifest.model_fields) - {"source_bundle"}
    if any(getattr(manifest, field) != getattr(expected, field) for field in fields):
        raise ValueError("RUNNER_DEPENDENCY_MISMATCH")
    if not require_source:
        return
    repository = resolve_repository_root(root, code="RUNNER_SOURCE_MISMATCH")
    if (
        manifest.source_bundle is None
        or manifest.source_bundle.producing_revision != manifest.source_revision
    ):
        raise ValueError("RUNNER_SOURCE_MISMATCH")
    _validate_source_revision(repository, manifest.source_revision)
    expected_bundle = source_bundle_identity(
        repository,
        manifest.source_revision,
        BUNDLE_FILES,
    )
    if expected_bundle != manifest.source_bundle:
        raise ValueError("RUNNER_SOURCE_MISMATCH")
    entry_map = {entry.path: entry.content_sha256 for entry in manifest.source_bundle.entries}
    if entry_map.get(SPEC_PATH) != manifest.spec.content_sha256:
        raise ValueError("RUNNER_SPEC_MISMATCH")
    _verify_imported_sources(repository, manifest.source_bundle)


def seal_runner(root: Path, source_revision: str) -> ArtifactIdentity:
    repository = resolve_repository_root(root, code="RUNNER_SOURCE_MISMATCH")
    bundle = source_bundle_identity(
        repository,
        source_revision,
        BUNDLE_FILES,
    )
    manifest = declared_manifest(repository, source_revision, bundle)
    validate_manifest(repository, manifest)
    return RunnerAuthorityStore(repository).write(manifest.model_dump(mode="json"))


def _load_manifest(
    root: Path,
    digest: str,
) -> tuple[ArtifactIdentity, RunnerManifest]:
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("RUNNER_MANIFEST_MISSING")
    relative = (
        "results/phase4/gate3/campaign_runner/runner_manifest/sha256/"
        f"{digest}/manifest.json"
    )
    identity = ArtifactIdentity(
        kind="gate3_campaign_runner_manifest",
        content_sha256=digest,
        path=relative,
        sha256=artifact_envelope_identity(
            content_sha256=digest,
            kind="gate3_campaign_runner_manifest",
            path=relative,
        ),
    )
    store = RunnerAuthorityStore(root)
    try:
        manifest = RunnerManifest.model_validate(store.read(identity))
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError("RUNNER_MANIFEST_MISSING") from exc
    return identity, manifest


def preflight_runner(
    root: Path,
    manifest_content_sha256: str,
) -> RunnerPreflight:
    identity, manifest = _load_manifest(root, manifest_content_sha256)
    validate_manifest(root, manifest)
    return RunnerPreflight(manifest=identity)


__all__ = (
    "BUNDLE_FILES",
    "RunnerManifest",
    "RunnerPreflight",
    "SOURCE_FILES",
    "SPEC_CONTENT_SHA256",
    "declared_manifest",
    "preflight_runner",
    "seal_runner",
    "spec_identity",
)
