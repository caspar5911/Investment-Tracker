from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from investment_tracker.independent_audit.successor import acquisition as acq
from investment_tracker.independent_audit.successor.acquisition_authority import (
    SCHEMA as ACQ_AUTH_SCHEMA,
    STATUS as ACQ_AUTH_STATUS,
    SuccessorAcquisitionAuthorityError,
    load_acquisition_authorization,
)
from investment_tracker.independent_audit.successor.phase6_contract import (
    build_phase6_contract,
    seal_phase6_contract,
)
from investment_tracker.independent_audit.successor.release import issue_release
from investment_tracker.independent_audit.successor.evaluate import evaluate_released_holdout
from investment_tracker.independent_audit.successor.closure import close_phase6
from investment_tracker.independent_audit.successor.virginity import (
    ATTESTATION_SCHEMA,
    ATTESTATION_STATUS,
)

ROOT = Path(__file__).resolve().parents[2]
CA_CONTRACT = ROOT / "data/governance/successor/corporate-action-normalization-v2.json"
REGISTRY = ROOT / "data/governance/holdout-exclusion-registry.json"
CLOSURE = ROOT / "data/generation2/phase6/phase6-final-holdout-closure.json"
NORMALIZER = ROOT / "src/investment_tracker/quant/successor/corporate_actions_v2.py"
EVALUATOR = ROOT / "src/investment_tracker/independent_audit/successor/evaluate.py"
ACQUISITION_IMPL = ROOT / "src/investment_tracker/independent_audit/successor/acquisition.py"
RELEASE_IMPL = ROOT / "src/investment_tracker/independent_audit/successor/release.py"
CANDIDATE = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
BINDING = "fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b"
IMPLEMENTATION = "35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return path


