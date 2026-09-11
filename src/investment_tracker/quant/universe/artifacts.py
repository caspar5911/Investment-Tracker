from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any

import pandas as pd

from investment_tracker.governance import assert_symbol_allowed
from investment_tracker.quant.data.cache import content_hash
from investment_tracker.quant.data.moomoo_client import (
    MoomooCalendarEvidence,
    MoomooFetchEvidence,
)

from .constants import RAW_EVIDENCE_SCHEMA_VERSION
from .hashing import canonical_json_bytes, canonical_sha256, tag_scalar
from .models import (
    ArtifactIdentity,
    CandidateDQResult,
    DQSnapshot,
    NormalizedDatasetMetadata,
    ProviderRequestRecord,
    UniverseManifest,
)


class ArtifactIntegrityError(RuntimeError):
    pass


_EVIDENCE_KINDS = {
    "raw_provider_evidence",
    "calendar_provider_evidence",
    "normalized_dataset",
    "quarantine",
    "candidate_dq",
}
_RESULT_KINDS = {"dq_snapshot", "dq_report", "universe_manifest"}


def _tag_nested(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _tag_nested(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_tag_nested(item) for item in value]
    return tag_scalar(value)


def _raw_payload(evidence: MoomooFetchEvidence, opend_version: str | None) -> dict[str, object]:
    pages = []
    for page in evidence.pages:
        columns = [str(column) for column in page.frame.columns]
        rows = [
            [tag_scalar(value) for value in row]
            for row in page.frame.itertuples(index=False, name=None)
        ]
        pages.append(
            {
                "page_number": page.page_number,
                "input_page_req_key": tag_scalar(page.input_page_req_key),
                "output_page_req_key": tag_scalar(page.output_page_req_key),
                "columns": columns,
                "dtypes": [str(dtype) for dtype in page.frame.dtypes],
                "rows": rows,
            }
        )
    return {
        "schema_version": RAW_EVIDENCE_SCHEMA_VERSION,
        "status": evidence.status,
        "request": evidence.request.model_dump(mode="json"),
        "request_parameters": evidence.request_parameters,
        "retrieved_at": evidence.retrieved_at.isoformat(),
        "sdk_version": evidence.sdk_version,
        "opend_version": opend_version,
        "pages": pages,
        "row_links": [
            {
                "page_number": link.page_number,
                "row_number": link.row_number,
                "code": link.code,
                "raw_time_key": link.raw_time_key,
                "normalized_date": link.normalized_date.isoformat(),
            }
            for link in evidence.row_links
        ],
        "error": evidence.error,
        "error_data": _tag_nested(evidence.error_data),
    }


class Phase3ArtifactStore:
    def __init__(self, evidence_root: Path, results_root: Path) -> None:
        self._evidence_root = Path(evidence_root)
        self._results_root = Path(results_root)

    def _base_for_kind(self, kind: str) -> Path:
        if kind in _EVIDENCE_KINDS:
            return self._evidence_root
        if kind in _RESULT_KINDS:
            return self._results_root
        raise ArtifactIntegrityError(f"unknown artifact kind: {kind}")

    def resolve(self, identity: ArtifactIdentity) -> Path:
        logical = PurePosixPath(identity.path)
        if logical.is_absolute() or ".." in logical.parts:
            raise ArtifactIntegrityError("artifact path escapes configured root")
        base = self._base_for_kind(identity.kind).resolve()
        resolved = base.joinpath(*logical.parts).resolve()
        if not resolved.is_relative_to(base):
            raise ArtifactIntegrityError("artifact path escapes configured root")
        return resolved

    @staticmethod
    def _write_once(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                existing = path.read_bytes()
            except OSError as exc:
                raise ArtifactIntegrityError(f"immutable artifact unreadable: {path}") from exc
            if existing != payload:
                raise ArtifactIntegrityError(f"immutable artifact collision: {path}")
            return
        handle, temporary_name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _write_json_artifact(
        self,
        *,
        kind: str,
        payload: object,
        logical_path: str,
    ) -> ArtifactIdentity:
        encoded = canonical_json_bytes(payload)
        digest = sha256(encoded).hexdigest()
        relative = logical_path.format(digest=digest)
        identity = ArtifactIdentity(kind=kind, sha256=digest, path=relative)
        self._write_once(self.resolve(identity), encoded)
        return identity

    def read_json(self, identity: ArtifactIdentity) -> Any:
        path = self.resolve(identity)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ArtifactIntegrityError(f"artifact unreadable: {path}") from exc
        actual = sha256(payload).hexdigest()
        if actual != identity.sha256:
            raise ArtifactIntegrityError(
                f"artifact hash mismatch: expected {identity.sha256}, got {actual}"
            )
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ArtifactIntegrityError(f"artifact JSON invalid: {path}") from exc

    def write_raw_evidence(
        self, evidence: MoomooFetchEvidence, opend_version: str | None
    ) -> ArtifactIdentity:
        assert_symbol_allowed(evidence.request.symbol)
        payload = _raw_payload(evidence, opend_version)
        return self._write_json_artifact(
            kind="raw_provider_evidence",
            payload=payload,
            logical_path="phase3/raw/moomoo/sha256/{digest}/evidence.json",
        )

    def write_calendar_evidence(
        self, evidence: MoomooCalendarEvidence, opend_version: str | None
    ) -> ArtifactIdentity:
        assert_symbol_allowed(evidence.request.symbol)
        payload = {
            "schema_version": "MOOMOO-CALENDAR-EVIDENCE-v1",
            "status": evidence.status,
            "request": evidence.request.model_dump(mode="json"),
            "request_parameters": evidence.request_parameters,
            "retrieved_at": evidence.retrieved_at.isoformat(),
            "sdk_version": evidence.sdk_version,
            "opend_version": opend_version,
            "data": _tag_nested(evidence.data),
            "error": evidence.error,
        }
        return self._write_json_artifact(
            kind="calendar_provider_evidence",
            payload=payload,
            logical_path="phase3/raw/moomoo-calendar/sha256/{digest}/evidence.json",
        )

    def write_normalized_dataset(
        self,
        frame: pd.DataFrame,
        metadata: NormalizedDatasetMetadata,
    ) -> ArtifactIdentity:
        assert_symbol_allowed(metadata.symbol)
        self.read_json(metadata.raw_evidence)
        if frame.empty:
            raise ArtifactIntegrityError("normalized dataset cannot be empty")
        if len(frame) != metadata.row_count:
            raise ArtifactIntegrityError("normalized dataset row count mismatch")
        frame_digest = content_hash(frame)
        metadata_payload = {
            "metadata": metadata.model_dump(mode="json"),
            "content_sha256": frame_digest,
        }
        digest = canonical_sha256(metadata_payload)
        identity = ArtifactIdentity(
            kind="normalized_dataset",
            sha256=digest,
            path=f"phase3/normalized/sha256/{digest}",
        )
        final_path = self.resolve(identity)
        if final_path.exists():
            self.load_normalized_dataset(identity)
            return identity
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".tmp-", dir=final_path.parent))
        try:
            frame.to_parquet(temporary / "bars.parquet", engine="pyarrow")
            (temporary / "metadata.json").write_bytes(canonical_json_bytes(metadata_payload))
            os.replace(temporary, final_path)
        finally:
            if temporary.exists():
                root = self._evidence_root.resolve()
                resolved = temporary.resolve()
                if not resolved.is_relative_to(root):
                    raise ArtifactIntegrityError("temporary artifact path escaped evidence root")
                shutil.rmtree(resolved)
        self.load_normalized_dataset(identity)
        return identity

    def load_normalized_dataset(
        self, identity: ArtifactIdentity
    ) -> tuple[pd.DataFrame, NormalizedDatasetMetadata]:
        if identity.kind != "normalized_dataset":
            raise ArtifactIntegrityError("artifact is not a normalized dataset")
        path = self.resolve(identity)
        try:
            payload = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
            metadata = NormalizedDatasetMetadata.model_validate(payload["metadata"])
            frame = pd.read_parquet(path / "bars.parquet", engine="pyarrow")
        except Exception as exc:
            raise ArtifactIntegrityError(f"normalized dataset unreadable: {path}") from exc
        actual_content_hash = content_hash(frame)
        if payload.get("content_sha256") != actual_content_hash:
            raise ArtifactIntegrityError("normalized dataset content hash mismatch")
        if len(frame) != metadata.row_count:
            raise ArtifactIntegrityError("normalized dataset row count mismatch")
        actual_identity = canonical_sha256(payload)
        if actual_identity != identity.sha256:
            raise ArtifactIntegrityError("normalized dataset metadata hash mismatch")
        self.read_json(metadata.raw_evidence)
        return frame, metadata

    def write_quarantine(self, payload: dict[str, object]) -> ArtifactIdentity:
        symbol = payload.get("symbol")
        if not isinstance(symbol, str):
            raise ArtifactIntegrityError("quarantine requires a symbol")
        assert_symbol_allowed(symbol)
        return self._write_json_artifact(
            kind="quarantine",
            payload=payload,
            logical_path="phase3/quarantine/sha256/{digest}/quarantine.json",
        )

    def write_candidate_record(self, result: CandidateDQResult) -> ArtifactIdentity:
        assert_symbol_allowed(result.symbol)
        self.read_json(result.raw_evidence)
        if result.normalized_dataset is not None:
            self.load_normalized_dataset(result.normalized_dataset)
        if result.quarantine is not None:
            self.read_json(result.quarantine)
        for diagnostic in (*result.missing_sessions, *result.unexpected_sessions):
            if diagnostic.calendar.evidence is not None:
                self.read_json(diagnostic.calendar.evidence)
        return self._write_json_artifact(
            kind="candidate_dq",
            payload=result.model_dump(mode="json"),
            logical_path="phase3/candidates/sha256/{digest}/candidate.json",
        )

    def find_candidate_record(
        self,
        symbol: str,
        provider_request: ProviderRequestRecord,
        *,
        sdk_version: str | None,
        opend_version: str | None,
    ) -> CandidateDQResult | None:
        guarded = assert_symbol_allowed(symbol)
        if provider_request.symbol != guarded:
            return None
        root = self._evidence_root / "phase3" / "candidates" / "sha256"
        if not root.exists():
            return None
        for path in sorted(root.glob("*/candidate.json")):
            digest = path.parent.name
            identity = ArtifactIdentity(
                kind="candidate_dq",
                sha256=digest,
                path=f"phase3/candidates/sha256/{digest}/candidate.json",
            )
            result = CandidateDQResult.model_validate(self.read_json(identity))
            if (
                result.symbol == guarded
                and result.provider_request == provider_request
                and result.sdk_version == sdk_version
                and result.opend_version == opend_version
            ):
                self.read_json(result.raw_evidence)
                if result.normalized_dataset is not None:
                    self.load_normalized_dataset(result.normalized_dataset)
                if result.quarantine is not None:
                    self.read_json(result.quarantine)
                for diagnostic in (*result.missing_sessions, *result.unexpected_sessions):
                    if diagnostic.calendar.evidence is not None:
                        self.read_json(diagnostic.calendar.evidence)
                return result
        return None

    def freeze_dq_snapshot(self, snapshot: DQSnapshot) -> ArtifactIdentity:
        safe_campaign_id = re.sub(r"[^A-Za-z0-9_.-]", "_", snapshot.campaign_id)
        if safe_campaign_id != snapshot.campaign_id:
            raise ArtifactIntegrityError("campaign_id is not path-safe")
        return self._write_json_artifact(
            kind="dq_snapshot",
            payload=snapshot.model_dump(mode="json"),
            logical_path=(
                f"phase3/campaigns/{safe_campaign_id}/dq-snapshots/"
                "{digest}.json"
            ),
        )

    def load_frozen_snapshot(self, identity: ArtifactIdentity) -> DQSnapshot:
        if identity.kind != "dq_snapshot":
            raise ArtifactIntegrityError("artifact is not a DQ snapshot")
        return DQSnapshot.model_validate(self.read_json(identity))

    def write_report(self, campaign_id: str, report: str) -> ArtifactIdentity:
        safe_campaign_id = re.sub(r"[^A-Za-z0-9_.-]", "_", campaign_id)
        if safe_campaign_id != campaign_id:
            raise ArtifactIntegrityError("campaign_id is not path-safe")
        payload = report.encode("utf-8")
        digest = sha256(payload).hexdigest()
        identity = ArtifactIdentity(
            kind="dq_report",
            sha256=digest,
            path=f"phase3/campaigns/{campaign_id}/reports/{digest}.md",
        )
        self._write_once(self.resolve(identity), payload)
        return identity

    def read_text(self, identity: ArtifactIdentity) -> str:
        path = self.resolve(identity)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ArtifactIntegrityError(f"artifact unreadable: {path}") from exc
        actual = sha256(payload).hexdigest()
        if actual != identity.sha256:
            raise ArtifactIntegrityError(
                f"artifact hash mismatch: expected {identity.sha256}, got {actual}"
            )
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ArtifactIntegrityError(f"artifact text is not UTF-8: {path}") from exc

    def write_universe_manifest(self, manifest: UniverseManifest) -> ArtifactIdentity:
        self.load_frozen_snapshot(manifest.dq_snapshot)
        self.read_text(manifest.dq_report)
        for identity in manifest.raw_evidence:
            self.read_json(identity)
        for identity in manifest.normalized_datasets:
            self.load_normalized_dataset(identity)
        return self._write_json_artifact(
            kind="universe_manifest",
            payload=manifest.model_dump(mode="json"),
            logical_path="phase3/universes/{digest}/manifest.json",
        )
