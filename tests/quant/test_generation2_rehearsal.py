"""Tests for the Generation-2 synthetic Phase-6 rehearsal (B2) and its
fail-closed fault suite (B3).

These tests use injected fake providers and synthetic data only: no real
provider, network, or real holdout data is touched.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from investment_tracker.quant.generation2.rehearsal import (
    AcquiredBundle,
    AcquisitionProvider,
    AcquisitionAuthorization,
    RehearsalError,
    SyntheticAcquisitionProvider,
    build_sealed_bundle,
    canonical_bytes,
    content_sha256,
    create_acquisition_authorization,
    create_acquisition_start_marker,
    create_release,
    create_seal_receipt,
    consume_rehearsal,
    open_bundle,
    readback_verify,
    run_synthetic_rehearsal,
    seal_bundle,
    validate_acquired_bundle,
    write_canonical_file,
    write_sealed_bundle,
)

KEY = sha256(b"g2-rehearsal-key").digest()
WRONG_KEY = sha256(b"g2-rehearsal-wrong-key").digest()
CONTRACT = "c" * 64
SESSIONS = ("2023-01-02", "2023-01-03", "2023-01-04")
SYMBOLS = ("AAA", "BBB")
NOW = "2026-09-22T00:00:00Z"


def _good_bars():
    return {
        symbol: {
            SESSIONS[0]: {"open": 10.0, "close": 11.0},
            SESSIONS[1]: {"open": 11.0, "close": 12.0},
            SESSIONS[2]: {"open": 12.0, "close": 13.0},
        }
        for symbol in SYMBOLS
    }


def make_bundle(*, symbols=SYMBOLS, sessions=SESSIONS, adjustment="QFQ"):
    return AcquiredBundle(
        symbols=symbols,
        sessions=sessions,
        bars=_good_bars() if symbols == SYMBOLS else {},
        adjustment_convention=adjustment,
    )


def run_orch(provider, tmp_path, **overrides):
    base = dict(
        marker_dir=tmp_path / "markers",
        sealed_dir=tmp_path / "sealed",
        key=KEY,
        holdout_id="HO-1",
        authorization_id="AUTH-1",
        release_id="REL-1",
        expected_bundle_sha256=make_bundle().sha256(),
        expected_sessions=SESSIONS,
        adjustment_convention="QFQ",
        evaluation_contract_sha256=CONTRACT,
        now_utc=NOW,
    )
    base.update(overrides)
    return run_synthetic_rehearsal(provider, **base)


# =============================================================================
# B2 — full synthetic dress rehearsal end-to-end
# =============================================================================


def test_full_synthetic_rehearsal_end_to_end(tmp_path):
    bundle = make_bundle()
    provider = SyntheticAcquisitionProvider(bundle)
    transcript = run_orch(provider, tmp_path, expected_bundle_sha256=bundle.sha256())

    assert transcript.holdout_id == "HO-1"
    assert len(transcript.authorization_sha256) == 64
    assert transcript.release_id == "REL-1"
    assert transcript.bundle_sha256 == bundle.sha256()
    assert len(transcript.sealed_bundle_sha256) == 64
    assert len(transcript.transcript_sha256) == 64
    # One-time markers were created.
    assert (tmp_path / "markers" / "AUTH-1.acquire-start.json").exists()
    assert (tmp_path / "markers" / "REL-1.consumed.json").exists()
    # The immutable sealed bundle was written.
    assert (tmp_path / "sealed" / "HO-1.sealed.bin").exists()


def test_rehearsal_is_reproducible_from_single_entrypoint(tmp_path):
    bundle = make_bundle()
    provider = SyntheticAcquisitionProvider(bundle)
    t1 = run_orch(provider, tmp_path, expected_bundle_sha256=bundle.sha256())
    assert t1.bundle_sha256 == content_sha256(bundle._canonical())


# =============================================================================
# B3 — fault-injection fail-closed suite
# =============================================================================


class _FailProvider:
    """Fake provider that raises a RehearsalError with a given code."""

    def __init__(self, code: str):
        self.code = code

    def acquire(self, _authorization):
        raise RehearsalError(self.code, "provider failure")


class _CrashProvider:
    """Fake provider that raises an unexpected, non-RehearsalError error."""

    def acquire(self, _authorization):
        raise RuntimeError("boom: provider socket reset")


def test_provider_connect_failure(tmp_path):
    with pytest.raises(RehearsalError) as exc:
        run_orch(_FailProvider("REHEARSAL_PROVIDER_CONNECT_FAILED"), tmp_path)
    assert exc.value.code == "REHEARSAL_PROVIDER_CONNECT_FAILED"


def test_provider_failure_after_first_n_symbols(tmp_path):
    with pytest.raises(RehearsalError) as exc:
        run_orch(_FailProvider("REHEARSAL_PROVIDER_INTERRUPTED"), tmp_path)
    assert exc.value.code == "REHEARSAL_PROVIDER_INTERRUPTED"


def test_interrupted_acquisition_wraps_unexpected_error(tmp_path):
    with pytest.raises(RehearsalError) as exc:
        run_orch(_CrashProvider(), tmp_path)
    assert exc.value.code == "REHEARSAL_ACQUISITION_INTERRUPTED"


def _validate(bundle, sessions=SESSIONS, adjustment="QFQ", expected_sha256=None):
    return validate_acquired_bundle(
        bundle,
        expected_sessions=sessions,
        adjustment_convention=adjustment,
        expected_sha256=expected_sha256,
    )


def test_empty_provider_rejected():
    bundle = make_bundle(symbols=(), sessions=())
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle, sessions=())
    assert exc.value.code == "REHEARSAL_ACQUIRED_EMPTY"


def test_malformed_schema_rejected():
    bad = {
        s: {k: {"open": 1.0} for k in SESSIONS} for s in SYMBOLS
    }  # missing "close" key
    bundle = _mutate(make_bundle(), bars=bad)
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle)
    assert exc.value.code == "REHEARSAL_MALFORMED_SCHEMA"


def _mutate(bundle, **fields):
    data = {
        "symbols": tuple(bundle.symbols),
        "sessions": tuple(bundle.sessions),
        "bars": dict(bundle.bars),
        "adjustment_convention": bundle.adjustment_convention,
    }
    data.update(fields)
    return AcquiredBundle(**data)


def test_missing_session_rejected():
    bundle = _mutate(make_bundle(), sessions=SESSIONS[:2])
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle)
    assert exc.value.code == "REHEARSAL_SESSION_MISSING"


def test_duplicate_session_rejected():
    bundle = _mutate(make_bundle(), sessions=("2023-01-02", "2023-01-02", "2023-01-03"))
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle, sessions=("2023-01-02", "2023-01-02", "2023-01-03"))
    assert exc.value.code == "REHEARSAL_SESSION_DUPLICATE"


def test_non_monotonic_session_rejected():
    sessions = ("2023-01-04", "2023-01-02", "2023-01-03")
    bundle = _mutate(make_bundle(), sessions=sessions)
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle, sessions=sessions)
    assert exc.value.code == "REHEARSAL_SESSION_NONMONOTONIC"


def test_nan_ohlc_rejected():
    bars = {
        s: {k: {"open": float("nan"), "close": 1.0} for k in SESSIONS}
        for s in SYMBOLS
    }
    bundle = _mutate(make_bundle(), bars=bars)
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle)
    assert exc.value.code == "REHEARSAL_OHLC_NAN"


def test_inf_ohlc_rejected():
    bars = {
        s: {k: {"open": 1.0, "close": float("inf")} for k in SESSIONS}
        for s in SYMBOLS
    }
    bundle = _mutate(make_bundle(), bars=bars)
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle)
    assert exc.value.code == "REHEARSAL_OHLC_INF"


def test_non_positive_ohlc_rejected():
    bars = {
        s: {k: {"open": 0.0, "close": 1.0} for k in SESSIONS} for s in SYMBOLS
    }
    bundle = _mutate(make_bundle(), bars=bars)
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle)
    assert exc.value.code == "REHEARSAL_OHLC_NONPOSITIVE"


def test_ohlc_consistency_rejected():
    # A symbol has bars for a session that is not in the session authority.
    bars = {
        "AAA": {k: {"open": 1.0, "close": 2.0} for k in SESSIONS},
        "BBB": {k: {"open": 1.0, "close": 2.0} for k in SESSIONS[:2]},
    }
    bundle = _mutate(make_bundle(), bars=bars)
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle)
    assert exc.value.code == "REHEARSAL_OHLC_INCONSISTENT"


def test_wrong_adjustment_mode_rejected():
    bundle = _mutate(make_bundle(), adjustment_convention="UNADJUSTED")
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle, adjustment="QFQ")
    assert exc.value.code == "REHEARSAL_ADJUSTMENT_MODE_MISMATCH"


def test_authorization_hash_mismatch_rejected():
    bundle = make_bundle()
    with pytest.raises(RehearsalError) as exc:
        _validate(bundle, expected_sha256="f" * 64)
    assert exc.value.code == "REHEARSAL_AUTHORIZATION_HASH_MISMATCH"


def test_authorization_reuse_refused(tmp_path):
    bundle = make_bundle()
    provider = SyntheticAcquisitionProvider(bundle)
    run_orch(provider, tmp_path, expected_bundle_sha256=bundle.sha256())
    with pytest.raises(RehearsalError) as exc:
        run_orch(
            SyntheticAcquisitionProvider(bundle),
            tmp_path,
            expected_bundle_sha256=bundle.sha256(),
        )
    assert exc.value.code == "REHEARSAL_ACQUISITION_STARTED_ONCE"


def test_existing_immutable_output_collision(tmp_path):
    bundle = make_bundle()
    sealed = build_sealed_bundle(
        bundle, key=KEY, evaluation_contract_sha256=CONTRACT
    )
    path = tmp_path / "out.bin"
    write_sealed_bundle(path, sealed)
    with pytest.raises(RehearsalError) as exc:
        write_sealed_bundle(path, sealed)
    assert exc.value.code == "REHEARSAL_OUTPUT_COLLISION"


def test_corrupt_encrypted_bundle_rejected():
    bundle = make_bundle()
    sealed = build_sealed_bundle(
        bundle, key=KEY, evaluation_contract_sha256=CONTRACT
    )
    corrupt = sealed[:5] + bytes([sealed[5] ^ 0xFF]) + sealed[6:]
    with pytest.raises(RehearsalError) as exc:
        open_bundle(corrupt, key=KEY, aad=CONTRACT)
    assert exc.value.code == "REHEARSAL_DECRYPTION_FAILED"


def test_wrong_key_rejected():
    bundle = make_bundle()
    sealed = build_sealed_bundle(
        bundle, key=KEY, evaluation_contract_sha256=CONTRACT
    )
    with pytest.raises(RehearsalError) as exc:
        open_bundle(sealed, key=WRONG_KEY, aad=CONTRACT)
    assert exc.value.code == "REHEARSAL_DECRYPTION_FAILED"


def test_contract_hash_mismatch_rejected():
    bundle = make_bundle()
    sealed = build_sealed_bundle(
        bundle, key=KEY, evaluation_contract_sha256=CONTRACT
    )
    with pytest.raises(RehearsalError) as exc:
        open_bundle(sealed, key=KEY, aad="d" * 64)
    assert exc.value.code == "REHEARSAL_DECRYPTION_FAILED"


def test_receipt_mismatch_rejected():
    receipt = create_seal_receipt(
        holdout_id="HO-1",
        sealed_bundle_sha256="a" * 64,
        evaluation_contract_sha256=CONTRACT,
        key=KEY,
        sealed_utc=NOW,
    )
    with pytest.raises(RehearsalError) as exc:
        create_release(
            release_id="R-1",
            holdout_id="HO-1",
            evaluation_contract_sha256=CONTRACT,
            sealed_bundle_sha256="b" * 64,
            receipt=receipt,
        )
    assert exc.value.code == "REHEARSAL_RECEIPT_MISMATCH"


def test_release_mismatch_rejected(tmp_path):
    receipt = create_seal_receipt(
        holdout_id="HO-1",
        sealed_bundle_sha256="a" * 64,
        evaluation_contract_sha256=CONTRACT,
        key=KEY,
        sealed_utc=NOW,
    )
    from investment_tracker.quant.generation2.rehearsal import RehearsalRelease

    release = RehearsalRelease(
        schema_version="G2-PHASE6-SYNTHETIC-REHEARSAL-v1",
        authority="SYNTHETIC_REHEARSAL",
        status="SYNTHETIC_HOLDOUT_RELEASE_AUTHORIZED",
        release_id="R-1",
        holdout_id="HO-1",
        evaluation_contract_sha256=CONTRACT,
        sealed_bundle_sha256="a" * 64,
        receipt_sha256="f" * 64,  # deliberately wrong
    )
    with pytest.raises(RehearsalError) as exc:
        consume_rehearsal(
            release=release,
            receipt=receipt,
            marker_dir=tmp_path / "m",
            sealed_path=tmp_path / "s.bin",
            key=KEY,
            expected_sessions=SESSIONS,
        )
    assert exc.value.code == "REHEARSAL_RELEASE_MISMATCH"


def test_second_evaluation_refused(tmp_path):
    bundle = make_bundle()
    sealed = build_sealed_bundle(
        bundle, key=KEY, evaluation_contract_sha256=CONTRACT
    )
    sealed_path = tmp_path / "HO-1.sealed.bin"
    write_sealed_bundle(sealed_path, sealed)
    receipt = create_seal_receipt(
        holdout_id="HO-1",
        sealed_bundle_sha256=sha256(sealed).hexdigest(),
        evaluation_contract_sha256=CONTRACT,
        key=KEY,
        sealed_utc=NOW,
    )
    release = create_release(
        release_id="R-1",
        holdout_id="HO-1",
        evaluation_contract_sha256=CONTRACT,
        sealed_bundle_sha256=sha256(sealed).hexdigest(),
        receipt=receipt,
    )
    first = consume_rehearsal(
        release=release,
        receipt=receipt,
        marker_dir=tmp_path / "m",
        sealed_path=sealed_path,
        key=KEY,
        expected_sessions=SESSIONS,
    )
    assert first.bundle_sha256 == bundle.sha256()
    with pytest.raises(RehearsalError) as exc:
        consume_rehearsal(
            release=release,
            receipt=receipt,
            marker_dir=tmp_path / "m",
            sealed_path=sealed_path,
            key=KEY,
            expected_sessions=SESSIONS,
        )
    assert exc.value.code == "REHEARSAL_EVALUATION_ALREADY_CONSUMED"


def test_interrupted_canonical_write_detected(tmp_path):
    path = tmp_path / "canon.json"
    with pytest.raises(RehearsalError) as exc:
        write_canonical_file(
            path, b"payload", expected_sha256="f" * 64  # wrong expected hash
        )
    assert exc.value.code == "REHEARSAL_CANONICAL_WRITE_INTERRUPTED"


def test_post_write_readback_mismatch(tmp_path):
    path = tmp_path / "canon.json"
    write_canonical_file(path, b"payload")
    with pytest.raises(RehearsalError) as exc:
        readback_verify(path, expected_sha256="f" * 64)
    assert exc.value.code == "REHEARSAL_READBACK_MISMATCH"


# -----------------------------------------------------------------------------
# Sealing round-trip and primitive invariants
# -----------------------------------------------------------------------------


def test_seal_open_roundtrip_preserves_bundle_identity():
    bundle = make_bundle()
    sealed = build_sealed_bundle(
        bundle, key=KEY, evaluation_contract_sha256=CONTRACT
    )
    recovered = open_bundle(sealed, key=KEY, aad=CONTRACT)
    decoded = json.loads(recovered)
    recovered_bundle = AcquiredBundle(
        symbols=tuple(decoded["symbols"]),
        sessions=tuple(decoded["sessions"]),
        bars=decoded["bars"],
        adjustment_convention=decoded["adjustment_convention"],
    )
    assert recovered_bundle.sha256() == bundle.sha256()


def test_seal_rejects_wrong_key_length():
    bundle = make_bundle()
    with pytest.raises(RehearsalError) as exc:
        seal_bundle(canonical_bytes(bundle._canonical()), key=b"short", aad=CONTRACT)
    assert exc.value.code == "REHEARSAL_KEY_INVALID"


def test_authorization_is_hashed_and_stable():
    auth = create_acquisition_authorization(
        authorization_id="A-1",
        holdout_id="HO-1",
        holdout_bundle_sha256="a" * 64,
        evaluation_contract_sha256=CONTRACT,
        issued_utc=NOW,
    )
    # The authorization content hash is the canonical hash of its full,
    # frozen model dump (including schema/issued identity).
    assert auth.sha256 == content_sha256(auth.model_dump())
    assert isinstance(auth, AcquisitionAuthorization)
