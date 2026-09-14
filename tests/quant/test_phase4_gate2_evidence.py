from __future__ import annotations

import inspect

import pytest

try:
    from investment_tracker.quant.phase4.engine.evidence import (
        case_executable,
        evaluation_case_identity,
        evaluation_context_identity,
    )
    from investment_tracker.quant.phase4.engine.models import (
        Gate2EvaluationContext,
        Gate2EvidenceRecord,
        UnavailableStatistics,
    )

    _EVIDENCE_IMPORT_ERROR: Exception | None = None
except (ImportError, AttributeError) as exc:
    case_executable = None
    evaluation_case_identity = None
    evaluation_context_identity = None
    Gate2EvaluationContext = None
    Gate2EvidenceRecord = None
    UnavailableStatistics = None
    _EVIDENCE_IMPORT_ERROR = exc


CAMPAIGN_ID = "phase4-campaign-A"
MARKET_PANEL_SHA = "b" * 64
WARMUP_PANEL_SHA = "c" * 64
SCORED_PANEL_SHA = "d" * 64
RESET_CONFIG_SHA = "e" * 64
EXPECTED_SESSIONS_SHA = "f" * 64
FAMILY_DEFINITION_SHA = "1" * 64
RULE_SET_SHA = "2" * 64
PARAMETER_TUPLE_SHA = "3" * 64
ENGINE_IMPLEMENTATION_SHA = "4" * 64
INITIAL_CASH_HEX = float(1000.0).hex()
INITIAL_CASH_ALT_HEX = float(1000.5).hex()

# Fixed literal expectations, computed independently from the exact
# PHASE4-EVALUATION-CONTEXT-v1 / PHASE4-EVALUATION-CASE-v1 canonical payloads.
CTX_FULL = "b5463ec765d17f2cb86a4659d7044b2fc1227bdd477d591b2863cf1e2165731f"
CTX_CASH_ALT = "eeaece42f5bc7ce7547775490f91751250545a13621e7e52962cf44318be6616"
CTX_FOLD_BOUND = "c2a671e80e0baeb75b8bcb99c43a95d0401466ab6368d0e6241aa94388c8c2b1"
CTX_REGIME_BOUND = "c3b9fcefe554474d9a6072446528680d4544dc5ae01c121e9fb503f22b9bd974"
CASE_PRIMARY = "07c11298a621765e4378cdb778c7a2e241ae0e441665fe3636deca1bfc400be9"
CASE_3 = "dc36940a4929bd8bdba8788cd11228fdbc2aa072ab687a83f185ce04f8bca56d"
CASE_OTHER_CANDIDATE = "f4f7e1bb14ffbc75d225612a04915add5d56c430042cc7222a56bdda6c79ad94"
CASE_BOOTSTRAP = "7992bae3367779464caa79a451233808a9ecd43b116b317bb426f5949a426deb"
CASE_FOLD = "c61bba079ac16ea844a0ec4e16662b696a91c3a9027b31e58011a398d20e8c8b"

_SHA_VARIANTS = {
    "market_panel_sha256": "1" * 64,
    "warmup_panel_sha256": "2" * 64,
    "scored_panel_sha256": "3" * 64,
    "scored_reset_configuration_sha256": "4" * 64,
    "expected_sessions_authority_sha256": "5" * 64,
    "fold_authority_sha256": "a" * 64,
    "regime_authority_sha256": "a" * 64,
}


def _context(**overrides) -> object:
    payload = dict(
        campaign_id=CAMPAIGN_ID,
        market_panel_sha256=MARKET_PANEL_SHA,
        warmup_panel_sha256=WARMUP_PANEL_SHA,
        scored_panel_sha256=SCORED_PANEL_SHA,
        scored_reset_configuration_sha256=RESET_CONFIG_SHA,
        expected_sessions_authority_sha256=EXPECTED_SESSIONS_SHA,
        fold_authority_sha256=None,
        fold_authority_status="FOLD_AUTHORITY_MISSING",
        regime_authority_sha256=None,
        regime_authority_status="REGIME_AUTHORITY_MISSING",
        initial_cash_float64_hex=INITIAL_CASH_HEX,
        primary_friction_bps=3,
        execution_convention="COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN",
        execution_series="QFQ_NORMALIZED",
        decision_grade=False,
    )
    payload.update(overrides)
    return Gate2EvaluationContext(**payload)


def _case_kwargs(**overrides) -> dict[str, object]:
    payload = dict(
        candidate_id="phase4-candidate-0",
        family_definition_sha256=FAMILY_DEFINITION_SHA,
        rule_set_sha256=RULE_SET_SHA,
        parameter_tuple_sha256=PARAMETER_TUPLE_SHA,
        engine_implementation_sha256=ENGINE_IMPLEMENTATION_SHA,
        evaluation_context_sha256=CTX_FULL,
        evidence_kind="friction",
        case_id="PRIMARY",
    )
    payload.update(overrides)
    return payload


