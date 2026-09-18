from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from investment_tracker.quant.phase4.gate3.filesystem import contained_path, resolve_repository_root
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity, Gate3AuthorityError
from investment_tracker.quant.phase4.gate3.seal import GATE1_MANIFEST_IDENTITY, GATE2_MANIFEST_IDENTITY
from investment_tracker.quant.phase4.gate3_campaign.codec import canonical_bytes, decode
from investment_tracker.quant.phase4.gate3_campaign.result_methodology import ResultSchemaManifest
from investment_tracker.quant.phase4.gate3_campaign.result_schema import CandidateResult, SurvivorProjection
from investment_tracker.quant.phase4.gate3_campaign import validation as gate3_validation
from investment_tracker.quant.phase4.gate3_campaign.validation import oos_outcome
from investment_tracker.quant.phase4.gate3_runner.methodology import RunnerManifest
from investment_tracker.quant.phase4.gate3_runner.state import RunnerStateStore
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
)
from investment_tracker.quant.phase4.preregistration.policy import _eligible

from .models import AuditRow, Phase4Audit
from .selection import rejection_reasons


CAMPAIGN_RESULT_SET_CONTENT = "bbefc542547ddc5e541a2390a978cf45a4a25c65603e0d114a6cb7f1fb9f32a8"
CAMPAIGN_AGGREGATE_SHA256 = "cd84547dc82339746c1780ec5a78d9e5f91a9048a46f06ed96b5e745415b47d2"
RUNNER_MANIFEST_CONTENT = "ac13f1eef4639d5f4476b2a6d07df0434bf5c8d2c95d67330852db303d0aa5d4"
RESULT_SCHEMA_CONTENT = "70cabdd78bb5f473fbb94f969c21fd5add185ccc46f00fb217c2b415f404fa96"
CANDIDATE_POPULATION_SHA256 = "15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3"
BINDINGS_CONTENT = "b24e75010493d7ea0381294b6dbac682d554cbe5a6decfac63eeb1c514de0f7e"
FAMILIES_CONTENT = "d3a2744d5c642cf5fd5042df04630ec5fffc02709f0da25c4f326b5e57d9a55c"


def _identity(kind: str, content: str, path: str) -> ArtifactIdentity:
    return ArtifactIdentity(
        kind=kind,
        content_sha256=content,
        path=path,
        sha256=artifact_envelope_identity(
            content_sha256=content,
            kind=kind,
            path=path,
        ),
    )


CAMPAIGN_RESULT_SET_IDENTITY = _identity(
    "phase4_gate3_campaign_result_set",
    CAMPAIGN_RESULT_SET_CONTENT,
    f"results/phase4/gate3/campaign/result_set/sha256/{CAMPAIGN_RESULT_SET_CONTENT}/manifest.json",
)
RUNNER_MANIFEST_IDENTITY = _identity(
    "gate3_campaign_runner_manifest",
    RUNNER_MANIFEST_CONTENT,
    f"results/phase4/gate3/campaign_runner/runner_manifest/sha256/{RUNNER_MANIFEST_CONTENT}/manifest.json",
)
RESULT_SCHEMA_MANIFEST_IDENTITY = _identity(
    "gate3_result_schema_manifest",
    RESULT_SCHEMA_CONTENT,
    f"results/phase4/gate3/campaign_result_schema/gate3_result_schema_manifest/sha256/{RESULT_SCHEMA_CONTENT}/manifest.json",
)
BINDINGS_IDENTITY = _identity(
    "candidate_implementation_bindings",
    BINDINGS_CONTENT,
    f"results/phase4/gate2/candidate_implementation_bindings/sha256/{BINDINGS_CONTENT}/bindings.json",
)
FAMILIES_IDENTITY = _identity(
    "strategy_family_definitions",
    FAMILIES_CONTENT,
    f"results/phase4/gate1/strategy_family_definitions/sha256/{FAMILIES_CONTENT}/families.json",
)


