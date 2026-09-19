from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from investment_tracker.quant.phase4.engine.strategies import _cross_sectional_absolute_momentum
from investment_tracker.quant.phase4.gate3.authorities import (
    REGIME_IDS,
    build_regime_authority,
)

from .methodology import (
    INITIAL_CASH,
    MINIMUM_COMMON_YEARS,
    PRIMARY_FRICTION_BPS,
    PROTECTED_SYMBOLS,
    STRESS_FRICTION_BPS,
    SYMBOLS,
    WARMUP_OBSERVATIONS,
    assert_allowed_symbols,
    frozen_binding,
)


@dataclass(frozen=True)
class ReplayResult:
    friction_bps: int
    sessions: tuple[pd.Timestamp, ...]
    equity: tuple[float, ...]
    cash: tuple[float, ...]
    fills: tuple[dict[str, object], ...]
    total_turnover: float
    corporate_action_events: int

    @property
    def daily_returns(self) -> tuple[float, ...]:
        values = pd.Series(self.equity, index=pd.DatetimeIndex(self.sessions), dtype=float)
        return tuple(float(x) for x in values.pct_change().iloc[1:].to_numpy())


def _canonical_file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _verify_manifest(root: Path) -> dict[str, object]:
    path = root / "manifest.json"
    if not path.is_file():
        raise ValueError("PHASE5_OPEND_MANIFEST_MISSING")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("PHASE5_OPEND_MANIFEST_INVALID") from exc
    if (
        manifest.get("schema_version") != "PHASE5-OPEND-BUNDLE-v1"
        or manifest.get("provider") != "MOOMOO_OPEND"
        or manifest.get("raw_autype") != "NONE"
        or manifest.get("signal_autype") != "QFQ"
        or manifest.get("trading_context_created") is not False
        or manifest.get("final_holdout_accessed") is not False
        or manifest.get("protected_symbols_accessed") != []
    ):
        raise ValueError("PHASE5_OPEND_MANIFEST_GOVERNANCE_MISMATCH")
    symbols = tuple(str(x).upper() for x in manifest.get("symbols", ()))
    assert_allowed_symbols(symbols)
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != len(SYMBOLS) * 3:
        raise ValueError("PHASE5_OPEND_MANIFEST_FILESET_MISMATCH")
    for item in files:
        rel = item.get("path")
        expected = item.get("sha256")
        if not isinstance(rel, str) or not isinstance(expected, str):
            raise ValueError("PHASE5_OPEND_MANIFEST_FILE_INVALID")
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("PHASE5_OPEND_PATH_ESCAPE") from exc
        if not candidate.is_file() or _canonical_file_sha(candidate) != expected:
            raise ValueError("PHASE5_OPEND_FILE_IDENTITY_MISMATCH")
    return manifest


