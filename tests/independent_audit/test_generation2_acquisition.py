from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from investment_tracker.independent_audit.generation2 import acquisition as a

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/generation2/phase6/evaluation-contract.json"
AUTH = ROOT / "data/generation2/phase6/acquisition-authorization.json"
PREACCESS = ROOT / "data/generation2/preaccess/preaccess-status.json"
ATTESTATION = ROOT / "data/generation2/preaccess/virginity-attestation.json"
EVIDENCE = ROOT / "data/generation2/preaccess/virginity-evidence.json"
PROVENANCE = ROOT / "data/generation2/preaccess/provenance"
CLASSIFICATION = ROOT / "data/generation2/phase6/ci-classification.json"
AUTH_COMMIT = "51f077cc5acddd02a231567088f70a3c7bdb7d36"


def _kwargs(tmp_path: Path) -> dict:
    return dict(
        repository_root=ROOT,
        contract_path=CONTRACT,
        authorization_path=AUTH,
        preaccess_status_path=PREACCESS,
        attestation_path=ATTESTATION,
        evidence_path=EVIDENCE,
        provenance_root=PROVENANCE,
        ci_classification_path=CLASSIFICATION,
        authorization_commit_sha=AUTH_COMMIT,
        private_output_dir=tmp_path / "private",
    )


def test_committed_ci_classification_is_explicitly_not_green():
    value = a._verify_ci_classification(CLASSIFICATION, AUTH_COMMIT)
    assert value["full_suite"]["full_suite_green"] is False
    assert value["assessment"]["generic_suite_failure_waived_as_green"] is False
    assert value["assessment"]["generation2_regression_detected"] is False


def test_private_output_inside_repository_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="GEN2_PRIVATE_OUTPUT_MUST_BE_OUTSIDE_REPOSITORY"):
        a.acquire_and_seal(
            **{**_kwargs(tmp_path), "private_output_dir": ROOT / ".runtime" / "forbidden"}
        )


