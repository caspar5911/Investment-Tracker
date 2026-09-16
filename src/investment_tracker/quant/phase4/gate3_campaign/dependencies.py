"""Exact dependency metadata loading; no candidate results or strategy calls."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from investment_tracker.quant.phase4.engine.authority import load_gate2_authority
from investment_tracker.quant.phase4.engine.market import MarketPanel
from investment_tracker.quant.phase4.engine.models import CandidateBindingSet, FixedStrategyBinding, Gate2Authority, Phase4EngineManifest
from investment_tracker.quant.phase4.gate3.authorities import LaggedReturnRegimeAuthority, SYMBOLS
from investment_tracker.quant.phase4.gate3.inputs import (
    _read_identity,
    _safe_path,
    load_frozen_authority_inputs,
)
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity, Gate3AuthorityManifest
from investment_tracker.quant.phase4.gate3.seal import GATE1_MANIFEST_IDENTITY, GATE2_MANIFEST_IDENTITY
from investment_tracker.quant.phase4.gate3_execution.methodology import CORRECTED_GATE3_MANIFEST, preflight_execution_methodology

EXECUTION_CONTENT = '9c37e20ccc54132716c3e347b8005d097500a14aeba41d9eedeaf28de3ebe877'


@dataclass(frozen=True)
class Dependencies:
    root: Path
    gate2: Gate2Authority
    engine: Phase4EngineManifest
    gate3: Gate3AuthorityManifest
    execution: ArtifactIdentity
    bindings: tuple[FixedStrategyBinding, ...]
    sessions: tuple[pd.Timestamp, ...]
    scored_panel: MarketPanel
    regime: LaggedReturnRegimeAuthority
    policy_identities: tuple[ArtifactIdentity, ...]

    def neighbors(self, binding):
        family = next(f for f in self.gate2.family_definitions if f.family_id == binding.family_id)
        trial_ids = {c.trial_id for c in family.neighbors(binding.parameter_tuple_sha256)}
        return tuple(sorted((b for b in self.bindings if b.trial_id in trial_ids), key=lambda b: b.trial_id))

    @property
    def engine_sha256(self):
        return next(b.bundle_sha256 for b in self.engine.source_bundles if b.bundle_name == 'engine')


@dataclass(frozen=True)
class ResultAuthority:
    dependencies: Dependencies
    source_revision: str


def identity(value) -> ArtifactIdentity:
    return ArtifactIdentity.model_validate(value.model_dump(mode='json'))


def _load_scored_panel(root: Path) -> MarketPanel:
    frozen = load_frozen_authority_inputs(
        root,
        gate1_identity=GATE1_MANIFEST_IDENTITY,
        gate2_identity=GATE2_MANIFEST_IDENTITY,
    )
    split = json.loads(_read_identity(root, frozen.split))
    partitions = split['partitions']
    expected_all = frozen.all_sessions
    offset = len(expected_all) - len(frozen.validation_sessions)
    open_by_symbol: dict[str, tuple[float, ...]] = {}
    close_by_symbol: dict[str, tuple[float, ...]] = {}
    for partition in partitions:
        symbol = partition['symbol']
        bars = ArtifactIdentity(**partition['bars_artifact'])
        _read_identity(root, bars)
        table = pq.read_table(_safe_path(root, bars.path), columns=['timestamp', 'open', 'close'])
        observed = tuple(value.strftime('%Y-%m-%d') for value in table.column('timestamp').to_pylist())
        if observed != expected_all:
            raise ValueError('SCORED_MARKET_PANEL_MISMATCH')
        open_by_symbol[symbol] = tuple(float(value) for value in table.column('open').to_pylist()[offset:])
        close_by_symbol[symbol] = tuple(float(value) for value in table.column('close').to_pylist()[offset:])
    symbols = tuple(sorted(open_by_symbol))
    if set(symbols) != set(SYMBOLS):
        raise ValueError('SCORED_MARKET_PANEL_MISMATCH')
    sessions = pd.DatetimeIndex(
        tuple(pd.Timestamp(day, tz='UTC') for day in frozen.validation_sessions)
    )
    opens = pd.DataFrame({symbol: open_by_symbol[symbol] for symbol in symbols}, index=sessions)
    closes = pd.DataFrame({symbol: close_by_symbol[symbol] for symbol in symbols}, index=sessions)
    return MarketPanel.from_frames(opens, closes, role='SCORED')


def load_dependencies(root: Path) -> Dependencies:
    root = root.absolute()
    state = preflight_execution_methodology(root, EXECUTION_CONTENT)
    gate2 = load_gate2_authority(root)
    engine = Phase4EngineManifest.model_validate_json(_read_identity(root, GATE2_MANIFEST_IDENTITY))
    gate3 = Gate3AuthorityManifest.model_validate_json(_read_identity(root, CORRECTED_GATE3_MANIFEST))
    binding_ref = next(item for item in engine.write_ledger if item.kind == 'candidate_implementation_bindings')
    bindings = CandidateBindingSet.model_validate_json(_read_identity(root, identity(binding_ref))).bindings
    fold = json.loads(_read_identity(root, gate3.fold_authority))['authority']
    raw = json.loads(_read_identity(root, gate3.regime_authority))['authority']
    for key in ('symbols', 'regime_ids'):
        raw[key] = tuple(raw[key])
    raw['session_to_regime'] = tuple(tuple(row) for row in raw['session_to_regime'])
    policies = tuple(identity(getattr(gate2.manifest, name)) for name in ('survivor_policy', 'durability_policy', 'family_budget_policy'))
    for policy in policies:
        _read_identity(root, policy)
    scored_panel = _load_scored_panel(root)
    sessions = tuple(pd.Timestamp(day, tz='UTC') for day, _ in fold['session_to_fold'])
    if scored_panel.sessions != sessions:
        raise ValueError('SCORED_MARKET_PANEL_MISMATCH')
    return Dependencies(root, gate2, engine, gate3, state.manifest, bindings,
                        sessions, scored_panel, LaggedReturnRegimeAuthority(**raw), policies)
