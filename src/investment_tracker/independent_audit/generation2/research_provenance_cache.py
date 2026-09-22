from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from investment_tracker.quant.data.cache import content_hash
from investment_tracker.quant.generation2.grid import RESEARCH_SYMBOLS
from investment_tracker.quant.generation2.provenance import (
    FileHash,
    SourceSnapshot,
    reconcile,
    snapshot_content_sha256,
)
from investment_tracker.quant.generation2.reproduction import verify_reproduction_report
from investment_tracker.quant.universe.artifacts import Phase3ArtifactStore
from investment_tracker.quant.universe.models import ArtifactIdentity

from .research_provenance_export import _canonical_bytes, _expected_session_authority_sha256

CACHE_PROVENANCE_SCHEMA = "GENERATION2-PHASE3-PROVIDER-ORIGIN-PROVENANCE-v1"
RECONCILIATION_SCHEMA = "GENERATION2-INDEPENDENT-RECONCILIATION-v1"


def _load_dataset_for_symbol(
    *,
    store: Phase3ArtifactStore,
    normalized_root: Path,
    symbol: str,
) -> tuple[Any, Any, str]:
    matches: list[tuple[ArtifactIdentity, dict[str, Any]]] = []
    for metadata_path in sorted(normalized_root.glob("*/metadata.json")):
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata")
        if isinstance(metadata, dict) and metadata.get("symbol") == symbol:
            digest = metadata_path.parent.name
            matches.append(
                (
                    ArtifactIdentity(
                        kind="normalized_dataset",
                        sha256=digest,
                        path=f"phase3/normalized/sha256/{digest}",
                    ),
                    payload,
                )
            )
    if len(matches) != 1:
        raise ValueError(f"GEN2_CACHE_PROVENANCE_DATASET_COUNT:{symbol}:{len(matches)}")
    identity, payload = matches[0]
    frame, metadata = store.load_normalized_dataset(identity)
    digest = content_hash(frame)
    if payload.get("content_sha256") != digest:
        raise ValueError(f"GEN2_CACHE_PROVENANCE_NORMALIZED_HASH_MISMATCH:{symbol}")
    return frame, metadata, digest


