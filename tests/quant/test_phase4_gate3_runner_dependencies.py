from pathlib import Path

from investment_tracker.quant.phase4.gate3.authorities import SYMBOLS
from investment_tracker.quant.phase4.gate3_runner.dependencies import (
    SCORED_PANEL_SHA256,
    load_runner_dependencies,
)


ROOT = Path(__file__).resolve().parents[2]


def test_runner_dependencies_bind_exact_frozen_market_input():
    context = load_runner_dependencies(ROOT)
    assert len(context.campaign.bindings) == 180
    assert tuple(binding.budget_position for binding in context.campaign.bindings) == tuple(range(1, 181))
    assert len(context.market_input.indicator_warmup.sessions) == 1258
    assert len(context.market_input.scored.sessions) == 1008
    assert context.market_input.scored_panel_sha256 == SCORED_PANEL_SHA256
    assert frozenset(context.market_input.scored.symbols) == frozenset(SYMBOLS)
    assert context.market_input.indicator_warmup.sessions[-1] < context.market_input.scored.sessions[0]
