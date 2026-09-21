"""Tests for the Generation-2 synthetic-only CI rehearsal gate (B4).

The gate is the dedicated CI stage that must stay green for the generation-2
implementation. It asserts, fail-closed, that the frozen governance authority
keeps every real-boundary flag exactly ``false`` and that the permanent
holdout-exclusion registry still covers the entire research universe. It uses
no provider and no network.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from investment_tracker.quant.generation2.ci_gate import (
    CiGateError,
    assert_authority_frozen,
    assert_holdout_registry_active,
    evaluate,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

AUTHORITY = {
    "real_final_holdout_access_authorized": False,
    "phase7_authorized": False,
    "production_readiness_approved": False,
}
RESEARCH = ["GLD", "IEF", "IWM", "QQQ", "SPY", "TLT", "VNQ", "XLP"]
REGISTRY = {
    "permanent_exclusions": [
        {"symbols": RESEARCH, "reason": "PHASE4_PHASE5_RESEARCH_UNIVERSE"},
        {"symbols": ["HACK", "SOXX", "NLR", "URNM", "GEV"], "reason": "GEN1"},
    ]
}


def test_gate_passes_on_repository_governance():
    report = evaluate(REPO_ROOT)
    assert report["status"] == "PASS"
    assert report["real_final_holdout_access_authorized"] is False
    assert report["phase7_authorized"] is False
    assert report["holdout_exclusions_enforced"] is True
    assert report["synthetic_only"] is True
    assert report["network"] is False


def test_gate_main_returns_zero_on_repository(tmp_path, capsys):
    rc = main(["--repository-root", str(REPO_ROOT)])
    assert rc == 0
    assert "PASS" in capsys.readouterr().out


def test_authority_must_be_frozen_false():
    assert_authority_frozen(AUTHORITY)
    for key in AUTHORITY:
        mutated = dict(AUTHORITY)
        mutated[key] = True
        with _raises_gate("GATE_AUTHORITY_NOT_FROZEN"):
            assert_authority_frozen(mutated)


def test_authority_missing_key_rejected():
    for key in AUTHORITY:
        mutated = {k: v for k, v in AUTHORITY.items() if k != key}
        with _raises_gate("GATE_AUTHORITY_KEY_MISSING"):
            assert_authority_frozen(mutated)


def test_registry_must_cover_research_universe():
    assert_holdout_registry_active(REGISTRY)
    # Drop one research symbol from coverage.
    trimmed = {
        "permanent_exclusions": [
            {"symbols": RESEARCH[:7], "reason": "PHASE4_PHASE5_RESEARCH_UNIVERSE"}
        ]
    }
    with _raises_gate("GATE_RESEARCH_SYMBOLS_NOT_EXCLUDED"):
        assert_holdout_registry_active(trimmed)


def test_registry_empty_rejected():
    with _raises_gate("GATE_REGISTRY_EMPTY"):
        assert_holdout_registry_active({"permanent_exclusions": []})


def test_main_fails_when_authority_flipped(tmp_path):
    data = tmp_path / "data" / "governance"
    data.mkdir(parents=True)
    (data / "generation2-governance-authority.json").write_text(
        '{"real_final_holdout_access_authorized": true, "phase7_authorized": false, "production_readiness_approved": false}',
        encoding="utf-8",
    )
    shutil.copy(
        REPO_ROOT / "data" / "governance" / "holdout-exclusion-registry.json",
        data / "holdout-exclusion-registry.json",
    )
    rc = main(["--repository-root", str(tmp_path)])
    assert rc == 1


def _raises_gate(code: str):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        try:
            yield
        except CiGateError as exc:
            assert exc.code == code, f"expected {code}, got {exc.code}"
        else:
            raise AssertionError(f"expected CiGateError {code} to be raised")

    return _ctx()