def _fixture(tmp_path: Path):
    symbols = ("SYN1", "SYN2", "SYN3", "SYN4", "SYN5")
    methodology = _write(
        tmp_path / "methodology-auth.json",
        {
            "schema_version": "SUCCESSOR-PHASE6-METHODOLOGY-AUTHORIZATION-v1",
            "authority": "INDEPENDENT_AUDIT",
            "status": "SUCCESSOR_PHASE6_METHODOLOGY_AUTHORIZED",
            "approval_id": "AUDIT-SUCCESSOR-SYNTHETIC-1",
            "signed_by": "Synthetic Independent Auditor Fixture",
            "approved_at_utc": "2026-09-23T00:00:00Z",
            "predecessor_closure_commit": "f875167f3e758ab3391ff2f961aa740f231568e5",
            "predecessor_phase6_status": "PHASE6_UNKNOWN_ABSTAIN",
            "successor_formal_name": "GENERATION_3_TEST_FIXTURE",
            "candidate_id": CANDIDATE,
            "binding_sha256": BINDING,
            "implementation_sha256": IMPLEMENTATION,
            "corporate_action_contract_sha256": _sha(CA_CONTRACT),
            "successor_normalizer_sha256": _sha(NORMALIZER),
            "successor_evaluator_sha256": _sha(EVALUATOR),
            "holdout_exclusion_registry_sha256": _sha(REGISTRY),
            "evaluation_calendar_start": "2023-01-01",
            "evaluation_calendar_end": "2025-12-31",
            "required_pre_window_sessions": 210,
            "selection_count": 5,
            "listing_cutoff": "2022-03-03",
            "selection_seed_sha256": "1" * 64,
            "successor_methodology_authorized": True,
            "new_virgin_holdout_selection_authorized": True,
            "protected_history_access_authorized": False,
            "one_time_acquisition_required": True,
            "retry_after_historical_access_allowed": False,
            "symbol_substitution_after_access_allowed": False,
            "result_dependent_methodology_change_allowed": False,
            "phase7_authorized": False,
            "production_readiness_approved": False,
            "recon009_status": "OPEN",
            "paper_only": True,
        },
    )
    selection = _write(
        tmp_path / "selection.json",
        {
            "schema_version": "SUCCESSOR-BLIND-FINAL-HOLDOUT-SELECTION-v1",
            "authority": "INDEPENDENT_AUDIT",
            "status": "SUCCESSOR_HOLDOUT_SELECTION_FROZEN",
            "successor_formal_name": "GENERATION_3_TEST_FIXTURE",
            "methodology_authorization_id": "AUDIT-SUCCESSOR-SYNTHETIC-1",
            "methodology_authorization_sha256": _sha(methodology),
            "candidate_id": CANDIDATE,
            "binding_sha256": BINDING,
            "implementation_sha256": IMPLEMENTATION,
            "successor_normalizer_sha256": _sha(NORMALIZER),
            "successor_evaluator_sha256": _sha(EVALUATOR),
            "historical_market_data_api_called": False,
            "protected_history_access_authorized": False,
            "selected": [
                {"position": i + 1, "symbol": symbol}
                for i, symbol in enumerate(symbols)
            ],
        },
    )
    evidence = _write(
        tmp_path / "virginity-evidence.json",
        {
            "schema_version": "SUCCESSOR-COMPOSITE-VIRGINITY-EVIDENCE-v1",
            "authority": "INDEPENDENT_AUDIT",
            "status": ATTESTATION_STATUS,
            "selection_sha256": _sha(selection),
            "successor_formal_name": "GENERATION_3_TEST_FIXTURE",
            "selected_symbols": list(symbols),
            "historical_market_data_api_called": False,
            "protected_history_access_authorized": False,
        },
    )
    attestation = _write(
        tmp_path / "virginity-attestation.json",
        {
            "schema_version": ATTESTATION_SCHEMA,
            "authority": "INDEPENDENT_AUDIT",
            "status": ATTESTATION_STATUS,
            "attestation_id": "successor-virginity-synthetic",
            "successor_formal_name": "GENERATION_3_TEST_FIXTURE",
            "selected_symbols": list(symbols),
            "selection_sha256": _sha(selection),
            "evidence_bundle_sha256": _sha(evidence),
            "historical_market_data_api_called": False,
            "protected_history_access_authorized": False,
        },
    )

    phase6_payload = build_phase6_contract(
        methodology_authorization_path=methodology,
        selection_path=selection,
        virginity_evidence_path=evidence,
        virginity_attestation_path=attestation,
        corporate_action_contract_path=CA_CONTRACT,
        successor_normalizer_path=NORMALIZER,
        successor_evaluator_path=EVALUATOR,
        holdout_exclusion_registry_path=REGISTRY,
        predecessor_closure_path=CLOSURE,
    )
    phase6 = seal_phase6_contract(phase6_payload, tmp_path / "phase6-contract.json")

    acquisition_auth = _write(
        tmp_path / "acquisition-auth.json",
        {
            "schema_version": ACQ_AUTH_SCHEMA,
            "authority": "INDEPENDENT_AUDIT",
            "status": ACQ_AUTH_STATUS,
            "authorization_id": "AUDIT-SUCCESSOR-ACQUIRE-SYNTHETIC-1",
            "signed_by": "Synthetic Independent Auditor Fixture",
            "approved_at_utc": "2026-09-23T00:01:00Z",
            "successor_formal_name": "GENERATION_3_TEST_FIXTURE",
            "candidate_id": CANDIDATE,
            "binding_sha256": BINDING,
            "implementation_sha256": IMPLEMENTATION,
            "successor_normalizer_sha256": _sha(NORMALIZER),
            "successor_evaluator_sha256": _sha(EVALUATOR),
            "acquisition_implementation_sha256": _sha(ACQUISITION_IMPL),
            "release_implementation_sha256": _sha(RELEASE_IMPL),
            "phase6_contract_sha256": _sha(phase6),
            "selection_sha256": _sha(selection),
            "virginity_attestation_sha256": _sha(attestation),
            "virginity_evidence_sha256": _sha(evidence),
            "locked_symbols": list(symbols),
            "one_time": True,
            "acquisition_start_marker_required_before_provider_read": True,
            "retry_after_historical_access_allowed": False,
            "symbol_substitution_after_access_allowed": False,
            "historical_data_included_in_authorization_artifact": False,
            "holdout_performance_inspected": False,
            "one_time_evaluation_after_verified_release_authorized": True,
            "phase7_authorized": False,
            "production_readiness_approved": False,
            "recon009_status": "OPEN",
            "paper_only": True,
        },
    )
    return symbols, methodology, selection, evidence, attestation, phase6, acquisition_auth


