"""Generation-2 Phase-7 entry gate (future Phase-7 infrastructure).

This is *infrastructure only*: it defines and enforces the fail-closed gate that
must stand between the completed Generation-2 campaign and any Phase-7
progression. It makes **no** real-holdout call, touches **no** network, and
produces **no** real acquisition. Its job is to keep Phase-7 entry impossible
unless *both* of the frozen prerequisites are present and consistent:

1. the real Phase-6 result status is exactly
   ``PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE`` (consumed, not yet
   started, no production approval) — validated by the Checkpoint-A guard
   ``quant.phase7.readiness.assert_phase7_entry``; and
2. an explicit, content-addressed Generation-2 Phase-7 entry artifact
   (``GENERATION2-PHASE7-ENTRY-v1``), authoritative under INDEPENDENT_AUDIT,
   that binds the survivor and the sealed campaign evidence chain to that
   Phase-6 result.

On top of those two, the gate re-runs the synthetic-only CI gate
(``quant.generation2.ci_gate.evaluate``) so that the real-boundary authority
flags in the frozen governance authority remain exactly ``false``. The Phase-7
entry artifact is a *separate* authorization document: it does **not** flip any
authority flag, so the CI gate stays green (all authority flags ``false``) even
while Phase-7 entry is being evaluated.

Against the current repository state — no real Phase-6 result and no Generation-2
Phase-7 entry artifact — the gate fails closed. This module therefore cannot
open Phase-7 on its own; only a future Independent-Audit that produces the
explicit entry artifact from a genuinely-successful real Phase-6 result can.

Run from a repository checkout::

    python -m investment_tracker.quant.generation2.phase7_entry \
        --phase6-result <path> --entry-artifact <path> --repository-root .
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from investment_tracker.quant.generation2 import ci_gate
from investment_tracker.quant.generation2.campaign import content_sha256
from investment_tracker.quant.phase7.readiness import (
    PHASE6_SUCCESS_STATUS,
    Phase7EntryError,
    assert_phase7_entry,
)

GENERATION2_PHASE7_ENTRY_SCHEMA = "GENERATION2-PHASE7-ENTRY-v1"
PHASE7_ENTRY_REPORT_NAME = "generation2-phase7-entry.json"
REQUIRED_PHASE6_STATUS = PHASE6_SUCCESS_STATUS
PHASE7_ENTRY_AUTHORITY = "INDEPENDENT_AUDIT"

# Error codes.
PHASE7_ENTRY_FORBIDDEN = "GEN2_PHASE7_ENTRY_FORBIDDEN"
PHASE7_ENTRY_PHASE6_INVALID = "GEN2_PHASE7_ENTRY_PHASE6_INVALID"
PHASE7_ENTRY_ARTIFACT_MISSING = "GEN2_PHASE7_ENTRY_ARTIFACT_MISSING"
PHASE7_ENTRY_ARTIFACT_TAMPERED = "GEN2_PHASE7_ENTRY_ARTIFACT_TAMPERED"
PHASE7_ENTRY_PHASE6_STATUS_MISMATCH = "GEN2_PHASE7_ENTRY_PHASE6_STATUS_MISMATCH"
PHASE7_ENTRY_CANDIDATE_MISMATCH = "GEN2_PHASE7_ENTRY_CANDIDATE_MISMATCH"
PHASE7_ENTRY_CI_GATE_RED = "GEN2_PHASE7_ENTRY_CI_GATE_RED"

_HEX64 = r"^[0-9a-f]{64}$"
_HEX_SHA_RE = re.compile(_HEX64)


class Phase7EntryGateError(RuntimeError):
    """Fail-closed Generation-2 Phase-7 entry error carrying a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}" if not detail else f"{code}:{detail}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX_SHA_RE.fullmatch(value))


def _payload_sha256(payload: dict) -> str:
    return content_sha256(payload)


