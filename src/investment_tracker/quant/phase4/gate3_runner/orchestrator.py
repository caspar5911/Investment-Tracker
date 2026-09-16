from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from investment_tracker.quant.phase4.engine.benchmarks import cash_benchmark, equal_weight_buy_and_hold
from investment_tracker.quant.phase4.engine.execution import replay_targets
from investment_tracker.quant.phase4.engine.strategies import generate_target
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity
from investment_tracker.quant.phase4.gate3_campaign.result_artifacts import ResultArtifactStore
from investment_tracker.quant.phase4.gate3_campaign.result_schema import (
    CandidateResult,
    NeighborObservation,
    StopWitness,
)
from investment_tracker.quant.phase4.gate3_campaign.validation import (
    derive_evidence,
    make_provenance,
    oos_outcome,
    validate_result,
)
from investment_tracker.quant.phase4.preregistration.canonical import canonical_sha256
from investment_tracker.quant.phase4.preregistration.policy import update_oos_failure_streak

from .dependencies import RunnerDependencies
from .models import AttemptRecord, CampaignResultSet, PositionReceipt
from .state import RunnerStateStore


FRICTION_CASES = (0, 3, 10, 25, 50)


class CampaignExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CampaignRunSummary:
    status: str
    accounted_positions: int
    executed: int
    unknown: int
    abstain: int
    skipped_family_stop: int
    result_set: ArtifactIdentity


def _validate_population(context: RunnerDependencies) -> None:
    bindings = context.campaign.bindings
    if (
        len(bindings) != 180
        or tuple(binding.budget_position for binding in bindings) != tuple(range(1, 181))
        or len({binding.candidate_id for binding in bindings}) != 180
        or len({binding.trial_id for binding in bindings}) != 180
    ):
        raise ValueError("RUNNER_POPULATION_INVALID")
    closed: set[str] = set()
    current: str | None = None
    for binding in bindings:
        if binding.family_id != current:
            if current is not None:
                closed.add(current)
            if binding.family_id in closed:
                raise ValueError("RUNNER_FAMILY_ORDER_INVALID")
            current = binding.family_id


def generate_targets(context: RunnerDependencies, binding) -> tuple[object | None, ...]:
    return tuple(
        generate_target(context.campaign.gate2, binding, context.market_input, offset)
        for offset in range(len(context.market_input.scored.sessions))
    )


def _primary_neighbor_replay(context: RunnerDependencies, binding):
    targets = generate_targets(context, binding)
    return replay_targets(context.campaign.scored_panel, targets, friction_bps=3)


def evaluate_binding(context: RunnerDependencies, position: int) -> CandidateResult:
    if isinstance(position, bool) or not isinstance(position, int) or not 1 <= position <= 180:
        raise ValueError("RUNNER_POSITION_INVALID")
    binding = context.campaign.bindings[position - 1]
    if binding.budget_position != position:
        raise ValueError("RUNNER_POSITION_BINDING_MISMATCH")
    targets = generate_targets(context, binding)
    replays = tuple(
        replay_targets(context.campaign.scored_panel, targets, friction_bps=bps)
        for bps in FRICTION_CASES
    )
    benchmark = equal_weight_buy_and_hold(context.campaign.scored_panel, friction_bps=3)
    cash = cash_benchmark(context.campaign.scored_panel)
    neighbors = tuple(
        NeighborObservation(
            binding=neighbor,
            status="AVAILABLE",
            reason="OK",
            replay=_primary_neighbor_replay(context, neighbor),
        )
        for neighbor in context.campaign.neighbors(binding)
    )
    evidence = derive_evidence(replays, benchmark, cash, neighbors, context.campaign)
    result = CandidateResult(
        provenance=make_provenance(context.result_authority, position),
        status="EXECUTED",
        reason="OK",
        evidence=evidence,
    )
    return validate_result(result, context.result_authority)


