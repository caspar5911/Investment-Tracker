from __future__ import annotations

from datetime import date
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import Field, ValidationError, model_validator

from investment_tracker.governance import assert_symbol_allowed
from investment_tracker.quant.data.cache import content_hash
from investment_tracker.quant.universe.models import (
    DQSnapshot,
    NormalizedDatasetMetadata,
    UniverseManifest,
)

from .constants import (
    PHASE3_DATASETS,
    PHASE3_DQ_SNAPSHOT_PATH,
    PHASE3_DQ_SNAPSHOT_SHA256,
    PHASE3_SYMBOLS,
    PHASE3_UNIVERSE_PATH,
    PHASE3_UNIVERSE_SHA256,
    PHASE4_SPLIT_POLICY_VERSION,
    PHASE4_TRAIN_END,
    PHASE4_TRAIN_ROW_COUNT,
    PHASE4_TRAIN_START,
    PHASE4_VALIDATION_END,
    PHASE4_VALIDATION_ROW_COUNT,
    PHASE4_VALIDATION_START,
    PinnedPhase3Dataset,
)
from .hashing import canonical_json_bytes, canonical_sha256, normalize_repository_path
from .models import FrozenReadinessModel, ReadinessArtifactIdentity


class Phase3DependencyError(RuntimeError):
    """Raised when frozen Phase 3 evidence cannot be verified exactly."""


def _sessions_sha256(sessions: tuple[date, ...]) -> str:
    return canonical_sha256(tuple(session.isoformat() for session in sessions))


def _phase3_identity_path(repository_path: str) -> str:
    for prefix in ("results/", "data/cache/"):
        if repository_path.startswith(prefix):
            return repository_path.removeprefix(prefix)
    raise Phase3DependencyError("Phase 3 dependency path has an invalid root")


def _artifact_identity_from_bytes(
    repository_path: str,
    kind: Literal[
        "phase3_universe_manifest",
        "phase3_dq_snapshot",
        "phase3_normalized_dataset",
    ],
    payload: bytes,
) -> ReadinessArtifactIdentity:
    content_sha256 = sha256(payload).hexdigest()
    envelope = {
        "content_sha256": content_sha256,
        "kind": kind,
        "path": repository_path,
    }
    return ReadinessArtifactIdentity(
        **envelope,
        sha256=canonical_sha256(envelope),
    )


def _exact_file(repository_root: Path, repository_path: str) -> tuple[Path, bytes]:
    relative = Path(*repository_path.split("/"))
    try:
        normalized = normalize_repository_path(repository_root, relative)
    except (OSError, ValueError) as exc:
        raise Phase3DependencyError(
            f"Phase 3 dependency path is invalid: {repository_path}"
        ) from exc
    if normalized != repository_path:
        raise Phase3DependencyError(
            f"Phase 3 dependency path mismatch: {repository_path}"
        )
    path = Path(repository_root).resolve(strict=True).joinpath(*relative.parts)
    if not path.is_file() or path.is_symlink():
        raise Phase3DependencyError(
            f"Phase 3 dependency is missing or non-regular: {repository_path}"
        )
    try:
        return path, path.read_bytes()
    except OSError as exc:
        raise Phase3DependencyError(
            f"Phase 3 dependency is unreadable: {repository_path}"
        ) from exc


