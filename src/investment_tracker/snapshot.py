from __future__ import annotations

from collections.abc import Mapping


class StaleSnapshotError(RuntimeError):
    pass


def verify_snapshot_fresh(worker_manifest: object, current_input_digests: Mapping[str, str]) -> None:
    expected = getattr(worker_manifest, "input_snapshot_digests", None)
    if not isinstance(expected, Mapping) or not expected:
        raise StaleSnapshotError("worker manifest has no input snapshot digests")

    changed: list[str] = []
    for key, expected_digest in expected.items():
        current_digest = current_input_digests.get(key)
        if current_digest != expected_digest:
            changed.append(key)

    if changed:
        names = ", ".join(sorted(changed))
        raise StaleSnapshotError(f"stale snapshot inputs: {names}")
