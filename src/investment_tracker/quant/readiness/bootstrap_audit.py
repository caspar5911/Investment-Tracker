from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import Field, ValidationError, model_validator

from investment_tracker.quant.backtest.benchmark import aggregate_equal_weight
from investment_tracker.quant.backtest.engine import run_backtest
from investment_tracker.quant.backtest.models import ExecutionAssumptions
from investment_tracker.quant.data.cache import content_hash
from investment_tracker.quant.data.models import DatasetMetadata
from investment_tracker.quant.data.validation import REQUIRED_COLUMNS
from investment_tracker.quant.experiments import ExperimentRecord
from investment_tracker.quant.strategies.registry import build_strategy
from investment_tracker.quant.validation.bootstrap import bootstrap_interval

from .constants import (
    PINNED_BOOTSTRAP_DATASETS,
    PINNED_BOOTSTRAP_SOURCE_ARTIFACT_SHA256,
    PINNED_BOOTSTRAP_SOURCE_CONTENT_SHA256,
    PINNED_BOOTSTRAP_SOURCE_PATH,
    PINNED_BOOTSTRAP_VECTOR_SHA256,
    PINNED_CANDIDATE_MANIFEST_SHA256,
)
from .hashing import ArtifactIdentityError, canonical_sha256, normalize_repository_path
from .models import FrozenReadinessModel, ReadinessArtifactIdentity


PINNED_CANDIDATE_ID = "risk_managed_trend-ee8a71fb71e3d80f"
PINNED_STRATEGY_FAMILY = "risk_managed_trend"
PINNED_STRATEGY_PARAMETERS = {
    "maximum_exposure": 0.5,
    "target_volatility": 0.08,
    "trend_window": 150,
    "volatility_window": 40,
}
PINNED_SPLIT_DEFINITION_SHA256 = (
    "f958a1d548bedb76144ebd7b5725db814c78b425b5368870cd50c4589799fd08"
)
PINNED_ENGINE_VERSION = "QUANT-ENGINE-v1+SEARCH-POLICY-v2"
PINNED_EXECUTION_CONVENTION = "COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN"
PINNED_INITIAL_CAPITAL = 100_000.0
PINNED_COMMISSION_BPS = 1.0
PINNED_SLIPPAGE_BPS = 2.0
PINNED_ALLOW_FRACTIONAL = True
PINNED_TRAIN_PERIOD = (date(2010, 1, 1), date(2018, 12, 31))
PINNED_VALIDATION_PERIOD = (date(2019, 1, 1), date(2022, 12, 31))
PINNED_RETURN_COUNT = 1007
PINNED_SIGN_COUNTS = (288, 368, 351)


class BootstrapEvidenceError(RuntimeError):
    """Raised when pinned bootstrap evidence is absent or inconsistent."""


class PinnedBootstrapSource(FrozenReadinessModel):
    artifact: ReadinessArtifactIdentity
    record: ExperimentRecord


class BootstrapDatasetIdentity(FrozenReadinessModel):
    symbol: str = Field(min_length=1)
    path: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: int = Field(gt=0)
    first_timestamp: datetime
    last_timestamp: datetime


def _dataset_provenance(
    datasets: tuple[BootstrapDatasetIdentity, ...],
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (item.symbol, item.path, item.content_hash)
        for item in datasets
    )


def _frozen_dataset_provenance() -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (item.symbol, item.path, item.content_hash)
            for item in PINNED_BOOTSTRAP_DATASETS
        )
    )