def _load_bar(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"time_key", "open", "close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"PHASE5_BAR_SCHEMA_MISMATCH:{path.name}")
    dates = pd.to_datetime(frame["time_key"].astype(str).str.slice(0, 10), errors="raise", utc=True)
    result = pd.DataFrame(
        {
            "open": pd.to_numeric(frame["open"], errors="raise").astype(float),
            "close": pd.to_numeric(frame["close"], errors="raise").astype(float),
        },
        index=pd.DatetimeIndex(dates),
    )
    if (
        result.empty
        or not result.index.is_unique
        or not result.index.is_monotonic_increasing
        or not np.isfinite(result.to_numpy()).all()
        or (result.to_numpy() <= 0).any()
    ):
        raise ValueError(f"PHASE5_BAR_VALUES_INVALID:{path.name}")
    return result


def _num(row: pd.Series, name: str) -> float:
    if name not in row or pd.isna(row[name]) or row[name] == "":
        return 0.0
    value = float(row[name])
    if not math.isfinite(value):
        raise ValueError(f"PHASE5_REHAB_NONFINITE:{name}")
    return value


def _load_rehab(path: Path) -> dict[pd.Timestamp, list[dict[str, float]]]:
    frame = pd.read_csv(path)
    if frame.empty:
        return {}
    if "ex_div_date" not in frame.columns:
        raise ValueError(f"PHASE5_REHAB_SCHEMA_MISMATCH:{path.name}")
    events: dict[pd.Timestamp, list[dict[str, float]]] = {}
    for _, row in frame.iterrows():
        date = pd.Timestamp(str(row["ex_div_date"])[:10], tz="UTC")
        event = {
            name: _num(row, name)
            for name in (
                "split_base", "split_ert", "join_base", "join_ert",
                "bonus_base", "bonus_ratio", "transfer_base", "transfer_ratio",
                "allot_base", "allot_ratio", "allot_price",
                "cash_dividend", "sp_cash_dividend",
            )
        }
        for unsupported in ("bonus_base", "bonus_ratio", "transfer_base", "transfer_ratio", "allot_base", "allot_ratio", "allot_price"):
            if event[unsupported] != 0.0:
                raise ValueError(f"PHASE5_UNSUPPORTED_CORPORATE_ACTION:{unsupported}")
        events.setdefault(date, []).append(event)
    return events


def load_opend_bundle(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[pd.Timestamp, list[dict[str, float]]]], dict[str, object]]:
    root = Path(root).resolve()
    manifest = _verify_manifest(root)
    raw: dict[str, pd.DataFrame] = {}
    qfq: dict[str, pd.DataFrame] = {}
    rehab: dict[str, dict[pd.Timestamp, list[dict[str, float]]]] = {}
    for symbol in SYMBOLS:
        raw[symbol] = _load_bar(root / "raw" / f"{symbol}.csv")
        qfq[symbol] = _load_bar(root / "qfq" / f"{symbol}.csv")
        rehab[symbol] = _load_rehab(root / "rehab" / f"{symbol}.csv")

    common = raw[SYMBOLS[0]].index
    for symbol in SYMBOLS[1:]:
        common = common.intersection(raw[symbol].index)
    for symbol in SYMBOLS:
        common = common.intersection(qfq[symbol].index)
    common = common.sort_values()
    if len(common) <= WARMUP_OBSERVATIONS + 2:
        raise ValueError("PHASE5_COMMON_HISTORY_TOO_SHORT")

    raw_open = pd.DataFrame({s: raw[s].loc[common, "open"] for s in SYMBOLS}, index=common)
    raw_close = pd.DataFrame({s: raw[s].loc[common, "close"] for s in SYMBOLS}, index=common)
    qfq_close = pd.DataFrame({s: qfq[s].loc[common, "close"] for s in SYMBOLS}, index=common)
    raw_panel = pd.concat({"open": raw_open, "close": raw_close}, axis=1)

    years = (common[-1] - common[0]).days / 365.2425
    if years < MINIMUM_COMMON_YEARS:
        raise ValueError("PHASE5_COMMON_HISTORY_UNDER_15_YEARS")
    meta = {
        "first_common_session": common[0].strftime("%Y-%m-%d"),
        "last_common_session": common[-1].strftime("%Y-%m-%d"),
        "common_session_count": int(len(common)),
        "common_history_years": float(years),
        "manifest_sha256": _canonical_file_sha(root / "manifest.json"),
    }
    return raw_panel, qfq_close, rehab, meta


