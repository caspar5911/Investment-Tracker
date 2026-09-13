from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Callable

from pydantic import ValidationError

from investment_tracker.quant import constants as quant_constants
from investment_tracker.quant.phase4.preregistration.access import (
    Gate1AccessEvidence,
)
from investment_tracker.quant.phase4.preregistration.baselines import (
    BaselineDefinitionSet,
)
from investment_tracker.quant.phase4.preregistration.canonical import (
    artifact_envelope_identity,
    canonical_json_bytes,
)
from investment_tracker.quant.phase4.preregistration.grids import (
    PreregisteredGrids,
)
from investment_tracker.quant.phase4.preregistration.journal import (
    GENESIS_DIGEST,
    Gate1JournalRecord,
    Gate1JournalState,
)
from investment_tracker.quant.phase4.preregistration.models import (
    Gate1ArtifactIdentity,
)
from investment_tracker.quant.phase4.preregistration.policy import (
    DQ030UnavailableMetrics,
    DurabilityPolicy,
    FamilyStopPolicy,
    Phase5DownstreamContract,
    SurvivorPolicy,
)
from investment_tracker.quant.phase4.preregistration.seal import (
    READINESS_REVALIDATED_REVISION,
    Phase4PreregistrationManifest,
)
from .models import (
    DirectDependencyIdentity,
    Gate2Authority,
    Gate2SealError,
    HistoricalTrialAuthorityMetadata,
    HistoricalTrialIdentity,
    ReadinessTerminalMetadata,
    SafetyAccessState,
    SplitTerminalMetadata,
    TerminalArtifactIdentity,
    TerminalProtectedTreeDigest,
    TrialAuthorityTerminalMetadata,
    UnavailableStatistics,
)


STARTING_REVISION = "fb1c30a6c9789bddf2033301977fc8e2f3ebc1a0"
EXPECTED_EXECUTION_CONVENTION = "COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN"
EXPECTED_POPULATION_SHA256 = (
    "15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3"
)
MANIFEST_PATH = (
    "results/phase4/gate1/phase4_preregistration_manifest/sha256/"
    "dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89/"
    "manifest.json"
)


GATE1_MANIFEST_IDENTITY = Gate1ArtifactIdentity(
    kind="phase4_preregistration_manifest",
    path=MANIFEST_PATH,
    content_sha256=("dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89"),
    sha256="e43ccbb596a9f66222b4e2785b1c40c423e6bb43b54b788e1fdb6358e1cdf146",
)