class BootstrapInputVector(FrozenReadinessModel):
    schema_version: Literal["BOOTSTRAP-INPUT-VECTOR-v1"] = (
        "BOOTSTRAP-INPUT-VECTOR-v1"
    )
    dtype: Literal["IEEE-754-binary64"] = "IEEE-754-binary64"
    values_hex: tuple[str, ...] = Field(
        min_length=PINNED_RETURN_COUNT,
        max_length=PINNED_RETURN_COUNT,
    )
    negative_count: Literal[288]
    zero_count: Literal[368]
    positive_count: Literal[351]
    source_artifact: ReadinessArtifactIdentity
    datasets: tuple[BootstrapDatasetIdentity, ...] = Field(min_length=3, max_length=3)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_vector(self) -> "BootstrapInputVector":
        try:
            values = tuple(float.fromhex(value) for value in self.values_hex)
        except (TypeError, ValueError) as exc:
            raise ValueError("bootstrap vector contains an invalid hexadecimal float") from exc
        if any(not math.isfinite(value) for value in values):
            raise ValueError("bootstrap vector values must be finite")
        if any(value.hex() != encoded for value, encoded in zip(values, self.values_hex)):
            raise ValueError("bootstrap vector values must use canonical float.hex")
        counts = (
            sum(value < 0.0 for value in values),
            sum(value == 0.0 for value in values),
            sum(value > 0.0 for value in values),
        )
        if counts != (
            self.negative_count,
            self.zero_count,
            self.positive_count,
        ):
            raise ValueError("bootstrap vector sign counts do not match values")
        payload = {
            "dtype": self.dtype,
            "schema_version": self.schema_version,
            "values_hex": list(self.values_hex),
        }
        if canonical_sha256(payload) != self.sha256:
            raise ValueError("bootstrap vector digest does not match values")
        if tuple(item.symbol for item in self.datasets) != ("IEF", "QQQ", "TLT"):
            raise ValueError("bootstrap dataset identities must be symbol sorted")
        if _dataset_provenance(self.datasets) != _frozen_dataset_provenance():
            raise ValueError("bootstrap dataset provenance is not pinned")
        return self


class BootstrapAudit(FrozenReadinessModel):
    schema_version: Literal["BOOTSTRAP-AUDIT-v1"] = "BOOTSTRAP-AUDIT-v1"
    statistic: Literal["median_daily_equal_weight_portfolio_return"] = (
        "median_daily_equal_weight_portfolio_return"
    )
    sample_size: Literal[1007] = PINNED_RETURN_COUNT
    observed_median: Literal[0.0] = 0.0
    draws: Literal[2000] = 2000
    seed: Literal[0] = 0
    lower_percentile: Literal[5.0] = 5.0
    upper_percentile: Literal[95.0] = 95.0
    zero_resampled_medians: Literal[2000] = 2000
    interval: tuple[Literal[0.0], Literal[0.0]] = (0.0, 0.0)
    source_artifact: ReadinessArtifactIdentity
    vector_sha256: Literal[
        "878b8400fcf93776feda23c454182d36dca5efd4c32f51d2aa232abf003bf0b5"
    ] = PINNED_BOOTSTRAP_VECTOR_SHA256
    claim_scope: Literal["MEDIAN_DAILY_EQUAL_WEIGHT_PORTFOLIO_RETURN_ONLY"] = (
        "MEDIAN_DAILY_EQUAL_WEIGHT_PORTFOLIO_RETURN_ONLY"
    )
    decision_grade: Literal[False] = False


def _read_regular_file(
    repository_root: Path,
    relative_path: str,
    evidence_name: str,
) -> tuple[Path, bytes]:
    try:
        normalized = normalize_repository_path(repository_root, Path(relative_path))
    except ArtifactIdentityError as exc:
        raise BootstrapEvidenceError(f"pinned {evidence_name} path is unsafe") from exc
    if normalized != relative_path:
        raise BootstrapEvidenceError(f"pinned {evidence_name} path changed")
    path = Path(repository_root).resolve(strict=True) / Path(relative_path)
    if not path.is_file() or path.is_symlink():
        raise BootstrapEvidenceError(f"pinned {evidence_name} is not a regular file")
    try:
        return path, path.read_bytes()
    except OSError as exc:
        raise BootstrapEvidenceError(f"pinned {evidence_name} is unreadable") from exc


