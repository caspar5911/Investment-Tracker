from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path

import pandas as pd
import pytest

from investment_tracker.independent_audit.generation2 import acquisition as a
from investment_tracker.independent_audit.generation2 import evaluate as e
from investment_tracker.independent_audit.generation2.evaluate import (
    evaluate_released_holdout,
)
from investment_tracker.independent_audit.generation2.release import issue_release, load_release


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/generation2/phase6/evaluation-contract.json"
AUTH = ROOT / "data/generation2/phase6/acquisition-authorization.json"
LOCKED = ("BNO", "GBIL", "CWS", "ESG", "VICI")


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
        [value * (1.0 + 0.003 * math.sin(index / 3.0 + offset)) for index, value in enumerate(closes)]
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
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    contract = a.verify_contract(CONTRACT)
    warmup, scored = a.expected_sessions(contract)
    sessions = warmup.append(scored)
    symbols = (*LOCKED, "SPY")
    entries: dict[str, bytes] = {}
    for offset, symbol in enumerate(symbols):
        payload = _bars(sessions, offset)
        entries[f"bars/qfq/{symbol}.csv"] = payload
        entries[f"bars/unadjusted/{symbol}.csv"] = payload
        entries[f"corporate_actions/rehab/{symbol}.csv"] = b"ex_div_date\n"
        entries[f"corporate_actions/dividends/{symbol}.json"] = b'{"dividend_list":[]}'
        entries[f"corporate_actions/splits/{symbol}.json"] = b'{"split_list":[]}'
    manifest = {
        "schema_version": a.SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "provider": "MOOMOO_OPEND",
        "sdk_module": "synthetic",
        "sdk_version": "test",
        "evaluation_contract_sha256": contract["contract_sha256"],
        "evaluation_contract_file_sha256": sha256(CONTRACT.read_bytes()).hexdigest(),
        "acquisition_authorization_sha256": sha256(AUTH.read_bytes()).hexdigest(),
        "authorization_commit_sha": "51f077cc5acddd02a231567088f70a3c7bdb7d36",
        "ci_classification_sha256": "c" * 64,
        "locked_symbols": list(LOCKED),
        "benchmark_reference_symbol": "SPY",
        "signal_price_convention": "MOOMOO_QFQ_DAILY_RTH",
        "execution_price_convention": "MOOMOO_UNADJUSTED_DAILY_RTH",
        "corporate_action_sources": [
            "MOOMOO_REHAB",
            "MOOMOO_CORPORATE_ACTION_DIVIDENDS",
            "MOOMOO_CORPORATE_ACTION_STOCK_SPLITS",
        ],
        "requested_start": warmup[0].date().isoformat(),
        "requested_end": "2025-12-31",
        "holdout_start": "2023-01-01",
        "holdout_end": "2025-12-31",
        "warmup_session_count": 210,
        "scored_session_count": len(scored),
        "warmup_first_session": warmup[0].date().isoformat(),
        "warmup_last_session": warmup[-1].date().isoformat(),
        "scored_first_session": scored[0].date().isoformat(),
        "scored_last_session": scored[-1].date().isoformat(),
        "retrieved_at_utc": "2026-09-22T00:00:00+00:00",
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(LOCKED),
        "performance_computed": False,
        "performance_inspected": False,
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "phase7_started": False,
        "live_trading_capability": False,
    }
    plaintext, full_manifest = a._build_plain_bundle(manifest, entries)
    encrypted, key = a._encrypt(plaintext, contract["contract_sha256"])
    holdout_id = f"gen2-phase6-holdout-{sha256(plaintext).hexdigest()[:32]}"
    private = tmp_path / "private"
    private.mkdir()
    bundle = private / f"{holdout_id}.bundle.aesgcm"
    key_path = private / f"{holdout_id}.key"
    receipt = private / f"{holdout_id}.receipt.json"
    bundle.write_bytes(encrypted)
    key_path.write_text(key.hex(), encoding="ascii")
    receipt_payload = {
        "schema_version": a.RECEIPT_SCHEMA,
        "authority": "INDEPENDENT_AUDIT",
        "status": "SEALED_FINAL_HOLDOUT_BUNDLE_CREATED",
        "holdout_id": holdout_id,
        "evaluation_contract_sha256": contract["contract_sha256"],
        "acquisition_authorization_sha256": sha256(AUTH.read_bytes()).hexdigest(),
        "authorization_commit_sha": "51f077cc5acddd02a231567088f70a3c7bdb7d36",
        "candidate_id": contract["strategy"]["candidate_id"],
        "binding_sha256": contract["strategy"]["binding_sha256"],
        "implementation_sha256": contract["strategy"]["implementation_sha256"],
        "bundle_sha256": sha256(encrypted).hexdigest(),
        "plaintext_bundle_sha256": sha256(plaintext).hexdigest(),
        "bundle_manifest_sha256": sha256(a._canonical_bytes(full_manifest)).hexdigest(),
        "key_sha256": sha256(key).hexdigest(),
        "bundle_bytes": len(encrypted),
        "provider": "MOOMOO_OPEND",
        "requested_start": warmup[0].date().isoformat(),
        "requested_end": "2025-12-31",
        "holdout_start": "2023-01-01",
        "holdout_end": "2025-12-31",
        "warmup_session_count": 210,
        "scored_session_count": len(scored),
        "retrieved_at_utc": "2026-09-22T00:00:00+00:00",
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(LOCKED),
        "performance_computed": False,
        "performance_inspected": False,
        "retry_allowed": False,
        "artifact_readback_verified": True,
    }
    receipt_payload["receipt_sha256"] = sha256(a._canonical_bytes(receipt_payload)).hexdigest()
    receipt.write_bytes(a._canonical_bytes(receipt_payload))
    return receipt, bundle, key_path, private


