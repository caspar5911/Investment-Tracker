from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_tracker.quant.experiments import (
    ExperimentRecord,
    ResearchCandidateManifest,
)
from investment_tracker.quant.readiness.constants import PHASE2_CAMPAIGN_ID
from investment_tracker.quant.readiness.hashing import canonical_sha256, trial_identity
from investment_tracker.quant.readiness.models import ReadinessArtifactIdentity
from investment_tracker.quant.readiness.statistics import (
    Phase4BudgetError,
    Phase4BudgetState,
    SearchAwareInputError,
    build_search_aware_inputs,
    unimplemented_search_statistic,
)
from investment_tracker.quant.readiness.trials import (
    ExperimentEvidence,
    TrialAuthorityError,
    build_authority_from_records,
    build_trial_authority,
    classify_representation,
)


PRELIMINARY_REVISION = "d4b2dfc3bee03ad81e389cc2e21876f38fbf325f"
FINAL_REVISION = "c33fb0757f0ea8147749130fed90d278aed4fafe"
CORRECTED_ENGINE = "QUANT-ENGINE-v1+SEARCH-POLICY-v2"


def artifact_identity_for(label: str, path_label: str) -> ReadinessArtifactIdentity:
    content_sha256 = sha256(label.encode("utf-8")).hexdigest()
    path = f"results/experiments/{path_label}.json"
    envelope = {
        "content_sha256": content_sha256,
        "kind": "phase2_experiment",
        "path": path,
    }
    return ReadinessArtifactIdentity(
        **envelope,
        sha256=canonical_sha256(envelope),
    )


def experiment_record(
    candidate_id: str,
    representation: str,
    *,
    recorded_offset: int = 0,
) -> ExperimentRecord:
    if representation == "original":
        engine = "QUANT-ENGINE-v1"
        revision = "1" * 40
        validation_metrics = {"sharpe": 0.5}
    elif representation == "preliminary":
        engine = CORRECTED_ENGINE
        revision = PRELIMINARY_REVISION
        validation_metrics = {"sharpe": 0.75}
    elif representation == "final":
        engine = CORRECTED_ENGINE
        revision = FINAL_REVISION
        validation_metrics = {"sharpe": 1.25, "loss_rate": 0.4}
    elif representation == "out_of_scope":
        engine = CORRECTED_ENGINE
        revision = "2" * 40
        validation_metrics = {"sharpe": 0.25}
    else:
        raise AssertionError(f"unknown fixture representation: {representation}")

    recorded_at = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(
        seconds=recorded_offset
    )
    manifest = ResearchCandidateManifest.create(
        candidate_id=candidate_id,
        strategy_family="fixture",
        strategy_code_hash="a" * 64,
        strategy_parameters={"window": 20},
        universe_config_hash="b" * 64,
        data_manifest_hashes={"SPY": "c" * 64},
        split_definition_hash="d" * 64,
        engine_version=engine,
        fee_model={"commission_bps": 1.0},
        slippage_model={"slippage_bps": 1.0},
        execution_convention="COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN",
        dependency_lock_hash="e" * 64,
        git_commit=revision,
        created_at=recorded_at,
    )
    return ExperimentRecord(
        experiment_id=f"{candidate_id}-{representation}-{recorded_offset}",
        status="RESEARCH_ONLY",
        candidate_manifest=manifest,
        symbols=("SPY",),
        train_period=(date(2010, 1, 1), date(2018, 12, 31)),
        validation_period=(date(2019, 1, 1), date(2022, 12, 31)),
        metrics={"sharpe": 0.5},
        validation_metrics=validation_metrics,
        score=50.0,
        accepted=True,
        reason="fixture",
        stop_reason="EXHAUSTED",
        recorded_at=recorded_at,
    )


def evidence(
    candidate_id: str,
    representation: str,
    *,
    ordinal: int = 0,
    renamed: bool = False,
) -> ExperimentEvidence:
    record = experiment_record(candidate_id, representation, recorded_offset=ordinal)
    prefix = "renamed" if renamed else "fixture"
    return ExperimentEvidence(
        record=record,
        artifact=artifact_identity_for(
            f"{prefix}:{candidate_id}:{representation}:{ordinal}",
            f"{prefix}-{candidate_id}-{representation}-{ordinal}",
        ),
    )


@pytest.fixture(scope="module")
def experiment_fixtures() -> tuple[ExperimentEvidence, ...]:
    representations: list[ExperimentEvidence] = []
    for index in range(136):
        candidate_id = f"candidate-{index:03d}"
        representations.append(evidence(candidate_id, "preliminary"))
        representations.append(evidence(candidate_id, "final"))
        if index < 4:
            representations.append(evidence(candidate_id, "original"))
    return tuple(representations)


def authoritative_records(
    representations: tuple[ExperimentEvidence, ...],
) -> dict[str, ExperimentRecord]:
    return {
        trial_identity(PHASE2_CAMPAIGN_ID, item.record.candidate_manifest.candidate_id): item.record
        for item in representations
        if item.record.candidate_manifest.git_commit == FINAL_REVISION
    }


def test_phase2_preserved_evidence_yields_exactly_136_authoritative_trials() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    authority = build_trial_authority(
        repository_root,
        repository_root / "results" / "experiments",
    )
    assert authority.historical_phase2_trial_count == 136
    assert authority.total_representation_count == 276
    assert len(authority.trials) == 136
    assert len({trial.trial_id for trial in authority.trials}) == 136
    assert all(
        trial.authoritative_artifact.sha256 != trial.trial_id
        for trial in authority.trials
    )