PINNED_DIRECT_DEPENDENCIES = (
    DirectDependencyIdentity(**GATE1_MANIFEST_IDENTITY.model_dump()),
    DirectDependencyIdentity(
        kind="baseline_definitions",
        path="results/phase4/gate1/baseline_definitions/sha256/4ce3dedb8d4187a18175f08e22df63f2905ffd9df75aa72f6c11f31249a465b0/baselines.json",
        content_sha256="4ce3dedb8d4187a18175f08e22df63f2905ffd9df75aa72f6c11f31249a465b0",
        sha256="ee807d7cee694dfe495d3141a85666fe796e14cf8cd590e7f33b65deda6af178",
    ),
    DirectDependencyIdentity(
        kind="deterministic_grids",
        path="results/phase4/gate1/deterministic_grids/sha256/40f40573ac8abfc8707231cc05d65e780967b79495c0572c89b988eb1d20f0bd/grids.json",
        content_sha256="40f40573ac8abfc8707231cc05d65e780967b79495c0572c89b988eb1d20f0bd",
        sha256="a623a3974f0ef32128b192e00b8f0a711c2a236c6264460c9f23c2656ce55173",
    ),
    DirectDependencyIdentity(
        kind="durability_policy",
        path="results/phase4/gate1/durability_policy/sha256/37195247139733d81a0772c0fe84222e51237198ab33954eb2a4c0e96880843c/policy.json",
        content_sha256="37195247139733d81a0772c0fe84222e51237198ab33954eb2a4c0e96880843c",
        sha256="5739bbeba8298a1df72d65bfbb55b19a8be4d8d7899f987bb4aa4e0ceaee1d8f",
    ),
    DirectDependencyIdentity(
        kind="family_budget_policy",
        path="results/phase4/gate1/family_budget_policy/sha256/ae7482967c475216bb09e7c0beb39e179019c6f065ca271ee6f8d51756b478d5/policy.json",
        content_sha256="ae7482967c475216bb09e7c0beb39e179019c6f065ca271ee6f8d51756b478d5",
        sha256="caa5004667590ecbd7945fd04812960e8696a2f23a7b45fe9a86d7ea98af09b4",
    ),
    DirectDependencyIdentity(
        kind="information_access_policy",
        path="results/phase4/gate1/information_access_policy/sha256/286d167a06271fa6223641735f22d5b78ab71f0dca7ae7b03561eac2695e485e/policy.json",
        content_sha256="286d167a06271fa6223641735f22d5b78ab71f0dca7ae7b03561eac2695e485e",
        sha256="c90cfcd91ac4aed9434a018f3185d6c85e0f82b7946107d1b5c38edb7722134f",
    ),
    DirectDependencyIdentity(
        kind="research_report",
        path="results/phase4/gate1/research_report/sha256/3379e0382b5fcd5c9abffecf216e9243e67ddb77d3386bb1b7c7296bed8fc35a/report.md",
        content_sha256="3379e0382b5fcd5c9abffecf216e9243e67ddb77d3386bb1b7c7296bed8fc35a",
        sha256="60436b1ef997a904d97123c2551ac1ca21e7fa38f32ce5092023fb118d577e09",
    ),
    DirectDependencyIdentity(
        kind="strategy_family_definitions",
        path="results/phase4/gate1/strategy_family_definitions/sha256/d3a2744d5c642cf5fd5042df04630ec5fffc02709f0da25c4f326b5e57d9a55c/families.json",
        content_sha256="d3a2744d5c642cf5fd5042df04630ec5fffc02709f0da25c4f326b5e57d9a55c",
        sha256="38860148edd7683e73af09df1f78a0a999eba2660369a89cb77fb41a14c4ecc9",
    ),
    DirectDependencyIdentity(
        kind="survivor_policy",
        path="results/phase4/gate1/survivor_policy/sha256/7529b02a76622d97cf6568290a91142c33409ee4a02c137be6d09c0142655a63/policy.json",
        content_sha256="7529b02a76622d97cf6568290a91142c33409ee4a02c137be6d09c0142655a63",
        sha256="0d80fa6543b9045b165c1b407dba051513b913b367650111e80d061bdfe28fab",
    ),
    DirectDependencyIdentity(
        kind="hypothesis_journal",
        path="results/research/hypothesis_registry.jsonl",
        content_sha256="5a3fcd85805c2efb2fbff7c024511eddcff8bace0dcd2045c4c01521f6753b0d",
    ),
    DirectDependencyIdentity(
        kind="source_journal",
        path="results/research/sources.jsonl",
        content_sha256="93aa3a81c45b8f8f4b39c68e223787bd61300886081e1fa5dfd7e837105d8bd4",
    ),
    DirectDependencyIdentity(
        kind="research_notes",
        path="results/research/research_notes.md",
        content_sha256="405e99adefe5d36321f029b9525a51c244950674e3e61ff9e2387f371be30e0f",
    ),
    DirectDependencyIdentity(
        kind="phase4_readiness_manifest",
        path="results/phase4/readiness/phase4_readiness_manifest/sha256/4305845b627ed2d369f3e16b26eb0e9ec724c13ea50904fcf5fd4113f264a254/manifest.json",
        content_sha256="4305845b627ed2d369f3e16b26eb0e9ec724c13ea50904fcf5fd4113f264a254",
        sha256="25cea5b7cf490a4010244bd03968d342516bb27854b9488dbc9f9cdc2d375471",
    ),
    DirectDependencyIdentity(
        kind="phase4_split_manifest",
        path="results/phase4/readiness/phase4_split_manifest/sha256/b273f79795237caca08d1a10388be8d300e9f4b5f51c818a24456c972c7bb4d7/manifest.json",
        content_sha256="b273f79795237caca08d1a10388be8d300e9f4b5f51c818a24456c972c7bb4d7",
        sha256="3300510d6ea86aa077b5a2a2c2dd734d7e3602cc87513910af8db7c004fe0dab",
    ),
    DirectDependencyIdentity(
        kind="trial_authority",
        path="results/phase4/readiness/trial_authority/sha256/fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994/authority.json",
        content_sha256="fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994",
        sha256="2ab77e480a61c57f1c29395d4e93c2d9302533ab2f67ce364037965d1e1eb3f3",
    ),
)


