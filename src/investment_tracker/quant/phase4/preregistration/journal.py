from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field, model_validator

from .canonical import canonical_json_bytes, canonical_sha256, normalize_repository_path
from .models import FrozenGate1Model


GENESIS_DIGEST = "0" * 64
JournalKind = Literal["SOURCE", "HYPOTHESIS"]


class Gate1JournalError(RuntimeError):
    """Raised when an append-only Gate 1 journal cannot be trusted."""


class Gate1JournalRecord(FrozenGate1Model):
    schema_version: Literal["PHASE4-JOURNAL-RECORD-v1"] = (
        "PHASE4-JOURNAL-RECORD-v1"
    )
    record_kind: JournalKind
    record_id: str = Field(min_length=1)
    recorded_at: str = Field(min_length=1)
    predecessor_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: dict[str, object]
    record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_record(self) -> "Gate1JournalRecord":
        try:
            parsed = datetime.strptime(
                self.recorded_at, "%Y-%m-%dT%H:%M:%S.%fZ"
            )
        except ValueError as exc:
            raise ValueError("recorded_at must be UTC RFC3339 with microseconds") from exc
        if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != self.recorded_at:
            raise ValueError("recorded_at must be canonical UTC RFC3339")
        expected = canonical_sha256(
            {
                "schema_version": self.schema_version,
                "record_kind": self.record_kind,
                "record_id": self.record_id,
                "recorded_at": self.recorded_at,
                "predecessor_digest": self.predecessor_digest,
                "payload": self.payload,
            }
        )
        if self.record_digest != expected:
            raise ValueError("record digest mismatch")
        return self


