from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path

import pandas as pd

from investment_tracker.quant.phase4.engine.durability import (
    calculate_durability,
    expected_session_identity,
)
from investment_tracker.quant.phase4.engine.execution import _replay, replay_targets
from investment_tracker.quant.phase4.engine.market import MarketPanel, ScoredMarketInput
from investment_tracker.quant.phase4.engine.metrics import calculate_metrics
from investment_tracker.quant.phase4.engine.models import (
    ExpectedSessionAuthority,
    TargetInstruction,
)
from investment_tracker.quant.phase4.engine.robustness import (
    bootstrap_median_daily_return,
    run_friction_cases,
)
from investment_tracker.quant.phase4.engine.strategies import (
    _cross_sectional_absolute_momentum,
)
from investment_tracker.quant.phase5.methodology import frozen_binding
from investment_tracker.quant.phase6.preseal import (
    consume_released_bundle,
    load_release_envelope,
)

from .authority import (
    BENCHMARK_SYMBOL,
    CONTRACT_SHA256,
    FRICTION_CASE_BPS,
    HOLDOUT_END,
    HOLDOUT_START,
    INITIAL_CASH,
    LOCKED_SYMBOLS,
    PRIMARY_FRICTION_BPS,
    WARMUP_SESSIONS,
    canonical_json_bytes,
    load_frozen_contract,
    sha256_bytes,
)
from .bundle import decrypt_bundle, open_plain_bundle
from .opend_qfq import expected_sessions
from .release import _load_receipt


def _load_key(path: Path) -> bytes:
    text = Path(path).read_text(encoding="ascii").strip()
    try:
        key = bytes.fromhex(text)
    except ValueError as exc:
        raise ValueError("PHASE6_HOLDOUT_KEY_INVALID") from exc
    if len(key) != 32:
        raise ValueError("PHASE6_HOLDOUT_KEY_INVALID")
    return key


def _frame(entries: dict[str, bytes], symbol: str) -> pd.DataFrame:
    path = f"bars/{symbol}.csv"
    if path not in entries:
        raise ValueError(f"PHASE6_BUNDLE_SYMBOL_MISSING:{symbol}")
    frame = pd.read_csv(BytesIO(entries[path]))
    if tuple(frame.columns) != ("session", "open", "high", "low", "close"):
        raise ValueError(f"PHASE6_BUNDLE_BAR_SCHEMA_MISMATCH:{symbol}")
    sessions = pd.to_datetime(frame["session"], errors="raise", utc=True).dt.normalize()
    if sessions.duplicated().any():
        raise ValueError(f"PHASE6_BUNDLE_DUPLICATE_SESSION:{symbol}")
    result = pd.DataFrame(index=pd.DatetimeIndex(sessions))
    for name in ("open", "high", "low", "close"):
        result[name] = pd.to_numeric(frame[name], errors="raise").to_numpy(dtype=float)
    matrix = result.to_numpy(dtype=float)
    if (
        result.empty
        or not result.index.is_monotonic_increasing
        or not all(math.isfinite(float(value)) and float(value) > 0.0 for value in matrix.flat)
        or (result["low"] > result[["open", "close"]].min(axis=1)).any()
        or (result["high"] < result[["open", "close"]].max(axis=1)).any()
        or (result["low"] > result["high"]).any()
    ):
        raise ValueError(f"PHASE6_BUNDLE_BAR_VALUES_INVALID:{symbol}")
    return result


def _validate_manifest(manifest: dict[str, object]) -> None:
    if (
        manifest.get("schema_version") != "PHASE6-SEALED-HOLDOUT-BUNDLE-v1"
        or manifest.get("authority") != "INDEPENDENT_AUDIT"
        or manifest.get("provider") != "MOOMOO_OPEND"
        or manifest.get("bar_type") != "K_DAY"
        or manifest.get("bar_autype") != "QFQ"
        or manifest.get("extended_time") is not False
        or manifest.get("trading_context_created") is not False
        or manifest.get("evaluation_contract_sha256") != CONTRACT_SHA256
        or tuple(manifest.get("locked_symbols", ())) != LOCKED_SYMBOLS
        or manifest.get("benchmark_symbol") != BENCHMARK_SYMBOL
        or manifest.get("holdout_start") != HOLDOUT_START
        or manifest.get("holdout_end") != HOLDOUT_END
        or manifest.get("warmup_session_count") != WARMUP_SESSIONS
        or manifest.get("final_holdout_accessed") is not True
        or manifest.get("protected_symbols_accessed") != list(LOCKED_SYMBOLS)
        or manifest.get("candidate_search_executed") is not False
        or manifest.get("candidate_parameters_changed") is not False
        or manifest.get("phase4_feedback_written") is not False
        or manifest.get("phase5_feedback_written") is not False
        or manifest.get("live_trading_capability") is not False
        or manifest.get("phase7_started") is not False
    ):
        raise ValueError("PHASE6_BUNDLE_GOVERNANCE_MISMATCH")


