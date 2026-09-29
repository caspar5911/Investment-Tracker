from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from investment_tracker.independent_audit.post_generation3 import (
    phase7_entry as phase7_entry_module,
    phase7_entry_cli,
    phase7_start as phase7_start_module,
    phase7_start_cli,
)
from investment_tracker.independent_audit.post_generation3.phase7_start import (
    GEN4_PHASE7_ALREADY_STARTED,
    GEN4_PHASE7_START_BINDING_MISMATCH,
    GEN4_PHASE7_START_CONTRACT_INVALID,
    GEN4_PHASE7_START_CONTRACT_MISSING,
    GEN4_PHASE7_START_ENTRY_INVALID,
    GEN4_PHASE7_START_GOVERNANCE_MISMATCH,
    Generation4Phase7StartContract,
    Generation4Phase7StartError,
    load_generation4_phase7_start_contract,
    start_generation4_phase7,
    verify_generation4_phase7_start_readiness,
)
from tests.independent_audit.test_generation4_phase7_entry import (
    _audit_request,
    _authorization,
    _entry,
    _readiness,
    _valid_chain,
    _write,
)


EXPECTED_SYMBOLS = ["QQQM", "FALN", "IIPR", "PSTL", "EFAS"]
ROOT = Path(__file__).resolve().parents[2]
COMMITTED_START_CONTRACT = (
    ROOT / "data/governance/successor/generation4-phase7-start-contract.json"
)
COMMITTED_START_ARTIFACT = (
    ROOT / "data/governance/successor/generation4-phase7-start.json"
)
EVIDENCE_HASH_FIELDS = (
    "phase6_contract_sha256",
    "acquisition_authorization_sha256",
    "acquisition_receipt_sha256",
    "release_sha256",
    "evaluation_result_sha256",
    "evaluation_consumption_marker_sha256",
    "phase6_closure_sha256",
)
IDENTITY_FIELDS = (
    "candidate_id",
    "binding_sha256",
    "implementation_sha256",
    "split_normalizer_sha256",
    "dividend_reconciliation_sha256",
    "successor_evaluator_sha256",
)


def _valid_start_inputs(tmp_path: Path) -> tuple[dict[str, Path], dict[str, object]]:
    paths = _valid_chain(tmp_path)
    readiness = _readiness(paths)
    request_path = _audit_request(tmp_path, readiness)
    authorization_path = _authorization(tmp_path, readiness, request_path)
    entry = _entry(paths, request_path, authorization_path)
    paths.update(
        {
            "audit_request": request_path,
            "authorization": authorization_path,
            "phase7_entry": Path(phase7_entry_module.__file__),
            "phase7_entry_cli": tmp_path / "phase7_entry_cli.py",
        }
    )
    return paths, entry


def _start_kwargs(paths: dict[str, Path]) -> dict[str, Path]:
    return {
        "audit_request_path": paths["audit_request"],
        "authorization_path": paths["authorization"],
        "phase6_contract_path": paths["contract"],
        "acquisition_authorization_path": paths["acquisition_authorization"],
        "selection_path": paths["selection"],
        "virginity_attestation_path": paths["virginity_attestation"],
        "virginity_evidence_path": paths["virginity_evidence"],
        "acquisition_receipt_path": paths["receipt"],
        "release_path": paths["release"],
        "phase6_result_path": paths["result"],
        "consumption_marker_path": paths["marker"],
        "phase6_closure_path": paths["closure"],
        "phase7_entry_path": paths["phase7_entry"],
        "phase7_entry_cli_path": paths["phase7_entry_cli"],
    }


def _replace_entry(monkeypatch: pytest.MonkeyPatch, entry: dict[str, object]) -> None:
    monkeypatch.setattr(
        phase7_start_module,
        "evaluate_generation4_phase7_entry",
        lambda **_: entry.copy(),
    )


