"""Generation-2 permanent holdout-exclusion enforcement.

Canonical loader and enforcement point for
``data/governance/holdout-exclusion-registry.json``.

``governance.assert_symbol_allowed`` only locks the five Generation-1 original
holdout symbols. Generation-2 must reject every permanently excluded symbol in
the frozen registry (the research universe, the Generation-1 original holdout,
and the Generation-1 replacement holdout) before any candidate ranking. This
module is additive: it does not modify ``governance`` or the sealed
Generation-1 semantics.

The registry's governance rules are frozen to ``True`` by the model: no
re-entry, no manual exception, apply before ranking, performance independent.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "HoldoutExclusionError",
    "HoldoutExclusionRegistry",
    "assert_holdout_symbols_allowed",
    "excluded_symbols",
    "load_holdout_exclusion_registry",
    "registry_content_sha256",
]

DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "governance"
    / "holdout-exclusion-registry.json"
)


class HoldoutExclusionError(ValueError):
    """Raised when a permanently excluded holdout symbol is requested."""


class _ExclusionGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbols: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)

    @property
    def normalized_symbols(self) -> tuple[str, ...]:
        return tuple(symbol.strip().upper() for symbol in self.symbols)


class _Rules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    no_reentry_into_final_holdout: Literal[True] = True
    no_manual_exception: Literal[True] = True
    registry_must_be_applied_before_ranking: Literal[True] = True
    performance_independent: Literal[True] = True


class HoldoutExclusionRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["HOLDOUT-EXCLUSION-REGISTRY-v1"]
    status: Literal["FROZEN"]
    purpose: str = Field(min_length=1)
    permanent_exclusions: tuple[_ExclusionGroup, ...] = Field(min_length=1)
    rules: _Rules


def _canonical_bytes(registry: HoldoutExclusionRegistry) -> bytes:
    payload = json.loads(registry.model_dump_json())
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


def registry_content_sha256(registry: HoldoutExclusionRegistry) -> str:
    """Stable content identity for the registry (content-addressed evidence)."""
    return hashlib.sha256(_canonical_bytes(registry)).hexdigest()


def load_holdout_exclusion_registry(
    path: Path | str | None = None,
) -> HoldoutExclusionRegistry:
    """Load and validate the frozen holdout-exclusion registry."""
    target = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    raw = json.loads(target.read_text(encoding="utf-8"))
    return HoldoutExclusionRegistry.model_validate(raw)


def excluded_symbols(registry: HoldoutExclusionRegistry) -> frozenset[str]:
    """All permanently excluded symbols, normalized to upper case."""
    return frozenset(
        symbol
        for group in registry.permanent_exclusions
        for symbol in group.normalized_symbols
    )


def assert_holdout_symbols_allowed(
    symbols: Sequence[str] | Iterable[str],
    *,
    registry: HoldoutExclusionRegistry | None = None,
) -> frozenset[str]:
    """Reject any permanently excluded holdout symbol before ranking.

    Symbols are normalized (strip + upper). A caller cannot substitute or
    override the registry contents to permit an excluded symbol.
    """
    active = registry if registry is not None else load_holdout_exclusion_registry()
    excluded = excluded_symbols(active)
    normalized: list[str] = []
    for symbol in symbols:
        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string")
        candidate = symbol.strip().upper()
        if not candidate:
            raise ValueError("symbol must not be empty")
        if candidate in excluded:
            raise HoldoutExclusionError(
                f"excluded holdout symbol denied: {candidate}"
            )
        normalized.append(candidate)
    return frozenset(normalized)