def _validate_pinned_source(source: PinnedBootstrapSource) -> ExperimentRecord:
    if (
        source.artifact.path != PINNED_BOOTSTRAP_SOURCE_PATH
        or source.artifact.kind != "phase2_experiment"
        or source.artifact.content_sha256
        != PINNED_BOOTSTRAP_SOURCE_CONTENT_SHA256
        or source.artifact.sha256 != PINNED_BOOTSTRAP_SOURCE_ARTIFACT_SHA256
    ):
        raise BootstrapEvidenceError("pinned source identity mismatch")
    try:
        record = ExperimentRecord.model_validate(source.record.model_dump(mode="json"))
    except ValidationError as exc:
        raise BootstrapEvidenceError("pinned candidate manifest is invalid") from exc
    manifest = record.candidate_manifest
    expected_data_hashes = {
        item.symbol: item.content_hash for item in PINNED_BOOTSTRAP_DATASETS
    }
    if (
        manifest.digest != PINNED_CANDIDATE_MANIFEST_SHA256
        or manifest.candidate_id != PINNED_CANDIDATE_ID
        or manifest.strategy_family != PINNED_STRATEGY_FAMILY
        or manifest.strategy_parameters != PINNED_STRATEGY_PARAMETERS
        or manifest.data_manifest_hashes != expected_data_hashes
        or manifest.split_definition_hash != PINNED_SPLIT_DEFINITION_SHA256
        or manifest.engine_version != PINNED_ENGINE_VERSION
        or manifest.fee_model
        != {"name": "notional_bps", "commission_bps": PINNED_COMMISSION_BPS}
        or manifest.slippage_model
        != {"name": "adverse_bps", "slippage_bps": PINNED_SLIPPAGE_BPS}
        or manifest.execution_convention != PINNED_EXECUTION_CONVENTION
        or record.symbols != ("IEF", "QQQ", "TLT")
        or record.train_period != PINNED_TRAIN_PERIOD
        or record.validation_period != PINNED_VALIDATION_PERIOD
        or record.validation_metrics.get("bootstrap_median_lower") != 0.0
        or record.validation_metrics.get("bootstrap_median_upper") != 0.0
    ):
        raise BootstrapEvidenceError("pinned candidate manifest evidence mismatch")
    return record


def load_pinned_bootstrap_source(repository_root: Path) -> PinnedBootstrapSource:
    _, payload = _read_regular_file(
        repository_root,
        PINNED_BOOTSTRAP_SOURCE_PATH,
        "source",
    )
    content_digest = sha256(payload).hexdigest()
    envelope = {
        "content_sha256": content_digest,
        "kind": "phase2_experiment",
        "path": PINNED_BOOTSTRAP_SOURCE_PATH,
    }
    if (
        content_digest != PINNED_BOOTSTRAP_SOURCE_CONTENT_SHA256
        or canonical_sha256(envelope) != PINNED_BOOTSTRAP_SOURCE_ARTIFACT_SHA256
    ):
        raise BootstrapEvidenceError("pinned source exact-byte identity mismatch")
    try:
        record = ExperimentRecord.model_validate_json(payload)
        source = PinnedBootstrapSource(
            artifact=ReadinessArtifactIdentity(
                **envelope,
                sha256=PINNED_BOOTSTRAP_SOURCE_ARTIFACT_SHA256,
            ),
            record=record,
        )
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise BootstrapEvidenceError("pinned source is invalid") from exc
    _validate_pinned_source(source)
    return source


