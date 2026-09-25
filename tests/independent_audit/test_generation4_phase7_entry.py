from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from investment_tracker.independent_audit.post_generation3.phase7_entry import (
    GEN4_PHASE7_CHAIN_MISMATCH,
    GEN4_PHASE7_EVIDENCE_INVALID,
    GEN4_PHASE7_GOVERNANCE_MISMATCH,
    GEN4_PHASE7_IDENTITY_MISMATCH,
    Generation4Phase7EntryError,
    verify_generation4_phase7_readiness,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/generation4/phase6/evaluation-contract.json"
ACQUISITION_AUTHORIZATION = (
    ROOT / "data/governance/successor/generation4-acquisition-authorization.json"
)
SELECTION = ROOT / "data/generation4/preaccess/holdout-selection.json"
ATTESTATION = ROOT / "data/generation4/preaccess/virginity-attestation.json"
EVIDENCE = ROOT / "data/generation4/preaccess/virginity-evidence.json"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(value: dict[str, object]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _write(path: Path, value: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))
    return path


def _valid_chain(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "contract": tmp_path / "evaluation-contract.json",
        "acquisition_authorization": tmp_path / "acquisition-authorization.json",
        "selection": tmp_path / "holdout-selection.json",
        "virginity_attestation": tmp_path / "virginity-attestation.json",
        "virginity_evidence": tmp_path / "virginity-evidence.json",
        "receipt": tmp_path / "acquisition-receipt.json",
        "release": tmp_path / "release.json",
        "result": tmp_path / "result.json",
        "marker": tmp_path / "consumed.json",
        "closure": tmp_path / "closure.json",
    }
    for source, name in (
        (CONTRACT, "contract"),
        (ACQUISITION_AUTHORIZATION, "acquisition_authorization"),
        (SELECTION, "selection"),
        (ATTESTATION, "virginity_attestation"),
        (EVIDENCE, "virginity_evidence"),
    ):
        shutil.copyfile(source, paths[name])

    contract = json.loads(paths["contract"].read_text(encoding="utf-8"))
    authorization = json.loads(
        paths["acquisition_authorization"].read_text(encoding="utf-8")
    )
    strategy = contract["strategy"]
    methodology = contract["methodology"]
    symbols = contract["final_holdout"]["locked_symbols"]
    holdout_id = "successor-phase6-holdout-synthetic"

    receipt = {
        "schema_version": "SUCCESSOR-PHASE6-HOLDOUT-ACQUISITION-RECEIPT-v1",
        "authority": "INDEPENDENT_AUDIT",
        "status": "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED",
        "successor_formal_name": contract["successor_formal_name"],
        "phase6_contract_sha256": _sha(paths["contract"]),
        "acquisition_authorization_sha256": _sha(
            paths["acquisition_authorization"]
        ),
        "candidate_id": strategy["candidate_id"],
        "binding_sha256": strategy["binding_sha256"],
        "implementation_sha256": strategy["implementation_sha256"],
        "successor_normalizer_sha256": methodology["split_normalizer_sha256"],
        "successor_evaluator_sha256": methodology["successor_evaluator_sha256"],
        "protected_symbols_accessed": symbols,
        "holdout_id": holdout_id,
        "bundle_sha256": "1" * 64,
        "plaintext_bundle_sha256": "2" * 64,
        "bundle_manifest_sha256": "3" * 64,
        "key_sha256": "4" * 64,
        "final_holdout_accessed": True,
        "performance_computed": False,
        "performance_inspected": False,
        "retry_allowed": False,
        "artifact_readback_verified": True,
    }
    receipt["receipt_sha256"] = sha256(_canonical(receipt)).hexdigest()
    _write(paths["receipt"], receipt)

    release_seed = {
        "holdout_id": holdout_id,
        "candidate_id": strategy["candidate_id"],
        "contract_sha256": _sha(paths["contract"]),
        "bundle_sha256": receipt["bundle_sha256"],
        "receipt_sha256": _sha(paths["receipt"]),
    }
    release_id = (
        "successor-phase6-release-"
        + sha256(_canonical(release_seed)).hexdigest()[:32]
    )
    release = {
        "schema_version": "SUCCESSOR-PHASE6-HOLDOUT-RELEASE-v1",
        "authority": "INDEPENDENT_AUDIT",
        "status": "FINAL_HOLDOUT_RELEASE_AUTHORIZED",
        "release_id": release_id,
        "successor_formal_name": contract["successor_formal_name"],
        "holdout_id": holdout_id,
        "candidate_id": strategy["candidate_id"],
        "binding_sha256": strategy["binding_sha256"],
        "implementation_sha256": strategy["implementation_sha256"],
        "successor_normalizer_sha256": methodology["split_normalizer_sha256"],
        "successor_evaluator_sha256": methodology["successor_evaluator_sha256"],
        "phase6_contract_sha256": _sha(paths["contract"]),
        "holdout_bundle_sha256": receipt["bundle_sha256"],
        "holdout_key_sha256": receipt["key_sha256"],
        "acquisition_receipt_file_sha256": _sha(paths["receipt"]),
        "locked_symbols": symbols,
        "one_time": True,
        "performance_inspected_before_release": False,
        "one_time_evaluation_authorized": True,
        "phase7_authorized": False,
        "production_readiness_approved": False,
        "recon009_status": "OPEN",
    }
    _write(paths["release"], release)

    result = {
        "schema_version": "SUCCESSOR-PHASE6-FINAL-HOLDOUT-EVALUATION-v2",
        "authority": "COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE",
        "status": "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE",
        "successor_formal_name": contract["successor_formal_name"],
        "phase6_contract_sha256": _sha(paths["contract"]),
        "release_id": release_id,
        "holdout_id": holdout_id,
        "candidate_id": strategy["candidate_id"],
        "binding_sha256": strategy["binding_sha256"],
        "implementation_sha256": strategy["implementation_sha256"],
        "successor_normalizer_sha256": methodology["split_normalizer_sha256"],
        "successor_evaluator_sha256": methodology["successor_evaluator_sha256"],
        "locked_symbols": symbols,
        "metrics": {"ignored_for_authorization": 1.0},
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "holdout_symbol_substitution_executed": False,
        "one_time_consumed": True,
        "phase7_authorized": False,
        "phase7_started": False,
        "production_readiness_approved": False,
        "recon009_status": "OPEN",
    }
    _write(paths["result"], result)

    marker = {
        "schema_version": "SUCCESSOR-PHASE6-HOLDOUT-CONSUMPTION-v1",
        "status": "FINAL_HOLDOUT_RELEASE_CONSUMED",
        "release_id": release_id,
        "holdout_id": holdout_id,
        "candidate_id": strategy["candidate_id"],
        "phase6_contract_sha256": _sha(paths["contract"]),
        "holdout_bundle_sha256": receipt["bundle_sha256"],
        "retry_allowed": False,
        "evaluation_status": result["status"],
        "evaluation_result_sha256": _sha(paths["result"]),
        "result_readback_verified": True,
    }
    _write(paths["marker"], marker)

    closure = {
        "schema_version": "SUCCESSOR-PHASE6-FINAL-HOLDOUT-CLOSURE-v1",
        "authority": "COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE",
        "status": result["status"],
        "successor_formal_name": contract["successor_formal_name"],
        "candidate_id": strategy["candidate_id"],
        "binding_sha256": strategy["binding_sha256"],
        "implementation_sha256": strategy["implementation_sha256"],
        "successor_normalizer_sha256": methodology["split_normalizer_sha256"],
        "successor_evaluator_sha256": methodology["successor_evaluator_sha256"],
        "locked_symbols": symbols,
        "holdout_id": holdout_id,
        "release_id": release_id,
        "phase6_contract_sha256": _sha(paths["contract"]),
        "acquisition_receipt_sha256": _sha(paths["receipt"]),
        "release_sha256": _sha(paths["release"]),
        "evaluation_result_sha256": _sha(paths["result"]),
        "evaluation_consumption_marker_sha256": _sha(paths["marker"]),
        "one_time_semantics": {
            "holdout_consumed": True,
            "retry_authorized": False,
            "symbol_substitution_authorized": False,
            "methodology_change_from_holdout_forbidden": True,
            "parameter_change_from_holdout_forbidden": True,
        },
        "phase7": {
            "eligible_for_independent_entry_review": True,
            "authorized": False,
            "entry_artifact_created": False,
            "started": False,
        },
        "production_readiness_approved": False,
        "recon009_status": "OPEN",
    }
    _write(paths["closure"], closure)
    assert authorization["paper_only"] is True
    return paths


def _readiness(paths: dict[str, Path]) -> dict[str, object]:
    return verify_generation4_phase7_readiness(
        phase6_contract_path=paths["contract"],
        acquisition_authorization_path=paths["acquisition_authorization"],
        selection_path=paths["selection"],
        virginity_attestation_path=paths["virginity_attestation"],
        virginity_evidence_path=paths["virginity_evidence"],
        acquisition_receipt_path=paths["receipt"],
        release_path=paths["release"],
        phase6_result_path=paths["result"],
        consumption_marker_path=paths["marker"],
        phase6_closure_path=paths["closure"],
    )


def test_readiness_accepts_upstream_paper_only_without_downstream_field(
    tmp_path: Path,
):
    paths = _valid_chain(tmp_path)
    report = _readiness(paths)
    assert report["status"] == "GENERATION4_PHASE7_READY_FOR_INDEPENDENT_AUDIT"
    assert report["paper_only"] is True
    for name in ("receipt", "release", "result", "marker", "closure"):
        assert "paper_only" not in json.loads(
            paths[name].read_text(encoding="utf-8")
        )


def test_readiness_accepts_dividend_binding_without_downstream_field(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    report = _readiness(paths)
    contract = json.loads(paths["contract"].read_text(encoding="utf-8"))
    assert (
        report["dividend_reconciliation_sha256"]
        == contract["methodology"]["dividend_reconciliation_sha256"]
    )
    for name in ("receipt", "release", "result"):
        assert "dividend_reconciliation_sha256" not in json.loads(
            paths[name].read_text(encoding="utf-8")
        )


def test_readiness_reports_validated_acquisition_authorization_hash(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    report = _readiness(paths)
    assert report["acquisition_authorization_sha256"] == _sha(
        paths["acquisition_authorization"]
    )


def test_readiness_rejects_dividend_contract_authorization_mismatch(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    contract = json.loads(paths["contract"].read_text(encoding="utf-8"))
    contract["methodology"]["dividend_reconciliation_sha256"] = "0" * 64
    _write(paths["contract"], contract)
    with pytest.raises(Generation4Phase7EntryError) as excinfo:
        _readiness(paths)
    assert excinfo.value.code == GEN4_PHASE7_IDENTITY_MISMATCH


def _mutate(paths: dict[str, Path], name: str, mutation) -> None:
    value = json.loads(paths[name].read_text(encoding="utf-8"))
    mutation(value)
    _write(paths[name], value)


def _expect_readiness_error(
    paths: dict[str, Path], expected: str | tuple[str, ...]
) -> None:
    with pytest.raises(Generation4Phase7EntryError) as excinfo:
        _readiness(paths)
    expected_codes = (expected,) if isinstance(expected, str) else expected
    assert excinfo.value.code in expected_codes


@pytest.mark.parametrize(
    "status", [None, "PHASE6_UNKNOWN_ABSTAIN", "PHASE6_COMPLETE"]
)
def test_readiness_rejects_wrong_phase6_status(tmp_path: Path, status: object):
    paths = _valid_chain(tmp_path)
    _mutate(paths, "result", lambda value: value.__setitem__("status", status))
    _expect_readiness_error(paths, GEN4_PHASE7_GOVERNANCE_MISMATCH)


def test_readiness_rejects_unconsumed_result(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    _mutate(
        paths, "result", lambda value: value.__setitem__("one_time_consumed", False)
    )
    _expect_readiness_error(paths, GEN4_PHASE7_GOVERNANCE_MISMATCH)


@pytest.mark.parametrize("artifact", ["result", "closure"])
def test_readiness_rejects_started_state(tmp_path: Path, artifact: str):
    paths = _valid_chain(tmp_path)
    if artifact == "result":
        _mutate(
            paths, artifact, lambda value: value.__setitem__("phase7_started", True)
        )
    else:
        _mutate(
            paths,
            artifact,
            lambda value: value["phase7"].__setitem__("started", True),
        )
    _expect_readiness_error(paths, GEN4_PHASE7_GOVERNANCE_MISMATCH)


@pytest.mark.parametrize(
    ("artifact", "mutation"),
    [
        (
            "contract",
            lambda value: value["governance"].__setitem__(
                "production_readiness_approved", True
            ),
        ),
        (
            "acquisition_authorization",
            lambda value: value.__setitem__("production_readiness_approved", True),
        ),
        (
            "release",
            lambda value: value.__setitem__("production_readiness_approved", True),
        ),
        (
            "result",
            lambda value: value.__setitem__("production_readiness_approved", True),
        ),
        (
            "closure",
            lambda value: value.__setitem__("production_readiness_approved", True),
        ),
    ],
)
def test_readiness_rejects_production_approval(
    tmp_path: Path, artifact: str, mutation
):
    paths = _valid_chain(tmp_path)
    _mutate(paths, artifact, mutation)
    _expect_readiness_error(
        paths,
        (
            GEN4_PHASE7_GOVERNANCE_MISMATCH,
            GEN4_PHASE7_IDENTITY_MISMATCH,
        ),
    )


def test_readiness_rejects_ineligible_closure(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    _mutate(
        paths,
        "closure",
        lambda value: value["phase7"].__setitem__(
            "eligible_for_independent_entry_review", False
        ),
    )
    _expect_readiness_error(paths, GEN4_PHASE7_GOVERNANCE_MISMATCH)


@pytest.mark.parametrize(
    ("artifact", "mutation"),
    [
        (
            "contract",
            lambda value: value["governance"].__setitem__("phase7_authorized", True),
        ),
        (
            "acquisition_authorization",
            lambda value: value.__setitem__("phase7_authorized", True),
        ),
        ("release", lambda value: value.__setitem__("phase7_authorized", True)),
        ("result", lambda value: value.__setitem__("phase7_authorized", True)),
        (
            "closure",
            lambda value: value["phase7"].__setitem__("authorized", True),
        ),
    ],
)
def test_readiness_rejects_preexisting_phase7_authority(
    tmp_path: Path, artifact: str, mutation
):
    paths = _valid_chain(tmp_path)
    _mutate(paths, artifact, mutation)
    _expect_readiness_error(
        paths,
        (
            GEN4_PHASE7_GOVERNANCE_MISMATCH,
            GEN4_PHASE7_IDENTITY_MISMATCH,
        ),
    )


@pytest.mark.parametrize("artifact", ["contract", "receipt", "release", "result", "closure"])
@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("candidate_id", "G2-A|lookback=190|skip=21|top_k=1|rebalance=21"),
        ("binding_sha256", "a" * 64),
        ("implementation_sha256", "b" * 64),
    ],
)
def test_readiness_rejects_strategy_identity_drift(
    tmp_path: Path, artifact: str, field: str, replacement: str
):
    paths = _valid_chain(tmp_path)
    if artifact == "contract":
        _mutate(
            paths,
            artifact,
            lambda value: value["strategy"].__setitem__(field, replacement),
        )
    else:
        _mutate(paths, artifact, lambda value: value.__setitem__(field, replacement))
    _expect_readiness_error(paths, GEN4_PHASE7_IDENTITY_MISMATCH)


@pytest.mark.parametrize("mutation", ["replace", "swap"])
def test_readiness_rejects_locked_symbol_drift(tmp_path: Path, mutation: str):
    paths = _valid_chain(tmp_path)

    def change(value: dict[str, object]) -> None:
        symbols = list(value["locked_symbols"])
        if mutation == "replace":
            symbols[0] = "SPY"
        else:
            symbols[0], symbols[1] = symbols[1], symbols[0]
        value["locked_symbols"] = symbols

    _mutate(paths, "result", change)
    _expect_readiness_error(paths, GEN4_PHASE7_IDENTITY_MISMATCH)


@pytest.mark.parametrize("artifact", ["receipt", "release", "result", "marker"])
def test_readiness_rejects_hash_chain_tamper(tmp_path: Path, artifact: str):
    paths = _valid_chain(tmp_path)
    value = json.loads(paths[artifact].read_text(encoding="utf-8"))
    paths[artifact].write_text(
        json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _expect_readiness_error(paths, GEN4_PHASE7_CHAIN_MISMATCH)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda value: value.__setitem__("schema_version", "WRONG"),
            GEN4_PHASE7_EVIDENCE_INVALID,
        ),
        (
            lambda value: value.__setitem__("candidate_id", "WRONG"),
            GEN4_PHASE7_IDENTITY_MISMATCH,
        ),
        (
            lambda value: value["phase7"].__setitem__("started", True),
            GEN4_PHASE7_GOVERNANCE_MISMATCH,
        ),
        (
            lambda value: value.__setitem__("release_sha256", "0" * 64),
            GEN4_PHASE7_CHAIN_MISMATCH,
        ),
    ],
)
def test_readiness_rejects_closure_semantic_mutation(
    tmp_path: Path, mutation, expected: str
):
    paths = _valid_chain(tmp_path)
    _mutate(paths, "closure", mutation)
    _expect_readiness_error(paths, expected)


def test_readiness_reports_semantically_equivalent_closure_bytes(tmp_path: Path):
    paths = _valid_chain(tmp_path)
    original = _sha(paths["closure"])
    closure = json.loads(paths["closure"].read_text(encoding="utf-8"))
    paths["closure"].write_text(
        json.dumps(closure, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report = _readiness(paths)
    assert report["phase6_closure_sha256"] == _sha(paths["closure"])
    assert report["phase6_closure_sha256"] != original


@pytest.mark.parametrize(
    ("artifact", "mutation"),
    [
        (
            "contract",
            lambda value: value["governance"].__setitem__(
                "retry_after_historical_access_allowed", True
            ),
        ),
        (
            "acquisition_authorization",
            lambda value: value.__setitem__(
                "retry_after_historical_access_allowed", True
            ),
        ),
        ("receipt", lambda value: value.__setitem__("retry_allowed", True)),
        ("marker", lambda value: value.__setitem__("retry_allowed", True)),
        (
            "closure",
            lambda value: value["one_time_semantics"].__setitem__(
                "retry_authorized", True
            ),
        ),
    ],
)
def test_readiness_rejects_retry_authority(
    tmp_path: Path, artifact: str, mutation
):
    paths = _valid_chain(tmp_path)
    _mutate(paths, artifact, mutation)
    _expect_readiness_error(
        paths,
        (GEN4_PHASE7_GOVERNANCE_MISMATCH, GEN4_PHASE7_IDENTITY_MISMATCH),
    )


@pytest.mark.parametrize(
    ("artifact", "mutation"),
    [
        (
            "contract",
            lambda value: value["governance"].__setitem__(
                "symbol_substitution_after_access_allowed", True
            ),
        ),
        (
            "acquisition_authorization",
            lambda value: value.__setitem__(
                "symbol_substitution_after_access_allowed", True
            ),
        ),
        (
            "result",
            lambda value: value.__setitem__(
                "holdout_symbol_substitution_executed", True
            ),
        ),
        (
            "closure",
            lambda value: value["one_time_semantics"].__setitem__(
                "symbol_substitution_authorized", True
            ),
        ),
    ],
)
def test_readiness_rejects_symbol_substitution(
    tmp_path: Path, artifact: str, mutation
):
    paths = _valid_chain(tmp_path)
    _mutate(paths, artifact, mutation)
    _expect_readiness_error(
        paths,
        (GEN4_PHASE7_GOVERNANCE_MISMATCH, GEN4_PHASE7_IDENTITY_MISMATCH),
    )


@pytest.mark.parametrize(
    ("artifact", "mutation"),
    [
        (
            "result",
            lambda value: value.__setitem__("candidate_search_executed", True),
        ),
        (
            "result",
            lambda value: value.__setitem__("candidate_parameters_changed", True),
        ),
        (
            "closure",
            lambda value: value["one_time_semantics"].__setitem__(
                "methodology_change_from_holdout_forbidden", False
            ),
        ),
        (
            "closure",
            lambda value: value["one_time_semantics"].__setitem__(
                "parameter_change_from_holdout_forbidden", False
            ),
        ),
    ],
)
def test_readiness_rejects_result_dependent_change_authority(
    tmp_path: Path, artifact: str, mutation
):
    paths = _valid_chain(tmp_path)
    _mutate(paths, artifact, mutation)
    _expect_readiness_error(paths, GEN4_PHASE7_GOVERNANCE_MISMATCH)


@pytest.mark.parametrize(
    ("artifact", "mutation"),
    [
        (
            "contract",
            lambda value: value["governance"].__setitem__(
                "recon009_status", "CLOSED"
            ),
        ),
        (
            "acquisition_authorization",
            lambda value: value.__setitem__("recon009_status", "CLOSED"),
        ),
        ("release", lambda value: value.__setitem__("recon009_status", "CLOSED")),
        ("result", lambda value: value.__setitem__("recon009_status", "CLOSED")),
        ("closure", lambda value: value.__setitem__("recon009_status", "CLOSED")),
    ],
)
def test_readiness_rejects_recon009_change(
    tmp_path: Path, artifact: str, mutation
):
    paths = _valid_chain(tmp_path)
    _mutate(paths, artifact, mutation)
    _expect_readiness_error(
        paths,
        (GEN4_PHASE7_GOVERNANCE_MISMATCH, GEN4_PHASE7_IDENTITY_MISMATCH),
    )


@pytest.mark.parametrize("artifact", ["contract", "acquisition_authorization"])
def test_readiness_rejects_upstream_paper_only_change(
    tmp_path: Path, artifact: str
):
    paths = _valid_chain(tmp_path)
    if artifact == "contract":
        _mutate(
            paths,
            artifact,
            lambda value: value["governance"].__setitem__("paper_only", False),
        )
    else:
        _mutate(paths, artifact, lambda value: value.__setitem__("paper_only", False))
    _expect_readiness_error(
        paths,
        (GEN4_PHASE7_GOVERNANCE_MISMATCH, GEN4_PHASE7_IDENTITY_MISMATCH),
    )
