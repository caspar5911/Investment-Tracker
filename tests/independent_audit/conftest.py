"""Internally consistent, local-only Phase-7 authorization evidence."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest


REPO = Path(__file__).resolve().parents[2]
GOVERNANCE = Path("data/governance/successor")
SOURCE_PATHS = {
    "evaluation_module_sha256": Path("src/investment_tracker/independent_audit/post_generation3/phase7_evaluation.py"),
    "evaluation_cli_sha256": Path("src/investment_tracker/independent_audit/post_generation3/phase7_evaluation_cli.py"),
    "durability_module_sha256": Path("src/investment_tracker/quant/phase7/generation4_durability.py"),
    "data_boundary_module_sha256": Path("src/investment_tracker/independent_audit/post_generation3/phase7_data.py"),
}


def file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@dataclass
class BoundEvidence:
    root: Path
    authorization: dict
    paths: dict[str, Path]

    def auth(self, **overrides):
        return {**self.authorization, **overrides}

    def auth_path(self, **overrides) -> Path:
        path = self.root / GOVERNANCE / f"synthetic-evaluation-{uuid4().hex}.json"
        write_json(path, self.auth(**overrides))
        return path


@pytest.fixture
def bound_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BoundEvidence:
    """A synthetic Git freeze and actual hashed copies of public governance files."""
    from investment_tracker.independent_audit.post_generation3 import phase7_data

    paths: dict[str, Path] = {}
    for name, filename in {
        "start_artifact": "generation4-phase7-start.json",
        "start_contract": "generation4-phase7-start-contract.json",
        "entry_authorization": "generation4-phase7-entry-authorization.json",
    }.items():
        target = tmp_path / GOVERNANCE / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / GOVERNANCE / filename, target)
        paths[name] = target

    for field, relative in SOURCE_PATHS.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"synthetic frozen source: {field}\n".encode())
        paths[field] = target

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", *[str(p) for p in SOURCE_PATHS.values()]], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=Synthetic Test", "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "freeze synthetic Phase-7 sources"],
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    contract = json.loads((REPO / GOVERNANCE / "generation4-phase7-evaluation-contract.json").read_text(encoding="utf-8"))
    contract["phase7_evaluation_implementation_commit"] = commit
    contract["phase7_evaluation_source_sha256"] = file_sha(paths["evaluation_module_sha256"])
    contract["phase7_evaluation_cli_source_sha256"] = file_sha(paths["evaluation_cli_sha256"])
    contract["phase7_durability_source_sha256"] = file_sha(paths["durability_module_sha256"])
    contract["phase7_data_boundary_source_sha256"] = file_sha(paths["data_boundary_module_sha256"])
    contract_path = tmp_path / GOVERNANCE / "generation4-phase7-evaluation-contract.json"
    write_json(contract_path, contract)
    paths["evaluation_contract"] = contract_path

    request = json.loads((REPO / GOVERNANCE / "generation4-phase7-evaluation-independent-audit-request.json").read_text(encoding="utf-8"))
    request["frozen_evaluation_implementation_commit"] = commit
    for field in SOURCE_PATHS:
        request[field] = file_sha(paths[field])
    request["evaluation_contract_sha256"] = file_sha(contract_path)
    request_path = tmp_path / GOVERNANCE / "generation4-phase7-evaluation-independent-audit-request.json"
    write_json(request_path, request)
    paths["audit_request"] = request_path

    authorization = {
        **{key: value for key, value in request.items() if key not in {"schema_version", "status", "authority", "generation", "phase7_performance_evaluation_authorized"}},
        "schema_version": "GENERATION4-PHASE7-EVALUATION-AUTHORIZATION-v1",
        "status": "GENERATION4_PHASE7_EVALUATION_AUTHORIZED",
        "authority": "INDEPENDENT_AUDIT",
        "authorization_id": "SYNTHETIC-GEN4-PHASE7-EVALUATION-0001",
        "approved_at_utc": "2026-09-28T00:00:00Z",
        "audit_request_sha256": file_sha(request_path),
        "phase7_performance_evaluation_authorized": True,
    }
    monkeypatch.setattr(phase7_data, "_REPO_ROOT", tmp_path, raising=False)
    return BoundEvidence(tmp_path, authorization, paths)
