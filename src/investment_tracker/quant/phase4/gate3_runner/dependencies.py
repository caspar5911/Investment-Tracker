from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from investment_tracker.quant.phase4.engine.market import MarketPanel, ScoredMarketInput
from investment_tracker.quant.phase4.gate3.authorities import SYMBOLS
from investment_tracker.quant.phase4.gate3.inputs import (
    _read_identity,
    _safe_path,
    load_frozen_authority_inputs,
)
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity
from investment_tracker.quant.phase4.gate3.seal import (
    GATE1_MANIFEST_IDENTITY,
    GATE2_MANIFEST_IDENTITY,
    TRAIN_IDENTITY,
    VALIDATION_IDENTITY,
)
from investment_tracker.quant.phase4.gate3_campaign.dependencies import ResultAuthority
from investment_tracker.quant.phase4.gate3_campaign.result_methodology import (
    load_result_authority,
    preflight_result_schema,
)


RESULT_SCHEMA_CONTENT = "70cabdd78bb5f473fbb94f969c21fd5add185ccc46f00fb217c2b415f404fa96"
SCORED_PANEL_SHA256 = "410465adf5765cb2d316eda1d00d718c99f4aa8c3634ce99cda00d11a08496c0"


@dataclass(frozen=True)
class RunnerDependencies:
    root: Path
    result_authority: ResultAuthority
    market_input: ScoredMarketInput

    @property
    def campaign(self):
        return self.result_authority.dependencies


def _load_train_warmup(root: Path, authority: ResultAuthority) -> MarketPanel:
    frozen = load_frozen_authority_inputs(
        root,
        gate1_identity=GATE1_MANIFEST_IDENTITY,
        gate2_identity=GATE2_MANIFEST_IDENTITY,
    )
    if frozen.train_identity != TRAIN_IDENTITY or frozen.validation_identity != VALIDATION_IDENTITY:
        raise ValueError("RUNNER_PARTITION_IDENTITY_MISMATCH")
    split = json.loads(_read_identity(root, frozen.split))
    partitions = split.get("partitions")
    if not isinstance(partitions, list) or len(partitions) != 8:
        raise ValueError("RUNNER_SPLIT_MISMATCH")

    all_sessions = frozen.all_sessions
    train_count = TRAIN_IDENTITY.row_count
    train_sessions = tuple(pd.Timestamp(day, tz="UTC") for day in all_sessions[:train_count])
    if len(train_sessions) != 1258 or train_sessions[-1] >= authority.dependencies.sessions[0]:
        raise ValueError("RUNNER_WARMUP_SESSION_MISMATCH")

    opens: dict[str, tuple[float, ...]] = {}
    closes: dict[str, tuple[float, ...]] = {}
    for partition in partitions:
        if not isinstance(partition, dict):
            raise ValueError("RUNNER_SPLIT_MISMATCH")
        symbol = partition.get("symbol")
        if symbol not in SYMBOLS:
            raise ValueError("RUNNER_UNIVERSE_MISMATCH")
        bars = ArtifactIdentity(**partition["bars_artifact"])
        _read_identity(root, bars)
        table = pq.read_table(_safe_path(root, bars.path), columns=["timestamp", "open", "close"])
        observed = tuple(item.strftime("%Y-%m-%d") for item in table.column("timestamp").to_pylist())
        if observed != all_sessions:
            raise ValueError("RUNNER_BAR_CALENDAR_MISMATCH")
        opens[str(symbol)] = tuple(float(value) for value in table.column("open").to_pylist()[:train_count])
        closes[str(symbol)] = tuple(float(value) for value in table.column("close").to_pylist()[:train_count])

    symbols = authority.dependencies.scored_panel.symbols
    if tuple(sorted(opens)) != symbols or frozenset(symbols) != frozenset(SYMBOLS):
        raise ValueError("RUNNER_UNIVERSE_MISMATCH")
    open_frame = pd.DataFrame({symbol: opens[symbol] for symbol in symbols}, index=pd.DatetimeIndex(train_sessions))
    close_frame = pd.DataFrame({symbol: closes[symbol] for symbol in symbols}, index=pd.DatetimeIndex(train_sessions))
    warmup = MarketPanel.from_frames(open_frame, close_frame, role="WARMUP")
    if warmup.symbols != authority.dependencies.scored_panel.symbols:
        raise ValueError("RUNNER_WARMUP_SYMBOL_MISMATCH")
    return warmup


def load_runner_dependencies(
    repository_root: Path,
    *,
    result_schema_content_sha256: str = RESULT_SCHEMA_CONTENT,
) -> RunnerDependencies:
    root = repository_root.absolute()
    state = preflight_result_schema(root, result_schema_content_sha256)
    if state.status != "GATE3_CAMPAIGN_RESULT_SCHEMA_SEALED":
        raise ValueError("RUNNER_RESULT_SCHEMA_NOT_SEALED")
    authority = load_result_authority(root, result_schema_content_sha256)
    deps = authority.dependencies
    if (
        len(deps.bindings) != 180
        or tuple(binding.budget_position for binding in deps.bindings) != tuple(range(1, 181))
        or len({binding.candidate_id for binding in deps.bindings}) != 180
        or deps.scored_panel.panel_sha256 != SCORED_PANEL_SHA256
        or len(deps.sessions) != 1008
    ):
        raise ValueError("RUNNER_DEPENDENCY_MISMATCH")
    warmup = _load_train_warmup(root, authority)
    market_input = ScoredMarketInput.from_panels(warmup, deps.scored_panel)
    if (
        len(market_input.indicator_warmup.sessions) != 1258
        or len(market_input.scored.sessions) != 1008
        or market_input.scored_panel_sha256 != SCORED_PANEL_SHA256
    ):
        raise ValueError("RUNNER_MARKET_INPUT_MISMATCH")
    return RunnerDependencies(root=root, result_authority=authority, market_input=market_input)


__all__ = (
    "RESULT_SCHEMA_CONTENT",
    "RunnerDependencies",
    "SCORED_PANEL_SHA256",
    "load_runner_dependencies",
)