@pytest.mark.parametrize(
    ("representation", "expected"),
    [
        ("original", "ORIGINAL"),
        ("preliminary", "PRELIMINARY_CORRECTED"),
        ("final", "FINAL_AUTHORITATIVE"),
        ("out_of_scope", "OUT_OF_SCOPE"),
    ],
)
def test_representation_classification_uses_only_frozen_structural_predicates(
    representation: str,
    expected: str,
) -> None:
    record = experiment_record("candidate-a", representation, recorded_offset=99)
    assert classify_representation(record) == expected


def test_admission_is_independent_of_path_timestamp_and_input_order(
    experiment_fixtures: tuple[ExperimentEvidence, ...],
) -> None:
    forward = build_authority_from_records(experiment_fixtures)
    reverse = build_authority_from_records(tuple(reversed(experiment_fixtures)))
    assert forward == reverse

    renamed = tuple(
        evidence(
            item.record.candidate_manifest.candidate_id,
            (
                "original"
                if item.record.candidate_manifest.engine_version == "QUANT-ENGINE-v1"
                else "preliminary"
                if item.record.candidate_manifest.git_commit == PRELIMINARY_REVISION
                else "final"
            ),
            ordinal=10_000 + index,
            renamed=True,
        )
        for index, item in enumerate(experiment_fixtures)
    )
    assert tuple(item.trial_id for item in forward.trials) == tuple(
        item.trial_id for item in build_authority_from_records(renamed).trials
    )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unexpected", "ambiguous"])
def test_invalid_authoritative_populations_fail_closed(
    experiment_fixtures: tuple[ExperimentEvidence, ...],
    mutation: str,
) -> None:
    mutated = list(experiment_fixtures)
    if mutation == "missing":
        mutated = [
            item
            for item in mutated
            if not (
                item.record.candidate_manifest.candidate_id == "candidate-000"
                and item.record.candidate_manifest.git_commit == FINAL_REVISION
            )
        ]
    elif mutation == "duplicate":
        mutated.append(evidence("candidate-000", "final", ordinal=1))
    elif mutation == "unexpected":
        mutated.extend(
            (
                evidence("candidate-136", "preliminary"),
                evidence("candidate-136", "final"),
            )
        )
    else:
        preliminary = next(
            item
            for item in mutated
            if item.record.candidate_manifest.candidate_id == "candidate-000"
            and item.record.candidate_manifest.git_commit == PRELIMINARY_REVISION
        )
        final_index = next(
            index
            for index, item in enumerate(mutated)
            if item.record.candidate_manifest.candidate_id == "candidate-000"
            and item.record.candidate_manifest.git_commit == FINAL_REVISION
        )
        mutated[final_index] = ExperimentEvidence(
            record=mutated[final_index].record,
            artifact=preliminary.artifact,
        )

    with pytest.raises(TrialAuthorityError):
        build_authority_from_records(tuple(mutated))


def test_duplicate_representations_do_not_inflate_search_inputs(
    experiment_fixtures: tuple[ExperimentEvidence, ...],
) -> None:
    base_authority = build_authority_from_records(experiment_fixtures)
    records = authoritative_records(experiment_fixtures)
    base = build_search_aware_inputs(base_authority, records)

    duplicated_evidence = (
        *experiment_fixtures,
        evidence("candidate-000", "preliminary", ordinal=2),
    )
    duplicated_authority = build_authority_from_records(duplicated_evidence)
    duplicated = build_search_aware_inputs(duplicated_authority, records)

    assert duplicated.historical_trial_count == base.historical_trial_count == 136
    assert duplicated.multiple_testing_count == base.multiple_testing_count == 136
    assert duplicated.ordered_sharpe_trial_ids == base.ordered_sharpe_trial_ids
    assert duplicated.ordered_pbo_trial_ids == base.ordered_pbo_trial_ids


def test_search_inputs_require_exact_trial_keyed_authoritative_records(
    experiment_fixtures: tuple[ExperimentEvidence, ...],
) -> None:
    authority = build_authority_from_records(experiment_fixtures)
    records = authoritative_records(experiment_fixtures)
    records.pop(next(iter(records)))
    with pytest.raises(SearchAwareInputError, match="trial IDs"):
        build_search_aware_inputs(authority, records)


def test_phase4_budget_starts_at_zero_and_first_trial_is_position_one() -> None:
    state = Phase4BudgetState.initial()
    assert state.historical_phase2_trial_count == 136
    assert state.phase4_new_trials_consumed == 0
    assert state.phase4_new_trials_remaining == 3000
    assert state.phase4_historical_trials_consume_budget is False

    first = state.consume("phase4-candidate-0001")
    assert first.phase4_new_trials_consumed == 1
    assert first.phase4_new_trials_remaining == 2999
    assert first.last_consumed_budget_position == 1


def test_phase4_budget_rejects_historical_duplicate_and_combined_counts() -> None:
    state = Phase4BudgetState.initial()
    with pytest.raises(Phase4BudgetError, match="Phase 4"):
        state.consume("risk_managed_trend-ee8a71fb71e3d80f")
    first = state.consume("phase4-candidate-0001")
    with pytest.raises(Phase4BudgetError, match="already consumed"):
        first.consume("phase4-candidate-0001")
    with pytest.raises(ValidationError):
        Phase4BudgetState(
            phase4_new_trials_consumed=136,
            phase4_new_trials_remaining=3000,
            consumed_candidate_ids=tuple(f"phase4-{index}" for index in range(136)),
            last_consumed_budget_position=136,
        )


def test_unimplemented_search_statistics_never_return_a_number() -> None:
    for name in ("DSR", "PBO"):
        result = unimplemented_search_statistic(name, "ESTIMATOR_NOT_IMPLEMENTED")
        assert result.status == "NOT_IMPLEMENTED"
        assert result.interpretation == "UNKNOWN"
        assert result.value is None
