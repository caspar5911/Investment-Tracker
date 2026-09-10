from __future__ import annotations

from collections.abc import Mapping


class StaleSnapshotError(RuntimeError):
    pass


class SnapshotLineageError(ValueError):
    pass


def verify_snapshot_fresh(worker_manifest: object, current_input_digests: Mapping[str, str]) -> None:
    expected = getattr(worker_manifest, "input_snapshot_digests", None)
    if not isinstance(expected, Mapping) or not expected:
        raise StaleSnapshotError("worker manifest has no input snapshot digests")

    expected_keys = set(expected)
    current_keys = set(current_input_digests)
    if expected_keys != current_keys:
        missing = sorted(expected_keys - current_keys)
        added = sorted(current_keys - expected_keys)
        detail = []
        if missing:
            detail.append(f"missing={','.join(missing)}")
        if added:
            detail.append(f"added={','.join(added)}")
        suffix = f" ({'; '.join(detail)})" if detail else ""
        raise StaleSnapshotError(f"canonical digest set changed{suffix}")

    changed = [
        key
        for key, expected_digest in expected.items()
        if current_input_digests.get(key) != expected_digest
    ]
    if changed:
        names = ", ".join(sorted(changed))
        raise StaleSnapshotError(f"stale snapshot inputs: {names}")


def verify_manifest_snapshot_lineage(
    worker_manifest: object,
    input_snapshot: object,
    current_input_digests: Mapping[str, str],
) -> None:
    manifest_snapshot_id = getattr(worker_manifest, "input_snapshot_id", None)
    snapshot_id = getattr(input_snapshot, "snapshot_id", None)
    if manifest_snapshot_id != snapshot_id:
        raise SnapshotLineageError("snapshot ID mismatch")

    manifest_asset = getattr(worker_manifest, "asset", None)
    snapshot_asset = getattr(input_snapshot, "asset", None)
    if manifest_asset != snapshot_asset:
        raise SnapshotLineageError("asset scope mismatch")

    manifest_start = getattr(worker_manifest, "start_date", None)
    manifest_end = getattr(worker_manifest, "end_date", None)
    snapshot_start = getattr(input_snapshot, "start_date", None)
    snapshot_end = getattr(input_snapshot, "end_date", None)
    if (manifest_start, manifest_end) != (snapshot_start, snapshot_end):
        raise SnapshotLineageError("date scope mismatch")

    manifest_versions = getattr(worker_manifest, "versions", None)
    snapshot_versions = getattr(input_snapshot, "versions", None)
    if manifest_versions != snapshot_versions:
        raise SnapshotLineageError("frozen version mismatch")

    manifest_digests = getattr(worker_manifest, "input_snapshot_digests", None)
    snapshot_digests = getattr(input_snapshot, "input_digests", None)
    if manifest_digests != snapshot_digests:
        raise SnapshotLineageError("snapshot digest map mismatch")

    snapshot_spy_digest = getattr(input_snapshot, "spy_digest", None)
    if not isinstance(snapshot_digests, Mapping) or snapshot_digests.get("spy") != snapshot_spy_digest:
        raise SnapshotLineageError("snapshot SPY digest is inconsistent with input digest map")

    verify_snapshot_fresh(worker_manifest, current_input_digests)