def _mutate_json(path: Path, field: str, value: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    _write(path, payload)


def _expect_start_error(
    paths: dict[str, Path], code: str
) -> pytest.ExceptionInfo[Generation4Phase7StartError]:
    with pytest.raises(Generation4Phase7StartError) as excinfo:
        verify_generation4_phase7_start_readiness(**_start_kwargs(paths))
    assert excinfo.value.code == code
    return excinfo


def test_valid_synthetic_entry_chain_is_ready_without_metrics(tmp_path: Path):
    paths, _ = _valid_start_inputs(tmp_path)

    report = verify_generation4_phase7_start_readiness(**_start_kwargs(paths))

    assert report["schema_version"] == "GENERATION4-PHASE7-START-READINESS-v1"
    assert report["status"] == "GENERATION4_PHASE7_START_READY"
    assert report["candidate_id"] == (
        "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
    )
    assert report["locked_symbols"] == EXPECTED_SYMBOLS
    assert report["phase7_entry_authorized"] is True
    assert report["phase7_started"] is False
    assert report["phase7_performance_evaluation_authorized"] is False
    assert report["production_readiness_approved"] is False
    assert report["live_trading_authorized"] is False
    assert report["recon009_status"] == "OPEN"
    assert report["paper_only"] is True
    assert "metrics" not in report


def test_missing_authorization_fails_closed(tmp_path: Path):
    paths, _ = _valid_start_inputs(tmp_path)
    paths["authorization"].unlink()

    _expect_start_error(paths, GEN4_PHASE7_START_ENTRY_INVALID)


def test_invalid_authorization_fails_closed(tmp_path: Path):
    paths, _ = _valid_start_inputs(tmp_path)
    _mutate_json(paths["authorization"], "unexpected", True)

    _expect_start_error(paths, GEN4_PHASE7_START_ENTRY_INVALID)


def test_wrong_authorization_id_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    paths, entry = _valid_start_inputs(tmp_path)
    entry["authorization_id"] = "DIFFERENT-AUTHORIZATION"
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_BINDING_MISMATCH)


def test_audit_request_hash_mismatch_fails_closed(tmp_path: Path):
    paths, _ = _valid_start_inputs(tmp_path)
    request = json.loads(paths["audit_request"].read_text(encoding="utf-8"))
    request["authority"] = "INDEPENDENT_AUDIT"
    _write(paths["audit_request"], request)

    _expect_start_error(paths, GEN4_PHASE7_START_ENTRY_INVALID)


@pytest.mark.parametrize("field", IDENTITY_FIELDS)
def test_identity_drift_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
):
    paths, entry = _valid_start_inputs(tmp_path)
    entry[field] = "f" * 64 if field != "candidate_id" else "DIFFERENT-CANDIDATE"
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_BINDING_MISMATCH)


def test_locked_symbol_order_drift_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    paths, entry = _valid_start_inputs(tmp_path)
    _mutate_json(paths["authorization"], "locked_symbols", list(reversed(EXPECTED_SYMBOLS)))
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_BINDING_MISMATCH)


@pytest.mark.parametrize("field", EVIDENCE_HASH_FIELDS)
def test_each_evidence_hash_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
):
    paths, entry = _valid_start_inputs(tmp_path)
    entry[field] = "f" * 64
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_BINDING_MISMATCH)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("production_readiness_approved", True),
        ("live_trading_authorized", True),
        ("recon009_status", "CLOSED"),
        ("paper_only", False),
    ),
)
def test_entry_governance_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
):
    paths, entry = _valid_start_inputs(tmp_path)
    entry[field] = value
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_GOVERNANCE_MISMATCH)