def _load_pinned_dataset(
    repository_root: Path,
    source: PinnedBootstrapSource,
    symbol: str,
    relative_path: str,
    expected_content_hash: str,
) -> tuple[BootstrapDatasetIdentity, pd.DataFrame]:
    try:
        normalized = normalize_repository_path(repository_root, Path(relative_path))
    except ArtifactIdentityError as exc:
        raise BootstrapEvidenceError(f"pinned dataset path is unsafe: {symbol}") from exc
    dataset_path = Path(repository_root).resolve(strict=True) / Path(relative_path)
    if (
        normalized != relative_path
        or not dataset_path.is_dir()
        or dataset_path.is_symlink()
    ):
        raise BootstrapEvidenceError(f"pinned dataset directory mismatch: {symbol}")
    _, metadata_payload = _read_regular_file(
        repository_root,
        f"{relative_path}/metadata.json",
        f"dataset metadata for {symbol}",
    )
    bars_path, _ = _read_regular_file(
        repository_root,
        f"{relative_path}/bars.parquet",
        f"dataset bars for {symbol}",
    )
    try:
        metadata = DatasetMetadata.model_validate_json(metadata_payload)
        frame = pd.read_parquet(bars_path, engine="pyarrow")
        computed_hash = content_hash(frame)
    except Exception as exc:
        raise BootstrapEvidenceError(f"pinned dataset is unreadable: {symbol}") from exc
    manifest_hash = source.record.candidate_manifest.data_manifest_hashes.get(symbol)
    actual_identity = (
        metadata.provider,
        metadata.symbol,
        metadata.interval,
        metadata.adjustment,
        metadata.requested_start,
        metadata.requested_end,
        metadata.row_count,
        metadata.content_hash,
    )
    expected_identity = (
        "MOOMOO",
        symbol,
        "1d",
        "QFQ",
        date(2010, 1, 1),
        date(2022, 12, 31),
        3272,
        expected_content_hash,
    )
    if (
        actual_identity != expected_identity
        or manifest_hash != expected_content_hash
        or computed_hash != expected_content_hash
        or len(frame) != metadata.row_count
        or tuple(frame.columns) != REQUIRED_COLUMNS
        or not isinstance(frame.index, pd.DatetimeIndex)
        or frame.index.has_duplicates
        or not frame.index.is_monotonic_increasing
        or frame.index[0].to_pydatetime() != metadata.first_timestamp
        or frame.index[-1].to_pydatetime() != metadata.last_timestamp
    ):
        raise BootstrapEvidenceError(f"pinned dataset identity mismatch: {symbol}")
    return (
        BootstrapDatasetIdentity(
            symbol=symbol,
            path=relative_path,
            content_hash=computed_hash,
            row_count=len(frame),
            first_timestamp=metadata.first_timestamp,
            last_timestamp=metadata.last_timestamp,
        ),
        frame,
    )


def reconstruct_bootstrap_vector(
    repository_root: Path,
    source: PinnedBootstrapSource,
) -> BootstrapInputVector:
    record = _validate_pinned_source(source)
    datasets: list[BootstrapDatasetIdentity] = []
    frames: dict[str, pd.DataFrame] = {}
    for expected in PINNED_BOOTSTRAP_DATASETS:
        identity, frame = _load_pinned_dataset(
            repository_root,
            source,
            expected.symbol,
            expected.path,
            expected.content_hash,
        )
        datasets.append(identity)
        dates = frame.index.date
        frames[expected.symbol] = frame.loc[
            (dates >= record.validation_period[0])
            & (dates <= record.validation_period[1])
        ]

    strategy = build_strategy(
        record.candidate_manifest.strategy_family,
        record.candidate_manifest.strategy_parameters,
    )
    assumptions = ExecutionAssumptions(
        initial_capital=PINNED_INITIAL_CAPITAL,
        commission_bps=PINNED_COMMISSION_BPS,
        slippage_bps=PINNED_SLIPPAGE_BPS,
        allow_fractional=PINNED_ALLOW_FRACTIONAL,
    )
    if assumptions.execution_convention != record.candidate_manifest.execution_convention:
        raise BootstrapEvidenceError("pinned execution convention mismatch")
    try:
        results = {
            symbol: run_backtest(frame, strategy.targets(frame), assumptions)
            for symbol, frame in frames.items()
        }
        equity = aggregate_equal_weight(
            {
                symbol: result.equity_curve
                for symbol, result in results.items()
            },
            assumptions.initial_capital,
        )
        values = tuple(
            float(value)
            for value in equity.pct_change(fill_method=None).dropna().tolist()
        )
    except Exception as exc:
        raise BootstrapEvidenceError("pinned bootstrap reconstruction failed") from exc
    if any(not math.isfinite(value) for value in values):
        raise BootstrapEvidenceError("pinned bootstrap vector contains non-finite values")
    values_hex = tuple(value.hex() for value in values)
    counts = (
        sum(value < 0.0 for value in values),
        sum(value == 0.0 for value in values),
        sum(value > 0.0 for value in values),
    )
    payload = {
        "dtype": "IEEE-754-binary64",
        "schema_version": "BOOTSTRAP-INPUT-VECTOR-v1",
        "values_hex": list(values_hex),
    }
    vector_digest = canonical_sha256(payload)
    if (
        len(values) != PINNED_RETURN_COUNT
        or counts != PINNED_SIGN_COUNTS
        or vector_digest != PINNED_BOOTSTRAP_VECTOR_SHA256
    ):
        raise BootstrapEvidenceError("pinned bootstrap vector identity mismatch")
    try:
        return BootstrapInputVector(
            values_hex=values_hex,
            negative_count=counts[0],
            zero_count=counts[1],
            positive_count=counts[2],
            source_artifact=source.artifact,
            datasets=tuple(sorted(datasets, key=lambda item: item.symbol)),
            sha256=vector_digest,
        )
    except ValidationError as exc:
        raise BootstrapEvidenceError("pinned bootstrap vector is invalid") from exc