def seal_generation2_phase7_entry(
    *,
    candidate_id: str,
    survivor: str,
    phase6_status: str,
    phase6_result_sha256: str,
    validation_report_sha256: str,
    survivor_freeze_sha256: str,
    survivor_rehearsal_sha256: str,
    authority: str = PHASE7_ENTRY_AUTHORITY,
    root: Path | str | None = None,
) -> dict:
    """Build and exclusively write the Generation-2 Phase-7 entry artifact.

    The payload is canonical-JSON, self-hashing (``artifact_sha256`` is computed
    over the payload without that key) and refuses to overwrite an existing
    artifact. ``phase6_status`` must already be the required Phase-6 success
    status; the artifact *records* that status but does not itself authorize
    any real-boundary action (the CI authority flags remain ``false``).
    """
    if not isinstance(candidate_id, str) or not candidate_id:
        raise Phase7EntryGateError(PHASE7_ENTRY_FORBIDDEN, "candidate_id missing")
    if not isinstance(survivor, str) or not survivor:
        raise Phase7EntryGateError(PHASE7_ENTRY_FORBIDDEN, "survivor missing")
    if phase6_status != REQUIRED_PHASE6_STATUS:
        raise Phase7EntryGateError(
            PHASE7_ENTRY_FORBIDDEN,
            f"phase6_status must be {REQUIRED_PHASE6_STATUS}",
        )
    for name, value in (
        ("phase6_result_sha256", phase6_result_sha256),
        ("validation_report_sha256", validation_report_sha256),
        ("survivor_freeze_sha256", survivor_freeze_sha256),
        ("survivor_rehearsal_sha256", survivor_rehearsal_sha256),
    ):
        if not _is_hex64(value):
            raise Phase7EntryGateError(PHASE7_ENTRY_FORBIDDEN, f"{name} invalid")

    payload: dict = {
        "schema_version": GENERATION2_PHASE7_ENTRY_SCHEMA,
        "authority": authority,
        "generation": "GENERATION_2",
        "candidate_id": candidate_id,
        "survivor": survivor,
        "phase6_status": phase6_status,
        "phase6_result_sha256": phase6_result_sha256,
        "validation_report_sha256": validation_report_sha256,
        "survivor_freeze_sha256": survivor_freeze_sha256,
        "survivor_rehearsal_sha256": survivor_rehearsal_sha256,
    }
    payload["artifact_sha256"] = _payload_sha256(payload)

    base = Path(root) if root is not None else _repo_root() / "data" / "governance"
    base.mkdir(parents=True, exist_ok=True)
    path = base / PHASE7_ENTRY_REPORT_NAME
    if path.exists():
        raise Phase7EntryGateError(
            PHASE7_ENTRY_FORBIDDEN, f"entry artifact already exists at {path}"
        )
    try:
        with path.open("xb") as handle:
            handle.write(
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                    ensure_ascii=False,
                ).encode("utf-8")
            )
    except FileExistsError as exc:
        raise Phase7EntryGateError(
            PHASE7_ENTRY_FORBIDDEN, f"entry artifact already exists at {path}"
        ) from exc
    return payload


def verify_generation2_phase7_entry(path: Path | str) -> dict:
    """Verify a sealed Generation-2 Phase-7 entry artifact; fail closed."""
    path = Path(path)
    try:
        payload = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_TAMPERED, str(path)) from exc
    if not isinstance(payload, dict):
        raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_TAMPERED, str(path))

    if payload.get("schema_version") != GENERATION2_PHASE7_ENTRY_SCHEMA:
        raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_TAMPERED, "schema")
    if payload.get("authority") != PHASE7_ENTRY_AUTHORITY:
        raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_TAMPERED, "authority")

    claimed = payload.pop("artifact_sha256", None)
    if claimed is None or _payload_sha256(payload) != claimed:
        raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_TAMPERED, "content-hash")
    payload["artifact_sha256"] = claimed

    if not isinstance(payload.get("candidate_id"), str) or not payload["candidate_id"]:
        raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_TAMPERED, "candidate_id")
    if not isinstance(payload.get("survivor"), str) or not payload["survivor"]:
        raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_TAMPERED, "survivor")
    if payload.get("phase6_status") != REQUIRED_PHASE6_STATUS:
        raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_TAMPERED, "phase6_status")
    for name in (
        "phase6_result_sha256",
        "validation_report_sha256",
        "survivor_freeze_sha256",
        "survivor_rehearsal_sha256",
    ):
        if not _is_hex64(payload.get(name)):
            raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_TAMPERED, name)
    return payload


