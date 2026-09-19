from __future__ import annotations

from pathlib import Path

import pandas as pd

from .accounting import replay_targets
from .authority import load_phase4_authority
from .benchmark import build_benchmark
from .conclusion import classify_phase5
from .dataset import load_opend_dataset, raw_close_frame
from .durability import calculate_durability
from .methodology import FRICTION_CASE_BPS, PRIMARY_FRICTION_BPS
from .reconciliation import reconcile_massive_snapshot
from .signals import generate_targets, target_equivalence
from .targets import extract_sealed_validation_targets


def _fill_sessions(replays: dict[int, object]) -> set[str]:
    values: set[str] = set()
    for replay in replays.values():
        for fill in replay.fills:  # type: ignore[attr-defined]
            values.add(fill.fill_session.strftime("%Y-%m-%d"))
    return values


def evaluate_bundle(
    provider_dir: Path,
    *,
    repository_root: Path,
    massive_snapshot: Path | None = None,
) -> dict[str, object]:
    try:
        load_phase4_authority(repository_root)
    except (OSError, ValueError) as exc:
        return {
            "status": "PHASE5_UNKNOWN_ABSTAIN",
            "reasons": [f"PHASE4_IDENTITY:{exc}"],
            "safety": _safety(),
        }

    try:
        dataset = load_opend_dataset(provider_dir)
    except (OSError, ValueError) as exc:
        return {
            "status": "PHASE5_UNKNOWN_ABSTAIN",
            "reasons": [f"OPEND_DATA:{exc}"],
            "safety": _safety(),
        }

    raw_close = raw_close_frame(dataset)
    try:
        targets = generate_targets(raw_close, dataset.actions.rehab)
        sealed_targets = extract_sealed_validation_targets(repository_root)
        equivalence = target_equivalence(targets, sealed_targets)
    except (OSError, ValueError) as exc:
        return {
            "status": "PHASE5_UNKNOWN_ABSTAIN",
            "reasons": [f"SIGNAL_OR_TARGET:{exc}"],
            "safety": _safety(),
        }

    replays = {
        bps: replay_targets(dataset, targets, friction_bps=bps)
        for bps in FRICTION_CASE_BPS
    }
    benchmarks = {
        bps: build_benchmark(dataset, targets, friction_bps=bps)
        for bps in FRICTION_CASE_BPS
    }
    summaries = {
        bps: calculate_durability(dataset, replays[bps], benchmarks[bps])
        for bps in FRICTION_CASE_BPS
    }

    comparison_end = pd.Timestamp("2022-12-30", tz="UTC")
    comparison_replay = replay_targets(
        dataset,
        sealed_targets,
        friction_bps=PRIMARY_FRICTION_BPS,
        start_session=sealed_targets[0].signal_session,
        end_session=comparison_end,
    )
    comparison_benchmark = build_benchmark(
        dataset,
        sealed_targets,
        friction_bps=PRIMARY_FRICTION_BPS,
        end_session=comparison_end,
    )
    comparison_summary = calculate_durability(
        dataset, comparison_replay, comparison_benchmark
    )

    reconciliation = reconcile_massive_snapshot(
        dataset,
        massive_snapshot,
        fill_sessions=_fill_sessions(replays),
    )
    decision = classify_phase5(
        identity_ok=True,
        reconciliation=reconciliation,
        equivalence=equivalence,
        primary=summaries[PRIMARY_FRICTION_BPS],
        friction_25=summaries[25],
    )
    return {
        **decision,
        "schema_version": "PHASE5-EVALUATION-v1",
        "common_history": {
            "first_session": dataset.first_common_session,
            "last_session": dataset.last_common_session,
            "years": dataset.common_history_years,
            "session_count": len(dataset.common_sessions),
            "provider_manifest_sha256": dataset.provider_manifest_sha256,
        },
        "signal_equivalence": equivalence,
        "reconciliation": reconciliation,
        "durability_by_friction_bps": {str(key): value for key, value in summaries.items()},
        "phase4_comparison_slice": comparison_summary,
        "safety": _safety(),
    }


def _safety() -> dict[str, object]:
    return {
        "final_holdout_accessed": False,
        "protected_symbols_accessed": [],
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "phase4_feedback_written": False,
        "live_trading_capability": False,
        "phase6_started": False,
    }