def _repository_root(repository_root: Path, code: str) -> Path:
    supplied = Path(repository_root)
    try:
        if supplied.is_symlink():
            raise Gate2SealError(code, "repository root is a symlink")
        root = supplied.resolve(strict=True)
    except Gate2SealError:
        raise
    except OSError as exc:
        raise Gate2SealError(code, "repository root does not exist") from exc
    if not root.is_dir():
        raise Gate2SealError(code, "repository root is not a directory")
    return root


def _read_exact(
    root: Path,
    identity: DirectDependencyIdentity,
    observer: Callable[[str], None],
    code: str,
) -> bytes:
    current = root
    for component in PurePosixPath(identity.path).parts:
        current = current / component
        if current.is_symlink():
            raise Gate2SealError(code, f"dependency path is symlinked: {identity.path}")
    if not current.is_file():
        raise Gate2SealError(code, f"dependency is not a regular file: {identity.path}")
    try:
        payload = current.read_bytes()
    except OSError as exc:
        raise Gate2SealError(
            code, f"dependency is unreadable: {identity.path}"
        ) from exc
    if sha256(payload).hexdigest() != identity.content_sha256:
        raise Gate2SealError(code, f"dependency content mismatch: {identity.path}")
    observer(identity.path)
    return payload


def _canonical_json(payload: bytes, code: str, label: str) -> object:
    try:
        parsed = json.loads(payload.decode("utf-8"))
        if canonical_json_bytes(parsed) != payload:
            raise ValueError("noncanonical JSON bytes")
        return parsed
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise Gate2SealError(code, f"{label} is not canonical JSON") from exc


def _model(model_type, payload: bytes, code: str, label: str):
    parsed = _canonical_json(payload, code, label)
    try:
        return model_type.model_validate(parsed)
    except (ValidationError, ValueError, TypeError) as exc:
        raise Gate2SealError(code, f"{label} model mismatch") from exc


def _verify_journal(
    payload: bytes,
    state: Gate1JournalState,
    code: str,
) -> None:
    if sha256(payload).hexdigest() != state.file_sha256:
        raise Gate2SealError(code, "journal exact-byte identity mismatch")
    if not payload.endswith(b"\n") or b"\r" in payload:
        raise Gate2SealError(code, "journal serialization mismatch")
    predecessor = GENESIS_DIGEST
    records = []
    try:
        for raw_line in payload[:-1].split(b"\n"):
            parsed = json.loads(raw_line.decode("utf-8"))
            if canonical_json_bytes(parsed) != raw_line:
                raise ValueError("noncanonical journal record")
            record = Gate1JournalRecord.model_validate(parsed)
            if record.record_kind != state.record_kind:
                raise ValueError("journal record kind mismatch")
            if record.predecessor_digest != predecessor:
                raise ValueError("journal predecessor mismatch")
            predecessor = record.record_digest
            records.append(record)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ) as exc:
        raise Gate2SealError(code, "journal chain mismatch") from exc
    if len(records) != state.record_count or predecessor != state.terminal_digest:
        raise Gate2SealError(code, "journal terminal state mismatch")


def _terminal_artifact(payload: object) -> TerminalArtifactIdentity:
    if not isinstance(payload, dict):
        raise ValueError("terminal artifact identity must be an object")
    return TerminalArtifactIdentity.model_validate(payload)


