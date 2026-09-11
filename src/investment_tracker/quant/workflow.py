from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import inspect
import json
from pathlib import Path
import subprocess
from typing import Iterable, Mapping
from uuid import uuid4

import numpy as np
import pandas as pd

from .backtest.benchmark import aggregate_equal_weight, buy_and_hold
from .backtest.engine import run_backtest
from .backtest.metrics import PerformanceMetrics, calculate_metrics, metrics_for_backtest
from .backtest.models import ExecutionAssumptions
from .configuration import QuantConfig
from .data.cache import ImmutableParquetCache, content_hash
from .data.models import DataRequest
from .experiments import (
    ExperimentRecord,
    ExperimentStore,
    ResearchCandidateManifest,
    artifact_digest,
)
from .moomoo.strategybase_exporter import export_strategy
from .optimizer.candidate_generator import CandidateConfiguration, CandidateGenerator, default_generators
from .optimizer.scorer import CandidateEvidence, ScoreBreakdown, score_candidate
from .promotion import BaselineRegistry, PromotionGate, ValidatedSnapshot, promote_candidate
from .reports.generate_report import load_experiments, write_leaderboard, write_report
from .strategies.base import StrategyDefinition
from .strategies.registry import build_strategy
from .validation.access import SplitDefinition
from .validation.robustness import friction_scenarios, neighbor_parameters, robustness_summary


@dataclass(frozen=True)
class FixturePipelineResult:
    experiment_count: int
    final_holdout_accessed: bool
    snapshot: ValidatedSnapshot
    export_path: Path


@dataclass(frozen=True)
class EvaluatedCandidate:
    configuration: CandidateConfiguration
    evidence: CandidateEvidence
    score: ScoreBreakdown
    train_metrics: PerformanceMetrics
    validation_metrics: PerformanceMetrics
    benchmark_validation_metrics: PerformanceMetrics
    experiment: ExperimentRecord


def run_fixture_pipeline(
    root: Path,
    *,
    fixture_universe: tuple[str, ...] = ("SPY", "QQQ"),
) -> FixturePipelineResult:
    root = Path(root)
    bars_by_symbol = {
        symbol: _fixture_bars(offset=index * 10.0)
        for index, symbol in enumerate(fixture_universe)
    }
    split_index = len(next(iter(bars_by_symbol.values()))) // 2
    first = next(iter(bars_by_symbol.values()))
    train_period = (first.index[0].date(), first.index[split_index - 1].date())
    validation_period = (first.index[split_index].date(), first.index[-1].date())
    split_definition = SplitDefinition.create(
        version="QUANT-SPLIT-v1",
        train_start=train_period[0],
        train_end=train_period[1],
        validation_start=validation_period[0],
        validation_end=validation_period[1],
        final_holdout_start=validation_period[1] + timedelta(days=1),
        final_holdout_end=validation_period[1] + timedelta(days=365),
    )
    assumptions = ExecutionAssumptions(100_000.0, 1.0, 2.0, True)
    candidates = CandidateGenerator.from_parameter_grid(
        "trend",
        {"fast_window": [5, 10], "slow_window": [20, 30], "allocation": [1.0]},
    )
    results_directory = root / "results"
    evaluated = _evaluate_and_store(
        candidates,
        bars_by_symbol,
        train_period,
        validation_period,
        split_definition,
        assumptions,
        results_directory,
        dependency_lock_hash=artifact_digest("FIXTURE_DEPENDENCY_LOCK"),
        reason_prefix="FIXTURE_ONLY deterministic mechanical validation",
    )
    accepted = [item for item in evaluated if item.experiment.accepted]
    if not accepted:
        raise RuntimeError("deterministic fixture produced no mechanically validated candidate")
    best = max(accepted, key=lambda item: float(item.score.total or float("-inf")))
    gate = PromotionGate(
        research_passed=best.train_metrics.total_return > 0,
        validation_passed=best.validation_metrics.total_return > 0,
        walk_forward_passed=bool(best.evidence.walk_forward_consistency == 1.0),
        robustness_passed=not best.evidence.robustness_deteriorated,
        benchmark_passed=bool(best.evidence.benchmark_excess_return and best.evidence.benchmark_excess_return > 0),
        tests_passed=True,
    )
    snapshot = promote_candidate(best.experiment, gate, BaselineRegistry(results_directory / "baselines"))
    snapshot_path = results_directory / "validated" / f"{snapshot.digest}.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with snapshot_path.open("x", encoding="utf-8") as handle:
        json.dump(snapshot.model_dump(mode="json"), handle, sort_keys=True, separators=(",", ":"))
    export_path = results_directory / "exports" / f"{snapshot.digest}.py"
    export_strategy(snapshot, export_path, symbol=fixture_universe[0])
    records = load_experiments(results_directory / "experiments")
    write_leaderboard(records, results_directory / "leaderboard.csv")
    write_report(records, results_directory / "latest_report.md")
    return FixturePipelineResult(len(evaluated), False, snapshot, export_path)


