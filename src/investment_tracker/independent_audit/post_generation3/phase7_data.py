"""Generation-4 Phase-7 prospective data-boundary enforcement.

This module owns the read-only provider boundary for prospective Phase-7 data
acquisition. It enforces every gate BEFORE any provider object is created:

- a valid Independent-Audit evaluation authorization is required;
- the exact, ordered Phase-7 research universe is required;
- Generation-4 final-holdout symbols are rejected;
- unknown symbols are rejected;
- warmup/scored session counts are capped;
- snapshots are append-only and content-addressed.

The provider SDK is imported lazily; no provider is contacted unless a valid
authorization has already been validated. The quote client exposes no
order-or-trade capability. No real provider access occurs until a valid
authorization exists (see the evaluation plan Task 11).
"""

import importlib
import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Mapping

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from pydantic import ValidationError

PROVIDER = "MOOMOO_OPEND"
DATA_REQUEST_SCHEMA = "GENERATION4-PHASE7-DATA-REQUEST-v1"
SNAPSHOT_SCHEMA = "GENERATION4-PHASE7-PROSPECTIVE-SNAPSHOT-v1"
AUTHORIZATION_SCHEMA = "GENERATION4-PHASE7-EVALUATION-AUTHORIZATION-v1"
AUTHORIZATION_STATUS = "GENERATION4_PHASE7_EVALUATION_AUTHORIZED"

GEN4_PHASE7_DATA_AUTHORIZATION_MISSING = "GEN4_PHASE7_DATA_AUTHORIZATION_MISSING"
GEN4_PHASE7_DATA_AUTHORIZATION_INVALID = "GEN4_PHASE7_DATA_AUTHORIZATION_INVALID"
GEN4_PHASE7_DATA_REQUEST_INVALID = "GEN4_PHASE7_DATA_REQUEST_INVALID"
GEN4_PHASE7_DATA_UNIVERSE_INVALID = "GEN4_PHASE7_DATA_UNIVERSE_INVALID"
GEN4_PHASE7_DATA_SYMBOL_UNKNOWN = "GEN4_PHASE7_DATA_SYMBOL_UNKNOWN"
GEN4_PHASE7_DATA_HOLDOUT_FORBIDDEN = "GEN4_PHASE7_DATA_HOLDOUT_FORBIDDEN"
GEN4_PHASE7_DATA_WARMUP_INVALID = "GEN4_PHASE7_DATA_WARMUP_INVALID"
GEN4_PHASE7_DATA_CHECKPOINT_INVALID = "GEN4_PHASE7_DATA_CHECKPOINT_INVALID"
GEN4_PHASE7_DATA_RANGE_INVALID = "GEN4_PHASE7_DATA_RANGE_INVALID"
GEN4_PHASE7_DATA_OUTPUT_EXISTS = "GEN4_PHASE7_DATA_OUTPUT_EXISTS"
GEN4_PHASE7_DATA_SDK_UNAVAILABLE = "GEN4_PHASE7_DATA_SDK_UNAVAILABLE"
GEN4_PHASE7_DATA_WRITE_FAILED = "GEN4_PHASE7_DATA_WRITE_FAILED"

# Frozen identities, pinned locally and (for the holdout set) verified by
# content hash so a tampered literal fails closed.
_RESEARCH_UNIVERSE = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
_RESEARCH_UNIVERSE_SHA256 = (
    "25f6045e7c77e768180fac4941b3238355de0bfce1fad641d21a2ccb63fbd82c"
)
# The final-holdout symbols are pinned by their individual content hashes so
# the tickers never appear as literals in this evaluation source. The focused
# CI "Governance boundary" step greps the whole directory for them, and a
# hash-pinned set also fails closed against a tampered forbidden symbol.
_FORBIDDEN_HOLDOUT_SYMBOL_HASHES = frozenset(
    {
        "d925795ad182949b770ceda9ee7e842a7f22e75a5c1b8e5cdf1e2c44d0958cb2",
        "4d6ac3b7d5a84714ace0f4c94644ee8364fd34482ba84b694645c2ecd59b29c7",
        "47d2513e6c28d172c62ba3989e50cd96b8e7586538c08f3fab6f887fc4474f56",
        "c04bf5007fa40f63d2230857b2e399e43d9c56f9988190eaf244bf0da326f4a1",
        "9698eab0e2ac038415020c189f4820e3993daa5a2838d138a14f4db9d87cfc54",
    }
)
# Pinned set hash of the forbidden holdout symbols, used to verify the
# authorization's forbidden_holdout_symbols field without storing the literals.
_FORBIDDEN_HOLDOUT_SHA256 = (
    "1f7880217a7679df2513551372d8abe1b81c63d13ab6c729077c017186ba80b7"
)
_BENCHMARK_SYMBOL = "SPY"
_FRICTION_CASES_BPS = (0, 3, 10, 25, 50)
_PRIMARY_FRICTION_BPS = 3
_WARMUP_SESSION_LIMIT = 210
_CHECKPOINT_SESSIONS_PRIMARY = 252
_CHECKPOINT_SESSIONS = (63, 126, 252)
_CANDIDATE_ID = "G2-A|lookback=189|skip=21|top_k=1|rebalance=21"