def evaluate_generation2_phase7_entry(
    *,
    phase6_result_path: Path | str,
    entry_artifact_path: Path | str,
    repository_root: Path | str,
) -> dict:
    """Top-level fail-closed Generation-2 Phase-7 entry gate.

    Passes only when ALL of the following hold, in order:

    1. the real Phase-6 result validates under the Checkpoint-A guard
       (``assert_phase7_entry``) — status exactly
       ``PHASE6_COMPLETE_NON_DECISION_GRADE_RESEARCH_EVIDENCE``, consumed,
       ``phase7_started`` exactly ``False``, no production approval; and
    2. the explicit Generation-2 Phase-7 entry artifact exists, verifies, and
       binds the same Phase-6 candidate; and
    3. the synthetic-only CI gate evaluates green (authority flags exactly
       ``false``, holdout-exclusion registry active).

    Any violation raises :class:`Phase7EntryGateError` with a stable code.
    The gate never flips an authority flag; on success the CI gate report is
    included verbatim to prove the real-boundary flags stayed ``false``.
    """
    # 1) Real Phase-6 result, exact required status, consumed, not started.
    try:
        phase6_result = assert_phase7_entry(
            phase6_result_path=Path(phase6_result_path)
        )
    except Phase7EntryError as exc:
        raise Phase7EntryGateError(PHASE7_ENTRY_PHASE6_INVALID, str(exc)) from exc
    if phase6_result.get("status") != REQUIRED_PHASE6_STATUS:
        raise Phase7EntryGateError(
            PHASE7_ENTRY_PHASE6_INVALID,
            f"phase6_status={phase6_result.get('status')}",
        )

    # 2) Explicit Generation-2 Phase-7 entry artifact.
    artifact_path = Path(entry_artifact_path)
    if not artifact_path.exists():
        raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_MISSING, str(artifact_path))
    try:
        artifact = verify_generation2_phase7_entry(artifact_path)
    except Phase7EntryGateError as exc:
        if exc.code != PHASE7_ENTRY_ARTIFACT_TAMPERED:
            raise
        raise Phase7EntryGateError(PHASE7_ENTRY_ARTIFACT_TAMPERED, str(exc)) from exc

    if artifact.get("phase6_status") != REQUIRED_PHASE6_STATUS:
        raise Phase7EntryGateError(
            PHASE7_ENTRY_PHASE6_STATUS_MISMATCH,
            f"artifact={artifact.get('phase6_status')}",
        )
    if artifact.get("candidate_id") != phase6_result.get("candidate_id"):
        raise Phase7EntryGateError(
            PHASE7_ENTRY_CANDIDATE_MISMATCH,
            f"artifact={artifact.get('candidate_id')!r} "
            f"phase6={phase6_result.get('candidate_id')!r}",
        )

    # 3) Synthetic-only CI gate: authority flags remain exactly false.
    try:
        gate_report = ci_gate.evaluate(repository_root)
    except ci_gate.CiGateError as exc:
        raise Phase7EntryGateError(
            PHASE7_ENTRY_CI_GATE_RED, f"{exc.code}:{exc}"
        ) from exc
    if gate_report.get("status") != "PASS":
        raise Phase7EntryGateError(PHASE7_ENTRY_CI_GATE_RED, "gate status not PASS")

    return {
        "schema_version": GENERATION2_PHASE7_ENTRY_SCHEMA,
        "status": "GENERATION2_PHASE7_ENTRY_ALLOWED",
        "candidate_id": phase6_result.get("candidate_id"),
        "survivor": artifact.get("survivor"),
        "phase6_status": phase6_result.get("status"),
        "entry_artifact_sha256": artifact.get("artifact_sha256"),
        "ci_gate": gate_report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="investment-tracker-gen2-phase7-entry"
    )
    parser.add_argument(
        "--phase6-result",
        default=str(_repo_root() / "data" / "governance" / "generation2-phase6-result.json"),
        help="path to the real Phase-6 result JSON (exact success status required)",
    )
    parser.add_argument(
        "--entry-artifact",
        default=str(
            _repo_root() / "data" / "governance" / PHASE7_ENTRY_REPORT_NAME
        ),
        help="path to the explicit Generation-2 Phase-7 entry artifact",
    )
    parser.add_argument("--repository-root", default=".")
    args = parser.parse_args(argv)
    try:
        report = evaluate_generation2_phase7_entry(
            phase6_result_path=args.phase6_result,
            entry_artifact_path=args.entry_artifact,
            repository_root=args.repository_root,
        )
    except Phase7EntryGateError as exc:
        print(json.dumps({"schema_version": GENERATION2_PHASE7_ENTRY_SCHEMA,
                          "status": "FORBIDDEN", "code": exc.code,
                          "detail": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
