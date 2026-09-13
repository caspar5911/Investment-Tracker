from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping, Sequence


class Gate1IdentityError(ValueError):
    """Raised when a value cannot participate in a canonical Gate 1 identity."""


def _reject_nonfinite(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise Gate1IdentityError("canonical numeric values must be finite")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise Gate1IdentityError("canonical object keys must be strings")
            _reject_nonfinite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_nonfinite(item)


def canonical_json_bytes(payload: object) -> bytes:
    _reject_nonfinite(payload)
    try:
        return json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Gate1IdentityError("payload is not canonical JSON") from exc


def canonical_sha256(payload: object) -> str:
    return sha256(canonical_json_bytes(payload)).hexdigest()


def _portable_relative_path(path: str) -> str:
    posix = PurePosixPath(path)
    windows = PureWindowsPath(path)
    if (
        not path
        or "\\" in path
        or path.startswith("/")
        or windows.drive
        or windows.is_absolute()
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise Gate1IdentityError("path must be portable repository-relative POSIX")
    return posix.as_posix()


def normalize_repository_path(repository_root: Path, path: Path) -> str:
    repository = Path(repository_root).resolve(strict=True)
    raw_path = str(path)
    if PureWindowsPath(raw_path).drive and not Path(path).is_absolute():
        raise Gate1IdentityError("path must be portable repository-relative POSIX")
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = repository / candidate
    resolved = candidate.resolve(strict=False)
    try:
        relative = resolved.relative_to(repository)
    except ValueError as exc:
        raise Gate1IdentityError("path is outside repository") from exc
    return _portable_relative_path(relative.as_posix())


def _require_sha256(value: str, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise Gate1IdentityError(f"{field} must be 64 lowercase hexadecimal digits")
    return value


def artifact_envelope_identity(
    *, content_sha256: str, kind: str, path: str
) -> str:
    return canonical_sha256(
        {
            "content_sha256": _require_sha256(content_sha256, "content_sha256"),
            "kind": kind,
            "path": _portable_relative_path(path),
        }
    )


def source_identity(bibliographic_identity: Mapping[str, object]) -> str:
    return f"source-{canonical_sha256(dict(bibliographic_identity))}"


def hypothesis_identity(semantic_payload: Mapping[str, object]) -> str:
    return f"phase4-hypothesis-{canonical_sha256(dict(semantic_payload))}"


def family_identity(semantic_payload: Mapping[str, object]) -> str:
    return f"phase4-family-{canonical_sha256(dict(semantic_payload))}"


def candidate_identity(
    *,
    campaign_id: str,
    hypothesis_id: str,
    family_id: str,
    parameters: Mapping[str, object],
) -> str:
    return "phase4-" + canonical_sha256(
        {
            "campaign_id": campaign_id,
            "hypothesis_id": hypothesis_id,
            "family_id": family_id,
            "parameters": dict(parameters),
        }
    )


def trial_identity(campaign_id: str, candidate_id: str) -> str:
    return canonical_sha256(
        {"campaign_id": campaign_id, "candidate_id": candidate_id}
    )


def _canonical_parameter_value(value: object) -> dict[str, object]:
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise Gate1IdentityError("float parameters must be finite")
        return {"type": "float64_hex", "value": value.hex()}
    if isinstance(value, str):
        return {"type": "string", "value": value}
    raise Gate1IdentityError(f"unsupported parameter type: {type(value).__name__}")


def canonical_parameter_map(
    parameters: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    if any(not isinstance(name, str) or not name for name in parameters):
        raise Gate1IdentityError("parameter names must be non-empty strings")
    return {
        name: _canonical_parameter_value(parameters[name])
        for name in sorted(parameters)
    }


RULE_SET_FIELDS = (
    "input_fields",
    "warmup_rule",
    "signal_algorithm",
    "ranking_algorithm",
    "allocation_algorithm",
    "cash_rule",
    "risk_rule",
    "rebalance_rule",
    "execution_timing_rule",
    "long_only_no_leverage_invariants",
    "regime_partition_algorithm",
    "implementation_interface",
)


def rule_set_identity(family_id: str, family_definition: Mapping[str, object]) -> str:
    missing = tuple(field for field in RULE_SET_FIELDS if field not in family_definition)
    if missing:
        raise Gate1IdentityError(f"rule-set fields are missing: {', '.join(missing)}")
    payload = {
        "schema_version": "PHASE4-RULE-SET-IDENTITY-v1",
        "family_id": family_id,
        **{field: family_definition[field] for field in RULE_SET_FIELDS},
    }
    return canonical_sha256(payload)


def parameter_tuple_identity(
    family_id: str, parameters: Mapping[str, object]
) -> str:
    return canonical_sha256(
        {
            "schema_version": "PHASE4-PARAMETER-TUPLE-IDENTITY-v1",
            "family_id": family_id,
            "parameters": dict(parameters),
        }
    )


def candidate_parameter_population_identity(
    rows: Sequence[Mapping[str, str]],
) -> str:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if set(row) != {"candidate_id", "parameter_tuple_sha256"}:
            raise Gate1IdentityError("population row has unexpected fields")
        candidate_id = row["candidate_id"]
        if candidate_id in seen:
            raise Gate1IdentityError("duplicate candidate in parameter population")
        seen.add(candidate_id)
        normalized.append(
            {
                "candidate_id": candidate_id,
                "parameter_tuple_sha256": _require_sha256(
                    row["parameter_tuple_sha256"], "parameter_tuple_sha256"
                ),
            }
        )
    return canonical_sha256(normalized)
