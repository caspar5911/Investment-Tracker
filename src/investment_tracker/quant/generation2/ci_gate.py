"""Generation-2 synthetic-only CI rehearsal gate (B4).

This module implements the dedicated CI stage that must stay green for the
generation-2 implementation. It is *fail-closed* and *synthetic only*: it makes
no provider call and touches no network. Its purpose is to make it impossible
to issue a real final-holdout authorization (or to authorize Phase 7) while the
generation-2 pipeline is in flight: the frozen governance authority must keep
every real-boundary flag exactly ``false``, and the permanent holdout-exclusion
registry must still cover the entire research universe.

If any of these invariants is violated, ``evaluate`` raises :class:`CiGateError`
and ``main`` exits non-zero, which red the CI stage and therefore blocks the
commit that would have flipped a real boundary.

Run from a repository checkout::

    python -m investment_tracker.quant.generation2.ci_gate --repository-root .
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

GATE_SCHEMA = "G2-SYNTHETIC-CI-GATE-v1"

AUTHORITY_REL = "data/governance/generation2-governance-authority.json"
REGISTRY_REL = "data/governance/holdout-exclusion-registry.json"

# The research universe frozen in the generation-2 preregistration. Every one
# of these symbols must remain permanently excluded from final-holdout
# selection while generation 2 is under campaign.
RESEARCH_SYMBOLS = ("GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP")

# Real-boundary flags that must be exactly ``false`` (not merely "not true").
FORBIDDEN_TRUE_KEYS = (
    "real_final_holdout_access_authorized",
    "phase7_authorized",
    "production_readiness_approved",
)


class CiGateError(RuntimeError):
    """Fail-closed gate error carrying a stable machine-readable code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CiGateError("GATE_GOVERNANCE_FILE_INVALID", str(path)) from exc
    if not isinstance(value, dict):
        raise CiGateError("GATE_GOVERNANCE_FILE_INVALID", str(path))
    return value


def assert_authority_frozen(authority: dict) -> None:
    """Every real-boundary flag must be present and exactly ``false``."""
    if not isinstance(authority, dict):
        raise CiGateError("GATE_AUTHORITY_INVALID")
    for key in FORBIDDEN_TRUE_KEYS:
        if key not in authority:
            raise CiGateError("GATE_AUTHORITY_KEY_MISSING", key)
        if authority[key] is not False:
            raise CiGateError("GATE_AUTHORITY_NOT_FROZEN", key)


def _excluded_symbols(registry: dict) -> set[str]:
    entries = registry.get("permanent_exclusions")
    if not isinstance(entries, list):
        return set()
    excluded: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        symbols = entry.get("symbols")
        if isinstance(symbols, list):
            excluded.update(symbol for symbol in symbols if isinstance(symbol, str))
    return excluded


def assert_holdout_registry_active(registry: dict) -> None:
    """The permanent exclusion registry must be non-empty and cover research."""
    if not isinstance(registry, dict):
        raise CiGateError("GATE_REGISTRY_INVALID")
    excluded = _excluded_symbols(registry)
    if not excluded:
        raise CiGateError("GATE_REGISTRY_EMPTY")
    missing = [symbol for symbol in RESEARCH_SYMBOLS if symbol not in excluded]
    if missing:
        raise CiGateError(
            "GATE_RESEARCH_SYMBOLS_NOT_EXCLUDED", ",".join(missing)
        )


def evaluate(repository_root: str | Path) -> dict:
    """Evaluate the gate against a repository checkout. Fail-closed.

    Raises :class:`CiGateError` on any violated invariant; returns the PASS
    report otherwise.
    """
    root = Path(repository_root)
    assert_authority_frozen(_load_json(root / AUTHORITY_REL))
    assert_holdout_registry_active(_load_json(root / REGISTRY_REL))
    return {
        "schema_version": GATE_SCHEMA,
        "status": "PASS",
        "real_final_holdout_access_authorized": False,
        "phase7_authorized": False,
        "production_readiness_approved": False,
        "holdout_exclusions_enforced": True,
        "synthetic_only": True,
        "network": False,
        "provider_calls": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investment-tracker-gen2-ci-gate")
    parser.add_argument("--repository-root", default=".")
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.repository_root)
    except CiGateError as exc:
        print(
            json.dumps(
                {
                    "schema_version": GATE_SCHEMA,
                    "status": "FAIL",
                    "code": exc.code,
                    "detail": str(exc),
                    "synthetic_only": True,
                    "network": False,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
