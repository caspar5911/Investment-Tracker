"""Exact, nonexecuting authority seal for the pre-campaign result schema."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Literal

from pydantic import Field

from investment_tracker.quant.phase4.engine.models import FrozenGate2Model
from investment_tracker.quant.phase4.engine.source_identity import SourceBundleIdentity, source_bundle_identity
from investment_tracker.quant.phase4.gate3.filesystem import contained_path, resolve_repository_root
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity, DataPartitionIdentity, SafetyState, Gate3AuthorityError
from investment_tracker.quant.phase4.gate3.seal import GATE1_MANIFEST_IDENTITY, GATE2_MANIFEST_IDENTITY, TRAIN_IDENTITY, VALIDATION_IDENTITY, _validate_source_revision, preflight_gate3
from investment_tracker.quant.phase4.gate3_execution.campaign import POPULATION_SHA256
from investment_tracker.quant.phase4.gate3_execution.methodology import CORRECTED_GATE3_MANIFEST, preflight_execution_methodology
from investment_tracker.quant.phase4.preregistration.canonical import artifact_envelope_identity, canonical_json_bytes, normalize_repository_path
from investment_tracker.quant.phase4.preregistration.policy import SURVIVOR_POLICY

from .dependencies import EXECUTION_CONTENT, ResultAuthority, load_dependencies

SPEC_PATH = 'docs/superpowers/specs/2026-09-16-phase-4-gate-3-campaign-result-schema-design.md'
SPEC_CONTENT_SHA256 = 'cd62102571fa348ff734c6b992c92c0eaea8732f6e8dc43223e975f972ba8396'
SOURCE_FILES = tuple(sorted('src/investment_tracker/quant/phase4/gate3_campaign/' + name for name in (
    '__init__.py','codec.py','dependencies.py','result_artifacts.py','result_methodology.py','result_schema.py','validation.py','cli.py')))


class ResultSchemaManifest(FrozenGate2Model):
    schema_version: Literal['PHASE4-GATE3-RESULT-SCHEMA-AUTHORITY-v1'] = 'PHASE4-GATE3-RESULT-SCHEMA-AUTHORITY-v1'
    status: Literal['GATE3_CAMPAIGN_RESULT_SCHEMA_SEALED'] = 'GATE3_CAMPAIGN_RESULT_SCHEMA_SEALED'
    spec: ArtifactIdentity
    schema_contract: ArtifactIdentity
    gate1_manifest: ArtifactIdentity
    gate2_manifest: ArtifactIdentity
    gate3_authority_manifest: ArtifactIdentity
    execution_methodology: ArtifactIdentity
    survivor_policy: ArtifactIdentity
    durability_policy: ArtifactIdentity
    family_stop_policy_container: ArtifactIdentity
    candidate_population_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    candidate_count: Literal[180] = 180
    train_identity: DataPartitionIdentity
    validation_identity: DataPartitionIdentity
    engine_implementation_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    source_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    source_bundle: SourceBundleIdentity | None
    result_identity_algorithm: Literal['SHA256_CANONICAL_JSON_FULL_TYPED_RESULT'] = 'SHA256_CANONICAL_JSON_FULL_TYPED_RESULT'
    safety: SafetyState = SafetyState()


class ResultSchemaPreflight(FrozenGate2Model):
    gate1: Literal['VALID'] = 'VALID'
    gate2: Literal['VALID'] = 'VALID'
    gate3_authorities: Literal['VALID'] = 'VALID'
    execution_methodology: Literal['BOUND'] = 'BOUND'
    candidate_population: Literal[180] = 180
    survivor_policy: Literal['BOUND'] = 'BOUND'
    durability_policy: Literal['BOUND'] = 'BOUND'
    family_stop_policy: Literal['BOUND'] = 'BOUND'
    campaign_result_schema: Literal['BOUND'] = 'BOUND'
    result_schema_source_bundle: Literal['BOUND'] = 'BOUND'
    status: Literal['GATE3_CAMPAIGN_RESULT_SCHEMA_SEALED'] = 'GATE3_CAMPAIGN_RESULT_SCHEMA_SEALED'
    manifest: ArtifactIdentity
    safety: SafetyState = SafetyState()


def spec_identity(root: Path) -> ArtifactIdentity:
    repository = resolve_repository_root(root, code='RESULT_SCHEMA_SPEC_MISMATCH')
    path = contained_path(repository, tuple(SPEC_PATH.split('/')), code='RESULT_SCHEMA_SPEC_MISMATCH')
    content = sha256(path.read_bytes()).hexdigest()
    if content != SPEC_CONTENT_SHA256:
        raise ValueError('RESULT_SCHEMA_SPEC_MISMATCH: exact specification changed')
    return ArtifactIdentity(kind='phase4_gate3_result_schema_spec', content_sha256=content, path=SPEC_PATH,
                            sha256=artifact_envelope_identity(content_sha256=content,kind='phase4_gate3_result_schema_spec',path=SPEC_PATH))


def schema_contract(root: Path) -> dict[str, object]:
    deps = load_dependencies(root)
    return {
        'schema_version':'PHASE4-GATE3-RESULT-SCHEMA-CONTRACT-v1',
        'candidate_result_schema':'PHASE4-GATE3-CANDIDATE-RESULT-v1',
        'canonical_result_identity':'SHA256_CANONICAL_JSON_FULL_TYPED_RESULT',
        'survivor_hard_gate_count':12,'survivor_ordering_key_count':22,
        'survivor_ranking_keys':list(SURVIVOR_POLICY.ranking_keys),
        'authoritative_generic_result_dict':False,'campaign_execution_entrypoint':False,
        'decision_grade':False,'execution_series':'QFQ_NORMALIZED','primary_friction_bps':3,
        'statuses':['EXECUTED','UNKNOWN','ABSTAIN','SKIPPED_FAMILY_STOP','CAMPAIGN_EXECUTION_FAILED'],
        'friction_cases_bps':[0,3,10,25,50],'fold_ids':['FOLD_2019','FOLD_2020','FOLD_2021','FOLD_2022'],
        'regime_ids':['broad_negative_trend','broad_positive_trend','mixed_cross_asset'],
        'bootstrap':{'statistic':'median_daily_return','draws':2000,'seed':0},
        'dq030':{'max_drawdown':'UNKNOWN','calmar':'UNKNOWN','dsr':'UNKNOWN/NOT_IMPLEMENTED','pbo':'UNKNOWN/NOT_IMPLEMENTED'},
        'pre_candidate':True,'candidate_executed':False,'validation_candidate_performance_accessed':False,
    }


class AuthorityStore:
    _FILES={'result_schema_contract':'contract.json','gate3_result_schema_manifest':'manifest.json'}
    def __init__(self, root: Path):
        try:
            self.root=resolve_repository_root(root,code='ARTIFACT_PATH_INVALID')
            contained_path(self.root,('results','phase4','gate3','campaign_result_schema'),code='ARTIFACT_PATH_INVALID')
        except Gate3AuthorityError as exc: raise ValueError('ARTIFACT_PATH_INVALID') from exc
    def _path(self,kind,content):
        if kind not in self._FILES or re.fullmatch(r'[0-9a-f]{64}',content) is None: raise ValueError('ARTIFACT_IDENTITY_INVALID')
        try: return contained_path(self.root,('results','phase4','gate3','campaign_result_schema',kind,'sha256',content,self._FILES[kind]),code='ARTIFACT_PATH_INVALID')
        except Gate3AuthorityError as exc: raise ValueError('ARTIFACT_PATH_INVALID') from exc
    def identity(self,kind,document):
        content=sha256(canonical_json_bytes(document)).hexdigest(); path=self._path(kind,content); relative=normalize_repository_path(self.root,path)
        return ArtifactIdentity(kind=kind,content_sha256=content,path=relative,sha256=artifact_envelope_identity(content_sha256=content,kind=kind,path=relative))
    def write(self,kind,document):
        payload=canonical_json_bytes(document); identity=self.identity(kind,document); destination=self._path(kind,identity.content_sha256)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file() or destination.read_bytes()!=payload: raise ValueError('IMMUTABLE_ARTIFACT_COLLISION')
            return identity
        destination.parent.mkdir(parents=True,exist_ok=True); self._path(kind,identity.content_sha256)
        handle,name=tempfile.mkstemp(prefix='.tmp-result-schema-',dir=destination.parent); temporary=Path(name)
        try:
            with os.fdopen(handle,'wb') as stream: stream.write(payload);stream.flush();os.fsync(stream.fileno())
            try: os.link(temporary,destination)
            except FileExistsError:
                if destination.read_bytes()!=payload: raise ValueError('IMMUTABLE_ARTIFACT_COLLISION')
        finally: temporary.unlink(missing_ok=True)
        return identity
    def read(self,identity):
        path=self._path(identity.kind,identity.content_sha256)
        expected=ArtifactIdentity(kind=identity.kind,content_sha256=identity.content_sha256,path=normalize_repository_path(self.root,path),sha256=artifact_envelope_identity(content_sha256=identity.content_sha256,kind=identity.kind,path=normalize_repository_path(self.root,path)))
        if identity!=expected: raise ValueError('ARTIFACT_IDENTITY_INVALID')
        payload=path.read_bytes()
        if sha256(payload).hexdigest()!=identity.content_sha256: raise ValueError('ARTIFACT_BYTES_INVALID')
        parsed=json.loads(payload)
        if canonical_json_bytes(parsed)!=payload: raise ValueError('ARTIFACT_BYTES_INVALID')
        return parsed


def _contract_identity(root): return AuthorityStore(root).identity('result_schema_contract',schema_contract(root))


def declared_manifest(root: Path, source_revision: str, source_bundle: SourceBundleIdentity | None) -> ResultSchemaManifest:
    deps=load_dependencies(root); survivor,durability,budget=deps.policy_identities
    return ResultSchemaManifest(spec=spec_identity(root),schema_contract=_contract_identity(root),gate1_manifest=GATE1_MANIFEST_IDENTITY,
        gate2_manifest=GATE2_MANIFEST_IDENTITY,gate3_authority_manifest=CORRECTED_GATE3_MANIFEST,execution_methodology=deps.execution,
        survivor_policy=survivor,durability_policy=durability,family_stop_policy_container=budget,candidate_population_sha256=POPULATION_SHA256,
        train_identity=TRAIN_IDENTITY,validation_identity=VALIDATION_IDENTITY,
        engine_implementation_sha256=deps.engine_sha256,source_revision=source_revision,source_bundle=source_bundle)


def validate_declared_manifest(root: Path, manifest: ResultSchemaManifest, *, require_source: bool=True) -> None:
    expected=declared_manifest(root,manifest.source_revision,manifest.source_bundle)
    fields=set(ResultSchemaManifest.model_fields)-{'source_bundle'}
    if any(getattr(manifest,name)!=getattr(expected,name) for name in fields): raise ValueError('RESULT_SCHEMA_DEPENDENCY_MISMATCH')
    if require_source:
        if manifest.source_bundle is None or manifest.source_bundle.producing_revision!=manifest.source_revision: raise ValueError('RESULT_SCHEMA_SOURCE_MISMATCH')
        _validate_source_revision(resolve_repository_root(root,code='RESULT_SCHEMA_SOURCE_MISMATCH'),manifest.source_revision)
        if source_bundle_identity(root,manifest.source_revision,SOURCE_FILES)!=manifest.source_bundle: raise ValueError('RESULT_SCHEMA_SOURCE_MISMATCH')
    if preflight_gate3(root,CORRECTED_GATE3_MANIFEST.content_sha256).gate3!='READY': raise ValueError('RESULT_SCHEMA_DEPENDENCY_MISMATCH')
    if preflight_execution_methodology(root,EXECUTION_CONTENT).gate3!='GATE3_CAMPAIGN_READY_TO_EXECUTE': raise ValueError('RESULT_SCHEMA_DEPENDENCY_MISMATCH')


def seal_result_schema(root: Path, source_revision: str) -> ArtifactIdentity:
    repository=resolve_repository_root(root,code='RESULT_SCHEMA_SOURCE_MISMATCH')
    bundle=source_bundle_identity(repository,source_revision,SOURCE_FILES)
    manifest=declared_manifest(repository,source_revision,bundle);validate_declared_manifest(repository,manifest)
    store=AuthorityStore(repository)
    if store.write('result_schema_contract',schema_contract(repository))!=manifest.schema_contract: raise ValueError('RESULT_SCHEMA_DEPENDENCY_MISMATCH')
    return store.write('gate3_result_schema_manifest',manifest.model_dump(mode='json'))


def _load_manifest(root,digest):
    if re.fullmatch(r'[0-9a-f]{64}',digest) is None: raise ValueError('RESULT_SCHEMA_MANIFEST_MISSING')
    store=AuthorityStore(root); identity=ArtifactIdentity(kind='gate3_result_schema_manifest',content_sha256=digest,
        path=f'results/phase4/gate3/campaign_result_schema/gate3_result_schema_manifest/sha256/{digest}/manifest.json',
        sha256=artifact_envelope_identity(content_sha256=digest,kind='gate3_result_schema_manifest',path=f'results/phase4/gate3/campaign_result_schema/gate3_result_schema_manifest/sha256/{digest}/manifest.json'))
    try: return identity,ResultSchemaManifest.model_validate(store.read(identity))
    except (OSError,ValueError,KeyError) as exc: raise ValueError('RESULT_SCHEMA_MANIFEST_MISSING') from exc


def preflight_result_schema(root: Path, manifest_content_sha256: str) -> ResultSchemaPreflight:
    identity,manifest=_load_manifest(root,manifest_content_sha256);validate_declared_manifest(root,manifest)
    store=AuthorityStore(root)
    if store.read(manifest.schema_contract)!=schema_contract(root): raise ValueError('RESULT_SCHEMA_DEPENDENCY_MISMATCH')
    return ResultSchemaPreflight(manifest=identity)


def load_result_authority(root: Path, digest: str) -> ResultAuthority:
    _,manifest=_load_manifest(root,digest);preflight_result_schema(root,digest)
    return ResultAuthority(load_dependencies(root),manifest.source_revision)