@pytest.mark.parametrize(
    "field",
    (
        "retry_authorized",
        "holdout_reuse_authorized",
        "candidate_search_authorized",
        "symbol_substitution_authorized",
        "result_dependent_methodology_change_allowed",
        "result_dependent_parameter_change_allowed",
    ),
)
def test_forbidden_authority_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
):
    paths, entry = _valid_start_inputs(tmp_path)
    _mutate_json(paths["authorization"], field, True)
    _replace_entry(monkeypatch, entry)

    _expect_start_error(paths, GEN4_PHASE7_START_ENTRY_INVALID)


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _contract_fixture(
    tmp_path: Path,
) -> tuple[dict[str, Path], dict[str, object], dict[str, object]]:
    paths, _ = _valid_start_inputs(tmp_path)
    readiness = verify_generation4_phase7_start_readiness(**_start_kwargs(paths))
    paths["phase7_start"] = Path(phase7_start_module.__file__)
    paths["phase7_start_cli"] = tmp_path / "phase7_start_cli.py"
    paths["phase7_start_cli"].write_text(
        "# synthetic start CLI identity\n", encoding="utf-8"
    )
    contract = {
        "schema_version": "GENERATION4-PHASE7-START-CONTRACT-v1",
        "status": "FROZEN_PRE_START",
        "authority": "COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION",
        "generation": "GENERATION_4",
        "candidate_id": readiness["candidate_id"],
        "binding_sha256": readiness["binding_sha256"],
        "implementation_sha256": readiness["implementation_sha256"],
        "split_normalizer_sha256": readiness["split_normalizer_sha256"],
        "dividend_reconciliation_sha256": readiness[
            "dividend_reconciliation_sha256"
        ],
        "successor_evaluator_sha256": readiness["successor_evaluator_sha256"],
        "locked_symbols": readiness["locked_symbols"],
        "holdout_id": readiness["holdout_id"],
        "release_id": readiness["release_id"],
        "authorization_id": readiness["authorization_id"],
        "entry_authorization_sha256": readiness["entry_authorization_sha256"],
        "audit_request_sha256": readiness["audit_request_sha256"],
        "phase6_status": readiness["phase6_status"],
        "one_time_consumed": True,
        "phase7_entry_implementation_commit": readiness[
            "phase7_entry_implementation_commit"
        ],
        "phase7_entry_source_sha256": _file_sha(paths["phase7_entry"]),
        "phase7_entry_cli_source_sha256": _file_sha(paths["phase7_entry_cli"]),
        "phase7_start_implementation_commit": "2" * 40,
        "phase7_start_source_sha256": _file_sha(paths["phase7_start"]),
        "phase7_start_cli_source_sha256": _file_sha(paths["phase7_start_cli"]),
        "phase7_entry_authorized": True,
        "phase7_started": False,
        "phase7_performance_evaluation_authorized": False,
        "production_readiness_approved": False,
        "live_trading_authorized": False,
        "retry_authorized": False,
        "holdout_reuse_authorized": False,
        "candidate_search_authorized": False,
        "parameter_mutation_authorized": False,
        "symbol_substitution_authorized": False,
        "result_dependent_methodology_change_allowed": False,
        "result_dependent_parameter_change_allowed": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }
    contract.update(
        {field: readiness[field] for field in EVIDENCE_HASH_FIELDS}
    )
    paths["start_contract"] = _write(tmp_path / "start-contract.json", contract)
    return paths, readiness, contract


def _load_contract(
    paths: dict[str, Path], readiness: dict[str, object]
) -> Generation4Phase7StartContract:
    return load_generation4_phase7_start_contract(
        contract_path=paths["start_contract"],
        readiness=readiness,
        authorization_path=paths["authorization"],
        audit_request_path=paths["audit_request"],
        phase7_entry_path=paths["phase7_entry"],
        phase7_entry_cli_path=paths["phase7_entry_cli"],
        phase7_start_path=paths["phase7_start"],
        phase7_start_cli_path=paths["phase7_start_cli"],
    )


def _expect_contract_error(
    paths: dict[str, Path], readiness: dict[str, object], code: str
) -> pytest.ExceptionInfo[Generation4Phase7StartError]:
    with pytest.raises(Generation4Phase7StartError) as excinfo:
        _load_contract(paths, readiness)
    assert excinfo.value.code == code
    return excinfo


def test_valid_strict_start_contract_loads(tmp_path: Path):
    paths, readiness, _ = _contract_fixture(tmp_path)

    contract = _load_contract(paths, readiness)

    assert contract.schema_version == "GENERATION4-PHASE7-START-CONTRACT-v1"
    assert contract.status == "FROZEN_PRE_START"
    assert contract.phase7_started is False
    assert contract.phase7_performance_evaluation_authorized is False