def audit_bootstrap_vector(
    vector: BootstrapInputVector,
    source: PinnedBootstrapSource,
) -> BootstrapAudit:
    record = _validate_pinned_source(source)
    try:
        raw_vector = {
            field_name: getattr(vector, field_name)
            for field_name in BootstrapInputVector.model_fields
        }
        verified = BootstrapInputVector.model_validate(raw_vector)
    except (AttributeError, TypeError, ValidationError) as exc:
        raise BootstrapEvidenceError(
            "pinned bootstrap vector is invalid, including dataset provenance"
        ) from exc
    pinned_paths = {
        item.symbol: item.path for item in PINNED_BOOTSTRAP_DATASETS
    }
    source_provenance = tuple(
        sorted(
            (
                symbol,
                pinned_paths[symbol],
                content_digest,
            )
            for symbol, content_digest in (
                record.candidate_manifest.data_manifest_hashes.items()
            )
        )
    )
    if _dataset_provenance(verified.datasets) != source_provenance:
        raise BootstrapEvidenceError(
            "pinned bootstrap vector dataset provenance mismatch"
        )
    if (
        verified.sha256 != PINNED_BOOTSTRAP_VECTOR_SHA256
        or verified.source_artifact != source.artifact
    ):
        raise BootstrapEvidenceError("pinned bootstrap vector identity mismatch")
    values = tuple(float.fromhex(value) for value in verified.values_hex)
    interval = bootstrap_interval(
        values,
        draws=2000,
        seed=0,
        lower_percentile=5.0,
        upper_percentile=95.0,
    )
    rng = np.random.default_rng(0)
    samples = rng.choice(values, size=(2000, len(values)), replace=True)
    medians = np.median(samples, axis=1)
    zero_medians = int(np.count_nonzero(medians == 0.0))
    stored_interval = (
        record.validation_metrics.get("bootstrap_median_lower"),
        record.validation_metrics.get("bootstrap_median_upper"),
    )
    if (
        interval != stored_interval
        or interval != (0.0, 0.0)
        or float(np.median(values)) != 0.0
        or zero_medians != 2000
    ):
        raise BootstrapEvidenceError("pinned bootstrap audit does not reproduce")
    return BootstrapAudit(
        observed_median=0.0,
        zero_resampled_medians=zero_medians,
        interval=interval,
        source_artifact=source.artifact,
        vector_sha256=verified.sha256,
    )