def _read_bytes(root: Path, identity: ArtifactIdentity) -> bytes:
    try:
        repository = resolve_repository_root(
            root,
            code="PHASE4_FINALIZATION_EVIDENCE_INVALID",
        )
        path = contained_path(
            repository,
            tuple(identity.path.split("/")),
            code="PHASE4_FINALIZATION_EVIDENCE_INVALID",
        )
    except Gate3AuthorityError as exc:
        raise ValueError("PHASE4_FINALIZATION_EVIDENCE_INVALID") from exc
    if path.is_symlink() or not path.is_file():
        raise ValueError("PHASE4_FINALIZATION_EVIDENCE_INVALID")
    payload = path.read_bytes()
    if sha256(payload).hexdigest() != identity.content_sha256:
        raise ValueError("PHASE4_FINALIZATION_EVIDENCE_INVALID")
    return payload


def _read_json(root: Path, identity: ArtifactIdentity) -> dict:
    payload = _read_bytes(root, identity)
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("PHASE4_FINALIZATION_EVIDENCE_INVALID") from exc
    if canonical_json_bytes(parsed) != payload:
        raise ValueError("PHASE4_FINALIZATION_EVIDENCE_INVALID")
    if not isinstance(parsed, dict):
        raise ValueError("PHASE4_FINALIZATION_EVIDENCE_INVALID")
    return parsed