def build_from_phase3_cache(
    *,
    cache_root: Path,
    output_root: Path,
    reproduction_report_path: Path,
) -> dict[str, Any]:
    cache_root = Path(cache_root)
    output_root = Path(output_root)
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError("GEN2_CACHE_PROVENANCE_OUTPUT_NOT_EMPTY")

    normalized_root = cache_root / "phase3" / "normalized" / "sha256"
    if not normalized_root.is_dir():
        raise ValueError("GEN2_CACHE_PROVENANCE_NORMALIZED_ROOT_MISSING")

    reproduction = verify_reproduction_report(reproduction_report_path)
    primary_hashes = reproduction.get("snapshot_symbols")
    if not isinstance(primary_hashes, dict) or set(primary_hashes) != set(RESEARCH_SYMBOLS):
        raise ValueError("GEN2_CACHE_PROVENANCE_PRIMARY_HASH_SET_INVALID")

    store = Phase3ArtifactStore(cache_root, cache_root)
    normalized_hashes: list[FileHash] = []
    raw_hashes: list[FileHash] = []
    lineage: list[dict[str, Any]] = []
    normalization_versions: set[str] = set()

    for symbol in RESEARCH_SYMBOLS:
        frame, metadata, normalized_digest = _load_dataset_for_symbol(
            store=store,
            normalized_root=normalized_root,
            symbol=symbol,
        )
        if normalized_digest != primary_hashes[symbol]:
            raise ValueError(f"GEN2_CACHE_PROVENANCE_REPRODUCTION_HASH_MISMATCH:{symbol}")

        raw_identity = metadata.raw_evidence
        raw_payload = store.read_json(raw_identity)
        request = raw_payload.get("request")
        if not isinstance(request, dict):
            raise ValueError(f"GEN2_CACHE_PROVENANCE_RAW_REQUEST_INVALID:{symbol}")
        if raw_payload.get("status") != "SUCCESS":
            raise ValueError(f"GEN2_CACHE_PROVENANCE_RAW_STATUS_INVALID:{symbol}")
        if (
            request.get("symbol") != symbol
            or request.get("start") != "2014-01-01"
            or request.get("end") != "2022-12-31"
            or request.get("adjustment") != "QFQ"
        ):
            raise ValueError(f"GEN2_CACHE_PROVENANCE_RAW_REQUEST_MISMATCH:{symbol}")

        raw_path = store.resolve(raw_identity)
        raw_bytes = raw_path.read_bytes()
        raw_digest = sha256(raw_bytes).hexdigest()
        if raw_digest != raw_identity.sha256:
            raise ValueError(f"GEN2_CACHE_PROVENANCE_RAW_HASH_MISMATCH:{symbol}")

        normalized_hashes.append(FileHash(symbol=symbol, sha256=normalized_digest))
        raw_hashes.append(FileHash(symbol=symbol, sha256=raw_digest))
        normalization_versions.add(metadata.normalization_version)
        lineage.append(
            {
                "symbol": symbol,
                "normalized_dataset_identity": identity_dict(
                    kind="normalized_dataset",
                    sha256_value=_dataset_identity_sha(normalized_root, symbol),
                ),
                "normalized_content_sha256": normalized_digest,
                "raw_evidence": raw_identity.model_dump(mode="json"),
                "raw_evidence_sha256": raw_digest,
                "retrieved_at": metadata.retrieved_at.isoformat(),
                "sdk_version": metadata.sdk_version,
                "opend_version": metadata.opend_version,
                "normalization_version": metadata.normalization_version,
            }
        )

    if len(normalization_versions) != 1:
        raise ValueError("GEN2_CACHE_PROVENANCE_NORMALIZATION_VERSION_MISMATCH")
    normalization_version = next(iter(normalization_versions))
    expected_session_sha = _expected_session_authority_sha256()

    independent = SourceSnapshot(
        schema_version="G2-INDEPENDENT-SOURCE-PROVENANCE-v1",
        provider="MOOMOO_PHASE3_IMMUTABLE_RAW_EVIDENCE",
        acquisition_utc="ORIGINAL_PHASE3_PROVIDER_ACQUISITION",
        symbols=RESEARCH_SYMBOLS,
        range_start="2014-01-01",
        range_end="2022-12-31",
        adjustment_convention="QFQ",
        raw_file_hashes=tuple(raw_hashes),
        normalized_file_hashes=tuple(normalized_hashes),
        expected_session_authority_sha256=expected_session_sha,
        corporate_action_source_hashes=(),
        transformation_code_version=normalization_version,
        independence="PROVIDER_ORIGIN_EXPORT",
    )
    primary = SourceSnapshot(
        schema_version="G2-INDEPENDENT-SOURCE-PROVENANCE-v1",
        provider="SEALED_GENERATION2_RESEARCH_CACHE",
        acquisition_utc="SEALED_PRE_GENERATION2_CAMPAIGN",
        symbols=RESEARCH_SYMBOLS,
        range_start="2014-01-01",
        range_end="2022-12-31",
        adjustment_convention="QFQ",
        raw_file_hashes=(),
        normalized_file_hashes=tuple(
            FileHash(symbol=symbol, sha256=str(primary_hashes[symbol]))
            for symbol in RESEARCH_SYMBOLS
        ),
        expected_session_authority_sha256=expected_session_sha,
        corporate_action_source_hashes=(),
        transformation_code_version=normalization_version,
        independence="SAME_PROVIDER",
    )
    reconciliation = reconcile(primary, independent)

    output_root.mkdir(parents=True, exist_ok=True)
    primary_payload = primary.model_dump(mode="json")
    primary_payload["snapshot_sha256"] = snapshot_content_sha256(primary)
    independent_payload = independent.model_dump(mode="json")
    independent_payload["snapshot_sha256"] = snapshot_content_sha256(independent)
    independent_payload["schema_version_cache_provenance"] = CACHE_PROVENANCE_SCHEMA
    independent_payload["lineage"] = lineage
    reconciliation_payload = reconciliation.model_dump(mode="json")
    reconciliation_payload["schema_version_reconciliation"] = RECONCILIATION_SCHEMA
    reconciliation_payload["reproduction_report_sha256"] = reproduction["report_sha256"]

    (output_root / "primary-snapshot.json").write_bytes(_canonical_bytes(primary_payload))
    (output_root / "provider-origin-snapshot.json").write_bytes(_canonical_bytes(independent_payload))
    (output_root / "reconciliation.json").write_bytes(_canonical_bytes(reconciliation_payload))

    result = {
        "status": reconciliation.status,
        "independent_source_established": reconciliation.independent_source_established,
        "decision_critical": reconciliation.decision_critical,
        "primary_snapshot_sha256": primary_payload["snapshot_sha256"],
        "provider_origin_snapshot_sha256": independent_payload["snapshot_sha256"],
        "reconciliation_sha256": sha256(
            (output_root / "reconciliation.json").read_bytes()
        ).hexdigest(),
        "research_symbols": list(RESEARCH_SYMBOLS),
        "provider_history_requested": False,
        "holdout_symbols_accessed": [],
        "output_root": str(output_root),
    }
    (output_root / "result.json").write_bytes(_canonical_bytes(result))
    return result


def _dataset_identity_sha(normalized_root: Path, symbol: str) -> str:
    matches = []
    for metadata_path in sorted(normalized_root.glob("*/metadata.json")):
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata")
        if isinstance(metadata, dict) and metadata.get("symbol") == symbol:
            matches.append(metadata_path.parent.name)
    if len(matches) != 1:
        raise ValueError(f"GEN2_CACHE_PROVENANCE_DATASET_COUNT:{symbol}:{len(matches)}")
    return matches[0]


def identity_dict(*, kind: str, sha256_value: str) -> dict[str, str]:
    return {
        "kind": kind,
        "sha256": sha256_value,
        "path": f"phase3/normalized/sha256/{sha256_value}",
    }
