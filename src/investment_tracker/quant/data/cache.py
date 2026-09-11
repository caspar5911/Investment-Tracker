from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

import pandas as pd

from investment_tracker.governance import assert_symbol_allowed

from .models import DataRequest, DatasetMetadata
from .validation import DataQualityError, DataValidationReport, REQUIRED_COLUMNS


class CacheIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class CachedDataset:
    dataset_path: Path
    data_path: Path
    metadata_path: Path
    metadata: DatasetMetadata
    frame: pd.DataFrame


def content_hash(frame: pd.DataFrame) -> str:
    canonical = frame.loc[:, REQUIRED_COLUMNS].copy()
    canonical.index.name = "timestamp"
    payload = canonical.to_csv(
        index=True,
        date_format="%Y-%m-%dT%H:%M:%S.%f%z",
        float_format="%.17g",
        lineterminator="\n",
    ).encode("utf-8")
    return sha256(payload).hexdigest()


class ImmutableParquetCache:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def find(self, request: DataRequest) -> CachedDataset | None:
        symbol = assert_symbol_allowed(request.symbol)
        guarded = request.model_copy(update={"symbol": symbol})
        request_dir = self._request_dir(guarded)
        if not request_dir.exists():
            return None
        candidates: list[CachedDataset] = []
        for metadata_path in request_dir.glob("*/metadata.json"):
            candidates.append(self._read_dataset(metadata_path.parent, guarded))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.metadata.retrieved_at)

    def admit(
        self,
        request: DataRequest,
        frame: pd.DataFrame,
        report: DataValidationReport,
        provider_api_version: str | None,
        retrieved_at: datetime | None = None,
    ) -> CachedDataset:
        symbol = assert_symbol_allowed(request.symbol)
        guarded = request.model_copy(update={"symbol": symbol})
        moment = retrieved_at or datetime.now(timezone.utc)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        if not report.clean:
            self._record_quarantine(guarded, report, moment)
            raise DataQualityError(report)
        if frame.empty:
            raise ValueError("cannot admit an empty dataset")

        digest = content_hash(frame)
        existing = self._find_by_hash(guarded, digest)
        if existing is not None:
            return existing

        metadata = DatasetMetadata(
            provider=guarded.provider,
            provider_api_version=provider_api_version,
            symbol=guarded.symbol,
            interval=guarded.interval,
            adjustment=guarded.adjustment,
            requested_start=guarded.start,
            requested_end=guarded.end,
            retrieved_at=moment,
            first_timestamp=frame.index[0].to_pydatetime(),
            last_timestamp=frame.index[-1].to_pydatetime(),
            row_count=len(frame),
            content_hash=digest,
        )
        request_dir = self._request_dir(guarded)
        request_dir.mkdir(parents=True, exist_ok=True)
        stamp = moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        final_path = request_dir / f"{stamp}_{digest}"
        if final_path.exists():
            raise CacheIntegrityError(f"dataset version already exists: {final_path}")

        temp_path = Path(tempfile.mkdtemp(prefix=".tmp-", dir=request_dir))
        try:
            frame.to_parquet(temp_path / "bars.parquet", engine="pyarrow")
            (temp_path / "metadata.json").write_text(
                json.dumps(
                    metadata.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            os.replace(temp_path, final_path)
        finally:
            if temp_path.exists():
                resolved = temp_path.resolve()
                if not resolved.is_relative_to(self._root.resolve()):
                    raise CacheIntegrityError("temporary cache path escaped cache root")
                shutil.rmtree(resolved)
        return self._read_dataset(final_path, guarded)

    def _request_dir(self, request: DataRequest) -> Path:
        return (
            self._root
            / request.provider.lower()
            / request.symbol
            / request.interval
            / request.adjustment.lower()
            / f"{request.start.isoformat()}_{request.end.isoformat()}"
        )

    def _find_by_hash(self, request: DataRequest, digest: str) -> CachedDataset | None:
        request_dir = self._request_dir(request)
        if not request_dir.exists():
            return None
        for metadata_path in request_dir.glob("*/metadata.json"):
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            if payload.get("content_hash") == digest:
                return self._read_dataset(metadata_path.parent, request)
        return None

    def _read_dataset(self, path: Path, request: DataRequest) -> CachedDataset:
        metadata_path = path / "metadata.json"
        data_path = path / "bars.parquet"
        try:
            metadata = DatasetMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
            frame = pd.read_parquet(data_path, engine="pyarrow")
        except Exception as exc:
            raise CacheIntegrityError(f"cache dataset unreadable: {path}") from exc
        expected = (
            request.provider,
            request.symbol,
            request.interval,
            request.adjustment,
            request.start,
            request.end,
        )
        actual = (
            metadata.provider,
            metadata.symbol,
            metadata.interval,
            metadata.adjustment,
            metadata.requested_start,
            metadata.requested_end,
        )
        if actual != expected:
            raise CacheIntegrityError(f"cache metadata identity mismatch: {path}")
        if metadata.row_count != len(frame):
            raise CacheIntegrityError(f"cache row count mismatch: {path}")
        if content_hash(frame) != metadata.content_hash:
            raise CacheIntegrityError(f"cache content hash mismatch: {path}")
        return CachedDataset(path, data_path, metadata_path, metadata, frame)

    def _record_quarantine(
        self,
        request: DataRequest,
        report: DataValidationReport,
        retrieved_at: datetime,
    ) -> None:
        quarantine = self._root / "quarantine"
        quarantine.mkdir(parents=True, exist_ok=True)
        path = quarantine / f"{retrieved_at.strftime('%Y%m%dT%H%M%S%fZ')}_{uuid4().hex}.json"
        payload = {
            "request": request.model_dump(mode="json"),
            "retrieved_at": retrieved_at.isoformat(),
            "status": "QUARANTINED",
            "issues": [issue.__dict__ for issue in report.issues],
        }
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
