"""Deterministic provider-free seal for the Phase 4 Gate 2 research engine.

The seal publishes the engine contract, the four family bindings, the 180
candidate bindings, the synthetic conformance record, and the report as
immutable content-addressed artifacts, then commits one
PHASE4-ENGINE-MANIFEST-v1 as the final fallible write.  Every failure is
mapped to a frozen machine-readable Gate 2 failure code; nothing is repaired,
substituted, or retried with altered inputs.
"""

from __future__ import annotations

import platform
import sys
from hashlib import sha256
from pathlib import Path
from typing import Callable

from .artifacts import (
    Gate2ArtifactError,
    Gate2ArtifactStore,
    MANIFEST_KIND,
    MARKDOWN_KIND,
)
from .authority import load_gate2_authority
from .conformance import (
    SyntheticConformanceRecord,
    run_synthetic_conformance,
)
from .models import (
    CandidateBindingSet,
    DirectDependencyIdentity,
    EngineContract,
    Gate2Authority,
    EngineRuntimeIdentity,
    FamilyBindingSet,
    FamilyImplementationBinding,
    FixedStrategyBinding,
    Gate2ArtifactIdentity,
    Gate2SealError,
    Gate2SealResult,
    Gate2SourceBundleDigest,
    Phase4EngineManifest,
)
from .source_identity import (
    GATE2_SOURCE_BUNDLES,
    SourceBundleIdentity,
    source_bundle_identity,
)

_NON_FINAL_KINDS = (
    "engine_contract",
    "family_implementation_bindings",
    "candidate_implementation_bindings",
    "synthetic_conformance",
    "phase4_engine_report",
)


def seal_gate2(
    repository_root: Path,
    *,
    fail_after_kind: str | None = None,
    write_observer: Callable[[str], None] | None = None,
) -> Gate2SealResult:
    """Seal the Gate 2 engine and return its exact written artifact set."""

    if fail_after_kind is not None and fail_after_kind not in _NON_FINAL_KINDS:
        raise Gate2SealError(
            "INPUT_BOUNDARY_VIOLATION",
            "INPUT_BOUNDARY_VIOLATION: fail_after_kind must name one of the "
            f"five non-final Gate 2 artifact kinds: {fail_after_kind!r}",
        )
    try:
        return _seal(
            Path(repository_root),
            fail_after_kind=fail_after_kind,
            write_observer=write_observer,
        )
    except Gate2SealError:
        raise
    except Gate2ArtifactError as exc:
        code = (
            "IMMUTABLE_ARTIFACT_COLLISION"
            if "collision" in str(exc)
            else "SEAL_PUBLICATION_FAILED"
        )
        raise Gate2SealError(code, f"{code}: {exc}") from exc
    except Exception as exc:
        raise Gate2SealError(
            "SEAL_PUBLICATION_FAILED", f"SEAL_PUBLICATION_FAILED: {exc}"
        ) from exc


