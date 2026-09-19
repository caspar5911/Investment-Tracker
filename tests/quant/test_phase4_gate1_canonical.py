from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_tracker.quant.phase4.preregistration.canonical import (
    Gate1IdentityError,
    artifact_envelope_identity,
    candidate_identity,
    candidate_parameter_population_identity,
    canonical_json_bytes,
    canonical_parameter_map,
    canonical_sha256,
    family_identity,
    hypothesis_identity,
    normalize_repository_path,
    parameter_tuple_identity,
    rule_set_identity,
    source_identity,
    trial_identity,
)
from investment_tracker.quant.phase4.preregistration.models import (
    Gate1ArtifactIdentity,
)


def _sha(payload: object) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _rule_fields() -> dict[str, object]:
    return {
        "input_fields": ["close"],
        "warmup_rule": {"earlier_train_for_lagged_indicators_only": True},
        "signal_algorithm": {"kind": "trailing_return", "lagged": True},
        "ranking_algorithm": {"kind": "descending", "tie": "symbol"},
        "allocation_algorithm": {"kind": "equal_weight"},
        "cash_rule": {"when_no_asset": "cash"},
        "risk_rule": {"maximum_gross_exposure": "0x1.0000000000000p+0"},
        "rebalance_rule": {"anchor": "first_validation_session"},
        "execution_timing_rule": {"signal": "t", "fill": "next_eligible"},
        "long_only_no_leverage_invariants": {
            "long_only": True,
            "maximum_gross_exposure": "0x1.0000000000000p+0",
        },
        "regime_partition_algorithm": {"kind": "lagged_sign"},
        "implementation_interface": "PHASE4-MULTIASSET-STRATEGY-v1",
    }


def test_canonical_json_is_compact_sorted_utf8_and_rejects_nonfinite() -> None:
    assert canonical_json_bytes({"z": "é", "a": [True, None]}) == (
        b'{"a":[true,null],"z":"\xc3\xa9"}'
    )
    assert canonical_sha256({"b": 2, "a": 1}) == _sha({"a": 1, "b": 2})

    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(Gate1IdentityError, match="finite"):
            canonical_json_bytes({"value": value})