def _apply_events(
    session: pd.Timestamp,
    holdings: dict[str, float],
    cash: float,
    rehab: dict[str, dict[pd.Timestamp, list[dict[str, float]]]],
) -> tuple[float, int]:
    count = 0
    for symbol in SYMBOLS:
        for event in rehab[symbol].get(session, ()):
            units_before = holdings[symbol]
            split_base, split_ert = event["split_base"], event["split_ert"]
            join_base, join_ert = event["join_base"], event["join_ert"]
            if split_base > 0.0 or split_ert > 0.0:
                if split_base <= 0.0 or split_ert <= 0.0:
                    raise ValueError("PHASE5_SPLIT_RATIO_INVALID")
                holdings[symbol] *= split_base / split_ert
            if join_base > 0.0 or join_ert > 0.0:
                if join_base <= 0.0 or join_ert <= 0.0:
                    raise ValueError("PHASE5_JOIN_RATIO_INVALID")
                holdings[symbol] *= join_ert / join_base
            dividend = event["cash_dividend"] + event["sp_cash_dividend"]
            if dividend:
                cash += units_before * dividend
            count += 1
    return cash, count


def replay(
    raw_panel: pd.DataFrame,
    qfq_close: pd.DataFrame,
    rehab: dict[str, dict[pd.Timestamp, list[dict[str, float]]]],
    *,
    friction_bps: int,
) -> ReplayResult:
    if tuple(qfq_close.columns) != SYMBOLS:
        raise ValueError("PHASE5_SIGNAL_SYMBOL_ORDER_MISMATCH")
    raw_open = raw_panel["open"]
    raw_close = raw_panel["close"]
    if tuple(raw_open.columns) != SYMBOLS or not raw_open.index.equals(qfq_close.index):
        raise ValueError("PHASE5_EXECUTION_SIGNAL_CALENDAR_MISMATCH")
    sessions = tuple(qfq_close.index[WARMUP_OBSERVATIONS:])
    if len(sessions) < 2:
        raise ValueError("PHASE5_SCORED_HISTORY_EMPTY")

    binding = frozen_binding()
    holdings = {symbol: 0.0 for symbol in SYMBOLS}
    cash = float(INITIAL_CASH)
    pending: tuple[pd.Timestamp, tuple[tuple[str, float], ...]] | None = None
    fills: list[dict[str, object]] = []
    equity: list[float] = []
    cash_path: list[float] = []
    total_turnover = 0.0
    event_count = 0
    friction_rate = float(friction_bps) / 10000.0

    for offset, session in enumerate(sessions):
        cash, applied = _apply_events(session, holdings, cash, rehab)
        event_count += applied
        open_row = raw_open.loc[session]
        open_equity = cash + sum(holdings[s] * float(open_row[s]) for s in SYMBOLS)
        if not math.isfinite(open_equity) or open_equity <= 0.0:
            raise ValueError("PHASE5_OPEN_EQUITY_INVALID")

        if pending is not None and pending[0] == session:
            weights = dict(pending[1])
            desired = {s: float(weights.get(s, 0.0)) * open_equity for s in SYMBOLS}
            current = {s: holdings[s] * float(open_row[s]) for s in SYMBOLS}
            deltas = {s: desired[s] - current[s] for s in SYMBOLS}

            for symbol in SYMBOLS:
                delta = deltas[symbol]
                if delta >= -1e-12:
                    continue
                price = float(open_row[symbol])
                target_units = desired[symbol] / price
                units_delta = target_units - holdings[symbol]
                notional = units_delta * price
                fee = abs(notional) * friction_rate
                holdings[symbol] = target_units
                cash += -notional - fee
                total_turnover += abs(notional)
                fills.append({"symbol": symbol, "session": session.isoformat(), "notional": float(notional), "friction": float(fee)})

            buys = {s: d for s, d in deltas.items() if d > 1e-12}
            total_buy = sum(buys.values())
            scale = 1.0
            if total_buy > 0.0 and total_buy * (1.0 + friction_rate) > cash:
                scale = cash / (total_buy * (1.0 + friction_rate))
            for symbol in SYMBOLS:
                if symbol not in buys:
                    continue
                price = float(open_row[symbol])
                notional = buys[symbol] * scale
                fee = notional * friction_rate
                units_delta = notional / price
                holdings[symbol] += units_delta
                cash -= notional + fee
                total_turnover += abs(notional)
                fills.append({"symbol": symbol, "session": session.isoformat(), "notional": float(notional), "friction": float(fee)})
            pending = None

        if cash < -1e-8 or any(value < -1e-12 for value in holdings.values()):
            raise ValueError("PHASE5_LONG_ONLY_ACCOUNTING_BREACH")
        if -1e-8 <= cash < 0.0:
            cash = 0.0

        close_row = raw_close.loc[session]
        close_equity = cash + sum(holdings[s] * float(close_row[s]) for s in SYMBOLS)
        if not math.isfinite(close_equity) or close_equity <= 0.0:
            raise ValueError("PHASE5_CLOSE_EQUITY_INVALID")
        equity.append(float(close_equity))
        cash_path.append(float(cash))

        if offset % 21 == 0:
            history_end = qfq_close.index.get_loc(session)
            signal_history = qfq_close.iloc[: history_end + 1]
            weights = _cross_sectional_absolute_momentum(binding, signal_history)
            if offset + 1 < len(sessions):
                pending = (sessions[offset + 1], weights)

    return ReplayResult(
        friction_bps=int(friction_bps),
        sessions=sessions,
        equity=tuple(equity),
        cash=tuple(cash_path),
        fills=tuple(fills),
        total_turnover=float(total_turnover),
        corporate_action_events=event_count,
    )