def _readiness_metadata(payload: bytes) -> ReadinessTerminalMetadata:
    parsed = _canonical_json(payload, "GATE1_DEPENDENCY_MISMATCH", "readiness manifest")
    expected_fields = {
        "bootstrap_audit",
        "bootstrap_input_vector",
        "campaign_configuration",
        "decision_grade",
        "dependency_identity",
        "dsr",
        "execution_series",
        "external_strategy_research_performed",
        "final_holdout_accessed",
        "historical_phase2_trial_count",
        "live_trading_capability",
        "pbo",
        "phase4_new_trials_consumed",
        "phase4_new_trials_remaining",
        "protected_symbols_accessed",
        "protected_tree_digests",
        "provider_calls",
        "readiness_report",
        "schema_version",
        "signal_series",
        "source_revision",
        "split_manifest",
        "status",
        "strategy_discovery_authorized",
        "strategy_search_executed",
        "trial_authority",
    }
    try:
        if not isinstance(parsed, dict) or set(parsed) != expected_fields:
            raise ValueError("readiness manifest fields mismatch")
        if parsed["schema_version"] != "PHASE4-READINESS-MANIFEST-v1":
            raise ValueError("readiness schema mismatch")
        for name in (
            "bootstrap_audit",
            "bootstrap_input_vector",
            "campaign_configuration",
            "readiness_report",
        ):
            _terminal_artifact(parsed[name])
        for name in ("dsr", "pbo"):
            statistic = parsed[name]
            if (
                not isinstance(statistic, dict)
                or set(statistic)
                != {
                    "interpretation",
                    "name",
                    "reason",
                    "schema_version",
                    "status",
                    "value",
                }
                or statistic["name"] != name.upper()
                or statistic["status"] != "NOT_IMPLEMENTED"
                or statistic["interpretation"] != "UNKNOWN"
                or statistic["value"] is not None
            ):
                raise ValueError("readiness statistic mismatch")
        return ReadinessTerminalMetadata(
            status=parsed["status"],
            source_revision=parsed["source_revision"],
            trial_authority=_terminal_artifact(parsed["trial_authority"]),
            split_manifest=_terminal_artifact(parsed["split_manifest"]),
            historical_phase2_trial_count=parsed["historical_phase2_trial_count"],
            phase4_new_trials_consumed=parsed["phase4_new_trials_consumed"],
            phase4_new_trials_remaining=parsed["phase4_new_trials_remaining"],
            signal_series=parsed["signal_series"],
            execution_series=parsed["execution_series"],
            decision_grade=parsed["decision_grade"],
            provider_calls=parsed["provider_calls"],
            external_strategy_research_performed=parsed[
                "external_strategy_research_performed"
            ],
            strategy_search_executed=parsed["strategy_search_executed"],
            strategy_discovery_authorized=parsed["strategy_discovery_authorized"],
            final_holdout_accessed=parsed["final_holdout_accessed"],
            protected_symbols_accessed=tuple(parsed["protected_symbols_accessed"]),
            live_trading_capability=parsed["live_trading_capability"],
            protected_tree_digests=tuple(
                TerminalProtectedTreeDigest.model_validate(item)
                for item in parsed["protected_tree_digests"]
            ),
        )
    except (KeyError, TypeError, ValidationError, ValueError) as exc:
        raise Gate2SealError(
            "GATE1_DEPENDENCY_MISMATCH", "readiness terminal metadata mismatch"
        ) from exc


def _split_metadata(payload: bytes) -> SplitTerminalMetadata:
    parsed = _canonical_json(payload, "GATE1_DEPENDENCY_MISMATCH", "split manifest")
    expected_fields = {
        "final_holdout_accessed",
        "partitions",
        "phase3_dq_snapshot_artifact",
        "phase3_dq_snapshot_digest",
        "phase3_universe_artifact",
        "phase3_universe_digest",
        "protected_symbols_accessed",
        "provider_calls",
        "schema_version",
        "split_policy_version",
        "symbols",
    }
    try:
        if not isinstance(parsed, dict) or set(parsed) != expected_fields:
            raise ValueError("split manifest fields mismatch")
        if (
            parsed["schema_version"] != "PHASE4-SPLIT-MANIFEST-v1"
            or parsed["split_policy_version"] != "PHASE4-TEMPORAL-SPLIT-v1"
        ):
            raise ValueError("split schema mismatch")
        partitions = parsed["partitions"]
        if not isinstance(partitions, list) or len(partitions) != 8:
            raise ValueError("split partition count mismatch")
        if tuple(item["symbol"] for item in partitions) != tuple(parsed["symbols"]):
            raise ValueError("split symbol order mismatch")
        partition_artifacts = tuple(
            _terminal_artifact(item[name])
            for item in partitions
            for name in ("metadata_artifact", "bars_artifact")
        )
        return SplitTerminalMetadata(
            phase3_universe_artifact=_terminal_artifact(
                parsed["phase3_universe_artifact"]
            ),
            phase3_universe_digest=parsed["phase3_universe_digest"],
            phase3_dq_snapshot_artifact=_terminal_artifact(
                parsed["phase3_dq_snapshot_artifact"]
            ),
            phase3_dq_snapshot_digest=parsed["phase3_dq_snapshot_digest"],
            symbols=tuple(parsed["symbols"]),
            partition_artifact_identities=partition_artifacts,
            provider_calls=parsed["provider_calls"],
            final_holdout_accessed=parsed["final_holdout_accessed"],
            protected_symbols_accessed=tuple(parsed["protected_symbols_accessed"]),
        )
    except (KeyError, TypeError, ValidationError, ValueError) as exc:
        raise Gate2SealError(
            "GATE1_DEPENDENCY_MISMATCH", "split terminal metadata mismatch"
        ) from exc


