from __future__ import annotations

import csv
import os
from pathlib import Path
import tempfile
from typing import Iterable

from investment_tracker.quant.experiments import ExperimentRecord


LEADERBOARD_FIELDS = (
    "experiment_id",
    "candidate_id",
    "strategy_family",
    "score",
    "accepted",
    "validation_cagr",
    "sharpe",
    "max_drawdown",
    "stop_reason",
)


def load_experiments(directory: Path) -> tuple[ExperimentRecord, ...]:
    directory = Path(directory)
    records = []
    for path in sorted(directory.glob("*.json")):
        records.append(ExperimentRecord.model_validate_json(path.read_text(encoding="utf-8")))
    return tuple(records)


def _rank_key(record: ExperimentRecord) -> tuple[bool, float, str]:
    return (record.score is None, -(record.score or 0.0), record.experiment_id)


def _display(value: object) -> str:
    return "UNKNOWN" if value is None else str(value)


def leaderboard_rows(records: Iterable[ExperimentRecord]) -> list[dict[str, object]]:
    rows = []
    for record in sorted(records, key=_rank_key):
        rows.append({
            "experiment_id": record.experiment_id,
            "candidate_id": record.candidate_manifest.candidate_id,
            "strategy_family": record.candidate_manifest.strategy_family,
            "score": _display(record.score),
            "accepted": record.accepted,
            "validation_cagr": _display(record.validation_metrics.get("cagr")),
            "sharpe": _display(record.validation_metrics.get("sharpe")),
            "max_drawdown": _display(record.validation_metrics.get("max_drawdown", record.metrics.get("max_drawdown"))),
            "stop_reason": record.stop_reason,
        })
    return rows


def write_leaderboard(records: Iterable[ExperimentRecord], destination: Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent, text=True)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=LEADERBOARD_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(leaderboard_rows(records))
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def render_report(records: Iterable[ExperimentRecord]) -> str:
    ranked = sorted(records, key=_rank_key)
    lines = [
        "# ETF Quant Research Report",
        "",
        "Research-only historical evidence. Human and Independent Audit approval remain required.",
        "",
        f"Experiments: {len(ranked)}",
        "",
    ]
    for record in ranked:
        lines.extend([
            f"## {record.experiment_id}",
            "",
            f"Candidate: {record.candidate_manifest.candidate_id}",
            f"Family: {record.candidate_manifest.strategy_family}",
            f"Score: {_display(record.score)}",
            f"Validation CAGR: {_display(record.validation_metrics.get('cagr'))}",
            f"Sharpe: {_display(record.validation_metrics.get('sharpe'))}",
            f"Max drawdown: {_display(record.validation_metrics.get('max_drawdown', record.metrics.get('max_drawdown')))}",
            f"Accepted: {record.accepted}",
            f"Reason: {record.reason}",
            f"Stop reason: {record.stop_reason}",
            "",
        ])
    if not ranked:
        lines.extend(["No experiment evidence is available.", ""])
    return "\n".join(lines)


def write_report(records: Iterable[ExperimentRecord], destination: Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = render_report(records)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent, text=True)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