def optimize_cached_universe(
    *,
    config: QuantConfig,
    cache_root: Path,
    results_dir: Path,
) -> dict[str, object]:
    request_start = config.validation.train_start
    request_end = config.validation.validation_end
    cache = ImmutableParquetCache(cache_root)
    datasets = {}
    bars_by_symbol = {}
    for symbol in config.universe.symbols:
        request = DataRequest(symbol=symbol, start=request_start, end=request_end)
        dataset = cache.find(request)
        if dataset is None:
            raise FileNotFoundError(f"clean cached data unavailable for {symbol}")
        datasets[symbol] = dataset
        bars_by_symbol[symbol] = dataset.frame

    split_definition = SplitDefinition.create(
        version="QUANT-SPLIT-v1",
        train_start=config.validation.train_start,
        train_end=config.validation.train_end,
        validation_start=config.validation.validation_start,
        validation_end=config.validation.validation_end,
        final_holdout_start=config.validation.final_holdout_start,
        final_holdout_end=config.validation.final_holdout_end,
    )
    assumptions = ExecutionAssumptions(
        config.backtest.initial_capital,
        config.backtest.commission_bps,
        config.backtest.slippage_bps,
        config.backtest.allow_fractional,
    )
    lock_hash = _dependency_lock_hash(Path("requirements-quant.lock"))
    all_evaluated: list[EvaluatedCandidate] = []
    family_stops = {}
    for family, generator in default_generators().items():
        bounded = tuple(generator)[: config.validation.max_candidates_per_family]
        stale = 0
        best_score: float | None = None
        stop_reason = "EXHAUSTED"
        for configuration in bounded:
            item = _evaluate_and_store(
                CandidateGenerator((configuration,)),
                bars_by_symbol,
                (config.validation.train_start, config.validation.train_end),
                (config.validation.validation_start, config.validation.validation_end),
                split_definition,
                assumptions,
                Path(results_dir),
                dependency_lock_hash=lock_hash,
                reason_prefix="MARKET_DATA_RESEARCH_ONLY",
                data_hashes={symbol: dataset.metadata.content_hash for symbol, dataset in datasets.items()},
            )[0]
            all_evaluated.append(item)
            if item.evidence.robustness_deteriorated:
                stop_reason = "ROBUSTNESS_DETERIORATED"
                break
            score = item.score.total
            if score is not None and (best_score is None or score > best_score + 0.01):
                best_score = score
                stale = 0
            else:
                stale += 1
                if stale >= config.validation.patience:
                    stop_reason = "NO_MEANINGFUL_IMPROVEMENT_50"
                    break
        family_stops[family] = stop_reason
    records = load_experiments(Path(results_dir) / "experiments")
    write_leaderboard(records, Path(results_dir) / "leaderboard.csv")
    write_report(records, Path(results_dir) / "latest_report.md")
    best = max(
        (item for item in all_evaluated if item.score.total is not None),
        key=lambda item: float(item.score.total),
        default=None,
    )
    return {
        "status": "RESEARCH_ONLY",
        "experiment_count": len(all_evaluated),
        "family_stop_reasons": family_stops,
        "best_candidate_id": None if best is None else best.configuration.candidate_id,
        "best_score": None if best is None else best.score.total,
        "final_holdout_accessed": False,
    }