def _trial_metadata(payload: bytes) -> TrialAuthorityTerminalMetadata:
    parsed = _canonical_json(payload, "GATE1_DEPENDENCY_MISMATCH", "trial authority")
    authority_fields = {
        "campaign_id",
        "final_authoritative_representation_count",
        "historical_phase2_trial_count",
        "non_authoritative_artifacts",
        "original_representation_count",
        "out_of_scope_representation_count",
        "preliminary_representation_count",
        "representation_selector_version",
        "schema_version",
        "source_revisions",
        "total_representation_count",
        "trials",
    }
    search_fields = {
        "historical_trial_count",
        "multiple_testing_count",
        "ordered_pbo_trial_ids",
        "ordered_sharpe_trial_ids",
        "schema_version",
        "sharpe_inputs",
    }
    try:
        if not isinstance(parsed, dict) or set(parsed) != {
            "authority",
            "schema_version",
            "search_aware_inputs",
        }:
            raise ValueError("trial authority wrapper fields mismatch")
        if parsed["schema_version"] != "PHASE4-TRIAL-AUTHORITY-EVIDENCE-v1":
            raise ValueError("trial authority wrapper schema mismatch")
        authority = parsed["authority"]
        search = parsed["search_aware_inputs"]
        if not isinstance(authority, dict) or set(authority) != authority_fields:
            raise ValueError("trial authority fields mismatch")
        if (
            authority["schema_version"] != "PHASE4-TRIAL-AUTHORITY-v1"
            or authority["representation_selector_version"]
            != "PHASE2-REPRESENTATION-SELECTOR-v1"
        ):
            raise ValueError("trial authority schema mismatch")
        trials = tuple(
            HistoricalTrialIdentity(
                trial_id=item["trial_id"],
                campaign_id=item["campaign_id"],
                candidate_id=item["candidate_id"],
                authoritative_artifact=_terminal_artifact(
                    item["authoritative_artifact"]
                ),
                non_authoritative_artifacts=tuple(
                    _terminal_artifact(artifact)
                    for artifact in item["non_authoritative_artifacts"]
                ),
            )
            for item in authority["trials"]
        )
        terminal_authority = HistoricalTrialAuthorityMetadata(
            campaign_id=authority["campaign_id"],
            historical_phase2_trial_count=authority["historical_phase2_trial_count"],
            total_representation_count=authority["total_representation_count"],
            original_representation_count=authority["original_representation_count"],
            preliminary_representation_count=authority[
                "preliminary_representation_count"
            ],
            final_authoritative_representation_count=authority[
                "final_authoritative_representation_count"
            ],
            out_of_scope_representation_count=authority[
                "out_of_scope_representation_count"
            ],
            source_revisions=tuple(authority["source_revisions"]),
            non_authoritative_artifacts=tuple(
                _terminal_artifact(item)
                for item in authority["non_authoritative_artifacts"]
            ),
            trials=trials,
        )
        if not isinstance(search, dict) or set(search) != search_fields:
            raise ValueError("search-aware input fields mismatch")
        ordered_ids = tuple(search["ordered_sharpe_trial_ids"])
        if (
            search["schema_version"] != "PHASE4-SEARCH-AWARE-INPUTS-v1"
            or search["historical_trial_count"] != 136
            or search["multiple_testing_count"] != 136
            or tuple(search["ordered_pbo_trial_ids"]) != ordered_ids
            or tuple(item["trial_id"] for item in search["sharpe_inputs"])
            != ordered_ids
        ):
            raise ValueError("search-aware trial linkage mismatch")
        return TrialAuthorityTerminalMetadata(
            authority=terminal_authority,
            ordered_trial_ids=ordered_ids,
        )
    except (KeyError, TypeError, ValidationError, ValueError) as exc:
        raise Gate2SealError(
            "GATE1_DEPENDENCY_MISMATCH", "trial authority terminal metadata mismatch"
        ) from exc


def _head_revision(root: Path, supplied: str | None) -> str:
    if supplied is None:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            raise Gate2SealError("GATE1_MANIFEST_MISMATCH", "HEAD is unavailable")
        try:
            revision = completed.stdout.decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise Gate2SealError(
                "GATE1_MANIFEST_MISMATCH", "HEAD revision is invalid"
            ) from exc
    else:
        revision = supplied
    if len(revision) != 40 or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise Gate2SealError("GATE1_MANIFEST_MISMATCH", "HEAD revision is invalid")
    return revision


