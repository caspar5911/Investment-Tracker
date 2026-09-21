"""Generation-2 synthetic Phase-6 dress rehearsal.

B2 provides a *single-command* end-to-end rehearsal of the one-time
irreversible Phase-6 pipeline on fully synthetic data, using dependency
injection (a fake acquisition provider) so that no real symbol, real history,
or real network/provider call is ever made:

    virginity evidence
    -> acquisition authorization
    -> acquisition-start marker (exclusive, one-time)
    -> synthetic-provider acquisition
    -> session validation
    -> encrypted AES-256-GCM seal (AAD = evaluation-contract sha256)
    -> seal receipt
    -> release
    -> one-time evaluation
    -> consumption marker (exclusive, one-time)

B3 (fault-injection) drives this same machinery into each failure mode and
checks that it is fail-closed: every defect raises ``RehearsalError`` with a
stable ``code`` rather than silently producing evidence.

Two irreversible boundaries are enforced with exclusive ``open("x")`` marker
files: the *acquisition-start* marker and the *consumption* marker. Once
written they cannot be re-created, so a second run of that step is refused.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict, Field

REHEARSAL_SCHEMA = "G2-PHASE6-SYNTHETIC-REHEARSAL-v1"

__all__ = [
    "REHEARSAL_SCHEMA",
    "AcquiredBundle",
    "AcquisitionAuthorization",
    "AcquisitionProvider",
    "EvaluationResult",
    "RehearsalError",
    "RehearsalRelease",
    "RehearsalTranscript",
    "SealReceipt",
    "SyntheticAcquisitionProvider",
    "VirginityEvidence",
    "build_sealed_bundle",
    "canonical_bytes",
    "content_sha256",
    "create_acquisition_authorization",
    "create_acquisition_start_marker",
    "create_release",
    "create_seal_receipt",
    "consume_rehearsal",
    "open_bundle",
    "produce_virginity_evidence",
    "readback_verify",
    "run_synthetic_rehearsal",
    "seal_bundle",
    "validate_acquired_bundle",
    "write_canonical_file",
    "write_sealed_bundle",
]

_KEY_BYTES = 32
_NONCE_BYTES = 12


class RehearsalError(RuntimeError):
    """Fail-closed rehearsal error carrying a stable machine-readable code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


def content_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


# ---------------------------------------------------------------------------
# Acquired data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AcquiredBundle:
    """Synthetic acquisition result.

    ``bars`` maps symbol -> session -> ``{"open": float, "close": float}``.
    """

    symbols: tuple[str, ...]
    sessions: tuple[str, ...]
    bars: dict[str, dict[str, dict[str, float]]]
    adjustment_convention: str

    def _canonical(self) -> dict:
        return {
            "symbols": sorted(self.symbols),
            "sessions": list(self.sessions),
            "bars": {symbol: self.bars[symbol] for symbol in sorted(self.symbols)},
            "adjustment_convention": self.adjustment_convention,
        }

    def sha256(self) -> str:
        return content_sha256(self._canonical())


class AcquisitionProvider(Protocol):
    def acquire(self, authorization: "AcquisitionAuthorization") -> AcquiredBundle: ...


class SyntheticAcquisitionProvider:
    """Default DI fake provider that returns a pre-built synthetic bundle."""

    def __init__(self, bundle: AcquiredBundle) -> None:
        self._bundle = bundle

    def acquire(self, authorization: "AcquisitionAuthorization") -> AcquiredBundle:
        return self._bundle


# ---------------------------------------------------------------------------
# Cryptographic seal (AES-256-GCM, AAD = evaluation-contract sha256)
# ---------------------------------------------------------------------------


def seal_bundle(plaintext: bytes, *, key: bytes, aad: str) -> bytes:
    if len(key) != _KEY_BYTES:
        raise RehearsalError("REHEARSAL_KEY_INVALID", f"key must be {_KEY_BYTES} bytes")
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad.encode("ascii"))
    return nonce + ciphertext


def open_bundle(payload: bytes, *, key: bytes, aad: str) -> bytes:
    if len(payload) < _NONCE_BYTES + 1:
        raise RehearsalError("REHEARSAL_BUNDLE_CORRUPT", "sealed payload too short")
    nonce, ciphertext = payload[:_NONCE_BYTES], payload[_NONCE_BYTES:]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad.encode("ascii"))
    except RehearsalError:
        raise
    except Exception as exc:  # noqa: BLE001 - GCM raises cryptography.exceptions
        raise RehearsalError("REHEARSAL_DECRYPTION_FAILED", str(exc)) from exc


