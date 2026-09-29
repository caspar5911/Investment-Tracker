"""Provider-free tests for governed Phase-7 prospective collection."""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd
import pytest

from investment_tracker.independent_audit.post_generation3 import phase7_collector as collector
from investment_tracker.independent_audit.post_generation3.phase7_data import (
    Generation4Phase7DataRequest,
    _build_snapshot,
    _canonical_json,
    _snapshot_id,
    _write_snapshot,
    verify_generation4_phase7_evaluation_authorization,
)


UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
FIRST_SCORED = "2026-09-28"
WARMUP_START = "2025-11-24"


@pytest.fixture
def environment(bound_evidence, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    auth_path = tmp_path / "authorization.json"
    auth_path.write_text(json.dumps(bound_evidence.authorization), encoding="utf-8")
    output_dir = tmp_path / "prospective"
    output_dir.mkdir()
    monkeypatch.setattr(collector, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(collector, "_AUTHORIZATION_PATH", auth_path, raising=False)
    monkeypatch.setattr(collector, "_OUTPUT_DIR", output_dir, raising=False)
    monkeypatch.setattr(
        collector, "_utc_now",
        lambda: datetime.fromisoformat("2026-09-30T00:30:00+00:00"),
    )
    return {
        "auth_path": auth_path,
        "output_dir": output_dir,
        "authorization": verify_generation4_phase7_evaluation_authorization(auth_path),
    }


def _write_synthetic_snapshot(
    environment, *, scored_count: int = 1, retrieved_at_utc: str | None = None
) -> tuple[Path, dict]:
    calendar = xcals.get_calendar("XNYS")
    scored = calendar.sessions_in_range(FIRST_SCORED, "2026-10-01")[:scored_count]
    end = str(scored[-1].date())
    sessions = calendar.sessions_in_range(WARMUP_START, end)
    request = Generation4Phase7DataRequest.model_validate({
        "schema_version": "GENERATION4-PHASE7-DATA-REQUEST-v1",
        "symbols": list(UNIVERSE),
        "requested_start": WARMUP_START,
        "requested_end": end,
        "scored_start": FIRST_SCORED,
        "warmup_session_count": 210,
        "scored_session_count": scored_count,
    })
    authorization = environment["authorization"]
    frames = {}
    for offset, symbol in enumerate(UNIVERSE):
        values = [100.0 + offset + i / 100.0 for i in range(len(sessions))]
        frames[symbol] = pd.DataFrame({
            "open": values,
            "high": [value + 1 for value in values],
            "low": [value - 1 for value in values],
            "close": values,
            "volume": [1000] * len(sessions),
        }, index=sessions)
    rehab = {symbol: pd.DataFrame(columns=["ex_div_date"]) for symbol in UNIVERSE}
    dividends = {symbol: {"dividend_list": []} for symbol in UNIVERSE}
    splits = {symbol: {"split_list": []} for symbol in UNIVERSE}
    retrieved = retrieved_at_utc or (
        calendar.session_close(scored[-1]) + pd.Timedelta(hours=1)
    ).isoformat()
    snapshot_id = _snapshot_id(authorization, request, retrieved)
    manifest, payloads = _build_snapshot(
        authorization, request, frames, frames, rehab, dividends, splits, retrieved,
        snapshot_id=snapshot_id,
        authorization_sha256=sha256(environment["auth_path"].read_bytes()).hexdigest(),
    )
    snapshot_dir = environment["output_dir"] / "snapshots" / snapshot_id
    _write_snapshot(snapshot_dir, manifest, payloads)
    return snapshot_dir, manifest


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        ("2026-09-28T19:59:59+00:00", "2026-09-25"),
        ("2026-09-28T20:00:00+00:00", "2026-09-28"),
        ("2026-09-06T22:00:00+00:00", "2026-09-04"),
        ("2026-09-07T22:00:00+00:00", "2026-09-04"),
    ],
)
def test_latest_completed_session_respects_close_weekend_and_holiday(
    monkeypatch: pytest.MonkeyPatch, now: str, expected: str
) -> None:
    monkeypatch.setattr(collector, "_utc_now", lambda: datetime.fromisoformat(now))

    assert collector.latest_completed_session() == expected


