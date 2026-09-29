from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from investment_tracker.quant.phase5.methodology import (
    SELECTED_BINDING_SHA256,
    SELECTED_CANDIDATE_ID,
    SELECTED_IMPLEMENTATION_SHA256,
)
from investment_tracker.quant.phase6.preseal import (
    HoldoutRelease,
    consume_released_bundle,
    validate_evaluation_contract_identity,
)


def _release(*, contract_sha: str, bundle_sha: str) -> HoldoutRelease:
    return HoldoutRelease.model_validate(
        {
            "schema_version": "PHASE6-HOLDOUT-RELEASE-v1",
            "authority": "INDEPENDENT_AUDIT",
            "status": "FINAL_HOLDOUT_RELEASE_AUTHORIZED",
            "release_id": "audit-release-bundle-test",
            "holdout_id": "holdout-bundle-test",
            "candidate_id": SELECTED_CANDIDATE_ID,
            "binding_sha256": SELECTED_BINDING_SHA256,
            "implementation_sha256": SELECTED_IMPLEMENTATION_SHA256,
            "evaluation_contract_sha256": contract_sha,
            "holdout_bundle_sha256": bundle_sha,
            "one_time": True,
        }
    )


def test_evaluation_contract_identity_is_verified_before_consumption(
    tmp_path: Path,
) -> None:
    contract = tmp_path / "contract.json"
    contract.write_bytes(b'{"contract":"sealed"}')
    bundle_sha = "b" * 64
    release = _release(
        contract_sha=sha256(contract.read_bytes()).hexdigest(),
        bundle_sha=bundle_sha,
    )

    validate_evaluation_contract_identity(release, contract)

    contract.write_bytes(b'{"contract":"mutated"}')
    with pytest.raises(ValueError, match="PHASE6_EVALUATION_CONTRACT_IDENTITY_MISMATCH"):
        validate_evaluation_contract_identity(release, contract)


def test_bundle_hash_is_checked_only_after_consumption_marker_exists(
    tmp_path: Path,
) -> None:
    contract = tmp_path / "contract.json"
    contract.write_bytes(b'{"contract":"sealed"}')
    bundle = tmp_path / "holdout.bin"
    bundle.write_bytes(b"sealed-holdout-fixture")
    release = _release(
        contract_sha=sha256(contract.read_bytes()).hexdigest(),
        bundle_sha=sha256(bundle.read_bytes()).hexdigest(),
    )
    marker_dir = tmp_path / "markers"

    payload = consume_released_bundle(
        release,
        evaluation_contract_path=contract,
        bundle_path=bundle,
        marker_directory=marker_dir,
    )

    assert payload == b"sealed-holdout-fixture"
    assert (marker_dir / f"{release.release_id}.consumed.json").is_file()


def test_bundle_identity_failure_still_consumes_the_release(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    contract.write_bytes(b'{"contract":"sealed"}')
    bundle = tmp_path / "holdout.bin"
    bundle.write_bytes(b"wrong-bundle")
    release = _release(
        contract_sha=sha256(contract.read_bytes()).hexdigest(),
        bundle_sha="b" * 64,
    )
    marker_dir = tmp_path / "markers"

    with pytest.raises(ValueError, match="PHASE6_HOLDOUT_BUNDLE_IDENTITY_MISMATCH"):
        consume_released_bundle(
            release,
            evaluation_contract_path=contract,
            bundle_path=bundle,
            marker_directory=marker_dir,
        )

    assert (marker_dir / f"{release.release_id}.consumed.json").is_file()