def test_missing_start_contract_fails_closed(tmp_path: Path):
    paths, readiness, _ = _contract_fixture(tmp_path)
    paths["start_contract"].unlink()

    _expect_contract_error(paths, readiness, GEN4_PHASE7_START_CONTRACT_MISSING)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("schema_version", "GENERATION4-PHASE7-START-CONTRACT-v2"),
        ("status", "STARTED"),
        ("authority", "INDEPENDENT_AUDIT"),
    ),
)
def test_contract_header_mismatch_is_invalid(
    tmp_path: Path, field: str, value: object
):
    paths, readiness, contract = _contract_fixture(tmp_path)
    contract[field] = value
    _write(paths["start_contract"], contract)

    _expect_contract_error(paths, readiness, GEN4_PHASE7_START_CONTRACT_INVALID)


def test_contract_unknown_field_is_invalid(tmp_path: Path):
    paths, readiness, contract = _contract_fixture(tmp_path)
    contract["unexpected"] = True
    _write(paths["start_contract"], contract)

    _expect_contract_error(paths, readiness, GEN4_PHASE7_START_CONTRACT_INVALID)


def test_wrong_entry_implementation_commit_fails_binding(tmp_path: Path):
    paths, readiness, contract = _contract_fixture(tmp_path)
    contract["phase7_entry_implementation_commit"] = "f" * 40
    _write(paths["start_contract"], contract)

    _expect_contract_error(paths, readiness, GEN4_PHASE7_START_BINDING_MISMATCH)


def test_malformed_start_implementation_commit_is_invalid(tmp_path: Path):
    paths, readiness, contract = _contract_fixture(tmp_path)
    contract["phase7_start_implementation_commit"] = "not-a-commit"
    _write(paths["start_contract"], contract)

    _expect_contract_error(paths, readiness, GEN4_PHASE7_START_CONTRACT_INVALID)


@pytest.mark.parametrize(
    "field",
    (
        "phase7_entry_source_sha256",
        "phase7_entry_cli_source_sha256",
        "phase7_start_source_sha256",
        "phase7_start_cli_source_sha256",
    ),
)
def test_source_hash_drift_fails_binding(tmp_path: Path, field: str):
    paths, readiness, contract = _contract_fixture(tmp_path)
    contract[field] = "f" * 64
    _write(paths["start_contract"], contract)

    _expect_contract_error(paths, readiness, GEN4_PHASE7_START_BINDING_MISMATCH)


@pytest.mark.parametrize(
    ("path_name", "field"),
    (
        ("authorization", "entry_authorization_sha256"),
        ("audit_request", "audit_request_sha256"),
    ),
)
def test_entry_authority_file_drift_fails_binding(
    tmp_path: Path, path_name: str, field: str
):
    paths, readiness, _ = _contract_fixture(tmp_path)
    paths[path_name].write_bytes(paths[path_name].read_bytes() + b"\n")

    excinfo = _expect_contract_error(
        paths, readiness, GEN4_PHASE7_START_BINDING_MISMATCH
    )
    assert excinfo.value.detail == field


@pytest.mark.parametrize("field", EVIDENCE_HASH_FIELDS)
def test_contract_evidence_hash_drift_fails_binding(tmp_path: Path, field: str):
    paths, readiness, contract = _contract_fixture(tmp_path)
    contract[field] = "f" * 64
    _write(paths["start_contract"], contract)

    _expect_contract_error(paths, readiness, GEN4_PHASE7_START_BINDING_MISMATCH)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("phase7_entry_authorized", False),
        ("phase7_started", True),
        ("phase7_performance_evaluation_authorized", True),
        ("production_readiness_approved", True),
        ("live_trading_authorized", True),
        ("retry_authorized", True),
        ("holdout_reuse_authorized", True),
        ("candidate_search_authorized", True),
        ("parameter_mutation_authorized", True),
        ("symbol_substitution_authorized", True),
        ("result_dependent_methodology_change_allowed", True),
        ("result_dependent_parameter_change_allowed", True),
        ("recon009_status", "CLOSED"),
        ("paper_only", False),
    ),
)
def test_contract_governance_drift_fails_closed(
    tmp_path: Path, field: str, value: object
):
    paths, readiness, contract = _contract_fixture(tmp_path)
    contract[field] = value
    _write(paths["start_contract"], contract)

    _expect_contract_error(
        paths, readiness, GEN4_PHASE7_START_GOVERNANCE_MISMATCH
    )


