from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_tracker.quant.phase4.preregistration.access import (
    Gate1AccessError,
    Gate1ReadCapability,
    Gate1SafetyStatus,
)
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
)
from investment_tracker.quant.phase4.preregistration.models import (
    Gate1ArtifactIdentity,
)


def _identity(path: str, payload: bytes = b"payload") -> Gate1ArtifactIdentity:
    content_sha256 = sha256(payload).hexdigest()
    envelope = {
        "content_sha256": content_sha256,
        "kind": "phase4_readiness_manifest",
        "path": path,
    }
    return Gate1ArtifactIdentity(
        **envelope,
        sha256=artifact_envelope_identity(**envelope),
    )


def test_unlisted_artifact_is_rejected_before_filesystem_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    allowed = _identity("results/phase4/readiness/allowed.json")
    capability = Gate1ReadCapability(repository, artifacts=(allowed,))
    unexpected = _identity("results/phase4/readiness/unexpected.json")
    calls = {"exists": 0, "read": 0}

    def counted_exists(_path: Path) -> bool:
        calls["exists"] += 1
        return False

    def counted_read(_path: Path) -> bytes:
        calls["read"] += 1
        return b""

    monkeypatch.setattr(Path, "exists", counted_exists)
    monkeypatch.setattr(Path, "read_bytes", counted_read)

    with pytest.raises(Gate1AccessError, match="not admitted"):
        capability.read_admitted_artifact(unexpected)
    assert calls == {"exists": 0, "read": 0}


@pytest.mark.parametrize(
    "path",
    (
        "data/cache/SPY.parquet",
        "results/phase4/validation/metrics.json",
        "results/FINAL_HOLDOUT/evidence.json",
        "results/HACK/evidence.json",
        "results/SOXX/evidence.json",
        "results/NLR/evidence.json",
        "results/URNM/evidence.json",
        "results/GEV/evidence.json",
    ),
)
def test_forbidden_artifact_cannot_be_admitted(
    tmp_path: Path, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    looked_up = False

    def counted_exists(_path: Path) -> bool:
        nonlocal looked_up
        looked_up = True
        return False

    monkeypatch.setattr(Path, "exists", counted_exists)
    with pytest.raises(Gate1AccessError, match="forbidden Gate 1 resource"):
        Gate1ReadCapability(repository, artifacts=(_identity(path),))
    assert looked_up is False


def test_admitted_artifact_is_hash_checked_and_recorded(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    artifact = repository / "results" / "phase4" / "readiness" / "manifest.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"payload")
    identity = _identity("results/phase4/readiness/manifest.json")
    capability = Gate1ReadCapability(repository, artifacts=(identity,))

    assert capability.read_admitted_artifact(identity) == b"payload"
    evidence = capability.evidence()
    assert evidence.observed_reads == (
        f"artifact:{identity.kind}:{identity.path}:{identity.content_sha256}",
    )
    assert evidence.safety == Gate1SafetyStatus()

    artifact.write_bytes(b"mutated")
    with pytest.raises(Gate1AccessError, match="content digest mismatch"):
        capability.read_admitted_artifact(identity)


def test_symlink_component_is_rejected_before_content_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    identity = _identity("results/phase4/readiness/link/manifest.json")
    capability = Gate1ReadCapability(repository, artifacts=(identity,))
    reads = 0

    def pretend_symlink(path: Path) -> bool:
        return path.name == "link"

    def counted_read(_path: Path) -> bytes:
        nonlocal reads
        reads += 1
        return b"payload"

    monkeypatch.setattr(Path, "is_symlink", pretend_symlink)
    monkeypatch.setattr(Path, "read_bytes", counted_read)

    with pytest.raises(Gate1AccessError, match="symlink"):
        capability.read_admitted_artifact(identity)
    assert reads == 0


def test_safety_status_fails_closed_for_any_nonempty_flag() -> None:
    invalid_values = (
        {"validation_data_access": True},
        {"validation_metrics_access": True},
        {"campaign_results_access": True},
        {"final_holdout_accessed": True},
        {"protected_symbols_accessed": ("HACK",)},
        {"provider_calls": 1},
        {"strategy_search_executed": True},
        {"live_trading_capability": True},
    )
    for values in invalid_values:
        with pytest.raises(ValidationError):
            Gate1SafetyStatus(**values)


def test_observed_read_evidence_is_sorted_unique(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    paths = (
        "results/phase4/readiness/z.json",
        "results/phase4/readiness/a.json",
    )
    identities = tuple(_identity(path) for path in paths)
    for path in paths:
        destination = repository.joinpath(*path.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"payload")
    capability = Gate1ReadCapability(repository, artifacts=identities)

    capability.read_admitted_artifact(identities[0])
    capability.read_admitted_artifact(identities[1])
    capability.read_admitted_artifact(identities[0])

    assert capability.evidence().observed_reads == tuple(
        sorted(
            {
                f"artifact:{item.kind}:{item.path}:{item.content_sha256}"
                for item in identities
            }
        )
    )