def test_successor_phase6_contract_is_still_pre_access(tmp_path: Path) -> None:
    _, _, _, _, _, phase6, _ = _fixture(tmp_path)
    value = json.loads(phase6.read_text())
    assert value["status"] == "FROZEN_PRE_ACCESS"
    assert value["methodology"]["accounting"] == "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v2"
    assert value["governance"]["protected_history_access_authorized"] is False
    assert value["governance"]["acquisition_authorization_required"] is True
    assert value["governance"]["phase7_authorized"] is False
    assert value["governance"]["recon009_status"] == "OPEN"


def test_separate_acquisition_authorization_binds_all_preaccess_evidence(tmp_path: Path) -> None:
    symbols, _, selection, evidence, attestation, phase6, auth_path = _fixture(tmp_path)
    auth = load_acquisition_authorization(
        authorization_path=auth_path,
        phase6_contract_path=phase6,
        selection_path=selection,
        virginity_attestation_path=attestation,
        virginity_evidence_path=evidence,
    )
    assert auth.locked_symbols == symbols
    assert auth.one_time is True
    assert auth.retry_after_historical_access_allowed is False
    assert auth.phase7_authorized is False


def test_missing_acquisition_authorization_fails_closed(tmp_path: Path) -> None:
    _, _, selection, evidence, attestation, phase6, _ = _fixture(tmp_path)
    with pytest.raises(
        SuccessorAcquisitionAuthorityError,
        match="SUCCESSOR_ACQUISITION_AUTHORIZATION_MISSING",
    ):
        load_acquisition_authorization(
            authorization_path=tmp_path / "missing.json",
            phase6_contract_path=phase6,
            selection_path=selection,
            virginity_attestation_path=attestation,
            virginity_evidence_path=evidence,
        )


def test_irreversible_marker_is_true_before_first_mocked_history_read(
    monkeypatch, tmp_path: Path
) -> None:
    symbols, _, selection, evidence, attestation, phase6, auth_path = _fixture(tmp_path)
    private = tmp_path.parent / (tmp_path.name + "-private")
    sessions = pd.date_range("2022-03-03", periods=212, freq="B", tz="UTC")
    warmup, scored = sessions[:210], sessions[210:]

    class Context:
        def __init__(self, *args, **kwargs):
            pass

        def request_history_kline(self, *args, **kwargs):
            marker = next(private.glob("*.acquisition-start.json"))
            value = json.loads(marker.read_text())
            assert value["historical_access_started"] is True
            assert value["retry_allowed_after_historical_access"] is False
            raise RuntimeError("STOP_AT_FIRST_HISTORY")

        def close(self):
            pass

    sdk = SimpleNamespace(
        OpenQuoteContext=Context,
        RET_OK=0,
        AuType=SimpleNamespace(QFQ="QFQ", NONE="NONE"),
        KLType=SimpleNamespace(K_DAY="K_DAY"),
        __version__="synthetic",
    )

    monkeypatch.setattr(acq, "_load_sdk", lambda: (sdk, "synthetic"))
    monkeypatch.setattr(acq, "_verify_sdk_capabilities", lambda sdk: None)
    monkeypatch.setattr(
        acq,
        "_provider_quota_preflight",
        lambda context, sdk, locked_symbols, required_capacity: {
            "used": 0,
            "remaining": 300,
            "locked_matches": [],
        },
    )
    monkeypatch.setattr(acq, "expected_sessions", lambda contract: (warmup, scored))

    with pytest.raises(RuntimeError, match="STOP_AT_FIRST_HISTORY"):
        acq.acquire_and_seal(
            repository_root=ROOT,
            authorization_path=auth_path,
            phase6_contract_path=phase6,
            selection_path=selection,
            virginity_attestation_path=attestation,
            virginity_evidence_path=evidence,
            private_output_dir=private,
        )
    marker = next(private.glob("*.acquisition-start.json"))
    assert json.loads(marker.read_text())["historical_access_started"] is True