def _evaluate_and_store(
    candidates: Iterable[CandidateConfiguration],
    bars_by_symbol: Mapping[str, pd.DataFrame],
    train_period: tuple[date, date],
    validation_period: tuple[date, date],
    split_definition: SplitDefinition,
    assumptions: ExecutionAssumptions,
    results_directory: Path,
    *,
    dependency_lock_hash: str,
    reason_prefix: str,
    data_hashes: Mapping[str, str] | None = None,
) -> list[EvaluatedCandidate]:
    experiment_store = ExperimentStore(results_directory / "experiments")
    evaluated: list[EvaluatedCandidate] = []
    hashes = dict(data_hashes or {symbol: content_hash(frame) for symbol, frame in bars_by_symbol.items()})
    for configuration in candidates:
        strategy = build_strategy(configuration.family, configuration.parameters)
        train_frames = {symbol: _slice(frame, train_period) for symbol, frame in bars_by_symbol.items()}
        validation_frames = {symbol: _slice(frame, validation_period) for symbol, frame in bars_by_symbol.items()}
        train_metrics = _portfolio_metrics(strategy, train_frames, assumptions)
        validation_metrics = _portfolio_metrics(strategy, validation_frames, assumptions)
        benchmark_metrics = _benchmark_metrics(validation_frames, assumptions)
        neighbor_returns = _neighbor_returns(strategy, validation_frames, assumptions)
        friction_returns = _friction_returns(strategy, validation_frames, assumptions)
        fold_returns = _fold_returns(strategy, validation_frames, assumptions, folds=3)
        robust = robustness_summary(
            base_validation_return=validation_metrics.total_return,
            neighbor_returns=neighbor_returns,
            friction_returns=friction_returns,
            fold_returns=fold_returns,
        )
        excess = validation_metrics.total_return - benchmark_metrics.total_return
        evidence = CandidateEvidence(
            validation_cagr=validation_metrics.cagr,
            sharpe=validation_metrics.sharpe,
            sortino=validation_metrics.sortino,
            calmar=validation_metrics.calmar,
            benchmark_excess_return=excess,
            walk_forward_consistency=robust.walk_forward_consistency,
            parameter_stability=robust.parameter_stability,
            turnover=validation_metrics.turnover,
            max_drawdown=validation_metrics.max_drawdown,
            friction_sensitivity=robust.friction_sensitivity,
            period_concentration=robust.period_concentration,
            out_of_sample_improved=excess > 0,
            robustness_deteriorated=robust.deteriorated,
        )
        score = score_candidate(evidence)
        accepted = (
            score.status == "RANKED"
            and score.total is not None
            and score.total >= 60.0
            and excess > 0
            and not robust.deteriorated
            and robust.walk_forward_consistency == 1.0
        )
        moment = datetime.now(timezone.utc)
        manifest = ResearchCandidateManifest.create(
            candidate_id=configuration.candidate_id,
            strategy_family=configuration.family,
            strategy_code_hash=_strategy_code_hash(strategy),
            strategy_parameters=configuration.parameters,
            universe_config_hash=artifact_digest(tuple(sorted(bars_by_symbol))),
            data_manifest_hashes=hashes,
            split_definition_hash=split_definition.digest,
            engine_version=assumptions.engine_version,
            fee_model={"name": "notional_bps", "commission_bps": assumptions.commission_bps},
            slippage_model={"name": "adverse_bps", "slippage_bps": assumptions.slippage_bps},
            execution_convention=assumptions.execution_convention,
            dependency_lock_hash=dependency_lock_hash,
            git_commit=_git_commit(),
            created_at=moment,
        )
        experiment_id = f"{configuration.candidate_id}-{moment.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:8]}"
        record = ExperimentRecord(
            experiment_id=experiment_id,
            status="RESEARCH_ONLY",
            candidate_manifest=manifest,
            symbols=tuple(sorted(bars_by_symbol)),
            train_period=train_period,
            validation_period=validation_period,
            metrics=_metrics_dict(train_metrics),
            validation_metrics={
                **_metrics_dict(validation_metrics),
                "benchmark_total_return": benchmark_metrics.total_return,
                "benchmark_excess_return": excess,
                "walk_forward_consistency": robust.walk_forward_consistency,
                "parameter_stability": robust.parameter_stability,
                "friction_sensitivity": robust.friction_sensitivity,
                "period_concentration": robust.period_concentration,
            },
            score=score.total,
            accepted=accepted,
            reason=f"{reason_prefix}; " + ("gates passed" if accepted else "one or more gates failed"),
            stop_reason="CANDIDATE_EVALUATED",
            recorded_at=moment,
        )
        experiment_store.append(record)
        evaluated.append(EvaluatedCandidate(
            configuration, evidence, score, train_metrics, validation_metrics, benchmark_metrics, record
        ))
    return evaluated


def _portfolio_metrics(
    strategy: StrategyDefinition,
    bars_by_symbol: Mapping[str, pd.DataFrame],
    assumptions: ExecutionAssumptions,
) -> PerformanceMetrics:
    results = {
        symbol: run_backtest(frame, strategy.targets(frame), assumptions)
        for symbol, frame in bars_by_symbol.items()
    }
    equity = aggregate_equal_weight(
        {symbol: result.equity_curve for symbol, result in results.items()},
        assumptions.initial_capital,
    )
    exposure = pd.concat(
        [result.exposure_curve for result in results.values()], axis=1
    ).mean(axis=1)
    pnls = tuple(trade.realized_pnl for result in results.values() for trade in result.trades)
    turnover = sum(result.turnover_notional for result in results.values()) / len(results)
    return calculate_metrics(equity, realized_pnls=pnls, turnover_notional=turnover, exposure=exposure)