def _seal(
    root: Path,
    *,
    fail_after_kind: str | None,
    write_observer: Callable[[str], None] | None,
) -> Gate2SealResult:
    authority = load_gate2_authority(root)
    for identity in authority.direct_dependencies:
        payload = _reread_dependency(root, identity)
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise Gate2SealError(
                "HISTORICAL_ARTIFACT_MUTATION",
                f"dependency changed between load and commit: {identity.kind}",
            )

    def observe(kind: str) -> None:
        if write_observer is not None:
            write_observer(kind)

    bundle_set: dict[str, SourceBundleIdentity] = {}
    digests: list[Gate2SourceBundleDigest] = []
    for name in sorted(GATE2_SOURCE_BUNDLES):
        identity = source_bundle_identity(
            root, authority.head_revision, GATE2_SOURCE_BUNDLES[name]
        )
        bundle_set[name] = identity
        digests.append(
            Gate2SourceBundleDigest(
                bundle_name=name,
                producing_revision=authority.head_revision,
                entry_count=len(identity.entries),
                bundle_sha256=identity.bundle_sha256,
            )
        )

    record = run_synthetic_conformance(authority, bundle_set)

    candidates = authority.grids.candidates
    if len(candidates) != 180:
        raise Gate2SealError(
            "FIXED_STRATEGY_INVARIANT_FAILURE",
            "FIXED_STRATEGY_INVARIANT_FAILURE: the sealed candidate "
            f"population holds {len(candidates)} candidates, not 180",
        )
    families = authority.grids.families
    if len(families) != 4:
        raise Gate2SealError(
            "FIXED_STRATEGY_INVARIANT_FAILURE",
            "FIXED_STRATEGY_INVARIANT_FAILURE: the sealed family population "
            f"holds {len(families)} families, not 4",
        )
    family_implementation: dict[str, str] = {
        family.family_id: bundle_set[
            f"family:{family.family_semantic_name}"
        ].bundle_sha256
        for family in families
    }
    candidate_bindings = tuple(
        FixedStrategyBinding.from_authority(
            authority,
            candidate.candidate_id,
            family_implementation[candidate.family_id],
        )
        for candidate in candidates
    )
    family_bindings = tuple(
        FamilyImplementationBinding.from_family(
            family,
            family_implementation[family.family_id],
        )
        for family in families
    )

    store = Gate2ArtifactStore(root, root / "results")
    gate2_root = root / "results" / "phase4" / "gate2"

    def gate2_files() -> frozenset[Path]:
        if not gate2_root.exists():
            return frozenset()
        return frozenset(
            path for path in gate2_root.rglob("*") if path.is_file()
        )

    snapshot = gate2_files()

    def publish_json(kind: str, payload: object) -> Gate2ArtifactIdentity:
        identity = store.write_json(kind, payload)
        observe(kind)
        if kind == fail_after_kind:
            raise Gate2SealError(
                "SEAL_PUBLICATION_FAILED",
                f"SEAL_PUBLICATION_FAILED: injected failure after publishing "
                f"{kind}",
            )
        return identity

    published: list[Gate2ArtifactIdentity] = [
        publish_json(
            "engine_contract",
            EngineContract(
                gate1_manifest=authority.manifest_identity,
                qfq_methodology_identity=authority.qfq_methodology_identity,
                friction_cases_bps=(0, 3, 10, 25, 50),
                unavailable_statistics=authority.unavailable_statistics,
                safety=authority.safety,
            ).model_dump(mode="json"),
        ),
        publish_json(
            "family_implementation_bindings",
            FamilyBindingSet(bindings=family_bindings).model_dump(
                mode="json"
            ),
        ),
        publish_json(
            "candidate_implementation_bindings",
            CandidateBindingSet(bindings=candidate_bindings).model_dump(
                mode="json"
            ),
        ),
        publish_json(
            "synthetic_conformance",
            record.model_dump(mode="json"),
        ),
    ]

    report_bytes = _report_bytes(authority, record)
    report_identity = store.write_bytes(MARKDOWN_KIND, report_bytes)
    observe("phase4_engine_report")
    if "phase4_engine_report" == fail_after_kind:
        raise Gate2SealError(
            "SEAL_PUBLICATION_FAILED",
            "SEAL_PUBLICATION_FAILED: injected failure after publishing "
            "phase4_engine_report",
        )
    published.append(report_identity)

    confined = gate2_files() - snapshot
    expected_paths = {
        root.joinpath(*Path(identity.path).parts)
        for identity in published
    }
    unconfined = confined - expected_paths
    if unconfined:
        raise Gate2SealError(
            "SEAL_PUBLICATION_FAILED",
            "SEAL_PUBLICATION_FAILED: writes escaped the Gate 2 confinement: "
            f"{sorted(path.as_posix() for path in unconfined)}",
        )

    for identity in authority.direct_dependencies:
        _reread_dependency(root, identity)

    manifest = Phase4EngineManifest(
        head_revision=authority.head_revision,
        gate1_manifest=authority.manifest_identity,
        qfq_methodology_identity=authority.qfq_methodology_identity,
        candidate_population_sha256=(
            authority.grids.candidate_parameter_population_sha256
        ),
        family_identities=tuple(
            family.family_id for family in families
        ),
        readiness_manifest=authority.readiness_manifest,
        runtime=EngineRuntimeIdentity(
            python_implementation=platform.python_implementation(),
            python_version=platform.python_version(),
            platform=sys.platform,
        ),
        source_bundles=tuple(digests),
        unavailable_statistics=authority.unavailable_statistics,
        safety=authority.safety,
        read_ledger=authority.direct_dependencies,
        write_ledger=tuple(published),
    )
    manifest_identity = store.commit_manifest(
        manifest.model_dump(mode="json")
    )
    observe(MANIFEST_KIND)

    written = (*published, manifest_identity)
    for identity in written:
        store.verify(identity)

    return Gate2SealResult(
        head_revision=authority.head_revision,
        manifest=manifest_identity,
        written=written,
    )