def _panels(
    entries: dict[str, bytes],
) -> tuple[ScoredMarketInput, MarketPanel, pd.DatetimeIndex]:
    warmup_sessions, scored_sessions = expected_sessions()
    all_sessions = warmup_sessions.append(scored_sessions)
    frames = {
        symbol: _frame(entries, symbol)
        for symbol in (*LOCKED_SYMBOLS, BENCHMARK_SYMBOL)
    }
    for symbol, frame in frames.items():
        if not frame.index.equals(all_sessions):
            raise ValueError(f"PHASE6_BUNDLE_SESSION_COVERAGE_MISMATCH:{symbol}")

    candidate_symbols = tuple(sorted(LOCKED_SYMBOLS))
    warmup_open = pd.DataFrame(
        {symbol: frames[symbol].loc[warmup_sessions, "open"] for symbol in candidate_symbols},
        index=warmup_sessions,
    )
    warmup_close = pd.DataFrame(
        {symbol: frames[symbol].loc[warmup_sessions, "close"] for symbol in candidate_symbols},
        index=warmup_sessions,
    )
    scored_open = pd.DataFrame(
        {symbol: frames[symbol].loc[scored_sessions, "open"] for symbol in candidate_symbols},
        index=scored_sessions,
    )
    scored_close = pd.DataFrame(
        {symbol: frames[symbol].loc[scored_sessions, "close"] for symbol in candidate_symbols},
        index=scored_sessions,
    )
    warmup_panel = MarketPanel.from_frames(warmup_open, warmup_close, role="WARMUP")
    scored_panel = MarketPanel.from_frames(scored_open, scored_close, role="SCORED")
    market_input = ScoredMarketInput.from_panels(warmup_panel, scored_panel)

    spy_open = pd.DataFrame(
        {BENCHMARK_SYMBOL: frames[BENCHMARK_SYMBOL].loc[scored_sessions, "open"]},
        index=scored_sessions,
    )
    spy_close = pd.DataFrame(
        {BENCHMARK_SYMBOL: frames[BENCHMARK_SYMBOL].loc[scored_sessions, "close"]},
        index=scored_sessions,
    )
    spy_panel = MarketPanel.from_frames(spy_open, spy_close, role="SCORED")
    return market_input, spy_panel, scored_sessions


def _targets(market_input: ScoredMarketInput) -> tuple[TargetInstruction | None, ...]:
    binding = frozen_binding()
    combined = market_input.combined_close_history
    warmup_count = len(market_input.indicator_warmup.sessions)
    sessions = market_input.scored.sessions
    rebalance = int(binding.parameters_dict["rebalance_sessions"])
    targets: list[TargetInstruction | None] = []
    for offset, session in enumerate(sessions):
        if offset % rebalance:
            targets.append(None)
            continue
        causal = combined.iloc[: warmup_count + offset + 1].copy(deep=True)
        weights = _cross_sectional_absolute_momentum(binding, causal)
        due = sessions[offset + 1] if offset + 1 < len(sessions) else None
        targets.append(
            TargetInstruction(
                signal_timestamp=session,
                due_session=due,
                weights=weights,
                binding=binding,
            )
        )
    return tuple(targets)


def _benchmark_replay(spy_panel: MarketPanel, friction_bps: int):
    sessions = spy_panel.sessions
    if len(sessions) < 2:
        raise ValueError("PHASE6_BENCHMARK_SESSIONS_INSUFFICIENT")
    pending = [None] * len(sessions)
    pending[0] = (
        sessions[0],
        sessions[1],
        ((BENCHMARK_SYMBOL, 1.0),),
    )
    return _replay(
        spy_panel.open_prices.to_numpy(dtype=float, copy=True),
        spy_panel.close_prices.to_numpy(dtype=float, copy=True),
        spy_panel.symbols,
        sessions,
        pending,
        friction_bps=friction_bps,
        initial_cash=INITIAL_CASH,
        binding=None,
    )


