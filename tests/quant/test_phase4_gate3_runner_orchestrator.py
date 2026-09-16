from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity
from investment_tracker.quant.phase4.gate3_campaign.result_artifacts import ResultArtifactStore
from investment_tracker.quant.phase4.gate3_campaign.result_schema import CandidateResult
from investment_tracker.quant.phase4.gate3_campaign.validation import make_provenance
from investment_tracker.quant.phase4.gate3_runner.dependencies import load_runner_dependencies
import investment_tracker.quant.phase4.gate3_runner.orchestrator as orchestrator_module
from investment_tracker.quant.phase4.gate3_runner.orchestrator import (
    CampaignExecutionError,
    _run_campaign_verified,
    run_campaign,
)
from investment_tracker.quant.phase4.gate3_runner.state import RunnerStateStore
from investment_tracker.quant.phase4.preregistration.canonical import artifact_envelope_identity


ROOT = Path(__file__).resolve().parents[2]


def manifest_identity() -> ArtifactIdentity:
    content = "5" * 64
    path = (
        "results/phase4/gate3/campaign_runner/runner_manifest/sha256/"
        f"{content}/manifest.json"
    )
    return ArtifactIdentity(
        kind="gate3_campaign_runner_manifest",
        content_sha256=content,
        path=path,
        sha256=artifact_envelope_identity(
            content_sha256=content,
            kind="gate3_campaign_runner_manifest",
            path=path,
        ),
    )


@pytest.fixture(scope="module")
def context():
    return load_runner_dependencies(ROOT)


def allow_synthetic_runner(monkeypatch) -> ArtifactIdentity:
    manifest = manifest_identity()
    monkeypatch.setattr(
        orchestrator_module,
        "preflight_runner",
        lambda _root, digest: (
            SimpleNamespace(manifest=manifest)
            if digest == manifest.content_sha256
            else (_ for _ in ()).throw(ValueError("RUNNER_MANIFEST_MISSING"))
        ),
    )
    return manifest


def unavailable(context, position: int) -> CandidateResult:
    return CandidateResult(
        provenance=make_provenance(context.result_authority, position),
        status="UNKNOWN",
        reason="SYNTHETIC_NO_PRIMARY_OBSERVATION",
        evidence=None,
    )


def test_unavailable_oos_streak_stops_only_54_member_families_and_accounts_all_positions(
    context, tmp_path, monkeypatch
):
    manifest = allow_synthetic_runner(monkeypatch)
    calls: list[int] = []

    def evaluator(ctx, position):
        calls.append(position)
        return unavailable(ctx, position)

    state = RunnerStateStore(tmp_path)
    results = ResultArtifactStore(tmp_path)
    monkeypatch.setattr(orchestrator_module, "_evaluate_binding", evaluator)
    monkeypatch.setattr(orchestrator_module, "RunnerStateStore", lambda _root: state)
    monkeypatch.setattr(orchestrator_module, "ResultArtifactStore", lambda _root: results)
    summary = _run_campaign_verified(
        context,
        runner_manifest=manifest,
    )
    family_counts = Counter(binding.family_id for binding in context.campaign.bindings)
    expected_skips = sum(max(0, count - 50) for count in family_counts.values())
    assert expected_skips == 8
    assert summary.accounted_positions == 180
    assert summary.unknown == 180 - expected_skips
    assert summary.skipped_family_stop == expected_skips
    assert len(calls) == 180 - expected_skips
    assert 50 in calls and 51 not in calls and 54 not in calls
    assert 140 in calls and 141 not in calls and 144 not in calls

    def must_not_run(_ctx, _position):
        raise AssertionError("completed receipts must prevent duplicate evaluation")

    monkeypatch.setattr(orchestrator_module, "_evaluate_binding", must_not_run)
    second = _run_campaign_verified(
        context,
        runner_manifest=manifest,
    )
    assert second.result_set == summary.result_set