def test_release_validates_artifacts_and_publishes_non_market_receipt(tmp_path: Path):
    receipt, bundle, key, _ = _fixture(tmp_path)
    release = tmp_path / "generation2-phase6-release.json"
    evidence_receipt = tmp_path / "generation2-phase6-acquisition-receipt.json"

    issue_release(
        contract_path=CONTRACT,
        authorization_path=AUTH,
        receipt_path=receipt,
        encrypted_bundle_path=bundle,
        key_path=key,
        output_path=release,
        receipt_evidence_path=evidence_receipt,
    )

    payload = json.loads(release.read_text(encoding="utf-8"))
    assert payload["status"] == "FINAL_HOLDOUT_RELEASE_AUTHORIZED"
    assert payload["candidate_id"] == "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
    assert payload["one_time"] is True
    assert evidence_receipt.read_bytes() == receipt.read_bytes()


def test_one_time_frozen_evaluation_uses_exact_friction_and_dq030(tmp_path: Path):
    receipt, bundle, key, private = _fixture(tmp_path)
    release = tmp_path / "release.json"
    issue_release(
        contract_path=CONTRACT,
        authorization_path=AUTH,
        receipt_path=receipt,
        encrypted_bundle_path=bundle,
        key_path=key,
        output_path=release,
        receipt_evidence_path=tmp_path / "receipt-evidence.json",
    )
    result_path = tmp_path / "generation2-phase6-result.json"

    result = evaluate_released_holdout(
        release_path=release,
        contract_path=CONTRACT,
        receipt_path=receipt,
        encrypted_bundle_path=bundle,
        key_path=key,
        marker_directory=private / "evaluation-markers",
        output_path=result_path,
    )

    assert result["status"] == "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE"
    assert result["candidate_id"] == "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"
    assert list(result["friction_cases"]) == ["0", "3", "10", "25", "50"]
    assert result["primary_friction_bps"] == 3
    assert result["metrics"]["max_drawdown"]["status"] == "AVAILABLE"
    assert result["methodology"] == "UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1"
    assert result["signal_price_convention"] == "MOOMOO_QFQ_DAILY_RTH"
    assert result["execution_price_convention"] == "MOOMOO_UNADJUSTED_DAILY_RTH"
    assert result["phase7_authorized"] is False
    assert result["recon009_status"] == "OPEN"
    marker = private / "evaluation-markers" / f"{result['release_id']}.consumed.json"
    assert marker.is_file()

    with pytest.raises(RuntimeError, match="GEN2_PHASE6_RELEASE_ALREADY_CONSUMED"):
        evaluate_released_holdout(
            release_path=release,
            contract_path=CONTRACT,
            receipt_path=receipt,
            encrypted_bundle_path=bundle,
            key_path=key,
            marker_directory=private / "evaluation-markers",
            output_path=tmp_path / "second-result.json",
        )


def test_release_id_is_recomputed_and_cannot_create_a_second_consumption_slot(tmp_path: Path):
    receipt, bundle, key, _ = _fixture(tmp_path)
    release = tmp_path / "release.json"
    issue_release(
        contract_path=CONTRACT,
        authorization_path=AUTH,
        receipt_path=receipt,
        encrypted_bundle_path=bundle,
        key_path=key,
        output_path=release,
        receipt_evidence_path=tmp_path / "receipt-evidence.json",
    )
    payload = json.loads(release.read_text(encoding="utf-8"))
    payload["release_id"] = "gen2-phase6-release-arbitrary-retry"
    release.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="GEN2_PHASE6_RELEASE_ID_MISMATCH"):
        load_release(release, contract_path=CONTRACT)