def build_sealed_bundle(
    bundle: AcquiredBundle, *, key: bytes, evaluation_contract_sha256: str
) -> bytes:
    return seal_bundle(canonical_bytes(bundle._canonical()), key=key, aad=evaluation_contract_sha256)


# ---------------------------------------------------------------------------
# Governance models
# ---------------------------------------------------------------------------


class VirginityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[REHEARSAL_SCHEMA]
    holdout_id: str
    expected_bundle_sha256: str
    observed_bundle_sha256: str
    recorded_utc: str
    virgin: Literal[True] = True


class AcquisitionAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[REHEARSAL_SCHEMA]
    authorization_id: str
    holdout_id: str
    holdout_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_utc: str
    one_time: Literal[True] = True

    @property
    def sha256(self) -> str:
        return content_sha256(self.model_dump())


class SealReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[REHEARSAL_SCHEMA]
    holdout_id: str
    sealed_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    key_fingerprint: str
    sealed_utc: str

    @property
    def sha256(self) -> str:
        return content_sha256(self.model_dump())


class RehearsalRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[REHEARSAL_SCHEMA]
    authority: Literal["SYNTHETIC_REHEARSAL"]
    status: Literal["SYNTHETIC_HOLDOUT_RELEASE_AUTHORIZED"]
    release_id: str
    holdout_id: str
    evaluation_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sealed_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    one_time: Literal[True] = True


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["SYNTHETIC_EVALUATION_COMPLETE"]
    holdout_id: str
    bundle_sha256: str
    session_count: int
    symbol_count: int


