from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from investment_tracker.independent_audit.post_generation3.phase7_evaluation import (
    GEN4_PHASE7_EVAL_BINDING_MISMATCH,
    GEN4_PHASE7_EVAL_CONTRACT_INVALID,
    GEN4_PHASE7_EVAL_CONTRACT_MISSING,
    GEN4_PHASE7_EVAL_EVIDENCE_INVALID,
    GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH,
    GEN4_PHASE7_EVAL_START_ARTIFACT_INVALID,
    GEN4_PHASE7_EVAL_START_CONTRACT_INVALID,
    Generation4Phase7EvaluationContract,
    Generation4Phase7EvaluationError,
    verify_generation4_phase7_evaluation_preflight,
)

CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
BINDING_SHA256 = "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"
IMPLEMENTATION_SHA256 = (
    "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"
)
SPLIT_NORMALIZER_SHA256 = (
    "bfbf0de5bdeb39af3535641570f3f9224f5301abb7db9fffc34c580481cace04"
)
DIVIDEND_RECONCILIATION_SHA256 = (
    "6baa251d51f6f16be602aa82b08fc46665a4ccdd62f68705821c48c8a28ac9bc"
)
SUCCESSOR_EVALUATOR_SHA256 = (
    "fb20b368d6d7ac0f698c5ab45e5824aaad73341cccfacc25bc6903b98c9a2b21"
)
RESEARCH_UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
HOLDOUT_SYMBOLS = ("QQQM", "FALN", "IIPR", "PSTL", "EFAS")
PHASE6_STATUS = "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"
AUTHORITY = "COORDINATOR_UNDER_INDEPENDENT_AUDIT_ENTRY_AUTHORIZATION"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> Path:
    path.write_bytes(_canonical(value))
    return path


def _self_hash(payload: dict[str, object]) -> str:
    body = dict(payload)
    body.pop("artifact_sha256", None)
    return sha256(_canonical(body)).hexdigest()