def _verify_ancestry(root: Path, head_revision: str, manifest_revision: str) -> None:
    for ancestor in (
        STARTING_REVISION,
        manifest_revision,
        READINESS_REVALIDATED_REVISION,
    ):
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, head_revision],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            raise Gate2SealError(
                "GATE1_MANIFEST_MISMATCH",
                f"required revision is not an ancestor of HEAD: {ancestor}",
            )


def _derived_dependencies(
    manifest: Phase4PreregistrationManifest,
) -> tuple[DirectDependencyIdentity, ...]:
    artifact_fields = (
        manifest.baseline_definitions,
        manifest.deterministic_grids,
        manifest.durability_policy,
        manifest.family_budget_policy,
        manifest.information_access_policy,
        manifest.research_report,
        manifest.strategy_family_definitions,
        manifest.survivor_policy,
    )
    return (
        DirectDependencyIdentity(**GATE1_MANIFEST_IDENTITY.model_dump()),
        *(DirectDependencyIdentity(**item.model_dump()) for item in artifact_fields),
        DirectDependencyIdentity(
            kind="hypothesis_journal",
            path=manifest.hypothesis_journal.path,
            content_sha256=manifest.hypothesis_journal.file_sha256,
        ),
        DirectDependencyIdentity(
            kind="source_journal",
            path=manifest.source_journal.path,
            content_sha256=manifest.source_journal.file_sha256,
        ),
        DirectDependencyIdentity(
            kind="research_notes",
            path=manifest.research_notes_path,
            content_sha256=manifest.research_notes_content_sha256,
        ),
        DirectDependencyIdentity(**manifest.readiness_manifest.model_dump()),
        DirectDependencyIdentity(**manifest.split_manifest.model_dump()),
        DirectDependencyIdentity(**manifest.trial_authority.model_dump()),
    )