def _failure_reason(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    message = str(exc).strip()
    token = message.split(":", 1)[0].strip() if message else ""
    if token and all(ch.isupper() or ch.isdigit() or ch == "_" for ch in token):
        return token
    return f"UNEXPECTED_{type(exc).__name__.upper()}"


def _failure_result(context: RunnerDependencies, position: int, exc: Exception) -> CandidateResult:
    return CandidateResult(
        provenance=make_provenance(context.result_authority, position),
        status="CAMPAIGN_EXECUTION_FAILED",
        reason=_failure_reason(exc),
        evidence=None,
    )


def _attempt_record(binding, runner_manifest: ArtifactIdentity) -> AttemptRecord:
    return AttemptRecord(
        population_position=binding.budget_position,
        candidate_id=binding.candidate_id,
        trial_id=binding.trial_id,
        family_id=binding.family_id,
        runner_manifest=runner_manifest,
    )


def _receipt_record(binding, result_identity: ArtifactIdentity, result: CandidateResult) -> PositionReceipt:
    return PositionReceipt(
        population_position=binding.budget_position,
        candidate_id=binding.candidate_id,
        trial_id=binding.trial_id,
        result_artifact=result_identity,
        result_status=result.status,
    )


def _load_existing(
    state: RunnerStateStore,
    results: ResultArtifactStore,
    context: RunnerDependencies,
    binding,
    runner_manifest: ArtifactIdentity,
) -> tuple[CandidateResult, ArtifactIdentity] | None:
    found = state.read_receipt(binding.budget_position)
    if found is None:
        return None
    receipt, _receipt_identity = found
    if (
        receipt.candidate_id != binding.candidate_id
        or receipt.trial_id != binding.trial_id
        or receipt.population_position != binding.budget_position
    ):
        raise ValueError("RUNNER_RECEIPT_BINDING_MISMATCH")
    result = results.read_result(receipt.result_artifact, context.result_authority)
    if (
        result.provenance.population_position != binding.budget_position
        or result.provenance.candidate_id != binding.candidate_id
        or result.provenance.trial_id != binding.trial_id
        or result.status != receipt.result_status
    ):
        raise ValueError("RUNNER_RECEIPT_RESULT_MISMATCH")
    attempt = state.read_attempt(binding.budget_position)
    if result.status == "SKIPPED_FAMILY_STOP":
        if attempt is not None:
            raise ValueError("RUNNER_SKIPPED_ATTEMPT_INVALID")
    elif attempt is None:
        raise ValueError("RUNNER_ATTEMPT_MISSING")
    else:
        attempt_record, _ = attempt
        expected = _attempt_record(binding, runner_manifest)
        if attempt_record != expected:
            raise ValueError("RUNNER_ATTEMPT_BINDING_MISMATCH")
    return result, receipt.result_artifact


def _observe(
    result: CandidateResult,
    result_identity: ArtifactIdentity,
    window: list[ArtifactIdentity],
) -> bool:
    outcome = oos_outcome(result)
    current_streak = len(window)
    next_streak, should_stop = update_oos_failure_streak(current_streak, outcome)
    if outcome.benchmark_excess_return is not None and outcome.benchmark_excess_return > 0:
        window.clear()
    else:
        window.append(result_identity)
        if len(window) > 50:
            del window[:-50]
    if next_streak != len(window):
        raise ValueError("RUNNER_OOS_STREAK_MISMATCH")
    return should_stop


def run_campaign(
    context: RunnerDependencies,
    *,
    runner_manifest: ArtifactIdentity,
    evaluator: Callable[[RunnerDependencies, int], CandidateResult] = evaluate_binding,
    state_store: RunnerStateStore | None = None,
    result_store: ResultArtifactStore | None = None,
) -> CampaignRunSummary:
    _validate_population(context)
    state = state_store or RunnerStateStore(context.root)
    results = result_store or ResultArtifactStore(context.root)
    windows: dict[str, list[ArtifactIdentity]] = defaultdict(list)
    stops: dict[str, tuple[int, tuple[ArtifactIdentity, ...]]] = {}
    ordered_results: list[ArtifactIdentity] = []
    counts = defaultdict(int)

    for binding in context.campaign.bindings:
        position = binding.budget_position
        existing = _load_existing(state, results, context, binding, runner_manifest)
        if existing is not None:
            result, result_identity = existing
            ordered_results.append(result_identity)
            counts[result.status] += 1
            if result.status == "CAMPAIGN_EXECUTION_FAILED":
                raise CampaignExecutionError(
                    f"CAMPAIGN_EXECUTION_FAILED at position {position}: {result.reason}"
                )
            if result.status == "SKIPPED_FAMILY_STOP":
                stop = stops.get(binding.family_id)
                if stop is None:
                    raise ValueError("RUNNER_STOP_STATE_MISSING")
                trigger, witness = stop
                if (
                    result.stop_witness is None
                    or result.stop_witness.trigger_position != trigger
                    or result.stop_witness.prior_results != witness
                ):
                    raise ValueError("RUNNER_STOP_WITNESS_MISMATCH")
                continue
            if _observe(result, result_identity, windows[binding.family_id]):
                witness = tuple(windows[binding.family_id])
                if len(witness) != 50:
                    raise ValueError("RUNNER_STOP_WINDOW_INVALID")
                stops.setdefault(binding.family_id, (position, witness))
            continue

        stop = stops.get(binding.family_id)
        if stop is not None:
            trigger, witness = stop
            skipped = CandidateResult(
                provenance=make_provenance(context.result_authority, position),
                status="SKIPPED_FAMILY_STOP",
                reason="PERSISTENT_OOS_FAILURE",
                evidence=None,
                stop_witness=StopWitness(
                    trigger_position=trigger,
                    prior_results=witness,
                ),
            )
            result_identity = results.write_result(skipped, context.result_authority)
            state.write_receipt(_receipt_record(binding, result_identity, skipped))
            ordered_results.append(result_identity)
            counts[skipped.status] += 1
            continue

        expected_attempt = _attempt_record(binding, runner_manifest)
        prior_attempt = state.read_attempt(position)
        if prior_attempt is None:
            state.write_attempt(expected_attempt)
        elif prior_attempt[0] != expected_attempt:
            raise ValueError("RUNNER_ATTEMPT_MISMATCH")

        try:
            result = evaluator(context, position)
            if result.provenance.population_position != position:
                raise ValueError("RUNNER_RESULT_POSITION_MISMATCH")
            if result.status == "SKIPPED_FAMILY_STOP":
                raise ValueError("RUNNER_EVALUATOR_CANNOT_INVENT_SKIP")
            result_identity = results.write_result(result, context.result_authority)
        except Exception as exc:
            failure = _failure_result(context, position, exc)
            try:
                failure_identity = results.write_result(failure, context.result_authority)
                state.write_receipt(_receipt_record(binding, failure_identity, failure))
            except Exception as publication_error:
                raise CampaignExecutionError(
                    f"CAMPAIGN_EXECUTION_FAILED_UNPUBLISHED at position {position}"
                ) from publication_error
            raise CampaignExecutionError(
                f"CAMPAIGN_EXECUTION_FAILED at position {position}: {failure.reason}"
            ) from exc

        state.write_receipt(_receipt_record(binding, result_identity, result))
        ordered_results.append(result_identity)
        counts[result.status] += 1
        if result.status == "CAMPAIGN_EXECUTION_FAILED":
            raise CampaignExecutionError(
                f"CAMPAIGN_EXECUTION_FAILED at position {position}: {result.reason}"
            )
        if _observe(result, result_identity, windows[binding.family_id]):
            witness = tuple(windows[binding.family_id])
            if len(witness) != 50:
                raise ValueError("RUNNER_STOP_WINDOW_INVALID")
            stops[binding.family_id] = (position, witness)

    if len(ordered_results) != 180:
        raise ValueError("RUNNER_ACCOUNTABILITY_INCOMPLETE")
    aggregate = canonical_sha256(
        {
            "schema_version": "PHASE4-GATE3-CAMPAIGN-RESULT-SET-IDENTITY-v1",
            "runner_manifest": runner_manifest.model_dump(mode="json"),
            "results": [item.model_dump(mode="json") for item in ordered_results],
        }
    )
    result_set = CampaignResultSet(
        runner_manifest=runner_manifest,
        result_artifacts=tuple(ordered_results),
        aggregate_sha256=aggregate,
    )
    result_set_identity = state.write_result_set(result_set)
    return CampaignRunSummary(
        status="GATE3_CAMPAIGN_RESULTS_COMPLETE",
        accounted_positions=180,
        executed=counts["EXECUTED"],
        unknown=counts["UNKNOWN"],
        abstain=counts["ABSTAIN"],
        skipped_family_stop=counts["SKIPPED_FAMILY_STOP"],
        result_set=result_set_identity,
    )


__all__ = (
    "CampaignExecutionError",
    "CampaignRunSummary",
    "FRICTION_CASES",
    "evaluate_binding",
    "generate_targets",
    "run_campaign",
)