def test_system_evaluation_failure_is_published_and_fails_closed(
    context, tmp_path, monkeypatch
):
    manifest = allow_synthetic_runner(monkeypatch)

    def broken(_ctx, _position):
        raise RuntimeError("synthetic failure")

    state = RunnerStateStore(tmp_path)
    results = ResultArtifactStore(tmp_path)
    monkeypatch.setattr(orchestrator_module, "_evaluate_binding", broken)
    monkeypatch.setattr(orchestrator_module, "RunnerStateStore", lambda _root: state)
    monkeypatch.setattr(orchestrator_module, "ResultArtifactStore", lambda _root: results)
    with pytest.raises(CampaignExecutionError, match="CAMPAIGN_EXECUTION_FAILED"):
        _run_campaign_verified(
            context,
            runner_manifest=manifest,
        )
    receipt = state.read_receipt(1)[0]
    assert receipt.result_status == "CAMPAIGN_EXECUTION_FAILED"


def test_runner_source_has_no_selection_provider_holdout_or_trading_surface():
    package = (
        ROOT
        / "src"
        / "investment_tracker"
        / "quant"
        / "phase4"
        / "gate3_runner"
    )
    forbidden = (
        "select_survivor",
        "moomoo",
        "OpenTradeContext",
        "unlock_trade",
        "place_order",
        "FINAL_HOLDOUT",
        "HACK",
        "SOXX",
        "NLR",
        "URNM",
        "GEV",
        "requests.",
        "httpx",
        "urllib.request",
    )
    for path in package.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{token} leaked into {path.name}"


def test_direct_runner_api_requires_sealed_explicit_manifest():
    with pytest.raises(ValueError, match="RUNNER_MANIFEST_MISSING"):
        run_campaign(
            ROOT,
            manifest_identity().content_sha256,
        )


def test_candidate_evaluator_is_not_a_public_ungated_api():
    import investment_tracker.quant.phase4.gate3_runner.orchestrator as module

    assert not hasattr(module, "evaluate_binding")
    assert not hasattr(module, "generate_targets")


def test_public_run_campaign_has_only_repository_and_explicit_manifest_inputs():
    import inspect

    assert set(inspect.signature(run_campaign).parameters) == {
        "repository_root",
        "runner_manifest_content_sha256",
    }


def test_positive_benchmark_excess_resets_family_stop_streak(
    context, tmp_path, monkeypatch
):
    manifest = allow_synthetic_runner(monkeypatch)
    state = RunnerStateStore(tmp_path)
    results = ResultArtifactStore(tmp_path)
    calls: list[int] = []

    def evaluator(ctx, position):
        calls.append(position)
        return unavailable(ctx, position)

    def synthetic_oos(result):
        position = result.provenance.population_position
        return SimpleNamespace(
            benchmark_excess_return=(
                0.01 if position in {25, 115} else None
            )
        )

    monkeypatch.setattr(orchestrator_module, "_evaluate_binding", evaluator)
    monkeypatch.setattr(orchestrator_module, "oos_outcome", synthetic_oos)
    monkeypatch.setattr(orchestrator_module, "RunnerStateStore", lambda _root: state)
    monkeypatch.setattr(orchestrator_module, "ResultArtifactStore", lambda _root: results)

    summary = _run_campaign_verified(
        context,
        runner_manifest=manifest,
    )
    assert summary.accounted_positions == 180
    assert summary.skipped_family_stop == 0
    assert calls == list(range(1, 181))


def test_interrupted_attempt_resumes_same_position_without_double_consumption(
    context, tmp_path, monkeypatch
):
    manifest = allow_synthetic_runner(monkeypatch)
    state = RunnerStateStore(tmp_path)
    results = ResultArtifactStore(tmp_path)
    first_binding = context.campaign.bindings[0]
    state.write_attempt(
        orchestrator_module._attempt_record(
            first_binding,
            manifest,
        )
    )
    calls: list[int] = []

    def evaluator(ctx, position):
        calls.append(position)
        return unavailable(ctx, position)

    monkeypatch.setattr(orchestrator_module, "_evaluate_binding", evaluator)
    monkeypatch.setattr(orchestrator_module, "RunnerStateStore", lambda _root: state)
    monkeypatch.setattr(orchestrator_module, "ResultArtifactStore", lambda _root: results)

    summary = _run_campaign_verified(
        context,
        runner_manifest=manifest,
    )
    assert summary.accounted_positions == 180
    assert calls[0] == 1
    assert calls.count(1) == 1