def _validate_payload_links(
    manifest: Phase4PreregistrationManifest,
    payloads: tuple[bytes, ...],
):
    baseline_payload, grid_payload, durability_payload, budget_payload = payloads[:4]
    access_payload, _, family_payload, survivor_payload = payloads[4:8]
    readiness_payload, split_payload, trial_payload = payloads[11:14]

    baselines = _model(
        BaselineDefinitionSet,
        baseline_payload,
        "GATE1_DEPENDENCY_MISMATCH",
        "baseline definitions",
    )
    try:
        grids = _model(
            PreregisteredGrids,
            grid_payload,
            "CANDIDATE_POPULATION_MISMATCH",
            "deterministic grids",
        )
        if (
            grids.candidate_parameter_population_sha256 != EXPECTED_POPULATION_SHA256
            or grids.candidate_parameter_population_sha256
            != manifest.candidate_parameter_population_sha256
            or len(grids.families) != 4
            or len(grids.candidates) != 180
            or tuple(len(item.candidates) for item in grids.families)
            != (54, 36, 36, 54)
            or tuple(item.budget_position for item in grids.candidates)
            != tuple(range(1, 181))
        ):
            raise ValueError("sealed candidate population mismatch")
    except Gate2SealError:
        raise
    except (ValidationError, ValueError, TypeError) as exc:
        raise Gate2SealError(
            "CANDIDATE_POPULATION_MISMATCH", "sealed candidate population mismatch"
        ) from exc

    family_set = _canonical_json(
        family_payload, "GATE1_DEPENDENCY_MISMATCH", "family definitions"
    )
    expected_family_set = {
        "schema_version": "PHASE4-STRATEGY-FAMILY-DEFINITION-SET-v1",
        "families": [
            item.model_dump(mode="json", exclude={"candidates"})
            for item in grids.families
        ],
    }
    if family_set != expected_family_set:
        raise Gate2SealError(
            "CANDIDATE_POPULATION_MISMATCH",
            "family definitions differ from deterministic grids",
        )
    if tuple(
        (item.family_id, item.rule_set_sha256) for item in grids.families
    ) != tuple(
        (item.family_id, item.rule_set_sha256)
        for item in manifest.family_rule_set_identities
    ):
        raise Gate2SealError(
            "CANDIDATE_POPULATION_MISMATCH", "family rule-set identities mismatch"
        )

    budget = _canonical_json(
        budget_payload, "GATE1_DEPENDENCY_MISMATCH", "family budget policy"
    )
    try:
        if set(budget) != {"budget_policy", "family_stop_policy"}:
            raise ValueError("budget payload fields mismatch")
        budget_policy = type(grids.budget_policy).model_validate(
            budget["budget_policy"]
        )
        FamilyStopPolicy.model_validate(budget["family_stop_policy"])
        if budget_policy != grids.budget_policy:
            raise ValueError("budget differs from deterministic grids")
    except (ValidationError, ValueError, TypeError) as exc:
        raise Gate2SealError(
            "CANDIDATE_POPULATION_MISMATCH", "family budget policy mismatch"
        ) from exc

    durability = _canonical_json(
        durability_payload, "GATE1_DEPENDENCY_MISMATCH", "durability policy"
    )
    survivor = _canonical_json(
        survivor_payload, "GATE1_DEPENDENCY_MISMATCH", "survivor policy"
    )
    try:
        if set(durability) != {"durability_policy", "phase5_downstream_contract"}:
            raise ValueError("durability payload fields mismatch")
        DurabilityPolicy.model_validate(durability["durability_policy"])
        Phase5DownstreamContract.model_validate(
            durability["phase5_downstream_contract"]
        )
        if set(survivor) != {"survivor_policy", "unavailable_metrics"}:
            raise ValueError("survivor payload fields mismatch")
        SurvivorPolicy.model_validate(survivor["survivor_policy"])
        DQ030UnavailableMetrics.model_validate(survivor["unavailable_metrics"])
    except (ValidationError, ValueError, TypeError) as exc:
        raise Gate2SealError(
            "GATE1_DEPENDENCY_MISMATCH", "Gate 1 policy model mismatch"
        ) from exc

    access = _model(
        Gate1AccessEvidence,
        access_payload,
        "GATE1_DEPENDENCY_MISMATCH",
        "information access policy",
    )
    readiness = _readiness_metadata(readiness_payload)
    split = _split_metadata(split_payload)
    trial_authority = _trial_metadata(trial_payload)

    try:
        if access.observed_reads != manifest.observed_read_set:
            raise ValueError("information access evidence mismatch")
        if (
            readiness.trial_authority.model_dump()
            != manifest.trial_authority.model_dump()
        ):
            raise ValueError("readiness trial authority mismatch")
        if (
            readiness.split_manifest.model_dump()
            != manifest.split_manifest.model_dump()
        ):
            raise ValueError("readiness split manifest mismatch")
        if readiness.historical_phase2_trial_count != 136:
            raise ValueError("readiness trial count mismatch")
        if trial_authority.authority.historical_phase2_trial_count != 136:
            raise ValueError("trial authority count mismatch")
        if readiness.execution_series != "QFQ_NORMALIZED" or readiness.decision_grade:
            raise ValueError("readiness execution methodology mismatch")
        if (
            split.phase3_universe_digest != manifest.universe_digest
            or split.phase3_dq_snapshot_digest != manifest.dq_snapshot_digest
        ):
            raise ValueError("split authority digest mismatch")
        if any(
            (
                readiness.phase4_new_trials_consumed,
                readiness.provider_calls,
                split.provider_calls,
            )
        ):
            raise ValueError("terminal authority records nonzero access")
        if any(
            (
                readiness.external_strategy_research_performed,
                readiness.strategy_search_executed,
                readiness.strategy_discovery_authorized,
                readiness.final_holdout_accessed,
                readiness.live_trading_capability,
                split.final_holdout_accessed,
            )
        ):
            raise ValueError("terminal authority records forbidden access")
        if (
            readiness.protected_symbols_accessed
            or split.protected_symbols_accessed
            or access.safety.protected_symbols_accessed
        ):
            raise ValueError("terminal authority records protected access")
        for baseline in baselines.baselines:
            if (
                baseline.readiness_manifest.model_dump()
                != manifest.readiness_manifest.model_dump()
                or baseline.split_manifest.model_dump()
                != manifest.split_manifest.model_dump()
                or baseline.trial_authority.model_dump()
                != manifest.trial_authority.model_dump()
                or baseline.qfq_methodology_identity
                != manifest.qfq_methodology_identity
                or baseline.phase4_family_slots_consumed != 0
                or baseline.phase4_candidate_trials_consumed != 0
                or baseline.phase4_validation_performance_used
                or baseline.eligible_for_selection
                or baseline.validation_driven_selection
            ):
                raise ValueError("baseline authority linkage mismatch")
    except ValueError as exc:
        raise Gate2SealError(
            "GATE1_DEPENDENCY_MISMATCH", "terminal authority linkage mismatch"
        ) from exc

    return baselines, grids, readiness, split, trial_authority