def test_preflight_sdk_failure_does_not_consume_authorization(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(a, "_load_sdk", lambda: (_ for _ in ()).throw(RuntimeError("SDK_PREFLIGHT_STOP")))
    with pytest.raises(RuntimeError, match="SDK_PREFLIGHT_STOP"):
        a.acquire_and_seal(**_kwargs(tmp_path))
    assert not list((tmp_path / "private").glob("*.acquisition-start.json"))


def test_sdk_capability_check_is_fail_closed():
    bad = SimpleNamespace(OpenQuoteContext=object, AuType=SimpleNamespace(QFQ=1), KLType=SimpleNamespace(K_DAY=1))
    with pytest.raises(RuntimeError, match="GEN2_ACQUISITION_SDK_CAPABILITY_MISSING"):
        a._verify_sdk_capabilities(bad)


def test_quota_preflight_rejects_locked_symbol_access():
    class Ctx:
        def get_history_kl_quota(self, get_detail=True):
            return 0, (1, 299, [{"code": "US.BNO", "name": "x", "request_time": "now"}])
    sdk = SimpleNamespace(RET_OK=0)
    with pytest.raises(RuntimeError, match="GEN2_ACQUISITION_VIRGINITY_RECHECK_FAILED"):
        a._provider_quota_preflight(Ctx(), sdk)


def test_quota_preflight_rejects_insufficient_capacity():
    class Ctx:
        def get_history_kl_quota(self, get_detail=True):
            return 0, (299, 1, [])
    sdk = SimpleNamespace(RET_OK=0)
    with pytest.raises(RuntimeError, match="GEN2_ACQUISITION_QUOTA_INSUFFICIENT"):
        a._provider_quota_preflight(Ctx(), sdk)


def test_marker_is_sealed_before_first_historical_request(monkeypatch, tmp_path: Path):
    contexts = []

    class PreflightContext:
        def close(self):
            pass

    class AcquisitionContext:
        def request_history_kline(self, *args, **kwargs):
            marker = next((tmp_path / "private").glob("*.acquisition-start.json"))
            payload = json.loads(marker.read_text(encoding="utf-8"))
            assert payload["historical_access_started"] is True
            assert payload["retry_allowed_after_historical_access"] is False
            raise RuntimeError("STOP_AT_FIRST_HISTORY")

        def close(self):
            pass

    def make_context(*args, **kwargs):
        ctx = PreflightContext() if not contexts else AcquisitionContext()
        contexts.append(ctx)
        return ctx

    sdk = SimpleNamespace(
        OpenQuoteContext=make_context,
        RET_OK=0,
        AuType=SimpleNamespace(QFQ="QFQ", NONE="NONE"),
        KLType=SimpleNamespace(K_DAY="K_DAY"),
        __version__="test",
    )
    monkeypatch.setattr(a, "_load_sdk", lambda: (sdk, "fake"))
    monkeypatch.setattr(a, "_verify_sdk_capabilities", lambda sdk: None)
    monkeypatch.setattr(a, "_provider_quota_preflight", lambda context, sdk: {"used": 0, "remaining": 300, "locked_matches": []})

    with pytest.raises(RuntimeError, match="STOP_AT_FIRST_HISTORY"):
        a.acquire_and_seal(**_kwargs(tmp_path))


def test_existing_start_marker_prevents_second_historical_attempt(monkeypatch, tmp_path: Path):
    contexts = []

    class Ctx:
        def request_history_kline(self, *args, **kwargs):
            raise RuntimeError("FIRST_HISTORY_STOP")
        def close(self):
            pass

    def make_context(*args, **kwargs):
        ctx = Ctx()
        contexts.append(ctx)
        return ctx

    sdk = SimpleNamespace(
        OpenQuoteContext=make_context,
        RET_OK=0,
        AuType=SimpleNamespace(QFQ="QFQ", NONE="NONE"),
        KLType=SimpleNamespace(K_DAY="K_DAY"),
        __version__="test",
    )
    monkeypatch.setattr(a, "_load_sdk", lambda: (sdk, "fake"))
    monkeypatch.setattr(a, "_verify_sdk_capabilities", lambda sdk: None)
    monkeypatch.setattr(a, "_provider_quota_preflight", lambda context, sdk: {"used": 0, "remaining": 300, "locked_matches": []})

    with pytest.raises(RuntimeError, match="FIRST_HISTORY_STOP"):
        a.acquire_and_seal(**_kwargs(tmp_path))

    calls_before = len(contexts)
    with pytest.raises(RuntimeError, match="GEN2_ACQUISITION_AUTHORIZATION_ALREADY_CONSUMED"):
        a.acquire_and_seal(**_kwargs(tmp_path))
    assert len(contexts) == calls_before + 1  # harmless quota-preflight context only


def test_tampered_ci_classification_stops_before_sdk(monkeypatch, tmp_path: Path):
    value = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    value["assessment"]["generation2_regression_detected"] = True
    bad = tmp_path / "bad-classification.json"
    bad.write_text(json.dumps(value), encoding="utf-8")
    called = False

    def forbidden():
        nonlocal called
        called = True
        raise AssertionError("SDK must not load")

    monkeypatch.setattr(a, "_load_sdk", forbidden)
    with pytest.raises(ValueError, match="GEN2_ACQUISITION_CI_CLASSIFICATION_INVALID"):
        a.acquire_and_seal(**{**_kwargs(tmp_path), "ci_classification_path": bad})
    assert called is False


def test_expected_sessions_match_frozen_contract():
    contract = a.verify_contract(CONTRACT)
    warmup, scored = a.expected_sessions(contract)
    assert len(warmup) == 210
    assert scored[0].date().isoformat() >= "2023-01-01"
    assert scored[-1].date().isoformat() <= "2025-12-31"
    assert warmup[-1] < scored[0]


def test_safe_preflight_never_creates_consumption_marker(monkeypatch, tmp_path: Path):
    class Ctx:
        def close(self):
            pass
    sdk = SimpleNamespace(
        OpenQuoteContext=lambda *args, **kwargs: Ctx(),
        RET_OK=0,
        AuType=SimpleNamespace(QFQ="QFQ", NONE="NONE"),
        KLType=SimpleNamespace(K_DAY="K_DAY"),
        __version__="test",
    )
    monkeypatch.setattr(a, "_load_sdk", lambda: (sdk, "fake"))
    monkeypatch.setattr(a, "_verify_sdk_capabilities", lambda sdk: None)
    monkeypatch.setattr(a, "_provider_quota_preflight", lambda context, sdk: {"used": 14, "remaining": 286, "locked_matches": []})
    result = a.preflight_acquisition(
        repository_root=ROOT,
        contract_path=CONTRACT,
        authorization_path=AUTH,
        preaccess_status_path=PREACCESS,
        attestation_path=ATTESTATION,
        evidence_path=EVIDENCE,
        provenance_root=PROVENANCE,
        ci_classification_path=CLASSIFICATION,
        authorization_commit_sha=AUTH_COMMIT,
    )
    assert result["status"] == "GEN2_ACQUISITION_PREFLIGHT_READY"
    assert result["historical_market_data_api_called"] is False
    assert result["historical_access_consumed"] is False
    assert not list(tmp_path.glob("*.acquisition-start.json"))


def test_successful_acquisition_seals_and_reads_back_every_private_artifact(
    monkeypatch, tmp_path: Path
):
    sessions = a.pd.DatetimeIndex(
        ["2022-12-30", "2023-01-03", "2023-01-04"], tz="UTC"
    )
    contexts = []

    class Context:
        def get_history_kl_quota(self, get_detail=True):
            return 0, (14, 286, [])

        def request_history_kline(self, code, **kwargs):
            frame = a.pd.DataFrame(
                {
                    "time_key": sessions.strftime("%Y-%m-%d"),
                    "open": [100.0, 101.0, 102.0],
                    "high": [101.0, 102.0, 103.0],
                    "low": [99.0, 100.0, 101.0],
                    "close": [100.5, 101.5, 102.5],
                }
            )
            return 0, frame, None

        def get_rehab(self, code):
            return 0, a.pd.DataFrame(columns=["ex_div_date"])

        def get_corporate_actions_dividends(self, code):
            return 0, {"dividend_list": []}

        def get_corporate_actions_stock_splits(self, code, next_key=None, num=50):
            return 0, {"split_list": [], "next_key": "-1"}

        def close(self):
            pass

    def make_context(*args, **kwargs):
        context = Context()
        contexts.append(context)
        return context

    sdk = SimpleNamespace(
        OpenQuoteContext=make_context,
        RET_OK=0,
        AuType=SimpleNamespace(QFQ="QFQ", NONE="NONE"),
        KLType=SimpleNamespace(K_DAY="K_DAY"),
        __version__="test",
    )
    monkeypatch.setattr(a, "_load_sdk", lambda: (sdk, "fake"))
    monkeypatch.setattr(a, "_verify_sdk_capabilities", lambda sdk: None)
    monkeypatch.setattr(a, "expected_sessions", lambda contract: (sessions[:1], sessions[1:]))

    receipt_path = a.acquire_and_seal(**_kwargs(tmp_path))
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    private = tmp_path / "private"
    bundle = private / f"{receipt['holdout_id']}.bundle.aesgcm"
    key = private / f"{receipt['holdout_id']}.key"
    marker = private / "gen2-phase6-acquire-484f902659d0dfc58f521ff5cd98b05c.acquisition-start.json"

    assert receipt["bundle_sha256"] == sha256(bundle.read_bytes()).hexdigest()
    assert receipt["key_sha256"] == sha256(bytes.fromhex(key.read_text(encoding="ascii"))).hexdigest()
    assert receipt["artifact_readback_verified"] is True
    assert receipt["receipt_sha256"] == sha256(
        a._canonical_bytes({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    ).hexdigest()
    marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    assert marker_payload["status"] == "FINAL_HOLDOUT_ACQUISITION_SEALED"
    assert marker_payload["artifact_readback_verified"] is True
    assert marker_payload["receipt_sha256"] == sha256(receipt_bytes).hexdigest()
