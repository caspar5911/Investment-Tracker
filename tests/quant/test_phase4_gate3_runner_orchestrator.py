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

    summary = run_campaign(
        context,
        runner_manifest=manifest,
        evaluator=evaluator,
        state_store=RunnerStateStore(tmp_path),
        result_store=ResultArtifactStore(tmp_path),
    )
    family_counts = Counter(binding.family_id for binding in context.campaign.bindings)
    expected_skips = sum(max(0, count - 50) for count in family_counts.values())
    assert expected_skips == 8
    assert summary.accounted_positions == 180
    assert summary.unknown == 180 - expected_skips
    assert summary.skipped_family_stop == expected_skips
    assert len(calls) == 180 - expected_skips

    def must_not_run(_ctx, _position):
        raise AssertionError("completed receipts must prevent duplicate evaluation")

    second = run_campaign(
        context,
        runner_manifest=manifest,
        evaluator=must_not_run,
        state_store=RunnerStateStore(tmp_path),
        result_store=ResultArtifactStore(tmp_path),
    )
    assert second.result_set == summary.result_set


def test_system_evaluation_failure_is_published_and_fails_closed(
    context, tmp_path, monkeypatch
):
    manifest = allow_synthetic_runner(monkeypatch)

    def broken(_ctx, _position):
        raise RuntimeError("synthetic failure")

    with pytest.raises(CampaignExecutionError, match="CAMPAIGN_EXECUTION_FAILED"):
        run_campaign(
            context,
            runner_manifest=manifest,
            evaluator=broken,
            state_store=RunnerStateStore(tmp_path),
            result_store=ResultArtifactStore(tmp_path),
        )
    receipt = RunnerStateStore(tmp_path).read_receipt(1)[0]
    assert receipt.result_status == "CAMPAIGN_EXECUTION_FAILED"


def test_runner_source_has_no_selection_provider_holdout_or_trading_surface():
    import inspect
    import investment_tracker.quant.phase4.gate3_runner.orchestrator as module

    source = inspect.getsource(module)
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
    )
    for token in forbidden:
        assert token not in source


def test_direct_runner_api_requires_sealed_explicit_manifest(context, tmp_path):
    calls: list[int] = []

    def evaluator(ctx, position):
        calls.append(position)
        return unavailable(ctx, position)

    with pytest.raises(ValueError, match="RUNNER_MANIFEST_MISSING"):
        run_campaign(
            context,
            runner_manifest=manifest_identity(),
            evaluator=evaluator,
            state_store=RunnerStateStore(tmp_path),
            result_store=ResultArtifactStore(tmp_path),
        )
    assert calls == []
