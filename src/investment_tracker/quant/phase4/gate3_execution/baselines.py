from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from investment_tracker.quant.phase4.engine.execution import _replay, _validated_scored
from investment_tracker.quant.phase4.engine.market import MarketPanel, ScoredMarketInput
from investment_tracker.quant.phase4.engine.models import Gate2Authority, PortfolioReplay
from investment_tracker.quant.phase4.gate3.authorities import SYMBOLS
from investment_tracker.quant.strategies.registry import build_strategy


INITIAL_SLEEVE_CASH = 12500.0
PRIMARY_FRICTION_BPS = 3


@dataclass(frozen=True)
class SleeveReplay:
    symbol: str
    replay: PortfolioReplay


@dataclass(frozen=True)
class BaselineComparison:
    baseline_id: str
    provenance_class: str
    sleeves: tuple[SleeveReplay, ...]
    close_equity: tuple[float, ...]
    daily_returns: tuple[float, ...]
    eligible_for_selection: bool = False


def _validated_pending(
    sessions: tuple[pd.Timestamp, ...],
    symbol: str,
    exposures: tuple[float, ...],
) -> tuple[tuple[pd.Timestamp, pd.Timestamp | None, tuple[tuple[str, float], ...]] | None, ...]:
    if len(exposures) != len(sessions):
        raise ValueError("BASELINE_TARGET_INVALID: exposure/session count mismatch")
    pending = []
    last_submitted = 0.0
    for offset, (session, exposure) in enumerate(zip(sessions, exposures, strict=True)):
        if not math.isfinite(exposure) or not 0.0 <= exposure <= 1.0:
            raise ValueError("BASELINE_TARGET_INVALID: exposure outside long-only range")
        if offset > 0 and np.isclose(exposure, last_submitted, atol=1e-12, rtol=0):
            pending.append(None)
            continue
        due = sessions[offset + 1] if offset + 1 < len(sessions) else None
        if due is not None and not session < due:
            raise ValueError("BASELINE_TARGET_INVALID: noncausal due session")
        instruction = (session, due, ((symbol, exposure),))
        if instruction[0] != session or (due is None) != (offset == len(sessions) - 1):
            raise ValueError("BASELINE_TARGET_INVALID: target alignment mismatch")
        pending.append(instruction)
        last_submitted = exposure
    if len(pending) != len(sessions):
        raise ValueError("BASELINE_TARGET_INVALID: pending count mismatch")
    return tuple(pending)


def _replay_one_sleeve(
    market: ScoredMarketInput,
    symbol: str,
    family: str,
    parameters: dict[str, int | float],
) -> PortfolioReplay:
    scored_open = market.scored.open_prices.loc[:, [symbol]]
    scored_close = market.scored.close_prices.loc[:, [symbol]]
    single_scored = MarketPanel.from_frames(scored_open, scored_close, role="SCORED")
    opens, closes, panel_symbols, sessions = _validated_scored(single_scored)
    if panel_symbols != (symbol,):
        raise ValueError("BASELINE_PANEL_INVALID: sleeve contains another asset")

    history = market.combined_close_history.loc[:, [symbol]]
    strategy = build_strategy(family, parameters)
    target_series = strategy.targets(pd.DataFrame({"close": history[symbol]}, index=history.index))
    warmup_count = len(market.indicator_warmup.sessions)
    exposures = tuple(float(value) for value in target_series.iloc[warmup_count:])
    pending = _validated_pending(sessions, symbol, exposures)
    replay = _replay(
        opens,
        closes,
        panel_symbols,
        sessions,
        pending,
        friction_bps=PRIMARY_FRICTION_BPS,
        initial_cash=INITIAL_SLEEVE_CASH,
        binding=None,
    )
    if (
        replay.candidate_id is not None
        or replay.binding_sha256 is not None
        or replay.initial_cash != INITIAL_SLEEVE_CASH
        or replay.friction_bps != PRIMARY_FRICTION_BPS
        or any(state.cash < 0 or state.realized_gross_exposure > 1.0 for state in replay.states)
    ):
        raise ValueError("BASELINE_REPLAY_INVALID: sleeve self-financing invariant failed")
    due_by_signal = {item[0]: item[1] for item in pending if item is not None}
    if any(
        fill.symbol != symbol
        or fill.signal_timestamp >= fill.fill_timestamp
        or fill.fill_timestamp != due_by_signal.get(fill.signal_timestamp)
        for fill in replay.fills
    ):
        raise ValueError("BASELINE_REPLAY_INVALID: fill violated next-open timing")
    return replay


def simulate_baseline(
    authority: Gate2Authority,
    market: ScoredMarketInput,
    baseline_id: str,
) -> BaselineComparison:
    """Eight independently funded, single-ETF Gate 2 replays; aggregate only afterward."""

    if not isinstance(authority, Gate2Authority) or not isinstance(market, ScoredMarketInput):
        raise ValueError("BASELINE_INPUT_INVALID: sealed authority and market are required")
    if authority.execution_series != "QFQ_NORMALIZED" or authority.primary_friction_bps != 3 or authority.decision_grade:
        raise ValueError("BASELINE_AUTHORITY_INVALID: sealed execution convention changed")
    if market.scored.symbols != tuple(sorted(SYMBOLS)) or market.indicator_warmup.symbols != tuple(sorted(SYMBOLS)):
        raise ValueError("BASELINE_UNIVERSE_INVALID: scored/warm-up symbols differ from frozen universe")
    definitions = {item.baseline_id: item for item in authority.baselines.baselines}
    try:
        definition = definitions[baseline_id]
    except KeyError as exc:
        raise ValueError("BASELINE_ID_INVALID: baseline is not a sealed comparison control") from exc
    if definition.frozen_universe != SYMBOLS or definition.eligible_for_selection:
        raise ValueError("BASELINE_AUTHORITY_INVALID: comparison provenance changed")

    sleeves = tuple(
        SleeveReplay(
            symbol=symbol,
            replay=_replay_one_sleeve(market, symbol, definition.family, definition.parameters),
        )
        for symbol in SYMBOLS
    )
    count = len(market.scored.sessions)
    if any(item.replay.sessions != market.scored.sessions for item in sleeves):
        raise ValueError("BASELINE_REPLAY_INVALID: sleeve session mismatch")
    equity = tuple(
        math.fsum(item.replay.close_equity[offset] for item in sleeves)
        for offset in range(count)
    )
    if equity[0] != 100000.0 or any(not math.isfinite(value) or value <= 0.0 for value in equity):
        raise ValueError("BASELINE_REPLAY_INVALID: aggregate equity invalid")
    daily_returns = tuple(equity[offset] / equity[offset - 1] - 1.0 for offset in range(1, count))
    return BaselineComparison(
        baseline_id=definition.baseline_id,
        provenance_class=definition.provenance_class,
        sleeves=sleeves,
        close_equity=equity,
        daily_returns=daily_returns,
    )