@pytest.fixture(autouse=True)
def require_evidence_types(request: pytest.FixtureRequest) -> None:
    if (
        request.node.name != "test_evidence_types_are_available"
        and _EVIDENCE_IMPORT_ERROR is not None
    ):
        pytest.skip("evidence types are not implemented yet")


def test_evidence_types_are_available() -> None:
    assert _EVIDENCE_IMPORT_ERROR is None
    assert inspect.isfunction(evaluation_context_identity)
    assert inspect.isfunction(evaluation_case_identity)
    assert inspect.isfunction(case_executable)
    assert inspect.isclass(Gate2EvaluationContext)
    assert inspect.isclass(Gate2EvidenceRecord)


def test_evaluation_context_identity_matches_fixed_literal() -> None:
    assert evaluation_context_identity(_context()) == CTX_FULL


@pytest.mark.parametrize(
    ("overrides", "expected"),
    (
        (dict(initial_cash_float64_hex=INITIAL_CASH_ALT_HEX), CTX_CASH_ALT),
        (
            dict(
                fold_authority_sha256="a" * 64,
                fold_authority_status="FOLD_AUTHORITY_BOUND",
            ),
            CTX_FOLD_BOUND,
        ),
        (
            dict(
                regime_authority_sha256="a" * 64,
                regime_authority_status="REGIME_AUTHORITY_BOUND",
            ),
            CTX_REGIME_BOUND,
        ),
    ),
)
def test_context_identity_is_sensitive_to_bound_and_cash_fields(
    overrides: dict[str, object], expected: str
) -> None:
    assert evaluation_context_identity(_context(**overrides)) == expected


@pytest.mark.parametrize(
    "field",
    (
        "campaign_id",
        "market_panel_sha256",
        "warmup_panel_sha256",
        "scored_panel_sha256",
        "scored_reset_configuration_sha256",
        "expected_sessions_authority_sha256",
        "fold_authority_sha256",
        "regime_authority_sha256",
        "initial_cash_float64_hex",
        "execution_convention",
        "execution_series",
        "decision_grade",
    ),
)
def test_every_context_field_changes_the_digest(field: str) -> None:
    value = _context().model_dump()[field]
    overrides: dict[str, object]
    if field in _SHA_VARIANTS:
        overrides = {field: _SHA_VARIANTS[field]}
        if field == "fold_authority_sha256":
            overrides["fold_authority_status"] = "FOLD_AUTHORITY_BOUND"
        if field == "regime_authority_sha256":
            overrides["regime_authority_status"] = "REGIME_AUTHORITY_BOUND"
    elif field == "initial_cash_float64_hex":
        overrides = {"initial_cash_float64_hex": INITIAL_CASH_ALT_HEX}
    else:
        overrides = {
            field: not value
            if isinstance(value, bool)
            else value + 1
            if isinstance(value, int)
            else value + "x"
        }
    assert evaluation_context_identity(_context(**overrides)) != CTX_FULL


def test_missing_fold_and_regime_states_cannot_execute_their_cases() -> None:
    assert (
        case_executable(
            "fold",
            fold_authority_status="FOLD_AUTHORITY_MISSING",
            regime_authority_status="REGIME_AUTHORITY_MISSING",
        )
        is False
    )
    assert (
        case_executable(
            "regime",
            fold_authority_status="FOLD_AUTHORITY_MISSING",
            regime_authority_status="REGIME_AUTHORITY_MISSING",
        )
        is False
    )
    for kind in ("friction", "bootstrap", "neighbor", "primary"):
        assert (
            case_executable(
                kind,
                fold_authority_status="FOLD_AUTHORITY_MISSING",
                regime_authority_status="REGIME_AUTHORITY_MISSING",
            )
            is True
        )
    assert (
        case_executable(
            "fold",
            fold_authority_status="FOLD_AUTHORITY_BOUND",
            regime_authority_status="REGIME_AUTHORITY_MISSING",
        )
        is True
    )
    assert (
        case_executable(
            "regime",
            fold_authority_status="FOLD_AUTHORITY_MISSING",
            regime_authority_status="REGIME_AUTHORITY_BOUND",
        )
        is True
    )


def test_evaluation_case_identity_matches_fixed_literals() -> None:
    assert evaluation_case_identity(**_case_kwargs()) == CASE_PRIMARY
    assert evaluation_case_identity(**_case_kwargs(case_id="3")) == CASE_3
    assert (
        evaluation_case_identity(
            **_case_kwargs(candidate_id="phase4-candidate-1")
        )
        == CASE_OTHER_CANDIDATE
    )
    assert (
        evaluation_case_identity(**_case_kwargs(evidence_kind="bootstrap"))
        == CASE_BOOTSTRAP
    )
    assert (
        evaluation_case_identity(
            **_case_kwargs(evidence_kind="fold", case_id="fold-0")
        )
        == CASE_FOLD
    )