def _exact_json(
    repository_root: Path,
    repository_path: str,
    expected_sha256: str,
    kind: Literal[
        "phase3_universe_manifest",
        "phase3_dq_snapshot",
        "phase3_normalized_dataset",
    ],
) -> tuple[dict[str, object], ReadinessArtifactIdentity]:
    _, raw = _exact_file(repository_root, repository_path)
    actual_sha256 = sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        raise Phase3DependencyError(
            f"Phase 3 dependency digest mismatch: {repository_path}"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Phase3DependencyError(
            f"Phase 3 dependency JSON is invalid: {repository_path}"
        ) from exc
    if not isinstance(payload, dict) or canonical_json_bytes(payload) != raw:
        raise Phase3DependencyError(
            f"Phase 3 dependency is not canonical JSON: {repository_path}"
        )
    return payload, _artifact_identity_from_bytes(repository_path, kind, raw)


class VerifiedPhase3Dataset(FrozenReadinessModel):
    schema_version: Literal["PHASE4-VERIFIED-PHASE3-DATASET-v1"] = (
        "PHASE4-VERIFIED-PHASE3-DATASET-v1"
    )
    symbol: str
    phase3_dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase3_dataset_path: str
    parquet_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata_artifact: ReadinessArtifactIdentity
    bars_artifact: ReadinessArtifactIdentity
    sessions: tuple[date, ...] = Field(min_length=1)
    sessions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_dataset(self) -> "VerifiedPhase3Dataset":
        symbol = assert_symbol_allowed(self.symbol)
        expected = next(
            (item for item in PHASE3_DATASETS if item.symbol == symbol), None
        )
        if expected is None or (
            self.phase3_dataset_sha256,
            self.phase3_dataset_path,
        ) != (expected.sha256, expected.path):
            raise ValueError("verified dataset does not match frozen identity")
        if self.metadata_artifact.kind != "phase3_normalized_dataset" or (
            self.metadata_artifact.path,
            self.metadata_artifact.content_sha256,
        ) != (f"{expected.path}/metadata.json", expected.sha256):
            raise ValueError("normalized metadata byte identity mismatch")
        if self.bars_artifact.kind != "phase3_normalized_dataset" or (
            self.bars_artifact.path != f"{expected.path}/bars.parquet"
        ):
            raise ValueError("normalized Parquet byte identity mismatch")
        if (
            len(set(self.sessions)) != len(self.sessions)
            or tuple(sorted(self.sessions)) != self.sessions
        ):
            raise ValueError("dataset sessions must be unique and increasing")
        if self.sessions_sha256 != _sessions_sha256(self.sessions):
            raise ValueError("dataset session digest mismatch")
        return self


class VerifiedPhase3Inputs(FrozenReadinessModel):
    schema_version: Literal["PHASE4-VERIFIED-PHASE3-INPUTS-v1"] = (
        "PHASE4-VERIFIED-PHASE3-INPUTS-v1"
    )
    universe_artifact: ReadinessArtifactIdentity
    dq_snapshot_artifact: ReadinessArtifactIdentity
    phase3_universe_digest: Literal[
        "de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76"
    ] = PHASE3_UNIVERSE_SHA256
    phase3_dq_snapshot_digest: Literal[
        "2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75"
    ] = PHASE3_DQ_SNAPSHOT_SHA256
    symbols: tuple[str, ...] = Field(min_length=8, max_length=8)
    datasets: tuple[VerifiedPhase3Dataset, ...] = Field(
        min_length=8, max_length=8
    )
    signal_series: Literal["QFQ"] = "QFQ"
    decision_grade: Literal[False] = False
    provider_calls: Literal[0] = 0
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()

    @model_validator(mode="after")
    def validate_inputs(self) -> "VerifiedPhase3Inputs":
        if self.symbols != PHASE3_SYMBOLS:
            raise ValueError("selected symbol order differs from frozen universe")
        if tuple(item.symbol for item in self.datasets) != self.symbols:
            raise ValueError("dataset dependencies differ from selected symbols")
        if (
            self.universe_artifact.kind != "phase3_universe_manifest"
            or self.universe_artifact.path != PHASE3_UNIVERSE_PATH
            or self.universe_artifact.content_sha256 != PHASE3_UNIVERSE_SHA256
        ):
            raise ValueError("universe artifact identity mismatch")
        if (
            self.dq_snapshot_artifact.kind != "phase3_dq_snapshot"
            or self.dq_snapshot_artifact.path != PHASE3_DQ_SNAPSHOT_PATH
            or self.dq_snapshot_artifact.content_sha256
            != PHASE3_DQ_SNAPSHOT_SHA256
        ):
            raise ValueError("DQ snapshot artifact identity mismatch")
        return self


class SplitPartition(FrozenReadinessModel):
    stage: Literal["TRAIN", "VALIDATION"]
    declared_start: date
    declared_end: date
    actual_start: date
    actual_end: date
    row_count: int = Field(gt=0)
    sessions: tuple[date, ...] = Field(min_length=1)
    sessions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_partition(self) -> "SplitPartition":
        expected = {
            "TRAIN": (
                PHASE4_TRAIN_START,
                PHASE4_TRAIN_END,
                PHASE4_TRAIN_START,
                PHASE4_TRAIN_END,
                PHASE4_TRAIN_ROW_COUNT,
            ),
            "VALIDATION": (
                PHASE4_VALIDATION_START,
                PHASE4_VALIDATION_END,
                date(2019, 1, 2),
                PHASE4_VALIDATION_END,
                PHASE4_VALIDATION_ROW_COUNT,
            ),
        }[self.stage]
        actual = (
            self.declared_start,
            self.declared_end,
            self.actual_start,
            self.actual_end,
            self.row_count,
        )
        if actual != expected:
            raise ValueError(f"{self.stage} partition boundary or count mismatch")
        if (
            len(self.sessions) != self.row_count
            or len(set(self.sessions)) != len(self.sessions)
            or tuple(sorted(self.sessions)) != self.sessions
            or self.sessions[0] != self.actual_start
            or self.sessions[-1] != self.actual_end
            or any(
                session < self.declared_start or session > self.declared_end
                for session in self.sessions
            )
        ):
            raise ValueError(f"{self.stage} partition sessions are invalid")
        if self.sessions_sha256 != _sessions_sha256(self.sessions):
            raise ValueError(f"{self.stage} partition session digest mismatch")
        return self


class DatasetPartition(FrozenReadinessModel):
    symbol: str
    phase3_dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata_artifact: ReadinessArtifactIdentity
    bars_artifact: ReadinessArtifactIdentity
    sessions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    train: SplitPartition
    validation: SplitPartition

    @model_validator(mode="after")
    def validate_partition(self) -> "DatasetPartition":
        symbol = assert_symbol_allowed(self.symbol)
        expected = next(
            (item for item in PHASE3_DATASETS if item.symbol == symbol), None
        )
        if expected is None or self.phase3_dataset_sha256 != expected.sha256:
            raise ValueError("partition dataset identity mismatch")
        if self.train.stage != "TRAIN" or self.validation.stage != "VALIDATION":
            raise ValueError("dataset partitions have invalid stages")
        if set(self.train.sessions).intersection(self.validation.sessions):
            raise ValueError("TRAIN and VALIDATION sessions must be disjoint")
        joined = (*self.train.sessions, *self.validation.sessions)
        if self.sessions_sha256 != _sessions_sha256(joined):
            raise ValueError("complete dataset session digest mismatch")
        return self


class Phase4SplitManifest(FrozenReadinessModel):
    schema_version: Literal["PHASE4-SPLIT-MANIFEST-v1"] = (
        "PHASE4-SPLIT-MANIFEST-v1"
    )
    split_policy_version: Literal["PHASE4-TEMPORAL-SPLIT-v1"] = (
        PHASE4_SPLIT_POLICY_VERSION
    )
    phase3_universe_artifact: ReadinessArtifactIdentity
    phase3_universe_digest: Literal[
        "de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76"
    ] = PHASE3_UNIVERSE_SHA256
    phase3_dq_snapshot_artifact: ReadinessArtifactIdentity
    phase3_dq_snapshot_digest: Literal[
        "2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75"
    ] = PHASE3_DQ_SNAPSHOT_SHA256
    symbols: tuple[str, ...] = Field(min_length=8, max_length=8)
    partitions: tuple[DatasetPartition, ...] = Field(min_length=8, max_length=8)
    provider_calls: Literal[0] = 0
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()

    @model_validator(mode="after")
    def validate_manifest(self) -> "Phase4SplitManifest":
        if self.symbols != PHASE3_SYMBOLS:
            raise ValueError("split symbol order differs from frozen universe")
        if tuple(item.symbol for item in self.partitions) != self.symbols:
            raise ValueError("split partitions differ from selected symbols")
        return self


class Phase4CampaignConfiguration(FrozenReadinessModel):
    schema_version: Literal["PHASE4-CAMPAIGN-CONFIG-v1"] = (
        "PHASE4-CAMPAIGN-CONFIG-v1"
    )
    phase3_universe_digest: Literal[
        "de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76"
    ] = PHASE3_UNIVERSE_SHA256
    split_manifest: ReadinessArtifactIdentity
    historical_phase2_trial_count: Literal[136] = 136
    phase4_new_trials_consumed: Literal[0] = 0
    phase4_new_trials_remaining: Literal[3000] = 3000
    phase4_historical_trials_consume_budget: Literal[False] = False
    maximum_new_strategy_families: Literal[10] = 10
    maximum_candidate_trials_per_family: Literal[500] = 500
    maximum_aggregate_new_candidate_trials: Literal[3000] = 3000
    signal_series: Literal["QFQ"] = "QFQ"
    execution_series: Literal["QFQ_NORMALIZED"] = "QFQ_NORMALIZED"
    decision_grade: Literal[False] = False
    provider_calls: Literal[0] = 0
    external_strategy_research_performed: Literal[False] = False
    strategy_search_executed: Literal[False] = False
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()
    live_trading_capability: Literal[False] = False

    @model_validator(mode="after")
    def validate_configuration(self) -> "Phase4CampaignConfiguration":
        if self.split_manifest.kind != "phase4_split_manifest":
            raise ValueError("configuration requires a written split manifest")
        expected_path = (
            "results/phase4/readiness/phase4_split_manifest/sha256/"
            f"{self.split_manifest.content_sha256}/manifest.json"
        )
        if self.split_manifest.path != expected_path:
            raise ValueError("split manifest identity is not a written artifact")
        if (
            self.phase4_new_trials_consumed != 0
            or self.phase4_new_trials_remaining
            != self.maximum_aggregate_new_candidate_trials
            or self.phase4_historical_trials_consume_budget is not False
        ):
            raise ValueError("Phase 4 budget must start at independent zero")
        return self


def _validate_universe_dependencies(
    universe: UniverseManifest,
    snapshot: DQSnapshot,
) -> None:
    expected_dq_path = _phase3_identity_path(PHASE3_DQ_SNAPSHOT_PATH)
    if (
        universe.dq_snapshot.sha256 != PHASE3_DQ_SNAPSHOT_SHA256
        or universe.dq_snapshot.path != expected_dq_path
        or universe.selected_symbols != PHASE3_SYMBOLS
        or universe.campaign_id != snapshot.campaign_id
        or universe.candidate_pool != snapshot.candidate_pool
        or universe.bars_repaired != 0
        or universe.decision_grade is not False
        or universe.strategy_performance_used is not False
        or universe.strategy_backtests_executed != 0
        or universe.final_holdout_accessed is not False
        or universe.protected_symbols_accessed != ()
        or universe.live_trading_capability is not False
    ):
        raise Phase3DependencyError("Phase 3 universe dependency mismatch")

    universe_candidates = {item.symbol: item for item in universe.candidates}
    snapshot_candidates = {item.symbol: item for item in snapshot.candidates}
    for expected in PHASE3_DATASETS:
        assert_symbol_allowed(expected.symbol)
        expected_phase3_path = _phase3_identity_path(expected.path)
        for candidate in (
            universe_candidates.get(expected.symbol),
            snapshot_candidates.get(expected.symbol),
        ):
            if (
                candidate is None
                or candidate.status != "PASS"
                or candidate.normalized_dataset is None
                or candidate.normalized_dataset.kind != "normalized_dataset"
                or candidate.normalized_dataset.sha256 != expected.sha256
                or candidate.normalized_dataset.path != expected_phase3_path
                or candidate.provider_request.adjustment != "QFQ"
            ):
                raise Phase3DependencyError(
                    f"Phase 3 selected dataset mismatch: {expected.symbol}"
                )


def _verify_dataset(
    repository_root: Path,
    expected: PinnedPhase3Dataset,
) -> tuple[VerifiedPhase3Dataset, pd.DatetimeIndex]:
    symbol = assert_symbol_allowed(expected.symbol)
    metadata_path = f"{expected.path}/metadata.json"
    payload, metadata_artifact = _exact_json(
        repository_root,
        metadata_path,
        expected.sha256,
        "phase3_normalized_dataset",
    )
    if set(payload) != {"content_sha256", "metadata"}:
        raise Phase3DependencyError(f"normalized metadata invalid: {symbol}")
    try:
        metadata = NormalizedDatasetMetadata.model_validate(payload["metadata"])
    except (TypeError, ValueError, ValidationError) as exc:
        raise Phase3DependencyError(
            f"normalized metadata model invalid: {symbol}"
        ) from exc
    if metadata.symbol != symbol or metadata.provider_request.adjustment != "QFQ":
        raise Phase3DependencyError(f"normalized metadata symbol mismatch: {symbol}")

    bars_path = f"{expected.path}/bars.parquet"
    _, bars_bytes = _exact_file(repository_root, bars_path)
    bars_artifact = _artifact_identity_from_bytes(
        bars_path, "phase3_normalized_dataset", bars_bytes
    )
    try:
        frame = pd.read_parquet(BytesIO(bars_bytes), engine="pyarrow")
    except Exception as exc:
        raise Phase3DependencyError(f"normalized Parquet invalid: {symbol}") from exc
    if (
        not isinstance(frame.index, pd.DatetimeIndex)
        or frame.index.tz is None
        or frame.index.has_duplicates
        or not frame.index.is_monotonic_increasing
    ):
        raise Phase3DependencyError(f"normalized sessions invalid: {symbol}")
    actual_content_hash = content_hash(frame)
    if payload["content_sha256"] != actual_content_hash:
        raise Phase3DependencyError(f"normalized content hash mismatch: {symbol}")
    if (
        metadata.row_count != len(frame)
        or pd.Timestamp(metadata.first_timestamp) != frame.index[0]
        or pd.Timestamp(metadata.last_timestamp) != frame.index[-1]
    ):
        raise Phase3DependencyError(f"normalized bounds mismatch: {symbol}")
    sessions = tuple(timestamp.date() for timestamp in frame.index)
    if len(set(sessions)) != len(sessions):
        raise Phase3DependencyError(f"normalized session dates duplicate: {symbol}")
    return (
        VerifiedPhase3Dataset(
            symbol=symbol,
            phase3_dataset_sha256=expected.sha256,
            phase3_dataset_path=expected.path,
            parquet_content_hash=actual_content_hash,
            metadata_artifact=metadata_artifact,
            bars_artifact=bars_artifact,
            sessions=sessions,
            sessions_sha256=_sessions_sha256(sessions),
        ),
        frame.index.copy(),
    )


def verify_phase3_dependencies(repository_root: Path) -> VerifiedPhase3Inputs:
    try:
        universe_payload, universe_artifact = _exact_json(
            repository_root,
            PHASE3_UNIVERSE_PATH,
            PHASE3_UNIVERSE_SHA256,
            "phase3_universe_manifest",
        )
        dq_payload, dq_artifact = _exact_json(
            repository_root,
            PHASE3_DQ_SNAPSHOT_PATH,
            PHASE3_DQ_SNAPSHOT_SHA256,
            "phase3_dq_snapshot",
        )
        universe = UniverseManifest.model_validate(universe_payload)
        snapshot = DQSnapshot.model_validate(dq_payload)
        _validate_universe_dependencies(universe, snapshot)

        datasets = []
        reference_index: pd.DatetimeIndex | None = None
        for expected in PHASE3_DATASETS:
            dataset, index = _verify_dataset(repository_root, expected)
            if reference_index is None:
                reference_index = index
            elif not index.equals(reference_index):
                raise Phase3DependencyError(
                    f"normalized session index mismatch: {expected.symbol}"
                )
            datasets.append(dataset)
        return VerifiedPhase3Inputs(
            universe_artifact=universe_artifact,
            dq_snapshot_artifact=dq_artifact,
            symbols=PHASE3_SYMBOLS,
            datasets=tuple(datasets),
        )
    except Phase3DependencyError:
        raise
    except Exception as exc:
        raise Phase3DependencyError("Phase 3 dependency verification failed") from exc


def _revalidate_inputs(inputs: VerifiedPhase3Inputs) -> VerifiedPhase3Inputs:
    try:
        return VerifiedPhase3Inputs.model_validate(inputs.model_dump())
    except (AttributeError, TypeError, ValueError, ValidationError) as exc:
        raise Phase3DependencyError("verified Phase 3 inputs are invalid") from exc


def build_split_manifest(inputs: VerifiedPhase3Inputs) -> Phase4SplitManifest:
    verified = _revalidate_inputs(inputs)
    partitions = []
    for dataset in verified.datasets:
        train_sessions = tuple(
            session
            for session in dataset.sessions
            if PHASE4_TRAIN_START <= session <= PHASE4_TRAIN_END
        )
        validation_sessions = tuple(
            session
            for session in dataset.sessions
            if PHASE4_VALIDATION_START <= session <= PHASE4_VALIDATION_END
        )
        if (*train_sessions, *validation_sessions) != dataset.sessions:
            raise Phase3DependencyError("dataset contains out-of-split sessions")
        try:
            partitions.append(
                DatasetPartition(
                    symbol=dataset.symbol,
                    phase3_dataset_sha256=dataset.phase3_dataset_sha256,
                    metadata_artifact=dataset.metadata_artifact,
                    bars_artifact=dataset.bars_artifact,
                    sessions_sha256=dataset.sessions_sha256,
                    train=SplitPartition(
                        stage="TRAIN",
                        declared_start=PHASE4_TRAIN_START,
                        declared_end=PHASE4_TRAIN_END,
                        actual_start=train_sessions[0],
                        actual_end=train_sessions[-1],
                        row_count=len(train_sessions),
                        sessions=train_sessions,
                        sessions_sha256=_sessions_sha256(train_sessions),
                    ),
                    validation=SplitPartition(
                        stage="VALIDATION",
                        declared_start=PHASE4_VALIDATION_START,
                        declared_end=PHASE4_VALIDATION_END,
                        actual_start=validation_sessions[0],
                        actual_end=validation_sessions[-1],
                        row_count=len(validation_sessions),
                        sessions=validation_sessions,
                        sessions_sha256=_sessions_sha256(validation_sessions),
                    ),
                )
            )
        except (IndexError, TypeError, ValueError, ValidationError) as exc:
            raise Phase3DependencyError(
                f"split partition invalid: {dataset.symbol}"
            ) from exc
    try:
        return Phase4SplitManifest(
            phase3_universe_artifact=verified.universe_artifact,
            phase3_dq_snapshot_artifact=verified.dq_snapshot_artifact,
            symbols=verified.symbols,
            partitions=tuple(partitions),
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise Phase3DependencyError("Phase 4 split manifest is invalid") from exc


def build_campaign_configuration(
    split: ReadinessArtifactIdentity,
) -> Phase4CampaignConfiguration:
    try:
        verified_split = ReadinessArtifactIdentity.model_validate(split.model_dump())
        return Phase4CampaignConfiguration(split_manifest=verified_split)
    except (AttributeError, TypeError, ValueError, ValidationError) as exc:
        raise Phase3DependencyError(
            "Phase 4 campaign configuration requires a valid written split"
        ) from exc