def _start_operation_kwargs(paths: dict[str, Path]) -> dict[str, object]:
    values: dict[str, object] = _start_kwargs(paths)
    values.update(
        {
            "start_contract_path": paths["start_contract"],
            "start_output_path": paths["start_output"],
            "phase7_start_path": paths["phase7_start"],
            "phase7_start_cli_path": paths["phase7_start_cli"],
        }
    )
    return values


def _start_fixture(tmp_path: Path) -> tuple[dict[str, Path], dict[str, object]]:
    paths, _, contract = _contract_fixture(tmp_path)
    paths["start_output"] = tmp_path / "phase7-start.json"
    return paths, contract


def _artifact_self_hash(artifact: dict[str, object]) -> str:
    payload = artifact.copy()
    del payload["artifact_sha256"]
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def test_start_creates_canonical_governed_artifact(tmp_path: Path):
    paths, contract = _start_fixture(tmp_path)

    artifact = start_generation4_phase7(**_start_operation_kwargs(paths))

    assert artifact["schema_version"] == "GENERATION4-PHASE7-START-v1"
    assert artifact["status"] == "GENERATION4_PHASE7_STARTED"
    assert artifact["authority"] == (
        "COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION"
    )
    assert artifact["phase7_entry_authorized"] is True
    assert artifact["phase7_started"] is True
    assert artifact["phase7_performance_evaluation_authorized"] is False
    assert artifact["production_readiness_approved"] is False
    assert artifact["live_trading_authorized"] is False
    assert artifact["retry_authorized"] is False
    assert artifact["holdout_reuse_authorized"] is False
    assert artifact["candidate_search_authorized"] is False
    assert artifact["parameter_mutation_authorized"] is False
    assert artifact["symbol_substitution_authorized"] is False
    assert artifact["result_dependent_methodology_change_allowed"] is False
    assert artifact["result_dependent_parameter_change_allowed"] is False
    assert artifact["recon009_status"] == "OPEN"
    assert artifact["paper_only"] is True
    assert artifact["artifact_sha256"] == _artifact_self_hash(artifact)
    assert json.loads(paths["start_output"].read_bytes()) == artifact
    assert paths["start_output"].read_bytes() == json.dumps(
        artifact,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    for field in (
        "candidate_id",
        "binding_sha256",
        "implementation_sha256",
        "split_normalizer_sha256",
        "dividend_reconciliation_sha256",
        "successor_evaluator_sha256",
        "locked_symbols",
        "holdout_id",
        "release_id",
        "authorization_id",
        "entry_authorization_sha256",
        "audit_request_sha256",
        "phase7_entry_implementation_commit",
        "phase7_entry_source_sha256",
        "phase7_entry_cli_source_sha256",
        "phase7_start_implementation_commit",
        "phase7_start_source_sha256",
        "phase7_start_cli_source_sha256",
        *EVIDENCE_HASH_FIELDS,
    ):
        assert artifact[field] == contract[field]
    assert artifact["start_contract_sha256"] == _file_sha(paths["start_contract"])
    assert "metrics" not in artifact


def test_second_start_attempt_never_overwrites(tmp_path: Path):
    paths, _ = _start_fixture(tmp_path)
    first = start_generation4_phase7(**_start_operation_kwargs(paths))
    original_bytes = paths["start_output"].read_bytes()

    with pytest.raises(Generation4Phase7StartError) as excinfo:
        start_generation4_phase7(**_start_operation_kwargs(paths))

    assert excinfo.value.code == GEN4_PHASE7_ALREADY_STARTED
    assert paths["start_output"].read_bytes() == original_bytes
    assert json.loads(original_bytes) == first


def test_malformed_existing_start_artifact_is_never_overwritten(tmp_path: Path):
    paths, _ = _start_fixture(tmp_path)
    paths["start_output"].write_bytes(b"not-json")

    with pytest.raises(Generation4Phase7StartError) as excinfo:
        start_generation4_phase7(**_start_operation_kwargs(paths))

    assert excinfo.value.code == GEN4_PHASE7_ALREADY_STARTED
    assert paths["start_output"].read_bytes() == b"not-json"


def test_failure_before_write_leaves_output_absent(tmp_path: Path):
    paths, contract = _start_fixture(tmp_path)
    contract["phase6_closure_sha256"] = "f" * 64
    _write(paths["start_contract"], contract)

    with pytest.raises(Generation4Phase7StartError) as excinfo:
        start_generation4_phase7(**_start_operation_kwargs(paths))

    assert excinfo.value.code == GEN4_PHASE7_START_BINDING_MISMATCH
    assert not paths["start_output"].exists()


def test_exclusive_create_race_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    paths, _ = _start_fixture(tmp_path)
    output = paths["start_output"]
    original_open = Path.open

    def racing_open(self: Path, mode: str = "r", *args, **kwargs):
        if self == output and mode == "xb":
            raise FileExistsError(str(self))
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", racing_open)

    with pytest.raises(Generation4Phase7StartError) as excinfo:
        start_generation4_phase7(**_start_operation_kwargs(paths))

    assert excinfo.value.code == GEN4_PHASE7_ALREADY_STARTED
    assert not output.exists()


def _cli_fixture(tmp_path: Path) -> dict[str, Path]:
    paths, _, contract = _contract_fixture(tmp_path)
    paths["phase7_entry_cli"] = Path(phase7_entry_cli.__file__)
    paths["phase7_start_cli"] = Path(phase7_start_cli.__file__)

    request = json.loads(paths["audit_request"].read_text(encoding="utf-8"))
    request["phase7_cli_implementation_sha256"] = _file_sha(
        paths["phase7_entry_cli"]
    )
    _write(paths["audit_request"], request)
    authorization = json.loads(
        paths["authorization"].read_text(encoding="utf-8")
    )
    authorization["phase7_cli_implementation_sha256"] = _file_sha(
        paths["phase7_entry_cli"]
    )
    authorization["audit_request_sha256"] = _file_sha(paths["audit_request"])
    _write(paths["authorization"], authorization)

    readiness = verify_generation4_phase7_start_readiness(**_start_kwargs(paths))
    for field in (
        "entry_authorization_sha256",
        "audit_request_sha256",
        "phase7_entry_cli_source_sha256",
    ):
        contract[field] = readiness[field]
    contract["phase7_start_source_sha256"] = _file_sha(paths["phase7_start"])
    contract["phase7_start_cli_source_sha256"] = _file_sha(
        paths["phase7_start_cli"]
    )
    _write(paths["start_contract"], contract)
    paths["start_output"] = tmp_path / "phase7-start.json"
    return paths


def _cli_common_args(paths: dict[str, Path]) -> list[str]:
    return [
        "--phase6-contract",
        str(paths["contract"]),
        "--acquisition-authorization",
        str(paths["acquisition_authorization"]),
        "--selection",
        str(paths["selection"]),
        "--virginity-attestation",
        str(paths["virginity_attestation"]),
        "--virginity-evidence",
        str(paths["virginity_evidence"]),
        "--acquisition-receipt",
        str(paths["receipt"]),
        "--release",
        str(paths["release"]),
        "--phase6-result",
        str(paths["result"]),
        "--consumption-marker",
        str(paths["marker"]),
        "--phase6-closure",
        str(paths["closure"]),
        "--audit-request",
        str(paths["audit_request"]),
        "--authorization",
        str(paths["authorization"]),
        "--start-contract",
        str(paths["start_contract"]),
    ]


def test_cli_verify_start_readiness_is_non_mutating(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    paths = _cli_fixture(tmp_path)

    result = phase7_start_cli.main(
        ["verify-start-readiness", *_cli_common_args(paths)]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "GENERATION4_PHASE7_START_READY"
    assert output["phase7_started"] is False
    assert output["phase7_performance_evaluation_authorized"] is False
    assert not paths["start_output"].exists()
    assert "metrics" not in output


def test_cli_start_phase7_creates_only_requested_artifact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    paths = _cli_fixture(tmp_path)

    result = phase7_start_cli.main(
        [
            "start-phase7",
            *_cli_common_args(paths),
            "--start-output",
            str(paths["start_output"]),
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "GENERATION4_PHASE7_STARTED"
    assert output["phase7_started"] is True
    assert output["phase7_performance_evaluation_authorized"] is False
    assert json.loads(paths["start_output"].read_bytes()) == output
    assert "metrics" not in output


def test_cli_error_is_canonical_nonzero_json_without_metrics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    paths = _cli_fixture(tmp_path)
    paths["authorization"].unlink()

    result = phase7_start_cli.main(
        ["verify-start-readiness", *_cli_common_args(paths)]
    )

    assert result == 1
    raw = capsys.readouterr().out.strip()
    output = json.loads(raw)
    assert raw == json.dumps(
        output,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    assert output["status"] == "FORBIDDEN"
    assert output["code"] == GEN4_PHASE7_START_ENTRY_INVALID
    assert "metrics" not in output


def test_cli_exposes_only_start_boundary_commands_and_arguments():
    source = Path(phase7_start_cli.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "OpenTradeContext",
        "place_order",
        "modify_order",
        "cancel_order",
        "unlock_trade",
        "acquire-final-holdout",
        "evaluate-final-holdout",
        "issue-final-holdout-release",
        "close-phase6",
        "--bundle",
        "--key",
        "--overwrite",
        "--production",
        "--live-trading",
    ):
        assert forbidden not in source

    parser = phase7_start_cli._parser()
    assert set(parser._subparsers._group_actions[0].choices) == {
        "verify-start-readiness",
        "start-phase7",
    }


def test_committed_start_contract_binds_frozen_implementation_and_entry():
    contract = json.loads(COMMITTED_START_CONTRACT.read_text(encoding="utf-8"))
    authorization_path = (
        ROOT
        / "data/governance/successor/generation4-phase7-entry-authorization.json"
    )
    request_path = (
        ROOT
        / "data/governance/successor/"
        "generation4-phase7-entry-independent-audit-request.json"
    )
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))

    assert contract["phase7_start_implementation_commit"] == (
        "356ee53a7652b33f2ea91bf8779bd174fa794fda"
    )
    assert contract["phase7_entry_implementation_commit"] == (
        "7893306e3c77b85c59f044b787a55579593c678b"
    )
    assert contract["phase7_start_source_sha256"] == _file_sha(
        Path(phase7_start_module.__file__)
    )
    assert contract["phase7_start_cli_source_sha256"] == _file_sha(
        Path(phase7_start_cli.__file__)
    )
    assert contract["phase7_entry_source_sha256"] == _file_sha(
        Path(phase7_entry_module.__file__)
    )
    assert contract["phase7_entry_cli_source_sha256"] == _file_sha(
        Path(phase7_entry_cli.__file__)
    )
    assert contract["entry_authorization_sha256"] == _file_sha(
        authorization_path
    )
    assert contract["audit_request_sha256"] == _file_sha(request_path)
    for field in (
        "candidate_id",
        "binding_sha256",
        "implementation_sha256",
        "split_normalizer_sha256",
        "dividend_reconciliation_sha256",
        "successor_evaluator_sha256",
        "locked_symbols",
        "holdout_id",
        "release_id",
        "authorization_id",
        *EVIDENCE_HASH_FIELDS,
    ):
        assert contract[field] == authorization[field]
    assert contract["phase7_entry_authorized"] is True
    assert contract["phase7_started"] is False
    assert contract["phase7_performance_evaluation_authorized"] is False
    assert contract["production_readiness_approved"] is False
    assert contract["live_trading_authorized"] is False
    assert contract["recon009_status"] == "OPEN"
    assert contract["paper_only"] is True


def test_real_repository_start_state_is_governed():
    if not COMMITTED_START_ARTIFACT.exists():
        return
    artifact = json.loads(COMMITTED_START_ARTIFACT.read_text(encoding="utf-8"))
    assert artifact["schema_version"] == "GENERATION4-PHASE7-START-v1"
    assert artifact["status"] == "GENERATION4_PHASE7_STARTED"
    assert artifact["phase7_entry_authorized"] is True
    assert artifact["phase7_started"] is True
    assert artifact["phase7_performance_evaluation_authorized"] is False
    assert artifact["production_readiness_approved"] is False
    assert artifact["live_trading_authorized"] is False
    assert artifact["recon009_status"] == "OPEN"
    assert artifact["paper_only"] is True
    assert artifact["artifact_sha256"] == _artifact_self_hash(artifact)
