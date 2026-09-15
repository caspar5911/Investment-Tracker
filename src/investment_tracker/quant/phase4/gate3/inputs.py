from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Mapping

import pyarrow.parquet as pq

from investment_tracker.quant.phase4.engine.authority import load_gate2_authority
from investment_tracker.quant.phase4.engine.models import Phase4EngineManifest
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
    canonical_sha256,
)
from investment_tracker.quant.phase4.preregistration.seal import Phase4PreregistrationManifest

from .authorities import SYMBOLS
from .filesystem import contained_path, resolve_repository_root
from .models import ArtifactIdentity, DataPartitionIdentity, Gate3AuthorityError


@dataclass(frozen=True)
class FrozenAuthorityInputs:
    gate1: ArtifactIdentity
    gate2: ArtifactIdentity
    universe: ArtifactIdentity
    split: ArtifactIdentity
    train_identity: DataPartitionIdentity
    validation_identity: DataPartitionIdentity
    all_sessions: tuple[str, ...]
    validation_sessions: tuple[str, ...]
    close_by_symbol: Mapping[str, tuple[float, ...]]


def _safe_path(root: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if relative.startswith("/") or "\\" in relative or any(part in {"", ".", ".."} for part in posix.parts):
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: invalid repository path")
    return contained_path(
        root, tuple(posix.parts), code="INPUT_IDENTITY_MISMATCH"
    )


def _read_identity(root: Path, identity: ArtifactIdentity) -> bytes:
    path = _safe_path(root, identity.path)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: pinned input missing") from exc
    if sha256(payload).hexdigest() != identity.content_sha256:
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: pinned content changed")
    if identity.sha256 != artifact_envelope_identity(
        content_sha256=identity.content_sha256, kind=identity.kind, path=identity.path
    ):
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: pinned envelope changed")
    return payload


def _canonical_object(payload: bytes, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate3AuthorityError(f"INPUT_IDENTITY_MISMATCH: {label} is invalid JSON") from exc
    if not isinstance(parsed, dict) or canonical_json_bytes(parsed) != payload:
        raise Gate3AuthorityError(f"INPUT_IDENTITY_MISMATCH: {label} is not canonical")
    return parsed


def _partition_identity(
    stage: str,
    partition: dict[str, object],
    symbols: tuple[str, ...],
    partitions: list[dict[str, object]],
) -> DataPartitionIdentity:
    sample = partition[stage.lower()]
    assert isinstance(sample, dict)
    dataset_pairs = tuple(
        (symbol, str(item["bars_artifact"]["content_sha256"]))
        for symbol, item in zip(symbols, partitions, strict=True)
    )
    semantic = {
        "stage": stage,
        "actual_start": sample["actual_start"],
        "actual_end": sample["actual_end"],
        "row_count": sample["row_count"],
        "sessions_sha256": sample["sessions_sha256"],
        "dataset_content_sha256_by_symbol": dataset_pairs,
    }
    return DataPartitionIdentity(**semantic, sha256=canonical_sha256(semantic))


def load_frozen_authority_inputs(
    repository_root: Path,
    *,
    gate1_identity: ArtifactIdentity,
    gate2_identity: ArtifactIdentity,
) -> FrozenAuthorityInputs:
    root = resolve_repository_root(
        repository_root, code="INPUT_IDENTITY_MISMATCH"
    )
    gate1_payload = _read_identity(root, gate1_identity)
    gate2_payload = _read_identity(root, gate2_identity)
    try:
        gate1_model = Phase4PreregistrationManifest.model_validate_json(gate1_payload)
        gate2_model = Phase4EngineManifest.model_validate_json(gate2_payload)
    except ValueError as exc:
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: sealed manifest invalid") from exc
    if (
        gate1_model.status != "PHASE4_PREREGISTRATION_SEALED"
        or gate2_model.status != "PHASE4_ENGINE_SEALED"
        or gate2_model.gate1_manifest.model_dump() != gate1_identity.model_dump()
        or gate2_model.candidate_count != 180
        or gate2_model.phase4_trials_consumed != 0
        or gate2_model.safety.model_dump() != gate2_model.safety.__class__().model_dump()
    ):
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: Gate 1/Gate 2 invariants failed")
    try:
        verified_gate1 = load_gate2_authority(root)
    except Exception as exc:
        raise Gate3AuthorityError(
            "INPUT_IDENTITY_MISMATCH: Gate 1 dependency verification failed"
        ) from exc
    if (
        verified_gate1.manifest_identity.model_dump() != gate1_identity.model_dump()
        or sum(len(family.candidates) for family in verified_gate1.grids.families) != 180
        or verified_gate1.phase4_trials_consumed != 0
    ):
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: Gate 1 population mismatch")
    for dependency in gate2_model.write_ledger:
        _read_identity(root, ArtifactIdentity(**dependency.model_dump()))

    split_ref = gate1_model.split_manifest
    split_identity = ArtifactIdentity(**split_ref.model_dump())
    split_payload = _read_identity(root, split_identity)
    split = _canonical_object(split_payload, "split manifest")
    symbols = tuple(split.get("symbols", ()))
    if symbols != SYMBOLS or split.get("provider_calls") != 0 or split.get("final_holdout_accessed") is not False or split.get("protected_symbols_accessed") != []:
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: split safety or universe mismatch")
    partitions = split.get("partitions")
    if not isinstance(partitions, list) or len(partitions) != 8:
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: split partitions mismatch")
    universe_identity = ArtifactIdentity(**split["phase3_universe_artifact"])
    _read_identity(root, universe_identity)
    first = partitions[0]
    if not isinstance(first, dict):
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: invalid split partition")
    train_sessions = tuple(first["train"]["sessions"])
    validation_sessions = tuple(first["validation"]["sessions"])
    if len(train_sessions) != 1258 or len(validation_sessions) != 1008:
        raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: session counts mismatch")
    all_sessions = train_sessions + validation_sessions

    close_by_symbol: dict[str, tuple[float, ...]] = {}
    for expected_symbol, partition in zip(SYMBOLS, partitions, strict=True):
        if not isinstance(partition, dict) or partition.get("symbol") != expected_symbol:
            raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: partition order mismatch")
        if tuple(partition["train"]["sessions"]) != train_sessions or tuple(partition["validation"]["sessions"]) != validation_sessions:
            raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: partition calendars differ")
        bars_identity = ArtifactIdentity(**partition["bars_artifact"])
        _read_identity(root, bars_identity)
        bars_path = _safe_path(root, bars_identity.path)
        table = pq.read_table(bars_path, columns=["timestamp", "close"])
        observed_sessions = tuple(
            item.strftime("%Y-%m-%d") for item in table.column("timestamp").to_pylist()
        )
        if observed_sessions != all_sessions:
            raise Gate3AuthorityError("INPUT_IDENTITY_MISMATCH: parquet calendar differs")
        close_by_symbol[expected_symbol] = tuple(
            float(item) for item in table.column("close").to_pylist()
        )

    train_identity = _partition_identity("TRAIN", first, SYMBOLS, partitions)
    validation_identity = _partition_identity("VALIDATION", first, SYMBOLS, partitions)
    return FrozenAuthorityInputs(
        gate1=gate1_identity,
        gate2=gate2_identity,
        universe=universe_identity,
        split=split_identity,
        train_identity=train_identity,
        validation_identity=validation_identity,
        all_sessions=all_sessions,
        validation_sessions=validation_sessions,
        close_by_symbol=close_by_symbol,
    )