class RehearsalTranscript(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[REHEARSAL_SCHEMA]
    holdout_id: str
    virginity_sha256: str
    authorization_sha256: str
    bundle_sha256: str
    sealed_bundle_sha256: str
    receipt_sha256: str
    release_id: str
    evaluation_sha256: str
    transcript_sha256: str


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def create_acquisition_authorization(
    *,
    authorization_id: str,
    holdout_id: str,
    holdout_bundle_sha256: str,
    evaluation_contract_sha256: str,
    issued_utc: str,
) -> AcquisitionAuthorization:
    return AcquisitionAuthorization(
        schema_version=REHEARSAL_SCHEMA,
        authorization_id=authorization_id,
        holdout_id=holdout_id,
        holdout_bundle_sha256=holdout_bundle_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        issued_utc=issued_utc,
    )


def produce_virginity_evidence(
    bundle: AcquiredBundle, *, expected_sha256: str, holdout_id: str, recorded_utc: str
) -> VirginityEvidence:
    observed = bundle.sha256()
    if observed != expected_sha256:
        raise RehearsalError(
            "REHEARSAL_VIRGINITY_HASH_MISMATCH",
            f"virgin bundle hash {observed} != expected {expected_sha256}",
        )
    return VirginityEvidence(
        schema_version=REHEARSAL_SCHEMA,
        holdout_id=holdout_id,
        expected_bundle_sha256=expected_sha256,
        observed_bundle_sha256=observed,
        recorded_utc=recorded_utc,
    )


def create_acquisition_start_marker(marker_dir: Path, authorization: AcquisitionAuthorization) -> Path:
    root = Path(marker_dir)
    root.mkdir(parents=True, exist_ok=True)
    marker = root / f"{authorization.authorization_id}.acquire-start.json"
    record = {
        "schema_version": REHEARSAL_SCHEMA,
        "status": "ACQUISITION_STARTED",
        "authorization_id": authorization.authorization_id,
        "holdout_id": authorization.holdout_id,
        "authorization_sha256": authorization.sha256,
    }
    try:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump(record, handle, sort_keys=True, separators=(",", ":"))
    except FileExistsError as exc:
        raise RehearsalError(
            "REHEARSAL_ACQUISITION_STARTED_ONCE",
            f"acquisition-start marker already exists: {authorization.authorization_id}",
        ) from exc
    return marker


def _check_finite_positive(value: float, *, nan_code: str, inf_code: str, positive_code: str) -> None:
    if value != value:  # NaN
        raise RehearsalError(nan_code, "OHLC value is NaN")
    if value in (float("inf"), float("-inf")):
        raise RehearsalError(inf_code, "OHLC value is infinite")
    if value <= 0.0:
        raise RehearsalError(positive_code, "OHLC value must be positive")


def validate_acquired_bundle(
    bundle: AcquiredBundle,
    *,
    expected_sessions: tuple[str, ...],
    adjustment_convention: str,
    expected_sha256: str | None = None,
) -> None:
    if not bundle.symbols:
        raise RehearsalError("REHEARSAL_ACQUIRED_EMPTY", "provider returned no symbols")

    # Malformed schema: bars must be a dict keyed exactly by the declared symbols,
    # and every bar must be a dict of session -> {"open","close"}.
    if set(bundle.bars.keys()) != set(bundle.symbols):
        raise RehearsalError("REHEARSAL_MALFORMED_SCHEMA", "bars do not cover declared symbols")
    for symbol in bundle.symbols:
        bars = bundle.bars[symbol]
        if not isinstance(bars, dict):
            raise RehearsalError("REHEARSAL_MALFORMED_SCHEMA", f"bars[{symbol}] not a mapping")
        for session, bar in bars.items():
            if not isinstance(bar, dict) or set(bar.keys()) != {"open", "close"}:
                raise RehearsalError("REHEARSAL_MALFORMED_SCHEMA", f"bar[{symbol}][{session}] malformed")

    sessions = bundle.sessions
    # Duplicate session.
    if len(sessions) != len(set(sessions)):
        raise RehearsalError("REHEARSAL_SESSION_DUPLICATE", "duplicate session in acquisition")
    # Non-monotonic session.
    if any(sessions[i] >= sessions[i + 1] for i in range(len(sessions) - 1)):
        raise RehearsalError("REHEARSAL_SESSION_NONMONOTONIC", "sessions are not strictly increasing")
    # Missing / unexpected sessions.
    if set(sessions) != set(expected_sessions) or len(sessions) != len(expected_sessions):
        raise RehearsalError("REHEARSAL_SESSION_MISSING", "acquired sessions != expected sessions")

    if bundle.adjustment_convention != adjustment_convention:
        raise RehearsalError(
            "REHEARSAL_ADJUSTMENT_MODE_MISMATCH",
            f"adjustment {bundle.adjustment_convention} != authorized {adjustment_convention}",
        )

    # OHLC quality + per-symbol session consistency.
    for symbol in bundle.symbols:
        bars = bundle.bars[symbol]
        if set(bars.keys()) != set(expected_sessions):
            raise RehearsalError(
                "REHEARSAL_OHLC_INCONSISTENT",
                f"symbol {symbol} bar sessions do not match session authority",
            )
        for session in sessions:
            _check_finite_positive(
                float(bars[session]["open"]),
                nan_code="REHEARSAL_OHLC_NAN",
                inf_code="REHEARSAL_OHLC_INF",
                positive_code="REHEARSAL_OHLC_NONPOSITIVE",
            )
            _check_finite_positive(
                float(bars[session]["close"]),
                nan_code="REHEARSAL_OHLC_NAN",
                inf_code="REHEARSAL_OHLC_INF",
                positive_code="REHEARSAL_OHLC_NONPOSITIVE",
            )

    if expected_sha256 is not None and bundle.sha256() != expected_sha256:
        raise RehearsalError(
            "REHEARSAL_AUTHORIZATION_HASH_MISMATCH",
            f"bundle {bundle.sha256()} != authorized {expected_sha256}",
        )


def write_sealed_bundle(path: Path, payload: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise RehearsalError(
            "REHEARSAL_OUTPUT_COLLISION", f"sealed bundle output already exists: {path.name}"
        ) from exc


def write_canonical_file(
    path: Path, payload: bytes, *, expected_sha256: str | None = None
) -> None:
    """Atomically write ``payload`` and read it back, verifying content identity.

    The ``expected_sha256`` argument is a fault-injection seam: when a readback
    disagrees with the intended content the write is classified as an
    interrupted canonical write rather than being trusted.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".partial")
    try:
        with tmp.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise

    readback = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    intended = expected_sha256 if expected_sha256 is not None else hashlib.sha256(payload).hexdigest()
    if readback != intended:
        raise RehearsalError("REHEARSAL_CANONICAL_WRITE_INTERRUPTED", "canonical write readback mismatch")


def readback_verify(path: Path, expected_sha256: str) -> None:
    observed = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if observed != expected_sha256:
        raise RehearsalError("REHEARSAL_READBACK_MISMATCH", f"readback {observed} != expected {expected_sha256}")


def create_seal_receipt(
    *,
    holdout_id: str,
    sealed_bundle_sha256: str,
    evaluation_contract_sha256: str,
    key: bytes,
    sealed_utc: str,
) -> SealReceipt:
    return SealReceipt(
        schema_version=REHEARSAL_SCHEMA,
        holdout_id=holdout_id,
        sealed_bundle_sha256=sealed_bundle_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        key_fingerprint=hashlib.sha256(key).hexdigest(),
        sealed_utc=sealed_utc,
    )


def create_release(
    *,
    release_id: str,
    holdout_id: str,
    evaluation_contract_sha256: str,
    sealed_bundle_sha256: str,
    receipt: SealReceipt,
) -> RehearsalRelease:
    if receipt.sealed_bundle_sha256 != sealed_bundle_sha256:
        raise RehearsalError("REHEARSAL_RECEIPT_MISMATCH", "receipt bundle hash != sealed bundle hash")
    if receipt.evaluation_contract_sha256 != evaluation_contract_sha256:
        raise RehearsalError("REHEARSAL_RECEIPT_MISMATCH", "receipt contract hash mismatch")
    return RehearsalRelease(
        schema_version=REHEARSAL_SCHEMA,
        authority="SYNTHETIC_REHEARSAL",
        status="SYNTHETIC_HOLDOUT_RELEASE_AUTHORIZED",
        release_id=release_id,
        holdout_id=holdout_id,
        evaluation_contract_sha256=evaluation_contract_sha256,
        sealed_bundle_sha256=sealed_bundle_sha256,
        receipt_sha256=receipt.sha256,
    )


def _load_receipt(release: RehearsalRelease, receipt: SealReceipt) -> SealReceipt:
    if receipt.sha256 != release.receipt_sha256:
        raise RehearsalError("REHEARSAL_RELEASE_MISMATCH", "release receipt hash != receipt")
    if release.sealed_bundle_sha256 != receipt.sealed_bundle_sha256:
        raise RehearsalError("REHEARSAL_RELEASE_MISMATCH", "release bundle hash != receipt")
    return receipt


def consume_rehearsal(
    *,
    release: RehearsalRelease,
    receipt: SealReceipt,
    marker_dir: Path,
    sealed_path: Path,
    key: bytes,
    expected_sessions: tuple[str, ...],
) -> EvaluationResult:
    """One-time evaluation behind an exclusive consumption marker."""
    _load_receipt(release, receipt)
    root = Path(marker_dir)
    root.mkdir(parents=True, exist_ok=True)
    marker = root / f"{release.release_id}.consumed.json"

    def _evaluate() -> EvaluationResult:
        payload = Path(sealed_path).read_bytes()
        if hashlib.sha256(payload).hexdigest() != release.sealed_bundle_sha256:
            raise RehearsalError("REHEARSAL_BUNDLE_CORRUPT", "sealed bundle hash mismatch on read")
        plaintext = open_bundle(
            payload, key=key, aad=release.evaluation_contract_sha256
        )
        decoded = json.loads(plaintext.decode("utf-8"))
        symbol_set = set(decoded["symbols"])
        bar = AcquiredBundle(
            symbols=tuple(sorted(symbol_set)),
            sessions=tuple(decoded["sessions"]),
            bars={symbol: decoded["bars"][symbol] for symbol in sorted(symbol_set)},
            adjustment_convention=decoded["adjustment_convention"],
        )
        validate_acquired_bundle(
            bar,
            expected_sessions=expected_sessions,
            adjustment_convention=decoded["adjustment_convention"],
            expected_sha256=content_sha256(decoded),
        )
        return EvaluationResult(
            status="SYNTHETIC_EVALUATION_COMPLETE",
            holdout_id=release.holdout_id,
            bundle_sha256=hashlib.sha256(plaintext).hexdigest(),
            session_count=len(bar.sessions),
            symbol_count=len(bar.symbols),
        )

    try:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump(
                {
                    "schema_version": REHEARSAL_SCHEMA,
                    "status": "SYNTHETIC_HOLDOUT_CONSUMED",
                    "release_id": release.release_id,
                    "holdout_id": release.holdout_id,
                },
                handle,
                sort_keys=True,
                separators=(",", ":"),
            )
    except FileExistsError as exc:
        raise RehearsalError(
            "REHEARSAL_EVALUATION_ALREADY_CONSUMED", f"release already consumed: {release.release_id}"
        ) from exc

    return _evaluate()


# ---------------------------------------------------------------------------
# Single entrypoint
# ---------------------------------------------------------------------------


def run_synthetic_rehearsal(
    provider: AcquisitionProvider,
    *,
    marker_dir: Path,
    sealed_dir: Path,
    key: bytes,
    holdout_id: str,
    authorization_id: str,
    release_id: str,
    expected_bundle_sha256: str,
    expected_sessions: tuple[str, ...],
    adjustment_convention: str,
    evaluation_contract_sha256: str,
    now_utc: str,
) -> RehearsalTranscript:
    """Run the full synthetic Phase-6 rehearsal from one call.

    ``expected_bundle_sha256`` is the pre-recorded hash of the virgin holdout
    bundle: the acquisition authorization is bound to it *before* any data is
    read, so a provider that returns a different bundle is rejected.
    """

    # 1. Acquisition authorization, bound to the pre-recorded bundle hash.
    authorization = create_acquisition_authorization(
        authorization_id=authorization_id,
        holdout_id=holdout_id,
        holdout_bundle_sha256=expected_bundle_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        issued_utc=now_utc,
    )

    # 2. Acquisition-start marker (one-time, irreversible).
    create_acquisition_start_marker(Path(marker_dir), authorization)

    # 3. Provider acquisition (DI). A provider that dies mid-acquisition is
    # fail-closed: any unexpected error is classified as an interrupted
    # acquisition, while provider-specific RehearsalError codes propagate.
    try:
        provisional = provider.acquire(authorization)
    except RehearsalError:
        raise
    except Exception as exc:  # noqa: BLE001 - any provider failure is fail-closed
        raise RehearsalError("REHEARSAL_ACQUISITION_INTERRUPTED", str(exc)) from exc

    # 4. Virginity evidence.
    virginity = produce_virginity_evidence(
        provisional,
        expected_sha256=expected_bundle_sha256,
        holdout_id=holdout_id,
        recorded_utc=now_utc,
    )

    # 5. Session + OHLC + adjustment + authorization-hash validation.
    validate_acquired_bundle(
        provisional,
        expected_sessions=expected_sessions,
        adjustment_convention=adjustment_convention,
        expected_sha256=expected_bundle_sha256,
    )

    # 6. Encrypted seal (AAD = evaluation contract).
    sealed = build_sealed_bundle(provisional, key=key, evaluation_contract_sha256=evaluation_contract_sha256)
    sealed_sha256 = hashlib.sha256(sealed).hexdigest()
    sealed_path = Path(sealed_dir) / f"{holdout_id}.sealed.bin"
    write_sealed_bundle(sealed_path, sealed)

    # 7. Seal receipt.
    receipt = create_seal_receipt(
        holdout_id=holdout_id,
        sealed_bundle_sha256=sealed_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        key=key,
        sealed_utc=now_utc,
    )

    # 8. Release.
    release = create_release(
        release_id=release_id,
        holdout_id=holdout_id,
        evaluation_contract_sha256=evaluation_contract_sha256,
        sealed_bundle_sha256=sealed_sha256,
        receipt=receipt,
    )

    # 9/10. One-time evaluation + consumption marker.
    evaluation = consume_rehearsal(
        release=release,
        receipt=receipt,
        marker_dir=marker_dir,
        sealed_path=sealed_path,
        key=key,
        expected_sessions=expected_sessions,
    )

    evaluation_sha256 = content_sha256(evaluation.model_dump())
    body = {
        "schema_version": REHEARSAL_SCHEMA,
        "holdout_id": holdout_id,
        "virginity_sha256": content_sha256(virginity.model_dump()),
        "authorization_sha256": authorization.sha256,
        "bundle_sha256": provisional.sha256(),
        "sealed_bundle_sha256": sealed_sha256,
        "receipt_sha256": receipt.sha256,
        "release_id": release_id,
        "evaluation_sha256": evaluation_sha256,
    }
    return RehearsalTranscript(
        transcript_sha256=content_sha256(body),
        **body,
    )
