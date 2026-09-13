from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from investment_tracker.quant.phase4.preregistration.canonical import (
    canonical_json_bytes,
)
from investment_tracker.quant.phase4.preregistration.journal import (
    GENESIS_DIGEST,
    Gate1Journal,
    Gate1JournalError,
)


RECORDED_AT = "2026-09-13T00:00:00.000000Z"


def _journal(repository: Path, *, sealed: bool = False) -> Gate1Journal:
    return Gate1Journal(
        repository,
        repository / "results" / "research" / "sources.jsonl",
        record_kind="SOURCE",
        sealed=sealed,
    )


def test_journal_appends_canonical_hash_chain_and_verifies(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    journal = _journal(repository)

    first = journal.append(
        record_id="source-first",
        payload={"title": "First"},
        recorded_at=RECORDED_AT,
    )
    second = journal.append(
        record_id="source-second",
        payload={"title": "Second"},
        recorded_at="2026-09-13T00:00:01.000000Z",
    )

    assert first.predecessor_digest == GENESIS_DIGEST
    assert second.predecessor_digest == first.record_digest
    raw = (repository / "results/research/sources.jsonl").read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw
    assert raw == b"".join(
        canonical_json_bytes(record.model_dump(mode="json")) + b"\n"
        for record in (first, second)
    )
    state = journal.verify()
    assert state.record_count == 2
    assert state.terminal_digest == second.record_digest
    assert state.file_sha256 == sha256(raw).hexdigest()


def test_journal_append_is_idempotent_for_exact_terminal_record(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    journal = _journal(repository)
    first = journal.append(
        record_id="source-first",
        payload={"title": "First"},
        recorded_at=RECORDED_AT,
    )
    before = (repository / "results/research/sources.jsonl").read_bytes()

    repeated = journal.append(
        record_id="source-first",
        payload={"title": "First"},
        recorded_at=RECORDED_AT,
    )

    assert repeated == first
    assert (repository / "results/research/sources.jsonl").read_bytes() == before


def test_duplicate_nonterminal_record_id_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    journal = _journal(repository)
    journal.append("source-first", {"title": "First"}, RECORDED_AT)
    journal.append("source-second", {"title": "Second"}, RECORDED_AT)
    before = (repository / "results/research/sources.jsonl").read_bytes()

    with pytest.raises(Gate1JournalError, match="duplicate record ID"):
        journal.append("source-first", {"title": "First"}, RECORDED_AT)
    assert (repository / "results/research/sources.jsonl").read_bytes() == before


@pytest.mark.parametrize("mutation", ("tail", "blank", "noncanonical", "utf8"))
def test_journal_corruption_fails_closed(tmp_path: Path, mutation: str) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    journal = _journal(repository)
    journal.append("source-first", {"title": "First"}, RECORDED_AT)
    path = repository / "results/research/sources.jsonl"
    raw = path.read_bytes()
    if mutation == "tail":
        path.write_bytes(raw.rstrip(b"\n"))
    elif mutation == "blank":
        path.write_bytes(raw + b"\n")
    elif mutation == "noncanonical":
        parsed = json.loads(raw)
        path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
    else:
        path.write_bytes(raw + b"\xff\n")

    with pytest.raises(Gate1JournalError):
        journal.verify()


def test_modified_predecessor_or_record_digest_fails(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    journal = _journal(repository)
    journal.append("source-first", {"title": "First"}, RECORDED_AT)
    journal.append("source-second", {"title": "Second"}, RECORDED_AT)
    path = repository / "results/research/sources.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    second = json.loads(lines[1])
    second["predecessor_digest"] = "f" * 64
    lines[1] = canonical_json_bytes(second).decode("utf-8")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    with pytest.raises(Gate1JournalError, match="predecessor"):
        journal.verify()


def test_expected_state_detects_valid_prefix_deletion(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    journal = _journal(repository)
    journal.append("source-first", {"title": "First"}, RECORDED_AT)
    journal.append("source-second", {"title": "Second"}, RECORDED_AT)
    expected = journal.verify()
    path = repository / "results/research/sources.jsonl"
    first_line = path.read_bytes().splitlines(keepends=True)[0]
    path.write_bytes(first_line)

    with pytest.raises(Gate1JournalError, match="expected state"):
        journal.verify(expected_state=expected)


def test_writer_lock_and_seal_reject_without_mutation(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    journal = _journal(repository)
    journal.append("source-first", {"title": "First"}, RECORDED_AT)
    path = repository / "results/research/sources.jsonl"
    before = path.read_bytes()
    lock = repository / ".phase4-gate1-journal.lock"
    lock.write_text("held", encoding="utf-8")

    with pytest.raises(Gate1JournalError, match="writer lock"):
        journal.append("source-second", {"title": "Second"}, RECORDED_AT)
    assert path.read_bytes() == before
    lock.unlink()

    sealed = _journal(repository, sealed=True)
    with pytest.raises(Gate1JournalError, match="sealed"):
        sealed.append("source-second", {"title": "Second"}, RECORDED_AT)
    assert path.read_bytes() == before