def _benchmark_metrics(
    bars_by_symbol: Mapping[str, pd.DataFrame],
    assumptions: ExecutionAssumptions,
) -> PerformanceMetrics:
    results = {symbol: buy_and_hold(frame, assumptions) for symbol, frame in bars_by_symbol.items()}
    equity = aggregate_equal_weight(
        {symbol: result.equity_curve for symbol, result in results.items()}, assumptions.initial_capital
    )
    exposure = pd.concat([result.exposure_curve for result in results.values()], axis=1).mean(axis=1)
    turnover = sum(result.turnover_notional for result in results.values()) / len(results)
    return calculate_metrics(equity, turnover_notional=turnover, exposure=exposure)


def _neighbor_returns(
    strategy: StrategyDefinition,
    bars_by_symbol: Mapping[str, pd.DataFrame],
    assumptions: ExecutionAssumptions,
) -> list[float]:
    returns = []
    for parameters in neighbor_parameters(strategy.family, strategy.parameters)[:8]:
        neighbor = build_strategy(strategy.family, parameters)
        returns.append(_portfolio_metrics(neighbor, bars_by_symbol, assumptions).total_return)
    return returns


def _friction_returns(
    strategy: StrategyDefinition,
    bars_by_symbol: Mapping[str, pd.DataFrame],
    assumptions: ExecutionAssumptions,
) -> dict[float, float]:
    base = assumptions.commission_bps + assumptions.slippage_bps
    outcomes = {}
    for total_bps in friction_scenarios(base):
        stressed = ExecutionAssumptions(
            assumptions.initial_capital,
            commission_bps=0.0,
            slippage_bps=total_bps,
            allow_fractional=assumptions.allow_fractional,
        )
        outcomes[total_bps] = _portfolio_metrics(strategy, bars_by_symbol, stressed).total_return
    return outcomes


def _fold_returns(
    strategy: StrategyDefinition,
    bars_by_symbol: Mapping[str, pd.DataFrame],
    assumptions: ExecutionAssumptions,
    *,
    folds: int,
) -> list[float]:
    size = min(len(frame) for frame in bars_by_symbol.values())
    boundaries = np.linspace(0, size, folds + 1, dtype=int)
    outcomes = []
    for start, end in zip(boundaries, boundaries[1:]):
        subset = {symbol: frame.iloc[start:end] for symbol, frame in bars_by_symbol.items()}
        outcomes.append(_portfolio_metrics(strategy, subset, assumptions).total_return)
    return outcomes


def _slice(frame: pd.DataFrame, period: tuple[date, date]) -> pd.DataFrame:
    dates = frame.index.date
    return frame.loc[(dates >= period[0]) & (dates <= period[1])]


def _metrics_dict(metrics: PerformanceMetrics) -> dict[str, float | int | None]:
    return asdict(metrics)


def _strategy_code_hash(strategy: StrategyDefinition) -> str:
    source = inspect.getsource(type(strategy)).encode("utf-8")
    return sha256(source).hexdigest()


def _git_commit() -> str:
    try:
        value = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("git commit identity is required for candidate manifests") from exc
    if len(value) not in (40, 64):
        raise RuntimeError("unexpected git commit identity")
    return value


def _dependency_lock_hash(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError("requirements-quant.lock is required for candidate identity")
    return sha256(path.read_bytes()).hexdigest()


def _fixture_bars(*, offset: float) -> pd.DataFrame:
    returns = []
    for index in range(756):
        returns.append(0.007 if index % 63 < 42 else -0.010)
    prices = [100.0 + offset]
    for value in returns[1:]:
        prices.append(prices[-1] * (1.0 + value))
    close = np.asarray(prices)
    open_price = np.concatenate(([close[0]], close[:-1]))
    return pd.DataFrame(
        {
            "open": open_price,
            "high": np.maximum(open_price, close) * 1.002,
            "low": np.minimum(open_price, close) * 0.998,
            "close": close,
            "volume": np.full(len(close), 1_000_000),
        },
        index=pd.bdate_range("2018-01-02", periods=len(close), tz="UTC", name="timestamp"),
    )
