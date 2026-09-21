"""Generation-2 independent-source provenance and reconciliation.

Implements the content-addressed source-snapshot provenance model from
``2026-09-22-generation2-independent-source-provenance.md``.

Two hard rules from that spec:

* A coordinator-generated statement that the data are independent is *not*
  evidence. Independence must be established by a separate-provider snapshot
  or an immutable provider-origin export.
* Reconciliation is result-independent and reports *all* mismatches. A
  decision-critical mismatch may never be overwritten, averaged, or chosen on
  the basis of downstream strategy performance.

This framework also never claims to resolve the Generation-1
``INDEPENDENT_SOURCE_SNAPSHOT_MISSING`` limitation: that is a separate,
frozen governance record.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PROVENANCE_SCHEMA = "G2-INDEPENDENT-SOURCE-PROVENANCE-v1"

__all__ = [
    "PROVENANCE_SCHEMA",
    "FileHash",
    "FieldMismatch",
    "ReconciliationReport",
    "SourceSnapshot",
    "reconcile",
    "snapshot_content_sha256",
]

IndependenceKind = Literal[
    "SAME_PROVIDER",
    "SEPARATE_PROVIDER",
    "PROVIDER_ORIGIN_EXPORT",
]
ReconciliationStatus = Literal["MATCHED", "MISMATCH", "UNKNOWN_ABSTAIN"]


class FileHash(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1)
    sha256: str = Field(min_length=1)

    @property
    def normalized_symbol(self) -> str:
        return self.symbol.strip().upper()


class SourceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[PROVENANCE_SCHEMA]
    provider: str = Field(min_length=1)
    acquisition_utc: str = Field(min_length=1)
    symbols: tuple[str, ...] = Field(min_length=1)
    range_start: str = Field(min_length=1)
    range_end: str = Field(min_length=1)
    adjustment_convention: str = Field(min_length=1)
    raw_file_hashes: tuple[FileHash, ...] = ()
    normalized_file_hashes: tuple[FileHash, ...] = ()
    expected_session_authority_sha256: str = Field(min_length=1)
    corporate_action_source_hashes: tuple[FileHash, ...] = ()
    transformation_code_version: str = Field(min_length=1)
    independence: IndependenceKind

    @property
    def normalized_symbols(self) -> frozenset[str]:
        return frozenset(symbol.strip().upper() for symbol in self.symbols)


def _canonical_bytes(snapshot: SourceSnapshot) -> bytes:
    payload = json.loads(snapshot.model_dump_json())
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


def snapshot_content_sha256(snapshot: SourceSnapshot) -> str:
    """Content-addressed identity of a source snapshot."""
    return hashlib.sha256(_canonical_bytes(snapshot)).hexdigest()


class FieldMismatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    primary: str
    independent: str
    decision_critical: bool


def _normalized_map(hashes: tuple[FileHash, ...]) -> dict[str, str]:
    return {item.normalized_symbol: item.sha256 for item in hashes}


class ReconciliationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    status: ReconciliationStatus
    mismatches: tuple[FieldMismatch, ...]
    decision_critical: bool
    independent_source_established: bool
    # Frozen to False: this framework must never claim to resolve the
    # Generation-1 independent-source limitation on its own.
    resolves_generation1_limitation: bool
    primary_hash: str
    independent_hash: str | None


def _independence_established(
    primary: SourceSnapshot, independent: SourceSnapshot
) -> bool:
    if independent.independence == "PROVIDER_ORIGIN_EXPORT":
        return True
    if independent.independence == "SEPARATE_PROVIDER":
        return independent.provider.strip().upper() != primary.provider.strip().upper()
    # SAME_PROVIDER: a coordinator statement is not evidence.
    return False


def reconcile(
    primary: SourceSnapshot,
    independent: SourceSnapshot | None,
) -> ReconciliationReport:
    """Result-independent reconciliation; reports ALL mismatches.

    Missing / non-independent evidence => ``UNKNOWN_ABSTAIN``. No downstream
    performance is consulted.
    """
    if independent is None:
        return ReconciliationReport(
            schema_version=PROVENANCE_SCHEMA,
            status="UNKNOWN_ABSTAIN",
            mismatches=(),
            decision_critical=False,
            independent_source_established=False,
            resolves_generation1_limitation=False,
            primary_hash=snapshot_content_sha256(primary),
            independent_hash=None,
        )

    established = _independence_established(primary, independent)
    mismatches: list[FieldMismatch] = []
    if not established:
        mismatches.append(
            FieldMismatch(
                field="independence",
                primary="NOT_ESTABLISHED",
                independent=independent.independence,
                decision_critical=True,
            )
        )
    else:
        p_norm = _normalized_map(primary.normalized_file_hashes)
        i_norm = _normalized_map(independent.normalized_file_hashes)
        if primary.normalized_symbols != independent.normalized_symbols:
            mismatches.append(
                FieldMismatch(
                    field="symbols",
                    primary=",".join(sorted(primary.normalized_symbols)),
                    independent=",".join(sorted(independent.normalized_symbols)),
                    decision_critical=True,
                )
            )
        for field in ("range_start", "range_end", "adjustment_convention", "expected_session_authority_sha256"):
            if getattr(primary, field) != getattr(independent, field):
                mismatches.append(
                    FieldMismatch(
                        field=field,
                        primary=getattr(primary, field),
                        independent=getattr(independent, field),
                        decision_critical=True,
                    )
                )
        if p_norm != i_norm:
            mismatches.append(
                FieldMismatch(
                    field="normalized_file_hashes",
                    primary=json.dumps(p_norm, sort_keys=True),
                    independent=json.dumps(i_norm, sort_keys=True),
                    decision_critical=True,
                )
            )
        if _normalized_map(primary.corporate_action_source_hashes) != _normalized_map(
            independent.corporate_action_source_hashes
        ):
            mismatches.append(
                FieldMismatch(
                    field="corporate_action_source_hashes",
                    primary=json.dumps(_normalized_map(primary.corporate_action_source_hashes), sort_keys=True),
                    independent=json.dumps(_normalized_map(independent.corporate_action_source_hashes), sort_keys=True),
                    decision_critical=True,
                )
            )
        # Transformation-code version is provenance metadata: a difference is
        # reported but is not decision-critical. Provider identity and the
        # acquisition timestamp are the independence mechanism, not data, so
        # they are not diffed here.
        if primary.transformation_code_version != independent.transformation_code_version:
            mismatches.append(
                FieldMismatch(
                    field="transformation_code_version",
                    primary=primary.transformation_code_version,
                    independent=independent.transformation_code_version,
                    decision_critical=False,
                )
            )

    decision_critical = any(item.decision_critical for item in mismatches)
    if not established:
        status: ReconciliationStatus = "UNKNOWN_ABSTAIN"
    elif mismatches:
        status = "MISMATCH"
    else:
        status = "MATCHED"

    return ReconciliationReport(
        schema_version=PROVENANCE_SCHEMA,
        status=status,
        mismatches=tuple(mismatches),
        decision_critical=decision_critical,
        independent_source_established=established,
        resolves_generation1_limitation=False,
        primary_hash=snapshot_content_sha256(primary),
        independent_hash=snapshot_content_sha256(independent),
    )
