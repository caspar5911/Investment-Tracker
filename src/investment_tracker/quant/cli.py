from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .reports.generate_report import load_experiments, write_leaderboard, write_report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="python -m investment_tracker.quant.cli",
        description="SIMULATE-only ETF quantitative research",
    )
    subparsers = root.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="cache quote-only historical bars")
    download.add_argument("--config-dir", type=Path)
    download.add_argument("--cache-root", type=Path, default=Path("data/cache"))
    download.add_argument("--host", default="127.0.0.1")
    download.add_argument("--port", type=int, default=11111)
    download.add_argument("--refresh", action="store_true")
    download.add_argument("--preflight", action="store_true")

    backtest = subparsers.add_parser("backtest", help="run one cached-data simulation")
    backtest.add_argument("--config-dir", type=Path)
    backtest.add_argument("--cache-root", type=Path, default=Path("data/cache"))
    backtest.add_argument("--symbol", required=True)
    backtest.add_argument("--family", required=True, choices=("trend", "momentum", "trend_momentum", "risk_managed_trend"))
    backtest.add_argument("--parameters", required=True, help="JSON strategy parameter object")

    optimize = subparsers.add_parser("optimize", help="run bounded deterministic research")
    optimize.add_argument("--config-dir", type=Path)
    optimize.add_argument("--cache-root", type=Path, default=Path("data/cache"))
    optimize.add_argument("--results-dir", type=Path, default=Path("results"))

    validate = subparsers.add_parser("validate", help="validate immutable research artifacts")
    validate.add_argument("--experiments-dir", type=Path, default=Path("results/experiments"))

    report = subparsers.add_parser("report", help="generate derived research views")
    report.add_argument("--experiments-dir", type=Path, default=Path("results/experiments"))
    report.add_argument("--leaderboard", type=Path, default=Path("results/leaderboard.csv"))
    report.add_argument("--report", type=Path, default=Path("results/latest_report.md"))

    export = subparsers.add_parser("export-moomoo", help="export a validated StrategyBase source file")
    export.add_argument("--snapshot", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "report":
            records = load_experiments(args.experiments_dir)
            write_leaderboard(records, args.leaderboard)
            write_report(records, args.report)
            print(json.dumps({"status": "OK", "experiments": len(records)}, sort_keys=True))
            return 0
        if args.command == "validate":
            records = load_experiments(args.experiments_dir)
            print(json.dumps({"status": "OK", "experiments": len(records)}, sort_keys=True))
            return 0
        if args.command == "download":
            return _download(args)
        if args.command == "backtest":
            return _backtest(args)
        if args.command == "optimize":
            return _optimize(args)
        if args.command == "export-moomoo":
            return _export_moomoo(args)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, sort_keys=True))
        return 2
    return 2


def _load_config(directory: Path | None):
    from .configuration import load_default_config, load_quant_config
    return load_default_config() if directory is None else load_quant_config(directory)


def _download(args: argparse.Namespace) -> int:
    from .configuration import load_default_config
    from .data.cache import ImmutableParquetCache
    from .data.models import DataRequest
    from .data.moomoo_client import MoomooHistoricalDataSource
    from .data.repository import HistoricalDataRepository
    from .data.validation import BarDataValidator

    config = _load_config(args.config_dir)
    source_factory = lambda: MoomooHistoricalDataSource(host=args.host, port=args.port)
    if args.preflight:
        source_factory().preflight(config.universe.symbols[0])
        print(json.dumps({"status": "OK", "mode": "SIMULATE", "opend": "REACHABLE"}, sort_keys=True))
        return 0
    repository = HistoricalDataRepository(
        ImmutableParquetCache(args.cache_root), source_factory, BarDataValidator("XNYS")
    )
    datasets = []
    for symbol in config.universe.symbols:
        dataset = repository.load(
            DataRequest(
                symbol=symbol,
                start=config.validation.train_start,
                end=config.validation.validation_end,
            ),
            refresh=args.refresh,
        )
        datasets.append({"symbol": symbol, "hash": dataset.metadata.content_hash})
    print(json.dumps({"status": "OK", "mode": "SIMULATE", "datasets": datasets}, sort_keys=True))
    return 0


def _backtest(args: argparse.Namespace) -> int:
    from .backtest.engine import run_backtest
    from .backtest.metrics import metrics_for_backtest
    from .backtest.models import ExecutionAssumptions
    from .data.cache import ImmutableParquetCache
    from .data.models import DataRequest
    from .strategies.registry import build_strategy

    config = _load_config(args.config_dir)
    request = DataRequest(
        symbol=args.symbol,
        start=config.validation.train_start,
        end=config.validation.validation_end,
    )
    dataset = ImmutableParquetCache(args.cache_root).find(request)
    if dataset is None:
        raise FileNotFoundError("no matching clean cached dataset")
    strategy = build_strategy(args.family, json.loads(args.parameters))
    assumptions = ExecutionAssumptions(
        initial_capital=config.backtest.initial_capital,
        commission_bps=config.backtest.commission_bps,
        slippage_bps=config.backtest.slippage_bps,
        allow_fractional=config.backtest.allow_fractional,
    )
    result = run_backtest(dataset.frame, strategy.targets(dataset.frame), assumptions)
    print(json.dumps(metrics_for_backtest(result).__dict__, sort_keys=True))
    return 0


def _optimize(args: argparse.Namespace) -> int:
    from .workflow import optimize_cached_universe
    summary = optimize_cached_universe(
        config=_load_config(args.config_dir),
        cache_root=args.cache_root,
        results_dir=args.results_dir,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


def _export_moomoo(args: argparse.Namespace) -> int:
    from .moomoo.strategybase_exporter import export_strategy
    from .promotion import ValidatedSnapshot
    snapshot = ValidatedSnapshot.model_validate_json(args.snapshot.read_text(encoding="utf-8"))
    path = export_strategy(snapshot, args.output)
    print(json.dumps({"status": "OK", "output": str(path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