def _start_contract_payload() -> dict[str, object]:
    return {
        "schema_version": "GENERATION4-PHASE7-START-CONTRACT-v1",
        "status": "FROZEN_PRE_START",
        "authority": AUTHORITY,
        "generation": "GENERATION_4",
        "candidate_id": CANDIDATE_ID,
        "binding_sha256": BINDING_SHA256,
        "implementation_sha256": IMPLEMENTATION_SHA256,
        "split_normalizer_sha256": SPLIT_NORMALIZER_SHA256,
        "dividend_reconciliation_sha256": DIVIDEND_RECONCILIATION_SHA256,
        "successor_evaluator_sha256": SUCCESSOR_EVALUATOR_SHA256,
        "locked_symbols": list(HOLDOUT_SYMBOLS),
        "holdout_id": "successor-phase6-holdout-synthetic",
        "release_id": "successor-phase6-release-synthetic",
        "authorization_id": "SYNTHETIC-GEN4-PHASE7-AUTHORIZATION",
        "entry_authorization_sha256": "a" * 64,
        "audit_request_sha256": "b" * 64,
        "phase6_contract_sha256": "1" * 64,
        "acquisition_authorization_sha256": "2" * 64,
        "acquisition_receipt_sha256": "3" * 64,
        "release_sha256": "4" * 64,
        "evaluation_result_sha256": "5" * 64,
        "evaluation_consumption_marker_sha256": "6" * 64,
        "phase6_closure_sha256": "7" * 64,
        "phase6_status": PHASE6_STATUS,
        "one_time_consumed": True,
        "phase7_entry_implementation_commit": "7" * 40,
        "phase7_entry_source_sha256": "c" * 64,
        "phase7_entry_cli_source_sha256": "d" * 64,
        "phase7_start_implementation_commit": "3" * 40,
        "phase7_start_source_sha256": "f" * 64,
        "phase7_start_cli_source_sha256": "9" * 64,
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


def _start_artifact_payload(start_contract_sha256: str) -> dict[str, object]:
    payload = dict(_start_contract_payload())
    payload.update(
        {
            "schema_version": "GENERATION4-PHASE7-START-v1",
            "status": "GENERATION4_PHASE7_STARTED",
            "started_at_utc": "2026-09-26T00:00:00Z",
            "start_contract_sha256": start_contract_sha256,
            "phase7_started": True,
        }
    )
    payload["artifact_sha256"] = _self_hash(payload)
    return payload


def _evaluation_contract_payload(
    start_artifact_sha256: str,
    start_artifact_self_hash: str,
    start_contract_sha256: str,
) -> dict[str, object]:
    return {
        "schema_version": "GENERATION4-PHASE7-EVALUATION-CONTRACT-v1",
        "status": "FROZEN_PRE_EVALUATION",
        "authority": AUTHORITY,
        "generation": "GENERATION_4",
        "candidate_id": CANDIDATE_ID,
        "binding_sha256": BINDING_SHA256,
        "implementation_sha256": IMPLEMENTATION_SHA256,
        "split_normalizer_sha256": SPLIT_NORMALIZER_SHA256,
        "dividend_reconciliation_sha256": DIVIDEND_RECONCILIATION_SHA256,
        "successor_evaluator_sha256": SUCCESSOR_EVALUATOR_SHA256,
        "start_artifact_sha256": start_artifact_sha256,
        "start_artifact_self_hash": start_artifact_self_hash,
        "start_contract_sha256": start_contract_sha256,
        "entry_authorization_id": "SYNTHETIC-GEN4-PHASE7-AUTHORIZATION",
        "entry_authorization_sha256": "a" * 64,
        "phase7_entry_implementation_commit": "7" * 40,
        "phase7_entry_source_sha256": "c" * 64,
        "phase7_entry_cli_source_sha256": "d" * 64,
        "phase7_start_implementation_commit": "3" * 40,
        "phase7_start_source_sha256": "f" * 64,
        "phase7_start_cli_source_sha256": "9" * 64,
        "phase7_evaluation_implementation_commit": "e" * 40,
        "phase7_evaluation_source_sha256": "0" * 64,
        "phase7_evaluation_cli_source_sha256": "8" * 64,
        "research_universe": list(RESEARCH_UNIVERSE),
        "forbidden_holdout_symbols": list(HOLDOUT_SYMBOLS),
        "benchmark_symbol": "SPY",
        "initial_cash": 100000.0,
        "friction_cases_bps": [0, 3, 10, 25, 50],
        "primary_friction_bps": 3,
        "prospective_first_scored_session": "2026-09-28",
        "warmup_session_limit": 210,
        "checkpoint_sessions": [63, 126, 252],
        "historical_lane_classification": "REUSED_HISTORY_DIAGNOSTIC_ONLY",
        "dq030_status": "UNRESOLVED",
        "phase7_started": True,
        "phase7_performance_evaluation_authorized": False,
        "production_readiness_approved": False,
        "live_trading_authorized": False,
        "holdout_reuse_authorized": False,
        "candidate_search_authorized": False,
        "parameter_mutation_authorized": False,
        "symbol_substitution_authorized": False,
        "adaptive_walk_forward_authorized": False,
        "annual_reoptimization_authorized": False,
        "result_dependent_methodology_change_allowed": False,
        "result_dependent_parameter_change_allowed": False,
        "recon009_status": "OPEN",
        "paper_only": True,
    }


def _valid_paths(tmp_path: Path) -> dict[str, Path]:
    start_contract = _write(tmp_path / "start-contract.json", _start_contract_payload())
    artifact_payload = _start_artifact_payload(_sha(start_contract))
    start_artifact = _write(tmp_path / "start.json", artifact_payload)
    evaluation_contract = _write(
        tmp_path / "evaluation-contract.json",
        _evaluation_contract_payload(
            _sha(start_artifact),
            str(artifact_payload["artifact_sha256"]),
            _sha(start_contract),
        ),
    )
    return {
        "start_artifact": start_artifact,
        "start_contract": start_contract,
        "evaluation_contract": evaluation_contract,
    }


def _preflight(paths: dict[str, Path]) -> dict[str, object]:
    return verify_generation4_phase7_evaluation_preflight(
        start_artifact_path=paths["start_artifact"],
        start_contract_path=paths["start_contract"],
        evaluation_contract_path=paths["evaluation_contract"],
    )


def _mutate(path: Path, field: str, value: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    _write(path, payload)


def _mutate_artifact(paths: dict[str, Path], field: str, value: object) -> None:
    payload = json.loads(paths["start_artifact"].read_text(encoding="utf-8"))
    payload[field] = value
    payload["artifact_sha256"] = _self_hash(payload)
    _write(paths["start_artifact"], payload)


def _expect_error(paths: dict[str, Path], code: str) -> None:
    with pytest.raises(Generation4Phase7EvaluationError) as excinfo:
        _preflight(paths)
    assert excinfo.value.code == code


def test_valid_chain_preflight_is_ready(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    report = _preflight(paths)
    assert report["schema_version"] == "GENERATION4-PHASE7-EVALUATION-PREFLIGHT-v1"
    assert report["status"] == "GENERATION4_PHASE7_EVALUATION_PREFLIGHT_READY"
    assert report["generation"] == "GENERATION_4"
    assert report["start_artifact_sha256"] == _sha(paths["start_artifact"])
    assert report["start_artifact_self_hash"] == _self_hash(
        json.loads(paths["start_artifact"].read_text(encoding="utf-8"))
    )
    assert report["start_contract_sha256"] == _sha(paths["start_contract"])
    assert report["evaluation_contract_sha256"] == _sha(paths["evaluation_contract"])
    assert report["candidate_id"] == CANDIDATE_ID
    assert report["binding_sha256"] == BINDING_SHA256
    assert report["implementation_sha256"] == IMPLEMENTATION_SHA256
    assert report["split_normalizer_sha256"] == SPLIT_NORMALIZER_SHA256
    assert report["dividend_reconciliation_sha256"] == DIVIDEND_RECONCILIATION_SHA256
    assert report["successor_evaluator_sha256"] == SUCCESSOR_EVALUATOR_SHA256
    assert report["entry_authorization_id"] == "SYNTHETIC-GEN4-PHASE7-AUTHORIZATION"
    assert report["research_universe"] == list(RESEARCH_UNIVERSE)
    assert report["forbidden_holdout_symbols_sha256"] == sha256(
        _canonical(list(HOLDOUT_SYMBOLS))
    ).hexdigest()
    assert report["benchmark_symbol"] == "SPY"
    assert report["friction_cases_bps"] == [0, 3, 10, 25, 50]
    assert report["primary_friction_bps"] == 3
    assert report["initial_cash"] == 100000.0
    assert report["prospective_first_scored_session"] == "2026-09-28"
    assert report["warmup_session_limit"] == 210
    assert report["checkpoint_sessions"] == [63, 126, 252]
    assert report["historical_lane_classification"] == "REUSED_HISTORY_DIAGNOSTIC_ONLY"
    assert report["dq030_status"] == "UNRESOLVED"
    assert report["phase7_started"] is True
    assert report["phase7_performance_evaluation_authorized"] is False
    assert report["production_readiness_approved"] is False
    assert report["live_trading_authorized"] is False
    assert report["holdout_reuse_authorized"] is False
    assert report["candidate_search_authorized"] is False
    assert report["parameter_mutation_authorized"] is False
    assert report["symbol_substitution_authorized"] is False
    assert report["adaptive_walk_forward_authorized"] is False
    assert report["annual_reoptimization_authorized"] is False
    assert report["result_dependent_methodology_change_allowed"] is False
    assert report["result_dependent_parameter_change_allowed"] is False
    assert report["recon009_status"] == "OPEN"
    assert report["paper_only"] is True
    assert "metrics" not in report


def test_missing_start_artifact_fails_closed(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    paths["start_artifact"].unlink()
    _expect_error(paths, GEN4_PHASE7_EVAL_EVIDENCE_INVALID)


def test_malformed_start_artifact_fails_closed(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    paths["start_artifact"].write_text("{not json", encoding="utf-8")
    _expect_error(paths, GEN4_PHASE7_EVAL_EVIDENCE_INVALID)


def test_missing_start_contract_fails_closed(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    paths["start_contract"].unlink()
    _expect_error(paths, GEN4_PHASE7_EVAL_START_CONTRACT_INVALID)


def test_missing_evaluation_contract_fails_closed(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    paths["evaluation_contract"].unlink()
    _expect_error(paths, GEN4_PHASE7_EVAL_CONTRACT_MISSING)


def test_start_artifact_self_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["start_artifact"], "artifact_sha256", "0" * 64)
    _expect_error(paths, GEN4_PHASE7_EVAL_EVIDENCE_INVALID)


def test_start_artifact_metrics_key_fails_closed(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate_artifact(paths, "metrics", {"total_return": 0.1})
    _expect_error(paths, GEN4_PHASE7_EVAL_EVIDENCE_INVALID)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "GENERATION4-PHASE7-START-CONTRACT-v1"),
        ("status", "FROZEN_PRE_START"),
        ("authority", "INDEPENDENT_AUDIT"),
    ],
)
def test_start_artifact_header_mismatch_fails_closed(
    tmp_path: Path, field: str, value: object
) -> None:
    paths = _valid_paths(tmp_path)
    _mutate_artifact(paths, field, value)
    _expect_error(paths, GEN4_PHASE7_EVAL_START_ARTIFACT_INVALID)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "GENERATION4-PHASE7-START-v1"),
        ("status", "GENERATION4_PHASE7_STARTED"),
        ("authority", "INDEPENDENT_AUDIT"),
    ],
)
def test_start_contract_header_mismatch_fails_closed(
    tmp_path: Path, field: str, value: object
) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["start_contract"], field, value)
    _expect_error(paths, GEN4_PHASE7_EVAL_START_CONTRACT_INVALID)


