from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .accounting import ReplayResult, replay_targets
from .dataset import Phase5Dataset
from .methodology import INITIAL_CASH, SYMBOLS
from .signals import TargetDecision


@dataclass(frozen=True)
class BenchmarkResult:
    friction_bps: int
    sessions: tuple[pd.Timestamp, ...]
    close_equity: tuple[float, ...]
    total_turnover: float


def build_benchmark(
    dataset: Phase5Dataset,
    strategy_targets: tuple[TargetDecision, ...],
    *,
    friction_bps: int,
    start_session: pd.Timestamp | None = None,
    end_session: pd.Timestamp | None = None,
) -> BenchmarkResult:
    if not strategy_targets:
        raise ValueError("PHASE5_BENCHMARK_TARGET_SEQUENCE_EMPTY")
    if start_session is None:
        entry = next(
            (item for item in strategy_targets if item.due_session is not None),
            None,
        )
        if entry is None:
            raise ValueError("PHASE5_BENCHMARK_NO_ENTRY_SESSION")
        replay_start = entry.signal_session
    else:
        entry = next(
            (
                item
                for item in strategy_targets
                if item.due_session is not None and item.due_session >= start_session
            ),
            None,
        )
        if entry is None:
            raise ValueError("PHASE5_BENCHMARK_NO_ENTRY_AFTER_START")
        replay_start = start_session

    sleeve_results: list[ReplayResult] = []
    for symbol in SYMBOLS:
        target = TargetDecision(entry.signal_session, entry.due_session, ((symbol, 1.0),))
        sleeve_results.append(
            replay_targets(
                dataset,
                (target,),
                friction_bps=friction_bps,
                initial_cash=INITIAL_CASH / len(SYMBOLS),
                symbols=(symbol,),
                start_session=replay_start,
                end_session=end_session,
            )
        )
    sessions = sleeve_results[0].sessions
    if any(item.sessions != sessions for item in sleeve_results):
        raise ValueError("PHASE5_BENCHMARK_SESSION_MISMATCH")
    equity = tuple(
        sum(result.close_equity[index] for result in sleeve_results)
        for index in range(len(sessions))
    )
    return BenchmarkResult(
        friction_bps,
        sessions,
        equity,
        sum(item.total_turnover for item in sleeve_results),
    )