def _bars(sessions: pd.DatetimeIndex, offset: int) -> bytes:
    closes = pd.Series(
        [
            (50.0 + offset)
            * (1.0 + 0.00010 * (offset + 1)) ** index
            * (1.0 + 0.02 * math.sin(index / 7.0 + offset))
            for index in range(len(sessions))
        ]
    )
    opens = pd.Series(
        [
            value * (1.0 + 0.003 * math.sin(index / 3.0 + offset))
            for index, value in enumerate(closes)
        ]
    )
    highs = pd.concat([opens, closes], axis=1).max(axis=1) * 1.001
    lows = pd.concat([opens, closes], axis=1).min(axis=1) * 0.999
    frame = pd.DataFrame(
        {
            "session": sessions.strftime("%Y-%m-%d"),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
        }
    )
    return frame.to_csv(
        index=False, lineterminator="\n", float_format="%.17g"
    ).encode()


def _sealed_fixture(tmp_path: Path):
    symbols, methodology, selection, evidence, attestation, phase6, auth_path = _fixture(tmp_path)
    contract = json.loads(phase6.read_text(encoding="utf-8"))
    warmup, scored = acq.expected_sessions(contract)
    sessions = warmup.append(scored)
    benchmark = contract["final_holdout"]["benchmark_reference_symbol"]
    data_symbols = (*symbols, benchmark)
    entries: dict[str, bytes] = {}
    for offset, symbol in enumerate(data_symbols):
        payload = _bars(sessions, offset)
        entries[f"bars/qfq/{symbol}.csv"] = payload
        entries[f"bars/unadjusted/{symbol}.csv"] = payload
        entries[f"corporate_actions/rehab/{symbol}.csv"] = b"ex_div_date\n"
        entries[f"corporate_actions/dividends/{symbol}.json"] = b'{"dividend_list":[]}'
        entries[f"corporate_actions/splits/{symbol}.json"] = b'{"split_list":[]}'

    manifest = {
        "schema_version": acq.SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "provider": "MOOMOO_OPEND",
        "sdk_module": "synthetic",
        "sdk_version": "test",
        "successor_formal_name": contract["successor_formal_name"],
        "phase6_contract_sha256": _sha(phase6),
        "acquisition_authorization_sha256": _sha(auth_path),
        "candidate_id": CANDIDATE,
        "binding_sha256": BINDING,
        "implementation_sha256": IMPLEMENTATION,
        "successor_normalizer_sha256": _sha(NORMALIZER),
        "successor_evaluator_sha256": _sha(EVALUATOR),
        "locked_symbols": list(symbols),
        "benchmark_reference_symbol": benchmark,
        "requested_start": warmup[0].date().isoformat(),
        "requested_end": contract["final_holdout"]["calendar_end"],
        "holdout_start": contract["final_holdout"]["calendar_start"],
        "holdout_end": contract["final_holdout"]["calendar_end"],
        "warmup_session_count": len(warmup),
        "scored_session_count": len(scored),
        "retrieved_at_utc": "2026-09-23T00:00:00+00:00",
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(symbols),
        "performance_computed": False,
        "performance_inspected": False,
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "phase7_started": False,
        "live_trading_capability": False,
    }
    plaintext, full_manifest = acq._build_bundle(manifest, entries)
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    encrypted = acq.MAGIC + nonce + AESGCM(key).encrypt(
        nonce, plaintext, _sha(phase6).encode("ascii")
    )
    holdout_id = f"successor-phase6-holdout-{sha256(plaintext).hexdigest()[:32]}"
    private = tmp_path / "private"
    private.mkdir()
    bundle = private / f"{holdout_id}.bundle.aesgcm"
    key_path = private / f"{holdout_id}.key"
    receipt = private / f"{holdout_id}.receipt.json"
    bundle.write_bytes(encrypted)
    key_path.write_text(key.hex(), encoding="ascii")
    receipt_payload = {
        "schema_version": acq.RECEIPT_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED",
        "successor_formal_name": contract["successor_formal_name"],
        "holdout_id": holdout_id,
        "phase6_contract_sha256": _sha(phase6),
        "acquisition_authorization_sha256": _sha(auth_path),
        "candidate_id": CANDIDATE,
        "binding_sha256": BINDING,
        "implementation_sha256": IMPLEMENTATION,
        "successor_normalizer_sha256": _sha(NORMALIZER),
        "successor_evaluator_sha256": _sha(EVALUATOR),
        "bundle_sha256": sha256(encrypted).hexdigest(),
        "plaintext_bundle_sha256": sha256(plaintext).hexdigest(),
        "bundle_manifest_sha256": sha256(acq._canonical_bytes(full_manifest)).hexdigest(),
        "key_sha256": sha256(key).hexdigest(),
        "bundle_bytes": len(encrypted),
        "provider": "MOOMOO_OPEND",
        "requested_start": warmup[0].date().isoformat(),
        "requested_end": contract["final_holdout"]["calendar_end"],
        "holdout_start": contract["final_holdout"]["calendar_start"],
        "holdout_end": contract["final_holdout"]["calendar_end"],
        "warmup_session_count": len(warmup),
        "scored_session_count": len(scored),
        "retrieved_at_utc": "2026-09-23T00:00:00+00:00",
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(symbols),
        "performance_computed": False,
        "performance_inspected": False,
        "retry_allowed": False,
        "artifact_readback_verified": True,
    }
    receipt_payload["receipt_sha256"] = sha256(
        acq._canonical_bytes(receipt_payload)
    ).hexdigest()
    receipt.write_bytes(acq._canonical_bytes(receipt_payload))
    return symbols, selection, evidence, attestation, phase6, auth_path, receipt, bundle, key_path, private