def test_repository_paths_are_portable_relative_and_contained(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    path = repository / "results" / "evidence.json"

    assert normalize_repository_path(repository, path) == "results/evidence.json"

    with pytest.raises(Gate1IdentityError, match="outside repository"):
        normalize_repository_path(repository, tmp_path / "outside.json")
    with pytest.raises(Gate1IdentityError, match="outside repository"):
        normalize_repository_path(repository, Path("C:\\escape.json"))


def test_artifact_identity_uses_content_kind_and_exact_normalized_path() -> None:
    content_sha256 = sha256(b"exact bytes").hexdigest()
    envelope = {
        "content_sha256": content_sha256,
        "kind": "survivor_policy",
        "path": "results/phase4/gate1/policy.json",
    }

    assert artifact_envelope_identity(**envelope) == _sha(envelope)
    assert artifact_envelope_identity(**envelope) != content_sha256
    with pytest.raises(Gate1IdentityError, match="portable"):
        artifact_envelope_identity(
            content_sha256=content_sha256,
            kind="survivor_policy",
            path="C:\\escape.json",
        )


def test_domain_identities_have_exact_canonical_formulas() -> None:
    bibliography = {
        "authors": ["A", "B"],
        "canonical_url": "https://doi.org/10.example/example",
        "title": "Evidence",
        "year": 2020,
    }
    hypothesis = {"mechanism": "underreaction", "signal": "momentum"}
    family = {"hypothesis_id": "h-1", "signal_algorithm": {"kind": "rank"}}
    parameters = canonical_parameter_map({"lookback": 126, "gate": True})

    assert source_identity(bibliography) == f"source-{_sha(bibliography)}"
    assert hypothesis_identity(hypothesis) == f"phase4-hypothesis-{_sha(hypothesis)}"
    assert family_identity(family) == f"phase4-family-{_sha(family)}"

    candidate_payload = {
        "campaign_id": "phase4-campaign-v1",
        "hypothesis_id": hypothesis_identity(hypothesis),
        "family_id": family_identity(family),
        "parameters": parameters,
    }
    candidate_id = candidate_identity(**candidate_payload)
    assert candidate_id == f"phase4-{_sha(candidate_payload)}"
    assert trial_identity("phase4-campaign-v1", candidate_id) == _sha(
        {"campaign_id": "phase4-campaign-v1", "candidate_id": candidate_id}
    )


def test_parameter_map_is_type_tagged_sorted_and_float_exact() -> None:
    parameters = canonical_parameter_map(
        {"weight": 0.25, "enabled": True, "lookback": 63, "mode": "rank"}
    )

    assert tuple(parameters) == ("enabled", "lookback", "mode", "weight")
    assert parameters == {
        "enabled": {"type": "bool", "value": True},
        "lookback": {"type": "int", "value": "63"},
        "mode": {"type": "string", "value": "rank"},
        "weight": {"type": "float64_hex", "value": "0x1.0000000000000p-2"},
    }

    with pytest.raises(Gate1IdentityError, match="unsupported parameter"):
        canonical_parameter_map({"bad": [1, 2]})
    with pytest.raises(Gate1IdentityError, match="finite"):
        canonical_parameter_map({"bad": float("nan")})


def test_fixed_rule_and_tuple_identities_change_only_for_semantic_inputs() -> None:
    family_id = "phase4-family-" + "a" * 64
    fields = _rule_fields()
    decorated = {
        **fields,
        "human_name": "ignored label",
        "recorded_at": "2026-09-13T00:00:00.000000Z",
        "observed_metrics": {"cagr": 99.0},
    }
    expected_rule_payload = {
        "schema_version": "PHASE4-RULE-SET-IDENTITY-v1",
        "family_id": family_id,
        **fields,
    }

    original = rule_set_identity(family_id, decorated)
    relabeled = rule_set_identity(
        family_id,
        {**decorated, "human_name": "another", "observed_metrics": {"cagr": -1}},
    )
    changed = rule_set_identity(
        family_id,
        {**decorated, "signal_algorithm": {"kind": "different", "lagged": True}},
    )

    assert original == _sha(expected_rule_payload)
    assert relabeled == original
    assert changed != original

    tuple_one = canonical_parameter_map({"lookback": 126, "weight": 0.5})
    tuple_two = canonical_parameter_map({"lookback": 252, "weight": 0.5})
    identity_one = parameter_tuple_identity(family_id, tuple_one)
    assert identity_one == _sha(
        {
            "schema_version": "PHASE4-PARAMETER-TUPLE-IDENTITY-v1",
            "family_id": family_id,
            "parameters": tuple_one,
        }
    )
    assert parameter_tuple_identity(family_id, tuple_two) != identity_one


def test_candidate_parameter_population_identity_preserves_order_and_uniqueness() -> None:
    rows = (
        {"candidate_id": "phase4-a", "parameter_tuple_sha256": "1" * 64},
        {"candidate_id": "phase4-b", "parameter_tuple_sha256": "2" * 64},
    )

    assert candidate_parameter_population_identity(rows) == _sha(list(rows))
    assert candidate_parameter_population_identity(tuple(reversed(rows))) != _sha(
        list(rows)
    )

    with pytest.raises(Gate1IdentityError, match="duplicate candidate"):
        candidate_parameter_population_identity((rows[0], rows[0]))


def test_artifact_model_recomputes_envelope_and_is_frozen() -> None:
    content_sha256 = sha256(b"payload").hexdigest()
    payload = {
        "content_sha256": content_sha256,
        "kind": "durability_policy",
        "path": "results/phase4/gate1/durability/policy.json",
    }
    identity = Gate1ArtifactIdentity(
        **payload,
        sha256=artifact_envelope_identity(**payload),
    )
    assert identity.kind == "durability_policy"

    with pytest.raises(ValidationError):
        Gate1ArtifactIdentity(
            **payload,
            sha256="0" * 64,
        )
    with pytest.raises(ValidationError):
        Gate1ArtifactIdentity(
            **payload,
            sha256=artifact_envelope_identity(**payload),
            unexpected=True,
        )
    with pytest.raises(ValidationError):
        identity.kind = "survivor_policy"  # type: ignore[misc]