def _evaluate_plain_bundle(plaintext: bytes) -> dict[str, object]:
    manifest, entries = open_plain_bundle(plaintext)
    _validate_manifest(manifest)
    market_input, spy_panel, scored_sessions = _panels(entries)
    targets = _targets(market_input)

    friction = run_friction_cases(market_input.scored, targets)
    primary = replay_targets(
        market_input.scored,
        targets,
        friction_bps=PRIMARY_FRICTION_BPS,
        initial_cash=INITIAL_CASH,
    )
    benchmark = _benchmark_replay(spy_panel, PRIMARY_FRICTION_BPS)
    supported = calculate_metrics(primary, benchmark)

    sessions_tuple = tuple(scored_sessions)
    expected = ExpectedSessionAuthority(
        sessions=sessions_tuple,
        sha256=expected_session_identity(sessions_tuple),
    )
    durability = calculate_durability(primary, expected, horizons=(12, 36))
    bootstrap = bootstrap_median_daily_return(primary.daily_returns)

    return {
        "schema_version": "PHASE6-FINAL-HOLDOUT-EVALUATION-v1",
        "authority": "COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE",
        "status": "PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE",
        "evaluation_contract_sha256": CONTRACT_SHA256,
        "candidate_id": primary.candidate_id,
        "binding_sha256": primary.binding_sha256,
        "methodology": "QFQ-NORMALIZED-RESEARCH-v1",
        "decision_grade": False,
        "phase5_formal_status": "PHASE5_UNKNOWN_ABSTAIN",
        "phase5_limitation": "INDEPENDENT_SOURCE_SNAPSHOT_MISSING",
        "performance_classification_threshold": None,
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "candidate_replacement_executed": False,
        "retry_authorized": False,
        "phase4_feedback_written": False,
        "phase5_feedback_written": False,
        "phase7_started": False,
        "production_readiness_approved": False,
        "metrics": supported.model_dump(mode="json"),
        "durability": durability.model_dump(mode="json"),
        "friction": friction.model_dump(mode="json"),
        "bootstrap": bootstrap.model_dump(mode="json"),
    }


def evaluate_released_holdout(
    *,
    release_path: Path,
    contract_path: Path,
    receipt_path: Path,
    encrypted_bundle_path: Path,
    key_path: Path,
    marker_directory: Path,
    output_path: Path,
) -> dict[str, object]:
    output = Path(output_path)
    if output.exists():
        raise FileExistsError("PHASE6_EVALUATION_RESULT_ALREADY_EXISTS")

    load_frozen_contract(contract_path)
    release = load_release_envelope(release_path)
    receipt = _load_receipt(receipt_path)
    if (
        release.holdout_id != receipt["holdout_id"]
        or release.holdout_bundle_sha256 != receipt["bundle_sha256"]
        or release.evaluation_contract_sha256 != CONTRACT_SHA256
    ):
        raise ValueError("PHASE6_RELEASE_RECEIPT_IDENTITY_MISMATCH")

    key = _load_key(key_path)
    if sha256(key).hexdigest() != receipt.get("key_sha256"):
        raise ValueError("PHASE6_HOLDOUT_KEY_IDENTITY_MISMATCH")

    marker_path = Path(marker_directory) / f"{release.release_id}.consumed.json"
    consumed = False
    try:
        encrypted = consume_released_bundle(
            release,
            evaluation_contract_path=contract_path,
            bundle_path=encrypted_bundle_path,
            marker_directory=marker_directory,
        )
        consumed = True
        plaintext = decrypt_bundle(encrypted, key=key)
        if sha256_bytes(plaintext) != receipt.get("plaintext_bundle_sha256"):
            raise ValueError("PHASE6_PLAINTEXT_BUNDLE_IDENTITY_MISMATCH")
        result = {
            **_evaluate_plain_bundle(plaintext),
            "release_id": release.release_id,
            "holdout_id": release.holdout_id,
            "one_time_consumed": True,
        }
    except Exception as exc:
        consumed = consumed or marker_path.is_file()
        if not consumed:
            raise
        result = {
            "schema_version": "PHASE6-FINAL-HOLDOUT-EVALUATION-v1",
            "authority": "COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE",
            "status": "PHASE6_UNKNOWN_ABSTAIN",
            "reason": f"{type(exc).__name__}:{exc}",
            "evaluation_contract_sha256": CONTRACT_SHA256,
            "release_id": release.release_id,
            "holdout_id": release.holdout_id,
            "one_time_consumed": True,
            "candidate_search_executed": False,
            "candidate_parameters_changed": False,
            "candidate_replacement_executed": False,
            "retry_authorized": False,
            "phase4_feedback_written": False,
            "phase5_feedback_written": False,
            "phase7_started": False,
            "production_readiness_approved": False,
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                result,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return result