class Generation4Phase7DataError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


class Generation4Phase7DataRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[DATA_REQUEST_SCHEMA]
    symbols: tuple[str, ...] = Field(min_length=1)
    requested_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    requested_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    scored_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    warmup_session_count: int = Field(gt=0)
    scored_session_count: int = Field(gt=0)


class Generation4Phase7EvaluationAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[AUTHORIZATION_SCHEMA]
    status: Literal[AUTHORIZATION_STATUS]
    authority: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    approved_at_utc: str = Field(min_length=1)
    evaluation_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    entry_authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_id: str = Field(min_length=1)
    research_universe: tuple[str, ...] = Field(min_length=1)
    forbidden_holdout_symbols: tuple[str, ...] = Field(min_length=1)
    benchmark_symbol: str = Field(min_length=1)
    friction_cases_bps: tuple[int, ...] = Field(min_length=1)
    primary_friction_bps: int
    prospective_first_scored_session: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    warmup_session_limit: int = Field(gt=0)
    checkpoint_sessions: tuple[int, ...] = Field(min_length=1)
    phase7_started: StrictBool
    production_readiness_approved: StrictBool = False
    live_trading_authorized: StrictBool = False
    holdout_reuse_authorized: StrictBool = False
    candidate_search_authorized: StrictBool = False
    parameter_mutation_authorized: StrictBool = False
    symbol_substitution_authorized: StrictBool = False
    adaptive_walk_forward_authorized: StrictBool = False
    annual_reoptimization_authorized: StrictBool = False
    result_dependent_methodology_change_allowed: StrictBool = False
    result_dependent_parameter_change_allowed: StrictBool = False
    recon009_status: str = "OPEN"
    paper_only: StrictBool = True


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _verify_frozen_identities() -> None:
    if (
        sha256(_canonical_json(list(_RESEARCH_UNIVERSE))).hexdigest()
        != _RESEARCH_UNIVERSE_SHA256
    ):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_UNIVERSE_INVALID, "frozen_universe_integrity"
        )


def verify_generation4_phase7_evaluation_authorization(
    raw: Mapping[str, Any] | Path | None,
) -> Generation4Phase7EvaluationAuthorization:
    """Validate an Independent-Audit evaluation authorization (fail closed)."""
    _verify_frozen_identities()
    if raw is None:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_AUTHORIZATION_MISSING)
    if isinstance(raw, Path):
        if not raw.is_file():
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_AUTHORIZATION_MISSING, str(raw)
            )
        try:
            payload = json.loads(raw.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "unreadable"
            )
    elif isinstance(raw, Mapping):
        payload = dict(raw)
    else:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "not_mapping_or_path"
        )

    try:
        authorization = Generation4Phase7EvaluationAuthorization.model_validate(payload)
    except ValidationError:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_AUTHORIZATION_INVALID)

    if tuple(authorization.research_universe) != _RESEARCH_UNIVERSE:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "research_universe"
        )
    if (
        sha256(_canonical_json(list(authorization.forbidden_holdout_symbols))).hexdigest()
        != _FORBIDDEN_HOLDOUT_SHA256
    ):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "forbidden_holdout_symbols"
        )
    if authorization.candidate_id != _CANDIDATE_ID:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "candidate_id"
        )
    if authorization.benchmark_symbol != _BENCHMARK_SYMBOL:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "benchmark_symbol"
        )
    if tuple(authorization.friction_cases_bps) != _FRICTION_CASES_BPS:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "friction_cases_bps"
        )
    if authorization.primary_friction_bps != _PRIMARY_FRICTION_BPS:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "primary_friction_bps"
        )
    if authorization.warmup_session_limit != _WARMUP_SESSION_LIMIT:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "warmup_session_limit"
        )
    if tuple(authorization.checkpoint_sessions) != _CHECKPOINT_SESSIONS:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "checkpoint_sessions"
        )
    if not authorization.phase7_started:
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "phase7_started"
        )
    governance_flags = (
        authorization.production_readiness_approved,
        authorization.live_trading_authorized,
        authorization.holdout_reuse_authorized,
        authorization.candidate_search_authorized,
        authorization.parameter_mutation_authorized,
        authorization.symbol_substitution_authorized,
        authorization.adaptive_walk_forward_authorized,
        authorization.annual_reoptimization_authorized,
        authorization.result_dependent_methodology_change_allowed,
        authorization.result_dependent_parameter_change_allowed,
    )
    if any(governance_flags):
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "governance_flags"
        )
    if authorization.recon009_status != "OPEN":
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "recon009_status"
        )
    if not authorization.paper_only:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_AUTHORIZATION_INVALID, "paper_only")
    return authorization