def _report_bytes(
    authority: Gate2Authority, record: SyntheticConformanceRecord
) -> bytes:
    lines = [
        "# Phase 4 Gate 2 Engine Seal Report",
        "",
        "Status: PHASE4_ENGINE_SEALED",
        "",
        "- Schema: PHASE4-ENGINE-MANIFEST-v1",
        "- Formula: PHASE4-ENGINE-FORMULA-v1",
        f"- Head revision: {authority.head_revision}",
        f"- Gate 1 manifest: {authority.manifest_identity.content_sha256}",
        f"- QFQ methodology: {authority.qfq_methodology_identity}",
        f"- Candidate population: "
        f"{authority.grids.candidate_parameter_population_sha256}",
        f"- Execution: {authority.execution_convention} on "
        f"{authority.execution_series}; primary friction "
        f"{authority.primary_friction_bps} bps; cases (0, 3, 10, 25, 50) bps",
        f"- Decision grade: {authority.decision_grade}",
        f"- Families: 4; candidates: 180",
        f"- Historical Phase 2 trials: "
        f"{authority.historical_phase2_trials}; Phase 4 trials consumed: "
        f"{authority.phase4_trials_consumed}",
        "- Fold status: NOT_BOUND_GATE3_REQUIRED (Gate 3 requirement)",
        "- Regime status: NOT_BOUND_GATE3_REQUIRED (Gate 3 requirement)",
        "",
        "Synthetic conformance invariants:",
    ]
    for invariant in record.invariants:
        lines.append(f"- {invariant.name}: {invariant.status}")
    lines.extend(
        (
            "",
            "Unavailable statistics: max drawdown and calmar remain "
            "UNKNOWN (null); DSR and PBO remain UNKNOWN (NOT_IMPLEMENTED, "
            "null); QFQ normalized series is not decision-grade.",
            "No Phase 4 train/validation replay, validation metric access, "
            "candidate ranking, survivor selection, provider call, or "
            "trading capability occurred.",
        )
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _reread_dependency(
    root: Path, identity: DirectDependencyIdentity
) -> bytes:
    path = root.joinpath(*Path(identity.path).parts)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise Gate2SealError(
            "HISTORICAL_ARTIFACT_MUTATION",
            f"HISTORICAL_ARTIFACT_MUTATION: direct dependency is unreadable: "
            f"{identity.path}",
        ) from exc
    if sha256(payload).hexdigest() != identity.content_sha256:
        raise Gate2SealError(
            "HISTORICAL_ARTIFACT_MUTATION",
            f"HISTORICAL_ARTIFACT_MUTATION: direct dependency content changed "
            f"since the authority load: {identity.path}",
        )
    return payload


__all__ = ("seal_gate2",)