@pytest.mark.parametrize(
    ("count", "next_checkpoint", "remaining", "status"),
    [
        (1, 63, 62, "PHASE7_COLLECTION_PENDING"),
        (62, 63, 1, "PHASE7_COLLECTION_PENDING"),
        (63, 63, 0, "PHASE7_CHECKPOINT_READY"),
        (64, 126, 62, "PHASE7_COLLECTION_PENDING"),
        (126, 126, 0, "PHASE7_CHECKPOINT_READY"),
        (252, 252, 0, "PHASE7_CHECKPOINT_READY"),
    ],
)
def test_progress_reports_frozen_checkpoints_without_evaluation(
    count: int, next_checkpoint: int, remaining: int, status: str
) -> None:
    result = collector.structural_progress(count)

    assert result == {
        "status": status,
        "scored_session_count": count,
        "next_checkpoint_sessions": next_checkpoint,
        "sessions_remaining": remaining,
    }


def test_collection_preserves_first_exact_checkpoint_before_later_session(environment) -> None:
    authorization = environment["authorization"]
    prior = [{"requested_end": "2026-12-23", "scored_session_count": 62}]
    assert collector._collection_target_end("2026-12-28", prior, authorization) == "2026-12-24"
    exact = {"requested_end": "2026-12-24", "scored_session_count": 63}
    assert collector._collection_target_end("2026-12-28", prior + [exact], authorization) == "2026-12-28"


def test_collection_abstains_if_later_snapshot_skipped_exact_63(environment) -> None:
    authorization = environment["authorization"]
    later = [{"requested_end": "2026-12-28", "scored_session_count": 64}]
    with pytest.raises(collector.Generation4Phase7CollectorError) as exc:
        collector._collection_target_end("2026-12-29", later, authorization)
    assert exc.value.code == collector.PHASE7_UNKNOWN_ABSTAIN


def test_valid_content_bound_snapshot_is_accepted_read_only(environment) -> None:
    snapshot_dir, expected = _write_synthetic_snapshot(environment)

    manifest = collector.verify_snapshot(
        snapshot_dir, environment["authorization"], environment["auth_path"]
    )

    assert manifest["snapshot_id"] == expected["snapshot_id"]
    assert manifest["scored_session_count"] == 1
    assert manifest["manifest_sha256"] == expected["manifest_sha256"]


def test_tampered_existing_file_fails_status_closed(environment) -> None:
    snapshot_dir, _ = _write_synthetic_snapshot(environment)
    with (snapshot_dir / "bars/qfq/SPY.csv").open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.prospective_status()


def test_extra_holdout_file_is_rejected_before_it_can_be_accepted(environment) -> None:
    snapshot_dir, _ = _write_synthetic_snapshot(environment)
    (snapshot_dir / "bars/qfq/QQQM.csv").write_text("synthetic only", encoding="utf-8")

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.verify_snapshot(
            snapshot_dir, environment["authorization"], environment["auth_path"]
        )