def test_identities_accept_no_metric_fields() -> None:
    context_fields = set(Gate2EvaluationContext.model_fields)
    case_parameters = set(inspect.signature(evaluation_case_identity).parameters)
    assert context_fields == {
        "campaign_id",
        "market_panel_sha256",
        "warmup_panel_sha256",
        "scored_panel_sha256",
        "scored_reset_configuration_sha256",
        "expected_sessions_authority_sha256",
        "fold_authority_sha256",
        "fold_authority_status",
        "regime_authority_sha256",
        "regime_authority_status",
        "initial_cash_float64_hex",
        "primary_friction_bps",
        "execution_convention",
        "execution_series",
        "decision_grade",
    }
    assert case_parameters == {
        "candidate_id",
        "family_definition_sha256",
        "rule_set_sha256",
        "parameter_tuple_sha256",
        "engine_implementation_sha256",
        "evaluation_context_sha256",
        "evidence_kind",
        "case_id",
    }
    forbidden = {
        "total_return",
        "benchmark_excess",
        "observed_median",
        "rank",
        "winner",
        "eligibility",
        "selection",
    }
    assert not (context_fields | case_parameters) & forbidden


def test_initial_cash_hex_must_be_a_finite_binary64_hex() -> None:
    _context()
    with pytest.raises(ValueError):
        _context(initial_cash_float64_hex=float("inf").hex())
    with pytest.raises(ValueError):
        _context(initial_cash_float64_hex="not-a-hex-float")
    with pytest.raises(ValueError):
        # Over-precise mantissa: rounds to 1.0, whose canonical hex is 0x1p+0.
        _context(initial_cash_float64_hex="0x1.00000000000001p+0")


def test_authority_statuses_are_fail_closed_literals() -> None:
    with pytest.raises(ValueError):
        _context(fold_authority_status="FOLD_AUTHORITY_MAYBE")
    with pytest.raises(ValueError):
        _context(regime_authority_status="x")


def test_context_requires_consistent_fold_and_regime_pairing() -> None:
    with pytest.raises(ValueError):
        _context(
            fold_authority_sha256="a" * 64,
            fold_authority_status="FOLD_AUTHORITY_MISSING",
        )
    with pytest.raises(ValueError):
        _context(fold_authority_status="FOLD_AUTHORITY_BOUND")
    with pytest.raises(ValueError):
        _context(
            regime_authority_sha256="a" * 64,
            regime_authority_status="REGIME_AUTHORITY_MISSING",
        )
    with pytest.raises(ValueError):
        _context(regime_authority_status="REGIME_AUTHORITY_BOUND")


def test_context_primary_friction_is_pinned_to_three_bps() -> None:
    assert _context().primary_friction_bps == 3
    for value in (0, 4, -1):
        with pytest.raises(ValueError):
            _context(primary_friction_bps=value)  # type: ignore[arg-type]


def test_evidence_context_is_frozen() -> None:
    context = _context()
    with pytest.raises(ValueError):
        context.campaign_id = "other"  # type: ignore[misc]


def _record_kwargs(**overrides) -> dict[str, object]:
    payload = dict(
        candidate_id="phase4-candidate-0",
        family_definition_sha256=FAMILY_DEFINITION_SHA,
        rule_set_sha256=RULE_SET_SHA,
        parameter_tuple_sha256=PARAMETER_TUPLE_SHA,
        engine_implementation_sha256=ENGINE_IMPLEMENTATION_SHA,
        evaluation_context_sha256=CTX_FULL,
        evaluation_case_sha256=CASE_PRIMARY,
        evidence_kind="friction",
        case_id="PRIMARY",
        unavailable_statistics=UnavailableStatistics(),
    )
    payload.update(overrides)
    return payload


def test_evidence_record_rejects_forbidden_fields() -> None:
    for field in ("rank", "winner", "eligibility", "selection", "total_return"):
        with pytest.raises(ValueError):
            Gate2EvidenceRecord(**_record_kwargs(**{field: 1}))
    with pytest.raises(ValueError):
        Gate2EvidenceRecord(
            **{k: v for k, v in _record_kwargs().items() if k != "unavailable_statistics"}
        )


def test_evidence_record_requires_consistent_case_identity() -> None:
    record = Gate2EvidenceRecord(**_record_kwargs())
    assert record.unavailable_statistics.max_drawdown_status == "UNKNOWN"
    assert record.unavailable_statistics.dsr_reason == "NOT_IMPLEMENTED"
    with pytest.raises(ValueError):
        Gate2EvidenceRecord(
            **_record_kwargs(evaluation_case_sha256="f" * 64)
        )
    with pytest.raises(ValueError):
        Gate2EvidenceRecord(**_record_kwargs(case_id="3"))
    with pytest.raises(ValueError):
        Gate2EvidenceRecord(
            **_record_kwargs(candidate_id="phase4-candidate-1")
        )


def test_evidence_record_is_frozen() -> None:
    record = Gate2EvidenceRecord(**_record_kwargs())
    with pytest.raises(ValueError):
        record.case_id = "3"  # type: ignore[misc]
