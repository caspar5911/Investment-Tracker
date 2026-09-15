"""Pre-campaign Phase 4 Gate 3 governance authorities only.

This namespace deliberately exposes no candidate execution, campaign,
ranking, survivor-selection, provider, export, account, order, or trading API.
"""

from .authorities import (
    FOLD_IDS,
    REGIME_IDS,
    AuthorityDefinitionError,
    build_fold_authority,
    build_regime_authority,
)
from .seal import preflight_gate3, seal_gate3_authorities

__all__ = (
    "FOLD_IDS",
    "REGIME_IDS",
    "AuthorityDefinitionError",
    "build_fold_authority",
    "build_regime_authority",
    "preflight_gate3",
    "seal_gate3_authorities",
)