def _period_returns(series: pd.Series, frequency: str) -> pd.Series:
    daily = series.pct_change().dropna()
    labels = daily.index.to_period(frequency)
    return daily.groupby(labels).apply(lambda x: float(np.prod(1.0 + x.to_numpy()) - 1.0))


def _rolling_compound(monthly: pd.Series, window: int) -> list[dict[str, object]]:
    if len(monthly) < window:
        return []
    values = monthly.to_numpy(dtype=float)
    out = []
    for end in range(window - 1, len(values)):
        value = float(np.prod(1.0 + values[end - window + 1 : end + 1]) - 1.0)
        out.append({"ending_month": str(monthly.index[end]), "return": value})
    return out


def _regime_summary(qfq_close: pd.DataFrame, replay_result: ReplayResult) -> dict[str, object]:
    all_sessions = tuple(ts.strftime("%Y-%m-%d") for ts in qfq_close.index)
    scored = tuple(ts.strftime("%Y-%m-%d") for ts in replay_result.sessions)
    closes = {symbol: tuple(float(x) for x in qfq_close[symbol].to_numpy()) for symbol in SYMBOLS}
    authority = build_regime_authority(all_sessions, closes, scored)
    mapping = dict(authority.session_to_regime)
    buckets = {name: [] for name in REGIME_IDS}
    for session, value in zip(replay_result.sessions[1:], replay_result.daily_returns, strict=True):
        buckets[mapping[session.strftime("%Y-%m-%d")]].append(float(value))
    result = {}
    for regime in REGIME_IDS:
        values = buckets[regime]
        result[regime] = {
            "observations": len(values),
            "positive_percentage": None if not values else sum(x > 0 for x in values) / len(values),
            "compounded_return": None if not values else float(np.prod(1.0 + np.asarray(values)) - 1.0),
        }
    return result