def test_synthetic_successor_release_evaluation_and_closure(tmp_path: Path) -> None:
    (
        symbols,
        selection,
        evidence,
        attestation,
        phase6,
        auth_path,
        receipt,
        bundle,
        key,
        private,
    ) = _sealed_fixture(tmp_path)
    release = tmp_path / "release.json"
    receipt_evidence = tmp_path / "receipt-evidence.json"
    issue_release(
        contract_path=phase6,
        authorization_path=auth_path,
        selection_path=selection,
        virginity_attestation_path=attestation,
        virginity_evidence_path=evidence,
        receipt_path=receipt,
        encrypted_bundle_path=bundle,
        key_path=key,
        output_path=release,
        receipt_evidence_path=receipt_evidence,
    )
    result_path = tmp_path / "result.json"
    result = evaluate_released_holdout(
        repository_root=ROOT,
        release_path=release,
        contract_path=phase6,
        authorization_path=auth_path,
        selection_path=selection,
        virginity_attestation_path=attestation,
        virginity_evidence_path=evidence,
        receipt_path=receipt,
        encrypted_bundle_path=bundle,
        key_path=key,
        marker_directory=private / "evaluation-markers",
        output_path=result_path,
    )
    assert result["status"] == "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"
    assert result["locked_symbols"] == list(symbols)
    assert result["methodology"] == "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v2"
    assert list(result["friction_cases"]) == ["0", "3", "10", "25", "50"]
    assert result["phase7_authorized"] is False
    assert result["recon009_status"] == "OPEN"

    marker = private / "evaluation-markers" / f"{result['release_id']}.consumed.json"
    closure_path = tmp_path / "closure.json"
    closure = close_phase6(
        contract_path=phase6,
        release_path=release,
        result_path=result_path,
        consumption_marker_path=marker,
        acquisition_receipt_path=receipt,
        output_path=closure_path,
    )
    assert closure["status"] == "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"
    assert closure["phase7"]["eligible_for_independent_entry_review"] is True
    assert closure["phase7"]["authorized"] is False
    assert closure["recon009_status"] == "OPEN"

    with pytest.raises(RuntimeError, match="SUCCESSOR_PHASE6_RELEASE_ALREADY_CONSUMED"):
        evaluate_released_holdout(
            repository_root=ROOT,
            release_path=release,
            contract_path=phase6,
            authorization_path=auth_path,
            selection_path=selection,
            virginity_attestation_path=attestation,
            virginity_evidence_path=evidence,
            receipt_path=receipt,
            encrypted_bundle_path=bundle,
            key_path=key,
            marker_directory=private / "evaluation-markers",
            output_path=tmp_path / "second-result.json",
        )