def test_evaluation_marker_directory_is_canonical_to_private_artifacts(tmp_path: Path):
    receipt, bundle, key, private = _fixture(tmp_path)
    release = tmp_path / "release.json"
    issue_release(
        contract_path=CONTRACT,
        authorization_path=AUTH,
        receipt_path=receipt,
        encrypted_bundle_path=bundle,
        key_path=key,
        output_path=release,
        receipt_evidence_path=tmp_path / "receipt-evidence.json",
    )
    with pytest.raises(ValueError, match="GEN2_PHASE6_MARKER_DIRECTORY_INVALID"):
        evaluate_released_holdout(
            release_path=release,
            contract_path=CONTRACT,
            receipt_path=receipt,
            encrypted_bundle_path=bundle,
            key_path=key,
            marker_directory=tmp_path / "alternate-markers",
            output_path=tmp_path / "result.json",
        )
    assert not list((tmp_path / "alternate-markers").glob("*.json"))


def _action_entries(
    *, rehab: str = "ex_div_date\n", dividends: list[dict] | None = None, splits: list[dict] | None = None
) -> dict[str, bytes]:
    return {
        "corporate_actions/rehab/BNO.csv": rehab.encode(),
        "corporate_actions/dividends/BNO.json": json.dumps(
            {"dividend_list": dividends or []}, separators=(",", ":")
        ).encode(),
        "corporate_actions/splits/BNO.json": json.dumps(
            {"split_list": splits or []}, separators=(",", ":")
        ).encode(),
    }


def test_dated_split_endpoint_without_rehab_match_fails_closed():
    scored = pd.bdate_range("2023-01-03", periods=5, tz="UTC")
    entries = _action_entries(
        splits=[{"ex_date_str": "2023-01-04", "rate": "1->2", "reform_type": "Split"}]
    )
    with pytest.raises(ValueError, match="GEN2_PHASE6_SPLIT_SOURCE_RECONCILIATION_FAILED"):
        e._corporate_actions(entries, "BNO", scored)


def test_ambiguous_dividend_statement_amount_fails_closed():
    scored = pd.bdate_range("2023-01-03", periods=5, tz="UTC")
    entries = _action_entries(
        rehab="ex_div_date,per_cash_div\n2023-01-04,1\n",
        dividends=[
            {
                "ex_date": "2023/01/04",
                "dividend_payable_date": "2023/01/06",
                "statement": "Cash Dividend: 1 USD; Cash Dividend: 2 USD",
            }
        ],
    )
    with pytest.raises(ValueError, match="GEN2_PHASE6_DIVIDEND_AMOUNT_AMBIGUOUS"):
        e._corporate_actions(entries, "BNO", scored)


@pytest.mark.parametrize(
    ("rehab", "dividends", "reason"),
    [
        (
            "ex_div_date,per_cash_div\n2023-01-07,1\n",
            [{"ex_date": "2023/01/07", "dividend_payable_date": "2023/01/09", "statement": "Cash Dividend: 1 USD Per Share"}],
            "GEN2_PHASE6_CORPORATE_ACTION_SESSION_INVALID",
        ),
        (
            "ex_div_date,per_cash_div\n2023-01-04,1\n",
            [{"ex_date": "2023/01/04", "dividend_payable_date": "2023/01/03", "statement": "Cash Dividend: 1 USD Per Share"}],
            "GEN2_PHASE6_DIVIDEND_PAY_DATE_INVALID",
        ),
    ],
)
def test_invalid_corporate_action_dates_fail_closed(rehab: str, dividends: list[dict], reason: str):
    scored = pd.bdate_range("2023-01-03", periods=5, tz="UTC")
    with pytest.raises(ValueError, match=reason):
        e._corporate_actions(_action_entries(rehab=rehab, dividends=dividends), "BNO", scored)


def test_implementation_identity_is_verified_before_consumption(monkeypatch, tmp_path: Path):
    receipt, bundle, key, private = _fixture(tmp_path)
    release = tmp_path / "release.json"
    issue_release(
        contract_path=CONTRACT,
        authorization_path=AUTH,
        receipt_path=receipt,
        encrypted_bundle_path=bundle,
        key_path=key,
        output_path=release,
        receipt_evidence_path=tmp_path / "receipt-evidence.json",
    )
    monkeypatch.setattr(
        e,
        "_verify_executing_implementation",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("SOURCE_DRIFT")),
    )
    markers = private / "evaluation-markers"
    with pytest.raises(ValueError, match="SOURCE_DRIFT"):
        evaluate_released_holdout(
            release_path=release,
            contract_path=CONTRACT,
            receipt_path=receipt,
            encrypted_bundle_path=bundle,
            key_path=key,
            marker_directory=markers,
            output_path=tmp_path / "result.json",
        )
    assert not list(markers.glob("*.json"))
