from __future__ import annotations

from investment_tracker.quant.phase4.preregistration.canonical import (
    canonical_sha256,
)

from .models import EvidenceKind, Gate2EvaluationContext


def evaluation_context_identity(context: Gate2EvaluationContext) -> str:
    return canonical_sha256(
        {
            "schema_version": "PHASE4-EVALUATION-CONTEXT-v1",
            **context.model_dump(),
        }
    )


def evaluation_case_identity(
    *,
    candidate_id: str,
    family_definition_sha256: str,
    rule_set_sha256: str,
    parameter_tuple_sha256: str,
    engine_implementation_sha256: str,
    evaluation_context_sha256: str,
    evidence_kind: EvidenceKind,
    case_id: str,
) -> str:
    return canonical_sha256(
        {
            "schema_version": "PHASE4-EVALUATION-CASE-v1",
            "candidate_id": candidate_id,
            "family_definition_sha256": family_definition_sha256,
            "rule_set_sha256": rule_set_sha256,
            "parameter_tuple_sha256": parameter_tuple_sha256,
            "engine_implementation_sha256": engine_implementation_sha256,
            "evaluation_context_sha256": evaluation_context_sha256,
            "evidence_kind": evidence_kind,
            "case_id": case_id,
        }
    )


def case_executable(
    evidence_kind: EvidenceKind,
    *,
    fold_authority_status: str,
    regime_authority_status: str,
) -> bool:
    if evidence_kind == "fold" and fold_authority_status == "FOLD_AUTHORITY_MISSING":
        return False
    if evidence_kind == "regime" and regime_authority_status == "REGIME_AUTHORITY_MISSING":
        return False
    return True
