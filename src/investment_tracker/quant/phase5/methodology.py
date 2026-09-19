from __future__ import annotations

from investment_tracker.quant.phase4.engine.models import FixedStrategyBinding

PHASE4_FINALIZATION_COMMIT = "69bb4347cbe577c4a1277335eef778ddf5b177d0"
PHASE4_DECISION_CONTENT_SHA256 = "913d14c1061c2cbbb16e66b448b715952c4a360dbda299500eacd0fd61156958"
PHASE4_AUDIT_CONTENT_SHA256 = "684c80fddf5557ff45fe03d8e6fab9ee65c8402f5c18af49f14b4c3188b00411"
PHASE4_MANIFEST_CONTENT_SHA256 = "a4b18e3a97b662b8e2a9134647d759b95bafa41b3f1a53716b77505b2a275281"
SELECTED_RESULT_CONTENT_SHA256 = "77d5d9c131ce57f81a4e40fe6657bcf41ae7dde39995795c337ddbc8ac5f193e"
SELECTED_CANDIDATE_ID = "phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075"
SELECTED_BINDING_SHA256 = "9ff5b11e1b7f381ce574f4b0fc37a16d824e64afa5afeba16be54980c3ed5d3a"
SELECTED_IMPLEMENTATION_SHA256 = "bebb913887573a293e6a8cf23ad3d28e5fa3bbd2f613995e37741ec4d80f7c6f"

SYMBOLS = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")
PROTECTED_SYMBOLS = frozenset(("HACK", "SOXX", "NLR", "URNM", "GEV"))
ACQUISITION_REQUEST_START = "1990-01-01"
ACQUISITION_CUTOFF = "2026-09-18"
PRIMARY_FRICTION_BPS = 3
FRICTION_CASE_BPS = (0, 3, 10, 25, 50)
INITIAL_CASH = 100000.0
LOOKBACK_SESSIONS = 126
SKIP_SESSIONS = 21
TOP_K = 3
REBALANCE_SESSIONS = 21
FIRST_SIGNAL_POSITION = LOOKBACK_SESSIONS + SKIP_SESSIONS

_BINDING_PAYLOAD = {
    "binding_sha256": SELECTED_BINDING_SHA256,
    "budget_position": 150,
    "campaign_id": "PHASE4-FIXED-LONG-ONLY-2014-2022-v1",
    "candidate_id": SELECTED_CANDIDATE_ID,
    "family_definition_sha256": "f39ffaa60053374a6715bdba22190a4151555105bfb0cdb4229190cb12dd95ae",
    "family_id": "phase4-family-fc27985857d177a02f837a76301d681b9c96cc67e41813207d0916d253a1a86d",
    "family_semantic_name": "cross_sectional_absolute_momentum_rotation",
    "grid_spec_sha256": "08c67c0a12fa7aaf25942fe78c47609828a4a8972afa7f8ae718cf97a2aac627",
    "hypothesis_id": "phase4-hypothesis-5d6dab4566bca8c68915f2c9058f34a870f77cc5042b92f6c5ea1a222eaf3fbb",
    "implementation_interface": "PHASE4-FIXED-LONG-ONLY-STRATEGY-v1",
    "implementation_sha256": SELECTED_IMPLEMENTATION_SHA256,
    "parameter_tuple_sha256": "059b8b6c0c574f68c1a0248a08811ca3049e61937b33665ff28472bddeb43737",
    "parameters": [
        {"name": "lookback_sessions", "type": "int", "value": "126"},
        {"name": "rebalance_sessions", "type": "int", "value": "21"},
        {"name": "skip_sessions", "type": "int", "value": "21"},
        {"name": "top_k", "type": "int", "value": "3"},
    ],
    "rule_set_sha256": "9b7dfadb7a0cf4fdd4c179f70dbff409a8d57bace871ca054bc2ad9e3cd77b0d",
    "schema_version": "PHASE4-FIXED-STRATEGY-BINDING-v1",
    "structural_parameters": [],
    "trial_id": "b7173ad220c9440213eab95545a228e80b3349cb060b5acd6bae2b3e1e35b113",
}


def frozen_binding() -> FixedStrategyBinding:
    binding = FixedStrategyBinding.model_validate(_BINDING_PAYLOAD)
    if (
        binding.candidate_id != SELECTED_CANDIDATE_ID
        or binding.binding_sha256 != SELECTED_BINDING_SHA256
        or binding.implementation_sha256 != SELECTED_IMPLEMENTATION_SHA256
        or binding.budget_position != 150
    ):
        raise ValueError("PHASE5_FROZEN_BINDING_MISMATCH")
    return binding


def assert_requested_symbols(symbols: object) -> tuple[str, ...]:
    if isinstance(symbols, (str, bytes)):
        raise ValueError("PHASE5_SYMBOL_REQUEST_INVALID")
    values = tuple(str(item).upper() for item in symbols)  # type: ignore[arg-type]
    if set(values) & PROTECTED_SYMBOLS:
        raise ValueError("PHASE5_PROTECTED_SYMBOL_ACCESS_FORBIDDEN")
    if len(values) != len(SYMBOLS) or set(values) != set(SYMBOLS):
        raise ValueError("PHASE5_UNIVERSE_MISMATCH")
    return SYMBOLS