def test_symlinked_manifest_is_rejected_before_reading_target(
    environment, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot_dir, _ = _write_synthetic_snapshot(environment)
    manifest_path = snapshot_dir / "manifest.json"
    external = tmp_path / "external-manifest.json"
    external.write_bytes(manifest_path.read_bytes())
    manifest_path.unlink()
    try:
        manifest_path.symlink_to(external)
    except OSError:
        pytest.skip("symlink creation unavailable")
    original_read = Path.read_bytes

    def guarded_read(path: Path) -> bytes:
        if path == manifest_path:
            pytest.fail("symlinked manifest was read")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.verify_snapshot(
            snapshot_dir, environment["authorization"], environment["auth_path"]
        )


def test_rehashed_invalid_ohlc_is_rejected(environment) -> None:
    snapshot_dir, manifest = _write_synthetic_snapshot(environment)
    relative = "bars/unadjusted/SPY.csv"
    path = snapshot_dir / relative
    lines = path.read_text(encoding="utf-8").splitlines()
    parts = lines[1].split(",")
    parts[2] = "1"
    lines[1] = ",".join(parts)
    payload = ("\n".join(lines) + "\n").encode()
    path.write_bytes(payload)
    digest = sha256(payload).hexdigest()
    entry = next(item for item in manifest["files"] if item["path"] == relative)
    entry["bytes"] = len(payload)
    entry["sha256"] = digest
    manifest["symbols"]["SPY"]["unadjusted_sha256"] = digest
    manifest["manifest_sha256"] = sha256(_canonical_json({
        key: value for key, value in manifest.items() if key != "manifest_sha256"
    })).hexdigest()
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.verify_snapshot(
            snapshot_dir, environment["authorization"], environment["auth_path"]
        )


@pytest.mark.parametrize(
    ("field", "coerced"),
    [
        ("performance_computed", 0),
        ("performance_inspected", 0),
        ("trading_context_created", 0),
        ("corporate_actions_included", 1),
    ],
)
def test_rehashed_non_boolean_governance_flag_is_rejected(
    environment, field: str, coerced: int
) -> None:
    snapshot_dir, manifest = _write_synthetic_snapshot(environment)
    manifest[field] = coerced
    manifest["manifest_sha256"] = sha256(_canonical_json({
        key: value for key, value in manifest.items() if key != "manifest_sha256"
    })).hexdigest()
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.verify_snapshot(
            snapshot_dir, environment["authorization"], environment["auth_path"]
        )


def test_status_uses_verified_snapshot_metadata_without_provider(environment) -> None:
    _, manifest = _write_synthetic_snapshot(environment)

    status = collector.prospective_status()

    assert status["status"] == "PHASE7_COLLECTION_PENDING"
    assert status["latest_completed_session"] == "2026-09-29"
    assert status["latest_acquired_session"] == "2026-09-28"
    assert status["scored_session_count"] == 1
    assert status["next_checkpoint_sessions"] == 63
    assert status["sessions_remaining"] == 62
    assert status["snapshot_id"] == manifest["snapshot_id"]
    assert status["manifest_verification"] == "VERIFIED"


def test_output_path_outside_repository_is_rejected_before_provider(
    environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        collector, "_OUTPUT_DIR", environment["auth_path"].parent.parent / "elsewhere"
    )
    monkeypatch.setattr(
        collector, "acquire_prospective_phase7_data",
        lambda **kwargs: pytest.fail("outside output path reached provider"),
    )

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.collect_prospective_data()


def test_symlinked_output_directory_is_rejected_for_status(
    environment, tmp_path: Path
) -> None:
    output_dir = environment["output_dir"]
    target = tmp_path / "redirected-output"
    target.mkdir()
    output_dir.rmdir()
    try:
        output_dir.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.prospective_status()


def test_no_new_completed_session_is_idempotent_and_provider_free(
    environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot_dir, _ = _write_synthetic_snapshot(environment)
    original_manifest = (snapshot_dir / "manifest.json").read_bytes()
    monkeypatch.setattr(
        collector, "_utc_now",
        lambda: datetime.fromisoformat("2026-09-29T19:00:00+00:00"),
    )
    monkeypatch.setattr(
        collector, "acquire_prospective_phase7_data",
        lambda **kwargs: pytest.fail("provider path reached on a no-op"),
        raising=False,
    )

    first = collector.collect_prospective_data()
    second = collector.collect_prospective_data()

    assert first["status"] == second["status"] == "NO_NEW_COMPLETED_SESSION"
    assert first["latest_acquired_session"] == "2026-09-28"
    assert (snapshot_dir / "manifest.json").read_bytes() == original_manifest
    assert len(list((environment["output_dir"] / "snapshots").iterdir())) == 1


def test_invalid_authorization_stops_before_acquisition(
    environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment["auth_path"].write_text('{"invalid":true}', encoding="utf-8")
    monkeypatch.setattr(
        collector, "acquire_prospective_phase7_data",
        lambda **kwargs: pytest.fail("provider path reached before authorization"),
        raising=False,
    )

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.collect_prospective_data()


def test_symlinked_authorization_is_rejected_before_reading_target(
    environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth_path = environment["auth_path"]
    target = auth_path.parent / "other-authorization.json"
    target.write_bytes(auth_path.read_bytes())
    auth_path.unlink()
    try:
        auth_path.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    monkeypatch.setattr(
        collector,
        "verify_generation4_phase7_evaluation_authorization",
        lambda path: pytest.fail("symlinked authorization was read"),
    )

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.prospective_status()


def test_forbidden_symbol_cannot_be_injected_via_authorization(
    environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = json.loads(environment["auth_path"].read_text(encoding="utf-8"))
    payload["research_universe"][-1] = "QQQM"
    environment["auth_path"].write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        collector, "acquire_prospective_phase7_data",
        lambda **kwargs: pytest.fail("forbidden symbol reached provider path"),
    )

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.collect_prospective_data()


def test_new_completed_session_uses_frozen_request_and_appends_snapshot(
    environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_dir, _ = _write_synthetic_snapshot(environment)
    original_manifest = (first_dir / "manifest.json").read_bytes()
    called = []

    def fake_acquire(**kwargs):
        called.append(kwargs)
        request = kwargs["request"]
        assert kwargs["evaluation_authorization"] == environment["auth_path"]
        assert tuple(request["symbols"]) == UNIVERSE
        assert request["requested_start"] == WARMUP_START
        assert request["requested_end"] == "2026-09-29"
        assert request["scored_start"] == FIRST_SCORED
        assert request["warmup_session_count"] == 210
        assert request["scored_session_count"] == 2
        assert kwargs["output_dir"] != environment["output_dir"]
        stage_environment = {**environment, "output_dir": kwargs["output_dir"]}
        return _write_synthetic_snapshot(
            stage_environment, scored_count=2,
            retrieved_at_utc=kwargs["retrieved_at_utc"],
        )[1]

    monkeypatch.setattr(
        collector, "acquire_prospective_phase7_data", fake_acquire, raising=False
    )

    result = collector.collect_prospective_data()

    assert len(called) == 1
    assert result["status"] == "PHASE7_COLLECTION_UPDATED"
    assert result["latest_acquired_session"] == "2026-09-29"
    assert result["scored_session_count"] == 2
    assert (first_dir / "manifest.json").read_bytes() == original_manifest
    assert len(list((environment["output_dir"] / "snapshots").iterdir())) == 2


def test_failed_acquisition_preserves_prior_snapshot(
    environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_dir, _ = _write_synthetic_snapshot(environment)
    original_manifest = (first_dir / "manifest.json").read_bytes()

    def fail_after_partial_write(**kwargs):
        stage = kwargs["output_dir"] / "snapshots" / "partial"
        stage.mkdir(parents=True)
        (stage / "incomplete").write_text("synthetic", encoding="utf-8")
        raise RuntimeError("synthetic provider failure")

    monkeypatch.setattr(
        collector, "acquire_prospective_phase7_data",
        fail_after_partial_write, raising=False,
    )

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.collect_prospective_data()

    assert (first_dir / "manifest.json").read_bytes() == original_manifest
    assert len(list((environment["output_dir"] / "snapshots").iterdir())) == 1
    assert not list(environment["output_dir"].glob(".phase7-collector-*"))


def test_failed_new_snapshot_validation_does_not_publish_it(
    environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_dir, _ = _write_synthetic_snapshot(environment)
    original_manifest = (first_dir / "manifest.json").read_bytes()

    def acquire_corrupt_snapshot(**kwargs):
        stage_environment = {**environment, "output_dir": kwargs["output_dir"]}
        stage_dir, manifest = _write_synthetic_snapshot(
            stage_environment, scored_count=2,
            retrieved_at_utc=kwargs["retrieved_at_utc"],
        )
        with (stage_dir / "bars/unadjusted/SPY.csv").open("ab") as handle:
            handle.write(b"tampered")
        return manifest

    monkeypatch.setattr(
        collector, "acquire_prospective_phase7_data",
        acquire_corrupt_snapshot, raising=False,
    )

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.collect_prospective_data()

    assert (first_dir / "manifest.json").read_bytes() == original_manifest
    assert len(list((environment["output_dir"] / "snapshots").iterdir())) == 1
    assert not list(environment["output_dir"].glob(".phase7-collector-*"))


def test_existing_destination_is_never_overwritten(
    environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_synthetic_snapshot(environment)
    collision = {}

    def concurrent_destination(**kwargs):
        stage_environment = {**environment, "output_dir": kwargs["output_dir"]}
        stage_dir, manifest = _write_synthetic_snapshot(
            stage_environment, scored_count=2,
            retrieved_at_utc=kwargs["retrieved_at_utc"],
        )
        final = environment["output_dir"] / "snapshots" / stage_dir.name
        final.mkdir()
        (final / "sentinel").write_text("keep", encoding="utf-8")
        collision["path"] = final
        return manifest

    monkeypatch.setattr(
        collector, "acquire_prospective_phase7_data",
        concurrent_destination, raising=False,
    )

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.collect_prospective_data()

    assert (collision["path"] / "sentinel").read_text(encoding="utf-8") == "keep"


def test_snapshot_root_symlink_created_during_acquisition_is_rejected(
    environment, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()

    def redirect_destination(**kwargs):
        stage_environment = {**environment, "output_dir": kwargs["output_dir"]}
        _, manifest = _write_synthetic_snapshot(
            stage_environment, scored_count=2,
            retrieved_at_utc=kwargs["retrieved_at_utc"],
        )
        try:
            (environment["output_dir"] / "snapshots").symlink_to(
                outside, target_is_directory=True
            )
        except OSError:
            pytest.skip("directory symlink creation unavailable")
        return manifest

    monkeypatch.setattr(
        collector, "acquire_prospective_phase7_data", redirect_destination
    )

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.collect_prospective_data()

    assert not list(outside.iterdir())


def test_corrupt_prior_snapshot_stops_before_provider(
    environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_dir, _ = _write_synthetic_snapshot(environment)
    (first_dir / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        collector, "acquire_prospective_phase7_data",
        lambda **kwargs: pytest.fail("provider path reached after corrupt snapshot"),
        raising=False,
    )

    with pytest.raises(collector.Generation4Phase7CollectorError):
        collector.collect_prospective_data()