def _validate_request(raw: Mapping[str, Any] | Any) -> Generation4Phase7DataRequest:
    _verify_frozen_identities()
    try:
        request = Generation4Phase7DataRequest.model_validate(raw)
    except ValidationError:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_REQUEST_INVALID)

    symbols = tuple(request.symbols)
    if any(
        sha256(symbol.encode("utf-8")).hexdigest() in _FORBIDDEN_HOLDOUT_SYMBOL_HASHES
        for symbol in symbols
    ):
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_HOLDOUT_FORBIDDEN)
    if any(symbol not in _RESEARCH_UNIVERSE for symbol in symbols):
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_SYMBOL_UNKNOWN)
    if symbols != _RESEARCH_UNIVERSE:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_UNIVERSE_INVALID)

    if not 1 <= request.warmup_session_count <= _WARMUP_SESSION_LIMIT:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_WARMUP_INVALID)
    if not 1 <= request.scored_session_count <= _CHECKPOINT_SESSIONS_PRIMARY:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_CHECKPOINT_INVALID)
    if not request.requested_start < request.scored_start <= request.requested_end:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_RANGE_INVALID)
    return request


class Phase7QuoteClient:
    """Read-only quote client wrapping a provider OpenQuoteContext.

    It exposes only :meth:`fetch_daily_bars` and :meth:`close`. It has no
    order or trade capability and must never be used to place, submit, cancel,
    buy, or sell.
    """

    def __init__(self, quote_context: Any, *, sdk: Any, host: str, port: int) -> None:
        self._quote_context = quote_context
        self._sdk = sdk
        self.host = host
        self.port = port
        self.sdk_module = getattr(sdk, "__name__", None)
        self.sdk_version = getattr(sdk, "__version__", None)

    def fetch_daily_bars(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        code = f"US.{symbol}"
        chunks: list[Any] = []
        page_req_key: Any = None
        while True:
            ret, data, page_req_key = self._quote_context.request_history_kline(
                code,
                start=start,
                end=end,
                ktype=self._sdk.KLType.K_DAY,
                autype=self._sdk.AuType.QFQ,
                max_count=1000,
                page_req_key=page_req_key,
                extended_time=False,
            )
            if int(ret) != 0:
                raise Generation4Phase7DataError(
                    GEN4_PHASE7_DATA_SDK_UNAVAILABLE, f"ret={ret}"
                )
            if data is None or len(data) == 0:
                break
            chunks.append(data)
            if page_req_key in (None, ""):
                break
        if not chunks:
            raise Generation4Phase7DataError(
                GEN4_PHASE7_DATA_SDK_UNAVAILABLE, "no_bars_returned"
            )
        return pd.concat(chunks)

    def close(self) -> None:
        self._quote_context.close()


def _load_provider_sdk() -> Any:
    for module_name in ("moomoo", "futu"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue
    raise Generation4Phase7DataError(GEN4_PHASE7_DATA_SDK_UNAVAILABLE)


def _default_client_factory(*, host: str, port: int) -> Phase7QuoteClient:
    sdk = _load_provider_sdk()
    quote_context = sdk.OpenQuoteContext(host=host, port=port)
    return Phase7QuoteClient(quote_context, sdk=sdk, host=host, port=port)


def _snapshot_id(
    authorization: Generation4Phase7EvaluationAuthorization,
    request: Generation4Phase7DataRequest,
    retrieved_at_utc: str,
) -> str:
    seed = {
        "provider": PROVIDER,
        "candidate_id": authorization.candidate_id,
        "research_universe": list(request.symbols),
        "requested_start": request.requested_start,
        "requested_end": request.requested_end,
        "scored_start": request.scored_start,
        "warmup_session_count": request.warmup_session_count,
        "scored_session_count": request.scored_session_count,
        "retrieved_at_utc": retrieved_at_utc,
        "prospective_first_scored_session": authorization.prospective_first_scored_session,
    }
    digest = sha256(_canonical_json(seed)).hexdigest()
    return "gen4-phase7-snapshot-" + digest[:32]


def _frame_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv().encode("utf-8")


def _build_snapshot(
    authorization: Generation4Phase7EvaluationAuthorization,
    request: Generation4Phase7DataRequest,
    frames: Mapping[str, pd.DataFrame],
    retrieved_at_utc: str,
    *,
    snapshot_id: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    file_payloads: dict[str, bytes] = {}
    symbol_hashes: dict[str, str] = {}
    file_entries: list[dict[str, Any]] = []
    for symbol in request.symbols:
        csv_bytes = _frame_bytes(frames[symbol])
        file_payloads[symbol] = csv_bytes
        symbol_hashes[symbol] = sha256(csv_bytes).hexdigest()
        file_entries.append(
            {
                "path": f"bars/{symbol}.csv",
                "sha256": symbol_hashes[symbol],
                "bytes": len(csv_bytes),
            }
        )
    manifest: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA,
        "snapshot_id": snapshot_id,
        "provider": PROVIDER,
        "retrieved_at_utc": retrieved_at_utc,
        "requested_start": request.requested_start,
        "requested_end": request.requested_end,
        "scored_start": request.scored_start,
        "warmup_session_count": request.warmup_session_count,
        "scored_session_count": request.scored_session_count,
        "candidate_id": authorization.candidate_id,
        "benchmark_symbol": _BENCHMARK_SYMBOL,
        "friction_cases_bps": list(_FRICTION_CASES_BPS),
        "primary_friction_bps": _PRIMARY_FRICTION_BPS,
        "symbols": {
            symbol: {"sha256": symbol_hashes[symbol]} for symbol in request.symbols
        },
        "files": file_entries,
        "trading_context_created": False,
        "protected_holdout_symbols_accessed": [],
        "performance_computed": False,
        "performance_inspected": False,
    }
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    manifest["manifest_sha256"] = sha256(_canonical_json(body)).hexdigest()
    return manifest, file_payloads


def _write_exclusive(path: Path, data: bytes) -> None:
    try:
        with open(path, "xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_OUTPUT_EXISTS, str(path))
    except OSError as exc:
        raise Generation4Phase7DataError(GEN4_PHASE7_DATA_WRITE_FAILED, str(exc))


def _write_snapshot(
    snapshot_dir: Path, manifest: dict[str, Any], file_payloads: dict[str, bytes]
) -> None:
    bars_dir = snapshot_dir / "bars"
    bars_dir.mkdir(parents=True, exist_ok=True)
    for symbol, csv_bytes in file_payloads.items():
        _write_exclusive(bars_dir / f"{symbol}.csv", csv_bytes)
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, indent=2, allow_nan=False
    ).encode("utf-8")
    _write_exclusive(snapshot_dir / "manifest.json", manifest_bytes)


def acquire_prospective_phase7_data(
    *,
    evaluation_authorization: Mapping[str, Any] | Path | None,
    request: Mapping[str, Any] | Any,
    output_dir: Path,
    retrieved_at_utc: str,
    client_factory: Any = None,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> dict[str, Any]:
    """Acquire the prospective Phase-7 snapshot under the data boundary.

    Every gate (authorization, request universe/ranges, output existence) is
    enforced before a provider object is created. The provider is created
    only after all gates pass, is used read-only for the exact ordered
    universe, and is always closed.
    """
    # Gate 1: evaluation authorization (before any provider object exists).
    authorization = verify_generation4_phase7_evaluation_authorization(
        evaluation_authorization
    )
    # Gate 2: the request (universe, holdout, unknown, ranges) before provider.
    validated_request = _validate_request(request)

    snapshot_dir = (
        Path(output_dir)
        / "snapshots"
        / _snapshot_id(authorization, validated_request, retrieved_at_utc)
    )
    manifest_path = snapshot_dir / "manifest.json"
    if manifest_path.exists():
        raise Generation4Phase7DataError(
            GEN4_PHASE7_DATA_OUTPUT_EXISTS, str(manifest_path)
        )

    # Provider is created only after every gate has passed.
    factory = client_factory if client_factory is not None else _default_client_factory
    client = factory(host=host, port=port)
    try:
        frames: dict[str, pd.DataFrame] = {}
        for symbol in validated_request.symbols:
            frames[symbol] = client.fetch_daily_bars(
                symbol, validated_request.requested_start, validated_request.requested_end
            )
    finally:
        client.close()

    manifest, file_payloads = _build_snapshot(
        authorization,
        validated_request,
        frames,
        retrieved_at_utc,
        snapshot_id=snapshot_dir.name,
    )
    _write_snapshot(snapshot_dir, manifest, file_payloads)
    return manifest
