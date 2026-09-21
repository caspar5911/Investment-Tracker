from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_tracker.quant.generation2.holdout_exclusion import (
    DEFAULT_REGISTRY_PATH,
    HoldoutExclusionError,
    HoldoutExclusionRegistry,
    assert_holdout_symbols_allowed,
    excluded_symbols,
    load_holdout_exclusion_registry,
    registry_content_sha256,
)

RESEARCH_UNIVERSE = {"GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP"}
GENERATION1_ORIGINAL = {"HACK", "SOXX", "NLR", "URNM", "GEV"}
GENERATION1_REPLACEMENT = {"FQAL", "FDMO", "CSB", "FTXO", "VNLA"}
ALL_EXCLUDED = RESEARCH_UNIVERSE | GENERATION1_ORIGINAL | GENERATION1_REPLACEMENT


@pytest.fixture(scope="module")
def registry() -> HoldoutExclusionRegistry:
    return load_holdout_exclusion_registry()


def test_default_registry_path_lives_in_repository() -> None:
    assert DEFAULT_REGISTRY_PATH.is_file()
    assert DEFAULT_REGISTRY_PATH.name == "holdout-exclusion-registry.json"


def test_registry_schema_and_frozen_status(registry: HoldoutExclusionRegistry) -> None:
    assert registry.schema_version == "HOLDOUT-EXCLUSION-REGISTRY-v1"
    assert registry.status == "FROZEN"
    assert len(registry.permanent_exclusions) == 3


def test_registry_rules_are_locked_to_true(registry: HoldoutExclusionRegistry) -> None:
    rules = registry.rules
    assert rules.no_reentry_into_final_holdout is True
    assert rules.no_manual_exception is True
    assert rules.registry_must_be_applied_before_ranking is True
    assert rules.performance_independent is True


def test_loader_covers_all_permanent_exclusions(registry: HoldoutExclusionRegistry) -> None:
    assert excluded_symbols(registry) == ALL_EXCLUDED


def test_every_permanent_exclusion_is_rejected(registry: HoldoutExclusionRegistry) -> None:
    for symbol in sorted(ALL_EXCLUDED):
        with pytest.raises(HoldoutExclusionError):
            assert_holdout_symbols_allowed([symbol], registry=registry)


def test_non_excluded_symbol_is_allowed(registry: HoldoutExclusionRegistry) -> None:
    assert assert_holdout_symbols_allowed(["XOM", "XLE"], registry=registry) == {
        "XOM",
        "XLE",
    }


def test_case_and_whitespace_bypass_is_rejected(registry: HoldoutExclusionRegistry) -> None:
    for variant in ("gld", "Gld", " GLD ", "GLD"):
        with pytest.raises(HoldoutExclusionError):
            assert_holdout_symbols_allowed([variant], registry=registry)


def test_mixed_batch_rejected_when_one_symbol_is_excluded(
    registry: HoldoutExclusionRegistry,
) -> None:
    with pytest.raises(HoldoutExclusionError):
        assert_holdout_symbols_allowed(["XOM", "SPY"], registry=registry)


def test_empty_symbol_rejected(registry: HoldoutExclusionRegistry) -> None:
    with pytest.raises(ValueError):
        assert_holdout_symbols_allowed(["   "], registry=registry)


def test_non_string_symbol_rejected(registry: HoldoutExclusionRegistry) -> None:
    with pytest.raises(TypeError):
        assert_holdout_symbols_allowed([42], registry=registry)  # type: ignore[list-item]


def test_registry_content_sha256_is_stable(registry: HoldoutExclusionRegistry) -> None:
    first = registry_content_sha256(registry)
    second = registry_content_sha256(load_holdout_exclusion_registry())
    assert first == second
    assert len(first) == 64
    assert first == second.lower()


def test_mutated_registry_status_rejected(tmp_path: Path) -> None:
    raw = json.loads(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    raw["status"] = "DRAFT"
    target = tmp_path / "registry.json"
    target.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_holdout_exclusion_registry(target)


def test_manual_exception_rule_cannot_be_disabled(tmp_path: Path) -> None:
    raw = json.loads(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    raw["rules"]["no_manual_exception"] = False
    target = tmp_path / "registry.json"
    target.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_holdout_exclusion_registry(target)


def test_removing_a_symbol_from_registry_is_detected(
    registry: HoldoutExclusionRegistry,
    tmp_path: Path,
) -> None:
    raw = json.loads(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    # Remove the entire research group; the hash must differ from the real one.
    raw["permanent_exclusions"] = raw["permanent_exclusions"][1:]
    mutated = json.loads(json.dumps(raw))
    target = tmp_path / "registry.json"
    target.write_text(json.dumps(mutated), encoding="utf-8")
    loaded = load_holdout_exclusion_registry(target)
    assert excluded_symbols(loaded) != excluded_symbols(registry)
    assert registry_content_sha256(loaded) != registry_content_sha256(registry)


def test_no_override_permits_an_excluded_symbol(registry: HoldoutExclusionRegistry) -> None:
    # Passing the registry explicitly must not bypass enforcement.
    with pytest.raises(HoldoutExclusionError):
        assert_holdout_symbols_allowed(["QQQ"], registry=registry)
    # And the default (no-registry) path enforces the same set.
    with pytest.raises(HoldoutExclusionError):
        assert_holdout_symbols_allowed(["QQQ"])
