from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class LockHeldError(RuntimeError):
    pass


class StaleLockError(LockHeldError):
    pass


class CanonicalWriteLock:
    def __init__(self, path: str | Path, stale_after_seconds: int = 3600) -> None:
        self.path = Path(path)
        self.stale_after_seconds = stale_after_seconds

    def _existing(self) -> dict[str, str]:
        try:
            return json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise LockHeldError("canonical write lock exists but cannot be safely read") from exc

    def _raise_existing(self) -> None:
        data = self._existing()
        try:
            acquired = datetime.fromisoformat(data["acquired_at"])
            if acquired.tzinfo is None:
                acquired = acquired.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - acquired.astimezone(timezone.utc)).total_seconds()
        except (KeyError, TypeError, ValueError) as exc:
            raise LockHeldError("canonical write lock metadata is invalid") from exc
        if age > self.stale_after_seconds:
            raise StaleLockError(
                f"stale canonical write lock owned by {data.get('run_id', 'UNKNOWN')}; explicit recovery required"
            )
        raise LockHeldError(f"canonical write lock held by {data.get('run_id', 'UNKNOWN')}")

    def acquire(self, run_id: str, scope: str, snapshot_id: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "run_id": run_id,
            "scope": scope,
            "snapshot_id": snapshot_id,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        }
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            self._raise_existing()
            return
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
        except Exception:
            self.path.unlink(missing_ok=True)
            raise

    def release(self, run_id: str) -> None:
        if not self.path.exists():
            raise LockHeldError("canonical write lock does not exist")
        data = self._existing()
        if data.get("run_id") != run_id:
            raise LockHeldError(
                f"canonical write lock owned by {data.get('run_id', 'UNKNOWN')}, not {run_id}"
            )
        self.path.unlink()