class Gate1JournalState(FrozenGate1Model):
    schema_version: Literal["PHASE4-JOURNAL-STATE-v1"] = (
        "PHASE4-JOURNAL-STATE-v1"
    )
    path: str
    record_kind: JournalKind
    record_count: int = Field(ge=0)
    terminal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Gate1Journal:
    def __init__(
        self,
        repository_root: Path,
        path: Path,
        *,
        record_kind: JournalKind,
        sealed: bool = False,
    ) -> None:
        try:
            repository = Path(repository_root).resolve(strict=True)
            relative = normalize_repository_path(repository, path)
        except (OSError, ValueError) as exc:
            raise Gate1JournalError("journal path must be repository constrained") from exc
        parts = PurePosixPath(relative).parts
        expected_name = {
            "SOURCE": "sources.jsonl",
            "HYPOTHESIS": "hypothesis_registry.jsonl",
        }[record_kind]
        if parts[:2] != ("results", "research") or parts[-1] != expected_name:
            raise Gate1JournalError("journal path is not an exact Gate 1 research path")
        self._repository_root = repository
        self._path = repository.joinpath(*parts)
        self._relative_path = relative
        self._record_kind = record_kind
        self._sealed = sealed
        self._lock_path = repository / ".phase4-gate1-journal.lock"

    def _assert_no_symlink(self) -> None:
        current = self._repository_root
        for component in self._path.relative_to(self._repository_root).parts:
            current = current / component
            if current.is_symlink():
                raise Gate1JournalError("journal path contains symlink component")

    def _read_records(self) -> tuple[tuple[Gate1JournalRecord, ...], bytes]:
        self._assert_no_symlink()
        if not self._path.exists():
            return (), b""
        if not self._path.is_file():
            raise Gate1JournalError("journal path is not a regular file")
        try:
            raw = self._path.read_bytes()
        except OSError as exc:
            raise Gate1JournalError("journal is unreadable") from exc
        if raw and not raw.endswith(b"\n"):
            raise Gate1JournalError("journal has a partial trailing record")
        if b"\r" in raw:
            raise Gate1JournalError("journal must use LF line endings")
        if not raw:
            return (), raw
        raw_lines = raw[:-1].split(b"\n")
        if any(not line for line in raw_lines):
            raise Gate1JournalError("journal contains a blank line")

        records: list[Gate1JournalRecord] = []
        predecessor = GENESIS_DIGEST
        ids: set[str] = set()
        digests: set[str] = set()
        for line in raw_lines:
            try:
                text = line.decode("utf-8", errors="strict")
                payload = json.loads(text)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise Gate1JournalError("journal record is invalid UTF-8 JSON") from exc
            if canonical_json_bytes(payload) != line:
                raise Gate1JournalError("journal record is not canonical JSON")
            if payload.get("predecessor_digest") != predecessor:
                raise Gate1JournalError("journal predecessor chain mismatch")
            try:
                record = Gate1JournalRecord.model_validate(payload)
            except Exception as exc:
                raise Gate1JournalError("journal record validation failed") from exc
            if record.record_kind != self._record_kind:
                raise Gate1JournalError("journal record kind mismatch")
            if record.record_id in ids:
                raise Gate1JournalError("duplicate record ID")
            if record.record_digest in digests:
                raise Gate1JournalError("duplicate record digest")
            ids.add(record.record_id)
            digests.add(record.record_digest)
            predecessor = record.record_digest
            records.append(record)
        return tuple(records), raw

    def verify(
        self,
        expected_state: Gate1JournalState | None = None,
    ) -> Gate1JournalState:
        records, raw = self._read_records()
        state = Gate1JournalState(
            path=self._relative_path,
            record_kind=self._record_kind,
            record_count=len(records),
            terminal_digest=(records[-1].record_digest if records else GENESIS_DIGEST),
            file_sha256=sha256(raw).hexdigest(),
        )
        if expected_state is not None and state != expected_state:
            raise Gate1JournalError("journal does not match its expected state")
        return state

    def _acquire_lock(self) -> int:
        try:
            return os.open(
                self._lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            raise Gate1JournalError("Gate 1 writer lock is already held") from exc
        except OSError as exc:
            raise Gate1JournalError("Gate 1 writer lock cannot be created") from exc

    def append(
        self,
        record_id: str,
        payload: dict[str, object],
        recorded_at: str,
    ) -> Gate1JournalRecord:
        if self._sealed:
            raise Gate1JournalError("Gate 1 journal is sealed")
        existing, _ = self._read_records()
        matches = tuple(record for record in existing if record.record_id == record_id)
        if matches:
            match = matches[0]
            if (
                match == existing[-1]
                and match.payload == payload
                and match.recorded_at == recorded_at
            ):
                return match
            raise Gate1JournalError("duplicate record ID")

        lock_fd = self._acquire_lock()
        try:
            os.write(lock_fd, b"held\n")
            os.fsync(lock_fd)
            current, _ = self._read_records()
            if any(record.record_id == record_id for record in current):
                raise Gate1JournalError("duplicate record ID")
            predecessor = (
                current[-1].record_digest if current else GENESIS_DIGEST
            )
            base = {
                "schema_version": "PHASE4-JOURNAL-RECORD-v1",
                "record_kind": self._record_kind,
                "record_id": record_id,
                "recorded_at": recorded_at,
                "predecessor_digest": predecessor,
                "payload": payload,
            }
            record = Gate1JournalRecord(
                **base,
                record_digest=canonical_sha256(base),
            )
            line = canonical_json_bytes(record.model_dump(mode="json")) + b"\n"
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._assert_no_symlink()
            descriptor = os.open(
                self._path,
                os.O_CREAT
                | os.O_APPEND
                | os.O_WRONLY
                | getattr(os, "O_BINARY", 0),
                0o600,
            )
            try:
                written = 0
                while written < len(line):
                    count = os.write(descriptor, line[written:])
                    if count <= 0:
                        raise Gate1JournalError("journal append made no progress")
                    written += count
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            verified, _ = self._read_records()
            if not verified or verified[-1] != record:
                raise Gate1JournalError("journal post-append verification failed")
            return record
        finally:
            os.close(lock_fd)
            try:
                self._lock_path.unlink()
            except OSError as exc:
                raise Gate1JournalError("Gate 1 writer lock cleanup failed") from exc