def _read_candidate(root: Path, identity: ArtifactIdentity) -> CandidateResult:
    expected_path = (
        "results/phase4/gate3/campaign/candidate_result/sha256/"
        f"{identity.content_sha256}/record.json"
    )
    expected = _identity(
        "phase4_gate3_candidate_result",
        identity.content_sha256,
        expected_path,
    )
    if identity != expected:
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
    payload = _read_bytes(root, identity)
    try:
        result = decode(CandidateResult, payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("PHASE4_FINALIZATION_EVIDENCE_INVALID") from exc
    if canonical_bytes(result) != payload:
        raise ValueError("PHASE4_FINALIZATION_EVIDENCE_INVALID")
    return result


def _projection_authority(bindings: list[dict], families: list[dict]):
    return SimpleNamespace(
        dependencies=SimpleNamespace(
            bindings=tuple(
                SimpleNamespace(
                    candidate_id=item["candidate_id"],
                    family_id=item["family_id"],
                )
                for item in bindings
            ),
            gate2=SimpleNamespace(
                family_definitions=tuple(
                    SimpleNamespace(
                        family_id=item["family_id"],
                        component_count=item["component_count"],
                    )
                    for item in families
                )
            ),
        )
    )


def _validate_provenance(
    result: CandidateResult,
    *,
    position: int,
    binding: dict,
    result_manifest: ResultSchemaManifest,
) -> None:
    provenance = result.provenance
    checks = (
        provenance.population_position == position,
        provenance.candidate_id == binding["candidate_id"],
        provenance.trial_id == binding["trial_id"],
        provenance.family_id == binding["family_id"],
        provenance.hypothesis_id == binding["hypothesis_id"],
        provenance.family_definition_sha256 == binding["family_definition_sha256"],
        provenance.rule_set_sha256 == binding["rule_set_sha256"],
        provenance.parameter_tuple_sha256 == binding["parameter_tuple_sha256"],
        provenance.candidate_population_sha256 == CANDIDATE_POPULATION_SHA256,
        provenance.gate1_manifest == GATE1_MANIFEST_IDENTITY,
        provenance.gate2_manifest == GATE2_MANIFEST_IDENTITY,
        provenance.gate3_manifest == result_manifest.gate3_authority_manifest,
        provenance.execution_methodology == result_manifest.execution_methodology,
        provenance.engine_implementation_sha256 == result_manifest.engine_implementation_sha256,
        provenance.scored_market_panel_sha256 == result_manifest.scored_market_panel_sha256,
        provenance.source_revision == result_manifest.source_revision,
        provenance.train_identity == result_manifest.train_identity,
        provenance.validation_identity == result_manifest.validation_identity,
    )
    if not all(checks):
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")


def _validate_stop_witness(
    result: CandidateResult,
    by_identity: dict[str, CandidateResult],
) -> None:
    if result.stop_witness is None or result.reason != "PERSISTENT_OOS_FAILURE":
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
    witness = result.stop_witness
    try:
        resolved = tuple(by_identity[item.content_sha256] for item in witness.prior_results)
    except KeyError as exc:
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH") from exc
    trigger = witness.trigger_position
    positions = tuple(row.provenance.population_position for row in resolved)
    if (
        len(resolved) != 50
        or positions != tuple(range(trigger - 49, trigger + 1))
        or trigger >= result.provenance.population_position
        or any(row.provenance.family_id != result.provenance.family_id for row in resolved)
        or any(row.status not in ("EXECUTED", "UNKNOWN", "ABSTAIN") for row in resolved)
    ):
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
    for row in resolved:
        outcome = oos_outcome(row)
        if outcome.benchmark_excess_return is not None and outcome.benchmark_excess_return > 0:
            raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")


def audit_campaign(
    repository_root: Path,
    campaign_result_set_identity: ArtifactIdentity,
) -> Phase4Audit:
    root = resolve_repository_root(
        repository_root,
        code="PHASE4_FINALIZATION_EVIDENCE_INVALID",
    )
    if campaign_result_set_identity != CAMPAIGN_RESULT_SET_IDENTITY:
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")

    state = RunnerStateStore(root)
    result_set, observed_identity = state.read_result_set(campaign_result_set_identity)
    if (
        observed_identity != CAMPAIGN_RESULT_SET_IDENTITY
        or result_set.aggregate_sha256 != CAMPAIGN_AGGREGATE_SHA256
        or result_set.expected_positions != 180
        or result_set.runner_manifest != RUNNER_MANIFEST_IDENTITY
    ):
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")

    runner_payload = _read_bytes(root, RUNNER_MANIFEST_IDENTITY)
    result_schema_payload = _read_bytes(root, RESULT_SCHEMA_MANIFEST_IDENTITY)
    if canonical_json_bytes(json.loads(runner_payload)) != runner_payload:
        raise ValueError("PHASE4_FINALIZATION_EVIDENCE_INVALID")
    if canonical_json_bytes(json.loads(result_schema_payload)) != result_schema_payload:
        raise ValueError("PHASE4_FINALIZATION_EVIDENCE_INVALID")
    runner_manifest = RunnerManifest.model_validate_json(runner_payload)
    result_manifest = ResultSchemaManifest.model_validate_json(result_schema_payload)
    if (
        runner_manifest.status != "GATE3_CAMPAIGN_RUNNER_READY_TO_EXECUTE"
        or runner_manifest.result_schema_manifest != RESULT_SCHEMA_MANIFEST_IDENTITY
        or runner_manifest.candidate_population_sha256 != CANDIDATE_POPULATION_SHA256
        or runner_manifest.survivor_policy != result_manifest.survivor_policy
        or runner_manifest.durability_policy != result_manifest.durability_policy
    ):
        raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")

    bindings_doc = _read_json(root, BINDINGS_IDENTITY)
    families_doc = _read_json(root, FAMILIES_IDENTITY)
    bindings = bindings_doc.get("bindings")
    families = families_doc.get("families")
    if (
        bindings_doc.get("candidate_count") != 180
        or not isinstance(bindings, list)
        or len(bindings) != 180
        or tuple(item.get("budget_position") for item in bindings) != tuple(range(1, 181))
        or not isinstance(families, list)
        or len(families) != 4
    ):
        raise ValueError("PHASE4_FINALIZATION_ACCOUNTING_INVALID")
    projection_authority = _projection_authority(bindings, families)

    decoded: list[CandidateResult] = []
    seen_candidates: set[str] = set()
    for position, artifact in enumerate(result_set.result_artifacts, start=1):
        receipt_found = state.read_receipt(position)
        if receipt_found is None:
            raise ValueError("PHASE4_FINALIZATION_ACCOUNTING_INVALID")
        receipt, _ = receipt_found
        result = _read_candidate(root, artifact)
        binding = bindings[position - 1]
        _validate_provenance(
            result,
            position=position,
            binding=binding,
            result_manifest=result_manifest,
        )
        if (
            receipt.population_position != position
            or receipt.candidate_id != result.provenance.candidate_id
            or receipt.trial_id != result.provenance.trial_id
            or receipt.result_artifact != artifact
            or receipt.result_status != result.status
            or receipt.runner_manifest != RUNNER_MANIFEST_IDENTITY
        ):
            raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
        attempt_found = state.read_attempt(position)
        if result.status == "SKIPPED_FAMILY_STOP":
            if attempt_found is not None:
                raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
        else:
            if attempt_found is None:
                raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
            attempt, _ = attempt_found
            if (
                attempt.population_position != position
                or attempt.candidate_id != result.provenance.candidate_id
                or attempt.trial_id != result.provenance.trial_id
                or attempt.runner_manifest != RUNNER_MANIFEST_IDENTITY
            ):
                raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
        if result.status == "CAMPAIGN_EXECUTION_FAILED":
            raise ValueError("PHASE4_FINALIZATION_CAMPAIGN_FAILED")
        if result.provenance.candidate_id in seen_candidates:
            raise ValueError("PHASE4_FINALIZATION_ACCOUNTING_INVALID")
        seen_candidates.add(result.provenance.candidate_id)
        decoded.append(result)

    if len(decoded) != 180 or len(seen_candidates) != 180:
        raise ValueError("PHASE4_FINALIZATION_ACCOUNTING_INVALID")

    by_identity = {
        artifact.content_sha256: result
        for artifact, result in zip(result_set.result_artifacts, decoded, strict=True)
    }
    rows: list[AuditRow] = []
    for position, (artifact, result) in enumerate(
        zip(result_set.result_artifacts, decoded, strict=True),
        start=1,
    ):
        if result.status == "SKIPPED_FAMILY_STOP":
            _validate_stop_witness(result, by_identity)
            projection_status = "NOT_APPLICABLE"
            eligibility_status = "NOT_APPLICABLE"
            reasons = ("PERSISTENT_OOS_FAILURE",)
            evidence = None
        elif result.status in ("UNKNOWN", "ABSTAIN"):
            projection_status = "UNKNOWN"
            eligibility_status = "UNKNOWN"
            reasons = ("PRIMARY_EVIDENCE_UNAVAILABLE", result.reason)
            evidence = None
        else:
            try:
                projection = gate3_validation.survivor_projection(
                    result,
                    projection_authority,
                )
            except (KeyError, StopIteration) as exc:
                raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH") from exc
            if result.stored_projection is not None and canonical_bytes(result.stored_projection) != canonical_bytes(projection):
                raise ValueError("PHASE4_FINALIZATION_AUTHORITY_MISMATCH")
            if projection.status != "AVAILABLE" or projection.evidence is None:
                projection_status = "UNKNOWN"
                eligibility_status = "UNKNOWN"
                reasons = projection.reasons or ("PRIMARY_EVIDENCE_UNAVAILABLE",)
                evidence = None
            else:
                projection_status = "AVAILABLE"
                evidence = projection.evidence
                reasons = rejection_reasons(evidence)
                eligibility_status = "ELIGIBLE" if _eligible(evidence) else "REJECTED"
        rows.append(
            AuditRow(
                population_position=position,
                candidate_id=result.provenance.candidate_id,
                trial_id=result.provenance.trial_id,
                family_id=result.provenance.family_id,
                hypothesis_id=result.provenance.hypothesis_id,
                rule_set_sha256=result.provenance.rule_set_sha256,
                parameter_tuple_sha256=result.provenance.parameter_tuple_sha256,
                family_definition_sha256=result.provenance.family_definition_sha256,
                result_artifact=artifact,
                result_status=result.status,
                projection_status=projection_status,
                eligibility_status=eligibility_status,
                rejection_reasons=tuple(reasons),
                survivor_evidence=evidence,
            )
        )

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.result_status] = counts.get(row.result_status, 0) + 1
    eligible = tuple(row.candidate_id for row in rows if row.eligibility_status == "ELIGIBLE")
    return Phase4Audit(
        campaign_result_set=CAMPAIGN_RESULT_SET_IDENTITY,
        campaign_aggregate_sha256=CAMPAIGN_AGGREGATE_SHA256,
        status_counts=dict(sorted(counts.items())),
        rows=tuple(rows),
        eligible_candidate_ids=eligible,
        survivor_policy=runner_manifest.survivor_policy,
        durability_policy=runner_manifest.durability_policy,
        candidate_population_sha256=CANDIDATE_POPULATION_SHA256,
        runner_manifest=RUNNER_MANIFEST_IDENTITY,
        result_schema_manifest=RESULT_SCHEMA_MANIFEST_IDENTITY,
    )