def test_start_artifact_phase7_started_false(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate_artifact(paths, "phase7_started", False)
    _expect_error(paths, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


def test_start_artifact_performance_evaluation_authorized_true(
    tmp_path: Path,
) -> None:
    paths = _valid_paths(tmp_path)
    _mutate_artifact(paths, "phase7_performance_evaluation_authorized", True)
    _expect_error(paths, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


@pytest.mark.parametrize(
    "field",
    ["production_readiness_approved", "live_trading_authorized"],
)
def test_start_artifact_production_or_live_authority_true(
    tmp_path: Path, field: str
) -> None:
    paths = _valid_paths(tmp_path)
    _mutate_artifact(paths, field, True)
    _expect_error(paths, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


def test_start_artifact_recon009_not_open(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate_artifact(paths, "recon009_status", "RESOLVED")
    _expect_error(paths, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


def test_start_artifact_paper_only_false(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate_artifact(paths, "paper_only", False)
    _expect_error(paths, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


@pytest.mark.parametrize(
    "field",
    [
        "candidate_id",
        "binding_sha256",
        "implementation_sha256",
    ],
)
def test_start_artifact_identity_mismatch(tmp_path: Path, field: str) -> None:
    paths = _valid_paths(tmp_path)
    _mutate_artifact(paths, field, "0" * 64)
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


@pytest.mark.parametrize(
    "field",
    [
        "candidate_id",
        "binding_sha256",
        "implementation_sha256",
        "split_normalizer_sha256",
        "dividend_reconciliation_sha256",
        "successor_evaluator_sha256",
    ],
)
def test_start_contract_identity_mismatch(tmp_path: Path, field: str) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["start_contract"], field, "0" * 64)
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


@pytest.mark.parametrize(
    "field",
    [
        "candidate_id",
        "binding_sha256",
        "implementation_sha256",
        "split_normalizer_sha256",
        "dividend_reconciliation_sha256",
        "successor_evaluator_sha256",
    ],
)
def test_evaluation_contract_identity_mismatch(tmp_path: Path, field: str) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], field, "0" * 64)
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_start_contract_phase7_started_true(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["start_contract"], "phase7_started", True)
    _expect_error(paths, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


def test_start_contract_recon009_not_open(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["start_contract"], "recon009_status", "RESOLVED")
    _expect_error(paths, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


def test_research_universe_reordered(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(
        paths["evaluation_contract"],
        "research_universe",
        list(reversed(RESEARCH_UNIVERSE)),
    )
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_research_universe_substituted_symbol(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(
        paths["evaluation_contract"],
        "research_universe",
        [symbol if symbol != "GLD" else "CORN" for symbol in RESEARCH_UNIVERSE],
    )
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_research_universe_extra_symbol(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(
        paths["evaluation_contract"],
        "research_universe",
        [*RESEARCH_UNIVERSE, "CORN"],
    )
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


@pytest.mark.parametrize("symbol", HOLDOUT_SYMBOLS)
def test_research_universe_holdout_symbol(tmp_path: Path, symbol: str) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(
        paths["evaluation_contract"],
        "research_universe",
        [symbol if s == "XLP" else s for s in RESEARCH_UNIVERSE],
    )
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_forbidden_holdout_symbols_drift(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(
        paths["evaluation_contract"],
        "forbidden_holdout_symbols",
        list(HOLDOUT_SYMBOLS[:4]),
    )
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_wrong_benchmark(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "benchmark_symbol", "QQQ")
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_wrong_friction_cases(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "friction_cases_bps", [0, 3, 10])
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_wrong_primary_friction(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "primary_friction_bps", 10)
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_wrong_initial_cash(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "initial_cash", 10000.0)
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_wrong_warmup_cap(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "warmup_session_limit", 211)
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_wrong_checkpoints(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "checkpoint_sessions", [63, 126])
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


@pytest.mark.parametrize(
    "field",
    [
        "adaptive_walk_forward_authorized",
        "annual_reoptimization_authorized",
        "result_dependent_methodology_change_allowed",
        "result_dependent_parameter_change_allowed",
    ],
)
def test_evaluation_contract_retuning_authority_enabled(
    tmp_path: Path, field: str
) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], field, True)
    _expect_error(paths, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


def test_evaluation_contract_phase7_started_false(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "phase7_started", False)
    _expect_error(paths, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


def test_evaluation_contract_recon009_not_open(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "recon009_status", "RESOLVED")
    _expect_error(paths, GEN4_PHASE7_EVAL_GOVERNANCE_MISMATCH)


def test_evaluation_contract_unknown_field(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "production_ready", True)
    _expect_error(paths, GEN4_PHASE7_EVAL_CONTRACT_INVALID)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "GENERATION4-PHASE7-START-v1"),
        ("status", "GENERATION4_PHASE7_STARTED"),
        ("authority", "INDEPENDENT_AUDIT"),
    ],
)
def test_evaluation_contract_header_mismatch(
    tmp_path: Path, field: str, value: object
) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], field, value)
    _expect_error(paths, GEN4_PHASE7_EVAL_CONTRACT_INVALID)


def test_evaluation_contract_malformed_commit(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(
        paths["evaluation_contract"],
        "phase7_evaluation_implementation_commit",
        "not-a-commit",
    )
    _expect_error(paths, GEN4_PHASE7_EVAL_CONTRACT_INVALID)


def test_evaluation_contract_start_artifact_sha_mismatch(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "start_artifact_sha256", "0" * 64)
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_evaluation_contract_start_artifact_self_hash_mismatch(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "start_artifact_self_hash", "0" * 64)
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_evaluation_contract_start_contract_sha_mismatch(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "start_contract_sha256", "0" * 64)
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_evaluation_contract_entry_commit_mismatch(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(
        paths["evaluation_contract"],
        "phase7_entry_implementation_commit",
        "1" * 40,
    )
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_evaluation_contract_entry_authorization_id_mismatch(
    tmp_path: Path,
) -> None:
    paths = _valid_paths(tmp_path)
    _mutate(paths["evaluation_contract"], "entry_authorization_id", "OTHER")
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_start_artifact_start_contract_sha_mismatch(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    _mutate_artifact(paths, "start_contract_sha256", "0" * 64)
    _expect_error(paths, GEN4_PHASE7_EVAL_BINDING_MISMATCH)


def test_preflight_does_not_create_or_modify_files(tmp_path: Path) -> None:
    paths = _valid_paths(tmp_path)
    before = {
        path.name: path.read_bytes() for path in paths.values()
    }
    _preflight(paths)
    after = {
        path.name: path.read_bytes() for path in paths.values()
    }
    assert before == after
    assert [path.name for path in tmp_path.iterdir()] == sorted(
        before
    )


def test_evaluation_contract_model_is_strict_and_frozen() -> None:
    payload = _evaluation_contract_payload("1" * 64, "2" * 64, "3" * 64)
    model = Generation4Phase7EvaluationContract.model_validate(payload)
    with pytest.raises(ValueError):
        model.schema_version = "GENERATION4-PHASE7-START-v1"  # type: ignore[misc]
    with pytest.raises(ValueError):
        Generation4Phase7EvaluationContract.model_validate(
            {**payload, "unexpected": True}
        )
    assert Generation4Phase7EvaluationContract.model_config["extra"] == "forbid"