def load_gate2_authority(
    repository_root: Path,
    *,
    head_revision: str | None = None,
    read_observer: Callable[[str], None] | None = None,
) -> Gate2Authority:
    """Load the one pinned Gate 1 authority through its terminal read set."""

    root = _repository_root(repository_root, "GATE1_MANIFEST_MISMATCH")
    observer = read_observer or (lambda _: None)
    manifest_dependency = DirectDependencyIdentity(
        **GATE1_MANIFEST_IDENTITY.model_dump()
    )
    manifest_bytes = _read_exact(
        root,
        manifest_dependency,
        observer,
        "GATE1_MANIFEST_MISMATCH",
    )
    manifest = _model(
        Phase4PreregistrationManifest,
        manifest_bytes,
        "GATE1_MANIFEST_MISMATCH",
        "Gate 1 manifest",
    )
    dependencies = _derived_dependencies(manifest)
    if tuple((item.kind, item.path) for item in dependencies) != tuple(
        (item.kind, item.path) for item in PINNED_DIRECT_DEPENDENCIES
    ):
        raise Gate2SealError(
            "GATE1_MANIFEST_MISMATCH", "Gate 1 direct dependency identities mismatch"
        )

    revision = _head_revision(root, head_revision)
    _verify_ancestry(root, revision, manifest.producing_revision)
    if quant_constants.EXECUTION_CONVENTION != EXPECTED_EXECUTION_CONVENTION:
        raise Gate2SealError(
            "EXECUTION_CONVENTION_MISMATCH", "governed execution convention mismatch"
        )

    payloads = tuple(
        _read_exact(
            root,
            identity,
            observer,
            "GATE1_DEPENDENCY_MISMATCH",
        )
        for identity in dependencies[1:]
    )
    _verify_journal(
        payloads[8], manifest.hypothesis_journal, "GATE1_DEPENDENCY_MISMATCH"
    )
    _verify_journal(payloads[9], manifest.source_journal, "GATE1_DEPENDENCY_MISMATCH")
    baselines, grids, readiness, split, trial_authority = _validate_payload_links(
        manifest, payloads
    )

    unavailable = UnavailableStatistics(
        max_drawdown=manifest.max_drawdown,
        max_drawdown_status=manifest.max_drawdown_status,
        calmar=manifest.calmar,
        calmar_status=manifest.calmar_status,
        dsr=manifest.dsr,
        dsr_status=manifest.dsr_status,
        dsr_reason=manifest.dsr_reason,
        pbo=manifest.pbo,
        pbo_status=manifest.pbo_status,
        pbo_reason=manifest.pbo_reason,
    )
    safety = SafetyAccessState(
        validation_metrics_accessed=manifest.validation_metrics_accessed,
        strategy_search_executed=manifest.strategy_search_executed,
        final_holdout_accessed=manifest.final_holdout_accessed,
        protected_symbols_accessed=manifest.protected_symbols_accessed,
        provider_calls=manifest.provider_calls,
        live_trading_capability=manifest.live_trading_capability,
        phase4_trials_consumed=manifest.phase4_initial_consumption,
    )
    return Gate2Authority(
        starting_revision=STARTING_REVISION,
        head_revision=revision,
        manifest_identity=GATE1_MANIFEST_IDENTITY,
        manifest=manifest,
        grids=grids,
        family_definitions=grids.families,
        baselines=baselines,
        family_definitions_payload=payloads[6],
        baseline_definitions_payload=payloads[0],
        direct_dependencies=dependencies,
        readiness_manifest=readiness,
        split_manifest=split,
        trial_authority=trial_authority,
        execution_convention=EXPECTED_EXECUTION_CONVENTION,
        execution_series=manifest.qfq_execution_methodology,
        primary_friction_bps=3,
        decision_grade=manifest.decision_grade,
        qfq_methodology_identity=manifest.qfq_methodology_identity,
        historical_phase2_trials=manifest.historical_phase2_trials,
        phase4_trials_consumed=manifest.phase4_initial_consumption,
        unavailable_statistics=unavailable,
        safety=safety,
    )