def summarize(
    replay_result: ReplayResult,
    qfq_close: pd.DataFrame,
    *,
    common_meta: dict[str, object],
) -> dict[str, object]:
    equity = pd.Series(replay_result.equity, index=pd.DatetimeIndex(replay_result.sessions), dtype=float)
    daily = equity.pct_change().dropna()
    total_return = float(equity.iloc[-1] / INITIAL_CASH - 1.0)
    years = (equity.index[-1] - equity.index[0]).days / 365.2425
    cagr = float((equity.iloc[-1] / INITIAL_CASH) ** (1.0 / years) - 1.0)
    std = float(daily.std(ddof=1))
    sharpe = None if std <= 0 else float(daily.mean() / std * math.sqrt(252.0))
    downside = daily[daily < 0.0]
    downside_std = float(downside.std(ddof=1)) if len(downside) >= 2 else 0.0
    sortino = None if downside_std <= 0 else float(daily.mean() / downside_std * math.sqrt(252.0))
    monthly = _period_returns(equity, "M")
    yearly = _period_returns(equity, "Y")
    positive_months = monthly[monthly > 0.0]
    negative_months = monthly[monthly < 0.0]

    streak = longest = 0
    for value in monthly.to_numpy():
        if value < 0.0:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0

    positive_sum = float(positive_months.sum())
    top3 = float(positive_months.nlargest(3).sum()) if len(positive_months) else 0.0

    return {
        "schema_version": "PHASE5-DURABILITY-SUMMARY-v1",
        "candidate_id": frozen_binding().candidate_id,
        "binding_sha256": frozen_binding().binding_sha256,
        "friction_bps": replay_result.friction_bps,
        "common_history": common_meta,
        "scored_first_session": equity.index[0].strftime("%Y-%m-%d"),
        "scored_last_session": equity.index[-1].strftime("%Y-%m-%d"),
        "scored_years": float(years),
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "annualized_one_way_turnover": float(replay_result.total_turnover / INITIAL_CASH / years),
        "calendar_month_returns": {str(k): float(v) for k, v in monthly.items()},
        "calendar_year_returns": {str(k): float(v) for k, v in yearly.items()},
        "positive_month_percentage": float((monthly > 0.0).mean()),
        "positive_year_percentage": float((yearly > 0.0).mean()),
        "average_winning_month": None if positive_months.empty else float(positive_months.mean()),
        "average_losing_month": None if negative_months.empty else float(negative_months.mean()),
        "worst_month": None if monthly.empty else float(monthly.min()),
        "worst_year": None if yearly.empty else float(yearly.min()),
        "longest_losing_month_sequence": int(longest),
        "rolling_12_month": _rolling_compound(monthly, 12),
        "rolling_36_month": _rolling_compound(monthly, 36),
        "rolling_60_month": _rolling_compound(monthly, 60),
        "top_three_positive_month_return_concentration": None if positive_sum <= 0 else float(top3 / positive_sum),
        "recovery_characteristics": {"status": "UNKNOWN", "reason": "DQ-030_UNRESOLVED"},
        "max_drawdown": None,
        "max_drawdown_status": "UNKNOWN",
        "calmar": None,
        "calmar_status": "UNKNOWN",
        "regime_consistency": _regime_summary(qfq_close, replay_result),
        "fill_count": len(replay_result.fills),
        "corporate_action_event_count": replay_result.corporate_action_events,
    }


def evaluate_bundle(root: Path) -> dict[str, object]:
    if PROTECTED_SYMBOLS & set(SYMBOLS):
        return {"status": "ABSTAIN_GOVERNANCE", "reason": "PROTECTED_SYMBOL_UNIVERSE_COLLISION"}
    try:
        raw_panel, qfq_close, rehab, meta = load_opend_bundle(root)
        primary = replay(raw_panel, qfq_close, rehab, friction_bps=PRIMARY_FRICTION_BPS)
        stress = [
            summarize(replay(raw_panel, qfq_close, rehab, friction_bps=bps), qfq_close, common_meta=meta)
            for bps in STRESS_FRICTION_BPS
        ]
        summary = summarize(primary, qfq_close, common_meta=meta)
    except ValueError as exc:
        return {"status": "ABSTAIN_DATA_INCOMPLETE", "reason": str(exc)}
    return {
        "status": "READY_FOR_PASS_REVIEW",
        "phase4_finalization_commit": "69bb4347cbe577c4a1277335eef778ddf5b177d0",
        "primary": summary,
        "stress": stress,
        "safety": {
            "protected_symbols_accessed": [],
            "final_holdout_accessed": False,
            "candidate_changed": False,
            "strategy_search_executed": False,
            "live_trading_capability": False,
        },
    }
