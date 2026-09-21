from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import pytest

from investment_tracker.independent_audit.phase6.authority import (
    BENCHMARK_SYMBOL,
    CONTRACT_SHA256,
    HOLDOUT_END,
    HOLDOUT_START,
    LOCKED_SYMBOLS,
    SELECTED_BINDING_SHA256,
    SELECTED_CANDIDATE_ID,
    SELECTED_IMPLEMENTATION_SHA256,
)
from investment_tracker.independent_audit.phase6.bundle import (
    build_plain_bundle,
    encrypt_bundle,
)
from investment_tracker.independent_audit.phase6.evaluate import (
    evaluate_released_holdout,
)
from investment_tracker.independent_audit.phase6.opend_qfq import expected_sessions


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/phase6/phase6-evaluation-contract.json"


def _csv(symbol: str, sessions: pd.DatetimeIndex, offset: int) -> bytes:
    sequence = pd.Series(range(len(sessions)), dtype=float)
    growth = 0.00005 * (offset + 1)
    opens = 50.0 + offset + sequence * growth * 50.0
    closes = opens * (1.0 + growth)
    frame = pd.DataFrame(
        {
            "session": sessions.strftime("%Y-%m-%d"),
            "open": opens,
            "high": closes * 1.001,
            "low": opens * 0.999,
            "close": closes,
        }
    )
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")


def _fixture(tmp_path: Path):
    warmup, scored = expected_sessions()
    sessions = warmup.append(scored)
    symbols = (*LOCKED_SYMBOLS, BENCHMARK_SYMBOL)
    entries = {
        f"bars/{symbol}.csv": _csv(symbol, sessions, index)
        for index, symbol in enumerate(sorted(symbols))
    }
    manifest = {
        "schema_version": "PHASE6-SEALED-HOLDOUT-BUNDLE-v1",
        "authority": "INDEPENDENT_AUDIT",
        "provider": "MOOMOO_OPEND",
        "bar_type": "K_DAY",
        "bar_autype": "QFQ",
        "extended_time": False,
        "trading_context_created": False,
        "evaluation_contract_sha256": CONTRACT_SHA256,
        "locked_symbols": list(LOCKED_SYMBOLS),
        "benchmark_symbol": BENCHMARK_SYMBOL,
        "holdout_start": HOLDOUT_START,
        "holdout_end": HOLDOUT_END,
        "warmup_session_count": len(warmup),
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(LOCKED_SYMBOLS),
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "phase4_feedback_written": False,
        "phase5_feedback_written": False,
        "live_trading_capability": False,
        "phase7_started": False,
    }
    plaintext, _ = build_plain_bundle(manifest=manifest, entries=entries)
    encrypted, key = encrypt_bundle(
        plaintext,
        key=b"k" * 32,
        nonce=b"n" * 12,
    )
    holdout_id = "phase6-holdout-synthetic"
    bundle_path = tmp_path / "bundle.aesgcm"
    key_path = tmp_path / "bundle.key"
    receipt_path = tmp_path / "receipt.json"
    release_path = tmp_path / "release.json"
    bundle_path.write_bytes(encrypted)
    key_path.write_text(key.hex(), encoding="ascii")
    receipt = {
        "schema_version": "PHASE6-HOLDOUT-ACQUISITION-RECEIPT-v1",
        "authority": "INDEPENDENT_AUDIT",
        "status": "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED",
        "holdout_id": holdout_id,
        "evaluation_contract_sha256": CONTRACT_SHA256,
        "acquisition_authorization_sha256": "a" * 64,
        "candidate_id": SELECTED_CANDIDATE_ID,
        "binding_sha256": SELECTED_BINDING_SHA256,
        "implementation_sha256": SELECTED_IMPLEMENTATION_SHA256,
        "bundle_sha256": sha256(encrypted).hexdigest(),
        "plaintext_bundle_sha256": sha256(plaintext).hexdigest(),
        "key_sha256": sha256(key).hexdigest(),
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(LOCKED_SYMBOLS),
        "performance_computed": False,
        "performance_inspected": False,
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    release = {
        "schema_version": "PHASE6-HOLDOUT-RELEASE-v1",
        "authority": "INDEPENDENT_AUDIT",
        "status": "FINAL_HOLDOUT_RELEASE_AUTHORIZED",
        "release_id": "synthetic-release",
        "holdout_id": holdout_id,
        "candidate_id": SELECTED_CANDIDATE_ID,
        "binding_sha256": SELECTED_BINDING_SHA256,
        "implementation_sha256": SELECTED_IMPLEMENTATION_SHA256,
        "evaluation_contract_sha256": CONTRACT_SHA256,
        "holdout_bundle_sha256": sha256(encrypted).hexdigest(),
        "one_time": True,
    }
    release_path.write_text(json.dumps(release), encoding="utf-8")
    return release_path, receipt_path, bundle_path, key_path


def test_synthetic_bundle_runs_exact_frozen_engine_once(tmp_path: Path):
    release, receipt, bundle, key = _fixture(tmp_path)
    result = evaluate_released_holdout(
        release_path=release,
        contract_path=CONTRACT,
        receipt_path=receipt,
        encrypted_bundle_path=bundle,
        key_path=key,
        marker_directory=tmp_path / "markers",
        output_path=tmp_path / "result.json",
    )
    assert result["status"] == "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"
    assert result["candidate_id"] == SELECTED_CANDIDATE_ID
    assert result["binding_sha256"] == SELECTED_BINDING_SHA256
    assert result["decision_grade"] is False
    assert result["phase5_formal_status"] == "PHASE5_UNKNOWN_ABSTAIN"
    assert result["candidate_search_executed"] is False
    assert result["candidate_parameters_changed"] is False
    assert result["phase7_started"] is False
    assert (tmp_path / "markers" / "synthetic-release.consumed.json").is_file()

    with pytest.raises(Exception):
        evaluate_released_holdout(
            release_path=release,
            contract_path=CONTRACT,
            receipt_path=receipt,
            encrypted_bundle_path=bundle,
            key_path=key,
            marker_directory=tmp_path / "markers",
            output_path=tmp_path / "second-result.json",
        )


def test_bundle_hash_failure_after_marker_is_unknown_abstain(tmp_path: Path):
    release, receipt, bundle, key = _fixture(tmp_path)
    bundle.write_bytes(bundle.read_bytes() + b"tamper")
    result = evaluate_released_holdout(
        release_path=release,
        contract_path=CONTRACT,
        receipt_path=receipt,
        encrypted_bundle_path=bundle,
        key_path=key,
        marker_directory=tmp_path / "markers",
        output_path=tmp_path / "result.json",
    )
    assert result["status"] == "PHASE6_UNKNOWN_ABSTAIN"
    assert result["one_time_consumed"] is True
    assert (tmp_path / "markers" / "synthetic-release.consumed.json").is_file()
