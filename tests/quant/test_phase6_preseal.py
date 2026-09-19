from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_tracker.quant.phase5.methodology import (
    SELECTED_BINDING_SHA256,
    SELECTED_CANDIDATE_ID,
    SELECTED_IMPLEMENTATION_SHA256,
)
from investment_tracker.quant.phase6.preseal import (
    HoldoutRelease,
    Phase6HoldoutReuseError,
    consume_released_holdout,
    load_release_envelope,
    phase6_preflight,
)


def _release(**overrides: object) -> HoldoutRelease:
    payload: dict[str, object] = {
        "schema_version": "PHASE6-HOLDOUT-RELEASE-v1",
        "authority": "INDEPENDENT_AUDIT",
        "status": "FINAL_HOLDOUT_RELEASE_AUTHORIZED",
        "release_id": "audit-release-test-001",
        "holdout_id": "sealed-final-holdout-test",
        "candidate_id": SELECTED_CANDIDATE_ID,
        "binding_sha256": SELECTED_BINDING_SHA256,
        "implementation_sha256": SELECTED_IMPLEMENTATION_SHA256,
        "evaluation_contract_sha256": "a" * 64,
        "holdout_bundle_sha256": "b" * 64,
        "one_time": True,
    }
    payload.update(overrides)
    return HoldoutRelease.model_validate(payload)


def test_phase6_preflight_binds_frozen_survivor_without_holdout_access() -> None:
    result = phase6_preflight(Path("."))

    assert result["status"] == "PHASE6_READY_FOR_INDEPENDENT_AUDIT_RELEASE"
    assert result["candidate_id"] == SELECTED_CANDIDATE_ID
    assert result["binding_sha256"] == SELECTED_BINDING_SHA256
    assert result["implementation_sha256"] == SELECTED_IMPLEMENTATION_SHA256
    assert result["phase5_formal_status"] == "PHASE5_UNKNOWN_ABSTAIN"
    assert result["phase5_limitation"] == "INDEPENDENT_SOURCE_SNAPSHOT_MISSING"
    assert result["safety"]["final_holdout_accessed"] is False
    assert result["safety"]["protected_symbols_accessed"] == []
    assert result["safety"]["phase7_started"] is False


def test_release_envelope_requires_independent_audit_authority(tmp_path: Path) -> None:
    path = tmp_path / "release.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "PHASE6-HOLDOUT-RELEASE-v1",
                "authority": "PROJECT_OWNER",
                "status": "FINAL_HOLDOUT_RELEASE_AUTHORIZED",
                "release_id": "owner-release",
                "holdout_id": "sealed",
                "candidate_id": SELECTED_CANDIDATE_ID,
                "binding_sha256": SELECTED_BINDING_SHA256,
                "implementation_sha256": SELECTED_IMPLEMENTATION_SHA256,
                "evaluation_contract_sha256": "a" * 64,
                "holdout_bundle_sha256": "b" * 64,
                "one_time": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises((ValidationError, ValueError)):
        load_release_envelope(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidate_id", "other-candidate"),
        ("binding_sha256", "c" * 64),
        ("implementation_sha256", "d" * 64),
        ("one_time", False),
    ],
)
def test_release_envelope_must_match_frozen_identity(
    field: str,
    value: object,
) -> None:
    with pytest.raises((ValidationError, ValueError)):
        _release(**{field: value})


def test_one_time_marker_is_written_before_payload_read(tmp_path: Path) -> None:
    release = _release()
    events: list[str] = []

    def reader() -> str:
        marker = tmp_path / f"{release.release_id}.consumed.json"
        assert marker.is_file()
        events.append("read")
        return "payload"

    result = consume_released_holdout(
        release,
        marker_directory=tmp_path,
        payload_reader=reader,
    )

    assert result == "payload"
    assert events == ["read"]

    marker = json.loads(
        (tmp_path / f"{release.release_id}.consumed.json").read_text(encoding="utf-8")
    )
    assert marker["status"] == "FINAL_HOLDOUT_CONSUMED"
    assert marker["release_id"] == release.release_id
    assert marker["candidate_id"] == SELECTED_CANDIDATE_ID
    assert "metrics" not in marker


def test_holdout_release_cannot_be_consumed_twice(tmp_path: Path) -> None:
    release = _release()
    reads = 0

    def reader() -> str:
        nonlocal reads
        reads += 1
        return "payload"

    assert (
        consume_released_holdout(
            release,
            marker_directory=tmp_path,
            payload_reader=reader,
        )
        == "payload"
    )

    with pytest.raises(Phase6HoldoutReuseError):
        consume_released_holdout(
            release,
            marker_directory=tmp_path,
            payload_reader=reader,
        )

    assert reads == 1


@pytest.mark.parametrize("release_id", ["../escape", "nested/path", ".", ".."])
def test_release_id_cannot_escape_consumption_marker_directory(
    release_id: str,
) -> None:
    with pytest.raises(ValidationError):
        _release(release_id=release_id)
